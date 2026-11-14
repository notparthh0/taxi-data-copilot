import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config  # noqa: E402


@pytest.fixture(scope="session")
def built():
    """Tests that touch the data need `make setups` to have been run."""
    if not (config.RAW_DB.exists() and config.WAREHOUSE_DB.exists() and config.SEMANTIC_MANIFEST.exists()):
        pytest.skip("run `make setups` first (needs ../nyc-taxi-aws data)")
