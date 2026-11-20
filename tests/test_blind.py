"""The blind question set (benchmark/blind/) is well formed and kept apart from the frozen 150."""
from copilot.benchmark import BLIND_DIR, load_questions


def test_blind_set_is_well_formed():
    qs = load_questions(directory=BLIND_DIR)
    assert len(qs) == 15
    assert [q.id for q in qs] == [f"b{i:03d}" for i in range(1, 16)]
    assert sorted(q.difficulty for q in qs).count(1) == 5
    for q in qs:
        assert q.answerable and q.gold_sql and q.naive_raw_sql, q.id
        assert q.author == "claude-fresh-context" and q.written_blind, q.id
        assert "?" in q.question, q.id


def test_blind_ids_do_not_clash_with_the_main_set():
    from copilot.benchmark import load_questions as main
    assert not {q.id for q in load_questions(directory=BLIND_DIR)} & {q.id for q in main()}
