"""
Runs the experiment: every question x every setup for one model, graded.
Appends one JSON line per answer to results/runs/<model>.jsonl and can be
stopped and restarted (answers already on disk are skipped).

    python scripts/run_eval.py --model gemini-flash-lite --repeats 3
    python scripts/run_eval.py --model qwen-coder-7b
    python scripts/run_eval.py --model gemini-flash-lite --limit 10 --setups s3_docs   # quick try
"""

import argparse
import datetime as dt
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config, grader, llm  # noqa: E402
from copilot.benchmark import load_gold, load_questions  # noqa: E402
from copilot.runner import answer_question  # noqa: E402
from copilot.setups import get_setups  # noqa: E402


def default(o):
    if isinstance(o, (dt.date, dt.datetime)):
        return grader.canon(o)
    if isinstance(o, Decimal):
        return float(o)
    return str(o)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help=f"one of {list(llm.MODELS)}")
    ap.add_argument("--setups", default="all")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="only the first N questions")
    ap.add_argument("--out", default="")
    ap.add_argument("--pause", type=float, default=0.0, help="seconds to wait between model calls")
    args = ap.parse_args()

    setups = get_setups()
    keys = list(setups) if args.setups == "all" else args.setups.split(",")
    questions = load_questions()[: args.limit or None]
    gold = load_gold()
    out = Path(args.out) if args.out else config.RESULTS_DIR / "runs" / f"{args.model}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            r = json.loads(line)
            done.add((r["setup"], r["question_id"], r["repeat"]))

    client = llm.get_client(args.model)
    todo = [(k, q, rep) for rep in range(args.repeats) for k in keys for q in questions
            if (k, q.id, rep) not in done]
    print(f"{args.model}: {len(todo)} answers to collect ({len(done)} already done) -> {out}", flush=True)
    start, failures = time.time(), 0
    with out.open("a") as f:
        for i, (key, q, rep) in enumerate(todo, 1):
            rec = answer_question(client, setups[key], q, gold.get(q.id))
            if rec.get("llm_failed"):
                failures += 1
                print(f"  model call failed for {key}/{q.id}: {rec['error']}", flush=True)
                if failures >= 10:
                    raise SystemExit("10 model calls failed; stopping. Re-run to resume.")
                continue
            rec.update(model=args.model, repeat=rep, difficulty=q.difficulty, category=q.category,
                       answerable=q.answerable)
            f.write(json.dumps(rec, default=default) + "\n")
            f.flush()
            if i % 25 == 0 or i == len(todo):
                rate = (time.time() - start) / i
                print(f"  {i}/{len(todo)}  {rate:.1f} s/answer  about {rate * (len(todo) - i) / 60:.0f} min left", flush=True)
            if args.pause:
                time.sleep(args.pause)


if __name__ == "__main__":
    main()
