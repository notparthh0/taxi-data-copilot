# Taxi Data Copilot

[![ci](https://github.com/notparthh0/taxi-data-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/notparthh0/taxi-data-copilot/actions/workflows/ci.yml)

An LLM that answers business questions about NYC Yellow Taxi data, and an experiment
that measures **where its accuracy comes from: the model, the documentation, or the
data engineering underneath**.

It sits on top of my lakehouse ([nyc-taxi-elt-pipeline](https://github.com/notparthh0/nyc-taxi-elt-pipeline)):
38.3 million raw 2023 trips, cleaned by PySpark into Apache Iceberg (35.6 million trips).

> Status (21 Nov 2026): **experiment run, results in.** 3,750 graded answers from
> three models, plus 375 on a 15-question blind set written by a fresh model instance (same
> ladder; not a human blind set). The questions are not yet reviewed by me, so treat the numbers
> as preliminary. Results: [docs/RESULTS.md](docs/RESULTS.md)
> (generated tables), [docs/FINDINGS.md](docs/FINDINGS.md) (what they mean), and
> [docs/literature_check.md](docs/literature_check.md) (what is and is not new here).

## The result in one table

Share of the 140 answerable questions answered **correctly** (from [docs/RESULTS.md](docs/RESULTS.md), table 1;
Gemini is pooled over 3 repeats, n=420 per cell; Qwen n=140 per cell):

| Setup: the model sees | Gemini 3.5 Flash-Lite | Qwen2.5-Coder 7B (local) | Qwen2.5-Coder 3B (local) |
|---|---:|---:|---:|
| 1 Raw data, schema only | 23.1% | 20.0% | 6.4% |
| 1+ Raw data + full docs (extra arm) | 18.3% | 19.3% | 8.6% |
| 2 Cleaned dbt tables, schema only | 93.6% | 77.1% | 53.6% |
| 3 Cleaned + docs | **98.3%** | **82.9%** | **55.0%** |
| 4 Cleaned + compiled semantic layer | 69.0% | 50.0% | 22.1% |

In plain words:

1. **Data engineering matters most.** Cleaning the tables added 47 to 71 points for every
   model. On raw data, silent errors (answers that look right but are wrong) were 61% to 77%.
2. **Docs cannot stand in for the cleaning.** Given the raw table *and* the 7 cleaning rules,
   Gemini tried to apply them: a third of its queries then failed (135 of its 143 loud errors
   came from one rule), and most of the rest applied the rules only partly. The Qwen models
   mostly ignored the rules.
3. **Docs on top of clean tables help a little** (+1.4 to +5.7 points; clearly above zero only for Gemini).
4. **The semantic layer did not beat equally informative docs**: it was 29 to 33 points lower,
   mostly because of interface mistakes (a month written as `'2023-01'` instead of a date) and
   questions the layer cannot express. The hypothesis is not supported.

Details, caveats and limits: [docs/FINDINGS.md](docs/FINDINGS.md).

## The experiment

The same questions are asked under four setups (plus one extra arm). Each adds exactly one thing:

| Setup | The model sees | What it adds |
|---|---|---|
| `s1_raw` | The raw TLC files as downloaded, table and column names only | the baseline |
| `s1d_raw_docs` | Setup 1 + the same written docs as setup 3 | can docs replace cleaning? |
| `s2_modelled` | The cleaned dbt tables, table and column names only | data engineering |
| `s3_docs` | Setup 2 + written docs: column meanings, cleaning rules, metric definitions | documentation |
| `s4_semantic` | Setup 2 + a compiled semantic layer: the model picks metrics and dimensions, [MetricFlow](https://github.com/dbt-labs/metricflow) writes the SQL | a semantic layer |

Every answer is graded **correct**, **silent error** (wrong but plausible), or
**error / refusal**. The silent-error rate is the headline number: a wrong answer that
looks right is worse than an error, because nobody knows to check it.

- **Benchmark:** 150 questions in `benchmark/questions/`: 140 answerable (50 / 55 / 35 at
  difficulty 1 / 2 / 3) and 10 that the data cannot answer. On 106 of the 140, the obvious
  query on raw data gives a different answer ("trap" questions). Results are always shown for
  trap and non-trap questions separately.
- **Grader:** `copilot/grader.py`, numbers must match within 0.1%. Frozen in a commit before any
  model ran.
- **Runs:** temperature 0, one attempt per question. Gemini 3 repeats, the local models 1.

### Setups 3 and 4 carry the same information

Column meanings and metric definitions are written **once**, in
[`dbt/taxi_copilot/models/semantic/trips.yml`](dbt/taxi_copilot/models/semantic/trips.yml).
The docs for setup 3 are rendered from that file, and the semantic layer for setup 4
is compiled from that file. `tests/test_parity.py` fails if one side knows something
the other does not. So a difference between setups 3 and 4 is a difference in *form*
(prose the model must turn into SQL, versus a compiled layer that writes the SQL),
not in *content*.

## The product: the copilot itself

Built on the same code, after the experiment was frozen. Nothing here changes the experiment.

- **Agent** (`copilot/agent.py`, LangGraph): write SQL, guard, run it; on an error, repair
  (up to 2 retries, with the error shown to the model); answer in one or two plain sentences
  with the SQL shown. Uses the setup-3 context (cleaned tables + docs), the best setup above.
- **HTTP API** (`copilot/api.py`, FastAPI): `POST /ask`, `GET /health`.
- **MCP server** (`copilot/mcp_server.py`, official `mcp` SDK, stdio): tools `get_schema`,
  `run_sql` (guarded) and `ask`.
- **Guardrails:** every query goes through `copilot/sqlguard.py` (one SELECT only, read-only
  file) and DuckDB runs with file access switched off. `tests/test_agent.py` includes
  prompt-injection tests where a fake model **obeys** the attacker, and the guard must still hold.
- **Tracing:** each run is logged to `logs/traces.jsonl` (model seconds, query seconds, tokens,
  retries). With `make langfuse-up`, a self-hosted Langfuse runs locally in Docker
  (`langfuse/docker-compose.yml`, no account needed) and every run also becomes a Langfuse trace:
  one observation per model call (prompt, reply, tokens) and per SQL run (query, rows or error).
  `make try-langfuse` runs 14 questions and reads the traces back through Langfuse's API
  (`results/langfuse_check.json`: 14 of 14 found, with 38,692 tokens across the model calls and
  14 SQL runs). Without the keys, tracing to Langfuse is off; tests and CI never need it.

Tried on the real warehouse (`results/api_trial.json`, `results/mcp_trial.json`): 12 of 12 sample
benchmark questions answered correctly over HTTP; 4 of 4 attack prompts refused; 6 of 6 attack
SQL statements sent straight to the MCP `run_sql` tool blocked; table row counts unchanged.
That is a smoke test, not a score.

```bash
make api        # http://127.0.0.1:8000/docs
curl -s localhost:8000/ask -H 'content-type: application/json' \
     -d '{"question": "How many trips started at JFK Airport in 2023?"}'
make try-api    # (with `make api` running) 12 questions + 4 attacks -> results/api_trial.json
make mcp        # MCP server on stdio, for Claude Desktop / Claude Code
make langfuse-up # local Langfuse on http://localhost:3000 (login in langfuse/.env); make langfuse-down
make try-mcp    # a real MCP client calls every tool -> results/mcp_trial.json
```

To use it from Claude Code: `claude mcp add taxi -- /path/to/taxi-data-copilot/.venv/bin/python -m copilot.mcp_server`
(run from the repo folder so `.env` and `data/` are found).

## Follow-up: a fine-tuned local model (QLoRA)

Run after the experiment was frozen; it does not change the tables above. A LoRA adapter on the
4-bit Qwen2.5-Coder 3B, trained on this MacBook Air with MLX (153 min) on 411 question-SQL pairs
written by Gemini, checked by a second opinion, and filtered so that none is close in meaning to,
or has the same answer as, any of the 165 benchmark questions ([finetune/README.md](finetune/README.md)).
Same setup (cleaned tables + docs), same grader, one run:

| Qwen2.5-Coder 3B | Correct (of 140) | Silent errors | Unanswerable refused |
|---|---:|---:|---:|
| base | 55.0% | 17.9% | 3/10 |
| **+ QLoRA adapter** | **80.0%** | 15.0% | 6/10 |
| (7B, for reference) | 82.9% | 6.4% | 6/10 |

+25.0 points, 95% bootstrap interval +17.9 to +32.1 (35 questions fixed, 0 broken); blind set
11/15 to 13/15. It mostly fixed failing and unsafe queries; it is still far more often silently
wrong than the 7B. Details and limits: [docs/FINETUNE.md](docs/FINETUNE.md).

## Run it

Needs `../nyc-taxi-aws` with the 2023 raw files and the Iceberg table (read-only), and [uv](https://docs.astral.sh/uv/).

```bash
make install            # Python 3.12 venv + requirements.txt
cp .env.example .env    # add GEMINI_API_KEY
make setups             # build data/raw.duckdb and data/warehouse.duckdb (about 1 minute)
make gold               # gold answers -> results/gold_answers.json
make blind              # 15 model-written blind questions -> results/gold_blind.json (not in the 150)
make eval MODEL=gemini-flash-lite REPEATS=3 BLIND=1   # blind set -> results/runs_blind/
make test               # 74 tests (8 skip when the data is not built)

make eval MODEL=gemini-flash-lite REPEATS=3   # resumable; results/runs/<model>.jsonl
make eval MODEL=qwen-coder-7b                 # local, needs: uv pip install -r requirements-local-models.txt
make summary                                  # results/summary.json + docs/RESULTS.md
```

CI (`.github/workflows/ci.yml`) runs the tests that need no data (guard, grader, prompts,
agent, prompt injection), checks that `docs/RESULTS.md` is exactly what `scripts/summarise.py`
produces from the committed run files, and fails if anyone edited the tables by hand.

## Layout

```
copilot/
  setups.py, context.py  the five setups: what the model sees, and how its answer is run
  semantic.py            turns a metric request into SQL with MetricFlow
  sqlguard.py            read-only guard
  benchmark.py, grader.py, prompts.py, llm.py, runner.py   the experiment harness
  agent.py, api.py, mcp_server.py, tracing.py              the product
dbt/taxi_copilot/        dbt project: fct_trips, dim_zones, trips_hourly_demand + semantic model, 21 metrics
knowledge/               the 7 cleaning rules, in words
benchmark/questions/     150 questions with gold SQL and naive raw SQL
scripts/                 build, gold, run_eval, summarise, try_api, try_mcp, ...
results/                 every number in this repo comes from a file here, written by a script
docs/                    RESULTS (generated), FINDINGS, literature_check
tests/                   73 tests
```

## Measured before any model ran

From `results/phase1_layer_profile.json` (`make profile`): the same obvious query on
the raw layer and on the cleaned layer.

| Question | Raw | Cleaned | Raw is off by |
|---|---:|---:|---:|
| Number of trips | 38,310,226 | 35,574,647 | +7.69% |
| Average fare ($) | 19.52 | 19.74 | −1.12% |
| Average trip distance (miles) | 4.09 | 3.63 | +12.53% |
| Total revenue ($) | 1,090,383,412 | 1,028,974,147 | +5.97% |
| Average passengers | 1.370 | 1.393 | −1.60% |
| Average duration (minutes) | 16.72 | 16.40 | +1.94% |

The raw data holds 381,650 negative fares, 1,309,356 trips with no passenger count,
773,457 trips with zero distance, and 730 trips whose pickup is outside the month of
the file they came in (104 of them not in 2023 at all).

A known limit of the cleaned layer: the 7 rules do not cap trip distance, so the
longest "cleaned" trip is still 161,726 miles. Clean does not mean perfect.

## How the numbers are kept honest

- Every number in this README and in `docs/` comes from a file in `results/` written by a script.
  Nothing is typed in by hand.
- CI regenerates `docs/RESULTS.md` from the committed run files and fails if anyone edited the
  tables by hand.
- The grader and its 0.1% tolerance were committed before any model ran. The two corrections made
  after a run are documented, with the script that applied each one (`scripts/regrade_refusals.py`,
  `scripts/regrade_blind.py`).
- The source lakehouse ([nyc-taxi-elt-pipeline](https://github.com/notparthh0/nyc-taxi-elt-pipeline))
  is only read, never modified. API keys live in a local `.env` that is never committed.
