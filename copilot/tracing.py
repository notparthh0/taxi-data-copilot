"""
Tracing for the copilot agent.

Always: one JSON line per agent run in logs/traces.jsonl (latency, tokens, attempts).
Also, when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set (`make langfuse-up` runs a local,
self-hosted Langfuse and writes them to .env): each run is a Langfuse trace with one observation
per model call (model, prompt, reply, tokens) and per SQL run (query, row count or error).
Without the keys, observe() does nothing, so tests and CI never need Langfuse.
"""

import datetime as dt
import json
import os
from contextlib import contextmanager

from copilot import config

TRACE_FILE = config.REPO / "logs" / "traces.jsonl"
_client = None


def langfuse():
    """The Langfuse client, or None when no keys are configured."""
    global _client
    if _client is None:
        if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
            from langfuse import Langfuse
            _client = Langfuse()           # reads LANGFUSE_PUBLIC_KEY / _SECRET_KEY / _BASE_URL
        else:
            _client = False
    return _client or None


@contextmanager
def observe(name: str, as_type: str = "span", **fields):
    """with observe("write_sql", as_type="generation", model=...) as obs: ... obs.update(output=...)"""
    lf = langfuse()
    if lf is None:
        yield None
        return
    with lf.start_as_current_observation(name=name, as_type=as_type, **fields) as obs:
        yield obs


def flush() -> None:
    if langfuse() is not None:
        langfuse().flush()


def log_run(record: dict) -> None:
    TRACE_FILE.parent.mkdir(exist_ok=True)
    record = {"at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **record}
    with TRACE_FILE.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")
