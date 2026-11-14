PY := .venv/bin/python

.PHONY: install setups check profile test check-llm all

install:            ## create the Python 3.12 venv and install everything
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -r requirements.txt

setups:             ## build data/raw.duckdb and data/warehouse.duckdb (reads ../nyc-taxi-aws, never writes to it)
	$(PY) scripts/build_setups.py

check:              ## run one probe + attack checks on each setup -> results/phase1_setups.json
	$(PY) scripts/check_setups.py

profile:            ## raw vs cleaned numbers -> results/phase1_layer_profile.json
	$(PY) scripts/profile_layers.py

test:               ## pytest (27 tests)
	$(PY) -m pytest -q

check-llm:          ## one Gemini call, to prove the key works
	$(PY) scripts/check_llm.py

all: setups check profile test
