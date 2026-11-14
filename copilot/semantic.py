"""
Setup 4: the model does not write SQL. It picks metrics and dimensions, and
MetricFlow (dbt's open-source semantic layer engine) writes the SQL.

A request is a small dict, e.g.
    {"metrics": ["avg_fare"], "group_by": ["trip__pickup_borough"],
     "where": ["{{ Dimension('trip__payment_type') }} = 'Cash'"],
     "order_by": ["-avg_fare"], "limit": 5}

compile_sql() only asks MetricFlow for the SQL (`mf query --explain`); the harness then
runs that SQL itself through the same read-only guard as every other setup.
"""

import json
import re
import subprocess
import time

from copilot import config

ALLOWED_KEYS = {"metrics", "group_by", "where", "order_by", "limit", "start_time", "end_time"}
_SQL_MARKER = re.compile(r"SQL \(remove --explain.*?\):\s*\n", re.S)


class SemanticQueryError(Exception):
    """MetricFlow rejected the request (unknown metric, bad filter, ...)."""


def load_manifest() -> dict:
    return json.loads(config.SEMANTIC_MANIFEST.read_text())


def _as_list(value) -> list:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def build_command(request: dict) -> list:
    unknown = set(request) - ALLOWED_KEYS
    if unknown:
        raise SemanticQueryError(f"unknown keys in request: {sorted(unknown)}")
    metrics = _as_list(request.get("metrics"))
    if not metrics:
        raise SemanticQueryError("request needs at least one metric")
    cmd = ["mf", "query", "--explain", "--metrics", ",".join(metrics)]
    group_by = _as_list(request.get("group_by"))
    if group_by:
        cmd += ["--group-by", ",".join(group_by)]
    for clause in _as_list(request.get("where")):
        cmd += ["--where", clause]
    order_by = _as_list(request.get("order_by"))
    if order_by:
        cmd += ["--order", ",".join(order_by)]
    if request.get("limit") is not None:
        cmd += ["--limit", str(int(request["limit"]))]
    if request.get("start_time"):
        cmd += ["--start-time", str(request["start_time"])]
    if request.get("end_time"):
        cmd += ["--end-time", str(request["end_time"])]
    return cmd


def compile_sql(request: dict, timeout_seconds: float = 120) -> str:
    """Ask MetricFlow to turn a metric request into SQL. Raises SemanticQueryError on failure."""
    command = build_command(request)
    for attempt in range(6):
        proc = subprocess.run(command, cwd=config.DBT_DIR, env=config.dbt_env(compile_only=True),
                              capture_output=True, text=True, timeout=timeout_seconds)
        output = proc.stdout + "\n" + proc.stderr
        # Another process may hold the DuckDB file for a moment; that is not the model's fault.
        if "lock" in output.lower() and "SQL (remove --explain" not in output:
            time.sleep(1.5 * (attempt + 1))
            continue
        break
    match = _SQL_MARKER.search(output)
    if not match:
        lines = [ln.strip() for ln in output.replace("\r", "\n").splitlines() if ln.strip()]
        keep = [ln for ln in lines if not ln.startswith(("Log File", "Artifact", "If you think", "https://"))]
        raise SemanticQueryError(" ".join(keep)[-1500:] or "MetricFlow returned no SQL")
    return output[match.end():].replace("\r", "").strip()
