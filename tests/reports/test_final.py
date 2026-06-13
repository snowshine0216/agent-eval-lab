"""Pure final-report builder + renderer (item 004 criteria 9, 14, 16, 19, 20)."""

from agent_eval_lab.metrics.cost import TokenPrice
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.reports.final import (
    FinalConditionInput,
    build_final_report,
    render_markdown,
)

TIERS = {"cr-001": "T1", "cr-002": "T3"}
CAPS = {"cr-001": "visible_test_localization", "cr-002": "overfit_resistance"}


def _run(condition, task_id, run_index, passed, *, status="failed", latency=0.5):
    evidence = {
        "execution": "run",
        "status": "passed" if passed else status,
        "exit_code": 0 if passed else 1,
        "counts": {"passed": 2, "failed": 0 if passed else 1, "errors": 0},
        "execution_hash": "h",
        "displaced_paths": [],
    }
    return RunResult(
        task_id=task_id,
        condition_id=condition,
        run_index=run_index,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=100, completion_tokens=20, latency_s=latency),
            run_index=run_index,
            stop_reason="completed",
            final_state={"files": {}},
        ),
        grade=GradeResult(
            grader_id="execution",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence=evidence,
            failure_reason=None,
        ),
    )


def _k3(condition, task_id, passed) -> list:
    return [_run(condition, task_id, i, passed) for i in range(3)]


C1 = "deepseek:deepseek-v4-pro"
C4 = "local:Qwen/Qwen3-8B"


def _conditions():
    return (
        FinalConditionInput(
            label="C1",
            condition_id=C1,
            results=tuple(_k3(C1, "cr-001", True) + _k3(C1, "cr-002", False)),
            hosted=True,
        ),
        FinalConditionInput(
            label="C4",
            condition_id=C4,
            results=tuple(_k3(C4, "cr-001", True) + _k3(C4, "cr-002", True)),
            hosted=False,
        ),
    )


def _build(conditions=None, prices=None):
    return build_final_report(
        conditions=conditions if conditions is not None else _conditions(),
        dataset_id="code_repair_v1",
        tiers=TIERS,
        capabilities=CAPS,
        k=3,
        expected_n_tasks=2,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
        prices=prices
        if prices is not None
        else {C1: TokenPrice(input_per_mtok=0.27, output_per_mtok=1.10)},
        prices_snapshot_date="2026-06-11",
        context_text="v1/v2 context body.\n",
    )


def test_build_and_render_are_byte_deterministic() -> None:
    assert render_markdown(_build()) == render_markdown(_build())


def test_header_names_dataset_k_seed_and_classifier_version() -> None:
    md = render_markdown(_build())
    assert "`code_repair_v1`" in md
    assert "k=3" in md
    assert "seed=20260610" in md
    assert "fc-v2" in md
    assert "not greedy-deterministic" in md  # temperature-honesty note


def test_no_generation_timestamp_anywhere() -> None:
    md = render_markdown(_build())
    assert "generated at" not in md.lower()
    assert "timestamp" not in md.lower()
    # The only date is the recorded prices snapshot (grill Q5).
    assert md.count("2026-") == md.count("2026-06-11")


def test_blocked_condition_renders_blocked_without_fabricated_numbers() -> None:
    blocked = FinalConditionInput(
        label="C3",
        condition_id=None,
        results=(),
        hosted=True,
        blocked_reason="no reachable records",
    )
    report = _build(conditions=(*_conditions(), blocked))
    md = render_markdown(report)
    c3 = next(c for c in report.conditions if c.label == "C3")
    assert c3.status == "blocked"
    assert c3.pass_at_1 is None and c3.pass_pow_k is None
    assert "| C3 | blocked |" in md
    assert "no reachable records" in md


def test_incomplete_condition_lists_excluded_task_ids() -> None:
    partial = FinalConditionInput(
        label="C2",
        condition_id="glm:Pro/zai-org/GLM-5.1",
        results=tuple(_k3("glm:Pro/zai-org/GLM-5.1", "cr-001", True))
        + (_run("glm:Pro/zai-org/GLM-5.1", "cr-002", 0, False),),
        hosted=True,
    )
    report = _build(conditions=(*_conditions(), partial))
    c2 = next(c for c in report.conditions if c.label == "C2")
    assert c2.status == "incomplete"
    assert c2.incomplete_task_ids == ("cr-002",)
    assert "cr-002" in render_markdown(report)


def test_classification_counts_and_deterministic_exemplar() -> None:
    report = _build()
    c1 = next(c for c in report.conditions if c.label == "C1")
    assert c1.classification_counts == {("agent_failure", "oracle_red"): 3}
    assert len(c1.exemplars) == 1
    exemplar = c1.exemplars[0]
    assert (exemplar.task_id, exemplar.run_index) == ("cr-002", 0)
    md = render_markdown(report)
    assert "| agent_failure | oracle_red | 3 |" in md
    assert "cr-002" in md


def test_judgment_footnotes_are_rendered() -> None:
    md = render_markdown(_build())
    assert "tree_collision" in md
    assert "ADR-0012" in md
    assert "foreign_verdict" in md


def test_task_defect_candidate_on_unanimous_failure() -> None:
    # cr-002 fails ALL recorded runs on EVERY condition with records for it.
    conds = (
        FinalConditionInput(
            label="C1",
            condition_id=C1,
            results=tuple(_k3(C1, "cr-001", True) + _k3(C1, "cr-002", False)),
            hosted=True,
        ),
        FinalConditionInput(
            label="C4",
            condition_id=C4,
            results=tuple(_k3(C4, "cr-001", True) + _k3(C4, "cr-002", False)),
            hosted=False,
        ),
    )
    report = _build(conditions=conds)
    [candidate] = report.task_defect_candidates
    assert candidate.task_id == "cr-002"
    assert candidate.n_conditions == 2
    assert candidate.n_runs == 6
    md = render_markdown(report)
    assert "cr-002" in md and "flagged for human review" in md


def test_no_candidate_when_one_condition_passes() -> None:
    report = _build()  # C4 passes cr-002
    assert report.task_defect_candidates == ()
    assert "none" in render_markdown(report)


def test_blocked_condition_excluded_from_unanimity() -> None:
    conds = (
        FinalConditionInput(
            label="C1",
            condition_id=C1,
            results=tuple(_k3(C1, "cr-002", False)),
            hosted=True,
        ),
        FinalConditionInput(
            label="C3",
            condition_id=None,
            results=(),
            hosted=True,
            blocked_reason="no reachable records",
        ),
    )
    report = _build(conditions=conds)
    [candidate] = report.task_defect_candidates
    assert (candidate.task_id, candidate.n_conditions) == ("cr-002", 1)


def test_condition_without_records_for_task_is_vacuous() -> None:
    # Grill Q10: C4 has records only for cr-001; its silence on cr-002
    # contributes nothing — cr-002 stays a candidate with n_conditions=1.
    conds = (
        FinalConditionInput(
            label="C1",
            condition_id=C1,
            results=tuple(_k3(C1, "cr-001", True) + _k3(C1, "cr-002", False)),
            hosted=True,
        ),
        FinalConditionInput(
            label="C4",
            condition_id=C4,
            results=tuple(_k3(C4, "cr-001", True)),
            hosted=False,
        ),
    )
    report = _build(conditions=conds)
    [candidate] = report.task_defect_candidates
    assert (candidate.task_id, candidate.n_conditions, candidate.n_runs) == (
        "cr-002",
        1,
        3,
    )


def test_cost_priced_condition_and_not_computed_local() -> None:
    report = _build()
    c1 = next(c for c in report.conditions if c.label == "C1")
    c4 = next(c for c in report.conditions if c.label == "C4")
    # 6 runs x (100 prompt x 0.27 + 20 completion x 1.10) per Mtok
    assert c1.cost_usd is not None and abs(c1.cost_usd - 294e-6) < 1e-9
    assert c4.cost_usd is None
    md = render_markdown(report)
    assert "not computed" in md
    assert "2026-06-11" in md  # snapshot date rendered as recorded data


def test_context_file_rendered_verbatim_under_heading() -> None:
    md = render_markdown(_build())
    assert "## Context: prior baselines (workspace_tool_use v1/v2)" in md
    assert "v1/v2 context body." in md


def test_excluded_conditions_and_limitations_sections() -> None:
    md = render_markdown(_build())
    assert "openrouter:openai/gpt-5.5" in md
    assert "dotted-path" in md  # criterion 10a residual
    assert "rmtree" in md  # criterion 10b residual
    assert "kernel-level" in md


def test_sections_render_in_spec_order() -> None:
    md = render_markdown(_build())
    headings = [
        "## Per-condition reliability",
        "## Per-tier pass^3",
        "## Per-capability pass^3",
        "## Failure classification (fc-v3)",
        "## Task-defect candidates",
        "## Cost and latency",
        "## Context: prior baselines (workspace_tool_use v1/v2)",
        "## Discriminativeness verdict",
        "## Known limitations",
        "## Roadmap takeaways",
        "## Excluded conditions",
    ]
    positions = [md.index(h) for h in headings]
    assert positions == sorted(positions)


def test_discriminativeness_renders_honesty_line() -> None:
    md = render_markdown(_build())
    assert "absence of" in md and "not evidence of no separation" in md


def test_harness_defect_narrative_leads_failure_classification() -> None:
    # Fix-round disclosure (item 004): the fc-v1 capture mis-attributed
    # budget-truncated runs to the agent; the narrative records it factually.
    md = render_markdown(_build())
    section = md.index("## Failure classification")
    narrative = md.index("### Harness defect found and fixed")
    first_condition = md.index("### C1 (")
    assert section < narrative < first_condition  # narrative leads the section
    assert "completion_tokens == 512" in md  # the diagnostic signature
    assert "token_budget_exhausted" in md
    assert "0.133" in md and "1.000" in md  # before/after pass@1, factual


def test_fc_design_note_names_cr007_vs_cr014_evidence_paths() -> None:
    md = render_markdown(_build())
    assert "cr-007" in md and "cr-014" in md
    assert "first execution leg" in md  # the all_of walk convention


def test_budget_asymmetry_limitation_is_rendered() -> None:
    # C1/C2 predate the explicit completion budget and were not rerun.
    md = render_markdown(_build())
    assert "predate the explicit completion budget" in md
    assert "max_tokens" in md
    assert "not binding" in md


def test_saturation_takeaway_names_hardness_levers() -> None:
    md = render_markdown(_build())
    assert "harder tiers" in md
    assert "deeper repair chains" in md
    assert "multi-file" in md
    assert "oblique specs" in md
