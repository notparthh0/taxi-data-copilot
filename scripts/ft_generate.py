"""
QLoRA step 1: Gemini writes NEW training questions with SQL over the cleaned tables (setup s3_docs).

This script never reads benchmark/ or the gold files. scripts/ft_filter.py removes any overlap
with the 165 benchmark questions afterwards, and is the only fine-tuning script that reads them.

For each candidate:
  1. Gemini (temperature 1, one topic per call) writes questions, each with one DuckDB query,
     or (unanswerable topic) questions these tables cannot answer.
     Models rotate when one runs out of free-tier quota (see GEN_MODELS / JUDGE_MODELS).
  2. The query runs through the read-only guard on the warehouse; errors, empty results and
     results over 30 rows are dropped.
  3. Second opinion: the question alone goes through the exact eval prompt (prompts.build for
     s3_docs) at temperature 0, like a benchmark answer. Kept only if that answer returns the same
     table (grader.tables_match); an unanswerable candidate is kept only if it is refused.

Output: results/finetune/candidates.jsonl, one line per candidate with its verdict. Resumable.

    .venv/bin/python scripts/ft_generate.py --rounds 4
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config, grader, llm, prompts  # noqa: E402
from copilot.setups import get_setups  # noqa: E402

OUT = config.RESULTS_DIR / "finetune" / "candidates.jsonl"
# The free tier caps each model at a daily number of requests, so both jobs rotate through models
# when one runs out (every candidate line records which models wrote and judged it).
GEN_MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
# Not gemini-3.5-flash as a judge: it is a thinking model, and its thinking uses up the harness's
# 600 output tokens, so its SQL came back cut off (every answer "disagreed"; those batches were redone).
JUDGE_MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
MAX_ROWS = 30
PER_CALL = 20

TOPICS = [
    "trip counts over time: by month, by date, by day of week, by hour",
    "pickup and dropoff zones: rankings, top and bottom N, specific named zones",
    "boroughs: pickups, dropoffs, trips between boroughs, shares of the total",
    "airports (JFK Airport, LaGuardia Airport, Newark Airport): trips, fares, rate codes",
    "fares and revenue: totals, averages, medians, by segment",
    "tips: average tip, tip rate on credit-card trips, by payment type, zone or hour",
    "trip distance, duration and average speed",
    "passenger counts: averages, distributions, shares of trips with N passengers",
    "tolls: totals, averages, which trips or zones pay the most tolls",
    "the trips_hourly_demand table: busiest zone-hours, peak hours, demand per zone and date",
    "weekends versus weekdays, rush hours versus nights",
    "payment types and rate codes: counts, shares and averages",
    "harder analysis: month-over-month change, ranks with window functions, CTEs, percentiles",
    "conditions combined: a zone or borough plus a month plus an hour range plus a payment type",
    "dim_zones: zones per borough, zones with no pickups, joining zone names",
    "single dates and holidays in 2023 (for example New Year's Day, July 4, Thanksgiving)",
]
UNANSWERABLE_TOPIC = (
    "questions that sound reasonable for a taxi company but CANNOT be answered from these tables, "
    "because the data is not there (for example driver identity, weather, cash tips, years other "
    "than 2023, vehicle details, customer ratings, routes, ride-hailing apps)"
)


def gen_prompt(context: str, topic: str, unanswerable: bool) -> str:
    if unanswerable:
        ask = (f"Write {PER_CALL // 2} {topic}. For each, give a one-line reason why the data cannot answer it.\n"
               'Return a JSON list: [{"q": "...", "reason": "..."}]')
    else:
        ask = (f"Write {PER_CALL} new business questions about this data on the topic: {topic}.\n"
               "Each question must have exactly one correct answer, say exactly what to return "
               "(for example 'Give the zone name and the number of trips'), and need at most 30 rows.\n"
               "Vary the wording, the filters (months, boroughs, zones, hours, payment types) and the "
               "difficulty: some single numbers, some GROUP BY with ranking, some joins, window functions or CTEs.\n"
               "For each, write one DuckDB SELECT query that answers it, following the documentation and "
               "metric definitions exactly.\n"
               'Return a JSON list: [{"q": "...", "sql": "..."}]')
    return f"{context}\n\n# Task\n{ask}"


class Rotation:
    """Calls fn(model) on the first model that still has quota; moves on after a 429."""

    def __init__(self, models):
        self.models = list(models)

    def call(self, fn):
        while self.models:
            try:
                return self.models[0], fn(self.models[0])
            except Exception as exc:  # noqa: BLE001
                if "429" not in str(exc) and "RESOURCE_EXHAUSTED" not in str(exc):
                    raise
                print(f"  {self.models[0]}: quota used up, next model", flush=True)
                self.models.pop(0)
        raise SystemExit("every model is out of quota for today; re-run later to resume")


def generate(client, types, model, context, topic, unanswerable, seed):
    cfg = types.GenerateContentConfig(temperature=1.0, seed=seed, max_output_tokens=12000,
                                      response_mime_type="application/json")
    reply = client.models.generate_content(model=model, contents=gen_prompt(context, topic, unanswerable),
                                           config=cfg)
    items = json.loads(reply.text or "[]")
    return [i for i in items if isinstance(i, dict) and i.get("q")]


def check(setup, judge, judges, item, unanswerable):
    """Run the candidate, ask the second opinion, return the candidate with its verdict."""
    rec = {"q": item["q"].strip(), "unanswerable": unanswerable,
           "gen_sql": item.get("sql", ""), "reason": item.get("reason", "")}
    if not unanswerable:
        first = setup.execute(rec["gen_sql"])
        if first.status != "ok":
            return {**rec, "keep": False, "why": f"generated SQL failed: {first.error_type}"}
        if not first.rows or len(first.rows) > MAX_ROWS:
            return {**rec, "keep": False, "why": f"{len(first.rows)} rows"}
        rec["rows"] = first.rows
    system, user = prompts.build(setup, rec["q"])
    try:
        rec["judge"], (text, _) = judge.call(lambda m: judges(m).generate(system, user))
    except Exception as exc:  # noqa: BLE001
        return {**rec, "keep": False, "why": f"second opinion failed: {exc}"[:200]}
    kind, action = prompts.parse(setup, text)
    if unanswerable:
        if kind == "refusal":     # store the clean form the eval parser accepts: CANNOT_ANSWER: <reason>
            reason = re.split(r"CANNOT[_ ]ANSWER:?", action, flags=re.I)[-1]
            reason = reason.replace("`", "").strip().splitlines()[0].strip() if reason.strip() else ""
            return {**rec, "keep": bool(reason), "target": f"CANNOT_ANSWER: {reason}"}
        return {**rec, "keep": False, "why": "second opinion answered it"}
    if kind != "action":
        return {**rec, "keep": False, "why": f"second opinion: {kind}"}
    second = setup.execute(action)
    if second.status == "ok" and grader.tables_match(second.rows, rec["rows"]):
        return {**rec, "keep": True, "target": action.strip()}
    return {**rec, "keep": False, "why": "second opinion disagrees", "second_sql": action[:2000]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=4, help="calls per topic")
    args = ap.parse_args()

    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    clients = {}
    judges = lambda m: clients.setdefault(m, llm.GeminiClient(m))  # noqa: E731
    gen_rot, judge_rot = Rotation(GEN_MODELS), Rotation(JUDGE_MODELS)
    setup = get_setups()["s3_docs"]
    context = setup.context()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        done = {(r["topic"], r["round"]) for r in map(json.loads, OUT.read_text().splitlines())}
    jobs = [(t, r, False) for r in range(args.rounds) for t in range(len(TOPICS))]
    jobs += [(len(TOPICS), r, True) for r in range(args.rounds * 2)]
    for topic_i, rnd, unans in jobs:
        if (topic_i, rnd) in done:
            continue
        topic = UNANSWERABLE_TOPIC if unans else TOPICS[topic_i]
        try:
            gen_model, items = gen_rot.call(
                lambda m: generate(client, types, m, context, topic, unans, seed=1000 * topic_i + rnd))
        except Exception as exc:  # noqa: BLE001
            print(f"topic {topic_i} round {rnd}: generation failed: {exc}"[:300], flush=True)
            continue
        recs = [check(setup, judge_rot, judges, it, unans) for it in items]   # one at a time: the guard's DuckDB connections are not thread-safe
        with OUT.open("a") as f:
            for rec in recs:
                rec.update(topic=topic_i, round=rnd, gen_model=gen_model)
                f.write(json.dumps(rec, default=str) + "\n")
        print(f"topic {topic_i:2d} round {rnd}: {sum(r['keep'] for r in recs)}/{len(recs)} kept", flush=True)


if __name__ == "__main__":
    main()
