PY := .venv/bin/python

.PHONY: install setups check profile test check-llm all gold blind eval summary api mcp try-api try-mcp langfuse-up langfuse-down try-langfuse

install:            ## create the Python 3.12 venv and install everything
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -r requirements.txt

setups:             ## build data/raw.duckdb and data/warehouse.duckdb (reads ../nyc-taxi-aws, never writes to it)
	$(PY) scripts/build_setups.py

check:              ## run one probe + attack checks on each setup -> results/phase1_setups.json
	$(PY) scripts/check_setups.py

profile:            ## raw vs cleaned numbers -> results/phase1_layer_profile.json
	$(PY) scripts/profile_layers.py

test:               ## pytest
	$(PY) -m pytest -q

check-llm:          ## one Gemini call, to prove the key works
	$(PY) scripts/check_llm.py

all: setups check profile test

gold:               ## run every gold SQL -> results/gold_answers.json
	$(PY) scripts/build_gold.py

blind:              ## gold answers for the blind set (benchmark/blind) -> results/gold_blind.json
	$(PY) scripts/build_gold.py --blind

MODEL ?= gemini-flash-lite
REPEATS ?= 1
eval:               ## run the experiment for one model (resumable): make eval MODEL=qwen-coder-7b
	$(PY) scripts/run_eval.py --model $(MODEL) --repeats $(REPEATS) $(if $(BLIND),--blind)

summary:            ## results/runs/*.jsonl -> results/summary.json + docs/RESULTS.md
	$(PY) scripts/summarise.py

api:                ## the copilot as an HTTP API on http://127.0.0.1:8000 (docs at /docs)
	$(PY) -m uvicorn copilot.api:app --host 127.0.0.1 --port 8000

mcp:                ## the copilot as an MCP server (stdio)
	$(PY) -m copilot.mcp_server

try-api:            ## needs `make api` running: 12 benchmark questions + 4 attacks over HTTP -> results/api_trial.json
	$(PY) scripts/try_api.py

try-mcp:            ## starts the MCP server over stdio and calls every tool -> results/mcp_trial.json
	$(PY) scripts/try_mcp.py

LF := docker compose --env-file langfuse/.env -f langfuse/docker-compose.yml -p taxi-langfuse
langfuse-up:        ## local self-hosted Langfuse on http://localhost:3000; the agent then sends traces there
	$(PY) scripts/langfuse_setup.py
	$(LF) up -d --wait

langfuse-down:      ## stop Langfuse (traces are kept in Docker volumes)
	$(LF) down

try-langfuse:       ## needs `make langfuse-up`: 14 agent runs, then reads the traces back -> results/langfuse_check.json
	$(PY) scripts/try_langfuse.py
