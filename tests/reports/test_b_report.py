from agent_eval_lab.metrics.cost import TokenPrice
from agent_eval_lab.records.b_trial import BTrial
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.reports.b_report import report_b


def _trial(*, condition_id, task_id, run_index, rounds, pt=100, ct=50, cost=None):
    return BTrial(
        run_uid=f"{condition_id}__{task_id}__{run_index:04d}",
        condition_id=condition_id,
        task_id=task_id,
        save_name=f"{condition_id}-{task_id}-{run_index}",
        folder="/f",
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=pt, completion_tokens=ct, latency_s=1.0),
            run_index=run_index,
            stop_reason="completed_natural",
            rounds=rounds,
            wall_time_s=10.0,
            total_cost_usd=cost,
        ),
        invalid=False,
        invalid_reason=None,
    )


def test_report_b_builds_pass_at_1_and_skill_delta() -> None:
    cond = "dashscope:qwen3.7-max"
    trials = [
        _trial(condition_id=cond, task_id="b-b1-noskill", run_index=i, rounds=5)
        for i in range(3)
    ] + [
        _trial(condition_id=cond, task_id="b-b1-skill", run_index=i, rounds=4)
        for i in range(3)
    ]
    verdicts = {
        # noskill: 2/3 pass; skill: 3/3 pass -> skill delta = +1/3.
        f"{cond}__b-b1-noskill__0000": "PASS",
        f"{cond}__b-b1-noskill__0001": "PASS",
        f"{cond}__b-b1-noskill__0002": "FAIL",
        f"{cond}__b-b1-skill__0000": "PASS",
        f"{cond}__b-b1-skill__0001": "PASS",
        f"{cond}__b-b1-skill__0002": "PASS",
    }
    report = report_b(
        trials,
        verdicts,
        pricing={cond: TokenPrice(input_per_mtok=1.0, output_per_mtok=2.0)},
    )
    rows = {(r.condition_id, r.arm): r for r in report.rows}
    assert rows[(cond, "b-b1-noskill")].pass_at_1 == 2 / 3
    assert rows[(cond, "b-b1-skill")].pass_at_1 == 1.0
    assert rows[(cond, "b-b1-noskill")].pass_pow_3 is False  # not all 3 passed
    assert rows[(cond, "b-b1-skill")].pass_pow_3 is True
    # Skill delta on pass_at_1 (skill - noskill), per model.
    assert report.skill_delta[cond] == 1.0 - (2 / 3)
    # Chat cost is tokens x pricing (3 noskill trials: 3*(100*1 + 50*2)/1e6).
    assert rows[(cond, "b-b1-noskill")].cost_usd > 0


def test_report_b_invalid_verdict_excluded_from_pass_at_1() -> None:
    cond = "deepseek:deepseek-v4-pro"
    trials = [
        _trial(condition_id=cond, task_id="b-b1-noskill", run_index=i, rounds=5)
        for i in range(3)
    ]
    verdicts = {
        f"{cond}__b-b1-noskill__0000": "PASS",
        f"{cond}__b-b1-noskill__0001": "INVALID",  # owner overrode to INVALID
        f"{cond}__b-b1-noskill__0002": "FAIL",
    }
    report = report_b(trials, verdicts, pricing={})
    row = next(r for r in report.rows if r.arm == "b-b1-noskill")
    # INVALID is masked: pass_at_1 over the 2 VALID verdicts = 1/2.
    assert row.valid == 2
    assert row.invalid == 1
    assert row.pass_at_1 == 0.5


def test_report_b_claude_efficiency_on_its_own_axis() -> None:
    cond = "claude-cli:claude-sonnet-4-6"
    trials = [
        _trial(
            condition_id=cond, task_id="b-b1-noskill", run_index=i, rounds=6, cost=0.03
        )
        for i in range(3)
    ]
    verdicts = {f"{cond}__b-b1-noskill__{i:04d}": "PASS" for i in range(3)}
    report = report_b(trials, verdicts, pricing={})
    row = next(r for r in report.rows if r.arm == "b-b1-noskill")
    # claude rows are flagged so the renderer never pools turns/USD with chat rounds.
    assert row.is_subprocess_driver is True
    # cost comes from total_cost_usd (3 * 0.03), not tokens x pricing.
    assert abs(row.cost_usd - 0.09) < 1e-9
