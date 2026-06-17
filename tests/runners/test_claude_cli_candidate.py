# tests/runners/test_claude_cli_candidate.py
import json
import os
import subprocess as _sp
from dataclasses import dataclass as _dc
from pathlib import Path

import pytest

from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import PROVIDER_ERROR, Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.claude_cli_candidate import (
    _CONTAMINATING_ENV_KEYS,
    SURFACES,
    BaselineRow,
    ClaudeResultParseError,
    ClaudeRunMeta,
    _sanitized_env,
    build_claude_argv,
    claude_system_prompt,
    make_claude_run_fn,
    materialize_tree,
    parse_claude_result,
    read_back_tree,
    summarize_baseline,
)
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
from agent_eval_lab.tasks.schema import AllOf, Task, TaskInput, TaskMetadata

# ---- helpers ------------------------------------------------------------------


def _result_json(**over):
    base = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 7,
        "total_cost_usd": 0.0123,
        "usage": {"input_tokens": 1500, "output_tokens": 320},
        "result": "done",
    }
    base.update(over)
    return json.dumps(base)


@_dc
class _FakeCompleted:
    stdout: str
    returncode: int = 0
    stderr: str = ""


def _edit_task(files):
    # NOTE deviation: Task requires capability + metadata (no defaults).
    # AllOf(specs=()) is a no-op verification; the runner only reads
    # initial_state["files"] and the first user message.
    return Task(
        id="f-f1",
        capability="repo_fix",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="Fix the bug in a.js"),),
            available_tools=("read_file",),
        ),
        verification=AllOf(specs=()),
        metadata=TaskMetadata(
            split="held_out", version="f-test-v1", provenance="unit test"
        ),
        initial_state={"files": dict(files)},
    )


def _rr(passed: bool) -> RunResult:
    return RunResult(
        task_id="f-f1",
        condition_id="cond",
        run_index=0,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
            run_index=0,
            stop_reason="completed_natural",
        ),
        grade=GradeResult(
            grader_id="node",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=None,
        ),
    )


# ---- Task 1: parse_claude_result ----------------------------------------------


def test_parse_happy_path_maps_usage_and_turns():
    meta = parse_claude_result(_result_json())
    assert meta == ClaudeRunMeta(
        prompt_tokens=1500,
        completion_tokens=320,
        num_turns=7,
        total_cost_usd=0.0123,
        is_error=False,
    )


def test_parse_is_error_true_is_carried():
    meta = parse_claude_result(_result_json(is_error=True, subtype="error_max_turns"))
    assert meta.is_error is True


def test_parse_malformed_json_raises_typed_error():
    with pytest.raises(ClaudeResultParseError):
        parse_claude_result("not json {")


def test_parse_missing_usage_raises_typed_error():
    with pytest.raises(ClaudeResultParseError):
        parse_claude_result(json.dumps({"type": "result", "is_error": False}))


# ---- Task 2: SURFACES, claude_system_prompt, build_claude_argv ----------------


def test_surfaces_are_the_two_expected():
    assert SURFACES == ("edit-only", "natural")


def test_system_prompt_differs_only_by_run_tests_line():
    edit = claude_system_prompt("edit-only")
    nat = claude_system_prompt("natural")
    assert "Do not attempt to run tests" in edit
    assert "Do not attempt to run tests" not in nat
    # No Factor-P scaffolding leaks into either baseline.
    assert "gather context" not in edit.lower()
    assert "gather context" not in nat.lower()
    # Identical apart from that one sentence.
    assert edit.replace("\n\nDo not attempt to run tests.", "").strip() == nat.strip()


def test_argv_edit_only_denies_bash_and_disables_skills():
    argv = build_claude_argv(
        model="claude-sonnet-4-6",
        surface="edit-only",
        prompt="fix it",
        system_prompt="SYS",
        max_budget_usd=0.5,
    )
    assert argv[0] == "claude"
    assert "-p" in argv
    assert "--output-format" in argv and "json" in argv
    # Vanilla isolation: --safe-mode disables CLAUDE.md/skills/plugins/hooks/MCP
    # (auth still works); --disable-slash-commands is belt-and-suspenders.
    assert "--safe-mode" in argv
    assert "--disable-slash-commands" in argv
    assert "--model" in argv and "claude-sonnet-4-6" in argv
    # Bash denied on edit-only; Read/Edit/Write allowed.
    deny = argv[argv.index("--disallowedTools") + 1]
    assert "Bash" in deny
    allow = argv[argv.index("--allowedTools") + 1]
    assert "Read" in allow and "Edit" in allow and "Write" in allow
    assert "Bash" not in allow
    # Prompt is the trailing positional.
    assert argv[-1] == "fix it"


def test_argv_natural_allows_bash():
    argv = build_claude_argv(
        model="claude-sonnet-4-6",
        surface="natural",
        prompt="fix it",
        system_prompt="SYS",
        max_budget_usd=0.5,
    )
    allow = argv[argv.index("--allowedTools") + 1]
    assert "Bash" in allow
    deny = argv[argv.index("--disallowedTools") + 1]
    assert "Bash" not in deny


def test_argv_rejects_unknown_surface():
    with pytest.raises(ValueError):
        build_claude_argv(
            model="m",
            surface="bogus",
            prompt="p",
            system_prompt="s",
            max_budget_usd=0.5,
        )


# ---- Task 3: materialize_tree + read_back_tree --------------------------------


def test_materialize_then_read_back_round_trips(tmp_path):
    tree = {
        "src/a.js": "console.log(1)\n",
        "nested/dir/b.txt": "hello\n",
    }
    materialize_tree(tree, tmp_path)
    assert (tmp_path / "src/a.js").read_text() == "console.log(1)\n"
    assert read_back_tree(tmp_path) == tree


def test_read_back_ignores_git_and_node_modules(tmp_path):
    materialize_tree({"keep.js": "x\n"}, tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("y\n")
    assert read_back_tree(tmp_path) == {"keep.js": "x\n"}


def test_read_back_includes_files_claude_created(tmp_path):
    materialize_tree({"a.js": "1\n"}, tmp_path)
    (tmp_path / "new.js").write_text("2\n")
    assert read_back_tree(tmp_path) == {"a.js": "1\n", "new.js": "2\n"}


# ---- Task 4: make_claude_run_fn -----------------------------------------------


def test_run_fn_success_builds_trajectory_with_produced_tree(tmp_path):
    captured = {}

    def fake_subprocess(argv, *, cwd, env, timeout):
        captured["argv"] = argv
        captured["cwd"] = cwd
        captured["home"] = env.get("HOME")
        # Claude "edits" a.js in the workdir.
        (Path(cwd) / "a.js").write_text("fixed\n")
        return _FakeCompleted(
            stdout=_result_json(
                num_turns=4, usage={"input_tokens": 10, "output_tokens": 5}
            )
        )

    def fake_workdir():
        wd = tmp_path / "wd"
        wd.mkdir()
        return wd

    run_fn = make_claude_run_fn(
        model="claude-sonnet-4-6",
        surface="edit-only",
        run_subprocess=fake_subprocess,
        workdir_factory=fake_workdir,
        max_budget_usd=0.5,
        timeout_s=300,
    )
    traj = run_fn(_edit_task({"a.js": "bug\n"}), 0)

    assert traj.final_state["files"] == {"a.js": "fixed\n"}
    assert traj.usage.prompt_tokens == 10
    assert traj.usage.completion_tokens == 5
    assert traj.rounds == 4
    assert traj.parse_failure is None
    # Ran in the workdir under the REAL HOME (auth resolves via $HOME); --safe-mode
    # provides the vanilla isolation; prompt carried the user message.
    assert captured["cwd"] == str(tmp_path / "wd")
    assert captured["home"] == os.environ.get("HOME")
    assert "--safe-mode" in captured["argv"]
    assert captured["argv"][-1] == "Fix the bug in a.js"


def test_run_fn_nonzero_exit_is_env_invalid(tmp_path):
    def fake_subprocess(argv, *, cwd, env, timeout):
        return _FakeCompleted(stdout="", returncode=1)

    def fake_workdir():
        wd = tmp_path / "wd2"
        wd.mkdir()
        return wd

    run_fn = make_claude_run_fn(
        model="m",
        surface="edit-only",
        run_subprocess=fake_subprocess,
        workdir_factory=fake_workdir,
        max_budget_usd=0.5,
        timeout_s=300,
    )
    traj = run_fn(_edit_task({"a.js": "bug\n"}), 0)
    assert traj.parse_failure is not None
    assert traj.parse_failure.error == PROVIDER_ERROR


def test_run_fn_timeout_is_env_invalid(tmp_path):
    def fake_subprocess(argv, *, cwd, env, timeout):
        raise _sp.TimeoutExpired(cmd=argv, timeout=timeout)

    def fake_workdir():
        wd = tmp_path / "wd3"
        wd.mkdir()
        return wd

    run_fn = make_claude_run_fn(
        model="m",
        surface="edit-only",
        run_subprocess=fake_subprocess,
        workdir_factory=fake_workdir,
        max_budget_usd=0.5,
        timeout_s=300,
    )
    traj = run_fn(_edit_task({"a.js": "bug\n"}), 0)
    assert traj.parse_failure is not None
    assert traj.parse_failure.error == PROVIDER_ERROR


# ---- Fix 4d: is_error / parse-error funnel to env-invalid (coverage gaps) ------


def test_run_fn_is_error_true_is_env_invalid(tmp_path):
    def fake_subprocess(argv, *, cwd, env, timeout):
        return _FakeCompleted(
            stdout=_result_json(is_error=True, subtype="error_max_turns")
        )

    def fake_workdir():
        wd = tmp_path / "wd_err"
        wd.mkdir()
        return wd

    run_fn = make_claude_run_fn(
        model="m",
        surface="edit-only",
        run_subprocess=fake_subprocess,
        workdir_factory=fake_workdir,
        max_budget_usd=0.5,
        timeout_s=300,
    )
    traj = run_fn(_edit_task({"a.js": "bug\n"}), 0)
    assert traj.parse_failure is not None
    assert traj.parse_failure.error == PROVIDER_ERROR


def test_run_fn_unparseable_stdout_is_env_invalid(tmp_path):
    def fake_subprocess(argv, *, cwd, env, timeout):
        return _FakeCompleted(stdout="not valid json {")

    def fake_workdir():
        wd = tmp_path / "wd_pe"
        wd.mkdir()
        return wd

    run_fn = make_claude_run_fn(
        model="m",
        surface="edit-only",
        run_subprocess=fake_subprocess,
        workdir_factory=fake_workdir,
        max_budget_usd=0.5,
        timeout_s=300,
    )
    traj = run_fn(_edit_task({"a.js": "bug\n"}), 0)
    assert traj.parse_failure is not None
    assert traj.parse_failure.error == PROVIDER_ERROR


# ---- Fix 3: an unreadable produced tree must not crash the whole run -----------


def test_run_fn_unreadable_produced_tree_is_env_invalid(tmp_path):
    # Claude (on `natural`/Bash) can emit a non-UTF-8 artifact. read_back_tree's
    # read_text() would raise UnicodeDecodeError OUTSIDE run_f_candidate's
    # env-invalid net, crashing the whole paid run. It must degrade to env-invalid.
    def fake_subprocess(argv, *, cwd, env, timeout):
        (Path(cwd) / "blob.bin").write_bytes(b"\xff\xfe\x00\x01")
        return _FakeCompleted(stdout=_result_json())

    def fake_workdir():
        wd = tmp_path / "wd_bin"
        wd.mkdir()
        return wd

    run_fn = make_claude_run_fn(
        model="m",
        surface="natural",
        run_subprocess=fake_subprocess,
        workdir_factory=fake_workdir,
        max_budget_usd=0.5,
        timeout_s=300,
    )
    traj = run_fn(_edit_task({"a.js": "bug\n"}), 0)
    assert traj.parse_failure is not None
    assert traj.parse_failure.error == PROVIDER_ERROR


# ---- pr-review nit 1: temp workdir must not leak across a 30-run ---------------


def test_run_fn_cleans_up_workdir(tmp_path):
    wd = tmp_path / "wd_clean"

    def fake_workdir():
        wd.mkdir()
        return wd

    def fake_subprocess(argv, *, cwd, env, timeout):
        (Path(cwd) / "a.js").write_text("fixed\n")
        return _FakeCompleted(stdout=_result_json())

    run_fn = make_claude_run_fn(
        model="m",
        surface="edit-only",
        run_subprocess=fake_subprocess,
        workdir_factory=fake_workdir,
        max_budget_usd=0.5,
        timeout_s=300,
    )
    traj = run_fn(_edit_task({"a.js": "bug\n"}), 0)
    # Read-back happened before cleanup (produced tree is captured in memory).
    assert traj.final_state["files"] == {"a.js": "fixed\n"}
    # The temp workdir is removed so a 30-attempt run does not leak tree copies.
    assert not wd.exists()


# ---- Fix 4a: nonzero-exit env-invalid carries stderr for debuggability ---------


def test_run_fn_nonzero_exit_carries_stderr_in_raw(tmp_path):
    def fake_subprocess(argv, *, cwd, env, timeout):
        return _FakeCompleted(stdout="", returncode=2, stderr="boom: auth failed")

    def fake_workdir():
        wd = tmp_path / "wd_se"
        wd.mkdir()
        return wd

    run_fn = make_claude_run_fn(
        model="m",
        surface="edit-only",
        run_subprocess=fake_subprocess,
        workdir_factory=fake_workdir,
        max_budget_usd=0.5,
        timeout_s=300,
    )
    traj = run_fn(_edit_task({"a.js": "bug\n"}), 0)
    assert traj.parse_failure is not None
    assert "boom: auth failed" in traj.parse_failure.raw


# ---- _sanitized_env strips contaminating vars, PRESERVES HOME/auth/PATH --------


def test_sanitized_env_strips_contaminating_keys_preserves_home_and_auth():
    base_env = {
        "HOME": "/original/home",
        "PATH": "/usr/bin:/bin",
        "ANTHROPIC_API_KEY": "sk-test-123",
        "CLAUDE_CODE_OAUTH_TOKEN": "oauth-abc",
        **{k: "contaminated" for k in _CONTAMINATING_ENV_KEYS},
    }
    result = _sanitized_env(base_env)
    # Contaminating vars are gone.
    for key in _CONTAMINATING_ENV_KEYS:
        assert key not in result, f"{key!r} should have been stripped"
    # HOME is PRESERVED (auth resolves via $HOME; isolation is via --safe-mode).
    assert result["HOME"] == "/original/home"
    # Auth keys survive.
    assert result["ANTHROPIC_API_KEY"] == "sk-test-123"
    assert result["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth-abc"
    # PATH survives.
    assert result["PATH"] == "/usr/bin:/bin"


# ---- Task 5: summarize_baseline -----------------------------------------------


def test_summary_clean_all_pass_is_pass_hat_k():
    a, b = _rr(True), _rr(True)
    o = ReplacementOutcome(
        valid_runs=(a, b),
        attempts=(
            TrialAttempt(attempt_index=0, valid=True, run=a),
            TrialAttempt(attempt_index=1, valid=True, run=b),
        ),
        void=False,
    )
    (row,) = summarize_baseline("cond", ["f1"], [o])
    assert row == BaselineRow(
        condition_id="cond",
        base="f1",
        k=2,
        valid=2,
        invalid=0,
        void=False,
        pass_hat_k=True,
        pass_at_1=1.0,
    )


def test_summary_one_valid_fail_breaks_pass_hat_k():
    a, b = _rr(True), _rr(False)
    o = ReplacementOutcome(
        valid_runs=(a, b),
        attempts=(
            TrialAttempt(attempt_index=0, valid=True, run=a),
            TrialAttempt(attempt_index=1, valid=True, run=b),
        ),
        void=False,
    )
    (row,) = summarize_baseline("cond", ["f1"], [o])
    assert row.pass_hat_k is False
    assert row.pass_at_1 == 0.5


def test_summary_void_when_an_attempt_is_env_invalid():
    a, bad = _rr(True), _rr(False)
    o = ReplacementOutcome(
        valid_runs=(a,),
        attempts=(
            TrialAttempt(attempt_index=0, valid=True, run=a),
            TrialAttempt(attempt_index=1, valid=False, run=bad),
        ),
        void=True,
    )
    (row,) = summarize_baseline("cond", ["f1"], [o])
    assert row.void is True
    assert row.pass_hat_k is False  # void never counts as a clean pass^k
    assert row.valid == 1 and row.invalid == 1


def test_summary_pairs_base_ids_to_outcomes_in_order():
    o1 = ReplacementOutcome(
        valid_runs=(_rr(True),),
        attempts=(TrialAttempt(attempt_index=0, valid=True, run=_rr(True)),),
        void=False,
    )
    o2 = ReplacementOutcome(
        valid_runs=(_rr(False),),
        attempts=(TrialAttempt(attempt_index=0, valid=True, run=_rr(False)),),
        void=False,
    )
    rows = summarize_baseline("cond", ["f1", "f2"], [o1, o2])
    assert [r.base for r in rows] == ["f1", "f2"]
    assert rows[0].pass_hat_k is True and rows[1].pass_hat_k is False
