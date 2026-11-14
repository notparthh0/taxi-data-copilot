"""
Runs every benchmark question's gold SQL, naive raw SQL and semantic request, and
writes results/gold_answers.json. Gold answers are never typed by hand.

Also checks the benchmark itself:
  * every gold SQL and naive raw SQL runs;
  * every semantic request gives the same answer as the gold SQL (otherwise the
    request is wrong and must be fixed or removed);
  * raw_diverges: does the obvious query on the raw data give a different answer?
    This is how "trap" questions are identified - measured, not asserted.
"""

import datetime as dt
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config, grader  # noqa: E402
from copilot.benchmark import GOLD_FILE, load_questions  # noqa: E402
from copilot.setups import get_setups  # noqa: E402


def jsonable(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return grader.canon(v)
    if isinstance(v, Decimal):
        return float(v)
    return v


def rows_json(rows):
    return [[jsonable(v) for v in r] for r in rows]


def main() -> int:
    setups = get_setups()
    raw, modelled, semantic = setups["s1_raw"], setups["s2_modelled"], setups["s4_semantic"]
    out, problems = {}, []
    questions = load_questions()
    for q in questions:
        if not q.answerable:
            out[q.id] = {"answerable": False}
            continue
        g = modelled.execute(q.gold_sql)
        r = raw.execute(q.naive_raw_sql)
        if g.status != "ok" or not g.rows:
            problems.append(f"{q.id}: gold SQL failed or empty: {g.error[:200]}")
            continue
        if r.status != "ok":
            problems.append(f"{q.id}: naive raw SQL failed: {r.error[:200]}")
            continue
        entry = {"answerable": True, "columns": g.columns, "rows": rows_json(g.rows),
                 "raw_columns": g.columns, "raw_rows": rows_json(r.rows)}
        entry["raw_diverges"] = not grader.answer_matches(q, g.columns, entry["rows"], entry["raw_rows"])
        entry["semantic_expressible"] = q.semantic is not None
        if q.semantic is not None:
            s = semantic.execute(q.semantic)
            ok = s.status == "ok" and grader.answer_matches(q, g.columns, entry["rows"], rows_json(s.rows))
            if not ok:
                problems.append(f"{q.id}: semantic request does not reproduce gold: "
                                f"{s.error[:200] or rows_json(s.rows)[:3]} vs gold {entry['rows'][:3]}")
        out[q.id] = entry
        print(f"{q.id} gold={str(entry['rows'][0])[:50]:52} raw_diverges={entry['raw_diverges']}", flush=True)

    answerable = [q for q in questions if q.answerable and q.id in out]
    summary = {
        "questions": len(questions),
        "answerable": len(answerable),
        "unanswerable": sum(not q.answerable for q in questions),
        "raw_diverges": sum(out[q.id]["raw_diverges"] for q in answerable),
        "semantic_expressible": sum(out[q.id]["semantic_expressible"] for q in answerable),
        "by_difficulty": {str(d): {"questions": sum(q.difficulty == d for q in answerable),
                                   "raw_diverges": sum(out[q.id]["raw_diverges"] for q in answerable if q.difficulty == d)}
                          for d in (1, 2, 3)},
        "numeric_tolerance_relative": grader.REL_TOL,
    }
    GOLD_FILE.write_text(json.dumps({"generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                     "summary": summary, "questions": out}, indent=1) + "\n")
    print(json.dumps(summary, indent=2))
    for p in problems:
        print("PROBLEM", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
