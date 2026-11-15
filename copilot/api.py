"""
HTTP API for the copilot.

    make api            # http://127.0.0.1:8000/docs
    curl -s localhost:8000/ask -H 'content-type: application/json' \
         -d '{"question": "How many trips started at JFK Airport in 2023?"}'

The model is chosen with COPILOT_MODEL (default gemini-flash-lite; see copilot/llm.py).
"""

import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from copilot import agent as agent_mod
from copilot import config, llm

MODEL = os.getenv("COPILOT_MODEL", "gemini-flash-lite")
app = FastAPI(title="Taxi Data Copilot", version="0.1.0")


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@lru_cache(maxsize=1)
def _agent():
    return agent_mod.build_agent(llm.get_client(MODEL))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL, "warehouse_built": config.WAREHOUSE_DB.exists()}


@app.post("/ask")
def ask(body: Ask) -> dict:
    if not config.WAREHOUSE_DB.exists():
        raise HTTPException(503, "warehouse not built: run `make setups`")
    try:
        return agent_mod.ask(_agent(), body.question, MODEL)
    except RuntimeError as exc:          # model unavailable (quota, network)
        raise HTTPException(502, str(exc)[:300]) from exc
