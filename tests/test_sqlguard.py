"""The read-only guard: only a single SELECT may run."""
import duckdb
import pytest

from copilot import sqlguard


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "select count(*) from t where x > 1;",
    "WITH a AS (SELECT 1 AS x) SELECT * FROM a",
])
def test_select_is_allowed(sql):
    assert sqlguard.check_read_only(sql)


@pytest.mark.parametrize("sql", [
    "",
    "DROP TABLE t",
    "DELETE FROM t",
    "UPDATE t SET x = 1",
    "INSERT INTO t VALUES (1)",
    "CREATE TABLE x AS SELECT 1",
    "SELECT 1; DROP TABLE t",
    "COPY t TO '/tmp/x.csv'",
    "ATTACH '/tmp/x.duckdb' AS x",
    "PRAGMA database_list",
    "SET enable_external_access = true",
    "INSTALL httpfs",
    "this is not sql",
])
def test_everything_else_is_refused(sql):
    with pytest.raises(sqlguard.UnsafeSQL):
        sqlguard.check_read_only(sql)


def test_connection_cannot_write_or_read_files(tmp_path):
    db = tmp_path / "t.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE t AS SELECT 1 AS x")
    con.close()
    secret = tmp_path / "secret.csv"
    secret.write_text("a\n1\n")

    con = sqlguard.connect(db)
    with pytest.raises(duckdb.Error):
        con.execute("INSERT INTO t VALUES (2)")                      # read-only file
    with pytest.raises(duckdb.Error):
        con.execute(f"SELECT * FROM read_csv('{secret}')")           # no file access
    with pytest.raises(duckdb.Error):
        con.execute("SET enable_external_access = true")             # configuration is locked
    con.close()
    assert sqlguard.run_select(db, "SELECT x FROM t", 10, 10) == (["x"], [(1,)])


def test_timeout(tmp_path):
    db = tmp_path / "t.duckdb"
    duckdb.connect(str(db)).close()
    slow = "SELECT count(*) FROM range(100000000000) a, range(1000) b"
    with pytest.raises(sqlguard.QueryTimeout):
        sqlguard.run_select(db, slow, 0.5, 10)
