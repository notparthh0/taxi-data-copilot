"""
Builds the two local DuckDB files the four setups read. Safe to re-run.

  data/raw.duckdb        setup 1: the 12 raw TLC parquet files loaded AS THEY ARE
                         (no filtering, no fixing) + the TLC zone lookup
  data/warehouse.duckdb  setups 2-4: built by dbt from the cleaned Iceberg table

Nothing in ../nyc-taxi-aws is written to; it is only read.
"""

import subprocess
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config  # noqa: E402


def build_raw() -> None:
    files = sorted(config.RAW_DIR.glob("yellow_tripdata_2023-*.parquet"))
    if len(files) != 12:
        raise SystemExit(f"expected 12 raw files in {config.RAW_DIR}, found {len(files)}")
    config.DATA_DIR.mkdir(exist_ok=True)
    tmp = config.RAW_DB.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    file_list = ", ".join(f"'{f}'" for f in files)
    # union_by_name: the monthly files disagree on a few column types and on the
    # spelling of airport_fee; this stacks them without changing any value.
    con.execute(f"""
        CREATE TABLE yellow_tripdata AS
        SELECT * EXCLUDE (filename), parse_filename(filename) AS source_file
        FROM read_parquet([{file_list}], union_by_name = true, filename = true)
    """)
    con.execute(f"CREATE TABLE taxi_zone_lookup AS SELECT * FROM read_csv('{config.ZONE_LOOKUP_CSV}', header = true)")
    rows = con.execute("SELECT count(*) FROM yellow_tripdata").fetchone()[0]
    con.close()
    tmp.replace(config.RAW_DB)
    print(f"raw.duckdb: yellow_tripdata has {rows:,} rows")


def build_modelled() -> None:
    subprocess.run(["dbt", "build"], cwd=config.DBT_DIR, env=config.dbt_env(), check=True)


def build_compile_copy() -> None:
    """Same tables as the warehouse but with zero rows, for MetricFlow to compile against."""
    config.COMPILE_DB.parent.mkdir(parents=True, exist_ok=True)
    config.COMPILE_DB.unlink(missing_ok=True)
    con = duckdb.connect(str(config.COMPILE_DB))
    con.execute(f"ATTACH '{config.WAREHOUSE_DB}' AS src (READ_ONLY)")
    tables = con.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog = 'src' "
                         "AND table_schema = 'main' AND table_type = 'BASE TABLE'").fetchall()
    for (name,) in tables:
        con.execute(f'CREATE TABLE "{name}" AS SELECT * FROM src.main."{name}" LIMIT 0')
    con.close()
    print(f"compile copy: {len(tables)} empty tables")


if __name__ == "__main__":
    build_raw()
    build_modelled()
    build_compile_copy()
