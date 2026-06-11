"""Hypothesis properties for the pure overlay and execution hash."""

import copy

from hypothesis import assume, given
from hypothesis import strategies as st

from agent_eval_lab.graders.execution import (
    OverlaidTree,
    execution_hash,
    overlay_oracle,
)
from agent_eval_lab.tasks.schema import ExecutionSpec

_SEGMENTS = st.text(alphabet="abcdefgh", min_size=1, max_size=6)
_PATHS = st.lists(_SEGMENTS, min_size=1, max_size=3).map("/".join)
_CONTENTS = st.text(max_size=50)
_TREES = st.dictionaries(_PATHS, _CONTENTS, max_size=4)
_ORACLES = st.dictionaries(_PATHS, _CONTENTS, min_size=1, max_size=4)
_TIMEOUTS = st.one_of(
    st.none(), st.floats(min_value=0.1, max_value=120.0, allow_nan=False)
)


@given(tree=_TREES, oracle=_ORACLES)
def test_overlay_never_mutates_inputs(
    tree: dict[str, str], oracle: dict[str, str]
) -> None:
    tree_snapshot = copy.deepcopy(tree)
    oracle_snapshot = copy.deepcopy(oracle)
    overlay_oracle(tree, oracle)
    assert tree == tree_snapshot
    assert oracle == oracle_snapshot


@given(tree=_TREES, oracle=_ORACLES)
def test_overlay_oracle_content_always_wins_and_displacement_is_the_overlap(
    tree: dict[str, str], oracle: dict[str, str]
) -> None:
    # Lowercase-only path alphabet => no canonical collisions are generable,
    # so the overlay always combines.
    overlaid = overlay_oracle(tree, oracle)
    assert isinstance(overlaid, OverlaidTree)
    assert overlaid.displaced_paths == tuple(sorted(set(tree) & set(oracle)))
    for path, content in oracle.items():
        assert overlaid.files[path] == content
    for path in set(tree) - set(oracle):
        assert overlaid.files[path] == tree[path]


@given(tree=_TREES, oracle=_ORACLES, timeout_s=_TIMEOUTS)
def test_execution_hash_is_deterministic(
    tree: dict[str, str], oracle: dict[str, str], timeout_s: float | None
) -> None:
    spec = ExecutionSpec(held_out_tests=oracle, timeout_s=timeout_s)
    again = ExecutionSpec(held_out_tests=dict(oracle), timeout_s=timeout_s)
    assert execution_hash(spec, tree) == execution_hash(again, dict(tree))


@given(tree=_TREES, oracle=_ORACLES, new_content=_CONTENTS)
def test_execution_hash_changes_when_any_oracle_content_changes(
    tree: dict[str, str], oracle: dict[str, str], new_content: str
) -> None:
    path = sorted(oracle)[0]
    assume(oracle[path] != new_content)
    spec = ExecutionSpec(held_out_tests=oracle)
    mutated = ExecutionSpec(held_out_tests={**oracle, path: new_content})
    assert execution_hash(spec, tree) != execution_hash(mutated, tree)


@given(tree=_TREES, oracle=_ORACLES, extra=_PATHS, content=_CONTENTS)
def test_execution_hash_changes_when_the_final_tree_changes(
    tree: dict[str, str], oracle: dict[str, str], extra: str, content: str
) -> None:
    changed = {**tree, extra: content}
    assume(changed != tree)
    spec = ExecutionSpec(held_out_tests=oracle)
    assert execution_hash(spec, tree) != execution_hash(spec, changed)
