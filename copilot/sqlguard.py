"""
Read-only guard for SQL written by a model. Two independent layers:

  1. check_read_only(): the text must be exactly ONE statement and it must be a SELECT.
     DuckDB's own parser decides, so tricks like "SELECT 1; DROP TABLE x" or a
     COPY/ATTACH/PRAGMA statement are refused before anything runs.
  2. connect(): the database file is opened read-only, and file/network access is
     switched off and locked, so even a SELECT cannot read other files
     (e.g. read_csv('/etc/passwd')) or write anywhere.
"""

import threading
import time
from pathlib import Path

import duckdb


class UnsafeSQL(Exception):
    """The SQL is not a single read-only SELECT."""


class QueryTimeout(Exception):
    """The query ran longer than the allowed time."""


class HarnessError(Exception):
    """The database file could not be opened. Our problem, never the model's."""


def check_read_only(sql: str) -> str:
    if not sql or not sql.strip():
        raise UnsafeSQL("empty SQL")
    try:
        statements = duckdb.extract_statements(sql)
    except Exception as exc:  # not parseable at all
        raise UnsafeSQL(f"cannot parse SQL: {exc}") from exc
    if len(statements) != 1:
        raise UnsafeSQL(f"expected exactly 1 statement, got {len(statements)}")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise UnsafeSQL(f"only SELECT is allowed, got {statements[0].type.name}")
    return sql.strip().rstrip(";")


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Read-only connection with external access off and the configuration locked."""
    for attempt in range(8):
        try:
            con = duckdb.connect(str(db_path), read_only=True)
            break
        except duckdb.IOException as exc:      # file briefly locked by a writer: wait, retry
            if attempt == 7:
                raise HarnessError(str(exc)) from exc
            time.sleep(1 + attempt)
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")
    return con


def run_select(db_path: Path, sql: str, timeout_seconds: float, max_rows: int):
    """Run one guarded SELECT. Returns (column_names, rows). Rows are capped at max_rows."""
    sql = check_read_only(sql)
    con = connect(db_path)
    timer = threading.Timer(timeout_seconds, con.interrupt)
    timer.start()
    try:
        cur = con.execute(sql)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(max_rows)
        return columns, rows
    except duckdb.InterruptException as exc:
        raise QueryTimeout(f"query exceeded {timeout_seconds:.0f} s") from exc
    finally:
        timer.cancel()
        con.close()
