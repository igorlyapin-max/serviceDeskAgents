from __future__ import annotations

import copy
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .action_gates import DEFAULT_STATE_DB_PATH, utc_now
from .contracts import ContractRegistry


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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

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
