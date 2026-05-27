COMPOSE ?= docker compose
PYTHON ?= python3

.PHONY: stage0-config
stage0-config:
	$(COMPOSE) config

.PHONY: stage0-up
stage0-up:
	$(COMPOSE) up -d postgres redis n8n

.PHONY: stage0-llm-up
stage0-llm-up:
	$(COMPOSE) --profile llm up -d litellm vllm-cpu

.PHONY: stage1-up
stage1-up:
	$(COMPOSE) --profile llm up -d vllm-cpu litellm

.PHONY: stage1-logs
stage1-logs:
	$(COMPOSE) --profile llm logs -f vllm-cpu litellm

.PHONY: stage1-smoke
stage1-smoke:
	./scripts/stage1-smoke.sh

.PHONY: stage2-contracts
stage2-contracts:
	./scripts/validate-contracts.sh

.PHONY: stage3-install
stage3-install:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install -e .

.PHONY: stage3-check
stage3-check:
	$(PYTHON) -m compileall -q apps/orchestrator
	./scripts/validate-contracts.sh

.PHONY: stage3-run
stage3-run:
	$(PYTHON) -m uvicorn apps.orchestrator.app.main:app --host 127.0.0.1 --port $${ORCHESTRATOR_PORT:-18088}

.PHONY: stage3-smoke
stage3-smoke:
	./scripts/stage3-smoke.sh

.PHONY: stage4-check
stage4-check:
	$(PYTHON) -m compileall -q apps/orchestrator
	./scripts/validate-contracts.sh

.PHONY: stage4-smoke
stage4-smoke:
	./scripts/stage4-smoke.sh

.PHONY: stage5-check
stage5-check:
	$(PYTHON) -m compileall -q apps/orchestrator
	./scripts/validate-contracts.sh

.PHONY: stage5-smoke
stage5-smoke:
	./scripts/stage5-smoke.sh

.PHONY: stage6-check
stage6-check:
	$(PYTHON) -m compileall -q apps/orchestrator
	./scripts/validate-contracts.sh

.PHONY: stage6-smoke
stage6-smoke:
	./scripts/stage6-smoke.sh

.PHONY: stage7-index
stage7-index:
	./scripts/rebuild-knowledge.sh

.PHONY: stage7-check
stage7-check:
	$(PYTHON) -m compileall -q apps/orchestrator
	./scripts/validate-contracts.sh

.PHONY: stage7-smoke
stage7-smoke:
	./scripts/stage7-smoke.sh

.PHONY: stage8-check
stage8-check:
	$(PYTHON) -m compileall -q apps/orchestrator
	node --check apps/operator-ui/static/app.js
	./scripts/validate-contracts.sh

.PHONY: stage8-smoke
stage8-smoke:
	./scripts/stage8-smoke.sh

.PHONY: stage9-check
stage9-check:
	$(PYTHON) -m compileall -q apps/orchestrator
	node --check apps/operator-ui/static/app.js
	./scripts/validate-contracts.sh

.PHONY: stage9-smoke
stage9-smoke:
	./scripts/stage9-smoke.sh

.PHONY: stage10-check
stage10-check:
	$(PYTHON) -m compileall -q apps/orchestrator
	node --check apps/operator-ui/static/app.js
	./scripts/validate-contracts.sh

.PHONY: stage10-smoke
stage10-smoke:
	./scripts/stage10-smoke.sh

.PHONY: stage0-ps
stage0-ps:
	$(COMPOSE) ps

.PHONY: stage0-smoke
stage0-smoke:
	$(COMPOSE) ps
	$(COMPOSE) exec -T redis redis-cli ping
	$(COMPOSE) exec -T postgres psql -U servicedesk -d servicedesk -c "select extname from pg_extension where extname = 'vector';"
	curl -fsS http://127.0.0.1:$${N8N_PORT:-5678}/healthz

.PHONY: stage0-logs
stage0-logs:
	$(COMPOSE) logs --tail=200

.PHONY: stage0-down
stage0-down:
	$(COMPOSE) down
