from __future__ import annotations

import base64
import json
import os
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.hashes import SHA256

from apps.orchestrator.app.contracts import ContractRegistry
from apps.orchestrator.app.security import CallbackTokenInvalid, SecurityManager


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def jwt_part(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return b64url(raw)


def unsigned_jwt(claims: dict) -> str:
    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(claims)}."


def part(payload: dict) -> str:
    return jwt_part(payload)


def rsa_jwk(private_key: rsa.RSAPrivateKey, *, kid: str = "test-key-1") -> dict:
    numbers = private_key.public_key().public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "kid": kid,
        "alg": "RS256",
        "n": b64url(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
        "e": b64url(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
    }


def signed_rs256_jwt(private_key: rsa.RSAPrivateKey, claims: dict, *, kid: str = "test-key-1") -> str:
    signing_input = f"{jwt_part({'alg': 'RS256', 'typ': 'JWT', 'kid': kid})}.{jwt_part(claims)}"
    signature = private_key.sign(signing_input.encode("ascii"), padding.PKCS1v15(), SHA256())
    return f"{signing_input}.{b64url(signature)}"


class SecurityCallbackTokenTest(unittest.TestCase):
    def test_local_callback_uses_global_token_fallback(self) -> None:
        manager = SecurityManager(ContractRegistry())
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "local",
                "INTEGRATION_CALLBACK_TOKEN": "global-token",
            },
            clear=True,
        ):
            context = manager.callback_context(
                {"x-servicedesk-callback-token": "global-token"},
                endpoint_id="provider_ops",
            )

        self.assertEqual(context.actor_id, "endpoint:provider_ops")

    def test_shared_callback_requires_source_specific_token(self) -> None:
        manager = SecurityManager(ContractRegistry())
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "shared",
                "INTEGRATION_CALLBACK_TOKEN": "global-token",
            },
            clear=True,
        ):
            with self.assertRaises(CallbackTokenInvalid):
                manager.callback_context(
                    {"x-servicedesk-callback-token": "global-token"},
                    endpoint_id="provider_ops",
                )

    def test_source_specific_callback_token_is_accepted(self) -> None:
        manager = SecurityManager(ContractRegistry())
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "shared",
                "INTEGRATION_CALLBACK_TOKEN__PROVIDER_OPS": "source-token",
            },
            clear=True,
        ):
            context = manager.callback_context(
                {"x-servicedesk-callback-token": "source-token"},
                endpoint_id="provider_ops",
            )

        self.assertEqual(context.actor_id, "endpoint:provider_ops")

    def test_oidc_proxy_callback_validates_claims(self) -> None:
        manager = SecurityManager(ContractRegistry())
        token = unsigned_jwt(
            {
                "iss": "https://idp.example",
                "aud": "servicedesk-callbacks",
                "exp": int(time.time()) + 300,
                "client_id": "mcp-provider-ops",
                "scope": "servicedesk.external_events.write",
            }
        )
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "shared",
                "SECURITY_CALLBACK_AUTH_MODE": "oidc_proxy_jwt",
                "CALLBACK_OIDC_ISSUER": "https://idp.example",
                "CALLBACK_OIDC_AUDIENCE": "servicedesk-callbacks",
                "CALLBACK_OIDC_ALLOWED_CLIENT_IDS": "mcp-provider-ops",
                "CALLBACK_OIDC_PROXY_TRUST_HEADER": "X-Trusted-Callback",
                "CALLBACK_OIDC_PROXY_TRUST_HEADER_VALUE": "proxy-ok",
            },
            clear=True,
        ):
            context = manager.callback_context(
                {
                    "authorization": f"Bearer {token}",
                    "X-Trusted-Callback": "proxy-ok",
                },
                endpoint_id="mcp.provider_ops",
            )

        self.assertEqual(context.auth_mode, "oidc_proxy_jwt")
        self.assertEqual(context.actor_id, "endpoint:mcp.provider_ops:mcp-provider-ops")

    def test_oidc_proxy_callback_rejects_unsigned_claims_without_trusted_proxy(self) -> None:
        manager = SecurityManager(ContractRegistry())
        token = unsigned_jwt(
            {
                "iss": "https://idp.example",
                "aud": "servicedesk-callbacks",
                "exp": int(time.time()) + 300,
                "client_id": "mcp-provider-ops",
                "scope": "servicedesk.external_events.write",
            }
        )
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "shared",
                "SECURITY_CALLBACK_AUTH_MODE": "oidc_proxy_jwt",
                "CALLBACK_OIDC_ISSUER": "https://idp.example",
                "CALLBACK_OIDC_AUDIENCE": "servicedesk-callbacks",
                "CALLBACK_OIDC_ALLOWED_CLIENT_IDS": "mcp-provider-ops",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(CallbackTokenInvalid, "доверенный proxy"):
                manager.callback_context(
                    {"authorization": f"Bearer {token}"},
                    endpoint_id="mcp.provider_ops",
                )

    def test_oidc_proxy_callback_rejects_wrong_audience(self) -> None:
        manager = SecurityManager(ContractRegistry())
        token = unsigned_jwt(
            {
                "iss": "https://idp.example",
                "aud": "wrong-audience",
                "exp": int(time.time()) + 300,
                "client_id": "mcp-provider-ops",
                "scope": "servicedesk.external_events.write",
            }
        )
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "shared",
                "SECURITY_CALLBACK_AUTH_MODE": "oidc_proxy_jwt",
                "CALLBACK_OIDC_ISSUER": "https://idp.example",
                "CALLBACK_OIDC_AUDIENCE": "servicedesk-callbacks",
                "CALLBACK_OIDC_ALLOWED_CLIENT_IDS": "mcp-provider-ops",
                "CALLBACK_OIDC_PROXY_TRUSTED_IPS": "10.20.30.0/24",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(CallbackTokenInvalid, "audience"):
                manager.callback_context(
                    {"authorization": f"Bearer {token}"},
                    endpoint_id="mcp.provider_ops",
                    ip_address="10.20.30.40",
                )

    def test_oidc_jwks_callback_verifies_rs256_signature_and_claims(self) -> None:
        manager = SecurityManager(ContractRegistry())
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = signed_rs256_jwt(
            private_key,
            {
                "iss": "https://idp.example",
                "aud": ["servicedesk-callbacks"],
                "exp": int(time.time()) + 300,
                "client_id": "mcp-provider-ops",
                "scope": "servicedesk.external_events.write",
            },
        )
        jwks = {"keys": [rsa_jwk(private_key)]}

        with (
            patch.dict(
                os.environ,
                {
                    "APP_ENV": "shared",
                    "SECURITY_CALLBACK_AUTH_MODE": "oidc_jwks",
                    "CALLBACK_OIDC_ISSUER": "https://idp.example",
                    "CALLBACK_OIDC_AUDIENCE": "servicedesk-callbacks",
                    "CALLBACK_OIDC_ALLOWED_CLIENT_IDS": "mcp-provider-ops",
                    "CALLBACK_OIDC_JWKS_URL": "https://idp.example/.well-known/jwks.json",
                },
                clear=True,
            ),
            patch(
                "apps.orchestrator.app.security.urlopen_with_retry",
                return_value=json.dumps(jwks).encode("utf-8"),
            ),
        ):
            context = manager.callback_context(
                {"authorization": f"Bearer {token}"},
                endpoint_id="mcp.provider_ops",
            )

        self.assertEqual(context.auth_mode, "oidc_jwks")
        self.assertEqual(context.actor_id, "endpoint:mcp.provider_ops:mcp-provider-ops")

    def test_oidc_jwks_callback_rejects_invalid_signature(self) -> None:
        manager = SecurityManager(ContractRegistry())
        trusted_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = signed_rs256_jwt(
            attacker_key,
            {
                "iss": "https://idp.example",
                "aud": "servicedesk-callbacks",
                "exp": int(time.time()) + 300,
                "client_id": "mcp-provider-ops",
                "scope": "servicedesk.external_events.write",
            },
        )
        jwks = {"keys": [rsa_jwk(trusted_key)]}

        with (
            patch.dict(
                os.environ,
                {
                    "APP_ENV": "shared",
                    "SECURITY_CALLBACK_AUTH_MODE": "oidc_jwks",
                    "CALLBACK_OIDC_ISSUER": "https://idp.example",
                    "CALLBACK_OIDC_AUDIENCE": "servicedesk-callbacks",
                    "CALLBACK_OIDC_ALLOWED_CLIENT_IDS": "mcp-provider-ops",
                    "CALLBACK_OIDC_JWKS_URL": "https://idp.example/.well-known/jwks.json",
                },
                clear=True,
            ),
            patch(
                "apps.orchestrator.app.security.urlopen_with_retry",
                return_value=json.dumps(jwks).encode("utf-8"),
            ),
        ):
            with self.assertRaisesRegex(CallbackTokenInvalid, "подпись"):
                manager.callback_context(
                    {"authorization": f"Bearer {token}"},
                    endpoint_id="mcp.provider_ops",
                )


if __name__ == "__main__":
    unittest.main()
