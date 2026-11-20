"""
Gold answers for the blind question set (benchmark/blind/*.yml) -> results/gold_blind.json.

Same rules as scripts/build_gold.py: the gold SQL runs on the cleaned tables (setup 2), the
naive raw SQL on the raw table (setup 1). The main gold file (results/gold_answers.json) is NOT
touched, so the frozen 150-question set stays as it was.

    .venv/bin/python scripts/build_blind.py
"""

import datetime as dt
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import grader  # noqa: E402
from copilot.benchmark import BLIND_DIR, BLIND_GOLD_FILE, load_questions  # noqa: E402
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
    raw, modelled = setups["s1_raw"], setups["s2_modelled"]
    questions = load_questions(directory=BLIND_DIR)
    out, problems = {}, []
    for q in questions:
        if not q.answerable:
            out[q.id] = {"answerable": False}
            continue
        g = modelled.execute(q.gold_sql)
        if g.status != "ok" or not g.rows:
            problems.append(f"{q.id}: gold SQL failed or empty: {g.error[:200]}")
            continue
        if not q.naive_raw_sql:
            problems.append(f"{q.id}: no naive raw SQL written")
            continue
        r = raw.execute(q.naive_raw_sql)
        if r.status != "ok":
            problems.append(f"{q.id}: naive raw SQL failed: {r.error[:200]}")
            continue
        entry = {"answerable": True, "columns": g.columns, "rows": rows_json(g.rows),
                 "raw_columns": g.columns, "raw_rows": rows_json(r.rows)}
        entry["raw_diverges"] = not grader.answer_matches(q, g.columns, entry["rows"], entry["raw_rows"])
        entry["semantic_expressible"] = q.semantic is not None   # blind questions carry no semantic request
        out[q.id] = entry
        print(f"{q.id} gold={str(entry['rows'][0])[:50]:52} raw_diverges={entry['raw_diverges']}", flush=True)

    summary = {"questions": len(questions), "answerable": sum(q.answerable for q in questions),
               "raw_diverges": sum(1 for v in out.values() if v.get("raw_diverges")),
               "problems": problems}
    BLIND_GOLD_FILE.write_text(json.dumps({"generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                           "summary": summary, "questions": out}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
