"""
Setups 3 (written docs) and 4 (semantic layer) must carry the same information.
Both texts are rendered from the same sources; these tests make sure it stays so.
"""
from copilot import context, sqlguard, config


def test_same_knowledge_in_docs_and_semantic_layer(built):
    k = context.load_knowledge()
    docs, sem = context.docs_text(), context.semantic_text()
    assert k.metrics and k.dimensions and len(k.rules) == 7
    for d in k.dimensions:
        assert d.description in docs and d.description in sem, d.name
    for m in k.metrics:
        for piece in (m.name, m.description, m.definition):
            assert piece in docs and piece in sem, (m.name, piece)
    for _, drop_if, why in k.rules:
        assert drop_if in docs and drop_if in sem
        assert why in docs and why in sem


def test_every_fact_column_is_in_the_semantic_layer(built):
    """Nothing in fct_trips is hidden from setup 4, and nothing extra is documented."""
    con = sqlguard.connect(config.WAREHOUSE_DB)
    columns = {r[0] for r in con.execute("DESCRIBE fct_trips").fetchall()}
    con.close()
    assert columns == {d.name for d in context.load_knowledge().dimensions}
