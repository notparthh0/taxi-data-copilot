# Taxi Data Copilot

An LLM that answers business questions about NYC Yellow Taxi data, and an experiment
that measures **where its accuracy comes from: the model, the documentation, or the
data engineering underneath**.

It sits on top of my lakehouse ([nyc-taxi-elt-pipeline](https://github.com/notparthh0/nyc-taxi-elt-pipeline)):
38.3 million raw 2023 trips, cleaned by PySpark into Apache Iceberg (35.6 million trips).

> Status: **phase 1 of 5** (setups built and tested; no model has been evaluated yet,
> so there are no accuracy results in this repo yet). Plan: [docs/PLAN.md](docs/PLAN.md).

## The experiment in one picture

The same questions are asked under four setups. Each adds exactly one thing:

| Setup | The model sees | What it adds |
|---|---|---|
| `s1_raw` | The raw TLC files as downloaded, table and column names only | the baseline |
| `s2_modelled` | The cleaned dbt tables, table and column names only | data engineering |
| `s3_docs` | Setup 2 + written docs: column meanings, cleaning rules, metric definitions | documentation |
| `s4_semantic` | Setup 2 + a compiled semantic layer: the model picks metrics and dimensions, [MetricFlow](https://github.com/dbt-labs/metricflow) writes the SQL | a semantic layer |

Every answer is graded **correct**, **wrong but plausible** (a silent error), or
**error / refusal**. The silent-error rate is the headline number: a wrong answer that
looks right is worse than an error, because nobody knows to check it.

### Setups 3 and 4 carry the same information

Column meanings and metric definitions are written **once**, in
[`dbt/taxi_copilot/models/semantic/trips.yml`](dbt/taxi_copilot/models/semantic/trips.yml).
The docs for setup 3 are rendered from that file, and the semantic layer for setup 4
is compiled from that file. `tests/test_parity.py` fails if one side knows something
the other does not. So a difference between setups 3 and 4 is a difference in *form*
(prose the model must turn into SQL, versus a compiled layer that writes the SQL),
not in *content*.

## What exists today (phase 1)

```
copilot/
  setups.py      the four setups: what the model sees, and how its answer is run
  context.py     renders schema text, the docs (setup 3) and the semantic catalogue (setup 4)
  semantic.py    turns a metric request into SQL with MetricFlow
  sqlguard.py    read-only guard: one SELECT only, read-only file, no file/network access
dbt/taxi_copilot/  dbt project: fct_trips, dim_zones, trips_hourly_demand + semantic model, 21 metrics
knowledge/cleaning_rules.yml   the 7 cleaning rules, in words
benchmark/       question format and grading rules (questions are added in reviewed batches)
scripts/         build_setups.py, check_setups.py, profile_layers.py, check_llm.py
results/         every number in this README comes from a file here, written by a script
docs/            PLAN.md, literature_check.md
tests/           27 tests
```

## Measured so far (no LLM involved)

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

From `results/phase1_setups.json` (`make check`): all four setups answer a probe
question, setups 2-4 agree with each other, and each SQL setup refuses 6 of 6 attacks
(DROP, DELETE, two statements in one, reading a local file, COPY to a file, ATTACH).

A known limit of the cleaned layer: the 7 rules do not cap trip distance, so the
longest "cleaned" trip is still 161,726 miles. Clean does not mean perfect, and the
paper will say so.

## Run it

Needs `../nyc-taxi-aws` with the 2023 raw files and the Iceberg table (read-only), and [uv](https://docs.astral.sh/uv/).

```bash
make install     # Python 3.12 venv
cp .env.example .env   # add GEMINI_API_KEY
make setups      # build data/raw.duckdb and data/warehouse.duckdb (about 1 minute)
make check       # results/phase1_setups.json
make profile     # results/phase1_layer_profile.json
make test        # 27 tests
```

## Rules of this repo

- No invented numbers. Every number is written to `results/` by a script.
- `../nyc-taxi-aws` is read, never written.
- `.env` is never committed.
