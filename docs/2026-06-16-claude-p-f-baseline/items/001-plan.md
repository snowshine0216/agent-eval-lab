# claude-p F baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run vanilla Claude Code (`claude -p`, Sonnet 4.6, no skills) as the agent on F1/F2/F3 repair tasks under two tool surfaces (`edit-only`, `natural`), graded by the existing held-out Node oracle, producing a Claude baseline separate from the v2 ablation.

**Architecture:** A new `runners/claude_cli_candidate.py` provides a claude-p `run_fn` with the SAME signature as `make_f_run_fn` — `(edit_task, run_index) -> Trajectory`. It materializes the seeded tree to a temp dir, runs `claude -p` in a clean HOME, reads the produced tree back, and wraps it in a synthetic `Trajectory(final_state={"files": ...})`. That plugs unchanged into `run_f_candidate`'s k-loop and `grade_f_attempt` (the Node oracle grades purely off `final_state["files"]`). A new CLI subcommand `run-f-claude-baseline` iterates surfaces × bases × k. Subprocess failures become env-invalid via `ParseFailure(error=PROVIDER_ERROR)`. Auth is the session's OAuth/subscription — no per-token dollars; `total_cost_usd` is recorded as an informational efficiency metric.

**Tech Stack:** Python 3.13, `subprocess`, `httpx` (existing), pytest. The `claude` CLI (2.1.177) with `--output-format json --disable-slash-commands --allowedTools/--disallowedTools --max-budget-usd`.

**Spec:** `docs/superpowers/specs/2026-06-16-claude-p-f-baseline-design.md`

---

## File Structure

- **Create** `src/agent_eval_lab/runners/claude_cli_candidate.py` — the claude-p runner (pure helpers + injected-dependency `run_fn` factory). One responsibility: turn an F edit-task into a graded-ready `Trajectory` by driving `claude -p`.
- **Create** `tests/runners/test_claude_cli_candidate.py` — unit tests (no real `claude`, no network).
- **Modify** `src/agent_eval_lab/cli.py` — add the `run-f-claude-baseline` subparser + `_run_f_claude_baseline_command` handler + dispatch.
- **Modify** `tests/test_cli.py` (or the existing CLI test module) — arg-parse + dry-run tests.
- **Create** `reports/agentic-v1/f-claude-baseline/.gitkeep` — output dir (records written at run time).

### Reused, unchanged
- `runners/f_candidate.py`: `build_candidate_tree`, `make_edit_task`, `grade_f_attempt`, **`run_f_candidate`** (the strict-VOID k-loop: k attempts, mask env-invalid, `void = fewer than k valid`).
- `datasets/f_tasks.py`: `build_f_tasks` (plain F1/F2/F3 — NOT the 2×2 arm variants).
- `runners/multi_run.py`: `ReplacementOutcome`, `TrialAttempt` (the strict-VOID outcome shapes; `reports/m1.py` already consumes them).
- `records/trajectory.py`: `Trajectory`, `Usage`, `ParseFailure`, `PROVIDER_ERROR`.
- `records/grade.py`: `is_env_invalid_run` (used inside `run_f_candidate` to mark each attempt valid/invalid).
- `runners/node_oracle_edge.py` + the held-out oracle: grading, unchanged.

### Strict VOID — why `run_f_candidate`
The baseline drives **whole tasks** per (surface, base): all k attempts for one
base together. That is exactly `run_f_candidate`'s contract — it yields one
`ReplacementOutcome` per task carrying `valid_runs`, per-attempt `attempts`
(each flagged `valid`), and `void` (True iff `< k` clean attempts). The v2
ablation command inlines its loop only because it needs a *seeded cross-arm
order*; a no-arm baseline has no such constraint, so it uses `run_f_candidate`
directly and gets D34 VOID accounting for free. A small pure `summarize_baseline`
rolls the outcomes into per-(surface, base) rows for drill-down.

### Naming
- condition ids: `claude-cli:claude-sonnet-4-6:edit-only` and `claude-cli:claude-sonnet-4-6:natural`.
- surfaces: the literal strings `"edit-only"` and `"natural"`.

---

## Task 1: `ClaudeRunMeta` + `parse_claude_result`

**Files:**
- Create: `src/agent_eval_lab/runners/claude_cli_candidate.py`
- Test: `tests/runners/test_claude_cli_candidate.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/runners/test_claude_cli_candidate.py
import json
import pytest
from agent_eval_lab.runners.claude_cli_candidate import (
    ClaudeRunMeta,
    ClaudeResultParseError,
    parse_claude_result,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/runners/test_claude_cli_candidate.py -v`
Expected: FAIL with `ModuleNotFoundError`/`ImportError` (module not created yet).

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/runners/claude_cli_candidate.py
"""EDGE: run vanilla `claude -p` (Sonnet 4.6, no skills) as the F-task agent.

A baseline harness DISTINCT from the lab's chat-loop runner: Claude Code drives
its own loop with its native tools over a materialized copy of the pinned
web-dossier tree, then the held-out Node oracle grades the produced tree. Auth is
the session's OAuth/subscription (no per-token dollars; total_cost_usd is the
API-equivalent efficiency metric). See
docs/superpowers/specs/2026-06-16-claude-p-f-baseline-design.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


class ClaudeResultParseError(ValueError):
    """`claude -p --output-format json` stdout could not be parsed into a result."""


@dataclass(frozen=True, kw_only=True)
class ClaudeRunMeta:
    prompt_tokens: int
    completion_tokens: int
    num_turns: int
    total_cost_usd: float
    is_error: bool


def parse_claude_result(stdout: str) -> ClaudeRunMeta:
    """Parse the single result object from `--output-format json`.

    Maps usage.input_tokens -> prompt_tokens, usage.output_tokens ->
    completion_tokens. Raises ClaudeResultParseError on malformed/incomplete JSON
    (the caller maps that to env-invalid, never a model FAIL)."""
    try:
        obj = json.loads(stdout)
        usage = obj["usage"]
        return ClaudeRunMeta(
            prompt_tokens=int(usage["input_tokens"]),
            completion_tokens=int(usage["output_tokens"]),
            num_turns=int(obj["num_turns"]),
            total_cost_usd=float(obj["total_cost_usd"]),
            is_error=bool(obj["is_error"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ClaudeResultParseError(str(exc)) from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runners/test_claude_cli_candidate.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/claude_cli_candidate.py tests/runners/test_claude_cli_candidate.py
git commit -m "feat(claude-baseline): ClaudeRunMeta + parse_claude_result"
```

---

## Task 2: `claude_system_prompt` + `build_claude_argv`

**Files:**
- Modify: `src/agent_eval_lab/runners/claude_cli_candidate.py`
- Test: `tests/runners/test_claude_cli_candidate.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/runners/test_claude_cli_candidate.py
from agent_eval_lab.runners.claude_cli_candidate import (
    SURFACES,
    build_claude_argv,
    claude_system_prompt,
)


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
            model="m", surface="bogus", prompt="p", system_prompt="s", max_budget_usd=0.5
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/runners/test_claude_cli_candidate.py -k "surface or system_prompt or argv" -v`
Expected: FAIL with `ImportError` (symbols not defined).

- [ ] **Step 3: Write minimal implementation**

Append to `claude_cli_candidate.py`:

```python
SURFACES: tuple[str, ...] = ("edit-only", "natural")

# Inspect + edit tools every surface gets (Claude Code native tool names).
_BASE_ALLOWED_TOOLS: tuple[str, ...] = ("Read", "Edit", "Write", "Glob", "Grep")
# Never allowed in either baseline (keep it offline + non-agentic-delegating).
_ALWAYS_DENIED_TOOLS: tuple[str, ...] = ("WebFetch", "WebSearch", "Task")

_EDIT_SYSTEM_BASE = (
    "You are fixing code in a checked-out repository. The repository's files are "
    "in your current working directory. Inspect the relevant files, then make the "
    "owner-specified change. Change ONLY what the task requires; leave every other "
    "file and layer untouched. When the edit is complete, reply with a one-line "
    "summary and stop."
)
_NO_TESTS_LINE = "Do not attempt to run tests."


def claude_system_prompt(surface: str) -> str:
    """The edit instructions appended to Claude's system prompt. edit-only forbids
    running tests; natural allows it. No Factor-P scaffolding in either."""
    if surface not in SURFACES:
        raise ValueError(f"unknown surface: {surface!r}")
    if surface == "edit-only":
        return f"{_EDIT_SYSTEM_BASE}\n\n{_NO_TESTS_LINE}"
    return _EDIT_SYSTEM_BASE


def build_claude_argv(
    *,
    model: str,
    surface: str,
    prompt: str,
    system_prompt: str,
    max_budget_usd: float,
) -> list[str]:
    """Assemble the `claude -p` argv for one attempt. Pure list construction.

    Skills are disabled (--disable-slash-commands). Bash is allowed iff natural.
    There is no --max-turns in CLI 2.1.177; rounds are bounded by the subprocess
    timeout (caller), with --max-budget-usd as a secondary cost stop."""
    if surface not in SURFACES:
        raise ValueError(f"unknown surface: {surface!r}")
    allowed = list(_BASE_ALLOWED_TOOLS) + (["Bash"] if surface == "natural" else [])
    denied = list(_ALWAYS_DENIED_TOOLS) + (
        [] if surface == "natural" else ["Bash"]
    )
    return [
        "claude",
        "-p",
        "--model",
        model,
        "--output-format",
        "json",
        "--disable-slash-commands",
        "--append-system-prompt",
        system_prompt,
        "--allowedTools",
        " ".join(allowed),
        "--disallowedTools",
        " ".join(denied),
        "--max-budget-usd",
        str(max_budget_usd),
        prompt,
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runners/test_claude_cli_candidate.py -v`
Expected: PASS (all tests, including Task 1's).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/claude_cli_candidate.py tests/runners/test_claude_cli_candidate.py
git commit -m "feat(claude-baseline): system prompt + claude -p argv builder"
```

---

## Task 3: `materialize_tree` + `read_back_tree`

**Files:**
- Modify: `src/agent_eval_lab/runners/claude_cli_candidate.py`
- Test: `tests/runners/test_claude_cli_candidate.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/runners/test_claude_cli_candidate.py
from agent_eval_lab.runners.claude_cli_candidate import (
    materialize_tree,
    read_back_tree,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/runners/test_claude_cli_candidate.py -k "materialize or read_back" -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

Add imports at top of module: `from collections.abc import Mapping` and `from pathlib import Path`. Append:

```python
_READBACK_IGNORE: tuple[str, ...] = (".git", "node_modules")


def materialize_tree(tree: Mapping[str, str], dest: Path) -> None:
    """Write a {posix-relpath: content} tree to disk under dest."""
    for rel, content in tree.items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def read_back_tree(
    dest: Path, *, ignore: tuple[str, ...] = _READBACK_IGNORE
) -> dict[str, str]:
    """Read the produced tree back into {posix-relpath: content}, skipping any
    path under an ignored top-level dir (.git, node_modules)."""
    out: dict[str, str] = {}
    for path in sorted(dest.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(dest)
        if rel.parts[0] in ignore:
            continue
        out[rel.as_posix()] = path.read_text()
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runners/test_claude_cli_candidate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/claude_cli_candidate.py tests/runners/test_claude_cli_candidate.py
git commit -m "feat(claude-baseline): tree materialize + read-back"
```

---

## Task 4: `make_claude_run_fn` (the injected-dependency run_fn)

**Files:**
- Modify: `src/agent_eval_lab/runners/claude_cli_candidate.py`
- Test: `tests/runners/test_claude_cli_candidate.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/runners/test_claude_cli_candidate.py
from dataclasses import dataclass as _dc
from agent_eval_lab.records.trajectory import PROVIDER_ERROR
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import Task, TaskInput
from agent_eval_lab.runners.claude_cli_candidate import make_claude_run_fn


@_dc
class _FakeCompleted:
    stdout: str
    returncode: int = 0


def _edit_task(files):
    return Task(
        id="f-f1",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="Fix the bug in a.js"),),
            available_tools=("read_file",),
        ),
        verification=None,  # not used by the runner (grading is separate)
        initial_state={"files": dict(files)},
    )


def test_run_fn_success_builds_trajectory_with_produced_tree(tmp_path):
    captured = {}

    def fake_subprocess(argv, *, cwd, env, timeout):
        captured["argv"] = argv
        captured["cwd"] = cwd
        captured["home"] = env.get("HOME")
        # Claude "edits" a.js in the workdir.
        (Path(cwd) / "a.js").write_text("fixed\n")
        return _FakeCompleted(
            stdout=_result_json(num_turns=4, usage={"input_tokens": 10, "output_tokens": 5})
        )

    def fake_workdir():
        wd = tmp_path / "wd"
        home = tmp_path / "home"
        wd.mkdir()
        home.mkdir()
        return wd, home

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
    # Ran in the workdir under a clean HOME; prompt carried the user message.
    assert captured["cwd"] == str(tmp_path / "wd")
    assert captured["home"] == str(tmp_path / "home")
    assert captured["argv"][-1] == "Fix the bug in a.js"


def test_run_fn_nonzero_exit_is_env_invalid(tmp_path):
    def fake_subprocess(argv, *, cwd, env, timeout):
        return _FakeCompleted(stdout="", returncode=1)

    def fake_workdir():
        wd, home = tmp_path / "wd2", tmp_path / "home2"
        wd.mkdir(); home.mkdir()
        return wd, home

    run_fn = make_claude_run_fn(
        model="m", surface="edit-only", run_subprocess=fake_subprocess,
        workdir_factory=fake_workdir, max_budget_usd=0.5, timeout_s=300,
    )
    traj = run_fn(_edit_task({"a.js": "bug\n"}), 0)
    assert traj.parse_failure is not None
    assert traj.parse_failure.error == PROVIDER_ERROR


def test_run_fn_timeout_is_env_invalid(tmp_path):
    import subprocess as _sp

    def fake_subprocess(argv, *, cwd, env, timeout):
        raise _sp.TimeoutExpired(cmd=argv, timeout=timeout)

    def fake_workdir():
        wd, home = tmp_path / "wd3", tmp_path / "home3"
        wd.mkdir(); home.mkdir()
        return wd, home

    run_fn = make_claude_run_fn(
        model="m", surface="edit-only", run_subprocess=fake_subprocess,
        workdir_factory=fake_workdir, max_budget_usd=0.5, timeout_s=300,
    )
    traj = run_fn(_edit_task({"a.js": "bug\n"}), 0)
    assert traj.parse_failure is not None
    assert traj.parse_failure.error == PROVIDER_ERROR
```

> NOTE for implementer: confirm the exact `Task`/`TaskInput`/`MessageTurn` constructor kwargs against `src/agent_eval_lab/tasks/schema.py` and `records/turns.py` before running — adjust the `_edit_task` helper to match (e.g. `verification` may be required/optional). The runner only reads `edit_task.initial_state["files"]` and the first user message's `content`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/runners/test_claude_cli_candidate.py -k run_fn -v`
Expected: FAIL with `ImportError` (`make_claude_run_fn` undefined).

- [ ] **Step 3: Write minimal implementation**

Add imports: `import os`, `import subprocess`, `from collections.abc import Callable`, and
`from agent_eval_lab.records.trajectory import PROVIDER_ERROR, ParseFailure, Trajectory, Usage`.
Append:

```python
# Injected so unit tests need no real `claude` / network.
RunSubprocess = Callable[..., object]  # (argv, *, cwd, env, timeout) -> completed
WorkdirFactory = Callable[[], tuple[Path, Path]]  # () -> (workdir, clean_home)


def _user_prompt(edit_task) -> str:
    msg = next(
        (m for m in edit_task.input.messages if m.role == "user"), None
    )
    return msg.content if msg is not None else ""


def _env_invalid_trajectory(run_index: int, *, raw: str) -> Trajectory:
    """A run where Claude never produced a fair trial (subprocess failed / timed
    out / unparseable). Mirrors the chat-loop PROVIDER_ERROR path so
    is_env_invalid_run masks it out of pass^k."""
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=run_index,
        stop_reason="env_unhealthy",
        parse_failure=ParseFailure(raw=raw[:500], error=PROVIDER_ERROR),
        final_state={"files": {}},
    )


def make_claude_run_fn(
    *,
    model: str,
    surface: str,
    run_subprocess: RunSubprocess,
    workdir_factory: WorkdirFactory,
    max_budget_usd: float = 0.5,
    timeout_s: int = 300,
) -> Callable[[object, int], Trajectory]:
    """Build the per-attempt claude-p driver for one surface. Same signature as
    runners.f_candidate.make_f_run_fn so it plugs into run_f_candidate."""
    system_prompt = claude_system_prompt(surface)

    def run_fn(edit_task, run_index: int) -> Trajectory:
        workdir, clean_home = workdir_factory()
        seeded = dict((edit_task.initial_state or {}).get("files", {}))
        materialize_tree(seeded, workdir)
        argv = build_claude_argv(
            model=model,
            surface=surface,
            prompt=_user_prompt(edit_task),
            system_prompt=system_prompt,
            max_budget_usd=max_budget_usd,
        )
        env = {**os.environ, "HOME": str(clean_home)}
        try:
            completed = run_subprocess(
                argv, cwd=str(workdir), env=env, timeout=timeout_s
            )
        except subprocess.TimeoutExpired:
            return _env_invalid_trajectory(run_index, raw="timeout")
        if getattr(completed, "returncode", 0) != 0:
            return _env_invalid_trajectory(
                run_index, raw=getattr(completed, "stdout", "")
            )
        try:
            meta = parse_claude_result(completed.stdout)
        except ClaudeResultParseError as exc:
            return _env_invalid_trajectory(run_index, raw=str(exc))
        if meta.is_error:
            return _env_invalid_trajectory(run_index, raw="claude is_error")
        produced = read_back_tree(workdir)
        return Trajectory(
            turns=(),
            usage=Usage(
                prompt_tokens=meta.prompt_tokens,
                completion_tokens=meta.completion_tokens,
                latency_s=0.0,
            ),
            run_index=run_index,
            stop_reason="completed_natural",
            final_state={"files": produced},
            rounds=meta.num_turns,
            tool_call_counts={},
        )

    return run_fn
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runners/test_claude_cli_candidate.py -v`
Expected: PASS (all). If `Task`/`TaskInput` kwargs differ, fix the `_edit_task` helper per the NOTE and re-run.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/claude_cli_candidate.py tests/runners/test_claude_cli_candidate.py
git commit -m "feat(claude-baseline): make_claude_run_fn (clean HOME, env-invalid on failure)"
```

---

## Task 5: `summarize_baseline` — strict VOID + pass^k/pass@1 rollup (pure)

**Files:**
- Modify: `src/agent_eval_lab/runners/claude_cli_candidate.py`
- Test: `tests/runners/test_claude_cli_candidate.py`

Rolls a list of `ReplacementOutcome` (one per base task, from `run_f_candidate`)
into per-(surface, base) rows the owner can drill into: valid/invalid counts,
VOID, pass^k, pass@1. Pure — synthetic outcomes, no Node.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/runners/test_claude_cli_candidate.py
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
from agent_eval_lab.runners.claude_cli_candidate import (
    BaselineRow,
    summarize_baseline,
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
        condition_id="cond", base="f1", k=2, valid=2, invalid=0,
        void=False, pass_hat_k=True, pass_at_1=1.0,
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
    o1 = ReplacementOutcome(valid_runs=(_rr(True),),
        attempts=(TrialAttempt(attempt_index=0, valid=True, run=_rr(True)),), void=False)
    o2 = ReplacementOutcome(valid_runs=(_rr(False),),
        attempts=(TrialAttempt(attempt_index=0, valid=True, run=_rr(False)),), void=False)
    rows = summarize_baseline("cond", ["f1", "f2"], [o1, o2])
    assert [r.base for r in rows] == ["f1", "f2"]
    assert rows[0].pass_hat_k is True and rows[1].pass_hat_k is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/runners/test_claude_cli_candidate.py -k summary -v`
Expected: FAIL with `ImportError` (`BaselineRow`/`summarize_baseline` undefined).

- [ ] **Step 3: Write minimal implementation**

Add `from collections.abc import Sequence` to the imports, and
`from agent_eval_lab.runners.multi_run import ReplacementOutcome`. Append:

```python
@dataclass(frozen=True, kw_only=True)
class BaselineRow:
    condition_id: str
    base: str            # "f1" / "f2" / "f3"
    k: int               # attempts run for this base (== requested k)
    valid: int           # clean (non env-invalid) attempts
    invalid: int         # env-invalid attempts (subprocess failure/timeout/parse)
    void: bool           # True iff < k clean attempts (D34: never scored over <k)
    pass_hat_k: bool     # not void AND all k clean attempts passed
    pass_at_1: float     # fraction of clean attempts that passed


def summarize_baseline(
    condition_id: str,
    base_ids: Sequence[str],
    outcomes: Sequence[ReplacementOutcome],
) -> tuple[BaselineRow, ...]:
    """Roll one ReplacementOutcome per base into per-(condition, base) rows.
    Pure. `base_ids` and `outcomes` are positionally paired (strict)."""
    rows = []
    for base, outcome in zip(base_ids, outcomes, strict=True):
        passed = [r.grade.passed for r in outcome.valid_runs]
        n_valid = len(passed)
        n_attempts = len(outcome.attempts)
        rows.append(
            BaselineRow(
                condition_id=condition_id,
                base=base,
                k=n_attempts,
                valid=n_valid,
                invalid=n_attempts - n_valid,
                void=outcome.void,
                pass_hat_k=(not outcome.void) and n_valid > 0 and all(passed),
                pass_at_1=(sum(passed) / n_valid) if n_valid else 0.0,
            )
        )
    return tuple(rows)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runners/test_claude_cli_candidate.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/claude_cli_candidate.py tests/runners/test_claude_cli_candidate.py
git commit -m "feat(claude-baseline): summarize_baseline (strict VOID + pass^k/pass@1)"
```

---

## Task 6: CLI subcommand `run-f-claude-baseline`

**Files:**
- Modify: `src/agent_eval_lab/cli.py`
- Test: `tests/test_cli.py` (the module that tests `_build_parser` / commands)

The handler drives **`run_f_candidate` per surface** (strict D34 VOID), writes
every attempt (valid + invalid) to a per-condition JSONL for raw drill-down, and
writes `claude-baseline-summary.json` from `summarize_baseline`.

> **Prep (implementer):** add these to the TOP-LEVEL imports of `cli.py` so the
> handler is monkeypatchable and matches house style (the v2 ablation already
> imports `build_candidate_tree`/`make_edit_task`/`grade_f_attempt` at top):
> `from agent_eval_lab.datasets.f_tasks import build_f_tasks`,
> `from agent_eval_lab.runners.f_candidate import build_candidate_tree, run_f_candidate`,
> `from agent_eval_lab.runners.claude_cli_candidate import make_claude_run_fn, summarize_baseline`.
> Confirm `build_f_tasks`'s real kwarg (`datasets/f_tasks.py:172` — `evaluator_store: Path`)
> and the real task ids (`f-f1`/`f-f2`/`f-f3`) before running.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_cli.py
def test_claude_baseline_parser_defaults():
    from agent_eval_lab.cli import _build_parser
    args = _build_parser().parse_args(["run-f-claude-baseline", "--out", "/tmp/x"])
    assert args.command == "run-f-claude-baseline"
    assert args.surface == "both"
    assert args.k == 5
    assert args.bases == ["f1", "f2", "f3"]
    assert args.model == "claude-sonnet-4-6"
    assert args.smoke is False


def test_claude_baseline_smoke_and_surface_choice():
    from agent_eval_lab.cli import _build_parser
    args = _build_parser().parse_args(
        ["run-f-claude-baseline", "--out", "/tmp/x", "--surface", "edit-only", "--smoke"]
    )
    assert args.surface == "edit-only"
    assert args.smoke is True


def test_claude_baseline_dry_run_makes_no_subprocess(tmp_path):
    import argparse, json
    from agent_eval_lab.cli import _run_f_claude_baseline_command
    args = argparse.Namespace(
        out=tmp_path, surface="edit-only", k=1, bases=["f1"],
        model="claude-sonnet-4-6", smoke=True, dry_run=True,
        evaluator_config=None,
    )
    rc = _run_f_claude_baseline_command(args)
    assert rc == 0
    plan = json.loads((tmp_path / "claude-baseline.plan.json").read_text())
    assert plan["attempts"] == 1 and plan["surfaces"] == ["edit-only"]


def test_claude_baseline_writes_records_and_void_summary(tmp_path, monkeypatch):
    import json
    from agent_eval_lab import cli
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

    monkeypatch.setattr(cli, "node_supports_junit", lambda *a, **k: True)

    class _Store:  # minimal load_evaluator_config().store.path stand-in
        path = str(tmp_path / "store")
    class _Cfg:
        store = _Store()
    monkeypatch.setattr(cli, "load_evaluator_config", lambda _p: _Cfg())

    class _T:  # stand-in task; only .id is read by the handler before run_f_candidate
        def __init__(self, tid): self.id = tid
    monkeypatch.setattr(cli, "build_f_tasks", lambda **_k: (_T("f-f1"),))
    monkeypatch.setattr(cli, "build_candidate_tree", lambda t, repo: {})

    def _rr(passed):
        return RunResult(
            task_id="f-f1", condition_id="c", run_index=0,
            trajectory=Trajectory(turns=(),
                usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
                run_index=0, stop_reason="completed_natural"),
            grade=GradeResult(grader_id="node", passed=passed, score=0.0, evidence={}),
        )

    def fake_run_f_candidate(*, tasks, k, condition_id, build_tree_fn, run_fn):
        a, bad = _rr(True), _rr(False)
        yield ReplacementOutcome(
            valid_runs=(a,),
            attempts=(TrialAttempt(attempt_index=0, valid=True, run=a),
                      TrialAttempt(attempt_index=1, valid=False, run=bad)),
            void=True,
        )
    monkeypatch.setattr(cli, "run_f_candidate", fake_run_f_candidate)

    import argparse
    args = argparse.Namespace(
        out=tmp_path, surface="edit-only", k=2, bases=["f1"],
        model="claude-sonnet-4-6", smoke=False, dry_run=False,
        evaluator_config=None,
    )
    rc = cli._run_f_claude_baseline_command(args, run_fn_factory=lambda **_k: (lambda et, i: None))
    assert rc == 0
    # Raw drill-down: both attempts (valid + invalid) written.
    jsonl = next(tmp_path.glob("runs-claude-*-F.jsonl")).read_text().splitlines()
    assert len(jsonl) == 2
    # Strict VOID surfaced in the summary.
    summary = json.loads((tmp_path / "claude-baseline-summary.json").read_text())
    assert summary[0]["void"] is True
    assert summary[0]["valid"] == 1 and summary[0]["invalid"] == 1
    assert summary[0]["pass_hat_k"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -k claude_baseline -v`
Expected: FAIL (`run-f-claude-baseline` not a subcommand / handler undefined).

- [ ] **Step 3: Write minimal implementation**

Add the subparser inside `_build_parser` (near the `run-f-ablation` block ~line 1606):

```python
    cb = subparsers.add_parser(
        "run-f-claude-baseline",
        help="run vanilla claude -p (Sonnet 4.6, no skills) as the F-task agent",
    )
    cb.add_argument("--out", type=Path, required=True)
    cb.add_argument("--surface", choices=["edit-only", "natural", "both"], default="both")
    cb.add_argument("--k", type=int, default=5)
    cb.add_argument("--bases", nargs="+", default=["f1", "f2", "f3"])
    cb.add_argument("--model", default="claude-sonnet-4-6")
    cb.add_argument("--evaluator-config", type=Path, default=None)
    cb.add_argument(
        "--smoke", action="store_true",
        help="1 attempt, base f1, edit-only — validate plumbing/cost, then stop",
    )
    cb.add_argument("--dry-run", action="store_true")
```

Add the real subprocess+tempdir factory and the handler near `_run_f_ablation_command`:

```python
def _real_claude_factory():
    import subprocess as _sp
    import tempfile

    def factory(*, model, surface, condition_id):
        def run_subprocess(argv, *, cwd, env, timeout):
            return _sp.run(
                argv, cwd=cwd, env=env, timeout=timeout,
                capture_output=True, text=True,
            )

        def workdir_factory():
            return (
                Path(tempfile.mkdtemp(prefix="claude-f-")),
                Path(tempfile.mkdtemp(prefix="claude-home-")),
            )

        return make_claude_run_fn(
            model=model, surface=surface,
            run_subprocess=run_subprocess, workdir_factory=workdir_factory,
        )

    return factory


def _run_f_claude_baseline_command(args, *, run_fn_factory=None) -> int:
    surfaces = (
        ["edit-only"] if args.smoke
        else ["edit-only", "natural"] if args.surface == "both"
        else [args.surface]
    )
    bases = ["f1"] if args.smoke else list(args.bases)
    k = 1 if args.smoke else args.k

    args.out.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        plan = {
            "surfaces": surfaces, "bases": bases, "k": k,
            "attempts": len(surfaces) * len(bases) * k,
        }
        (args.out / "claude-baseline.plan.json").write_text(json.dumps(plan, indent=2))
        print(args.out / "claude-baseline.plan.json")
        return 0

    # Fail fast: the held-out oracle needs Node >=20 (cf. _run_f_ablation_command).
    if run_fn_factory is None and not node_supports_junit():
        print(
            "error: resolved node cannot run the held-out oracle (needs Node >=20). "
            "Set NODE_BIN to a Node >=20 binary and retry.",
            file=sys.stderr,
        )
        return 1

    f_repo = Path.home() / "Documents/Repository/web-dossier"
    cfg = load_evaluator_config(args.evaluator_config)
    store = Path(cfg.store.path) / "web-dossier-golden"
    all_tasks = {t.id: t for t in build_f_tasks(evaluator_store=store)}
    base_to_task = {b: all_tasks[f"f-{b}"] for b in bases}

    factory = run_fn_factory or _real_claude_factory()
    rows: list[BaselineRow] = []
    handles: dict[str, TextIO] = {}
    try:
        for surface in surfaces:
            cond = f"claude-cli:{args.model}:{surface}"
            handle = (args.out / f"runs-claude-{_slug(cond)}-F.jsonl").open("w")
            handles[cond] = handle
            run_fn = factory(model=args.model, surface=surface, condition_id=cond)
            outcomes = list(
                run_f_candidate(
                    tasks=[base_to_task[b] for b in bases],
                    k=k,
                    condition_id=cond,
                    build_tree_fn=lambda t: build_candidate_tree(t, repo=f_repo),
                    run_fn=run_fn,
                )
            )
            for outcome in outcomes:
                _append_runs(handle, [att.run for att in outcome.attempts])
            rows.extend(summarize_baseline(cond, bases, outcomes))
    finally:
        for fh in handles.values():
            fh.close()

    (args.out / "claude-baseline-summary.json").write_text(
        json.dumps([asdict(r) for r in rows], indent=2)
    )
    print(args.out / "claude-baseline-summary.json")
    return 0
```

Ensure `from dataclasses import asdict` and `import json` are imported at top of
`cli.py` (add if missing). Then wire dispatch (near line 1719):

```python
    if args.command == "run-f-claude-baseline":
        return _run_f_claude_baseline_command(args)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -k claude_baseline -v`
Expected: PASS.

- [ ] **Step 5: Run the full unit suite + lint**

Run: `pytest -q && ruff check . && ruff format --check .`
Expected: all pass (run `ruff format .` if the format gate complains — CI gates on whole-repo format).

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/test_cli.py reports/agentic-v1/f-claude-baseline/.gitkeep
git commit -m "feat(claude-baseline): run-f-claude-baseline (run_f_candidate, strict VOID, summary)"
```

---

## Task 7: Smoke run (manual integration — then PAUSE)

**This is the agreed stop point. Do NOT run the full 30 without owner go-ahead.**

- [ ] **Step 1: Dry-run preview (no claude, no quota)**

Run: `python -m agent_eval_lab run-f-claude-baseline --out reports/agentic-v1/f-claude-baseline/_smoke --smoke --dry-run`
Expected: prints the plan path; `attempts: 1`.

- [ ] **Step 2: Confirm Node oracle is capable (>=20)**

Run: `node --version` (and set `NODE_BIN=/Users/snow/.../v22.../bin/node` if PATH default is v16 — see memory `f-oracle-node-20-requirement`).
Expected: v20+ resolvable; otherwise the command fail-fasts by design.

- [ ] **Step 3: Real smoke attempt (1 × F1 × edit-only)**

Run: `python -m agent_eval_lab run-f-claude-baseline --out reports/agentic-v1/f-claude-baseline/_smoke --smoke`
Expected: exit 0; one JSONL row in `runs-claude-claude-cli-claude-sonnet-4-6-edit-only-F.jsonl`.

- [ ] **Step 4: Inspect the attempt**

Verify in the JSONL row: a non-empty produced tree, a graded verdict (pass or a genuine FAIL — NOT env-invalid), recorded `rounds` (num_turns) and usage tokens. Capture `total_cost_usd` (API-equivalent) and note wall-time + rough quota footprint.

- [ ] **Step 5: Report to owner and PAUSE**

Summarize: did the plumbing work end-to-end? F1 verdict, rounds, tokens, API-equivalent cost, wall-time. Then STOP and ask whether to proceed to the full run (`--surface both`, default k=5, bases f1/f2/f3 = 30 attempts) — and whether to keep budget/timeout defaults.

---

## Self-Review

**Spec coverage:**
- Two surfaces (edit-only/natural) with the one-line system-prompt difference → Task 2. ✓
- Vanilla isolation (clean HOME, `--disable-slash-commands`) → Task 2 (flag) + Task 4 (HOME). ✓
- claude-sonnet-4-6, OAuth/subscription billing, total_cost_usd recorded → Task 4 (usage/cost via meta) + Task 7 (capture cost). ✓
- **Strict VOID bookkeeping (owner request)** → Task 6 handler drives `run_f_candidate` per surface (k attempts, env-invalid masked, `void = <k clean`); Task 5 `summarize_baseline` surfaces per-(surface,base) valid/invalid/void/pass^k/pass@1; per-attempt JSONL gives raw drill-down. ✓
- Reuse grade path → Task 6 via `run_f_candidate` (which calls `grade_f_attempt` + `is_env_invalid_run` internally). ✓
- Env-invalid on subprocess failure/timeout/parse-error → Task 4 (`_env_invalid_trajectory`, PROVIDER_ERROR) → masked by `run_f_candidate`'s `is_env_invalid_run` → contributes to VOID. ✓
- Bounding: 300s timeout + --max-budget-usd, no --max-turns → Task 2 (argv) + Task 4 (timeout). ✓
- Node fail-fast (>=20) → Task 6 handler. ✓
- Smoke-first then pause → Task 7. ✓
- Separate report dir → Task 6 (`reports/agentic-v1/f-claude-baseline/`). ✓

**Placeholder scan:** `NOTE`s flag real signatures to confirm against the codebase (`Task`/`TaskInput` kwargs in Task 4; `build_f_tasks` store arg + task ids in Task 6) — verification instructions with concrete fallbacks, not unfinished code. No "TODO/TBD/add error handling" placeholders.

**Type consistency:** `ClaudeRunMeta` fields used identically in Tasks 1 & 4. `make_claude_run_fn` signature used in Tasks 4 & 6. `BaselineRow`/`summarize_baseline` defined in Task 5, consumed in Task 6 (`asdict` → summary JSON). `ReplacementOutcome`/`TrialAttempt` shapes consistent (Tasks 5 & 6 tests). `surface` literals `"edit-only"`/`"natural"` and condition_id `claude-cli:{model}:{surface}` consistent throughout.

**Known limitation to surface in the report:** `natural`'s Bash can run in-tree tests but the temp tree has no installed wdio/node_modules, so its practical "run tests" advantage is limited unless Claude installs deps within the attempt; the held-out golden test is never seeded (D19). Record actuals; don't assume `natural` ≈ Factor V.
