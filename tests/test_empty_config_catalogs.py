from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from apps.orchestrator.app.config_registry import CONFIG_DOMAINS, ConfigStore
from apps.orchestrator.app.contracts import ContractRegistry


COLLECTION_KEYS = {
    "service_scenarios": "scenarios",
    "slot_schemas": "slot_schemas",
    "classification_routes": "routes",
    "orchestrator_policy": "policies",
    "prompt_packs": "packs",
    "escalation_policies": "policies",
    "tools": "tools",
    "integration_endpoints": "endpoints",
    "workflow_states": "states",
    "workflow_transitions": "rules",
    "prompts": "prompts",
    "n8n_workflows": "workflows",
    "interaction_channels": "channels",
    "attribute_resolution_profiles": "profiles",
}


def empty_config_payloads(store: ConfigStore) -> dict[str, dict]:
    payloads: dict[str, dict] = {}
    for domain, collection_key in COLLECTION_KEYS.items():
        payload = copy.deepcopy(store.active_payload(domain))
        payload[collection_key] = []
        payloads[domain] = payload

    model_routing = copy.deepcopy(store.active_payload("model_routing"))
    model_routing["providers"] = {}
    model_routing["routing"] = {}
    model_routing["fallbacks"] = []
    payloads["model_routing"] = model_routing
    return payloads


class EmptyConfigCatalogsTest(unittest.TestCase):
    def test_json_schema_accepts_empty_config_catalogs(self) -> None:
        contracts = ContractRegistry()
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(contracts, db_path=Path(tempdir) / "state.sqlite")
            payloads = empty_config_payloads(store)

        for domain, payload in payloads.items():
            with self.subTest(domain=domain):
                errors = contracts.validate(CONFIG_DOMAINS[domain].contract_name, payload)
                self.assertEqual(errors, [])

    def test_config_store_accepts_consistent_empty_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            payloads = empty_config_payloads(store)

            for domain, payload in payloads.items():
                with self.subTest(domain=domain):
                    validation = store.validate_payload(domain, payload, active_overrides=payloads)
                    self.assertEqual(validation["status"], "valid", validation["errors"])


if __name__ == "__main__":
    unittest.main()
