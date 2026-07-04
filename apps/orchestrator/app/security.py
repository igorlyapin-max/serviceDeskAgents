from __future__ import annotations

import base64
import copy
import ipaddress
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.request import Request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.hashes import SHA256, SHA384, SHA512

from .action_gates import DEFAULT_STATE_DB_PATH, utc_now
from .contracts import ContractRegistry
from .http_client import urlopen_with_retry
from .runtime_guardrails import is_non_local_environment


SENSITIVE_DETAIL_KEY_MARKERS = (
    "secret",
    "token",
    "password",
    "passwd",
    "pwd",
    "key",
    "apikey",
    "api_key",
    "credential",
    "credentials",
    "authorization",
    "auth",
    "bearer",
    "секрет",
    "токен",
    "пароль",
    "ключ",
    "учетн",
    "учётн",
    "доступ",
    "авторизац",
    "аутентиф",
    "автентиф",
)

OIDC_JWKS_ALGORITHMS = {
    "RS256": (padding.PKCS1v15(), SHA256),
    "RS384": (padding.PKCS1v15(), SHA384),
    "RS512": (padding.PKCS1v15(), SHA512),
}


class PermissionDenied(PermissionError):
    pass


class RateLimitExceeded(RuntimeError):
    pass


class CallbackTokenInvalid(PermissionError):
    pass


@dataclass(frozen=True)
class SecurityContext:
    actor_id: str
    display_name: str
    roles: tuple[str, ...]
    permissions: frozenset[str]
    session_id: str | None
    auth_mode: str
    ip_address: str | None = None
    request_id: str | None = None

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def as_dict(self) -> dict[str, Any]:
        result = {
            "schema_version": "1.0",
            "actor_id": self.actor_id,
            "display_name": self.display_name,
            "roles": list(self.roles),
            "permissions": sorted(self.permissions),
            "auth_mode": self.auth_mode,
        }
        if self.session_id:
            result["session_id"] = self.session_id
        if self.ip_address:
            result["ip_address"] = self.ip_address
        if self.request_id:
            result["request_id"] = self.request_id
        return result


class SecurityManager:
    def __init__(self, contracts: ContractRegistry):
        self.contracts = contracts
        self.catalog = contracts.security_catalog
        self.auth_mode = os.getenv("SECURITY_AUTH_MODE", self.catalog["auth_mode_default"])
        self.dev_actor = os.getenv("SECURITY_DEV_ACTOR", "admin-1")
        self.rate_limit_per_minute = int(os.getenv("SECURITY_RATE_LIMIT_PER_MINUTE", "600"))
        self._buckets: dict[str, tuple[float, int]] = {}
        self._jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self.permissions_by_id = {
            permission["permission_id"]: permission
            for permission in self.catalog["permissions"]
        }
        self.roles_by_id = {
            role["role_id"]: role
            for role in self.catalog["roles"]
        }
        self.users_by_id = {
            user["user_id"]: user
            for user in self.catalog["users"]
        }

    def context_from_headers(
        self,
        headers: Mapping[str, str],
        *,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> SecurityContext:
        if self.auth_mode == "disabled":
            return self._disabled_context(ip_address, request_id=request_id)

        actor_id = headers.get("x-servicedesk-actor") or self.dev_actor
        session_id = headers.get("x-servicedesk-session") or f"dev:{actor_id}"
        user = self.users_by_id.get(actor_id)
        if not user:
            raise PermissionDenied(f"Неизвестный actor: {actor_id}")
        if not user["enabled"]:
            raise PermissionDenied(f"Actor отключен: {actor_id}")
        return self._context_from_roles(
            actor_id=actor_id,
            display_name=user["display_name"],
            role_ids=user["roles"],
            session_id=session_id,
            auth_mode=self.auth_mode,
            ip_address=ip_address,
            request_id=request_id,
        )

    def callback_context(
        self,
        headers: Mapping[str, str],
        *,
        endpoint_id: str,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> SecurityContext:
        callback_auth_mode = os.getenv("SECURITY_CALLBACK_AUTH_MODE", "source_token").strip().lower()
        if callback_auth_mode == "oidc_jwks":
            return self._oidc_jwks_callback_context(
                headers,
                endpoint_id=endpoint_id,
                ip_address=ip_address,
                request_id=request_id,
            )
        if callback_auth_mode == "oidc_proxy_jwt":
            return self._oidc_proxy_callback_context(
                headers,
                endpoint_id=endpoint_id,
                ip_address=ip_address,
                request_id=request_id,
            )
        if callback_auth_mode not in {"source_token", "callback_token"}:
            raise CallbackTokenInvalid(f"Неподдерживаемый callback auth mode: {callback_auth_mode}.")
        return self._source_token_callback_context(
            headers,
            endpoint_id=endpoint_id,
            ip_address=ip_address,
            request_id=request_id,
        )

    def _source_token_callback_context(
        self,
        headers: Mapping[str, str],
        *,
        endpoint_id: str,
        ip_address: str | None,
        request_id: str | None,
    ) -> SecurityContext:
        source_token_env = self._callback_token_env_name(endpoint_id)
        expected_token = os.getenv(source_token_env)
        if not expected_token:
            if is_non_local_environment():
                raise CallbackTokenInvalid(f"Для callback source {endpoint_id} не задан {source_token_env}.")
            expected_token = os.getenv("INTEGRATION_CALLBACK_TOKEN", "dev-callback-token")
        actual_token = headers.get("x-servicedesk-callback-token")
        if expected_token and actual_token != expected_token:
            raise CallbackTokenInvalid("Callback token отсутствует или неверен.")
        return self._context_from_roles(
            actor_id=f"endpoint:{endpoint_id}",
            display_name=f"Integration endpoint {endpoint_id}",
            role_ids=["endpoint"],
            session_id=f"callback:{endpoint_id}",
            auth_mode="callback_token",
            ip_address=ip_address,
            request_id=request_id,
        )

    def _oidc_proxy_callback_context(
        self,
        headers: Mapping[str, str],
        *,
        endpoint_id: str,
        ip_address: str | None,
        request_id: str | None,
    ) -> SecurityContext:
        self._require_trusted_oidc_proxy(headers, ip_address=ip_address)
        token = self._bearer_token(headers)
        claims = self._decode_jwt_claims(token)
        return self._oidc_callback_context_from_claims(
            claims,
            endpoint_id=endpoint_id,
            ip_address=ip_address,
            request_id=request_id,
            auth_mode="oidc_proxy_jwt",
        )

    def _require_trusted_oidc_proxy(self, headers: Mapping[str, str], *, ip_address: str | None) -> None:
        trusted_ips = self._csv_env("CALLBACK_OIDC_PROXY_TRUSTED_IPS")
        if ip_address and trusted_ips and self._ip_matches_any(ip_address, trusted_ips):
            return

        header_name = os.getenv("CALLBACK_OIDC_PROXY_TRUST_HEADER", "").strip()
        header_value = os.getenv("CALLBACK_OIDC_PROXY_TRUST_HEADER_VALUE", "").strip()
        if header_name and header_value and self._header(headers, header_name) == header_value:
            return

        raise CallbackTokenInvalid(
            "oidc_proxy_jwt требует доверенный proxy: задайте CALLBACK_OIDC_PROXY_TRUSTED_IPS "
            "или CALLBACK_OIDC_PROXY_TRUST_HEADER/CALLBACK_OIDC_PROXY_TRUST_HEADER_VALUE."
        )

    def _oidc_jwks_callback_context(
        self,
        headers: Mapping[str, str],
        *,
        endpoint_id: str,
        ip_address: str | None,
        request_id: str | None,
    ) -> SecurityContext:
        token = self._bearer_token(headers)
        header, claims, signing_input, signature = self._decode_jwt_parts(token)
        self._verify_jwks_signature(header, signing_input, signature)
        return self._oidc_callback_context_from_claims(
            claims,
            endpoint_id=endpoint_id,
            ip_address=ip_address,
            request_id=request_id,
            auth_mode="oidc_jwks",
        )

    def _oidc_callback_context_from_claims(
        self,
        claims: dict[str, Any],
        *,
        endpoint_id: str,
        ip_address: str | None,
        request_id: str | None,
        auth_mode: str,
    ) -> SecurityContext:
        issuer = os.getenv("CALLBACK_OIDC_ISSUER", "").strip()
        audience = os.getenv("CALLBACK_OIDC_AUDIENCE", "").strip()
        if issuer and claims.get("iss") != issuer:
            raise CallbackTokenInvalid("Callback OIDC issuer не разрешен.")
        if audience and not self._audience_matches(claims.get("aud"), audience):
            raise CallbackTokenInvalid("Callback OIDC audience не разрешен.")
        now = int(time.time())
        try:
            exp = int(claims.get("exp"))
        except (TypeError, ValueError) as error:
            raise CallbackTokenInvalid("Callback OIDC JWT требует exp.") from error
        if exp <= now:
            raise CallbackTokenInvalid("Callback OIDC JWT истек.")
        nbf = claims.get("nbf")
        if nbf is not None:
            try:
                if int(nbf) > now + 60:
                    raise CallbackTokenInvalid("Callback OIDC JWT еще не действует.")
            except ValueError as error:
                raise CallbackTokenInvalid("Callback OIDC JWT содержит невалидный nbf.") from error
        subject = str(claims.get("sub") or "").strip()
        client_id = str(claims.get("client_id") or claims.get("azp") or "").strip()
        actor_ref = client_id or subject
        if not actor_ref:
            raise CallbackTokenInvalid("Callback OIDC JWT требует sub или client_id.")
        allowed_clients = self._csv_env("CALLBACK_OIDC_ALLOWED_CLIENT_IDS")
        if allowed_clients and actor_ref not in allowed_clients and client_id not in allowed_clients and subject not in allowed_clients:
            raise CallbackTokenInvalid("Callback OIDC client не разрешен.")
        required_scope = os.getenv("CALLBACK_OIDC_REQUIRED_SCOPE", "servicedesk.external_events.write").strip()
        if required_scope and required_scope not in self._claim_scopes(claims):
            raise CallbackTokenInvalid("Callback OIDC JWT не содержит required scope.")
        return self._context_from_roles(
            actor_id=f"endpoint:{endpoint_id}:{actor_ref}",
            display_name=f"Integration endpoint {endpoint_id}",
            role_ids=["endpoint"],
            session_id=f"callback:{endpoint_id}:{actor_ref}",
            auth_mode=auth_mode,
            ip_address=ip_address,
            request_id=request_id,
        )

    @staticmethod
    def _bearer_token(headers: Mapping[str, str]) -> str:
        authorization = SecurityManager._header(headers, "authorization")
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            raise CallbackTokenInvalid("Callback OIDC JWT требует Authorization: Bearer.")
        token = authorization[len(prefix):].strip()
        if not token:
            raise CallbackTokenInvalid("Callback OIDC JWT пуст.")
        return token

    @staticmethod
    def _decode_jwt_claims(token: str) -> dict[str, Any]:
        return SecurityManager._decode_jwt_parts(token)[1]

    @staticmethod
    def _decode_jwt_parts(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
        parts = token.split(".")
        if len(parts) != 3:
            raise CallbackTokenInvalid("Callback OIDC JWT имеет неверный формат.")
        try:
            raw_header = SecurityManager._b64url_decode(parts[0])
            raw_payload = SecurityManager._b64url_decode(parts[1])
            signature = SecurityManager._b64url_decode(parts[2])
            header = json.loads(raw_header.decode("utf-8"))
            claims = json.loads(raw_payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            raise CallbackTokenInvalid("Callback OIDC JWT payload невалиден.") from error
        if not isinstance(header, dict):
            raise CallbackTokenInvalid("Callback OIDC JWT header должен быть object.")
        if not isinstance(claims, dict):
            raise CallbackTokenInvalid("Callback OIDC JWT claims должны быть object.")
        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
        return header, claims, signing_input, signature

    @staticmethod
    def _b64url_decode(value: str) -> bytes:
        padded = value + ("=" * ((4 - len(value) % 4) % 4))
        return base64.urlsafe_b64decode(padded.encode("ascii"))

    def _verify_jwks_signature(self, header: dict[str, Any], signing_input: bytes, signature: bytes) -> None:
        alg = str(header.get("alg") or "")
        allowed_algs = self._csv_env("CALLBACK_OIDC_ALLOWED_ALGS") or {"RS256"}
        if alg not in allowed_algs:
            raise CallbackTokenInvalid("Callback OIDC JWT alg не разрешен.")
        algorithm = OIDC_JWKS_ALGORITHMS.get(alg)
        if not algorithm:
            raise CallbackTokenInvalid("Callback OIDC JWT alg не поддерживается.")
        jwks = self._callback_jwks()
        key = self._select_jwk(jwks, header)
        public_key = self._rsa_public_key_from_jwk(key)
        pad, hash_cls = algorithm
        try:
            public_key.verify(signature, signing_input, pad, hash_cls())
        except InvalidSignature as error:
            raise CallbackTokenInvalid("Callback OIDC JWT подпись невалидна.") from error

    def _callback_jwks(self) -> dict[str, Any]:
        jwks_url = os.getenv("CALLBACK_OIDC_JWKS_URL", "").strip()
        if not jwks_url:
            raise CallbackTokenInvalid("CALLBACK_OIDC_JWKS_URL обязателен для oidc_jwks callbacks.")
        cache_seconds = self._int_env("CALLBACK_OIDC_JWKS_CACHE_SECONDS", 300)
        now = time.time()
        cached = self._jwks_cache.get(jwks_url)
        if cached and now - cached[0] <= cache_seconds:
            return cached[1]
        request = Request(jwks_url, headers={"Accept": "application/json"}, method="GET")
        try:
            raw_body = urlopen_with_retry(
                request,
                timeout=self._float_env("CALLBACK_OIDC_JWKS_TIMEOUT_SECONDS", 5.0),
                operation_name="callback_oidc.jwks",
                attempts=max(1, self._int_env("CALLBACK_OIDC_JWKS_ATTEMPTS", 2)),
            )
            jwks = json.loads(raw_body.decode("utf-8"))
        except Exception as error:  # noqa: BLE001 - auth failure must not expose network internals or tokens
            raise CallbackTokenInvalid("Не удалось получить Callback OIDC JWKS.") from error
        if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
            raise CallbackTokenInvalid("Callback OIDC JWKS должен содержать keys array.")
        self._jwks_cache[jwks_url] = (now, jwks)
        return jwks

    @staticmethod
    def _select_jwk(jwks: dict[str, Any], header: dict[str, Any]) -> dict[str, Any]:
        kid = str(header.get("kid") or "").strip()
        alg = str(header.get("alg") or "").strip()
        keys = [key for key in jwks.get("keys", []) if isinstance(key, dict)]
        if kid:
            matches = [key for key in keys if str(key.get("kid") or "") == kid]
        else:
            matches = keys
        matches = [
            key for key in matches
            if str(key.get("kty") or "") == "RSA"
            and (not key.get("alg") or str(key.get("alg")) == alg)
            and (not key.get("use") or key.get("use") == "sig")
        ]
        if len(matches) != 1:
            raise CallbackTokenInvalid("Callback OIDC JWKS не содержит однозначный signing key.")
        return matches[0]

    @staticmethod
    def _rsa_public_key_from_jwk(jwk: dict[str, Any]) -> rsa.RSAPublicKey:
        try:
            modulus = int.from_bytes(SecurityManager._b64url_decode(str(jwk["n"])), "big")
            exponent = int.from_bytes(SecurityManager._b64url_decode(str(jwk["e"])), "big")
            return rsa.RSAPublicNumbers(exponent, modulus).public_key()
        except Exception as error:  # noqa: BLE001 - malformed public key
            raise CallbackTokenInvalid("Callback OIDC JWKS RSA key невалиден.") from error

    @staticmethod
    def _audience_matches(claim_audience: Any, expected: str) -> bool:
        if isinstance(claim_audience, str):
            return claim_audience == expected
        if isinstance(claim_audience, list):
            return expected in {str(item) for item in claim_audience}
        return False

    @staticmethod
    def _claim_scopes(claims: dict[str, Any]) -> set[str]:
        scopes: set[str] = set()
        scope = claims.get("scope")
        if isinstance(scope, str):
            scopes.update(item for item in scope.split() if item)
        scp = claims.get("scp")
        if isinstance(scp, str):
            scopes.update(item for item in scp.split() if item)
        elif isinstance(scp, list):
            scopes.update(str(item) for item in scp if item)
        permissions = claims.get("permissions")
        if isinstance(permissions, list):
            scopes.update(str(item) for item in permissions if item)
        return scopes

    @staticmethod
    def _csv_env(name: str) -> set[str]:
        return {item.strip() for item in os.getenv(name, "").split(",") if item.strip()}

    @staticmethod
    def _ip_matches_any(ip_address: str, allowed: set[str]) -> bool:
        try:
            candidate = ipaddress.ip_address(ip_address)
        except ValueError:
            return False
        for item in allowed:
            try:
                if "/" in item:
                    if candidate in ipaddress.ip_network(item, strict=False):
                        return True
                elif candidate == ipaddress.ip_address(item):
                    return True
            except ValueError:
                continue
        return False

    @staticmethod
    def _int_env(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _float_env(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str:
        value = headers.get(name)
        if value is not None:
            return str(value)
        lowered = name.lower()
        for key, candidate in headers.items():
            if str(key).lower() == lowered:
                return str(candidate)
        return ""

    @staticmethod
    def _callback_token_env_name(endpoint_id: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(endpoint_id or "")).strip("_").upper()
        return f"INTEGRATION_CALLBACK_TOKEN__{normalized or 'DEFAULT'}"

    def require_permission(self, context: SecurityContext, permission: str) -> None:
        if permission not in self.permissions_by_id:
            raise PermissionDenied(f"Право не зарегистрировано: {permission}")
        if not context.has_permission(permission):
            raise PermissionDenied(f"Недостаточно прав: требуется {permission}")

    def check_rate_limit(self, context: SecurityContext) -> None:
        if self.rate_limit_per_minute <= 0:
            return
        now = time.monotonic()
        window_started_at, count = self._buckets.get(context.actor_id, (now, 0))
        if now - window_started_at >= 60:
            self._buckets[context.actor_id] = (now, 1)
            return
        if count >= self.rate_limit_per_minute:
            raise RateLimitExceeded(
                f"Превышен лимит запросов: {self.rate_limit_per_minute} в минуту"
            )
        self._buckets[context.actor_id] = (window_started_at, count + 1)

    def session_info(self, context: SecurityContext) -> dict[str, Any]:
        return context.as_dict()

    def sanitized_catalog(self) -> dict[str, Any]:
        return copy.deepcopy(self.catalog)

    def secret_references(self) -> dict[str, Any]:
        references = []
        for secret in self.catalog["secret_references"]:
            item = copy.deepcopy(secret)
            if item["storage"] == "env":
                item["configured"] = bool(os.getenv(item["reference"]))
            else:
                item["configured"] = None
            references.append(item)
        return {
            "schema_version": "1.0",
            "secret_references": references,
        }

    def anonymous_context(
        self,
        *,
        actor_id: str = "anonymous",
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> SecurityContext:
        return SecurityContext(
            actor_id=actor_id,
            display_name=actor_id,
            roles=(),
            permissions=frozenset(),
            session_id=None,
            auth_mode=self.auth_mode,
            ip_address=ip_address,
            request_id=request_id,
        )

    def _context_from_roles(
        self,
        *,
        actor_id: str,
        display_name: str,
        role_ids: list[str],
        session_id: str | None,
        auth_mode: str,
        ip_address: str | None,
        request_id: str | None = None,
    ) -> SecurityContext:
        permissions: set[str] = set()
        for role_id in role_ids:
            role = self.roles_by_id[role_id]
            permissions.update(role["permissions"])
        return SecurityContext(
            actor_id=actor_id,
            display_name=display_name,
            roles=tuple(role_ids),
            permissions=frozenset(permissions),
            session_id=session_id,
            auth_mode=auth_mode,
            ip_address=ip_address,
            request_id=request_id,
        )

    def _disabled_context(self, ip_address: str | None, *, request_id: str | None = None) -> SecurityContext:
        admin_role = self.roles_by_id["admin"]
        return SecurityContext(
            actor_id="security-disabled",
            display_name="Security disabled",
            roles=("admin",),
            permissions=frozenset(admin_role["permissions"]),
            session_id="security-disabled",
            auth_mode="disabled",
            ip_address=ip_address,
            request_id=request_id,
        )


class AuditStore:
    def __init__(
        self,
        contracts: ContractRegistry,
        db_path: str | Path | None = None,
    ):
        self.contracts = contracts
        configured_path = db_path or os.getenv("ORCHESTRATOR_STATE_DB")
        self.db_path = Path(configured_path) if configured_path else DEFAULT_STATE_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def record(
        self,
        context: SecurityContext,
        *,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        permission: str | None = None,
        outcome: str = "success",
        request_method: str | None = None,
        request_path: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_details = copy.deepcopy(details or {})
        if context.request_id and "request_id" not in clean_details:
            clean_details["request_id"] = context.request_id
        event = {
            "schema_version": "1.0",
            "audit_id": f"aud-{uuid.uuid4().hex[:12]}",
            "actor_id": context.actor_id,
            "actor_roles": list(context.roles),
            "action": action,
            "resource_type": resource_type,
            "outcome": outcome,
            "created_at": utc_now(),
        }
        optional_values = {
            "session_id": context.session_id,
            "permission": permission,
            "resource_id": resource_id,
            "request_method": request_method,
            "request_path": request_path,
            "status_code": status_code,
            "ip_address": context.ip_address,
            "details": self._sanitize_details(clean_details),
        }
        for key, value in optional_values.items():
            if value not in (None, "", {}):
                event[key] = value

        self.contracts.require_valid("audit_event", event)
        with self._connect() as connection:
            connection.execute(
                """
                insert into audit_events (
                    audit_id,
                    actor_id,
                    action,
                    resource_type,
                    resource_id,
                    permission,
                    outcome,
                    request_method,
                    request_path,
                    status_code,
                    event_json,
                    created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["audit_id"],
                    event["actor_id"],
                    event["action"],
                    event["resource_type"],
                    event.get("resource_id"),
                    event.get("permission"),
                    event["outcome"],
                    event.get("request_method"),
                    event.get("request_path"),
                    event.get("status_code"),
                    self._to_json(event),
                    event["created_at"],
                ),
            )
        return event

    def list_all(
        self,
        *,
        limit: int = 100,
        outcome: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
    ) -> list[dict[str, Any]]:
        where_clauses = []
        parameters: list[Any] = []
        if outcome:
            where_clauses.append("outcome = ?")
            parameters.append(outcome)
        if actor_id:
            where_clauses.append("actor_id = ?")
            parameters.append(actor_id)
        if action:
            where_clauses.append("action = ?")
            parameters.append(action)
        where_sql = f"where {' and '.join(where_clauses)}" if where_clauses else ""
        safe_limit = min(max(limit, 0), 1000)
        parameters.append(safe_limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                select event_json
                from audit_events
                {where_sql}
                order by created_at desc, audit_id desc
                limit ?
                """,
                parameters,
            ).fetchall()
        events = [json.loads(row["event_json"]) for row in rows]
        for event in events:
            self.contracts.require_valid("audit_event", event)
        return events

    def summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            total = connection.execute("select count(*) as count from audit_events").fetchone()
            outcome_rows = connection.execute(
                """
                select outcome, count(*) as count
                from audit_events
                group by outcome
                order by outcome
                """
            ).fetchall()
            action_rows = connection.execute(
                """
                select action, count(*) as count
                from audit_events
                group by action
                order by action
                """
            ).fetchall()
            actor_rows = connection.execute(
                """
                select actor_id, count(*) as count
                from audit_events
                group by actor_id
                order by actor_id
                """
            ).fetchall()
        return {
            "schema_version": "1.0",
            "total": int(total["count"] if total else 0),
            "by_outcome": self._counts(outcome_rows, "outcome"),
            "by_action": self._counts(action_rows, "action"),
            "by_actor": self._counts(actor_rows, "actor_id"),
        }

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists audit_events (
                    audit_id text primary key,
                    actor_id text not null,
                    action text not null,
                    resource_type text not null,
                    resource_id text,
                    permission text,
                    outcome text not null,
                    request_method text,
                    request_path text,
                    status_code integer,
                    event_json text not null,
                    created_at text not null
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_audit_events_actor_id
                on audit_events(actor_id)
                """
            )
            connection.execute(
                """
                create index if not exists idx_audit_events_action
                on audit_events(action)
                """
            )
            connection.execute(
                """
                create index if not exists idx_audit_events_created_at
                on audit_events(created_at)
                """
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _counts(rows: list[sqlite3.Row], key: str) -> dict[str, int]:
        return {
            str(row[key]): int(row["count"])
            for row in rows
        }

    @classmethod
    def _sanitize_details(cls, value: Any) -> Any:
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                lowered = str(key).casefold()
                if any(marker in lowered for marker in SENSITIVE_DETAIL_KEY_MARKERS):
                    result[key] = "***"
                else:
                    result[key] = cls._sanitize_details(item)
            return result
        if isinstance(value, list):
            return [cls._sanitize_details(item) for item in value]
        return value

    @staticmethod
    def _to_json(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
