from agent_eval_lab.runners.round_budget import (
    DOMAIN_MAX_ROUNDS,
    resolve_max_rounds,
)
from agent_eval_lab.tasks.parse import parse_task


def _task(*, max_rounds=None):
    meta = {"split": "dev", "version": "1", "provenance": "hand"}
    if max_rounds is not None:
        meta["max_rounds"] = max_rounds
    return parse_task(
        {
            "id": "t1",
            "capability": "edit",
            "input": {
                "messages": [{"type": "message", "role": "user", "content": "x"}],
                "available_tools": [],
            },
            "verification": {
                "type": "tool_call_match",
                "expected_tool_calls": [],
                "match": "exact_sequence",
            },
            "metadata": meta,
        }
    )


def test_default_per_domain_caps():
    assert DOMAIN_MAX_ROUNDS == {"F": 20, "D": 50}


def test_domain_default_used_when_no_task_override():
    assert resolve_max_rounds(domain="F", task=_task()) == 20
    assert resolve_max_rounds(domain="D", task=_task()) == 50


def test_task_override_wins_over_domain_default():
    assert resolve_max_rounds(domain="F", task=_task(max_rounds=40)) == 40
    assert resolve_max_rounds(domain="D", task=_task(max_rounds=7)) == 7


def test_unknown_domain_falls_back_to_task_override_or_none():
    # B is config-only/deferred (no live runner); an unmapped domain returns the
    # task override if present, else None (unbounded — never invents a cap).
    assert resolve_max_rounds(domain="B", task=_task()) is None
    assert resolve_max_rounds(domain="B", task=_task(max_rounds=12)) == 12


def test_resolve_max_rounds_rejects_zero_and_negative():
    # F4: max_rounds=0 or negative is a config error (fires one API call then
    # stops, never a real budget). resolve_max_rounds must raise ValueError so the
    # misconfiguration surfaces at resolve time, not inside the loop.
    import pytest

    with pytest.raises(ValueError, match="max_rounds"):
        resolve_max_rounds(domain="D", task=_task(max_rounds=0))
    with pytest.raises(ValueError, match="max_rounds"):
        resolve_max_rounds(domain="D", task=_task(max_rounds=-1))
    with pytest.raises(ValueError, match="max_rounds"):
        resolve_max_rounds(domain="D", task=_task(max_rounds=-99))
