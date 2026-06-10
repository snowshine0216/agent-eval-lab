from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.prompt import apply_system_prompt


def test_none_prompt_returns_messages_unchanged() -> None:
    messages = (
        MessageTurn(role="system", content="orig"),
        MessageTurn(role="user", content="hi"),
    )
    assert apply_system_prompt(messages, None) == messages


def test_replaces_existing_leading_system_turn() -> None:
    messages = (
        MessageTurn(role="system", content="orig"),
        MessageTurn(role="user", content="hi"),
    )
    out = apply_system_prompt(messages, "PLAN FIRST")
    assert out == (
        MessageTurn(role="system", content="PLAN FIRST"),
        MessageTurn(role="user", content="hi"),
    )


def test_prepends_system_turn_when_none_present() -> None:
    messages = (MessageTurn(role="user", content="hi"),)
    out = apply_system_prompt(messages, "PLAN FIRST")
    assert out == (
        MessageTurn(role="system", content="PLAN FIRST"),
        MessageTurn(role="user", content="hi"),
    )


def test_does_not_mutate_input() -> None:
    messages = (
        MessageTurn(role="system", content="orig"),
        MessageTurn(role="user", content="hi"),
    )
    apply_system_prompt(messages, "PLAN FIRST")
    assert messages[0].content == "orig"  # input untouched
