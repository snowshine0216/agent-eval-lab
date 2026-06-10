import pytest

from agent_eval_lab.graders.judge import (
    JudgeParseFailure,
    JudgeVerdict,
    build_judge_prompt,
    collect_judge_specs,
    grade_llm_judge,
    parse_judge_response,
    prompt_hash,
)
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.tasks.schema import LlmJudgeSpec


def _trajectory(*turns) -> Trajectory:
    return Trajectory(
        turns=turns,
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
    )


SPEC = LlmJudgeSpec(rubric="Judge summary fidelity.", judge_model="m", scale=(1, 5))

TRAJ = _trajectory(
    MessageTurn(role="user", content="Close ticket T-1 and tell me."),
    ToolCallTurn(
        tool_calls=(
            ToolCall(call_id="c1", name="update_ticket",
                     arguments={"status": "closed", "ticket_id": "T-1"}),
        )
    ),
    ToolResultTurn(call_id="c1", outcome=ToolSuccess(result={"ok": True})),
    MessageTurn(role="assistant", content="Done. I closed ticket T-1."),
)


def test_build_judge_prompt_is_deterministic() -> None:
    a = build_judge_prompt(spec=SPEC, trajectory=TRAJ)
    b = build_judge_prompt(spec=SPEC, trajectory=TRAJ)
    assert a == b
    assert prompt_hash(a) == prompt_hash(b)


def test_prompt_renders_scale_and_score_contract() -> None:
    messages = build_judge_prompt(spec=SPEC, trajectory=TRAJ)
    text = "\n".join(m["content"] for m in messages)
    assert "score 1-5" in text or "1-5" in text
    assert "SCORE:" in text
    assert SPEC.rubric in text


def test_prompt_renders_trajectory_in_canonical_order() -> None:
    messages = build_judge_prompt(spec=SPEC, trajectory=TRAJ)
    text = "\n".join(m["content"] for m in messages)
    # sort_keys=True: status(s) before ticket_id(t)
    assert 'update_ticket({"status": "closed", "ticket_id": "T-1"})' in text
    assert "ok:" in text  # ToolSuccess discriminator
    assert "Done. I closed ticket T-1." in text


def test_different_scale_changes_prompt_and_hash() -> None:
    other = LlmJudgeSpec(rubric=SPEC.rubric, judge_model="m", scale=(1, 7))
    assert build_judge_prompt(spec=SPEC, trajectory=TRAJ) != build_judge_prompt(
        spec=other, trajectory=TRAJ
    )
    assert prompt_hash(build_judge_prompt(spec=SPEC, trajectory=TRAJ)) != prompt_hash(
        build_judge_prompt(spec=other, trajectory=TRAJ)
    )


def test_failure_outcome_renders_error_discriminator() -> None:
    traj = _trajectory(
        ToolCallTurn(tool_calls=(
            ToolCall(call_id="c1", name="get_account", arguments={"user_id": "u1"}),
        )),
        ToolResultTurn(call_id="c1", outcome=ToolFailure(error="not found")),
        MessageTurn(role="assistant", content="I looked it up."),
    )
    msgs = build_judge_prompt(spec=SPEC, trajectory=traj)
    text = "\n".join(m["content"] for m in msgs)
    assert "error:not found" in text


# Task 4: parse_judge_response tests


def test_parses_well_formed_reply() -> None:
    out = parse_judge_response("The summary is faithful.\nSCORE: 5", scale=(1, 5))
    assert isinstance(out, JudgeVerdict)
    assert out.score == 5
    assert out.rationale == "The summary is faithful.\nSCORE: 5"
    assert out.raw == "The summary is faithful.\nSCORE: 5"
    assert out.judge_model == ""   # edge stamps this later
    assert out.prompt_hash == ""


def test_no_extractable_integer_is_no_score() -> None:
    out = parse_judge_response("I cannot score this.", scale=(1, 5))
    assert out == JudgeParseFailure(raw="I cannot score this.", error="no_score")


def test_out_of_range_integer_is_out_of_range() -> None:
    out = parse_judge_response("SCORE: 9", scale=(1, 5))
    assert isinstance(out, JudgeParseFailure)
    assert out.error == "out_of_range"


def test_conflicting_scores_is_conflicting() -> None:
    out = parse_judge_response("SCORE: 4\nSCORE: 2", scale=(1, 5))
    assert isinstance(out, JudgeParseFailure)
    assert out.error == "conflicting_scores"


def test_score_must_be_a_score_line_not_any_integer() -> None:
    # An integer in prose with no SCORE line is no_score, never coerced.
    prose = "The agent made 3 tool calls and was faithful."
    out = parse_judge_response(prose, scale=(1, 5))
    assert out == JudgeParseFailure(raw=prose, error="no_score")


# Task 5: grade_llm_judge tests


def _verdict_for(spec, trajectory, score, *, model="deepseek:deepseek-v4-pro"):
    h = prompt_hash(build_judge_prompt(spec=spec, trajectory=trajectory))
    return h, JudgeVerdict(
        score=score, rationale="r", raw=f"raw\nSCORE: {score}",
        judge_model=model, prompt_hash=h,
    )


def test_grade_passes_at_threshold_4() -> None:
    h, v = _verdict_for(SPEC, TRAJ, 4)
    result = grade_llm_judge(spec=SPEC, trajectory=TRAJ, verdicts={h: v})
    assert result.passed is True
    assert result.grader_id == "llm_judge"
    assert result.failure_reason is None
    ev = result.evidence
    assert ev == {
        "judge_model": "deepseek:deepseek-v4-pro",
        "prompt_hash": h,
        "score": 4,
        "scale": [1, 5],
        "threshold": 4,
        "binary_label": "faithful",
        "rationale": "r",
        "raw": "raw\nSCORE: 4",
    }


def test_grade_fails_below_threshold() -> None:
    h, v = _verdict_for(SPEC, TRAJ, 3)
    result = grade_llm_judge(spec=SPEC, trajectory=TRAJ, verdicts={h: v})
    assert result.passed is False
    assert result.failure_reason is None
    assert result.evidence["binary_label"] == "unfaithful"


def test_grade_missing_verdict_is_judge_not_run() -> None:
    result = grade_llm_judge(spec=SPEC, trajectory=TRAJ, verdicts={})
    assert result.passed is False
    assert result.failure_reason is None
    assert result.evidence["judge"] == "not_run"


def test_grade_judge_error_at_key_is_structured_nonpass() -> None:
    from agent_eval_lab.runners.judge_edge import JudgeError

    h = prompt_hash(build_judge_prompt(spec=SPEC, trajectory=TRAJ))
    err = JudgeError(kind="http", error="500", prompt_hash=h, judge_model="m")
    result = grade_llm_judge(spec=SPEC, trajectory=TRAJ, verdicts={h: err})
    assert result.passed is False
    assert result.failure_reason is None
    assert result.evidence["judge"] == "error"
    assert result.evidence["kind"] == "http"


def test_judge_module_imports_no_http_client() -> None:
    import agent_eval_lab.graders.judge as judge_mod

    src = open(judge_mod.__file__).read()
    assert "httpx" not in src
    assert "chat_completion" not in src


# Task 6: collect_judge_specs tests


from agent_eval_lab.tasks.schema import AllOf, FinalStateSpec, StateEquals  # noqa: E402


def test_collect_finds_top_level_judge() -> None:
    assert collect_judge_specs(SPEC) == (SPEC,)


def test_collect_ignores_deterministic_specs() -> None:
    spec = FinalStateSpec(constraints=(StateEquals(path="a.b", expected=1),))
    assert collect_judge_specs(spec) == ()


def test_collect_recurses_all_of() -> None:
    det = FinalStateSpec(constraints=(StateEquals(path="a.b", expected=1),))
    spec = AllOf(specs=(det, SPEC, AllOf(specs=(SPEC,))))
    assert collect_judge_specs(spec) == (SPEC, SPEC)


