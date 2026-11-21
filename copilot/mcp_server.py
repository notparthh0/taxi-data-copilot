"""
MCP server: lets an MCP client (Claude Desktop, Claude Code, ...) use the taxi lakehouse.

    make mcp        # stdio transport

Tools
  get_schema()   tables, columns, column meanings, metric definitions, cleaning rules
  run_sql(sql)   run one read-only SELECT (guarded: SELECT only, read-only file, no file access)
  ask(question)  let the copilot agent write the SQL and explain the result
"""

import os
from functools import lru_cache

from mcp.server.mcpserver import MCPServer

from copilot import agent as agent_mod
from copilot import llm
from copilot.setups import get_setups

MODEL = os.getenv("COPILOT_MODEL", "gemini-flash-lite")
SETUP = get_setups()["s3_docs"]
server = MCPServer("taxi-data-copilot", instructions=(
    "Read-only access to cleaned 2023 NYC Yellow Taxi trips (35.6 million rows, DuckDB). "
    "Call get_schema first. All SQL is read-only."))


@lru_cache(maxsize=1)
def _agent():
    return agent_mod.build_agent(llm.get_client(MODEL), SETUP)


@server.tool()
def get_schema() -> str:
    """Tables, columns, what each column means, metric definitions and the cleaning rules."""
    return SETUP.context()


@server.tool()
def run_sql(sql: str) -> dict:
    """Run one read-only DuckDB SELECT on the taxi tables. Returns columns and up to 200 rows."""
    result = SETUP.execute(sql)
    if result.status != "ok":
        return {"ok": False, "error_type": result.error_type, "error": result.error[:500]}
    return {"ok": True, "columns": result.columns, "rows": [[str(v) if v is not None else None for v in r]
                                                          for r in result.rows[:200]],
            "row_count": len(result.rows)}


@server.tool()
def ask(question: str) -> dict:
    """Ask a business question in plain English. The copilot writes the SQL, runs it and explains the result."""
    out = agent_mod.ask(_agent(), question, MODEL)
    out["rows"] = [[str(v) if v is not None else None for v in r] for r in out["rows"][:200]]   # same cap as run_sql
    return out


if __name__ == "__main__":
    server.run("stdio")
