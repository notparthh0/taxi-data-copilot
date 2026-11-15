"""
One-off correction, applied after the first full run (15 Nov 2026).

Six Gemini replies said CANNOT_ANSWER inside a code block or as "SELECT CANNOT_ANSWER: ...".
The first parser treated them as SQL, so they were recorded as blocked SQL instead of
refusals. The parser now treats the marker anywhere in the reply as a refusal. This script
re-reads the stored replies and re-grades only those answers. No model is called again.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config, grader, prompts  # noqa: E402
from copilot.benchmark import load_gold, load_questions  # noqa: E402
from copilot.setups import get_setups  # noqa: E402

questions = {q.id: q for q in load_questions()}
gold, setups = load_gold(), get_setups()
for path in sorted((config.RESULTS_DIR / "runs").glob("*.jsonl")):
    rows, changed = [json.loads(line) for line in path.read_text().splitlines() if line.strip()], 0
    for r in rows:
        kind, _ = prompts.parse(setups[r["setup"]], r["reply"])
        if kind == "refusal" and r["status"] != "refusal":
            q = questions[r["question_id"]]
            verdict = grader.grade(q, gold.get(q.id), "refusal")
            r.update(status="refusal", error_type="refusal", grade=verdict["grade"],
                     detail=verdict["detail"], regraded="refusal marker inside code block")
            changed += 1
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"{path.name}: {changed} answers re-graded as refusals")
