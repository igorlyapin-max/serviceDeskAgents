from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.orchestrator.app.cases import CaseStore
from apps.orchestrator.app.contracts import ContractRegistry


class CallbackReceiptsTest(unittest.TestCase):
    def test_callback_receipt_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = CaseStore(ContractRegistry(), db_path=Path(directory) / "state.sqlite")
            result = {
                "schema_version": "1.0",
                "accepted": True,
                "case": {"case_id": "case-test"},
                "workflow_state": {"id": "resolved"},
                "tool_result": {
                    "invocation_id": "inv-test",
                    "status": "success",
                },
            }
            store.record_callback_receipt(
                invocation_id="inv-test",
                endpoint_id="mock",
                result=result,
            )

            receipt = store.callback_receipt("inv-test")
            self.assertIsNotNone(receipt)
            self.assertEqual(receipt["invocation_id"], "inv-test")
            self.assertEqual(receipt["result"]["tool_result"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
