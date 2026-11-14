"""Paths and settings. Everything that points outside this repo is read-only."""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
load_dotenv(REPO / ".env")

# The existing batch lakehouse. We only ever read from it.
TAXI_AWS_DIR = (REPO / os.getenv("TAXI_AWS_DIR", "../nyc-taxi-aws")).resolve()
RAW_DIR = TAXI_AWS_DIR / "raw"
ICEBERG_WAREHOUSE = TAXI_AWS_DIR / "data" / "lake" / "iceberg"

DATA_DIR = REPO / "data"                      # gitignored; rebuilt by `make setups`
RAW_DB = DATA_DIR / "raw.duckdb"              # setup 1
WAREHOUSE_DB = DATA_DIR / "warehouse.duckdb"  # setups 2, 3, 4 (built by dbt)

DBT_DIR = REPO / "dbt" / "taxi_copilot"
DBT_PROFILES_DIR = DBT_DIR / "profiles"
SEMANTIC_MANIFEST = DBT_DIR / "target" / "semantic_manifest.json"
DBT_MANIFEST = DBT_DIR / "target" / "manifest.json"
ZONE_LOOKUP_CSV = DBT_DIR / "seeds" / "taxi_zone_lookup.csv"

CLEANING_RULES = REPO / "knowledge" / "cleaning_rules.yml"
RESULTS_DIR = REPO / "results"

QUERY_TIMEOUT_SECONDS = float(os.getenv("QUERY_TIMEOUT_SECONDS", "60"))
MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", "1000"))


def dbt_env() -> dict:
    """Environment for dbt and MetricFlow subprocesses."""
    env = dict(os.environ)
    env["ICEBERG_WAREHOUSE"] = str(ICEBERG_WAREHOUSE)
    env["DBT_PROFILES_DIR"] = str(DBT_PROFILES_DIR)
    env["COPILOT_WAREHOUSE"] = str(WAREHOUSE_DB)
    env["PATH"] = f"{REPO / '.venv' / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    return env
