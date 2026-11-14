"""
Grades one answer as:  correct  |  silent_error  |  error_or_refusal

  correct           the returned values match the gold answer
  silent_error      the query ran and returned something, but it is wrong
                    (nothing tells the user it is wrong)
  error_or_refusal  SQL error, timeout, blocked by the guard, or the model said it cannot answer

For questions the data cannot answer, saying so is `correct` and any returned
answer is a `silent_error`.

Matching rules (fixed before any model was run):
  * Numbers match if they are within 0.1% of the gold value, or equal the gold value
    rounded to 2-6 decimals. (0.1% is far tighter than the dirt in the raw data:
    the raw average fare is 1.1% off.)
  * Text matches ignoring case and surrounding spaces. Dates match as dates.
  * Extra columns in the answer are fine. Every compared gold column must be present,
    and the number of rows must be the same.
  * Row order matters only when the question asks for an order.
"""

import datetime as dt
import itertools
import math
from decimal import Decimal

from copilot.benchmark import month_spellings

REL_TOL = 1e-3
CORRECT, SILENT, ERROR = "correct", "silent_error", "error_or_refusal"


def canon(v):
    """Bring a value to a comparable form: float, lower-case text, or None."""
    if v is None:
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float, Decimal)):
        f = float(v)
        return None if math.isnan(f) else f
    if isinstance(v, dt.datetime):
        return v.date().isoformat() if v.time() == dt.time(0) else v.isoformat(sep=" ")
    if isinstance(v, dt.date):
        return v.isoformat()
    s = str(v).strip().casefold()
    if s.endswith(" 00:00:00") and len(s) == 19:      # a midnight timestamp written as text
        s = s[:10]
    return s


def _as_number(v):
    if isinstance(v, float):
        return v
    if isinstance(v, str):
        try:
            return float(v.replace(",", ""))
        except ValueError:
            return None
    return None


def numbers_match(pred: float, gold: float) -> bool:
    if math.isclose(pred, gold, rel_tol=REL_TOL, abs_tol=1e-9):
        return True
    return any(math.isclose(pred, round(gold, d), rel_tol=0, abs_tol=1e-9) for d in range(2, 7))


def values_match(pred, gold, percent: bool = False) -> bool:
    pred, gold = canon(pred), canon(gold)
    if pred is None or gold is None:
        return pred is None and gold is None
    if isinstance(gold, float):
        p = _as_number(pred)
        if p is None:
            return False
        return numbers_match(p, gold) or (percent and numbers_match(p * 100, gold))
    if isinstance(pred, float):                       # gold is text, answer is a number
        g = _as_number(gold)
        return g is not None and numbers_match(pred, g)
    return pred == gold


def _sort_key(row):
    def key(v):
        v = canon(v)
        if v is None:
            return (0, "")
        if isinstance(v, float):
            return (1, f"{v:030.6f}" if v >= 0 else f"-{-v:030.6f}")
        return (2, v)
    return tuple(key(v) for v in row)


def _column_matches(pred_col, gold_col, percent):
    return all(values_match(p, g, percent) for p, g in zip(pred_col, gold_col))


def tables_match(pred_rows, gold_rows, ordered=False, skip_idx=(), percent=False) -> bool:
    """True if every compared gold column appears in the answer with the same values, row by row."""
    if len(pred_rows) != len(gold_rows):
        return False
    if not gold_rows:
        return True
    keep = [j for j in range(len(gold_rows[0])) if j not in skip_idx]
    gold = [[r[j] for j in keep] for r in gold_rows]
    n_pred_cols = len(pred_rows[0]) if pred_rows[0] is not None else 0
    if n_pred_cols < len(keep):
        return False
    # Pick a distinct answer column for each gold column, then check the rows line up.
    for cols in itertools.permutations(range(n_pred_cols), len(keep)):
        pred = [[r[c] for c in cols] for r in pred_rows]
        if not ordered:
            pred, g = sorted(pred, key=_sort_key), sorted(gold, key=_sort_key)
        else:
            g = gold
        if all(_column_matches([r[k] for r in pred], [r[k] for r in g], percent) for k in range(len(keep))):
            return True
        if n_pred_cols > 8:          # avoid a combinatorial blow-up on very wide answers
            break
    return False


def answer_matches(question, gold_columns, gold_rows, pred_rows) -> bool:
    skip_idx = tuple(i for i, c in enumerate(gold_columns) if c in question.skip)
    if tables_match(pred_rows, gold_rows, question.ordered, skip_idx, question.percent):
        return True
    # A single-value answer written another way (e.g. month 5 as '2023-05' or 'May').
    if len(gold_rows) == 1 and len(gold_rows[0]) == 1 and len(pred_rows) == 1:
        alternatives = list(question.also_accept)
        if question.month_answer:
            alternatives += month_spellings(gold_rows[0][0])
        for alt in alternatives:
            if any(values_match(v, alt) for v in pred_rows[0]):
                return True
    return False


def grade(question, gold: dict, status: str, rows=None, error_type: str = "") -> dict:
    """
    status: 'ok' (rows returned), 'refusal', or 'error'.
    gold:   this question's entry from results/gold_answers.json (None for unanswerable questions).
    """
    rows = rows or []
    if not question.answerable:
        if status == "refusal":
            return {"grade": CORRECT, "detail": "correctly refused"}
        if status == "ok":
            return {"grade": SILENT, "detail": "answered a question the data cannot answer"}
        return {"grade": ERROR, "detail": error_type or "error"}
    if status == "refusal":
        return {"grade": ERROR, "detail": "refused an answerable question"}
    if status != "ok":
        return {"grade": ERROR, "detail": error_type or "error"}
    if answer_matches(question, gold["columns"], gold["rows"], rows):
        return {"grade": CORRECT, "detail": ""}
    detail = "empty result" if not rows else "wrong values"
    same_as_raw = bool(gold.get("raw_diverges")) and bool(rows) and answer_matches(
        question, gold["raw_columns"], gold["raw_rows"], rows)
    return {"grade": SILENT, "detail": detail, "matches_naive_raw": same_as_raw}
