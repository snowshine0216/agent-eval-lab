import argparse
import json

from agent_eval_lab.records.b_trial import BTrial, b_trial_to_dict
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _trial(cond, arm, i):
    return BTrial(
        run_uid=f"{cond}__{arm}__{i:04d}",
        condition_id=cond,
        task_id=arm,
        save_name=f"{cond}-{arm}-{i}",
        folder="/f",
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
            run_index=i,
            stop_reason="completed_natural",
            rounds=5,
            wall_time_s=9.0,
        ),
        invalid=False,
        invalid_reason=None,
    )


def test_report_b_cli_joins_trials_and_verdicts(tmp_path) -> None:
    from agent_eval_lab import cli

    cond = "dashscope:qwen3.7-max"
    trials_path = tmp_path / "trials-b-x-b-b1-noskill.jsonl"
    trials_path.write_text(
        "".join(
            json.dumps(b_trial_to_dict(_trial(cond, "b-b1-noskill", i))) + "\n"
            for i in range(3)
        ),
        encoding="utf-8",
    )
    verdicts = tmp_path / "verdicts.json"
    verdicts.write_text(
        json.dumps(
            {
                f"{cond}__b-b1-noskill__0000": "PASS",
                f"{cond}__b-b1-noskill__0001": "PASS",
                f"{cond}__b-b1-noskill__0002": "FAIL",
            }
        ),
        encoding="utf-8",
    )
    prices = tmp_path / "pricing.json"
    prices.write_text(
        json.dumps(
            {
                "snapshot_date": "2026-06-17",
                "prices": {cond: {"input_per_mtok": 1.0, "output_per_mtok": 2.0}},
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "B1-report.md"
    args = argparse.Namespace(
        trials=[trials_path], verdicts=verdicts, prices=prices, out=out
    )
    rc = cli._run_report_b(args)
    assert rc == 0
    text = out.read_text()
    assert "pass_at_1" in text or "pass@1" in text.lower()
    assert "0.667" in text or "2/3" in text  # noskill pass_at_1


def test_report_b_dedupes_overlapping_run_uids(tmp_path) -> None:
    """P1-4: when two trial files share a run_uid, the report must count that trial
    ONCE (keeping the last occurrence), not twice. Metric counts must reflect the
    deduplicated set."""
    from agent_eval_lab import cli

    cond = "dashscope:qwen3.7-max"
    arm = "b-b1-noskill"

    # First file: run_uid 0000, 0001, 0002
    trials_a = tmp_path / "trials-b-x-a.jsonl"
    trials_a.write_text(
        "".join(
            json.dumps(b_trial_to_dict(_trial(cond, arm, i))) + "\n" for i in range(3)
        ),
        encoding="utf-8",
    )
    # Second file: run_uid 0002 AGAIN (overlap) + 0003
    trials_b = tmp_path / "trials-b-x-b.jsonl"
    trials_b.write_text(
        "".join(
            json.dumps(b_trial_to_dict(_trial(cond, arm, i))) + "\n" for i in [2, 3]
        ),
        encoding="utf-8",
    )

    verdicts = tmp_path / "verdicts.json"
    verdicts.write_text(
        json.dumps(
            {
                f"{cond}__{arm}__0000": "PASS",
                f"{cond}__{arm}__0001": "PASS",
                f"{cond}__{arm}__0002": "FAIL",
                f"{cond}__{arm}__0003": "PASS",
            }
        ),
        encoding="utf-8",
    )
    prices = tmp_path / "pricing.json"
    prices.write_text(
        json.dumps(
            {
                "snapshot_date": "2026-06-17",
                "prices": {cond: {"input_per_mtok": 1.0, "output_per_mtok": 2.0}},
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "B1-report.md"
    args = argparse.Namespace(
        trials=[trials_a, trials_b], verdicts=verdicts, prices=prices, out=out
    )
    rc = cli._run_report_b(args)
    assert rc == 0
    text = out.read_text()
    # 4 unique trials (0000, 0001, 0002, 0003), NOT 5 (0002 counted once).
    # pass_at_1 = 3/4 = 0.75 (PASSes: 0000, 0001, 0003).
    assert "0.75" in text or "3/4" in text or "3 / 4" in text
