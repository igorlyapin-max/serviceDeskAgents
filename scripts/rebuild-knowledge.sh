#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

OPERATOR_ID="${KNOWLEDGE_REBUILD_OPERATOR:-operator-stage7}"
export OPERATOR_ID

"${PYTHON_BIN}" - <<'PY'
import json
import os

from apps.orchestrator.app.contracts import ContractRegistry
from apps.orchestrator.app.knowledge import KnowledgeIndexer

contracts = ContractRegistry()
indexer = KnowledgeIndexer(contracts)
result = indexer.rebuild(os.environ["OPERATOR_ID"])
print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
PY
