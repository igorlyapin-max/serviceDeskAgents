from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DeploymentHardeningTest(unittest.TestCase):
    def test_compose_requires_secret_environment_variables(self) -> None:
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        for variable in [
            "POSTGRES_PASSWORD",
            "N8N_DB_PASSWORD",
            "N8N_ENCRYPTION_KEY",
            "N8N_WEBHOOK_TOKEN",
            "LITELLM_MASTER_KEY",
        ]:
            self.assertIn(f"${{{variable}:?", compose)

    def test_compose_and_env_example_do_not_use_old_dev_secret_defaults(self) -> None:
        checked_text = "\n".join(
            [
                (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"),
                (REPO_ROOT / ".env.example").read_text(encoding="utf-8"),
                (REPO_ROOT / "infra/postgres/init/00-create-n8n-db.sh").read_text(encoding="utf-8"),
            ]
        )

        for weak_value in [
            "servicedesk_dev_password",
            "n8n_dev_password",
            "replace_with_32_plus_chars_dev_key",
            "replace_with_dev_webhook_token",
            "sk-dev-litellm-master-key",
        ]:
            self.assertNotIn(weak_value, checked_text)

    def test_n8n_postgres_init_uses_environment_and_blocks_node_env_access(self) -> None:
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        init_script = (REPO_ROOT / "infra/postgres/init/00-create-n8n-db.sh").read_text(encoding="utf-8")

        self.assertIn("N8N_DB_PASSWORD: ${N8N_DB_PASSWORD:?", compose)
        self.assertIn('N8N_BLOCK_ENV_ACCESS_IN_NODE: "true"', compose)
        self.assertIn('N8N_DB_PASSWORD is required', init_script)
        self.assertIn("quote_literal(:'n8n_password')", init_script)


if __name__ == "__main__":
    unittest.main()
