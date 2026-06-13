import json

from agent_eval_lab.cli import main


def test_run_m1_streams_runs_per_condition_domain(tmp_path, monkeypatch):
    # Stub run_m1 so no provider/network is touched.
    from agent_eval_lab import cli
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

    def _outcome(tid, cond):
        r = RunResult(
            task_id=tid, condition_id=cond, run_index=0,
            trajectory=Trajectory(
                turns=(MessageTurn(role="assistant", content="x"),),
                usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
                run_index=0, stop_reason="completed_natural",
            ),
            grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}),
        )
        return ReplacementOutcome(
            valid_runs=(r,)*5,
            attempts=(TrialAttempt(attempt_index=0, valid=True, run=r),),
            void=False,
        )

    def fake_run_m1(*, configs, **kw):
        return {
            f"{c.id}:{c.model_id}": {
                "D": (_outcome("cmc-q01", f"{c.id}:{c.model_id}"),)
            }
            for c in configs
        }

    monkeypatch.setattr(cli, "run_m1", fake_run_m1)
    # Stub task+config loading so the edge is exercised without an evaluator store.
    monkeypatch.setattr(cli, "_load_m1_domain_tasks", lambda args, cfg: {"D": ()})

    # Minimal frozen spec on disk.
    from agent_eval_lab.cli import _spec_to_dict
    from agent_eval_lab.experiments.m1_spec import build_m1_spec
    from agent_eval_lab.experiments.spec_hash import freeze_spec
    spec = freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec_to_dict(spec)))

    # Minimal evaluator.toml so load_evaluator_config succeeds.
    (tmp_path / "evaluator.toml").write_text(
        '[store]\npath = "/tmp/eval-store"\n'
        '[health_probe]\nurl = "http://localhost"\nusername = "u"\npassword = "p"\n'
        '[skill]\nstrategy_test_path = "/tmp/skill"\n'
        '[runner]\nsafety_cap = 200\nk_valid = 5\nmax_invalid_rate = 0.40\n'
        '[oracle]\n[oracle.b_set]\nreadback = "playwright-cli"\n'
    )

    out = tmp_path / "runs"
    rc = main([
        "run-m1", "--spec", str(spec_path), "--provider", "deepseek",
        "--evaluator-config", str(tmp_path / "evaluator.toml"),
        "--out", str(out),
    ])
    assert rc == 0
    written = list(out.glob("runs-m1-*-D.jsonl"))
    assert len(written) == 1
    assert written[0].read_text().strip()  # non-empty JSONL
