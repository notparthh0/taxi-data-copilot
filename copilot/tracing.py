"""
Local tracing: one JSON line per agent run in logs/traces.jsonl (latency, tokens, attempts).

Langfuse is NOT wired up yet: it needs a Langfuse account and keys
(LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY), which this project does not have.
When keys exist, send the same record from log_run().
"""

import datetime as dt
import json

from copilot import config

TRACE_FILE = config.REPO / "logs" / "traces.jsonl"


def log_run(record: dict) -> None:
    TRACE_FILE.parent.mkdir(exist_ok=True)
    record = {"at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **record}
    with TRACE_FILE.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")
