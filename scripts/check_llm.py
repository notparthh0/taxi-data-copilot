"""One tiny Gemini call to prove the key and model work from this repo. Never prints the key."""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config  # noqa: E402,F401  (loads .env)

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
key = os.getenv("GEMINI_API_KEY", "")
if not key or key == "your_key_here":
    raise SystemExit("GEMINI_API_KEY is not set in .env")

# Same settings that work in nyc-taxi-streaming: 30 s timeout, no retries.
client = genai.Client(api_key=key, http_options=types.HttpOptions(
    timeout=30_000, retry_options=types.HttpRetryOptions(attempts=1)))
start = time.perf_counter()
reply = client.models.generate_content(
    model=MODEL, contents="Write one DuckDB SQL query that counts the rows of a table called trips. SQL only.",
    config=types.GenerateContentConfig(temperature=0))
print(f"{MODEL}: {reply.text.strip()!r} in {time.perf_counter() - start:.1f} s")
