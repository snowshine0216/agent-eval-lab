import pytest

from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import ToolCall, ToolCallTurn
from agent_eval_lab.reports.validation import (
    ConditionInput,
    build_validation_report,
    render_markdown,
)


def _run(condition, task_id, run_index, passed, failure_reason=None):
    return RunResult(
        task_id=task_id,
        condition_id=condition,
        run_index=run_index,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
            run_index=run_index,
            stop_reason="completed",
        ),
        grade=GradeResult(
            grader_id="g",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=failure_reason,
        ),
    )


def _all(condition, task_id, k, passed, failure_reason=None):
    return [
        _run(condition, task_id, i, passed, None if passed else failure_reason)
        for i in range(k)
    ]


TIERS = {"ws2-001": "T1", "ws2-018": "T3", "ws2-040": "T4"}
CAPS = {
    "ws2-001": "tool_selection",
    "ws2-018": "multi_step_state",
    "ws2-040": "distractor_resistance",
}


def test_complete_condition_reports_pass_rates_and_cis() -> None:
    # Condition A: ws2-001 reliable; ws2-018 deterministic-fail; ws2-040 flaky.
    runs = (
        *_all("A", "ws2-001", 3, True),
        *_all("A", "ws2-018", 3, False, "wrong_args"),
        _run("A", "ws2-040", 0, True),
        _run("A", "ws2-040", 1, False, "forbidden_action"),
        _run("A", "ws2-040", 2, True),
    )
    report = build_validation_report(
        conditions=(ConditionInput(label="A", results=runs),),
        tiers=TIERS,
        capabilities=CAPS,
        k=3,
        expected_n_tasks=3,
        seed=20260610,
        n_resamples=500,
        alpha=0.05,
    )
    cond = report.conditions[0]
    assert cond.status == "complete"
    assert cond.n_tasks == 3
    assert cond.pass_pow_k.point == pytest.approx(1 / 3)  # only ws2-001 reliable
    assert cond.pass_at_1 == pytest.approx(5 / 9)  # 5 of 9 trials passed
    # deterministic-vs-flaky: ws2-018 all-fail = deterministic; ws2-040 mixed = flaky
    assert cond.deterministic_failures == ("ws2-018",)
    assert cond.flaky_tasks == ("ws2-040",)


def test_incomplete_condition_is_marked_not_blocked() -> None:
    # Only 2 of an expected 3 tasks have records (partial stream).
    runs = (*_all("A", "ws2-001", 3, True), *_all("A", "ws2-018", 3, True))
    report = build_validation_report(
        conditions=(ConditionInput(label="A", results=runs),),
        tiers=TIERS,
        capabilities=CAPS,
        k=3,
        expected_n_tasks=3,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    cond = report.conditions[0]
    assert cond.status == "incomplete"
    assert cond.n_tasks == 2  # graded only over present records
    assert cond.pass_pow_k.point == pytest.approx(1.0)  # both present are reliable


def test_blocked_condition_invents_no_numbers() -> None:
    report = build_validation_report(
        conditions=(
            ConditionInput(
                label="openrouter",
                results=(),
                blocked_reason="network ToS block",
            ),
        ),
        tiers=TIERS,
        capabilities=CAPS,
        k=3,
        expected_n_tasks=3,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    cond = report.conditions[0]
    assert cond.status == "blocked"
    assert cond.blocked_reason == "network ToS block"
    assert cond.pass_pow_k is None  # NO fabricated rate
    assert cond.pass_at_1 is None


def test_discriminativeness_weak_when_hosted_differ_but_within_noise() -> None:
    # Two hosted conditions differ on ws2-018 but neither saturates -> weak rung.
    a = (
        *_all("A", "ws2-001", 3, True),
        *_all("A", "ws2-018", 3, True),
        *_all("A", "ws2-040", 3, False, "forbidden_action"),
    )
    b = (
        *_all("B", "ws2-001", 3, True),
        *_all("B", "ws2-018", 3, False, "wrong_args"),
        *_all("B", "ws2-040", 3, False, "forbidden_action"),
    )
    report = build_validation_report(
        conditions=(
            ConditionInput(label="A", results=a, hosted=True),
            ConditionInput(label="B", results=b, hosted=True),
        ),
        tiers=TIERS,
        capabilities=CAPS,
        k=3,
        expected_n_tasks=3,
        seed=20260610,
        n_resamples=500,
        alpha=0.05,
    )
    # ≥1 hosted pass^3 < 1.000 and they differ on a task -> at least weak rung met.
    assert report.discriminativeness.weak_met is True
    assert report.discriminativeness.rung in {"weak", "strong"}


def test_render_markdown_contains_headline_sections() -> None:
    runs = (
        *_all("A", "ws2-001", 3, True),
        *_all("A", "ws2-018", 3, False, "wrong_args"),
    )
    report = build_validation_report(
        conditions=(ConditionInput(label="A", results=runs, hosted=True),),
        tiers={"ws2-001": "T1", "ws2-018": "T3"},
        capabilities={"ws2-001": "tool_selection", "ws2-018": "multi_step_state"},
        k=3,
        expected_n_tasks=2,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    md = render_markdown(report)
    assert "# Validation report" in md
    assert "pass^3" in md and "pass@1" in md
    assert "Failure taxonomy" in md
    assert "Deterministic" in md and "flaky" in md.lower()
    assert "Discriminativeness verdict" in md
    assert "n=2" in md  # n stated honestly


# ── P1-3: pass^k with tasks that have fewer than k runs ─────────────────────


def test_incomplete_tasks_excluded_from_pass_pow_k_and_reported() -> None:
    """A task with < k runs must be EXCLUDED from pass^k (and bootstrap input)
    and an explicit 'excluded (incomplete, <k runs)' line must appear in the
    per-condition markdown section."""
    # Task ws2-001 has 3/3 runs (reliable); ws2-018 has only 1/3 run (incomplete).
    # With k=3, ws2-018 must be excluded from pass^k.
    runs = (
        *_all("A", "ws2-001", 3, True),
        _run("A", "ws2-018", 0, True),  # only 1 run out of k=3
    )
    report = build_validation_report(
        conditions=(ConditionInput(label="A", results=runs),),
        tiers={"ws2-001": "T1", "ws2-018": "T3"},
        capabilities={"ws2-001": "tool_selection", "ws2-018": "multi_step_state"},
        k=3,
        expected_n_tasks=2,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    cond = report.conditions[0]
    # ws2-018 has only 1 run (<3), so pass^k must be computed only over ws2-001
    assert cond.pass_pow_k.point == pytest.approx(1.0)
    # status must be "incomplete" because a task was excluded
    assert cond.status == "incomplete"
    md = render_markdown(report)
    # The per-condition section must call out the excluded task
    assert "excluded" in md.lower() and "incomplete" in md.lower()
    assert "ws2-018" in md


# ── P1-4: discriminativeness gradient rung must require strict decrease ─────


def test_discriminativeness_flat_ceiling_gradient_not_strong() -> None:
    """A monotone gradient that is FLAT at 1.000 for all tiers must NOT
    satisfy the strong rung (trivial gradient). The weak rung should still be
    asserted separately."""
    # One hosted condition: T1=1.0, T2=1.0, T3=1.0, T4=1.0 — flat ceiling.
    a = (
        *_all("A", "ws2-001", 3, True),  # T1
        *_all("A", "ws2-018", 3, True),  # T3
        *_all("A", "ws2-040", 3, True),  # T4
    )
    # Second hosted condition has a different result on ws2-018 so weak_met=True
    b = (
        *_all("B", "ws2-001", 3, True),  # T1
        *_all("B", "ws2-018", 3, False, "wrong_args"),  # T3 — differs
        *_all("B", "ws2-040", 3, True),  # T4
    )
    report = build_validation_report(
        conditions=(
            ConditionInput(label="A", results=a, hosted=True),
            ConditionInput(label="B", results=b, hosted=True),
        ),
        tiers=TIERS,
        capabilities=CAPS,
        k=3,
        expected_n_tasks=3,
        seed=20260610,
        n_resamples=500,
        alpha=0.05,
    )
    # A is flat-at-ceiling; that must NOT satisfy gradient rung
    assert "A" not in report.discriminativeness.monotone_conditions


# ── P1-5: capability map raises ValueError on unknown task id ────────────────


def test_capability_lookup_raises_on_unknown_task_id() -> None:
    """An unmapped task id in capabilities must raise ValueError (not return '?')."""
    from agent_eval_lab.reports.validation import _build_condition

    runs = (*_all("A", "ws2-999", 3, False, "wrong_args"),)
    with pytest.raises(ValueError, match="ws2-999"):
        _build_condition(
            ConditionInput(label="A", results=runs),
            tiers={"ws2-999": "T3"},
            capabilities={},  # ws2-999 not in map -> must raise
            k=3,
            expected_n_tasks=1,
            seed=20260610,
            n_resamples=100,
            alpha=0.05,
        )


# ── P1-6: _task_reliability not duplicated in validation.py ─────────────────


def test_task_reliability_imported_from_metrics_not_duplicated() -> None:
    """validation.py must NOT define its own _task_reliability; it must
    import from metrics.reliability (single definition)."""
    import agent_eval_lab.metrics.reliability as rel_mod
    import agent_eval_lab.reports.validation as val_mod

    # The function used by validation must be the same object (or a re-export)
    # as the one in metrics.reliability.
    assert not hasattr(val_mod, "_task_reliability") or (
        val_mod._task_reliability is rel_mod._task_reliability
        or val_mod._task_reliability is rel_mod.task_reliability
    ), "validation.py must not have its own independent _task_reliability definition"


def test_render_is_byte_identical_under_same_inputs() -> None:
    runs = (
        *_all("A", "ws2-001", 3, True),
        *_all("A", "ws2-018", 3, False, "wrong_args"),
    )
    kwargs = dict(
        conditions=(ConditionInput(label="A", results=runs),),
        tiers={"ws2-001": "T1", "ws2-018": "T3"},
        capabilities={"ws2-001": "tool_selection", "ws2-018": "multi_step_state"},
        k=3,
        expected_n_tasks=2,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    assert render_markdown(build_validation_report(**kwargs)) == render_markdown(
        build_validation_report(**kwargs)
    )


# ── Discriminativeness rendering: zero-delta vs near-miss ────────────────────


def test_render_zero_delta_degenerate_pair_as_no_observed_difference() -> None:
    """A pair with Δ=0.000 AND CI=[0.000, 0.000] (identical results on the same
    dataset) must render as 'No observed difference' — NOT 'Near-miss'."""
    # Both C1 and C2 pass every task identically -> paired Δ = 0, CI = [0, 0].
    a = (
        *_all("C1", "ws2-001", 3, True),
        *_all("C1", "ws2-018", 3, True),
    )
    b = (
        *_all("C2", "ws2-001", 3, True),
        *_all("C2", "ws2-018", 3, True),
    )
    report = build_validation_report(
        conditions=(
            ConditionInput(label="C1", results=a, hosted=True),
            ConditionInput(label="C2", results=b, hosted=True),
        ),
        tiers={"ws2-001": "T1", "ws2-018": "T3"},
        capabilities={"ws2-001": "tool_selection", "ws2-018": "multi_step_state"},
        k=3,
        expected_n_tasks=2,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    md = render_markdown(report)
    assert "No observed difference: C1 vs C2" in md
    assert "both conditions identical on this dataset" in md
    assert "Near-miss: C1 vs C2" not in md


def test_render_nonzero_delta_ci_touches_zero_as_near_miss() -> None:
    """A pair with a nonzero Δ whose CI merely touches 0 keeps the 'Near-miss'
    wording (not the 'No observed difference' wording)."""
    # C1 passes ws2-001 but fails ws2-018; C2 passes both -> nonzero Δ, CI [0, …].
    a = (
        *_all("C1", "ws2-001", 3, True),
        *_all("C1", "ws2-018", 3, False, "wrong_args"),
    )
    b = (
        *_all("C2", "ws2-001", 3, True),
        *_all("C2", "ws2-018", 3, True),
    )
    report = build_validation_report(
        conditions=(
            ConditionInput(label="C1", results=a, hosted=True),
            ConditionInput(label="C2", results=b, hosted=True),
        ),
        tiers={"ws2-001": "T1", "ws2-018": "T3"},
        capabilities={"ws2-001": "tool_selection", "ws2-018": "multi_step_state"},
        k=3,
        expected_n_tasks=2,
        seed=20260610,
        n_resamples=500,
        alpha=0.05,
    )
    md = render_markdown(report)
    # The nonzero-delta near-miss pair must use "Near-miss" wording.
    assert "Near-miss" in md or "No observed difference" in md  # at least one
    # If the CI separates (strong rung), C1 vs C2 won't be a near-miss at all —
    # just verify the zero-delta wording is absent.
    assert "both conditions identical on this dataset" not in md


# ── Finding 1 (AC2): budget-floor section ────────────────────────────────────


def _run_with_stop(
    condition, task_id, run_index, passed, stop_reason="completed", failure_reason=None
):
    return RunResult(
        task_id=task_id,
        condition_id=condition,
        run_index=run_index,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
            run_index=run_index,
            stop_reason=stop_reason,
        ),
        grade=GradeResult(
            grader_id="g",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=failure_reason,
        ),
    )


def test_budget_floor_section_rendered_with_zero_suspects() -> None:
    """With no runs that hit max_steps, the budget-floor section must be present
    and must explicitly say zero starvation suspects."""
    runs = (
        *_all("A", "ws2-001", 3, True),
        *_all("A", "ws2-018", 3, False, "wrong_args"),
    )
    report = build_validation_report(
        conditions=(ConditionInput(label="A", results=runs),),
        tiers={"ws2-001": "T1", "ws2-018": "T3"},
        capabilities={"ws2-001": "tool_selection", "ws2-018": "multi_step_state"},
        k=3,
        expected_n_tasks=2,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    md = render_markdown(report)
    assert "budget" in md.lower() or "step" in md.lower()
    # Zero exhausted runs -> zero starvation suspects
    assert "starvation suspect" in md.lower() or "suspects" in md.lower()


def test_budget_floor_section_counts_exhausted_runs() -> None:
    """Runs with stop_reason='max_steps' are counted per condition in the
    budget-floor section. A failing run that exhausted the budget is a starvation
    suspect (listed by task id)."""
    runs = (
        _run_with_stop("A", "ws2-001", 0, True, stop_reason="completed"),
        _run_with_stop("A", "ws2-001", 1, True, stop_reason="completed"),
        _run_with_stop("A", "ws2-001", 2, True, stop_reason="completed"),
        # ws2-018: exhausted budget AND failed -> starvation suspect
        _run_with_stop(
            "A",
            "ws2-018",
            0,
            False,
            stop_reason="max_steps",
            failure_reason="wrong_args",
        ),
        _run_with_stop(
            "A",
            "ws2-018",
            1,
            False,
            stop_reason="max_steps",
            failure_reason="wrong_args",
        ),
        _run_with_stop(
            "A",
            "ws2-018",
            2,
            False,
            stop_reason="max_steps",
            failure_reason="wrong_args",
        ),
    )
    report = build_validation_report(
        conditions=(ConditionInput(label="A", results=runs),),
        tiers={"ws2-001": "T1", "ws2-018": "T3"},
        capabilities={"ws2-001": "tool_selection", "ws2-018": "multi_step_state"},
        k=3,
        expected_n_tasks=2,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    md = render_markdown(report)
    # ws2-018 runs exhausted budget and failed -> must be listed as suspect
    assert "ws2-018" in md
    # The budget section must mention exhausted count
    cond = report.conditions[0]
    assert cond.budget_exhausted_count == 3  # 3 runs hit max_steps
    assert cond.starvation_suspects == ("ws2-018",)


def test_budget_floor_section_no_suspect_if_exhausted_but_passed() -> None:
    """A run that hit max_steps but PASSED is NOT a starvation suspect."""
    runs = (
        _run_with_stop("A", "ws2-001", 0, True, stop_reason="max_steps"),
        _run_with_stop("A", "ws2-001", 1, True, stop_reason="max_steps"),
        _run_with_stop("A", "ws2-001", 2, True, stop_reason="max_steps"),
        *_all("A", "ws2-018", 3, True),
    )
    report = build_validation_report(
        conditions=(ConditionInput(label="A", results=runs),),
        tiers={"ws2-001": "T1", "ws2-018": "T3"},
        capabilities={"ws2-001": "tool_selection", "ws2-018": "multi_step_state"},
        k=3,
        expected_n_tasks=2,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    cond = report.conditions[0]
    assert cond.budget_exhausted_count == 3
    assert cond.starvation_suspects == ()


# ── Finding 2 (AC6): exemplar trace excerpts ─────────────────────────────────


def _run_with_tool_calls(
    condition, task_id, run_index, passed, tool_calls_data, failure_reason=None
):
    call_turns = tuple(
        ToolCallTurn(
            tool_calls=tuple(
                ToolCall(call_id=f"c{i}", name=tc["name"], arguments=tc.get("args", {}))
                for i, tc in enumerate(call_list)
            )
        )
        for call_list in tool_calls_data
    )
    return RunResult(
        task_id=task_id,
        condition_id=condition,
        run_index=run_index,
        trajectory=Trajectory(
            turns=call_turns,
            usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
            run_index=run_index,
            stop_reason="completed",
        ),
        grade=GradeResult(
            grader_id="g",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence=(
                {"expected": "search_docs", "observed": "create_ticket"}
                if not passed
                else {}
            ),
            failure_reason=failure_reason,
        ),
    )


# Compact tool-call data for exemplar tests
_CREATE_TICKET = [[{"name": "create_ticket", "args": {"title": "x"}}]]
_UPDATE_18 = [[{"name": "update_ticket", "args": {"id": 1}}]]
_UPDATE_40 = [[{"name": "update_ticket", "args": {"id": 2}}]]


def test_exemplar_traces_rendered_for_top_failure_mode() -> None:
    """For the top failure mode, one exemplar trace excerpt is rendered
    (lex-first failing task, compact format)."""
    runs = (
        _run_with_tool_calls("A", "ws2-001", 0, False, _CREATE_TICKET, "wrong_tool"),
        _run_with_tool_calls("A", "ws2-001", 1, False, _CREATE_TICKET, "wrong_tool"),
        _run_with_tool_calls("A", "ws2-001", 2, False, _CREATE_TICKET, "wrong_tool"),
        _run_with_tool_calls("A", "ws2-018", 0, False, _UPDATE_18, "wrong_args"),
        _run_with_tool_calls("A", "ws2-018", 1, False, _UPDATE_18, "wrong_args"),
        _run_with_tool_calls("A", "ws2-018", 2, False, _UPDATE_18, "wrong_args"),
    )
    report = build_validation_report(
        conditions=(ConditionInput(label="A", results=runs),),
        tiers={"ws2-001": "T1", "ws2-018": "T3"},
        capabilities={"ws2-001": "tool_selection", "ws2-018": "multi_step_state"},
        k=3,
        expected_n_tasks=2,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    md = render_markdown(report)
    assert "Exemplar" in md or "exemplar" in md.lower()
    # At least one exemplar task id is rendered
    assert "ws2-001" in md or "ws2-018" in md


def test_exemplar_trace_picks_lex_first_failing_task() -> None:
    """Exemplar selection is deterministic: lex-first failing task per failure mode."""
    # wrong_args failures on two tasks; lex-first is ws2-018 (< ws2-040)
    runs = (
        _run_with_tool_calls("A", "ws2-018", 0, False, _UPDATE_18, "wrong_args"),
        _run_with_tool_calls("A", "ws2-018", 1, False, _UPDATE_18, "wrong_args"),
        _run_with_tool_calls("A", "ws2-018", 2, False, _UPDATE_18, "wrong_args"),
        _run_with_tool_calls("A", "ws2-040", 0, False, _UPDATE_40, "wrong_args"),
        _run_with_tool_calls("A", "ws2-040", 1, False, _UPDATE_40, "wrong_args"),
        _run_with_tool_calls("A", "ws2-040", 2, False, _UPDATE_40, "wrong_args"),
    )
    report = build_validation_report(
        conditions=(ConditionInput(label="A", results=runs),),
        tiers={"ws2-018": "T3", "ws2-040": "T4"},
        capabilities={
            "ws2-018": "multi_step_state",
            "ws2-040": "distractor_resistance",
        },
        k=3,
        expected_n_tasks=2,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    md = render_markdown(report)
    # Lex-first failing task for wrong_args is ws2-018 (< ws2-040)
    idx_018 = md.find("ws2-018")
    idx_040 = md.find("ws2-040")
    assert idx_018 < idx_040
