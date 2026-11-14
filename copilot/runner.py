"""Asks one model one question in one setup, runs the answer, and grades it."""

from copilot import grader, prompts, sqlguard
from copilot.setups import ExecResult

MAX_ROWS_KEPT = 50


def answer_question(client, setup, question, gold: dict) -> dict:
    system, user = prompts.build(setup, question.question)
    record = {"setup": setup.key, "question_id": question.id}
    try:
        text, info = client.generate(system, user)
    except Exception as exc:  # noqa: BLE001  (model unavailable: recorded, not graded as the model's fault)
        return {**record, "llm_failed": True, "error": str(exc)[:300]}
    kind, action = prompts.parse(setup, text)
    if kind == "refusal":
        status, result = "refusal", ExecResult("error", error_type="refusal", error=str(action))
    elif kind == "unparseable":
        status, result = "error", ExecResult("error", error_type="unparseable", error=str(action))
    else:
        try:
            result = setup.execute(action)
        except sqlguard.HarnessError as exc:      # our infrastructure failed: do not grade
            return {**record, "llm_failed": True, "error": f"harness: {exc}"[:300]}
        status = "refusal" if result.error_type == "refusal" else result.status
    verdict = grader.grade(question, gold, status, result.rows, result.error_type)
    return {**record, "reply": text[:2000], "status": status, "error_type": result.error_type,
            "error": result.error[:300], "sql": result.sql[:3000],
            "action": action if isinstance(action, dict) else None,
            "n_rows": len(result.rows), "rows": result.rows[:MAX_ROWS_KEPT],
            "grade": verdict["grade"], "detail": verdict.get("detail", ""),
            "matches_naive_raw": verdict.get("matches_naive_raw", False),
            "llm_seconds": info["seconds"], "sql_seconds": result.seconds,
            "tokens_in": info["tokens_in"], "tokens_out": info["tokens_out"]}
