# Item 004 — Failure Classification + Final Evaluation Report (Exit Gate) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Weeks 5-6 run end-to-end per `docs/2026-06-11-coding-agent-eval/items/004-spec.md` (strike-throughs + Resolved decisions authoritative): (A) code — the pure world resolver (`runners/worlds.py`), the pytest-edge executor, `run_task_k`/CLI code-world wiring, the fc-v1 total classifier (`reports/classify.py`, ADR-0013), and the `report-final` command (pure build `reports/final.py` + render); then (B) live — `code_repair_v1` × k=3 × 4 conditions captured to committed run JSONLs, and the byte-deterministically regenerable `final-evaluation-report.md` — the run's user-stated exit gate.

**Architecture:** Functional core / imperative shell throughout. Resolution, classification, and report build+render are pure and total; subprocess I/O stays behind `pytest_edge`, HTTP behind `client.py`, file I/O in `cli.py`. The classifier is *derived, never stored* (frozen `RunResult` untouched); the discriminativeness rule is shared with `reports/validation.py` **by import, not extraction** (the `metrics/reliability._percentile` precedent), so the frozen Weeks 3-4 validation render cannot drift — and a golden-sha regression test pins it anyway.

**Tech Stack:** Python 3.11+ (project venv 3.13), httpx + MockTransport for stubs, hypothesis ≥ 6.100 (already a dev dep — grill Q15), pytest 9, ruff (`E,F,I,UP`, line length 88). All commands run via `uv run` from the repo root.

**Branch:** stay on the branch the orchestrator checked out (item branch `claude/coding-agent-eval-004`, PR into `autodev/coding-agent-eval-feature` per spec Branch flow). Commit after every task. NEVER push — the orchestrator handles pushes.

**Already done — do NOT recreate:** `docs/adr/0013-failure-classification-is-derived-total-and-versioned.md` and the CONTEXT.md terms (*RunClassification (failure classification)*, *world binding*, *task-defect candidate*, updated *FailureCategory*) exist since the grill (commit `db76cdc`). No task here touches ADRs or CONTEXT.md.

**Baseline:** at HEAD `daa7588`, `uv run pytest --collect-only` reports **582 tests**. After Part A: **644 collected → 643 passed, 1 skipped** (the committed-runs gate skips until Part B lands artifacts), full suite ≈ 21 s (baseline ≈ 16 s; the +3 s is the connect-error test's two real retry backoffs — `chat_completion` binds `time.sleep` at def time, so it cannot be monkeypatched away).

**Two kinds of work — read this first:**
- **Part A (Tasks 1-10) is CODE**, fully pre-validated in a scratch worktree on this machine: every code block below was executed exactly as written; the red-green sequence, test counts, golden sha, and sha256 sums are *measured*, not predicted. If an outcome differs, suspect a transcription slip first.
- **Part B (Tasks 11-15) is LIVE**: outcomes are nondeterministic (provider sampling, reachability) — **record actuals**. Expected outputs there are *mechanical checks only* (artifact exists, row counts, byte-identical regeneration, every failing run classified). **No pass-rate below is a prediction; never fabricate one.** A condition that is unreachable is SKIPPED loudly and recorded — the report renders it `blocked`; the other conditions proceed.

**Pre-validated facts this plan relies on** (measured in the scratch worktree):
- Red state: the five new test files fail collection with `ImportError`/`ModuleNotFoundError` before their modules exist; the `run_task_k` tests fail `TypeError: run_task_k() got an unexpected keyword argument 'apply_fn'`; the report-final CLI tests fail `SystemExit: 2` (argparse: invalid choice).
- Green state: 643 passed, 1 skipped; `uv run ruff check .` → `All checks passed!`; `uv run ruff format --check .` → `108 files already formatted`.
- New-test arithmetic: worlds 10 + classify 23 + classify-properties 2 + final 16 + appended (loop 1, loop_effects 1, multi_run 2, cli 5, validation 1, committed-runs 1) = **62**; 582 + 62 = 644. ✓
- sha256 gates for the three new src modules (transcribe byte-exactly, including trailing newline):
  - `src/agent_eval_lab/runners/worlds.py` → `c9f6eece19e919ae82864fbdb9416c50b9c7f17e875cbf7278a834d6d2f5a336`
  - `src/agent_eval_lab/reports/classify.py` → `c21c04509884071f3f763bcb2a67e10e1b6fb4f11ec61f96dc7324ba35ad17e4`
  - `src/agent_eval_lab/reports/final.py` → `7a380b9aaf110fee89ff812771f399d405c40e486b7cb8b5d898e294a9a8eda3`
- Validation golden sha (Task 9): `423e3a820a4acf5943addf545cd8ffadc979b8844a36702be55ae76e89e03169`.
- Dress rehearsal (stub HTTP client, REAL `code_repair_v1`, k=3): `run-baseline` streams exactly **45 JSONL records**, `report-final` over 1 captured + 3 missing conditions renders blocked rows and regenerates **byte-identically** (`diff` empty); the fc-v1 census over those 45 stub runs was `('agent_failure', 'oracle_red') 45` (the stub never repairs — rehearsal artifacts are never committed).
- `git check-ignore docs/2026-06-11-coding-agent-eval/runs/<f>.jsonl` exits **1** (not ignored — `/reports/` and `/runs/` are root-anchored), confirming grill Q6.
- `tests/test_committed_runs.py` flips from `1 skipped` to `1 passed per captured condition` the moment files land in the run dir (verified both ways).
- One sandboxed `run_pytest` ≈ 0.07 s; the new tests add ~6 sandbox invocations total — far inside the CI budget.

---

## File map

| Path | Action | Responsibility |
|---|---|---|
| `src/agent_eval_lab/records/trajectory.py` | Modify | + `NO_CHOICES_ERROR` shared constant (grill Q3); no record-shape change. |
| `src/agent_eval_lab/runners/loop.py` | Modify | record the constant instead of the inline literal. |
| `src/agent_eval_lab/runners/pytest_edge.py` | Modify | + `execute_request` — the `Executor` at the pytest edge (criterion 2). |
| `src/agent_eval_lab/runners/worlds.py` | Create | pure `resolve_world` + frozen `WorldBinding` (criterion 1). |
| `src/agent_eval_lab/runners/multi_run.py` | Modify | thread `apply_fn`/`executor` through `run_task_k`, workspace defaults (criterion 3). |
| `src/agent_eval_lab/reports/classify.py` | Create | fc-v1 total classifier, `RunClassification` (criteria 6-8, ADR-0013). |
| `src/agent_eval_lab/reports/final.py` | Create | pure final-report build + render; defect queue; shared discriminativeness (criteria 9, 14, 16-18). |
| `src/agent_eval_lab/cli.py` | Modify | per-task world resolution, fail-loud reachability, `report-final` command (criteria 4-5, 15). |
| `tests/runners/test_worlds.py` | Create | 10 resolver tests incl. disjointness invariant + shipped-dataset sweep. |
| `tests/reports/test_classify.py` | Create | 23 tests: one per mapping row + walk + taxonomy pins. |
| `tests/reports/test_classify_properties.py` | Create | 2 Hypothesis properties: totality/closure, determinism. |
| `tests/reports/test_final.py` | Create | 16 builder/renderer tests incl. defect-queue quartet + determinism. |
| `tests/test_committed_runs.py` | Create | committed-artifact gate (skips until Part B). |
| `tests/runners/test_loop.py` | Append | constant-pin stub-loop test (criterion 7 row 2). |
| `tests/runners/test_loop_effects.py` | Append | `execute_request` integration through `run_single`. |
| `tests/runners/test_multi_run.py` | Append | byte-identical workspace regression + code-world threading. |
| `tests/test_cli.py` | Append | code-world E2E, connect-error, report-final CLI tests. |
| `tests/reports/test_validation.py` | Append | golden-sha pin of the frozen validation render (grill Q12). |
| `docs/2026-06-11-coding-agent-eval/prices.json` | Create (Part B) | pinned shape; **values recorded live** at snapshot date. |
| `docs/2026-06-11-coding-agent-eval/v2-context.md` | Create (Part B) | verbatim v1/v2 context, derived from committed Weeks 3-4 reports. |
| `docs/2026-06-11-coding-agent-eval/runs/runs-<slug>.jsonl` | Create (Part B, live) | committed run artifacts, one per reachable condition. |
| `docs/2026-06-11-coding-agent-eval/final-evaluation-report.md` | Create (Part B, live) | the exit-gate artifact. |
| `reports/code-repair/` | Working dir (gitignored) | live-run working copies; **never** write to `reports/` root (Weeks 3-4 artifacts live there and are the only regeneration source for the committed Weeks 3-4 reports — overwriting them is forbidden, criterion 12). |

Frozen (hard constraints): `RunResult`, `GradeResult`, `FailureCategory`, `Trajectory`, the runs-JSONL line format, `condition_id = provider:model`, the dataset + sidecars (append-only), `reports/validation.py` behavior (pinned by golden sha), the v1-era baseline renderer.

---

# Part A — code (TDD; every block pre-validated)


### Task 1: Shared empty-choices constant (`NO_CHOICES_ERROR`)

The fc-v1 row-2/row-3 split keys on the loop's empty-choices literal. Hoist it
to `records/trajectory.py` (schema-adjacent pure module; no record-shape
change) so loop and classifier share one constant (grill Q3).

**Files:**
- Modify: `src/agent_eval_lab/records/trajectory.py`
- Modify: `src/agent_eval_lab/runners/loop.py`
- Test: `tests/runners/test_loop.py` (append)

- [ ] **Step 1.1: Append the failing test to `tests/runners/test_loop.py`**

Append exactly this block at the end of the file:

```python
def test_empty_choices_records_the_shared_constant_verbatim() -> None:
    """Grill Q3: the classifier's harness/agent parse split keys on this exact
    string; loop and classifier share one constant so the split cannot drift."""
    from agent_eval_lab.records.trajectory import NO_CHOICES_ERROR

    client = _scripted_client(
        [{"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}]
    )

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=6,
        temperature=0.0,
    )

    assert trajectory.parse_failure is not None
    assert trajectory.parse_failure.error == NO_CHOICES_ERROR
```

- [ ] **Step 1.2: Run it — expect red**

Run: `uv run pytest tests/runners/test_loop.py -q`
Expected: 1 failed (ImportError: cannot import name 'NO_CHOICES_ERROR'), rest pass.

- [ ] **Step 1.3: Add the constant to `src/agent_eval_lab/records/trajectory.py`**

Replace this exact block:

```python
from agent_eval_lab.records.turns import Turn


@dataclass(frozen=True, kw_only=True)
class ParseFailure:
```

with:

```python
from agent_eval_lab.records.turns import Turn

# The loop's empty-choices parse-failure literal: the provider envelope carried
# no completion at all, so the model under test never acted on the turn.
# Schema-adjacent (no record-shape change) and shared between runners/loop.py,
# which records it, and reports/classify.py, whose fc-v1 harness/agent
# parse-failure split keys on it (ADR-0013) — one constant, so the two sides
# cannot drift (item 004 grill Q3).
NO_CHOICES_ERROR = "no choices in provider response"


@dataclass(frozen=True, kw_only=True)
class ParseFailure:
```

- [ ] **Step 1.4: Use the constant in `src/agent_eval_lab/runners/loop.py`**

Replace:

```python
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
```

with:

```python
from agent_eval_lab.records.trajectory import (
    NO_CHOICES_ERROR,
    ParseFailure,
    Trajectory,
    Usage,
)
```

and replace:

```python
            parse_failure = ParseFailure(
                raw=json.dumps(dict(response.payload)),
                error="no choices in provider response",
            )
```

with:

```python
            parse_failure = ParseFailure(
                raw=json.dumps(dict(response.payload)),
                error=NO_CHOICES_ERROR,
            )
```

(Leave `runners/judge_edge.py`'s copy of the literal alone: the classifier
reads only the trajectory's `parse_failure`, and the judge edge is a frozen
002 surface.)

- [ ] **Step 1.5: Run — expect green**

Run: `uv run pytest tests/runners/test_loop.py tests/records/ -q`
Expected: all pass (measured: 1 new test green; existing loop/record tests unaffected).

- [ ] **Step 1.6: Commit**

```bash
git add src/agent_eval_lab/records/trajectory.py src/agent_eval_lab/runners/loop.py tests/runners/test_loop.py
git commit -m "feat(004): hoist empty-choices literal to shared NO_CHOICES_ERROR constant (grill Q3)"
```


### Task 2: `execute_request` — the Executor at the pytest edge

**Files:**
- Modify: `src/agent_eval_lab/runners/pytest_edge.py`
- Test: `tests/runners/test_loop_effects.py` (append)

- [ ] **Step 2.1: Append the failing integration test to `tests/runners/test_loop_effects.py`**

Append exactly this block at the end of the file:

```python
def test_execute_request_fulfills_run_tests_through_the_loop() -> None:
    """Criterion 2: the shipped pytest-edge executor, end to end through
    run_single — a fulfilled run_tests records ToolSuccess carrying a
    serialized ExecutionResult, whatever the suite status (ADR-0008)."""
    from agent_eval_lab.runners.pytest_edge import execute_request

    failing = {"test_bug.py": "def test_bug():\n    assert 1 == 2\n"}
    client = _scripted_client(
        [_tool_call_response("run_tests", {}, "c1"), _final_response("Done.")]
    )

    trajectory = run_single(
        task=_task(failing),
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=execute_request,
    )

    outcome = trajectory.turns[2].outcome
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["status"] == "failed"
    assert outcome.result["exit_code"] == 1
    assert "<sandbox>" in outcome.result["stdout"] or outcome.result["stdout"]
```

- [ ] **Step 2.2: Run it — expect red**

Run: `uv run pytest tests/runners/test_loop_effects.py -q`
Expected: 1 failed (ImportError: cannot import name 'execute_request'), 7 pass.

- [ ] **Step 2.3: Implement `execute_request` in `src/agent_eval_lab/runners/pytest_edge.py`**

Replace:

```python
from agent_eval_lab.records.execution import (
    ExecutionResult,
```

with:

```python
from agent_eval_lab.records.execution import (
    ExecutionRequest,
    ExecutionResult,
```

and insert this function immediately ABOVE `def run_pytest(`:

```python
def execute_request(request: ExecutionRequest) -> ExecutionResult:
    """The loop's `Executor` satisfied at the pytest edge (item 004 crit. 2).

    The request carries only the tree (CONTEXT.md **ExecutionRequest**);
    timeout and interpreter stay edge policy, so the agent controls neither.
    """
    return run_pytest(request.files, timeout_s=DEFAULT_TIMEOUT_S)
```

- [ ] **Step 2.4: Run — expect green**

Run: `uv run pytest tests/runners/test_loop_effects.py tests/runners/test_pytest_edge.py -q`
Expected: all pass (the new test does ONE real sandboxed run, ~0.1 s).

- [ ] **Step 2.5: Commit**

```bash
git add src/agent_eval_lab/runners/pytest_edge.py tests/runners/test_loop_effects.py
git commit -m "feat(004): execute_request — run_pytest-backed Executor at the pytest edge (crit. 2)"
```


### Task 3: World resolver (`runners/worlds.py`)

**Files:**
- Create: `src/agent_eval_lab/runners/worlds.py`
- Test: `tests/runners/test_worlds.py` (create)

- [ ] **Step 3.1: Write the failing test file `tests/runners/test_worlds.py`**

```python
"""World resolver: dataset tools -> world binding (item 004 criterion 1)."""

from pathlib import Path

import pytest

from agent_eval_lab.runners.pytest_edge import execute_request
from agent_eval_lab.runners.worlds import WorldBinding, resolve_world
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS
from agent_eval_lab.tools.code_world import apply as code_world_apply
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS
from agent_eval_lab.tools.workspace import apply as workspace_apply


def test_pure_workspace_set_resolves_to_workspace_binding() -> None:
    binding = resolve_world(("search_docs", "create_ticket", "update_ticket"))
    assert binding == WorldBinding(
        registry=WORKSPACE_TOOLS, apply_fn=workspace_apply, executor=None
    )


def test_pure_code_set_resolves_to_code_binding_with_pytest_executor() -> None:
    binding = resolve_world(("read_file", "write_file", "list_files", "run_tests"))
    assert binding == WorldBinding(
        registry=CODE_WORLD_TOOLS, apply_fn=code_world_apply, executor=execute_request
    )


def test_partial_code_set_still_resolves_to_code_binding() -> None:
    assert resolve_world(("read_file",)).registry is CODE_WORLD_TOOLS


def test_cross_world_mix_raises_value_error_naming_offenders() -> None:
    with pytest.raises(ValueError, match="search_docs.*read_file|read_file"):
        resolve_world(("search_docs", "read_file"))


def test_unknown_name_raises_value_error_naming_it() -> None:
    with pytest.raises(ValueError, match="frobnicate"):
        resolve_world(("read_file", "frobnicate"))


def test_empty_tool_list_raises_value_error() -> None:
    with pytest.raises(ValueError, match="empty tool list"):
        resolve_world(())


def test_registries_are_disjoint_load_bearing_invariant() -> None:
    """Membership resolution is only sound while the name spaces stay disjoint:
    a future tool name reused across worlds must fail CI here (grill Q4)."""
    assert set(WORKSPACE_TOOLS) & set(CODE_WORLD_TOOLS) == set()


@pytest.mark.parametrize(
    ("dataset", "registry"),
    [
        ("examples/datasets/workspace_tool_use_v1.jsonl", WORKSPACE_TOOLS),
        ("examples/datasets/workspace_tool_use_v2.jsonl", WORKSPACE_TOOLS),
        ("examples/datasets/code_repair_v1.jsonl", CODE_WORLD_TOOLS),
    ],
)
def test_every_shipped_task_resolves_to_exactly_one_world(dataset, registry) -> None:
    for task in load_tasks(Path(dataset)):
        assert resolve_world(task.input.available_tools).registry is registry
```

- [ ] **Step 3.2: Run it — expect red**

Run: `uv run pytest tests/runners/test_worlds.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'agent_eval_lab.runners.worlds'`.

- [ ] **Step 3.3: Write `src/agent_eval_lab/runners/worlds.py`**

```python
"""Pure world resolution: a task's `available_tools` -> its world binding.

The dataset row is the single source of world truth (item 004 resolved Q1):
tool names resolve by membership in exactly one world's registry. The two
name spaces are disjoint by tested invariant; an unknown name, a cross-world
mix, or an empty tool list refuses to resolve — fail loud, never a silent
default (grill Q4). Resolution itself is pure; the code-world binding carries
the pytest edge's `execute_request` as a value, never invoking it here.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_eval_lab.runners.loop import ApplyFn, Executor
from agent_eval_lab.runners.pytest_edge import execute_request
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS
from agent_eval_lab.tools.code_world import apply as code_world_apply
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS, ToolDef
from agent_eval_lab.tools.workspace import apply as workspace_apply


@dataclass(frozen=True, kw_only=True)
class WorldBinding:
    """The frozen (registry, apply_fn, executor) triple (CONTEXT.md term)."""

    registry: Mapping[str, ToolDef]
    apply_fn: ApplyFn
    executor: Executor | None


_WORKSPACE_BINDING = WorldBinding(
    registry=WORKSPACE_TOOLS, apply_fn=workspace_apply, executor=None
)
_CODE_BINDING = WorldBinding(
    registry=CODE_WORLD_TOOLS, apply_fn=code_world_apply, executor=execute_request
)


def resolve_world(available_tools: Sequence[str]) -> WorldBinding:
    """Resolve by tool-name membership; ValueError names every offender."""
    names = tuple(available_tools)
    if not names:
        raise ValueError(
            "cannot resolve world: empty tool list (no shipped dataset has a "
            "tool-less task; refusing to invent semantics — item 004 grill Q4)"
        )
    unknown = tuple(
        name
        for name in names
        if name not in WORKSPACE_TOOLS and name not in CODE_WORLD_TOOLS
    )
    if unknown:
        raise ValueError(f"cannot resolve world: unknown tools {unknown!r}")
    workspace_names = tuple(name for name in names if name in WORKSPACE_TOOLS)
    code_names = tuple(name for name in names if name in CODE_WORLD_TOOLS)
    if workspace_names and code_names:
        raise ValueError(
            "cannot resolve world: cross-world tool mix "
            f"(workspace {workspace_names!r} vs code {code_names!r})"
        )
    return _CODE_BINDING if code_names else _WORKSPACE_BINDING
```

- [ ] **Step 3.4: Run — expect green; verify the sha gate**

Run: `uv run pytest tests/runners/test_worlds.py -q`
Expected: `10 passed` (5 resolution cases incl. empty-set ValueError, the
disjointness invariant, the partial-code case, and the 3-dataset sweep proving
every shipped task resolves — v1/v2 → workspace, code_repair_v1 → code).

Run: `shasum -a 256 src/agent_eval_lab/runners/worlds.py`
Expected: `c9f6eece19e919ae82864fbdb9416c50b9c7f17e875cbf7278a834d6d2f5a336`

- [ ] **Step 3.5: Commit**

```bash
git add src/agent_eval_lab/runners/worlds.py tests/runners/test_worlds.py
git commit -m "feat(004): pure world resolver — available_tools -> frozen WorldBinding (crit. 1)"
```


### Task 4: `run_task_k` threading (workspace defaults preserved)

Judgment call (pre-resolved): `run_task_k` takes the binding's **fields**
(`apply_fn`, `executor`), not the `WorldBinding` object — a binding default
would force `multi_run` to import `worlds`→`pytest_edge`, dragging
subprocess-adjacent modules into the runner; field defaults preserve today's
behavior with zero new imports beyond `workspace.apply`.

**Files:**
- Modify: `src/agent_eval_lab/runners/multi_run.py`
- Test: `tests/runners/test_multi_run.py` (append)

- [ ] **Step 4.1: Append the failing tests to `tests/runners/test_multi_run.py`**

Append exactly this block at the end of the file:

```python
def test_run_task_k_defaults_yield_byte_identical_workspace_run(monkeypatch) -> None:
    """Criterion 3: the new apply_fn/executor parameters default to today's
    workspace behavior EXACTLY — explicit workspace binding fields serialize
    byte-identically to the defaults. Latency is pinned (monotonic stubbed)
    because wall-clock is the one nondeterministic usage field."""
    import agent_eval_lab.runners.client as client_module
    from agent_eval_lab.records.serialize import run_result_to_dict
    from agent_eval_lab.tools.workspace import apply as workspace_apply

    monkeypatch.setattr(client_module.time, "monotonic", lambda: 0.0)

    def run(**extra):
        return run_task_k(
            task=TASK,
            registry=WORKSPACE_TOOLS,
            config=CONFIG,
            http_client=httpx.Client(transport=httpx.MockTransport(_handler)),
            k=1,
            max_steps=6,
            temperature=0.0,
            **extra,
        )

    defaults = json.dumps(run_result_to_dict(run()[0]), sort_keys=True)
    explicit = json.dumps(
        run_result_to_dict(run(apply_fn=workspace_apply, executor=None)[0]),
        sort_keys=True,
    )
    assert defaults == explicit


def test_run_task_k_threads_code_world_binding_to_run_single() -> None:
    """Criterion 3: a code-world task through run_task_k fulfills run_tests
    via the threaded executor and grades through the oracle edge."""
    from agent_eval_lab.records.turns import MessageTurn, ToolResultTurn, ToolSuccess
    from agent_eval_lab.runners.pytest_edge import execute_request
    from agent_eval_lab.tasks.schema import ExecutionSpec
    from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS
    from agent_eval_lab.tools.code_world import apply as code_world_apply

    task = Task(
        id="cw-thread-001",
        capability="code_repair",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="Run the tests."),),
            available_tools=("read_file", "write_file", "list_files", "run_tests"),
        ),
        verification=ExecutionSpec(
            held_out_tests={
                "test_oracle_demo.py": "def test_oracle():\n    assert True\n"
            }
        ),
        metadata=TaskMetadata(split="dev", version="1", provenance="hand_written"),
        initial_state={"files": {"test_demo.py": "def test_ok():\n    assert True\n"}},
    )
    responses = [
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {"name": "run_tests", "arguments": "{}"},
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
        {
            "choices": [{"message": {"role": "assistant", "content": "Done."}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    ]
    remaining = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=remaining.pop(0))

    [result] = run_task_k(
        task=task,
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        k=1,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=execute_request,
    )

    [tool_result] = [
        t for t in result.trajectory.turns if isinstance(t, ToolResultTurn)
    ]
    assert isinstance(tool_result.outcome, ToolSuccess)
    assert tool_result.outcome.result["status"] == "passed"
    assert result.grade.grader_id == "execution"
    assert result.grade.passed is True
    assert result.grade.evidence["execution"] == "run"
```

- [ ] **Step 4.2: Run them — expect red**

Run: `uv run pytest tests/runners/test_multi_run.py -q`
Expected: 2 failed — `TypeError: run_task_k() got an unexpected keyword argument 'apply_fn'`; existing tests pass.

- [ ] **Step 4.3: Thread the fields through `src/agent_eval_lab/runners/multi_run.py`**

Replace:

```python
from agent_eval_lab.runners.loop import run_single
```

with:

```python
from agent_eval_lab.runners.loop import ApplyFn, Executor, run_single
```

Replace:

```python
from agent_eval_lab.tools.workspace import ToolDef
```

with:

```python
from agent_eval_lab.tools.workspace import ToolDef
from agent_eval_lab.tools.workspace import apply as workspace_apply
```

Replace:

```python
    k: int,
    max_steps: int,
    temperature: float,
) -> tuple[RunResult, ...]:
    condition = condition_id(config)
```

with:

```python
    k: int,
    max_steps: int,
    temperature: float,
    apply_fn: ApplyFn = workspace_apply,
    executor: Executor | None = None,
) -> tuple[RunResult, ...]:
    # The world-binding fields (item 004 criterion 3) default to today's
    # workspace behavior exactly; cli.run_baseline threads the resolved
    # binding's fields per task (runners/worlds.resolve_world).
    condition = condition_id(config)
```

Replace:

```python
            max_steps=budget,
            temperature=temperature,
        )
```

with:

```python
            max_steps=budget,
            temperature=temperature,
            apply_fn=apply_fn,
            executor=executor,
        )
```

- [ ] **Step 4.4: Run — expect green**

Run: `uv run pytest tests/runners/test_multi_run.py -q`
Expected: all pass. The byte-identical regression pins criterion 3: with
`client.time.monotonic` stubbed (latency is the one wall-clock usage field),
the default path and the explicit workspace binding serialize to the SAME
`json.dumps(run_result_to_dict(...), sort_keys=True)` string. The threading
test fulfills a real `run_tests` and grades through the real oracle edge.

- [ ] **Step 4.5: Commit**

```bash
git add src/agent_eval_lab/runners/multi_run.py tests/runners/test_multi_run.py
git commit -m "feat(004): thread apply_fn/executor through run_task_k, workspace defaults byte-identical (crit. 3)"
```


### Task 5: CLI world resolution + fail-loud reachability

**Files:**
- Modify: `src/agent_eval_lab/cli.py`
- Test: `tests/test_cli.py` (append)

- [ ] **Step 5.1: Append the failing tests to `tests/test_cli.py`**

Append exactly this block at the end of the file:

```python
# ── Item 004: code-world wiring through run-baseline ─────────────────────────


def _write_code_dataset(path: Path) -> Path:
    row = {
        "id": "cr-e2e-001",
        "capability": "visible_test_localization",
        "input": {
            "messages": [
                {
                    "type": "message",
                    "role": "user",
                    "content": "Fix add in calc.py, then run the tests.",
                }
            ],
            "available_tools": [
                "read_file",
                "write_file",
                "list_files",
                "run_tests",
            ],
        },
        "verification": {
            "type": "execution",
            "held_out_tests": {
                "test_oracle_calc.py": (
                    "from calc import add\n\n\ndef test_add():\n"
                    "    assert add(1, 2) == 3\n"
                )
            },
        },
        "metadata": {"split": "dev", "version": "1", "provenance": "hand_written"},
        "initial_state": {
            "files": {
                "calc.py": "def add(a, b):\n    return a - b\n",
                "test_calc.py": (
                    "from calc import add\n\n\ndef test_add_smoke():\n"
                    "    assert add(2, 2) == 4\n"
                ),
            }
        },
    }
    path.write_text(json.dumps(row) + "\n")
    return path


def _code_world_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if any(m["role"] == "tool" for m in body["messages"]):
        message = {"role": "assistant", "content": "Ran the tests."}
    else:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "run_tests", "arguments": "{}"},
                }
            ],
        }
    return httpx.Response(
        200,
        json={
            "choices": [{"message": message}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


def test_run_baseline_resolves_code_world_and_grades_through_oracle(
    tmp_path: Path,
) -> None:
    """Criterion 4: no hardwired WORKSPACE_TOOLS — a code task resolves to the
    code world, fulfills a mid-trajectory run_tests at the pytest edge, grades
    through the oracle edge, and streams a parseable RunResult line."""
    from agent_eval_lab.cli import _load_run_results
    from agent_eval_lab.records.turns import ToolResultTurn, ToolSuccess

    dataset = _write_code_dataset(tmp_path / "code.jsonl")
    out_dir = tmp_path / "out"
    client = httpx.Client(transport=httpx.MockTransport(_code_world_handler))

    exit_code = main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "local",
            "--k",
            "1",
            "--out",
            str(out_dir),
        ],
        http_client=client,
    )

    assert exit_code == 0
    [run] = _load_run_results(out_dir / "runs-local-qwen3-8b.jsonl")
    [tool_result] = [t for t in run.trajectory.turns if isinstance(t, ToolResultTurn)]
    assert isinstance(tool_result.outcome, ToolSuccess)
    assert tool_result.outcome.result["status"] == "failed"  # unrepaired tree
    assert run.grade.grader_id == "execution"
    assert run.grade.passed is False
    assert run.grade.evidence["execution"] == "run"
    assert run.grade.evidence["status"] == "failed"


def test_run_baseline_connect_error_exits_1_with_provider_and_hint(
    tmp_path: Path, capsys
) -> None:
    """Criterion 5: a refused connection is a one-line exit-1 diagnostic naming
    provider id + base_url, with the start-the-server hint for `local` — never
    a traceback. (Wall time ~3s: the client's two retry backoffs.)"""
    dataset = _write_dataset(tmp_path / "tasks.jsonl")

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    exit_code = main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "local",
            "--k",
            "1",
            "--out",
            str(tmp_path / "out"),
        ],
        http_client=httpx.Client(transport=httpx.MockTransport(refuse)),
    )

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "local" in err
    assert "http://localhost:11434/v1" in err
    assert "is the server running?" in err
    assert "Traceback" not in err
```

- [ ] **Step 5.2: Run them — expect red**

Run: `uv run pytest tests/test_cli.py -q`
Expected: 2 errors/failures — the code-world E2E dies with
`ValueError: tools not in registry: ('read_file', ...)` (WORKSPACE_TOOLS is
hardwired today), and the connect-error test fails because `httpx.ConnectError`
propagates as a traceback instead of exit 1. Existing tests pass.

- [ ] **Step 5.3: Wire the resolver and the diagnostic into `src/agent_eval_lab/cli.py`**

(This task adds only the `worlds` import; Task 8 Step 8.3 adds the
`reports.final` imports once that module exists.)

Replace:

```python
from agent_eval_lab.runners.multi_run import run_task_k
from agent_eval_lab.runners.prompt import apply_system_prompt
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.schema import LlmJudgeSpec
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS
```

with:

```python
from agent_eval_lab.runners.multi_run import run_task_k
from agent_eval_lab.runners.prompt import apply_system_prompt
from agent_eval_lab.runners.worlds import resolve_world
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.schema import LlmJudgeSpec
```

In `run_baseline`, replace:

```python
        for task in tasks:
            run_task = (
```

with:

```python
        for task in tasks:
            binding = resolve_world(task.input.available_tools)
            run_task = (
```

and replace:

```python
            task_runs = run_task_k(
                task=run_task,
                registry=WORKSPACE_TOOLS,
                config=config,
                http_client=http_client,
                k=k,
                max_steps=max_steps,
                temperature=temperature,
            )
```

with:

```python
            task_runs = run_task_k(
                task=run_task,
                registry=binding.registry,
                config=config,
                http_client=http_client,
                k=k,
                max_steps=max_steps,
                temperature=temperature,
                apply_fn=binding.apply_fn,
                executor=binding.executor,
            )
```

In `_run_baseline_command`, add the `except` between the `run_baseline(...)`
call's closing paren and the existing `finally:`:

```python
    except httpx.TransportError as exc:
        # Criterion 5: a connection failure is a one-line exit-1 diagnostic —
        # never a traceback mid-corpus. The streamed JSONL keeps any partial
        # progress for `incomplete` reporting.
        hint = " — is the server running?" if config.id == "local" else ""
        print(
            f"error: cannot reach provider {config.id!r} at {config.base_url} "
            f"({type(exc).__name__}: {exc}){hint}",
            file=sys.stderr,
        )
        return 1
```

(`httpx.ConnectError` subclasses `TransportError`; `HTTPStatusError` does NOT,
so the existing mid-corpus 4xx/5xx propagation behavior — pinned by
`test_completed_runs_persist_when_later_task_fails` — is untouched.)

- [ ] **Step 5.4: Run — expect green**

Run: `uv run pytest tests/test_cli.py tests/runners -q`
Expected: all pass. The code-world E2E proves criterion 4 end to end: the
dataset row resolves the world, a mid-trajectory `run_tests` is fulfilled at
the real pytest edge (`ToolSuccess` with suite status `failed` — the visible
test in the fixture tree is red on the unrepaired `calc.py`), the oracle edge
grades it, and the streamed line round-trips through `_load_run_results`.
The connect-error test takes ~3 s (two real retry backoffs) and asserts exit
1 + provider id + base_url + the local hint + no traceback. Workspace CLI
tests pass unmodified (criterion 3's CLI-level guarantee).

- [ ] **Step 5.5: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/test_cli.py
git commit -m "feat(004): run-baseline resolves world per task; fail-loud provider reachability (crit. 4-5)"
```


### Task 6: fc-v1 classifier (`reports/classify.py`)

**Files:**
- Create: `src/agent_eval_lab/reports/classify.py`
- Test: `tests/reports/test_classify.py` (create), `tests/reports/test_classify_properties.py` (create)

- [ ] **Step 6.1: Write the failing row tests `tests/reports/test_classify.py`**

```python
"""fc-v1 mapping table: one dedicated test per row (item 004 criterion 7)."""

from typing import get_args

from agent_eval_lab.records.grade import FailureCategory, GradeResult, RunResult
from agent_eval_lab.records.trajectory import (
    NO_CHOICES_ERROR,
    ParseFailure,
    Trajectory,
    Usage,
)
from agent_eval_lab.reports.classify import (
    CLASSIFIER_VERSION,
    RunClassification,
    Subcategory,
    classify_run,
    first_execution_evidence,
)


def _run(
    *,
    passed=False,
    grader_id="execution",
    evidence=None,
    failure_reason=None,
    stop_reason="completed",
    parse_error=None,
) -> RunResult:
    """Synthetic RunResult mimicking the JSONL round-trip (plain dicts)."""
    return RunResult(
        task_id="cr-001",
        condition_id="deepseek:deepseek-v4-pro",
        run_index=0,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
            run_index=0,
            stop_reason=stop_reason,
            parse_failure=(
                None
                if parse_error is None
                else ParseFailure(raw="{}", error=parse_error)
            ),
            final_state={"files": {}},
        ),
        grade=GradeResult(
            grader_id=grader_id,
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence=evidence if evidence is not None else {},
            failure_reason=failure_reason,
        ),
    )


def _exec_run_evidence(status, counts=None):
    return {
        "execution": "run",
        "status": status,
        "exit_code": 1,
        "counts": counts or {"passed": 1, "failed": 2, "errors": 0, "skipped": 0},
        "tests": [],
        "stdout": "",
        "stderr": "",
        "execution_hash": "h",
        "displaced_paths": [],
    }


def _exec_error_evidence(kind, detail="boom"):
    return {
        "execution": "error",
        "execution_error": {"kind": kind, "detail": detail},
        "execution_hash": "h",
    }


def _is(c: RunClassification, category: str, subcategory) -> None:
    assert (c.category, c.subcategory) == (category, subcategory)
    assert c.classifier_version == CLASSIFIER_VERSION == "fc-v1"
    assert "\n" not in c.detail


# Row 1 — passed wins first, even over a recorded parse_failure (grill Q8).


def test_row_01_passed() -> None:
    _is(classify_run(_run(passed=True)), "passed", None)


def test_row_01_passed_wins_over_recorded_parse_failure() -> None:
    run = _run(passed=True, parse_error="unparseable", stop_reason="parse_failure")
    _is(classify_run(run), "passed", None)


# Rows 2-3 — parse failures split on the shared loop constant (grill Q3).


def test_row_02_empty_choices_parse_failure_is_harness() -> None:
    run = _run(parse_error=NO_CHOICES_ERROR, stop_reason="parse_failure")
    _is(classify_run(run), "harness_failure", "provider_response")


def test_row_03_any_other_parse_failure_is_agent() -> None:
    run = _run(
        parse_error="assistant message has neither content nor tool_calls",
        stop_reason="parse_failure",
    )
    _is(classify_run(run), "agent_failure", "malformed_reply")


# Rows 4-8 — execution not_run / error branch.


def test_row_04_not_run_missing_final_state_is_harness() -> None:
    ev = {"execution": "not_run", "reason": "missing_final_state"}
    _is(
        classify_run(_run(evidence=ev)),
        "harness_failure",
        "missing_final_state",
    )


def test_row_05_error_kind_harness_is_sandbox_fault() -> None:
    run = _run(evidence=_exec_error_evidence("harness"))
    _is(classify_run(run), "harness_failure", "sandbox_fault")


def test_row_06_error_kind_verdict_missing_is_harness() -> None:
    ev = {
        "execution": "error",
        "execution_error": {"kind": "verdict_missing", "execution_hash": "h"},
        "execution_hash": "h",
    }
    _is(classify_run(_run(evidence=ev)), "harness_failure", "verdict_missing")


def test_row_07_error_kind_tree_collision_is_agent() -> None:
    detail = "canonical-prefix collision: agent 'Tests/test_app.py' vs oracle"
    run = _run(evidence=_exec_error_evidence("tree_collision", detail))
    c = classify_run(run)
    _is(c, "agent_failure", "tree_collision")
    assert "Tests/test_app.py" in c.detail  # cites the colliding pair


def test_row_08_error_any_other_kind_is_foreign_verdict() -> None:
    # Grill Q1: a foreign value at a colliding hash carries its OWN kind
    # (e.g. a JudgeError's "transport"); the error branch closes by fallback.
    for kind in ("unknown", "transport", "parse", "weird-future-kind"):
        run = _run(evidence=_exec_error_evidence(kind))
        _is(classify_run(run), "harness_failure", "foreign_verdict")


def test_row_08_non_string_kind_is_foreign_verdict_not_a_crash() -> None:
    run = _run(evidence=_exec_error_evidence(["not", "hashable"]))
    _is(classify_run(run), "harness_failure", "foreign_verdict")


# Row 9 — empty oracle: the only mechanical post-conformance task defect.


def test_row_09_suite_no_tests_is_task_failure() -> None:
    ev = _exec_run_evidence("no_tests", {"passed": 0, "failed": 0})
    _is(classify_run(_run(evidence=ev)), "task_failure", "oracle_empty")


# Rows 10-11 — policy breaches from the grade taxonomy.


def test_row_10_forbidden_action_is_agent() -> None:
    run = _run(grader_id="trajectory", failure_reason="forbidden_action")
    _is(classify_run(run), "agent_failure", "forbidden_action")


def test_row_11_step_limit_exceeded_is_agent() -> None:
    run = _run(grader_id="trajectory", failure_reason="step_limit_exceeded")
    _is(classify_run(run), "agent_failure", "step_limit_exceeded")


# Row 12 — budget truncation outranks oracle statuses (grill Q13).


def test_row_12_max_steps_outranks_red_oracle() -> None:
    run = _run(evidence=_exec_run_evidence("failed"), stop_reason="max_steps")
    _is(classify_run(run), "agent_failure", "step_exhaustion")


# Rows 13-15 — oracle suite statuses on a full (untruncated) attempt.


def test_row_13_suite_timeout_is_oracle_timeout() -> None:
    ev = _exec_run_evidence("timeout", {"passed": 0, "failed": 0})
    _is(classify_run(_run(evidence=ev)), "agent_failure", "oracle_timeout")


def test_row_14_suite_failed_is_oracle_red() -> None:
    c = classify_run(_run(evidence=_exec_run_evidence("failed")))
    _is(c, "agent_failure", "oracle_red")
    assert "failed" in c.detail  # cites the suite counts/status


def test_row_15_suite_error_is_oracle_error() -> None:
    _is(
        classify_run(_run(evidence=_exec_run_evidence("error"))),
        "agent_failure",
        "oracle_error",
    )


# Row 16 — fallback: failed with no mapped discriminator.


def test_row_16_fallback_other_miss() -> None:
    run = _run(grader_id="final_state", evidence={"diff": []})
    _is(classify_run(run), "agent_failure", "other_miss")


# exec_ev walk: nested AllOf evidence, plain dicts (grill Q9).


def test_exec_evidence_found_through_nested_all_of_dicts() -> None:
    evidence = {
        "sub_results": [
            {"grader_id": "final_state", "passed": True, "evidence": {"diff": []}},
            {
                "grader_id": "all_of",
                "passed": False,
                "evidence": {
                    "sub_results": [
                        {
                            "grader_id": "execution",
                            "passed": False,
                            "evidence": _exec_run_evidence("failed"),
                        }
                    ]
                },
            },
        ]
    }
    run = _run(grader_id="all_of", evidence=evidence)
    _is(classify_run(run), "agent_failure", "oracle_red")


def test_first_execution_leg_wins_in_declared_order() -> None:
    evidence = {
        "sub_results": [
            {
                "grader_id": "execution",
                "passed": False,
                "evidence": _exec_run_evidence("failed"),
            },
            {
                "grader_id": "execution",
                "passed": False,
                "evidence": _exec_run_evidence("timeout"),
            },
        ]
    }
    found = first_execution_evidence(evidence, "all_of")
    assert found is not None and found["status"] == "failed"


def test_no_execution_leg_returns_none() -> None:
    assert first_execution_evidence({"diff": []}, "final_state") is None


# Criterion 8 — the grade-level taxonomy is untouched.


def test_failure_category_member_set_is_unchanged() -> None:
    assert set(get_args(FailureCategory)) == {
        "malformed_call",
        "schema_violation",
        "wrong_tool",
        "wrong_args",
        "missing_call",
        "extra_call",
        "order_mismatch",
        "forbidden_action",
        "step_limit_exceeded",
    }


def test_subcategory_vocabulary_is_closed_at_15() -> None:
    assert len(get_args(Subcategory)) == 15
```

- [ ] **Step 6.2: Write the failing property tests `tests/reports/test_classify_properties.py`**

```python
"""Hypothesis totality: fc-v1 never raises, always a closed category (crit. 6)."""

from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.reports.classify import RunClassification, classify_run

_CATEGORIES = {"passed", "task_failure", "agent_failure", "harness_failure"}

# Keys and atoms are biased toward the discriminators the table reads, so the
# search space is dense in realistic-but-adversarial evidence shapes — and a
# FOREIGN execution-error kind (grill Q1: "transport", "parse", arbitrary text)
# is generated explicitly alongside the named ones.
_keys = st.sampled_from(
    [
        "execution",
        "status",
        "execution_error",
        "kind",
        "detail",
        "sub_results",
        "grader_id",
        "evidence",
        "counts",
        "reason",
        "x",
    ]
) | st.text(max_size=8)

_atoms = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False)
    | st.text(max_size=12)
    | st.sampled_from(
        [
            "run",
            "not_run",
            "error",
            "passed",
            "failed",
            "timeout",
            "no_tests",
            "harness",
            "tree_collision",
            "verdict_missing",
            "unknown",
            "transport",
            "parse",
        ]
    )
)

_values = st.recursive(
    _atoms,
    lambda children: (
        st.lists(children, max_size=3) | st.dictionaries(_keys, children, max_size=4)
    ),
    max_leaves=16,
)

_evidence = st.dictionaries(_keys, _values, max_size=5)

_grades = st.builds(
    GradeResult,
    grader_id=st.sampled_from(
        ["execution", "all_of", "final_state", "trajectory", "output_match", "?"]
    ),
    passed=st.booleans(),
    score=st.sampled_from([0.0, 1.0]),
    evidence=_evidence,
    failure_reason=st.sampled_from(
        [
            None,
            "malformed_call",
            "schema_violation",
            "wrong_tool",
            "wrong_args",
            "missing_call",
            "extra_call",
            "order_mismatch",
            "forbidden_action",
            "step_limit_exceeded",
        ]
    ),
)

_parse_failures = st.none() | st.builds(
    ParseFailure,
    raw=st.just("{}"),
    error=st.text(max_size=40) | st.just("no choices in provider response"),
)

_trajectories = st.builds(
    Trajectory,
    turns=st.just(()),
    usage=st.just(Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0)),
    run_index=st.just(0),
    stop_reason=st.sampled_from(["completed", "max_steps", "parse_failure"]),
    parse_failure=_parse_failures,
    final_state=st.none() | st.just({"files": {}}),
)

_runs = st.builds(
    RunResult,
    task_id=st.just("t-1"),
    condition_id=st.just("p:m"),
    run_index=st.just(0),
    trajectory=_trajectories,
    grade=_grades,
)


@given(_runs)
def test_classify_run_is_total_and_closed(run: RunResult) -> None:
    classification = classify_run(run)
    assert isinstance(classification, RunClassification)
    assert classification.category in _CATEGORIES
    assert (classification.category == "passed") == (classification.subcategory is None)
    assert classification.classifier_version == "fc-v1"
    assert "\n" not in classification.detail


@given(_runs)
def test_classify_run_is_deterministic(run: RunResult) -> None:
    assert classify_run(run) == classify_run(run)
```

- [ ] **Step 6.3: Run them — expect red**

Run: `uv run pytest tests/reports/test_classify.py tests/reports/test_classify_properties.py -q`
Expected: collection errors — `ModuleNotFoundError: No module named 'agent_eval_lab.reports.classify'`.

- [ ] **Step 6.4: Write `src/agent_eval_lab/reports/classify.py`**

```python
"""Pure, total fc-v1 failure classification (ADR-0013): derived, never stored.

Maps every graded RunResult to exactly one of passed | task_failure |
agent_failure | harness_failure plus one closed subcategory, reading only the
mechanical discriminators already on the record: the trajectory's
parse_failure and stop_reason, the grade's failure_reason, and the first
execution leg's evidence — the plain dicts the JSONL round-trip yields, never
reconstructed dataclasses (grill Q9). The priority-ordered, first-match-wins
table is frozen with its version: changing any row's semantics mints fc-v2
and re-renders committed runs, never a model re-run.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.records.trajectory import NO_CHOICES_ERROR

CLASSIFIER_VERSION = "fc-v1"

Category = Literal["passed", "task_failure", "agent_failure", "harness_failure"]

# Closed at 15 values (item 004 resolved Q17); versioned with the classifier.
Subcategory = Literal[
    "provider_response",
    "malformed_reply",
    "missing_final_state",
    "sandbox_fault",
    "verdict_missing",
    "tree_collision",
    "foreign_verdict",
    "oracle_empty",
    "forbidden_action",
    "step_limit_exceeded",
    "step_exhaustion",
    "oracle_timeout",
    "oracle_red",
    "oracle_error",
    "other_miss",
]


@dataclass(frozen=True, kw_only=True)
class RunClassification:
    """One run's derived task/agent/harness interpretation (never a grade)."""

    category: Category
    subcategory: Subcategory | None  # None iff category == "passed"
    detail: str  # one-line evidence citation
    classifier_version: str = CLASSIFIER_VERSION


def _one_line(text: object, limit: int = 200) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _classification(
    category: Category, subcategory: Subcategory | None, detail: object
) -> RunClassification:
    return RunClassification(
        category=category, subcategory=subcategory, detail=_one_line(detail)
    )


def first_execution_evidence(
    evidence: Mapping[str, Any], grader_id: object
) -> Mapping[str, Any] | None:
    """The first execution leg's evidence, in declared order (grill Q9).

    Walks the plain dicts the JSONL round-trip yields: the grade's own
    evidence when it is the execution grader's, recursing `sub_results`
    entries (each a {"grader_id", "evidence", ...} dict) for all_of —
    including nested all_of, walked in declared order.
    """
    if grader_id == "execution":
        return evidence
    if grader_id != "all_of":
        return None
    subs = evidence.get("sub_results")
    if not isinstance(subs, Sequence) or isinstance(subs, (str, bytes)):
        return None
    for sub in subs:
        if not isinstance(sub, Mapping):
            continue
        sub_evidence = sub.get("evidence")
        if not isinstance(sub_evidence, Mapping):
            continue
        found = first_execution_evidence(sub_evidence, sub.get("grader_id"))
        if found is not None:
            return found
    return None


def classify_run(run: RunResult) -> RunClassification:
    """fc-v1: priority-ordered, first-match-wins, total — never raises."""
    if run.grade.passed:  # row 1 wins first, even over a recorded parse_failure
        return _classification("passed", None, "grade.passed")
    parse_failure = run.trajectory.parse_failure
    if parse_failure is not None:  # rows 2-3
        return _classify_parse_failure(parse_failure.error)
    exec_ev = first_execution_evidence(run.grade.evidence, run.grade.grader_id)
    early = _classify_execution_evidence(exec_ev)  # rows 4-9
    if early is not None:
        return early
    return _classify_grade_and_budget(run, exec_ev)  # rows 10-16


def _classify_parse_failure(error: str) -> RunClassification:
    if error == NO_CHOICES_ERROR:  # row 2: the provider delivered no completion
        return _classification(
            "harness_failure", "provider_response", f"parse_failure: {error}"
        )
    # row 3: the model emitted an unparseable payload (envelope was well-formed)
    return _classification(
        "agent_failure", "malformed_reply", f"parse_failure: {error}"
    )


_ERROR_KIND_ROWS: Mapping[str, tuple[Category, Subcategory]] = {
    "harness": ("harness_failure", "sandbox_fault"),  # row 5
    "verdict_missing": ("harness_failure", "verdict_missing"),  # row 6
    "tree_collision": ("agent_failure", "tree_collision"),  # row 7
}


def _classify_execution_evidence(
    exec_ev: Mapping[str, Any] | None,
) -> RunClassification | None:
    if exec_ev is None:
        return None
    execution = exec_ev.get("execution")
    if execution == "not_run":  # row 4: the runner always seeds final_state
        return _classification(
            "harness_failure",
            "missing_final_state",
            f"execution=not_run reason={exec_ev.get('reason')!r}",
        )
    if execution == "error":  # rows 5-8
        return _classify_execution_error(exec_ev)
    if execution == "run" and exec_ev.get("status") == "no_tests":  # row 9
        return _classification(
            "task_failure",
            "oracle_empty",
            f"oracle suite status=no_tests counts={exec_ev.get('counts')!r}",
        )
    return None


def _classify_execution_error(exec_ev: Mapping[str, Any]) -> RunClassification:
    error = exec_ev.get("execution_error")
    error_map = error if isinstance(error, Mapping) else {}
    kind = error_map.get("kind")
    # Row 8 closes the branch by construction (grill Q1): the kind is an OPEN
    # string, so any unrecognized (foreign) kind is a verdict-plumbing fault —
    # harness, never an agent miss. Non-string kinds fall through likewise.
    named = _ERROR_KIND_ROWS.get(kind) if isinstance(kind, str) else None
    category, subcategory = (
        named
        if named is not None
        else (
            "harness_failure",
            "foreign_verdict",
        )
    )
    return _classification(
        category,
        subcategory,
        f"execution_error kind={kind!r} detail={error_map.get('detail')!r}",
    )


_SUITE_STATUS_ROWS: Mapping[str, Subcategory] = {
    "timeout": "oracle_timeout",  # row 13
    "failed": "oracle_red",  # row 14
    "error": "oracle_error",  # row 15
}


def _classify_grade_and_budget(
    run: RunResult, exec_ev: Mapping[str, Any] | None
) -> RunClassification:
    reason = run.grade.failure_reason
    if reason == "forbidden_action":  # row 10
        return _classification(
            "agent_failure", "forbidden_action", "failure_reason=forbidden_action"
        )
    if reason == "step_limit_exceeded":  # row 11
        return _classification(
            "agent_failure",
            "step_limit_exceeded",
            "failure_reason=step_limit_exceeded",
        )
    if run.trajectory.stop_reason == "max_steps":  # row 12 outranks rows 13-15
        return _classification(
            "agent_failure", "step_exhaustion", "stop_reason=max_steps"
        )
    if exec_ev is not None and exec_ev.get("execution") == "run":  # rows 13-15
        status = exec_ev.get("status")
        named = _SUITE_STATUS_ROWS.get(status) if isinstance(status, str) else None
        if named is not None:
            return _classification(
                "agent_failure",
                named,
                f"oracle suite status={status} counts={exec_ev.get('counts')!r}",
            )
    return _classification(  # row 16: total without an unknown bucket
        "agent_failure",
        "other_miss",
        "failed with no mapped discriminator "
        f"(grader_id={run.grade.grader_id!r}, "
        f"stop_reason={run.trajectory.stop_reason!r})",
    )
```

- [ ] **Step 6.5: Run — expect green; verify the sha gate**

Run: `uv run pytest tests/reports/test_classify.py tests/reports/test_classify_properties.py -q`
Expected: `25 passed` — every criterion-7 row has a dedicated test (rows 7/8
in their post-grill order: named `tree_collision` precedes the any-other-kind
`foreign_verdict` fallback; row 8 also covers an UNHASHABLE kind — the
`.get(kind)` is guarded by `isinstance(kind, str)`, a totality requirement the
Hypothesis suite would otherwise find); `grade.passed` wins over a recorded
parse_failure (Q8); the exec-evidence walk recurses nested all_of dicts in
declared order (Q9); `FailureCategory`'s member set is pinned unchanged
(criterion 8) and `Subcategory` is closed at 15 (Q17).

Run: `shasum -a 256 src/agent_eval_lab/reports/classify.py`
Expected: `c21c04509884071f3f763bcb2a67e10e1b6fb4f11ec61f96dc7324ba35ad17e4`

- [ ] **Step 6.6: Commit**

```bash
git add src/agent_eval_lab/reports/classify.py tests/reports/test_classify.py tests/reports/test_classify_properties.py
git commit -m "feat(004): fc-v1 classifier — pure, total, priority-ordered RunClassification (ADR-0013)"
```


### Task 7: Final-report builder + renderer (`reports/final.py`)

Judgment call (pre-resolved): the discriminativeness rule is shared by
**importing** `reports/validation.py`'s `_build_condition` /
`_discriminativeness` / `_ci_str` / `_run_counts` (underscore-private, but the
repo's established convention — `metrics/reliability.py` imports
`agreement._percentile` with the same note). Zero edits to `validation.py`
means zero byte-drift risk on the frozen Weeks 3-4 surface; Task 9 pins it
with a golden sha anyway. The verdict's *prose* is re-rendered here from the
structured `Discriminativeness` fields because validation's `detail` strings
hardcode "v2"; the mechanical RULE (rungs, pairs, CIs) is byte-for-byte the
imported one.

**Files:**
- Create: `src/agent_eval_lab/reports/final.py`
- Test: `tests/reports/test_final.py` (create)

- [ ] **Step 7.1: Write the failing tests `tests/reports/test_final.py`**

```python
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
    assert "fc-v1" in md
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
        "## Failure classification (fc-v1)",
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
```

- [ ] **Step 7.2: Run them — expect red**

Run: `uv run pytest tests/reports/test_final.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'agent_eval_lab.reports.final'`.

- [ ] **Step 7.3: Write `src/agent_eval_lab/reports/final.py`**

```python
"""Pure final evaluation report (item 004 exit gate): build + render, no I/O.

Inputs: per-condition RunResult sequences loaded from committed runs JSONLs at
the edge, the tier sidecar, a capability map, the prices snapshot, and the
verbatim v1/v2 context text. Output: per-condition pass@1 / pass^k with seeded
cluster-bootstrap-by-task CIs, per-tier and per-capability pass^k, the fc-v1
task/agent/harness classification tables with deterministic exemplars, the
task-defect review queue, cost/latency from recorded usage, the Weeks 3-4
mechanical discriminativeness rule (shared by import from reports/validation —
the metrics/reliability `_percentile` precedent: import, don't extract, so the
frozen validation render cannot drift), pinned limitations, and roadmap
takeaways. No generation timestamp anywhere (grill Q5): time-like values
render only as recorded data, so build+render is a pure function of inputs.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from agent_eval_lab.metrics.agreement import BootstrapCI
from agent_eval_lab.metrics.cost import TokenPrice, total_cost_usd
from agent_eval_lab.metrics.reliability import (
    mean_latency_s,
    pass_at_1,
    pass_pow_k,
    pass_pow_k_bootstrap_ci,
    pass_pow_k_by_tier,
    token_totals,
)
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.reports.classify import (
    CLASSIFIER_VERSION,
    RunClassification,
    classify_run,
)
from agent_eval_lab.reports.validation import (
    TIER_ORDER,
    ConditionInput,
    Discriminativeness,
    _build_condition,
    _ci_str,
    _discriminativeness,
    _run_counts,
)

# Pinned by spec (criterion 16 section 12): excluded, not retried.
EXCLUDED_CONDITIONS: tuple[tuple[str, str], ...] = (
    (
        "openrouter:openai/gpt-5.5",
        "unreachable by network policy: direct access is region-blocked from "
        "this network and the datacenter-IP proxy route is ToS-blocked "
        "(docs/ROADMAP.md) — a network constraint, not a harness fault",
    ),
)


@dataclass(frozen=True, kw_only=True)
class FinalConditionInput:
    label: str
    condition_id: str | None  # None only when blocked with no records
    results: Sequence[RunResult] = field(default_factory=tuple)
    hosted: bool = False
    blocked_reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class ClassifiedExemplar:
    category: str
    subcategory: str
    task_id: str
    run_index: int
    detail: str


@dataclass(frozen=True, kw_only=True)
class FinalConditionReport:
    label: str
    condition_id: str | None
    hosted: bool
    status: str  # "complete" | "incomplete" | "blocked"
    n_tasks: int
    n_runs: int
    blocked_reason: str | None
    pass_at_1: float | None
    pass_pow_k: BootstrapCI | None
    pass_pow_k_by_tier: Mapping[str, float]
    pass_pow_k_by_capability: Mapping[str, float]
    classification_counts: Mapping[tuple[str, str], int]
    exemplars: tuple[ClassifiedExemplar, ...]
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None
    mean_latency_s: float | None
    incomplete_task_ids: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class TaskDefectCandidate:
    task_id: str
    n_conditions: int  # non-blocked conditions WITH records for the task
    n_runs: int  # total recorded runs over those conditions


@dataclass(frozen=True, kw_only=True)
class FinalReport:
    dataset_id: str
    k: int
    expected_n_tasks: int
    seed: int
    classifier_version: str
    prices_snapshot_date: str | None
    context_text: str
    conditions: tuple[FinalConditionReport, ...]
    task_defect_candidates: tuple[TaskDefectCandidate, ...]
    discriminativeness: Discriminativeness
    excluded_conditions: tuple[tuple[str, str], ...]


def _pass_pow_k_by_capability(
    results: Sequence[RunResult], capabilities: Mapping[str, str]
) -> dict[str, float]:
    by_capability: dict[str, list[RunResult]] = {}
    for run in results:
        capability = capabilities.get(run.task_id)
        if capability is None:
            raise ValueError(
                f"task {run.task_id!r} has no capability in the capability map"
            )
        by_capability.setdefault(capability, []).append(run)
    return {
        capability: pass_pow_k(runs)
        for capability, runs in sorted(by_capability.items())
    }


def _classified_failures(
    results: Sequence[RunResult],
) -> tuple[tuple[RunResult, RunClassification], ...]:
    return tuple((run, classify_run(run)) for run in results if not run.grade.passed)


def _classification_counts(
    classified: Sequence[tuple[RunResult, RunClassification]],
) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for _, classification in classified:
        key = (classification.category, classification.subcategory or "—")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _exemplars(
    classified: Sequence[tuple[RunResult, RunClassification]],
) -> tuple[ClassifiedExemplar, ...]:
    """One exemplar per category: lex-first task id, lowest run_index."""
    first: dict[str, tuple[RunResult, RunClassification]] = {}
    ordered = sorted(classified, key=lambda pair: (pair[0].task_id, pair[0].run_index))
    for run, classification in ordered:
        first.setdefault(classification.category, (run, classification))
    return tuple(
        ClassifiedExemplar(
            category=category,
            subcategory=first[category][1].subcategory or "—",
            task_id=first[category][0].task_id,
            run_index=first[category][0].run_index,
            detail=first[category][1].detail,
        )
        for category in sorted(first)
    )


def _blocked_condition(cond: FinalConditionInput) -> FinalConditionReport:
    return FinalConditionReport(
        label=cond.label,
        condition_id=cond.condition_id,
        hosted=cond.hosted,
        status="blocked",
        n_tasks=0,
        n_runs=0,
        blocked_reason=cond.blocked_reason or "no reachable records",
        pass_at_1=None,
        pass_pow_k=None,
        pass_pow_k_by_tier={},
        pass_pow_k_by_capability={},
        classification_counts={},
        exemplars=(),
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=None,
        mean_latency_s=None,
        incomplete_task_ids=(),
    )


def _build_final_condition(
    cond: FinalConditionInput,
    *,
    tiers: Mapping[str, str],
    capabilities: Mapping[str, str],
    k: int,
    expected_n_tasks: int,
    seed: int,
    n_resamples: int,
    alpha: float,
    prices: Mapping[str, TokenPrice],
) -> FinalConditionReport:
    if cond.blocked_reason is not None or not cond.results:
        return _blocked_condition(cond)
    counts = _run_counts(cond.results)
    deficit_ids = tuple(sorted(tid for tid, n in counts.items() if n < k))
    deficit = set(deficit_ids)
    complete = tuple(r for r in cond.results if r.task_id not in deficit)
    n_tasks = len({r.task_id for r in complete})
    status = (
        "complete" if n_tasks == expected_n_tasks and not deficit_ids else "incomplete"
    )
    classified = _classified_failures(cond.results)
    price = prices.get(cond.condition_id) if cond.condition_id else None
    prompt_tokens, completion_tokens = token_totals(cond.results)
    return FinalConditionReport(
        label=cond.label,
        condition_id=cond.condition_id,
        hosted=cond.hosted,
        status=status,
        n_tasks=n_tasks,
        n_runs=len(cond.results),
        blocked_reason=None,
        pass_at_1=pass_at_1(cond.results),
        pass_pow_k=(
            pass_pow_k_bootstrap_ci(
                complete, n_resamples=n_resamples, seed=seed, alpha=alpha
            )
            if complete
            else None
        ),
        pass_pow_k_by_tier=pass_pow_k_by_tier(complete, tiers) if complete else {},
        pass_pow_k_by_capability=(
            _pass_pow_k_by_capability(complete, capabilities) if complete else {}
        ),
        classification_counts=_classification_counts(classified),
        exemplars=_exemplars(classified),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=(
            total_cost_usd(cond.results, price=price) if price is not None else None
        ),
        mean_latency_s=mean_latency_s(cond.results),
        incomplete_task_ids=deficit_ids,
    )


def _task_defect_candidates(
    conditions: Sequence[FinalConditionInput],
) -> tuple[TaskDefectCandidate, ...]:
    """Tasks failing ALL recorded runs on EVERY non-blocked condition with
    records for them (grill Q10): a condition with no records for a task
    contributes nothing (vacuous); blocked conditions are excluded entirely.
    Flagged for human review, never auto-classified (ADR-0013)."""
    live = [c for c in conditions if c.blocked_reason is None and c.results]
    per_task: dict[str, dict[str, list[bool]]] = {}
    for cond in live:
        for run in cond.results:
            per_task.setdefault(run.task_id, {}).setdefault(cond.label, []).append(
                run.grade.passed
            )
    return tuple(
        TaskDefectCandidate(
            task_id=task_id,
            n_conditions=len(per_task[task_id]),
            n_runs=sum(len(passes) for passes in per_task[task_id].values()),
        )
        for task_id in sorted(per_task)
        if not any(any(passes) for passes in per_task[task_id].values())
    )


def _shared_discriminativeness(
    conditions: Sequence[FinalConditionInput],
    *,
    tiers: Mapping[str, str],
    capabilities: Mapping[str, str],
    k: int,
    expected_n_tasks: int,
    seed: int,
    n_resamples: int,
    alpha: float,
) -> Discriminativeness:
    """The Weeks 3-4 mechanical rule, reused by import (criterion 17)."""
    val_inputs = tuple(
        ConditionInput(
            label=c.label,
            results=tuple(c.results),
            hosted=c.hosted,
            blocked_reason=c.blocked_reason,
        )
        for c in conditions
    )
    built = tuple(
        _build_condition(
            ci,
            tiers=tiers,
            capabilities=capabilities,
            k=k,
            expected_n_tasks=expected_n_tasks,
            seed=seed,
            n_resamples=n_resamples,
            alpha=alpha,
        )
        for ci in val_inputs
    )
    return _discriminativeness(
        built,
        raw={c.label: c for c in val_inputs},
        seed=seed,
        n_resamples=n_resamples,
        alpha=alpha,
    )


def build_final_report(
    *,
    conditions: Sequence[FinalConditionInput],
    dataset_id: str,
    tiers: Mapping[str, str],
    capabilities: Mapping[str, str],
    k: int,
    expected_n_tasks: int,
    seed: int,
    n_resamples: int,
    alpha: float,
    prices: Mapping[str, TokenPrice],
    prices_snapshot_date: str | None,
    context_text: str,
) -> FinalReport:
    built = tuple(
        _build_final_condition(
            c,
            tiers=tiers,
            capabilities=capabilities,
            k=k,
            expected_n_tasks=expected_n_tasks,
            seed=seed,
            n_resamples=n_resamples,
            alpha=alpha,
            prices=prices,
        )
        for c in conditions
    )
    return FinalReport(
        dataset_id=dataset_id,
        k=k,
        expected_n_tasks=expected_n_tasks,
        seed=seed,
        classifier_version=CLASSIFIER_VERSION,
        prices_snapshot_date=prices_snapshot_date,
        context_text=context_text,
        conditions=built,
        task_defect_candidates=_task_defect_candidates(conditions),
        discriminativeness=_shared_discriminativeness(
            conditions,
            tiers=tiers,
            capabilities=capabilities,
            k=k,
            expected_n_tasks=expected_n_tasks,
            seed=seed,
            n_resamples=n_resamples,
            alpha=alpha,
        ),
        excluded_conditions=EXCLUDED_CONDITIONS,
    )


# ── Renderer (criterion 16's twelve sections, in order, plus the footer) ─────

_CLASSIFICATION_FOOTNOTES = (
    "`tree_collision` → agent_failure: oracle paths are disjoint from every "
    "initial-tree path (ADR-0012's conformance contract) and code-world has no "
    "delete tool, so a canonical-prefix collision can only be minted by the "
    "run's own write; exact-path equality is displacement, never collision "
    "(ADR-0010). Conditional on the conformance contract, which holds for the "
    "code-repair lineage.",
    "`oracle_empty` → task_failure: conformance proves every shipped oracle "
    "collects ≥1 test and the overlay always contributes the oracle files (a "
    "collection-breaking agent write yields suite status `error`, pytest exit "
    "2, never `no_tests`), so an empty oracle at grading time indicts the "
    "task data.",
    "`missing_final_state` → harness_failure: the runner always seeds "
    "final_state from initial_state, so its absence is a wiring defect.",
    "`step_exhaustion` outranks the oracle statuses: a budget-truncated "
    "attempt's red oracle is an artifact of the truncation, and the budget is "
    "data-validated (per-task metadata.max_steps via effective_max_steps, "
    "conformance-floored) — exhaustion is the agent's spend, not harness "
    "starvation.",
    "`malformed_reply` stays agent-side: message-level emptiness (assistant "
    "message with neither content nor tool_calls) means the provider envelope "
    "was well-formed and the model's own message was unparseable; only the "
    "empty-choices envelope (`provider_response`) is the harness's.",
    "`foreign_verdict` is the error-branch fallback: the evidence kind is an "
    "open string, so any unrecognized kind files as a harness verdict-plumbing "
    "fault, never an agent miss (grill Q1).",
)

_PINNED_LIMITATIONS = (
    "ADR-0010 residual trust boundary: the oracle suite imports agent-authored "
    "modules in-process, so import-time code in graded modules runs inside the "
    "sandbox process.",
    "Sandbox isolation is temp-dir-and-convention, not kernel-level: no "
    "containers, no per-test process isolation (001/002 non-goals).",
    "n=15 tasks, dev split only: intervals are wide and per-tier / "
    "per-capability cells are tiny.",
    "graders/policy.py dotted-path false-allow residual: an agent minting a "
    "fresh extension path at run time (e.g. writing `app.py.bak` under an "
    "`app.py` allowlist) is silently *passed* — a missed-detection bias the "
    "per-run classifier cannot see (003-spec criterion 16).",
    "pytest_edge cleanup is `shutil.rmtree(ignore_errors=True)`, so a sandbox "
    "dir can leak silently; a disk-full OSError mid-materialize is captured as "
    'an ExecutionError(kind="harness") by the oracle edge — the worked '
    "example of a `sandbox_fault` harness failure (001-review).",
    "Hosted providers are not greedy-deterministic at temperature 0; "
    "run-to-run variation is measured by k=3 + pass^3, never claimed away.",
    "`openrouter:gpt-5.5` is unreachable from this network (region / "
    "datacenter-IP ToS policy) — a network constraint, not a harness fault.",
)

_ROADMAP_TAKEAWAYS = (
    "The fc-v1 (category, subcategory) counts are the direct input to the "
    "Weeks 9-10 failure-mining work; downstream joins on "
    "(classifier_version, category, subcategory) (ADR-0013).",
    "Task-defect candidates are review-queue input, never auto-reclassified; "
    "an adjudicated defect ships as a future dataset version, never an edit "
    "(append-only).",
    "The per-tier and per-capability gradients feed the Weeks 9-10 hardness "
    "levers recorded in the Weeks 3-4 takeaways.",
    "The committed runs JSONLs embed agent solution trees and oracle output, "
    "so they join the Weeks 9-10 never-train manifest beside the "
    "review-fixtures sidecar.",
)

_RUN_DIR = "docs/2026-06-11-coding-agent-eval"
_REGEN_RUNS = (
    ("C1", "deepseek:deepseek-v4-pro", "runs-deepseek-deepseek-v4-pro.jsonl"),
    ("C2", "glm:Pro/zai-org/GLM-5.1", "runs-glm-Pro-zai-org-GLM-5.1.jsonl"),
    ("C3", "minimax:MiniMax-M3", "runs-minimax-MiniMax-M3.jsonl"),
    ("C4", "local:Qwen/Qwen3-8B", "runs-local-Qwen-Qwen3-8B.jsonl"),
)
# Static text by spec (criterion 16): the canonical regeneration command over
# the committed artifact paths — never derived from this build's inputs.
_REGENERATION_COMMAND = "\n".join(
    (
        "uv run python -m agent_eval_lab.cli report-final \\",
        "  --runs \\",
        *(
            f"    {label}={condition}={_RUN_DIR}/runs/{filename} \\"
            for label, condition, filename in _REGEN_RUNS
        ),
        "  --dataset examples/datasets/code_repair_v1.jsonl \\",
        "  --tiers examples/datasets/code_repair_v1_tiers.json \\",
        f"  --prices {_RUN_DIR}/prices.json \\",
        f"  --context-file {_RUN_DIR}/v2-context.md \\",
        "  --k 3 --expected-n-tasks 15 --seed 20260610 "
        "--n-resamples 2000 --alpha 0.05 \\",
        f"  --out {_RUN_DIR}/final-evaluation-report.md",
    )
)


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _header_lines(report: FinalReport) -> list[str]:
    condition_cells = ", ".join(
        f"{c.label}={c.condition_id or 'unknown'} "
        f"({'hosted' if c.hosted else 'local'}, {c.status})"
        for c in report.conditions
    )
    return [
        "# Final evaluation report — coding-agent-eval (Weeks 5-6)",
        "",
        f"- Dataset: `{report.dataset_id}` · n={report.expected_n_tasks} tasks "
        f"· k={report.k} · bootstrap seed={report.seed} "
        f"· classifier {report.classifier_version}",
        f"- Conditions: {condition_cells}",
        "- Temperature 0.0 was *requested*; no seed is sent and hosted providers "
        "are not greedy-deterministic at temp 0, so residual run-to-run variation "
        "is exactly what k=3 + pass^3 measures. The only seeded, reproducible knob "
        "is the bootstrap RNG.",
        "",
    ]


def _reliability_lines(report: FinalReport) -> list[str]:
    lines = [
        "## Per-condition reliability",
        "",
        "| condition | status | tasks | runs | pass@1 | pass^3 [95% CI] |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in report.conditions:
        if c.status == "blocked":
            lines.append(
                f"| {c.label} | blocked | 0 | 0 | — | — (reason: {c.blocked_reason}) |"
            )
        else:
            lines.append(
                f"| {c.label} | {c.status} | {c.n_tasks} | {c.n_runs} "
                f"| {_fmt(c.pass_at_1)} | {_ci_str(c.pass_pow_k)} |"
            )
    for c in report.conditions:
        if c.status == "blocked" or not c.incomplete_task_ids:
            continue
        ids = ", ".join(c.incomplete_task_ids)
        lines.append(
            f"  - {c.label}: excluded (incomplete, <k runs): "
            f"{len(c.incomplete_task_ids)} — {ids} "
            f"(pass@1 over observed runs; excluded from pass^k)"
        )
    return lines + [""]


def _axis_table_lines(
    report: FinalReport, *, title: str, axis: str, columns: tuple[str, ...]
) -> list[str]:
    lines = [
        title,
        "",
        "| condition | " + " | ".join(columns) + " |",
        "| --- | " + " | ".join("---" for _ in columns) + " |",
    ]
    for c in report.conditions:
        if c.status == "blocked":
            continue
        values = getattr(c, axis)
        cells = [f"{values[col]:.3f}" if col in values else "—" for col in columns]
        lines.append(f"| {c.label} | " + " | ".join(cells) + " |")
    return lines + [""]


def _classification_lines(report: FinalReport) -> list[str]:
    lines = [
        "## Failure classification (fc-v1)",
        "",
        "Derived at report time from the recorded mechanical discriminators; "
        "never stored on any record (ADR-0013).",
        "",
    ]
    for c in report.conditions:
        if c.status == "blocked":
            continue
        lines += [
            f"### {c.label} ({c.condition_id})",
            "",
            "| category | subcategory | count |",
            "| --- | --- | --- |",
        ]
        if not c.classification_counts:
            lines.append("| (no failures) | — | 0 |")
        else:
            for (category, subcategory), n in sorted(
                c.classification_counts.items(), key=lambda kv: (-kv[1], kv[0])
            ):
                lines.append(f"| {category} | {subcategory} | {n} |")
        lines.append("")
        if c.exemplars:
            lines.append(
                "Exemplars (deterministic: lex-first task id, lowest run_index):"
            )
            lines += [
                f"- **{e.category}/{e.subcategory}** — task `{e.task_id}`, "
                f"run {e.run_index}: {e.detail}"
                for e in c.exemplars
            ]
            lines.append("")
    lines += ["Judgment-row footnotes:", ""]
    lines += [f"- {note}" for note in _CLASSIFICATION_FOOTNOTES]
    return lines + [""]


def _defect_queue_lines(report: FinalReport) -> list[str]:
    lines = [
        "## Task-defect candidates",
        "",
        "Task ids failing all recorded runs on every non-blocked condition with "
        "records for them — *flagged for human review*, never auto-classified: "
        "conformance already proves solvability, oracle breadth, and symptom "
        'reality, so unanimity defaults to "hard, not defective" pending '
        "adjudication.",
        "",
    ]
    if not report.task_defect_candidates:
        lines.append("none")
    else:
        lines += [
            "| task | conditions with records | total runs (all failing) |",
            "| --- | --- | --- |",
        ]
        lines += [
            f"| {c.task_id} | {c.n_conditions} | {c.n_runs} |"
            for c in report.task_defect_candidates
        ]
    return lines + [""]


def _cost_lines(report: FinalReport) -> list[str]:
    snapshot = report.prices_snapshot_date or "unspecified"
    lines = [
        "## Cost and latency",
        "",
        f"Prices snapshot: {snapshot} (committed prices.json); conditions "
        "absent from the snapshot render as not computed. Latency is summed "
        "from recorded per-run `usage.latency_s`.",
        "",
        "| condition | prompt tokens | completion tokens | cost (USD) "
        "| mean run latency (s) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in report.conditions:
        if c.status == "blocked":
            continue
        cost = "not computed" if c.cost_usd is None else f"{c.cost_usd:.4f}"
        latency = "—" if c.mean_latency_s is None else f"{c.mean_latency_s:.2f}"
        lines.append(
            f"| {c.label} | {c.prompt_tokens} | {c.completion_tokens} "
            f"| {cost} | {latency} |"
        )
    return lines + [""]


def _context_lines(report: FinalReport) -> list[str]:
    return [
        "## Context: prior baselines (workspace_tool_use v1/v2)",
        "",
        report.context_text.rstrip("\n"),
        "",
        "Cross-dataset numbers are *context*, never a paired statistic: the "
        "task universes differ, so no CI is computed across them.",
        "",
    ]


def _discriminativeness_lines(report: FinalReport) -> list[str]:
    d = report.discriminativeness
    lines = [
        "## Discriminativeness verdict",
        "",
        f"- Rung met: **{d.rung}** (weak={d.weak_met}, strong={d.strong_met}) — "
        "the Weeks 3-4 mechanical rule, reused unchanged.",
    ]
    if d.strong_pair is not None:
        lines.append(
            f"- Separated hosted pair: {d.strong_pair[0]} vs {d.strong_pair[1]} "
            f"— Δ pass^3 {_ci_str(d.strong_pair_ci)} (CI excludes 0)."
        )
    if d.monotone_conditions:
        names = ", ".join(d.monotone_conditions)
        lines.append(
            "- Non-trivial monotone tier gradient (T1≥T2≥T3≥T4 with ≥1 strict "
            f"decrease): {names}."
        )
    for a_label, b_label, ci in d.near_miss_pairs:
        if ci.point == 0.0 and ci.lo == 0.0 and ci.hi == 0.0:
            lines.append(
                f"- No observed difference: {a_label} vs {b_label} — both "
                f"conditions identical on this dataset (Δ {ci.point:.3f})."
            )
        else:
            lines.append(
                f"- Near-miss: {a_label} vs {b_label} — Δ pass^3 {_ci_str(ci)} "
                f"(CI touches 0; not decisive at n={report.expected_n_tasks})."
            )
    for a_label, b_label in d.skipped_pairs:
        lines.append(
            f"- Skipped pair: {a_label} vs {b_label} — universe mismatch "
            f"(task-id sets differ; paired CI requires identical universe)."
        )
    lines.append(
        f"- n={report.expected_n_tasks} honesty: intervals are wide; absence of "
        "a detectable separation is not evidence of no separation."
    )
    return lines + [""]


def _limitations_lines(report: FinalReport) -> list[str]:
    lines = ["## Known limitations", ""]
    lines += [f"- {limitation}" for limitation in _PINNED_LIMITATIONS]
    for c in report.conditions:
        if c.status == "blocked":
            condition_name = c.condition_id or "condition id unknown — no records"
            lines.append(
                f"- Condition {c.label} ({condition_name}) is blocked: "
                f"{c.blocked_reason}; its rows render as blocked and no "
                "numbers are fabricated."
            )
        elif c.status == "incomplete":
            lines.append(
                f"- Condition {c.label} is incomplete "
                f"({c.n_tasks}/{report.expected_n_tasks} tasks at full k); "
                "pass^k covers only its complete tasks."
            )
    return lines + [""]


def _excluded_lines(report: FinalReport) -> list[str]:
    lines = ["## Excluded conditions", ""]
    lines += [
        f"- `{condition_id}` — {reason}"
        for condition_id, reason in report.excluded_conditions
    ]
    return lines + [""]


def _footer_lines() -> list[str]:
    return [
        "---",
        "",
        "Regenerate byte-identically from the committed artifacts with:",
        "",
        "```",
        _REGENERATION_COMMAND,
        "```",
    ]


def render_markdown(report: FinalReport) -> str:
    capabilities = tuple(
        sorted(
            {
                capability
                for c in report.conditions
                for capability in c.pass_pow_k_by_capability
            }
        )
    )
    lines = (
        _header_lines(report)
        + _reliability_lines(report)
        + _axis_table_lines(
            report,
            title="## Per-tier pass^3",
            axis="pass_pow_k_by_tier",
            columns=TIER_ORDER,
        )
        + _axis_table_lines(
            report,
            title="## Per-capability pass^3",
            axis="pass_pow_k_by_capability",
            columns=capabilities,
        )
        + _classification_lines(report)
        + _defect_queue_lines(report)
        + _cost_lines(report)
        + _context_lines(report)
        + _discriminativeness_lines(report)
        + _limitations_lines(report)
        + ["## Roadmap takeaways", ""]
        + [f"- {takeaway}" for takeaway in _ROADMAP_TAKEAWAYS]
        + [""]
        + _excluded_lines(report)
        + _footer_lines()
    )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 7.4: Run — expect green; verify the sha gate**

Run: `uv run pytest tests/reports/test_final.py tests/reports/test_validation.py -q`
Expected: `16 passed` for final (build+render byte-determinism; blocked
condition renders with NO fabricated numbers; the defect-queue quartet —
unanimous-fail, one-condition-passes, blocked-excluded, missing-records-vacuous
(Q10); priced vs `not computed` cost — the fixture's measured cost is
294e-6 USD; verbatim context under the exact heading; criterion 16's section
ORDER asserted by index; judgment footnotes; no-timestamp guard where the only
date is the prices snapshot) plus the untouched validation tests.

Run: `shasum -a 256 src/agent_eval_lab/reports/final.py`
Expected: `7a380b9aaf110fee89ff812771f399d405c40e486b7cb8b5d898e294a9a8eda3`

- [ ] **Step 7.5: Commit**

```bash
git add src/agent_eval_lab/reports/final.py tests/reports/test_final.py
git commit -m "feat(004): pure final-report builder + renderer — classification, defect queue, shared discriminativeness (crit. 9, 14, 16-18)"
```


### Task 8: `report-final` CLI command

**Files:**
- Modify: `src/agent_eval_lab/cli.py`
- Test: `tests/test_cli.py` (append)

- [ ] **Step 8.1: Append the failing tests to `tests/test_cli.py`**

Append exactly this block at the end of the file:

```python
# ── Item 004: report-final (criteria 15, 19, 20) ─────────────────────────────


def _final_report_inputs(tmp_path: Path):
    tiers = _write_tiers(tmp_path / "tiers.json", {"cr-001": "T1", "cr-002": "T3"})
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps(
            {
                "snapshot_date": "2026-06-11",
                "prices": {
                    "deepseek:deepseek-v4-pro": {
                        "input_per_mtok": 0.27,
                        "output_per_mtok": 1.1,
                    }
                },
            }
        )
        + "\n"
    )
    context = tmp_path / "v2-context.md"
    context.write_text("v1/v2 workspace baselines: see committed reports.\n")
    runs = [
        *[_mk_run("deepseek:deepseek-v4-pro", "cr-001", i, True) for i in range(3)],
        *[
            _mk_run("deepseek:deepseek-v4-pro", "cr-002", i, False, "wrong_args")
            for i in range(3)
        ],
    ]
    jsonl = _write_runs_jsonl(tmp_path / "runs-deepseek-deepseek-v4-pro.jsonl", runs)
    return tiers, prices, context, jsonl


def _report_final_args(tmp_path, tiers, prices, context, jsonl, out) -> list[str]:
    return [
        "report-final",
        "--runs",
        f"C1=deepseek:deepseek-v4-pro={jsonl}",
        f"C4=local:Qwen/Qwen3-8B={tmp_path / 'missing-local.jsonl'}",
        "--dataset",
        "examples/datasets/code_repair_v1.jsonl",
        "--tiers",
        str(tiers),
        "--prices",
        str(prices),
        "--context-file",
        str(context),
        "--k",
        "3",
        "--expected-n-tasks",
        "15",
        "--n-resamples",
        "200",
        "--out",
        str(out),
    ]


def test_report_final_renders_byte_identically_across_invocations(
    tmp_path: Path,
) -> None:
    tiers, prices, context, jsonl = _final_report_inputs(tmp_path)
    out_a, out_b = tmp_path / "final-a.md", tmp_path / "final-b.md"

    assert main(_report_final_args(tmp_path, tiers, prices, context, jsonl, out_a)) == 0
    assert main(_report_final_args(tmp_path, tiers, prices, context, jsonl, out_b)) == 0

    a, b = out_a.read_bytes(), out_b.read_bytes()
    assert a == b
    md = a.decode()
    assert "# Final evaluation report" in md
    assert "fc-v1" in md
    assert "| C4 | blocked |" in md  # zero-record condition: blocked, no numbers
    assert "incomplete" in md  # 2 of 15 expected tasks present


def test_report_final_rejects_heterogeneous_runs_file(tmp_path: Path, capsys) -> None:
    tiers, prices, context, _ = _final_report_inputs(tmp_path)
    mixed = _write_runs_jsonl(
        tmp_path / "mixed.jsonl",
        [
            _mk_run("deepseek:deepseek-v4-pro", "cr-001", 0, True),
            _mk_run("glm:Pro/zai-org/GLM-5.1", "cr-001", 1, True),
        ],
    )
    out = tmp_path / "final.md"

    exit_code = main(_report_final_args(tmp_path, tiers, prices, context, mixed, out))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "heterogeneous" in err
    assert "Traceback" not in err
    assert not out.exists()


def test_report_final_rejects_condition_segment_mismatch(
    tmp_path: Path, capsys
) -> None:
    tiers, prices, context, jsonl = _final_report_inputs(tmp_path)
    out = tmp_path / "final.md"
    args = _report_final_args(tmp_path, tiers, prices, context, jsonl, out)
    args[2] = f"C1=minimax:MiniMax-M3={jsonl}"  # segment contradicts the records

    exit_code = main(args)

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "minimax:MiniMax-M3" in err and "deepseek:deepseek-v4-pro" in err
    assert not out.exists()
```

- [ ] **Step 8.2: Run them — expect red**

Run: `uv run pytest tests/test_cli.py -q`
Expected: 3 failed — `SystemExit: 2` (argparse: `invalid choice: 'report-final'`).

- [ ] **Step 8.3: Add the command to `src/agent_eval_lab/cli.py`**

Add the two `reports.final` import lines from Task 5 Step 5.3 (after the
`reports.comparison` imports):

```python
from agent_eval_lab.reports.final import FinalConditionInput, build_final_report
from agent_eval_lab.reports.final import render_markdown as render_final
```

Insert these functions immediately ABOVE `def _run_compare_configs(`:

```python
def _parse_runs_spec_with_condition(spec: str) -> tuple[str, str | None, Path]:
    """'LABEL=condition_id=path' or 'LABEL=path' -> (label, condition_id, path).

    report-final makes the middle segment LIVE (grill Q11), unlike
    report-validation's _parse_runs_spec, which discards it. The same
    left-then-right split keeps any interior '=' inside the condition_id.
    """
    label_rest = spec.split("=", 1)
    if len(label_rest) < 2:
        raise ValueError(f"bad --runs spec {spec!r}; want LABEL=condition_id=path")
    label, rest = label_rest
    cond_or_path, *tail = rest.rsplit("=", 1)
    if tail:
        return label, cond_or_path, Path(tail[0])
    return label, None, Path(cond_or_path)


def _derived_condition_id(results: Sequence[RunResult], path: Path) -> str:
    """The condition_id every record in a runs file agrees on (grill Q11)."""
    ids = sorted({run.condition_id for run in results})
    if len(ids) > 1:
        raise ValueError(f"heterogeneous condition_id in {path}: {ids}")
    return ids[0]


def _load_prices(path: Path) -> tuple[str | None, dict[str, TokenPrice]]:
    """prices.json: {"snapshot_date", "prices": {condition_id: {input_per_mtok,
    output_per_mtok}}} — the pinned shape (grill Q11)."""
    data = json.loads(path.read_text())
    prices = {
        condition: TokenPrice(
            input_per_mtok=entry["input_per_mtok"],
            output_per_mtok=entry["output_per_mtok"],
        )
        for condition, entry in data.get("prices", {}).items()
    }
    return data.get("snapshot_date"), prices


def _final_condition_input(spec: str) -> FinalConditionInput:
    label, segment, path = _parse_runs_spec_with_condition(spec)
    results = _load_run_results(path) if path.exists() else []
    derived = _derived_condition_id(results, path) if results else None
    if derived is not None and segment is not None and derived != segment:
        raise ValueError(
            f"--runs {label}: condition_id segment {segment!r} does not match "
            f"the records' {derived!r} in {path}"
        )
    return FinalConditionInput(
        label=label,
        condition_id=derived or segment,
        results=results,
        hosted=_hosted_label(label),
        blocked_reason=None if results else "no reachable records",
    )


def _run_report_final(args: argparse.Namespace) -> int:
    tiers = json.loads(args.tiers.read_text())
    caps = _capability_map(args.dataset)
    snapshot_date, prices = _load_prices(args.prices)
    try:
        conditions = tuple(_final_condition_input(spec) for spec in args.runs)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    report = build_final_report(
        conditions=conditions,
        dataset_id=args.dataset.stem,
        tiers=tiers,
        capabilities=caps,
        k=args.k,
        expected_n_tasks=args.expected_n_tasks,
        seed=args.seed,
        n_resamples=args.n_resamples,
        alpha=args.alpha,
        prices=prices,
        prices_snapshot_date=snapshot_date,
        context_text=args.context_file.read_text(),
    )
    _atomic_write(args.out, render_final(report))
    print(args.out)
    return 0
```

In `_build_parser`, insert this block immediately ABOVE the
`cc = subparsers.add_parser("compare-configs", ...)` block:

```python
    rf = subparsers.add_parser(
        "report-final",
        help="rebuild the final evaluation report from JSONL (pure, replay-only)",
    )
    rf.add_argument(
        "--runs",
        required=True,
        nargs="+",
        help="one per condition: LABEL=condition_id=path/to/runs-*.jsonl "
        "(the condition_id segment is cross-checked against the records)",
    )
    rf.add_argument("--dataset", required=True, type=Path)
    rf.add_argument("--tiers", required=True, type=Path)
    rf.add_argument("--prices", required=True, type=Path)
    rf.add_argument("--context-file", required=True, type=Path)
    rf.add_argument("--k", type=int, default=3)
    rf.add_argument("--expected-n-tasks", type=int, default=15)
    rf.add_argument("--out", required=True, type=Path)
    rf.add_argument("--seed", type=int, default=20260610)
    rf.add_argument("--n-resamples", type=int, default=2000)
    rf.add_argument("--alpha", type=float, default=0.05)
```

In `main`, replace:

```python
    if args.command == "report-validation":
        return _run_report_validation(args)
```

with:

```python
    if args.command == "report-validation":
        return _run_report_validation(args)
    if args.command == "report-final":
        return _run_report_final(args)
```

- [ ] **Step 8.4: Run — expect green**

Run: `uv run pytest tests/test_cli.py -q`
Expected: all pass. The three new tests pin grill Q11: byte-identical output
across two invocations (criterion 19 at the CLI level, with one blocked
condition rendering `| C4 | blocked |` and the 2-of-15-task condition
rendering `incomplete`); a heterogeneous runs file is a loud exit-1 naming
both ids; a `--runs` segment contradicting the records' derived condition_id
is a loud exit-1 naming both — and `_atomic_write` means no partial report
file exists after either failure.

- [ ] **Step 8.5: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/test_cli.py
git commit -m "feat(004): report-final command — derived condition ids, prices join, atomic pure replay (crit. 15, 19)"
```


### Task 9: Regression pins — validation golden sha + committed-runs gate

These two are deliberate green-on-arrival pins, not red-green features: one
freezes EXISTING behavior against future drift (grill Q12), the other gates
artifacts that do not exist until Part B (it must skip today).

**Files:**
- Test: `tests/reports/test_validation.py` (append)
- Create: `tests/test_committed_runs.py`

- [ ] **Step 9.1: Append the golden-sha pin to `tests/reports/test_validation.py`**

Append exactly this block at the end of the file:

```python
def test_render_golden_sha_pins_the_frozen_validation_surface() -> None:
    """Item 004 grill Q12: the committed Weeks 3-4 reports are regenerable
    artifacts, and reports/final.py now imports this module's rule — any future
    sharing/extraction must keep this render byte-identical. The sha256 pins
    the exact bytes over a fixed, fully deterministic fixture."""
    import hashlib

    runs_a = (
        *_all("C1", "ws2-001", 3, True),
        *_all("C1", "ws2-018", 3, False, "wrong_args"),
        *_all("C1", "ws2-040", 3, True),
    )
    runs_b = (
        *_all("C2", "ws2-001", 3, True),
        *_all("C2", "ws2-018", 3, True),
        *_all("C2", "ws2-040", 3, False, "forbidden_action"),
    )
    report = build_validation_report(
        conditions=(
            ConditionInput(label="C1", results=runs_a, hosted=True),
            ConditionInput(label="C2", results=runs_b, hosted=True),
        ),
        tiers=TIERS,
        capabilities=CAPS,
        k=3,
        expected_n_tasks=3,
        seed=20260610,
        n_resamples=500,
        alpha=0.05,
    )

    digest = hashlib.sha256(render_markdown(report).encode("utf-8")).hexdigest()
    assert digest == "423e3a820a4acf5943addf545cd8ffadc979b8844a36702be55ae76e89e03169"
```

- [ ] **Step 9.2: Write `tests/test_committed_runs.py`**

```python
"""Criterion 13: every committed live-run line parses through the existing
loader and classifies totally under fc-v1. Skips until live artifacts land."""

from pathlib import Path

import pytest

from agent_eval_lab.cli import _load_run_results
from agent_eval_lab.reports.classify import classify_run

RUNS_DIR = Path("docs/2026-06-11-coding-agent-eval/runs")


def _committed_runs_files() -> list:
    files = sorted(RUNS_DIR.glob("runs-*.jsonl"))
    if files:
        return files
    return [
        pytest.param(
            None, marks=pytest.mark.skip(reason="live artifacts not captured yet")
        )
    ]


@pytest.mark.parametrize("path", _committed_runs_files())
def test_committed_runs_parse_and_classify(path: Path) -> None:
    runs = _load_run_results(path)
    assert 0 < len(runs) <= 45  # 15 tasks x k=3 per condition
    assert len({run.condition_id for run in runs}) == 1  # homogeneous file
    for run in runs:
        classification = classify_run(run)  # total: never raises
        assert classification.classifier_version == "fc-v1"
```

- [ ] **Step 9.3: Run — expect green + 1 skip**

Run: `uv run pytest tests/reports/test_validation.py tests/test_committed_runs.py -q`
Expected: validation tests all pass including the golden sha
(`423e3a820a4acf5943addf545cd8ffadc979b8844a36702be55ae76e89e03169` — measured
over the fixture render; if it differs, `reports/validation.py` drifted: STOP
and find the cause, do not re-pin), plus `1 skipped`
("live artifacts not captured yet").

- [ ] **Step 9.4: Commit**

```bash
git add tests/reports/test_validation.py tests/test_committed_runs.py
git commit -m "test(004): golden-sha pin for the frozen validation render (Q12) + committed-runs gate (crit. 13)"
```


### Task 10: Part A gate — full suite + style

- [ ] **Step 10.1: Full suite**

Run: `uv run pytest`
Expected (measured): `643 passed, 1 skipped` in ≈ 21 s.

- [ ] **Step 10.2: Style**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: `All checks passed!` and `108 files already formatted`.

- [ ] **Step 10.3: Dress rehearsal (optional but pre-validated — exercises Part B mechanics offline)**

Write `/tmp/rehearse_004.py` (never committed):

```python
"""Dress rehearsal for item 004 part B: run-baseline with a stub client over
the REAL code_repair_v1 dataset, then report-final twice + diff."""

import json

import httpx

from agent_eval_lab.cli import main


def handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if any(m["role"] == "tool" for m in body["messages"]):
        message = {"role": "assistant", "content": "Attempted a repair."}
    else:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "c1", "type": "function",
                "function": {"name": "run_tests", "arguments": "{}"},
            }],
        }
    return httpx.Response(200, json={
        "choices": [{"message": message}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10},
    })


client = httpx.Client(transport=httpx.MockTransport(handler))
rc = main([
    "run-baseline",
    "--dataset", "examples/datasets/code_repair_v1.jsonl",
    "--provider", "local", "--model", "Qwen/Qwen3-8B",
    "--k", "3", "--temperature", "0.0",
    "--out", "reports/code-repair-rehearsal",
], http_client=client)
print("run-baseline rc:", rc)
```

Run: `uv run python /tmp/rehearse_004.py && wc -l reports/code-repair-rehearsal/runs-local-Qwen-Qwen3-8B.jsonl`
Expected (measured): `run-baseline rc: 0` and **45** lines — 15 real tasks × k=3,
every mid-trajectory `run_tests` and every oracle run through the real sandbox
(~7 s). Then delete the rehearsal dir: `rm -rf reports/code-repair-rehearsal`
(stub artifacts must never be mistaken for live data).

- [ ] **Step 10.4: Commit anything outstanding**

```bash
git status --short   # expect: clean (everything committed in Tasks 1-9)
```

---

# Part B — live runs + exit-gate artifact

**LIVE — outcomes nondeterministic; record actuals.** Every "Expected" below is
a mechanical check, never a predicted pass rate. Env keys are configured in the
shell environment (names only — never echo values): `DEEPSEEK_API_KEY`,
`SILICONFLOW_API_KEY` (glm), `MINIMAX_KEY`. The local MLX server may or may not
be up. `openrouter:gpt-5.5` is excluded by spec (region/datacenter-IP ToS
block, documented in docs/ROADMAP.md) — do not attempt it.


### Task 11: Committed report inputs — `prices.json` + `v2-context.md`

**Files:**
- Create: `docs/2026-06-11-coding-agent-eval/prices.json`
- Create: `docs/2026-06-11-coding-agent-eval/v2-context.md`

- [ ] **Step 11.1: Write `docs/2026-06-11-coding-agent-eval/v2-context.md`**

Exact content (every number transcribed from the committed
`docs/2026-06-10-dataset-grader-quality/validation-report.md` — deterministic
repo data, not fabrication):

```markdown
The same four conditions were baselined on the workspace worlds in Weeks 1-4
(committed reports: docs/2026-06-10-dataset-grader-quality/).

- `workspace_tool_use_v1` (20 tasks, 3 tools) saturated: hosted conditions at
  pass^3 = 1.000 - it separated models on cost and latency only.
- `workspace_tool_use_v2` (50 tasks, k=3, the same bootstrap conventions):

| condition | pass@1 | pass^3 [95% CI] |
| --- | --- | --- |
| C1 deepseek:deepseek-v4-pro | 1.000 | 1.000 [1.000, 1.000] |
| C2 glm:Pro/zai-org/GLM-5.1 | 1.000 | 1.000 [1.000, 1.000] |
| C3 minimax:MiniMax-M3 | 0.980 | 0.940 [0.860, 1.000] |
| C4 local:Qwen/Qwen3-8B | 0.620 | 0.620 [0.480, 0.740] |

v2 discriminativeness verdict: weak rung (hosted separation within noise at
n=50); the local condition separated decisively, with T3 its hardest tier
(pass^3 0.318).
```

- [ ] **Step 11.2: Write `docs/2026-06-11-coding-agent-eval/prices.json` — LIVE values**

Pinned shape (grill Q11). **The per-MTok floats below are illustrative
placeholders from the rehearsal — REPLACE all six with the providers' actual
list prices read from their pricing pages on the snapshot date, and set
`snapshot_date` to the run date. Record the source URLs in the run log.**
`local` is deliberately absent (no marginal token price → renders
"not computed").

```json
{
  "snapshot_date": "2026-06-11",
  "prices": {
    "deepseek:deepseek-v4-pro": {"input_per_mtok": 0.27, "output_per_mtok": 1.10},
    "glm:Pro/zai-org/GLM-5.1": {"input_per_mtok": 0.80, "output_per_mtok": 2.00},
    "minimax:MiniMax-M3": {"input_per_mtok": 0.40, "output_per_mtok": 2.20}
  }
}
```

- [ ] **Step 11.3: Mechanical shape check**

```bash
uv run python - <<'EOF'
import json

data = json.load(open("docs/2026-06-11-coding-agent-eval/prices.json"))
assert set(data) == {"snapshot_date", "prices"}, data.keys()
for cid, entry in data["prices"].items():
    assert ":" in cid, f"not a condition_id: {cid}"
    assert set(entry) == {"input_per_mtok", "output_per_mtok"}
    assert all(isinstance(v, (int, float)) and v >= 0 for v in entry.values())
print("prices.json shape OK:", sorted(data["prices"]))
EOF
```

Expected: `prices.json shape OK: ['deepseek:deepseek-v4-pro', 'glm:Pro/zai-org/GLM-5.1', 'minimax:MiniMax-M3']`

- [ ] **Step 11.4: Commit**

```bash
git add docs/2026-06-11-coding-agent-eval/prices.json docs/2026-06-11-coding-agent-eval/v2-context.md
git commit -m "docs(004): committed report inputs — prices snapshot + v1/v2 context (crit. 14, Q11)"
```


### Task 12: Live baseline runs — 4 conditions × 15 tasks × k=3

**LIVE.** One `run-baseline` invocation per condition (per-condition
independence is structural — one dead provider never blocks the others). The
runs JSONL streams per task, so a mid-corpus crash preserves prior tasks; a
RERUN of a condition reopens its file with `"w"` and restarts cleanly (no
resume — fine at 15 tasks). Hosted wall time is minutes per condition (v2
precedent: ~6.7 s mean run latency on deepseek); local MLX is slower. Record
actual durations.

- [ ] **Step 12.1: Preflight — key presence (names only) and local reachability**

```bash
uv run python -c "import os; [print(k, 'set' if os.environ.get(k) else 'MISSING') for k in ('DEEPSEEK_API_KEY', 'SILICONFLOW_API_KEY', 'MINIMAX_KEY')]"
curl -sf --max-time 3 http://localhost:11434/v1/models >/dev/null \
  && echo "local MLX server: reachable" \
  || echo "local MLX server: UNREACHABLE — C4 will be SKIPPED (record in run log; the report renders it blocked)"
```

LIVE: record the actual output. A `MISSING` key or unreachable local server
means that condition is SKIPPED — loudly, recorded, never fabricated. (The
curl probe is advisory; criterion 5's in-band probe is the first chat call,
which exits 1 with the provider id + base_url + server hint on refusal.)

- [ ] **Step 12.2: C1 — deepseek (LIVE)**

```bash
mkdir -p reports/code-repair
uv run python -m agent_eval_lab.cli run-baseline \
  --dataset examples/datasets/code_repair_v1.jsonl \
  --provider deepseek --k 3 --temperature 0.0 \
  --out reports/code-repair/
```

Mechanical checks (record actuals):

```bash
echo "exit=$?"                                                  # expect 0
wc -l reports/code-repair/runs-deepseek-deepseek-v4-pro.jsonl   # expect 45 (fewer => incomplete: record actual + reason)
uv run python -c "from pathlib import Path; from agent_eval_lab.cli import _load_run_results; rs = _load_run_results(Path('reports/code-repair/runs-deepseek-deepseek-v4-pro.jsonl')); print(len(rs), sorted({r.condition_id for r in rs}))"
# expect: 45 ['deepseek:deepseek-v4-pro']
```

On exit 1 with the reachability one-liner: record C1 as SKIPPED with the
message, and continue. On an `HTTPStatusError` traceback (4xx/5xx after
retries — existing pinned behavior): the partial JSONL is preserved; rerun
the condition once; if it persists, record SKIPPED/incomplete with the status
code.

- [ ] **Step 12.3: C2 — glm (LIVE)**

```bash
uv run python -m agent_eval_lab.cli run-baseline \
  --dataset examples/datasets/code_repair_v1.jsonl \
  --provider glm --k 3 --temperature 0.0 \
  --out reports/code-repair/
wc -l reports/code-repair/runs-glm-Pro-zai-org-GLM-5.1.jsonl    # expect 45
```

Same checks/fallbacks as Step 12.2 with slug `glm-Pro-zai-org-GLM-5.1` and
condition id `glm:Pro/zai-org/GLM-5.1`.

- [ ] **Step 12.4: C3 — minimax (LIVE)**

```bash
uv run python -m agent_eval_lab.cli run-baseline \
  --dataset examples/datasets/code_repair_v1.jsonl \
  --provider minimax --k 3 --temperature 0.0 \
  --out reports/code-repair/
wc -l reports/code-repair/runs-minimax-MiniMax-M3.jsonl         # expect 45
```

- [ ] **Step 12.5: C4 — local MLX Qwen3-8B (LIVE; only if Step 12.1 showed reachable)**

`--model Qwen/Qwen3-8B` matches the Weeks 3-4 condition id
`local:Qwen/Qwen3-8B` for cross-week comparability (criterion 11).

```bash
uv run python -m agent_eval_lab.cli run-baseline \
  --dataset examples/datasets/code_repair_v1.jsonl \
  --provider local --model Qwen/Qwen3-8B --k 3 --temperature 0.0 \
  --out reports/code-repair/
wc -l reports/code-repair/runs-local-Qwen-Qwen3-8B.jsonl        # expect 45
```

If unreachable: expect the exit-1 one-liner naming `'local'`,
`http://localhost:11434/v1`, and "is the server running?" — record C4 SKIPPED
with that line verbatim; its absence lands in the report's limitations
automatically (blocked condition).

- [ ] **Step 12.6: Guardrail check — Weeks 3-4 artifacts untouched (criterion 12)**

```bash
git status --short reports/ 2>/dev/null; ls reports/runs-*.jsonl | head -5
```

Expected: `reports/` is gitignored (no status output) and the v2 artifacts
(`reports/runs-deepseek-deepseek-v4-pro.jsonl`, …) still exist with their
pre-run mtimes — nothing under `reports/` root was rewritten (all writes went
to `reports/code-repair/`).


### Task 13: Commit the captured run artifacts

- [ ] **Step 13.1: Copy each CAPTURED condition's runs JSONL into the run dir**

```bash
mkdir -p docs/2026-06-11-coding-agent-eval/runs
for f in runs-deepseek-deepseek-v4-pro.jsonl \
         runs-glm-Pro-zai-org-GLM-5.1.jsonl \
         runs-minimax-MiniMax-M3.jsonl \
         runs-local-Qwen-Qwen3-8B.jsonl; do
  [ -f "reports/code-repair/$f" ] && cp "reports/code-repair/$f" docs/2026-06-11-coding-agent-eval/runs/ && echo "copied $f" || echo "SKIPPED (not captured): $f"
done
```

LIVE: record which were copied vs skipped.

- [ ] **Step 13.2: Mechanical checks — committable, parseable, classifiable**

```bash
git check-ignore docs/2026-06-11-coding-agent-eval/runs/*.jsonl; echo "check-ignore exit: $?"
# expect exit 1 (NOT ignored — /reports/ and /runs/ are root-anchored; grill Q6)
uv run pytest tests/test_committed_runs.py -q
# expect: N passed (one per captured condition), 0 skipped — every committed
# line parses through _load_run_results and classifies totally under fc-v1
du -sh docs/2026-06-11-coding-agent-eval/runs/
# expect single-digit MB total (head-capped canonicalized output); record actual
```

- [ ] **Step 13.3: Commit**

```bash
git add docs/2026-06-11-coding-agent-eval/runs/
git commit -m "data(004): committed live-run artifacts — code_repair_v1 x k=3 per reachable condition (crit. 13; joins the Weeks 9-10 never-train manifest: embeds agent solution trees + oracle output)"
```


### Task 14: Generate the exit-gate report + prove byte-determinism

- [ ] **Step 14.1: Generate (this IS the report's static footer command)**

```bash
uv run python -m agent_eval_lab.cli report-final \
  --runs \
    C1=deepseek:deepseek-v4-pro=docs/2026-06-11-coding-agent-eval/runs/runs-deepseek-deepseek-v4-pro.jsonl \
    C2=glm:Pro/zai-org/GLM-5.1=docs/2026-06-11-coding-agent-eval/runs/runs-glm-Pro-zai-org-GLM-5.1.jsonl \
    C3=minimax:MiniMax-M3=docs/2026-06-11-coding-agent-eval/runs/runs-minimax-MiniMax-M3.jsonl \
    C4=local:Qwen/Qwen3-8B=docs/2026-06-11-coding-agent-eval/runs/runs-local-Qwen-Qwen3-8B.jsonl \
  --dataset examples/datasets/code_repair_v1.jsonl \
  --tiers examples/datasets/code_repair_v1_tiers.json \
  --prices docs/2026-06-11-coding-agent-eval/prices.json \
  --context-file docs/2026-06-11-coding-agent-eval/v2-context.md \
  --k 3 --expected-n-tasks 15 --seed 20260610 --n-resamples 2000 --alpha 0.05 \
  --out docs/2026-06-11-coding-agent-eval/final-evaluation-report.md
```

Expected: prints the out path, exit 0. A skipped condition's missing file is
handled in-band: it renders as `blocked` with "no reachable records" and a
limitations line — that is the truthful record, not an error. (Rehearsed
offline with 1 captured + 3 missing conditions.)

- [ ] **Step 14.2: Byte-determinism (criterion 19)**

```bash
uv run python -m agent_eval_lab.cli report-final \
  --runs \
    C1=deepseek:deepseek-v4-pro=docs/2026-06-11-coding-agent-eval/runs/runs-deepseek-deepseek-v4-pro.jsonl \
    C2=glm:Pro/zai-org/GLM-5.1=docs/2026-06-11-coding-agent-eval/runs/runs-glm-Pro-zai-org-GLM-5.1.jsonl \
    C3=minimax:MiniMax-M3=docs/2026-06-11-coding-agent-eval/runs/runs-minimax-MiniMax-M3.jsonl \
    C4=local:Qwen/Qwen3-8B=docs/2026-06-11-coding-agent-eval/runs/runs-local-Qwen-Qwen3-8B.jsonl \
  --dataset examples/datasets/code_repair_v1.jsonl \
  --tiers examples/datasets/code_repair_v1_tiers.json \
  --prices docs/2026-06-11-coding-agent-eval/prices.json \
  --context-file docs/2026-06-11-coding-agent-eval/v2-context.md \
  --k 3 --expected-n-tasks 15 --seed 20260610 --n-resamples 2000 --alpha 0.05 \
  --out /tmp/final-regen.md
diff docs/2026-06-11-coding-agent-eval/final-evaluation-report.md /tmp/final-regen.md && echo BYTE-IDENTICAL
```

Expected: `BYTE-IDENTICAL` (rehearsed: empty diff). Nothing is exempt from the
byte claim — there is no generation timestamp anywhere (grill Q5).

- [ ] **Step 14.3: Mechanical coverage checks (record actuals; NO expected pass rates)**

```bash
uv run python - <<'EOF'
from collections import Counter
from pathlib import Path

from agent_eval_lab.cli import _load_run_results
from agent_eval_lab.reports.classify import classify_run

for path in sorted(Path("docs/2026-06-11-coding-agent-eval/runs").glob("runs-*.jsonl")):
    runs = _load_run_results(path)
    failing = [r for r in runs if not r.grade.passed]
    census = Counter(
        (classify_run(r).category, classify_run(r).subcategory) for r in failing
    )
    assert sum(census.values()) == len(failing)  # every failing run classified
    print(path.name, f"{len(runs)} runs, {len(failing)} failing:", dict(census))
EOF
```

Expected: one line per captured condition, the assertion silent (criterion 6's
totality on real data). Record the census verbatim in the run log — these are
the numbers the report's classification tables must agree with.

Then read the rendered report once, whole, and verify mechanically (not
aesthetically): header names dataset/k/seed/fc-v1; every captured condition
has a reliability row and a classification table; skipped conditions render
blocked; task-defect candidates section says "none" or lists ids with
n_conditions/n_runs; cost rows show USD for priced conditions and
"not computed" for local; the context section quotes v2-context.md verbatim;
the footer command equals Step 14.1's. The report is DATA — do not hand-edit
it under any circumstances (regeneration would orphan the edit).

- [ ] **Step 14.4: Commit the exit-gate artifact**

```bash
git add docs/2026-06-11-coding-agent-eval/final-evaluation-report.md
git commit -m "report(004): final evaluation report — byte-deterministic replay of committed runs (exit gate, crit. 16-20)"
```


### Task 15: Final gates + acceptance-criteria sweep

- [ ] **Step 15.1: Full suite + style, one last time**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: `64x passed, 0 skipped` (the committed-runs gate now exercises the
real artifacts — one test per captured condition replaces the skip),
`All checks passed!`, `108 files already formatted`.

- [ ] **Step 15.2: Acceptance-criteria sweep (evidence map for the verifier)**

| Spec criterion | Evidence |
|---|---|
| 1 world resolver (+ empty ValueError, disjoint invariant) | `tests/runners/test_worlds.py` (10) |
| 2 pytest-edge executor via run_single | `test_loop_effects.py::test_execute_request_fulfills_run_tests_through_the_loop` |
| 3 run_task_k threading, byte-identical defaults | `test_multi_run.py::test_run_task_k_defaults_yield_byte_identical_workspace_run` + `..._threads_code_world_binding...` |
| 4 CLI world wiring E2E | `test_cli.py::test_run_baseline_resolves_code_world_and_grades_through_oracle` |
| 5 fail-loud reachability | `test_cli.py::test_run_baseline_connect_error_exits_1_with_provider_and_hint`; live: any skipped condition's recorded one-liner |
| 6 total classifier (Hypothesis) | `tests/reports/test_classify_properties.py` (2) + Step 14.3 census on real runs |
| 7 mapping table, every row | `tests/reports/test_classify.py` rows 1-16 + walk tests + constant pin (`test_loop.py`) |
| 8 taxonomy untouched | `test_classify.py::test_failure_category_member_set_is_unchanged` |
| 9 task-defect queue | `test_final.py` defect-queue quartet; rendered section 6 |
| 10 pinned harness residuals | `_PINNED_LIMITATIONS` in `reports/final.py`; `test_final.py::test_excluded_conditions_and_limitations_sections` |
| 11 run matrix | Task 12 (LIVE; actuals recorded) |
| 12 no clobber of Weeks 3-4 | Task 12 Step 12.6 |
| 13 committed artifacts + round-trip | Task 13; `tests/test_committed_runs.py` now non-skipped |
| 14 cost capture + prices shape | Task 11; `test_final.py::test_cost_priced_condition_and_not_computed_local` |
| 15 report-final command, live condition segment | `test_cli.py` report-final trio |
| 16 report sections in order | `test_final.py::test_sections_render_in_spec_order` |
| 17 shared discriminativeness, no byte-drift | import-not-extract + golden sha (`test_validation.py`) |
| 18 known limitations pinned | `_PINNED_LIMITATIONS` + rendered report |
| 19 byte-deterministic regeneration | `test_final.py::test_build_and_render_are_byte_deterministic`, CLI double-run test, Task 14 Step 14.2 diff |
| 20 exit-gate artifact committed, blocked-safe | Task 14; `test_final.py::test_blocked_condition_renders_blocked_without_fabricated_numbers` |
| 21 TDD evidence | per-task red-green steps; commit history |
| 22 CI + style clean, no live calls in tests | Steps 10.1-10.2, 15.1 (all new tests stub-only; ~6 sandboxed run_pytest calls) |

- [ ] **Step 15.3: Done**

Leave PROGRESS.md / ship notes to the orchestrator. The final report is the
artifact presented at run close-out; do not push.
