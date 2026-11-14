"""
The four setups of the experiment ("the ladder"). Each adds exactly one thing:

  s1_raw       raw TLC files as downloaded            + schema only
  s2_modelled  cleaned, modelled dbt tables           + schema only
  s3_docs      s2 + written documentation
  s4_semantic  s2 + compiled semantic layer (MetricFlow writes the SQL)

A setup knows two things: what text the model is shown (context) and how to run the
model's answer (execute). Every execution goes through the read-only guard.

To add a second dataset later: add another list of Setup objects to DATASETS.
"""

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import duckdb

from copilot import config, context, semantic, sqlguard


@dataclass
class ExecResult:
    status: str                    # 'ok' or 'error'
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    sql: str = ""                  # the SQL that actually ran (for setup 4: written by MetricFlow)
    error_type: str = ""           # unsafe_sql | sql_error | timeout | semantic_error | bad_request | refusal
    error: str = ""
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Setup:
    key: str
    title: str
    db_path: Path
    tables: tuple
    mode: str = "sql"              # 'sql': model writes SQL; 'semantic': model writes a metric request
    with_docs: bool = False

    def context(self) -> str:
        """Exactly what the model sees about the data in this setup."""
        if self.mode == "semantic":
            return context.semantic_text()
        text = "# Database schema (DuckDB)\n" + context.schema_text(self.db_path, self.tables)
        return text + "\n\n" + context.docs_text() if self.with_docs else text

    def execute(self, action) -> ExecResult:
        """Run the model's answer: a SQL string, or (setup 4) a metric request dict / JSON string."""
        start = time.perf_counter()
        result = self._execute(action)
        result.seconds = round(time.perf_counter() - start, 3)
        return result

    def _execute(self, action) -> ExecResult:
        sql = action
        if self.mode == "semantic":
            try:
                request = json.loads(action) if isinstance(action, str) else action
                if not isinstance(request, dict):
                    raise ValueError("request must be a JSON object")
            except ValueError as exc:
                return ExecResult("error", error_type="bad_request", error=str(exc))
            if "cannot_answer" in request:
                return ExecResult("error", error_type="refusal", error=str(request["cannot_answer"]))
            try:
                sql = semantic.compile_sql(request)
            except semantic.SemanticQueryError as exc:
                return ExecResult("error", error_type="semantic_error", error=str(exc))
        try:
            columns, rows = sqlguard.run_select(self.db_path, sql, config.QUERY_TIMEOUT_SECONDS,
                                                config.MAX_RESULT_ROWS)
            return ExecResult("ok", columns=columns, rows=[list(r) for r in rows], sql=sql)
        except sqlguard.UnsafeSQL as exc:
            return ExecResult("error", sql=str(sql), error_type="unsafe_sql", error=str(exc))
        except sqlguard.QueryTimeout as exc:
            return ExecResult("error", sql=str(sql), error_type="timeout", error=str(exc))
        except duckdb.Error as exc:
            return ExecResult("error", sql=str(sql), error_type="sql_error", error=str(exc))


MODELLED_TABLES = ("fct_trips", "dim_zones", "trips_hourly_demand")

DATASETS = {
    "nyc_taxi": (
        Setup("s1_raw", "Raw TLC data, schema only",
              config.RAW_DB, ("yellow_tripdata", "taxi_zone_lookup")),
        Setup("s2_modelled", "Cleaned dbt tables, schema only",
              config.WAREHOUSE_DB, MODELLED_TABLES),
        Setup("s3_docs", "Cleaned dbt tables + written docs",
              config.WAREHOUSE_DB, MODELLED_TABLES, with_docs=True),
        Setup("s4_semantic", "Cleaned dbt tables + semantic layer (MetricFlow)",
              config.WAREHOUSE_DB, ("fct_trips",), mode="semantic"),
    ),
}


def get_setups(dataset: str = "nyc_taxi") -> dict:
    return {s.key: s for s in DATASETS[dataset]}
