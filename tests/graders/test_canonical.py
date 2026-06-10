from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.graders.canonical import canonicalize


def test_sorts_mapping_keys_recursively_and_freezes_sequences() -> None:
    value = {"b": 1, "a": [{"d": 1, "c": 2}]}

    result = canonicalize(value)

    assert result == {"a": ({"c": 2, "d": 1},), "b": 1}
    assert list(result) == ["a", "b"]
    assert isinstance(result["a"], tuple)


def test_values_are_never_coerced() -> None:
    assert canonicalize({"n": "1"}) == {"n": "1"}
    assert canonicalize({"n": 1}) == {"n": 1}
    assert canonicalize({"n": "1"}) != canonicalize({"n": 1})


json_values = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda children: (
        st.lists(children, max_size=4)
        | st.dictionaries(st.text(max_size=8), children, max_size=4)
    ),
    max_leaves=16,
)


@given(value=json_values)
def test_canonicalize_is_idempotent(value) -> None:
    once = canonicalize(value)

    assert canonicalize(once) == once
