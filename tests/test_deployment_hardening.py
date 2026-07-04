from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DeploymentHardeningTest(unittest.TestCase):
    def test_compose_requires_secret_environment_variables(self) -> None:
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        for variable in [
            "POSTGRES_PASSWORD",
            "LITELLM_MASTER_KEY",
        ]:
            self.assertIn(f"${{{variable}:?", compose)

        self.assertIn("INTEGRATION_CALLBACK_TOKEN: ${INTEGRATION_CALLBACK_TOKEN:-}", compose)
        self.assertNotIn("${INTEGRATION_CALLBACK_TOKEN:?", compose)

    def test_compose_and_env_example_do_not_use_old_dev_secret_defaults(self) -> None:
        checked_text = "\n".join(
            [
                (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"),
                (REPO_ROOT / ".env.example").read_text(encoding="utf-8"),
            ]
        )

        for weak_value in [
            "servicedesk_dev_password",
            "replace_with_32_plus_chars_dev_key",
            "replace_with_dev_webhook_token",
            "sk-dev-litellm-master-key",
        ]:
            self.assertNotIn(weak_value, checked_text)

    def test_service_desk_agents_does_not_ship_in_repo_n8n_runtime(self) -> None:
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertNotIn("n8n:", compose)
        self.assertNotIn("N8N_", compose)
        n8n_dir = REPO_ROOT / "infra/n8n"
        self.assertFalse(n8n_dir.exists() and any(path.is_file() for path in n8n_dir.rglob("*")))

    def test_compose_callback_url_default_is_reachable_from_neighboring_mcp_runtime(self) -> None:
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn(
            "ORCHESTRATOR_PUBLIC_URL: ${COMPOSE_ORCHESTRATOR_PUBLIC_URL:-http://hostmachine:18088}",
            compose,
        )
        self.assertIn("COMPOSE_ORCHESTRATOR_PUBLIC_URL=http://hostmachine:18088", env_example)
        self.assertNotIn("COMPOSE_ORCHESTRATOR_PUBLIC_URL=http://orchestrator:18088", env_example)


if __name__ == "__main__":
    unittest.main()
