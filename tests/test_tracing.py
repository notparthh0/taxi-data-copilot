from copilot import tracing


def test_observe_is_a_no_op_without_langfuse_keys():
    tracing._client = None
    with tracing.observe("x", as_type="generation", model="m") as obs:
        assert obs is None
    assert tracing.langfuse() is None
