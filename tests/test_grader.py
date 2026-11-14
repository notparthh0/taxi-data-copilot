"""The grading rules. These decide every number in the paper, so each rule has a test."""
import datetime as dt

from copilot import grader
from copilot.benchmark import Question

Q = Question(id="t", question="?", difficulty=1, category="x")
GOLD = {"columns": ["v"], "rows": [[19.7441]], "raw_columns": ["v"], "raw_rows": [[19.5223]], "raw_diverges": True}


def g(rows, q=Q, gold=GOLD, status="ok", error_type=""):
    return grader.grade(q, gold, status, rows, error_type)["grade"]


def test_exact_and_rounded_numbers_are_correct():
    assert g([[19.7441]]) == "correct"
    assert g([[19.74]]) == "correct"            # rounded to 2 decimals
    assert g([[19.744]]) == "correct"


def test_the_naive_raw_answer_is_a_silent_error():
    """The raw average fare is 1.1% off: it must NOT pass the tolerance."""
    verdict = grader.grade(Q, GOLD, "ok", [[19.5223]])
    assert verdict["grade"] == "silent_error" and verdict["matches_naive_raw"] is True


def test_small_differences_beyond_tolerance_are_wrong():
    assert g([[19.80]]) == "silent_error"       # 0.28% off
    assert g([[20]]) == "silent_error"          # rounding to a whole number is not accepted


def test_errors_and_refusals():
    assert g([], status="error", error_type="sql_error") == "error_or_refusal"
    assert g([], status="refusal") == "error_or_refusal"
    assert g([]) == "silent_error"              # ran fine, returned nothing


def test_unanswerable_questions():
    u = Question(id="u", question="?", difficulty=2, category="unanswerable", answerable=False)
    assert g([], q=u, gold=None, status="refusal") == "correct"
    assert g([[0.0]], q=u, gold=None) == "silent_error"
    assert g([], q=u, gold=None, status="error", error_type="sql_error") == "error_or_refusal"


def test_extra_columns_are_fine_missing_columns_are_not():
    gold = {"columns": ["zone"], "rows": [["JFK Airport"]], "raw_diverges": False}
    assert g([["jfk airport", 1887939]], gold=gold) == "correct"
    assert g([[1887939]], gold=gold) == "silent_error"


def test_row_order_only_matters_when_asked():
    gold = {"columns": ["b", "n"], "rows": [["Manhattan", 10], ["Queens", 5]], "raw_diverges": False}
    flipped = [["Queens", 5], ["Manhattan", 10]]
    assert g(flipped, gold=gold) == "correct"
    ordered = Question(id="o", question="?", difficulty=2, category="x", ordered=True)
    assert g(flipped, q=ordered, gold=gold) == "silent_error"
    assert g([["Manhattan", 5], ["Queens", 10]], gold=gold) == "silent_error"   # values on the wrong rows


def test_row_count_must_match():
    gold = {"columns": ["z"], "rows": [["A"]], "raw_diverges": False}
    assert g([["A"], ["B"]], gold=gold) == "silent_error"


def test_label_columns_can_be_skipped():
    q = Question(id="m", question="?", difficulty=2, category="x", ordered=True, skip=("month_key",))
    gold = {"columns": ["month_key", "n"], "rows": [["2023-01", 10], ["2023-02", 20]], "raw_diverges": False}
    assert g([[dt.date(2023, 1, 1), 10], [dt.date(2023, 2, 1), 20]], q=q, gold=gold) == "correct"
    assert g([[1, 20], [2, 10]], q=q, gold=gold) == "silent_error"


def test_percent_and_fraction():
    q = Question(id="p", question="?", difficulty=2, category="x", percent=True)
    gold = {"columns": ["v"], "rows": [[22.326]], "raw_diverges": False}
    assert g([[22.33]], q=q, gold=gold) == "correct"
    assert g([[0.22326]], q=q, gold=gold) == "correct"
    assert g([[0.22326]], gold=gold) == "silent_error"       # only when the question is a percentage


def test_month_and_date_spellings():
    q = Question(id="m", question="?", difficulty=2, category="x", month_answer=True)
    gold = {"columns": ["m"], "rows": [[5]], "raw_diverges": False}
    for answer in (5, "2023-05", dt.date(2023, 5, 1), dt.datetime(2023, 5, 1), "May"):
        assert g([[answer]], q=q, gold=gold) == "correct", answer
    assert g([["2023-06"]], q=q, gold=gold) == "silent_error"
    gold = {"columns": ["d"], "rows": [["2023-12-14"]], "raw_diverges": False}
    assert g([[dt.datetime(2023, 12, 14)]], gold=gold) == "correct"
