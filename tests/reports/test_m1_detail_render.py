import re

from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1_detail import build_m1_detail, render_detail
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

_COND = "deepseek:deepseek-v4-pro"
_PRICING = PricingSnapshot(
    snapshot_date="2026-06-13",
    prices={_COND: PricePoint(input_per_mtok=1.0, output_per_mtok=2.0)},
)


def _node_grade(passed, tests, **extra):
    ev = {
        "execution": "run",
        "status": "passed" if passed else "failed",
        "tests": tests,
        "displaced_paths": [],
    }
    ev.update(extra)
    return GradeResult(
        grader_id="node_execution",
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence=ev,
    )


def _f_run(
    idx,
    passed,
    tests,
    *,
    stop="completed_natural",
    safety_cap_bound=False,
    max_rounds_bound=False,
    max_rounds=None,
    rounds=4,
):
    return RunResult(
        task_id="f1",
        condition_id=_COND,
        run_index=idx,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
            run_index=idx,
            stop_reason=stop,
            rounds=rounds,
            safety_cap_bound=safety_cap_bound,
            max_rounds_bound=max_rounds_bound,
            max_rounds=max_rounds,
            final_state={"files": {}, "target_paths": ["wdio.conf.ts"]},
        ),
        grade=_node_grade(passed, tests),
    )


def _outcome(runs):
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=tuple(runs), attempts=attempts, void=False)


def _spec():
    return freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )


def _render(runs):
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={_COND: (_outcome(runs),)},
        pricing=_PRICING,
        spec=_spec(),
    )
    return render_detail(detail)


def test_render_has_all_sections():
    md = _render([_f_run(i, passed=False, tests=[["a", "failed"]]) for i in range(3)])
    assert "# M1 subreport — F" in md
    assert "## Task quick-reference" in md
    assert "## Cross-model summary" in md
    assert "## Per-task detail" in md
    assert "## Task-defect candidates" in md
    assert "## Per-condition efficiency" in md
    assert "## Failure classification (fc-v4) per task × condition" in md


def test_render_per_trial_string_and_gap():
    md = _render(
        [
            _f_run(0, passed=True, tests=[["a", "passed"], ["b", "passed"]]),
            _f_run(1, passed=False, tests=[["a", "passed"], ["b", "failed"]]),
        ]
    )
    assert "✅" in md and "❌" in md
    # grader-aware gap names the failing oracle test
    assert "b" in md


def test_render_censoring_annotation():
    md = _render(
        [
            _f_run(0, passed=False, tests=[["a", "failed"]]),
            _f_run(
                1,
                passed=False,
                tests=[["a", "failed"]],
                stop="max_rounds",
                max_rounds=40,
                max_rounds_bound=True,
                rounds=40,
            ),
        ]
    )
    # the censored run must annotate the rounds cell, never silently
    assert "right-censored" in md
    assert "cap 40" in md


def test_render_administrative_label():
    admin = RunResult(
        task_id="f1",
        condition_id=_COND,
        run_index=0,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=0,
            stop_reason="completed_natural",
            rounds=0,
            final_state={"files": {}, "target_paths": []},
        ),
        grade=GradeResult(
            grader_id="node_execution",
            passed=False,
            score=0.0,
            evidence={"marked_failed_not_executed": True},
        ),
    )
    md = _render([admin])
    assert "administrative" in md
    assert "not executed" in md


# ---------------------------------------------------------------------------
# Finding 1 — cross-model summary must NOT render 0/1 ❌ for admin cells
# ---------------------------------------------------------------------------


def _make_admin_run():
    return RunResult(
        task_id="f1",
        condition_id=_COND,
        run_index=0,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=0,
            stop_reason="completed_natural",
            rounds=0,
            final_state={"files": {}, "target_paths": []},
        ),
        grade=GradeResult(
            grader_id="node_execution",
            passed=False,
            score=0.0,
            evidence={"marked_failed_not_executed": True},
        ),
    )


def test_summary_admin_cell_does_not_render_zero_slash_failure():
    """Cross-model summary for an admin cell must NOT show a real-failure tally."""
    md = _render([_make_admin_run()])
    # They mustn't appear together in an admin context
    assert "0/1" not in md or "❌" not in md
    assert "admin" in md.lower()


def test_summary_admin_cell_contains_admin_marker():
    """Summary line for admin cell: admin marker present, ❌ absent."""
    md = _render([_make_admin_run()])
    # Find the summary section
    summary_section = md[
        md.find("## Cross-model summary") : md.find("## Per-task detail")
    ]
    # Admin marker must be present in the summary
    assert "admin" in summary_section.lower()
    # The real failure symbol ❌ must NOT appear in the summary for this admin cell
    assert "❌" not in summary_section


# ---------------------------------------------------------------------------
# Finding 1 round-2 — admin cell must NOT appear in fc-v4 classification table
# ---------------------------------------------------------------------------


def test_admin_cell_absent_from_classification_table():
    """An admin (marked_failed_not_executed) cell must NOT produce a fc-v4
    classification row — even though _cell computes non-empty classifications
    before setting administrative=True.  The skip guard in _classification_lines
    must honour cell.administrative.
    """
    md = _render([_make_admin_run()])
    # Extract only the fc-v4 section
    fc_start = md.find("## Failure classification (fc-v4)")
    assert fc_start != -1, "fc-v4 section must exist"
    fc_section = md[fc_start:]
    # There must be NO category row (lines with "| … | … |" inside a task block)
    # The only admissible content is the header + the "(no failures classified)" note.
    assert "### `f1`" not in fc_section, (
        "Administrative cell must NOT appear as a task block in the fc-v4 table"
    )
    assert "agent_failure" not in fc_section, (
        "Administrative cell classification category must not leak into fc-v4"
    )


# ---------------------------------------------------------------------------
# Minor: void domain renders explicit note
# ---------------------------------------------------------------------------


def test_render_void_domain_emits_note():
    """Void domain (zero tasks): render_detail emits an explicit note."""
    from agent_eval_lab.reports.m1_detail import M1Detail, render_detail

    detail = M1Detail(
        domain="F",
        conditions_present=(_COND,),
        k=3,
        spec_hash="abc",
        task_quick_refs=(),
        tasks=(),
        defect_candidates=(),
        efficiency=(),
        efficiency_condition_ids=(),
    )
    md = render_detail(detail)
    # Must include an explicit note about no executed tasks
    assert "no executed tasks" in md.lower() or "all runs voided" in md.lower()


# ---------------------------------------------------------------------------
# Finding 4 — dominant stop tie-break consistency
# ---------------------------------------------------------------------------


def _make_run_with_stop(stop, idx, rounds=4):
    return RunResult(
        task_id="f1",
        condition_id=_COND,
        run_index=idx,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=1.0),
            run_index=idx,
            stop_reason=stop,
            rounds=rounds,
            final_state={"files": {}, "target_paths": ["wdio.conf.ts"]},
        ),
        grade=GradeResult(
            grader_id="node_execution",
            passed=False,
            score=0.0,
            evidence={
                "execution": "run",
                "status": "failed",
                "tests": [["a", "failed"]],
                "displaced_paths": [],
            },
        ),
    )


def test_dominant_stop_tie_break_consistent_in_summary_and_efficiency():
    """For a tie input (1 'completed_natural', 1 'max_rounds'),
    both the per-cell summary and efficiency table agree on the dominant stop."""
    run_a = _make_run_with_stop("completed_natural", 0)
    run_b = _make_run_with_stop("max_rounds", 1, rounds=40)
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={_COND: (_outcome([run_a, run_b]),)},
        pricing=_PRICING,
        spec=_spec(),
    )
    md = render_detail(detail)
    # Extract the dominant stop from per-task detail section
    task_section = md[md.find("## Per-task detail") : md.find("## Task-defect")]
    eff_section = md[
        md.find("## Per-condition efficiency") : md.find("## Failure classification")
    ]
    # Both must agree - find the stop reason shown in task detail
    # The per-task detail has "- dominant stop: <value>"
    task_dom = re.search(r"- dominant stop: (\S+)", task_section)
    # The efficiency table has the stop in the last column
    eff_dom = re.search(r"\|\s*(\w+)\s*\|$", eff_section, re.MULTILINE)
    assert task_dom is not None
    assert eff_dom is not None
    assert task_dom.group(1) == eff_dom.group(1)
