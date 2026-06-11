import copy

from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS, apply

_SEGMENTS = st.text(alphabet="abcdefgh", min_size=1, max_size=6)
_PATHS = st.lists(_SEGMENTS, min_size=1, max_size=3).map("/".join)
_CONTENTS = st.text(max_size=50)
_TREES = st.dictionaries(_PATHS, _CONTENTS, max_size=4)


def _calls(path: str, content: str) -> tuple[tuple[str, dict], ...]:
    return (
        ("read_file", {"path": path}),
        ("write_file", {"path": path, "content": content}),
        ("list_files", {}),
        ("run_tests", {}),
    )


@given(tree=_TREES, path=_PATHS, content=_CONTENTS)
def test_apply_never_mutates_the_input_state(
    tree: dict[str, str], path: str, content: str
) -> None:
    state = {"files": tree}
    snapshot = copy.deepcopy(state)
    for name, arguments in _calls(path, content):
        apply(
            registry=CODE_WORLD_TOOLS, name=name, arguments=arguments, state=state
        )
        assert state == snapshot


@given(tree=_TREES, path=_PATHS, content=_CONTENTS)
def test_apply_is_deterministic(
    tree: dict[str, str], path: str, content: str
) -> None:
    state = {"files": tree}
    for name, arguments in _calls(path, content):
        first = apply(
            registry=CODE_WORLD_TOOLS, name=name, arguments=arguments, state=state
        )
        second = apply(
            registry=CODE_WORLD_TOOLS, name=name, arguments=arguments, state=state
        )
        assert first == second
