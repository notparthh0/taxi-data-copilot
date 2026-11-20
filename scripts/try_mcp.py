"""
Try the MCP server (`make mcp`) as a real MCP client would, over stdio, on the real warehouse.
Writes results/mcp_trial.json.

    make try-mcp

Checks: the three tools are listed; get_schema returns the context; run_sql answers a simple
count; run_sql BLOCKS attack SQL sent straight to the tool (no model involved, so this tests
the guard itself on the real file); ask() answers one benchmark question end to end.
"""

import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "mcp_trial.json"

ATTACK_SQL = [
    "DROP TABLE fct_trips",
    "DELETE FROM fct_trips WHERE fare_amount > 100",
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT 1; DROP TABLE fct_trips",
    "ATTACH 'data/raw.duckdb' AS r",
    "COPY (SELECT * FROM fct_trips LIMIT 1) TO '/tmp/leak.csv'",
]
COUNT_SQL = "SELECT COUNT(*) AS trips FROM fct_trips"


def payload(result):
    if result.structured_content:
        sc = result.structured_content
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    text = "".join(getattr(c, "text", "") for c in result.content)
    try:
        return json.loads(text)
    except ValueError:
        return text


async def main() -> int:
    params = StdioServerParameters(command=str(REPO / ".venv" / "bin" / "python"),
                                   args=["-m", "copilot.mcp_server"], cwd=str(REPO))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(t.name for t in (await session.list_tools()).tools)

            schema = payload(await session.call_tool("get_schema", {}))
            count = payload(await session.call_tool("run_sql", {"sql": COUNT_SQL}))
            attacks = []
            for sql in ATTACK_SQL:
                out = payload(await session.call_tool("run_sql", {"sql": sql}))
                attacks.append({"sql": sql, "blocked": isinstance(out, dict) and out.get("ok") is False,
                                "error_type": out.get("error_type") if isinstance(out, dict) else None})
            count_after = payload(await session.call_tool("run_sql", {"sql": COUNT_SQL}))
            ask = payload(await session.call_tool(
                "ask", {"question": "How many trips started at JFK Airport in 2023?"}))

    record = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "tools": tools,
        "get_schema_characters": len(schema) if isinstance(schema, str) else None,
        "run_sql_count": count,
        "attack_sql": attacks,
        "all_attacks_blocked": all(a["blocked"] for a in attacks),
        "row_count_unchanged": count == count_after,
        "ask": {k: ask.get(k) for k in ("answer", "sql", "attempts", "seconds", "refused", "failed")}
               if isinstance(ask, dict) else ask,
    }
    OUT.write_text(json.dumps(record, indent=2, default=str) + "\n")
    print(json.dumps(record, indent=2, default=str))
    return 0 if record["all_attacks_blocked"] and record["row_count_unchanged"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
