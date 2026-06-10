from agent_eval_lab.graders.canonicalize import canonicalize


def test_sorts_object_keys():
    assert canonicalize({"b": 1, "a": 2}) == canonicalize({"a": 2, "b": 1})


def test_is_idempotent():
    value = {"b": [3, {"y": 1, "x": 2}], "a": "s"}
    once = canonicalize(value)
    assert canonicalize(once) == once


def test_preserves_values_no_coercion():
    # canonicalization must NOT turn "1" into 1.
    assert canonicalize({"n": "1"}) != canonicalize({"n": 1})


def test_distinguishes_bool_from_int():
    assert canonicalize(True) != canonicalize(1)


def test_lists_keep_order():
    assert canonicalize([1, 2, 3]) != canonicalize([3, 2, 1])
