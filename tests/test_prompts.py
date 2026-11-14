"""Turning a model reply into an action."""
from copilot import prompts
from copilot.setups import get_setups

S = get_setups()


def test_sql_replies():
    sql = S["s2_modelled"]
    assert prompts.parse(sql, "```sql\nSELECT 1\n```") == ("action", "SELECT 1")
    assert prompts.parse(sql, "SELECT 1") == ("action", "SELECT 1")
    assert prompts.parse(sql, "CANNOT_ANSWER: no driver id")[0] == "refusal"
    assert prompts.parse(sql, "")[0] == "unparseable"


def test_semantic_replies():
    sem = S["s4_semantic"]
    assert prompts.parse(sem, '```json\n{"metrics": ["avg_fare"]}\n```') == ("action", {"metrics": ["avg_fare"]})
    assert prompts.parse(sem, '{"cannot_answer": "no such metric"}')[0] == "refusal"
    assert prompts.parse(sem, "I think the answer is 5")[0] == "unparseable"
    assert prompts.parse(sem, '{"metrics": [')[0] == "unparseable"


def test_benchmark_is_well_formed():
    from copilot.benchmark import load_questions
    qs = load_questions()
    assert len(qs) == 150
    assert sum(not q.answerable for q in qs) == 10
    for q in qs:
        assert "?" in q.question, q.id
        if q.answerable:
            assert q.gold_sql and q.naive_raw_sql, q.id
            assert "fct_trips" in q.gold_sql and "yellow_tripdata" in q.naive_raw_sql, q.id
