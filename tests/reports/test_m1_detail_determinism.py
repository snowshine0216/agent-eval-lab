from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.reports.m1_detail import build_m1_detail, render_detail
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

_A, _B = "a:m1", "b:m2"
_PRICING = PricingSnapshot(
    snapshot_date="2026-06-13",
    prices={
        _A: PricePoint(input_per_mtok=1.0, output_per_mtok=2.0),
        _B: PricePoint(input_per_mtok=0.5, output_per_mtok=1.0),
    },
)


def _run(task_id, cond, idx, passed, tests):
    return RunResult(
        task_id=task_id, condition_id=cond, run_index=idx,
        trajectory=Trajectory(
            turns=(
                ToolCallTurn(tool_calls=(
                    ToolCall(call_id="c1", name="str_replace",
                             arguments={"path": "wdio.conf.ts"}),
                    ToolCall(call_id="c2", name="write_file",
                             arguments={"path": "extra.ts", "content": "x"}),
                )),
                MessageTurn(role="assistant", content="done"),
            ),
            usage=Usage(prompt_tokens=100 + idx, completion_tokens=50, latency_s=1.0),
            run_index=idx, stop_reason="completed_natural", rounds=4 + idx,
            tool_call_counts={"str_replace": 1, "write_file": 1, "read_file": 2},
            final_state={"files": {}, "target_paths": ["wdio.conf.ts"]},
        ),
        grade=GradeResult(
            grader_id="node_execution", passed=passed,
            score=1.0 if passed else 0.0,
            evidence={"execution": "run", "status": "passed" if passed else "failed",
                      "tests": tests, "displaced_paths": []},
        ),
    )


def _outcome(runs):
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=tuple(runs), attempts=attempts, void=False)


def test_build_render_byte_identical():
    spec = freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )
    outcomes = {
        _A: (
            _outcome([_run("f1", _A, i, i == 0,
                           [["a", "passed" if i == 0 else "failed"]]) for i in range(3)]),
            _outcome([_run("f2", _A, i, False, [["b", "failed"]]) for i in range(3)]),
        ),
        _B: (
            _outcome([_run("f1", _B, i, False, [["a", "failed"]]) for i in range(3)]),
            _outcome([_run("f2", _B, i, False, [["b", "failed"]]) for i in range(3)]),
        ),
    }
    kw = dict(domain="F", outcomes_by_condition=outcomes, pricing=_PRICING, spec=spec)
    md1 = render_detail(build_m1_detail(**kw))
    md2 = render_detail(build_m1_detail(**kw))
    assert md1 == md2
