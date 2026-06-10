import pytest

from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.reports.comparison import build_comparison_report, render_markdown


def _run(task_id, run_index, passed, failure_reason=None, ptoks=10, ctoks=5):
    return RunResult(
        task_id=task_id,
        condition_id="deepseek:deepseek-v4-pro",
        run_index=run_index,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=ptoks, completion_tokens=ctoks, latency_s=0.1),
            run_index=run_index,
            stop_reason="completed",
        ),
        grade=GradeResult(
            grader_id="g",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=None if passed else failure_reason,
        ),
    )


def _all(task_id, k, passed, failure_reason=None):
    return [_run(task_id, i, passed, failure_reason) for i in range(k)]


TIERS = {"ws2-001": "T1", "ws2-018": "T3", "ws2-040": "T4"}
PROMPT_TEXT = "PLAN FIRST: identify before you act.\n"


def test_primary_t3t4_delta_and_hash_pin() -> None:
    # T1 (ws2-001) unchanged near-ceiling; on BOTH hard tasks A fails every run
    # and B passes every run. With the hard universe {ws2-018, ws2-040} all-fail
    # in A and all-pass in B, every cluster resample yields Δ = +1.0, so the CI
    # is [1.0, 1.0] — strictly above 0 (verified offline, seed 20260610).
    a = (*_all("ws2-001", 3, True), *_all("ws2-018", 3, False, "wrong_args"),
         *_all("ws2-040", 3, False, "forbidden_action"))
    b = (*_all("ws2-001", 3, True), *_all("ws2-018", 3, True),
         *_all("ws2-040", 3, True))
    report = build_comparison_report(
        results_a=a,
        results_b=b,
        tiers=TIERS,
        planning_prompt_text=PROMPT_TEXT,
        config_a_path="reports/runs-deepseek-deepseek-v4-pro__default.jsonl",
        config_b_path="reports/runs-deepseek-deepseek-v4-pro__planning-v1.jsonl",
        k=3,
        seed=20260610,
        n_resamples=500,
        alpha=0.05,
    )
    import hashlib
    expected = hashlib.sha256(PROMPT_TEXT.encode("utf-8")).hexdigest()
    assert report.planning_prompt_hash == expected
    assert report.config_a_label == "default (per-task author prompt, no override)"
    # Hard universe {ws2-018, ws2-040}: pass^3(A)=0.0, pass^3(B)=1.0 -> point Δ=+1.0.
    assert report.delta_hard.point == pytest.approx(1.0)
    assert report.delta_hard.lo == pytest.approx(1.0)  # CI strictly above 0
    # CI excludes 0 and lies above -> "planning helps on hard tiers".
    assert report.verdict.startswith("planning helps on hard tiers")


def test_verdict_no_effect_when_ci_includes_zero() -> None:
    # Identical outcomes -> Δ = 0, CI includes 0.
    a = (*_all("ws2-018", 3, True), *_all("ws2-040", 3, False, "forbidden_action"))
    b = (*_all("ws2-018", 3, True), *_all("ws2-040", 3, False, "forbidden_action"))
    report = build_comparison_report(
        results_a=a,
        results_b=b,
        tiers={"ws2-018": "T3", "ws2-040": "T4"},
        planning_prompt_text=PROMPT_TEXT,
        config_a_path="a.jsonl",
        config_b_path="b.jsonl",
        k=3,
        seed=20260610,
        n_resamples=200,
        alpha=0.05,
    )
    assert report.delta_hard.point == pytest.approx(0.0)
    assert report.verdict.startswith("no detectable effect at n=50")


def test_secondary_extra_call_and_wrong_args_rates() -> None:
    a = (*_all("ws2-018", 3, False, "extra_call"),)
    b = (*_all("ws2-018", 3, False, "wrong_args"),)
    report = build_comparison_report(
        results_a=a,
        results_b=b,
        tiers={"ws2-018": "T3"},
        planning_prompt_text=PROMPT_TEXT,
        config_a_path="a.jsonl",
        config_b_path="b.jsonl",
        k=3,
        seed=20260610,
        n_resamples=100,
        alpha=0.05,
    )
    assert report.extra_call_rate_a == pytest.approx(1.0)  # 3/3 trials
    assert report.extra_call_rate_b == pytest.approx(0.0)
    assert report.wrong_args_rate_b == pytest.approx(1.0)


def test_render_contains_hypothesis_hash_and_decision_rule() -> None:
    a = (*_all("ws2-018", 3, False, "wrong_args"), *_all("ws2-040", 3, True))
    b = (*_all("ws2-018", 3, True), *_all("ws2-040", 3, True))
    md = render_markdown(
        build_comparison_report(
            results_a=a,
            results_b=b,
            tiers={"ws2-018": "T3", "ws2-040": "T4"},
            planning_prompt_text=PROMPT_TEXT,
            config_a_path="a.jsonl",
            config_b_path="b.jsonl",
            k=3,
            seed=20260610,
            n_resamples=200,
            alpha=0.05,
        )
    )
    assert "# Configuration comparison" in md
    assert "Hypothesis (pre-declared" in md
    assert "sha256" in md.lower()
    assert "Decision rule" in md
    assert "T3+T4" in md
    assert "n=50" in md
