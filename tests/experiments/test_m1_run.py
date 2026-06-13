import httpx

from agent_eval_lab.experiments.m1_run import run_m1
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
from agent_eval_lab.tasks.schema import FactKeySpec, Task, TaskInput, TaskMetadata


def _task(tid):
    return Task(
        id=tid, capability="docs_qa",
        input=TaskInput(messages=(MessageTurn(role="user", content="q"),),
                        available_tools=("bash",)),
        verification=FactKeySpec(required=("x",), forbidden=(), page_snapshot="x",
                                 page_snapshot_sha256="s", level=1),
        metadata=TaskMetadata(split="held_out", version="v", provenance="t"),
    )


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


def test_run_m1_threads_dset_per_condition(monkeypatch):
    from agent_eval_lab.experiments import m1_run

    calls = []

    def fake_run_dset(*, config, tasks, k_valid, **kw):
        calls.append((config.model_id, tuple(t.id for t in tasks), k_valid))
        cond = f"{config.id}:{config.model_id}"
        return tuple(_outcome(t.id, cond) for t in tasks)

    monkeypatch.setattr(m1_run, "run_dset", fake_run_dset)

    configs = (
        ProviderConfig(
            id="deepseek", base_url="u", api_key_env="K", model_id="deepseek-v4-pro"
        ),
        ProviderConfig(
            id="minimax", base_url="u", api_key_env="K", model_id="MiniMax-M3"
        ),
    )
    out = run_m1(
        configs=configs,
        domain_tasks={"D": (_task("t0"), _task("t1"))},  # F/B absent -> skipped
        http_client=httpx.Client(), k_valid=5, max_invalid_rate=0.40,
        temperature=0.0, max_tokens=4096, health_probe_fn=None, reference_sha256=None,
        evaluator_store=None,
    )
    assert len(calls) == 2  # one per condition
    assert set(out) == {"deepseek:deepseek-v4-pro", "minimax:MiniMax-M3"}
    assert set(out["deepseek:deepseek-v4-pro"]) == {"D"}  # only D ran
    assert len(out["deepseek:deepseek-v4-pro"]["D"]) == 2  # two tasks


def test_run_m1_skips_absent_domains_without_crashing(monkeypatch):
    from agent_eval_lab.experiments import m1_run

    monkeypatch.setattr(m1_run, "run_dset", lambda **kw: ())
    out = run_m1(
        configs=(ProviderConfig(
            id="local", base_url="u", api_key_env="", model_id="qwen3-8b"
        ),),
        domain_tasks={},  # no domains at all
        http_client=httpx.Client(), k_valid=5, max_invalid_rate=0.40,
        temperature=0.0, max_tokens=4096, health_probe_fn=None, reference_sha256=None,
        evaluator_store=None,
    )
    assert out == {"local:qwen3-8b": {}}  # present condition, no domains, no crash
