"""
One-off correction to the blind set, applied after its first run (21 Nov 2026).

The model that wrote the blind questions wrapped 8 gold queries in round(), so the gold was up
to 0.11% away from the exact value, beyond the grader's 0.1% tolerance (b003: 4.40 vs 4.3952).
round() was removed from those gold and raw queries (benchmark/blind/blind.yml) and the gold was
rebuilt (make blind). This script re-grades the stored answers to those 8 questions with the same
grader. No model is called. Where the stored rows were cut at 50, the stored SQL is run again.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config, grader  # noqa: E402
from copilot.benchmark import BLIND_DIR, BLIND_GOLD_FILE, load_gold, load_questions  # noqa: E402
from copilot.setups import get_setups  # noqa: E402

CHANGED = {"b003", "b004", "b007", "b009", "b011", "b012", "b014", "b015"}

questions = {q.id: q for q in load_questions(directory=BLIND_DIR)}
gold, setups = load_gold(BLIND_GOLD_FILE), get_setups()
for path in sorted((config.RESULTS_DIR / "runs_blind").glob("*.jsonl")):
    rows, changed = [json.loads(line) for line in path.read_text().splitlines() if line.strip()], 0
    for r in rows:
        if r["question_id"] not in CHANGED or r.get("regraded") == "gold round() removed":
            continue
        answer = r["rows"]
        if r["status"] == "ok" and len(answer or []) != r["n_rows"]:
            answer = setups[r["setup"]].execute(r["action"] or r["sql"]).rows   # rows were cut at 50; action is set only for semantic requests
        q = questions[r["question_id"]]
        verdict = grader.grade(q, gold.get(q.id), r["status"], answer, r["error_type"])
        changed += verdict["grade"] != r["grade"]
        r.update(grade=verdict["grade"], detail=verdict["detail"],
                 matches_naive_raw=verdict.get("matches_naive_raw", False), regraded="gold round() removed")
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"{path.name}: {changed} grades changed")
