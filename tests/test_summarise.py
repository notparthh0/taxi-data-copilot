"""Error-cause labels (RESULTS table 11). The error strings are real ones from results/runs/."""
import importlib.util

import pytest

from copilot import config

_spec = importlib.util.spec_from_file_location("summarise", config.REPO / "scripts" / "summarise.py")
summarise = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(summarise)


@pytest.mark.parametrize("error_type, error, sql, cause", [
    ("semantic_error", "Fatal Python error: init_sys_streams: can't initialize sys standard streams", "",
     "harness crash"),
    ("refusal", "There is no metric for the minimum or lowest fare amount in the semantic layer.", "",
     "refused an answerable question"),
    ("unsafe_sql", "cannot parse SQL: Parser Error: unterminated quoted identifier", "",
     "guard could not parse"),
    ("sql_error", "Binder Error: No function matches the given name and argument types 'date_part(STRING_LITERAL, INTEGER)'",
     "SELECT count(*) FROM yellow_tripdata WHERE month(tpep_pickup_datetime) = SUBSTR(source_file, 18, 2)",
     "cleaning rule 7"),
    ("sql_error", 'Conversion Error: invalid timestamp field format: "2023", expected format is (YYYY-MM-DD HH:MM[:SS])',
     "", "month written as '2023-01'"),
    ("semantic_error", "request needs at least one metric", "", "invalid request"),
    ("sql_error", 'Binder Error: Referenced column "t_pickup_datetime" not found in FROM clause!', "",
     "other SQL error"),
])
def test_error_cause(error_type, error, sql, cause):
    assert cause in summarise.error_cause({"error_type": error_type, "error": error, "sql": sql})


def test_bootstrap_interval():
    import random
    assert summarise.boot_ci([0.5] * 40, random.Random(0)) == (0.5, 0.5)
    lo, hi = summarise.boot_ci([0, 1] * 50, random.Random(0))
    assert lo < 0.5 < hi and summarise.boot_ci([0, 1] * 50, random.Random(0)) == (lo, hi)
