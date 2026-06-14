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
        id=tid,
        capability="docs_qa",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="q"),), available_tools=("bash",)
        ),
        verification=FactKeySpec(
            required=("x",),
            forbidden=(),
            page_snapshot="x",
            page_snapshot_sha256="s",
            level=1,
        ),
        metadata=TaskMetadata(split="held_out", version="v", provenance="t"),
    )


def _outcome(tid, cond):
    r = RunResult(
        task_id=tid,
        condition_id=cond,
        run_index=0,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
            run_index=0,
            stop_reason="completed_natural",
        ),
        grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}),
    )
    return ReplacementOutcome(
        valid_runs=(r,) * 5,
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
        http_client=httpx.Client(),
        k_valid=5,
        max_invalid_rate=0.40,
        temperature=0.0,
        max_tokens=4096,
        health_probe_fn=None,
        reference_sha256=None,
        evaluator_store=None,
    )
    assert len(calls) == 2  # one per condition
    assert set(out) == {"deepseek:deepseek-v4-pro", "minimax:MiniMax-M3"}
    assert set(out["deepseek:deepseek-v4-pro"]) == {"D"}  # only D ran
    assert len(out["deepseek:deepseek-v4-pro"]["D"]) == 2  # two tasks


def test_run_m1_f_branch_yields_outcomes(monkeypatch) -> None:
    from agent_eval_lab.experiments import m1_run
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.config import ProviderConfig
    from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
    from agent_eval_lab.tasks.schema import (
        NodeExecutionSpec,
        Task,
        TaskInput,
        TaskMetadata,
    )

    def _outcome(task):
        traj = Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=0,
            stop_reason="completed",
            final_state={"files": {}},
        )
        run = RunResult(
            task_id=task.id,
            condition_id="c",
            run_index=0,
            trajectory=traj,
            grade=GradeResult(
                grader_id="node_execution",
                passed=True,
                score=1.0,
                evidence={},
                failure_reason=None,
            ),
        )
        return ReplacementOutcome(
            valid_runs=(run,),
            attempts=(TrialAttempt(attempt_index=0, valid=True, run=run),),
            void=False,
        )

    # stub run_f so no node/subprocess is needed in this unit test
    monkeypatch.setattr(
        m1_run,
        "run_f",
        lambda *, tasks, build_tree_fn, k: iter(_outcome(t) for t in tasks),
    )

    f_task = Task(
        id="f-f1",
        capability="repo_fix",
        input=TaskInput(messages=(), available_tools=("bash",)),
        verification=NodeExecutionSpec(held_out_files={}, test_paths=()),
        metadata=TaskMetadata(split="held_out", version="f-domain-v1", provenance="x"),
        initial_state={
            "candidate_base_sha": "5b0c13a6",
            "target_paths": (),
            "repo": "web-dossier",
        },
    )
    cfg = ProviderConfig(
        id="local",
        base_url="http://x",
        api_key_env="",
        model_id="m",
    )
    out = m1_run.run_m1(
        configs=(cfg,),
        domain_tasks={"F": (f_task,)},
        http_client=None,
        k_valid=2,
        max_invalid_rate=0.5,
        temperature=0.0,
        max_tokens=64,
        health_probe_fn=None,
        reference_sha256=None,
        evaluator_store=None,
        f_repo=__import__("pathlib").Path("/fake/repo"),
    )
    [(cond, by_domain)] = out.items()
    assert "F" in by_domain
    assert by_domain["F"][0].valid_runs[0].grade.passed is True


def test_run_m1_skips_absent_domains_without_crashing(monkeypatch):
    from agent_eval_lab.experiments import m1_run

    monkeypatch.setattr(m1_run, "run_dset", lambda **kw: ())
    out = run_m1(
        configs=(
            ProviderConfig(
                id="local", base_url="u", api_key_env="", model_id="qwen3-8b"
            ),
        ),
        domain_tasks={},  # no domains at all
        http_client=httpx.Client(),
        k_valid=5,
        max_invalid_rate=0.40,
        temperature=0.0,
        max_tokens=4096,
        health_probe_fn=None,
        reference_sha256=None,
        evaluator_store=None,
    )
    assert out == {"local:qwen3-8b": {}}  # present condition, no domains, no crash


def test_run_m1_b_branch_yields_outcomes(monkeypatch) -> None:
    from agent_eval_lab.experiments import m1_run
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.config import ProviderConfig
    from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
    from agent_eval_lab.tasks.schema import (
        ReadbackSpec,
        Task,
        TaskInput,
        TaskMetadata,
    )

    def _outcome(task):
        traj = Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=0,
            stop_reason="completed",
        )
        run = RunResult(
            task_id=task.id,
            condition_id="c",
            run_index=0,
            trajectory=traj,
            grade=GradeResult(
                grader_id="b1_readback", passed=True, score=1.0, evidence={}
            ),
        )
        return ReplacementOutcome(
            valid_runs=(run,),
            attempts=(TrialAttempt(attempt_index=0, valid=True, run=run),),
            void=False,
        )

    # stub run_b so no MSTR client is needed in this unit test
    monkeypatch.setattr(
        m1_run,
        "run_b",
        lambda *, tasks, client, project_id, folder, condition_id, k: iter(
            _outcome(t) for t in tasks
        ),
    )

    b_task = Task(
        id="b-b1-skill",
        capability="browser_mstr",
        input=TaskInput(messages=(), available_tools=("bash",)),
        verification=ReadbackSpec(
            expected_cube="C",
            required_rows=(),
            required_columns=(),
            expected_prompt="South",
            golden_grid=(),
        ),
        metadata=TaskMetadata(split="held_out", version="b-domain-v1", provenance="x"),
        initial_state={"task_key": "B-1"},
    )
    cfg = ProviderConfig(id="local", base_url="http://x", api_key_env="", model_id="m")

    class _FakeClient:
        def name_exists(self, target):
            return False

        def created_object_id(self, target):
            return "obj-1"

        def readback(self, *, project_id, object_id, prompt):
            raise AssertionError("run_b is stubbed; client must not be called")

        def delete_object(self, *, project_id, object_id):
            return None

    out = m1_run.run_m1(
        configs=(cfg,),
        domain_tasks={"B": (b_task,)},
        http_client=None,
        k_valid=2,
        max_invalid_rate=0.5,
        temperature=0.0,
        max_tokens=64,
        health_probe_fn=None,
        reference_sha256=None,
        evaluator_store=None,
        b_client=_FakeClient(),
        b_project_id="FAKE_PROJECT",
        b_folder="/runs",
    )
    [(cond, by_domain)] = out.items()
    assert "B" in by_domain
    assert by_domain["B"][0].valid_runs[0].grade.passed is True
