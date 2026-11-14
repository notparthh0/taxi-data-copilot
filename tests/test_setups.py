"""The four setups run, see only their own tables, and agree where they should."""
import pytest

from copilot.setups import get_setups

SETUPS = get_setups()


def test_ladder_has_four_setups():
    from copilot.setups import LADDER
    assert LADDER == ("s1_raw", "s2_modelled", "s3_docs", "s4_semantic")
    assert set(SETUPS) == set(LADDER) | {"s1d_raw_docs"}


def test_row_counts(built):
    raw = SETUPS["s1_raw"].execute("SELECT count(*) FROM yellow_tripdata")
    clean = SETUPS["s2_modelled"].execute("SELECT count(*) FROM fct_trips")
    assert raw.rows == [[38310226]]
    assert clean.rows == [[35574647]]          # same as the Iceberg table in nyc-taxi-elt-pipeline


def test_raw_setup_cannot_see_cleaned_tables(built):
    r = SETUPS["s1_raw"].execute("SELECT count(*) FROM fct_trips")
    assert r.status == "error" and r.error_type == "sql_error"


def test_schema_only_setups_show_no_docs(built):
    assert "Documentation" not in SETUPS["s1_raw"].context()
    assert "Documentation" not in SETUPS["s2_modelled"].context()
    assert "Cleaning rules" in SETUPS["s3_docs"].context()
    assert "Cleaning rules" in SETUPS["s4_semantic"].context()


def test_sql_and_semantic_layer_agree(built):
    sql = SETUPS["s3_docs"].execute(
        "SELECT pickup_borough, avg(fare_amount) FROM fct_trips GROUP BY 1 ORDER BY 1")
    sem = SETUPS["s4_semantic"].execute(
        {"metrics": ["avg_fare"], "group_by": ["trip__pickup_borough"], "order_by": ["trip__pickup_borough"]})
    assert sql.status == sem.status == "ok"
    assert len(sql.rows) == len(sem.rows) > 0
    for (b1, v1), (b2, v2) in zip(sql.rows, sem.rows):
        assert b1 == b2 and v1 == pytest.approx(v2, rel=1e-9)


def test_semantic_errors_are_reported_not_raised(built):
    s4 = SETUPS["s4_semantic"]
    assert s4.execute({"metrics": ["no_such_metric"]}).error_type == "semantic_error"
    assert s4.execute("not json").error_type == "bad_request"
    assert s4.execute({"cannot_answer": "no such metric"}).error_type == "refusal"
    assert s4.execute({"metrics": ["avg_fare"], "sql": "DROP TABLE x"}).error_type == "semantic_error"


def test_destructive_sql_is_refused(built):
    for s in ("s1_raw", "s1d_raw_docs", "s2_modelled", "s3_docs"):
        r = SETUPS[s].execute(f"DROP TABLE {SETUPS[s].tables[0]}")
        assert r.status == "error" and r.error_type == "unsafe_sql"
