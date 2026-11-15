"""The prompt is identical in every setup except for the context block."""

import json
import re

SYSTEM_SQL = (
    "You are a careful data analyst. You answer business questions about New York City "
    "yellow taxi trips by writing one DuckDB SQL query.\n"
    "Rules:\n"
    "- Reply with exactly one SELECT statement inside a ```sql code block, and nothing else.\n"
    "- Return only the columns the question asks for.\n"
    "- If the question cannot be answered from this data, do not guess. Reply with exactly:\n"
    "  CANNOT_ANSWER: <one short reason>"
)

SYSTEM_SEMANTIC = (
    "You are a careful data analyst. You answer business questions about New York City "
    "yellow taxi trips by querying a semantic layer.\n"
    "Rules:\n"
    "- Reply with exactly one JSON object inside a ```json code block, and nothing else.\n"
    "- If the question cannot be answered with the metrics and dimensions listed, do not guess. "
    'Reply with {"cannot_answer": "<one short reason>"}.'
)


def build(setup, question_text: str):
    """Returns (system, user). The context comes first so it can be cached across questions."""
    system = SYSTEM_SEMANTIC if setup.mode == "semantic" else SYSTEM_SQL
    return system, f"{setup.context()}\n\n# Question\n{question_text}"


_FENCE = re.compile(r"```(?:sql|json|duckdb)?\s*(.*?)```", re.S | re.I)


def parse(setup, text: str):
    """
    Model reply -> (kind, action).
      ('refusal', reason)   the model said it cannot answer
      ('action', sql_or_request)
      ('unparseable', text)
    """
    text = (text or "").strip()
    fenced = _FENCE.search(text)
    body = fenced.group(1).strip() if fenced else text
    if setup.mode == "semantic":
        start, end = body.find("{"), body.rfind("}")
        if start == -1 or end <= start:
            if "cannot_answer" in text.lower() or text.upper().startswith("CANNOT_ANSWER"):
                return "refusal", text[:300]
            return "unparseable", text[:500]
        try:
            request = json.loads(body[start:end + 1])
        except ValueError:
            return "unparseable", text[:500]
        if isinstance(request, dict) and "cannot_answer" in request:
            return "refusal", str(request["cannot_answer"])[:300]
        return "action", request
    # The refusal marker anywhere in the reply counts as a refusal, even when the model
    # wrapped it in a code block or wrote "SELECT CANNOT_ANSWER: ...".
    if re.search(r"CANNOT[_ ]ANSWER", text, re.I):
        return "refusal", text[:300]
    if not body:
        return "unparseable", text[:500]
    return "action", body
