# Item 002 — Execution-Based Graders (Tests as the Oracle): Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the Tier-2 grading leg: the `ExecutionSpec` `VerificationSpec` variant (held-out oracle tests + optional `timeout_s`), the pure oracle-wins overlay and `execution_hash`, the pure `grade_execution` grader, the oracle edge (`runners/oracle_edge.py`) that precomputes `ExecutionVerdict`s into the shared verdict map, dispatch + `multi_run` wiring, and nine golden conformance cases that run real sandboxed pytest — per `docs/2026-06-11-coding-agent-eval/items/002-spec.md`, ADR-0010, and ADR-0011.

**Architecture:** Functional core / imperative shell. `graders/execution.py` is pure (overlay, hash, collector, grader — importing it never executes anything); all execution I/O lives in `runners/oracle_edge.py`, which calls item 001's `runners/pytest_edge.run_pytest`. Verdicts thread through the **existing** `verdicts` mapping of `grade_trajectory`/`grade_all_of` (zero signature change), keyed by `execution_hash(spec, final_tree)`, values discriminated by `isinstance` — the judge pattern (ADR-0005) generalized (ADR-0011). The overlay is oracle-wins with displaced-path evidence; canonical-prefix collisions are structured `ExecutionError(kind="tree_collision")` records, never crashes (ADR-0010).

**Tech Stack:** Python 3.11+ (project venv 3.13), stdlib only for new runtime code (`hashlib`, `json`), pytest 9.0.3 + Hypothesis (dev), ruff (`E,F,I,UP`, line length 88, `ruff format`). All commands run via `uv run`.

**Branch:** stay on `autodev/coding-agent-eval-feature`. Commit after every task. NEVER push — the orchestrator handles pushes.

**Already done — do NOT recreate:** `docs/adr/0010-oracle-tests-overlay-final-tree-oracle-wins.md`, `docs/adr/0011-execution-verdicts-share-the-verdict-map-keyed-by-execution-hash.md`, the ADR-0008 clarifying sentence, and the CONTEXT.md oracle-cluster terms (*oracle tests*, *overlay (oracle-wins)*, *displaced path*, *execution hash*, *ExecutionVerdict*, *oracle edge*, updated *VerificationSpec*) all exist (commit `aa6e8ed`). Spec criterion 16 is "the implementation conforms to ADR-0010/0011"; no plan task touches docs.

**Baseline:** `uv run pytest` currently reports `450 passed`. Every task below keeps the cumulative suite green; the expected count after each task is stated at its commit step.

**Pre-validated:** the final assembly of every code block in this plan was executed in a scratch worktree on this machine during planning: `528 passed` (zero warnings, ~9.4 s), `ruff check .` clean, `ruff format --check .` reports `99 files already formatted`. The code below is exact — type it verbatim; if a step's outcome differs from the stated expectation, suspect a transcription slip before suspecting the design.

**Empirically verified facts this plan relies on** (probed in the scratch worktree):
- `tests/graders/test_execution.py` collides with the existing `tests/records/test_execution.py` basename under pytest's rootdir import mode → collection error. Fix: an empty `tests/graders/__init__.py` (the exact mechanism `tests/runners/__init__.py` already uses so `runners/test_parse.py` can coexist with `tasks/test_parse.py`). Task 4 creates it.
- Package-ifying `tests/graders/` recompiles `tests/graders/test_judge.py`, surfacing a pre-existing `SyntaxWarning: invalid escape sequence '\s'` in a docstring at line 263. Task 4 fixes it with a raw docstring (`r"""`), keeping the suite warning-free.
- The policy grader's `GRADER_ID` is `"trajectory_policy"` (not `"trajectory"`) — asserted as such in Task 10.
- A combined tree with an *agent-internal* canonical collision (e.g. `Lib/a.py` + `lib/b.py`) passes the agent↔oracle overlay check and is then caught by `pytest_edge`'s materializer guard (`RuntimeError`), which the oracle edge captures as `ExecutionError(kind="harness")` — measured, deterministic.
- An oracle file `test_oracle_empty.py` containing only `HELPER = 1` is collected by pytest but yields zero tests → exit 5 → `no_tests`. A `timeout_s=1.0` spec over a `time.sleep(30)` tree reliably yields `timeout` in ~1.2 s.
- The full golden suite (32 cases, 10 of which run real sandboxed pytest) completes in ~1.6 s; the whole test suite in ~9.4 s — far under the ~20 s budget.

---

## File map

| Path | Action | Responsibility |
|---|---|---|
| `src/agent_eval_lab/tools/code_world.py` | Modify (one rename) | `_prefix_collision` → public `prefix_collision`: the single shared collision predicate (grill resolved decision 8). Nothing else moves. |
| `src/agent_eval_lab/tasks/schema.py` | Modify | Frozen `ExecutionSpec` + completed `VerificationSpec` union; stale comment retired. |
| `src/agent_eval_lab/tasks/parse.py` | Modify | `"execution"` branch: structural validation of oracle paths (reusing `path_error` + `prefix_collision`), `timeout_s` typing. |
| `src/agent_eval_lab/graders/execution.py` | Create | Pure core: `ExecutionVerdict`/`OverlaidTree`/`OverlayCollision` records, `overlay_oracle`, `execution_hash`, `collect_execution_specs`, `grade_execution`. No I/O imports. 175 lines. |
| `src/agent_eval_lab/runners/oracle_edge.py` | Create | The oracle edge: `ExecutionError` record + `precompute_execution_verdicts` atop `pytest_edge.run_pytest`. 86 lines. |
| `src/agent_eval_lab/records/serialize.py` | Modify | `verdict_to_dict`/`verdict_from_dict` gain `"execution_verdict"`/`"execution_error"` tags; judge's legacy `"verdict"` tag frozen. |
| `src/agent_eval_lab/graders/dispatch.py` | Modify | `isinstance(verification, ExecutionSpec)` branch → `grade_execution`. No signature change. |
| `src/agent_eval_lab/runners/multi_run.py` | Modify | `precompute_execution_verdicts` between `run_single` and `grade_trajectory`; `{}` for non-execution tasks (behavior-preserving). |
| `tests/graders/__init__.py` | Create (empty) | Resolves the `test_execution.py` basename collision (see verified facts). |
| `tests/graders/test_judge.py` | Modify (1 char) | `r"""` raw docstring — silences the surfaced pre-existing SyntaxWarning. |
| `tests/tasks/test_schema.py` | Modify (append) | `ExecutionSpec` shape/frozen/union test. |
| `tests/tasks/test_parse.py` | Modify (append) | Parse + every structural rejection, unit-tested. |
| `tests/graders/test_execution.py` | Create | Overlay/hash/collector/grader unit tests (no mocks, no sandbox) + taxonomy + module-purity tests. |
| `tests/graders/test_execution_properties.py` | Create | Hypothesis: overlay no-mutation/oracle-wins; hash determinism/sensitivity. |
| `tests/runners/test_oracle_edge.py` | Create | Edge integration matrix on real sandboxed pytest + byte-identical reproducibility test. |
| `tests/records/test_serialize.py` | Modify (append) | Round-trips for both new tags + legacy-tag freeze test. |
| `tests/graders/test_dispatch.py` | Modify (append) | ExecutionSpec dispatch, `AllOf(execution, policy)`, judge+execution coexistence in one map. |
| `tests/runners/test_multi_run.py` | Modify (append) | Production call-site test (real sandbox run through `run_task_k`). |
| `tests/golden/24…32_execution_*.json` | Create (9 files) | Golden cases (a)–(i) of criterion 14. |
| `tests/test_golden_conformance.py` | Modify (rewrite) | `"registry"` field, production precompute, count 23→32, oracle-secrecy security test. |

Untouched (constraint): `records/execution.py`, `records/turns.py`, `records/grade.py` (taxonomy), `runners/pytest_edge.py` (its private `_has_prefix_collision` stays as defense-in-depth), `runners/wire.py`, `graders/composite.py`, `graders/judge.py`, `runners/judge_edge.py`, `tests/runners/test_loop.py`.

---

### Task 1: Export the shared collision predicate from code-world

The grill (resolved decision 8) allows exactly one additive, behavior-preserving public export of code-world's existing collision predicate. We rename `_prefix_collision` → `prefix_collision` (the docstring rides along; one internal call site updates; behavior identical). `pytest_edge.py`'s duplicate `_has_prefix_collision` is deliberately untouched.

**Files:**
- Modify: `tests/tools/test_code_world.py` (append)
- Modify: `src/agent_eval_lab/tools/code_world.py`

- [ ] **Step 1.1: Append the failing test**

Append to the end of `tests/tools/test_code_world.py`:

```python
def test_prefix_collision_is_the_public_shared_predicate() -> None:
    """Item 002: the single collision predicate, exported for the oracle
    overlay and the oracle-path parser (grill resolved decision 8)."""
    from agent_eval_lab.tools.code_world import prefix_collision

    assert prefix_collision("Tests/test_app.py", "tests/test_app.py") is True
    assert prefix_collision("tests/test_app.py", "tests/test_app.py") is False
    assert prefix_collision("tests/a.py", "tests/b.py") is False
```

- [ ] **Step 1.2: Run the test to verify it fails**

Run: `uv run pytest tests/tools/test_code_world.py`
Expected: FAIL — `44 passed, 1 failed`; the new test errors with `ImportError: cannot import name 'prefix_collision'`.

- [ ] **Step 1.3: Rename the predicate**

In `src/agent_eval_lab/tools/code_world.py`, replace exactly this block:

```python
def _prefix_collision(new_path: str, existing_path: str) -> bool:
    """True when new_path and existing_path share a canonically identical prefix
    at some depth but spell it differently — unsafe on normalization-insensitive
    (APFS) or case-insensitive filesystems.

    Two paths with the exact same spelling are not a collision (overwrite allowed).
    Same-spelled directory, different filenames: not a collision.
    """
```

with:

```python
def prefix_collision(new_path: str, existing_path: str) -> bool:
    """True when new_path and existing_path share a canonically identical prefix
    at some depth but spell it differently — unsafe on normalization-insensitive
    (APFS) or case-insensitive filesystems.

    Two paths with the exact same spelling are not a collision (overwrite allowed).
    Same-spelled directory, different filenames: not a collision.

    Public: this is the project's single collision predicate — the oracle
    overlay (graders/execution.overlay_oracle) and the oracle-path parser
    reuse it; pytest_edge's materializer guard stays defense-in-depth only.
    """
```

Then replace exactly this block (the only internal call site):

```python
    clash = next(
        (existing for existing in files if _prefix_collision(path, existing)),
        None,
    )
```

with:

```python
    clash = next(
        (existing for existing in files if prefix_collision(path, existing)),
        None,
    )
```

- [ ] **Step 1.4: Run the tests to verify they pass**

Run: `uv run pytest tests/tools/test_code_world.py && uv run ruff check .`
Expected: `45 passed`; `All checks passed!`

- [ ] **Step 1.5: Commit**

```bash
git add tests/tools/test_code_world.py src/agent_eval_lab/tools/code_world.py
git commit -m "feat(tools): export prefix_collision — the single shared collision predicate"
```

---

### Task 2: `ExecutionSpec` schema variant

**Files:**
- Modify: `tests/tasks/test_schema.py` (append)
- Modify: `src/agent_eval_lab/tasks/schema.py`

- [ ] **Step 2.1: Append the failing test**

Append to the end of `tests/tasks/test_schema.py`:

```python
def test_execution_spec_shape_defaults_and_union_membership() -> None:
    import dataclasses

    import pytest

    from agent_eval_lab.tasks.schema import ExecutionSpec, VerificationSpec

    spec = ExecutionSpec(
        held_out_tests={"test_oracle.py": "def test_ok():\n    assert True\n"}
    )

    assert spec.type == "execution"
    assert spec.timeout_s is None
    assert isinstance(spec, VerificationSpec)
    assert [f.name for f in dataclasses.fields(ExecutionSpec)] == [
        "type",
        "held_out_tests",
        "timeout_s",
    ]
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.timeout_s = 5.0  # type: ignore[misc]
```

(The exact-fields assertion is criterion 1's "exactly these fields, no `expected_status`" made executable.)

- [ ] **Step 2.2: Run the test to verify it fails**

Run: `uv run pytest tests/tasks/test_schema.py`
Expected: FAIL — `4 passed, 1 failed`; `ImportError: cannot import name 'ExecutionSpec'`.

- [ ] **Step 2.3: Add the variant and complete the union**

In `src/agent_eval_lab/tasks/schema.py`, replace exactly this block:

```python
# Weeks 3-4 deterministic tier + the Tier-3 model-based grader (item 003).
# ExecutionSpec (Weeks 5-6) extends this union later without breaking serialization.
VerificationSpec = (
    OutputMatchSpec
    | ToolCallMatchSpec
    | FinalStateSpec
    | TrajectorySpec
    | AllOf
    | LlmJudgeSpec
)
```

with:

```python
@dataclass(frozen=True, kw_only=True)
class ExecutionSpec:
    """Tier-2 oracle tests: held-out files the agent never sees (ADR-0010).

    `held_out_tests` maps POSIX-relative path -> text content; `timeout_s`
    is the per-task sandbox budget (None => the edge's DEFAULT_TIMEOUT_S).
    No expected_status knob exists: pass means suite status == "passed".
    """

    type: Literal["execution"] = "execution"
    held_out_tests: Mapping[str, str]
    timeout_s: float | None = None


# The complete tagged union: deterministic tiers (Weeks 1-4), the Tier-3
# model-based judge (item 003), and the Tier-2 execution oracle (Weeks 5-6).
VerificationSpec = (
    OutputMatchSpec
    | ToolCallMatchSpec
    | FinalStateSpec
    | TrajectorySpec
    | AllOf
    | LlmJudgeSpec
    | ExecutionSpec
)
```

- [ ] **Step 2.4: Run the tests to verify they pass**

Run: `uv run pytest tests/tasks/test_schema.py && uv run ruff check .`
Expected: `5 passed`; `All checks passed!`

- [ ] **Step 2.5: Commit**

```bash
git add tests/tasks/test_schema.py src/agent_eval_lab/tasks/schema.py
git commit -m "feat(tasks): ExecutionSpec variant completes the VerificationSpec union"
```

---

### Task 3: Parse `"execution"` with structural oracle validation

**Files:**
- Modify: `tests/tasks/test_parse.py` (append)
- Modify: `src/agent_eval_lab/tasks/parse.py`

- [ ] **Step 3.1: Append the failing tests**

Append to the end of `tests/tasks/test_parse.py`:

```python
_ORACLE_TESTS = {
    "test_oracle_calc.py": (
        "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    ),
    "conftest.py": "# oracle helper modules are legitimate\n",
}


def test_verification_from_dict_parses_execution_spec() -> None:
    from agent_eval_lab.tasks.schema import ExecutionSpec

    spec = verification_from_dict(
        {"type": "execution", "held_out_tests": _ORACLE_TESTS, "timeout_s": 5}
    )

    assert spec == ExecutionSpec(held_out_tests=_ORACLE_TESTS, timeout_s=5.0)
    assert isinstance(spec.timeout_s, float)  # JSON int stored as float


def test_execution_spec_timeout_defaults_to_none() -> None:
    spec = verification_from_dict(
        {"type": "execution", "held_out_tests": _ORACLE_TESTS}
    )

    assert spec.timeout_s is None


def test_execution_task_row_parses_from_jsonl_shape() -> None:
    import json

    from agent_eval_lab.tasks.schema import ExecutionSpec

    row = json.loads(
        json.dumps(
            {
                **TASK_DATA,
                "verification": {
                    "type": "execution",
                    "held_out_tests": _ORACLE_TESTS,
                    "timeout_s": 5,
                },
                "initial_state": {"files": {"calc.py": "def add(a, b): ...\n"}},
            }
        )
    )

    task = parse_task(row)

    assert task.verification == ExecutionSpec(
        held_out_tests=_ORACLE_TESTS, timeout_s=5.0
    )


def test_execution_rejects_empty_held_out_tests() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        verification_from_dict({"type": "execution", "held_out_tests": {}})


@pytest.mark.parametrize(
    "path",
    ["/abs.py", "../escape.py", "a/../b.py", "a//b.py", ".", "a\\b.py", "bad\x00.py"],
)
def test_execution_rejects_non_canonical_oracle_paths(path: str) -> None:
    with pytest.raises(ValueError, match="held_out_tests"):
        verification_from_dict(
            {"type": "execution", "held_out_tests": {path: "x = 1\n"}}
        )


def test_execution_rejects_reserved_junit_path() -> None:
    with pytest.raises(ValueError, match="reserved"):
        verification_from_dict(
            {"type": "execution", "held_out_tests": {".junit.xml": "<xml/>"}}
        )


def test_execution_rejects_oracle_internal_prefix_collision() -> None:
    with pytest.raises(ValueError, match="canonical-prefix collision"):
        verification_from_dict(
            {
                "type": "execution",
                "held_out_tests": {
                    "tests/test_a.py": "x = 1\n",
                    "Tests/test_b.py": "y = 2\n",
                },
            }
        )


@pytest.mark.parametrize("timeout_s", [0, -1, 0.0, -0.5, True, False, "5"])
def test_execution_rejects_non_positive_or_non_numeric_timeout(timeout_s) -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        verification_from_dict(
            {
                "type": "execution",
                "held_out_tests": _ORACLE_TESTS,
                "timeout_s": timeout_s,
            }
        )
```

- [ ] **Step 3.2: Run the tests to verify they fail**

Run: `uv run pytest tests/tasks/test_parse.py`
Expected: FAIL — `20 failed, 16 passed`. Every new test hits `ValueError: unknown verification type: 'execution'` (the rejection tests fail because that message does not match their expected patterns).

- [ ] **Step 3.3: Implement the parse branch**

In `src/agent_eval_lab/tasks/parse.py`, replace exactly this block (the import section — note the **new last line**):

```python
from agent_eval_lab.records.serialize import turn_from_dict
from agent_eval_lab.records.turns import MessageTurn, Turn
from agent_eval_lab.tasks.schema import (
    AllOf,
    ExpectedToolCall,
    FinalStateSpec,
    LlmJudgeSpec,
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    OutputMatchSpec,
    StateConstraint,
    StateContains,
    StateEquals,
    Task,
    TaskInput,
    TaskMetadata,
    ToolCallMatchSpec,
    TrajectoryConstraint,
    TrajectorySpec,
    VerificationSpec,
)
```

with:

```python
from agent_eval_lab.records.serialize import turn_from_dict
from agent_eval_lab.records.turns import MessageTurn, Turn
from agent_eval_lab.tasks.schema import (
    AllOf,
    ExecutionSpec,
    ExpectedToolCall,
    FinalStateSpec,
    LlmJudgeSpec,
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    OutputMatchSpec,
    StateConstraint,
    StateContains,
    StateEquals,
    Task,
    TaskInput,
    TaskMetadata,
    ToolCallMatchSpec,
    TrajectoryConstraint,
    TrajectorySpec,
    VerificationSpec,
)
from agent_eval_lab.tools.code_world import path_error, prefix_collision
```

(`tools/code_world.py` is pure — importing it performs no I/O; `path_error` already covers non-canonical form, leading `/`, backslash/NUL, *and* the reserved `.junit.xml` key.)

Then replace exactly this block:

```python
def _state_constraint_from_dict(data: Mapping[str, Any]) -> StateConstraint:
```

with:

```python
def _parse_timeout(raw: Any) -> float | None:
    """Accept a JSON int or float, store as float; bool and <= 0 are rejected."""
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"timeout_s must be a number, got {raw!r}")
    if raw <= 0:
        raise ValueError(f"timeout_s must be positive, got {raw!r}")
    return float(raw)


def _oracle_collision(paths: tuple[str, ...]) -> tuple[str, str] | None:
    """First oracle-internal canonical-prefix collision (001's invariant)."""
    return next(
        (
            (path_a, path_b)
            for i, path_a in enumerate(paths)
            for path_b in paths[i + 1 :]
            if prefix_collision(path_a, path_b)
        ),
        None,
    )


def _parse_held_out_tests(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping) or not raw:
        raise ValueError(
            f"held_out_tests must be a non-empty path->content mapping, got {raw!r}"
        )
    for path in raw:
        error = path_error(path)
        if error is not None:
            raise ValueError(f"held_out_tests: {error}")
    collision = _oracle_collision(tuple(sorted(raw)))
    if collision is not None:
        raise ValueError(
            "held_out_tests: canonical-prefix collision between "
            f"{collision[0]!r} and {collision[1]!r}"
        )
    return dict(raw)


def _state_constraint_from_dict(data: Mapping[str, Any]) -> StateConstraint:
```

Then replace exactly this block:

```python
    if kind == "llm_judge":
        return LlmJudgeSpec(
            rubric=data["rubric"],
            judge_model=data["judge_model"],
            scale=_parse_scale(data.get("scale", [1, 5])),
        )
    raise ValueError(f"unknown verification type: {kind!r}")
```

with:

```python
    if kind == "llm_judge":
        return LlmJudgeSpec(
            rubric=data["rubric"],
            judge_model=data["judge_model"],
            scale=_parse_scale(data.get("scale", [1, 5])),
        )
    if kind == "execution":
        return ExecutionSpec(
            held_out_tests=_parse_held_out_tests(data["held_out_tests"]),
            timeout_s=_parse_timeout(data.get("timeout_s")),
        )
    raise ValueError(f"unknown verification type: {kind!r}")
```

- [ ] **Step 3.4: Run the tests to verify they pass**

Run: `uv run pytest tests/tasks/test_parse.py && uv run ruff check .`
Expected: `36 passed`; `All checks passed!`

- [ ] **Step 3.5: Commit**

```bash
git add tests/tasks/test_parse.py src/agent_eval_lab/tasks/parse.py
git commit -m "feat(tasks): parse execution specs with structural oracle validation"
```

---

### Task 4: Pure oracle-wins overlay (`graders/execution.py`, part 1)

This task also creates `tests/graders/__init__.py` and applies the one-character `test_judge.py` fix — both forced by the new test module (see "Empirically verified facts").

**Files:**
- Create: `tests/graders/__init__.py` (empty)
- Modify: `tests/graders/test_judge.py` (one character)
- Create: `tests/graders/test_execution.py`
- Create: `src/agent_eval_lab/graders/execution.py`

- [ ] **Step 4.1: Create the test package marker and fix the surfaced warning**

```bash
touch tests/graders/__init__.py
```

In `tests/graders/test_judge.py`, replace exactly this block:

```python
def test_parse_rejects_bold_markdown_score_line() -> None:
    """'**SCORE: 4**' is NOT accepted: the asterisks are non-whitespace chars on the
    line, so the strict ^\s*SCORE:\s*(\d+)\s*$ pattern does not match — no_score."""
```

with:

```python
def test_parse_rejects_bold_markdown_score_line() -> None:
    r"""'**SCORE: 4**' is NOT accepted: the asterisks are non-whitespace chars on the
    line, so the strict ^\s*SCORE:\s*(\d+)\s*$ pattern does not match — no_score."""
```

(Without `__init__.py`, the new `tests/graders/test_execution.py` collides with `tests/records/test_execution.py` and pytest aborts collection. Adding the package marker recompiles the directory's modules, which surfaces a pre-existing `SyntaxWarning` in this docstring; the raw-string prefix keeps the suite warning-free. Both effects were measured.)

- [ ] **Step 4.2: Write the failing overlay tests**

Create `tests/graders/test_execution.py` with exactly:

```python
"""Pure execution-grading core: overlay, hash, collector, grader (no sandbox)."""

from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    OverlaidTree,
    OverlayCollision,
    overlay_oracle,
)
from agent_eval_lab.records.execution import ExecutionResult, TestCaseResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import ExecutionSpec

ORACLE = {
    "test_oracle_calc.py": (
        "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
}

TREE = {"calc.py": "def add(a, b):\n    return a + b\n"}

SPEC = ExecutionSpec(held_out_tests=ORACLE)

PASSED_RESULT = ExecutionResult(
    status="passed",
    exit_code=0,
    passed=1,
    failed=0,
    errors=0,
    skipped=0,
    tests=(TestCaseResult(test_id="test_oracle_calc::test_add", status="passed"),),
    stdout="1 passed in <duration>",
    stderr="",
)

FAILED_RESULT = ExecutionResult(
    status="failed",
    exit_code=1,
    passed=0,
    failed=1,
    errors=0,
    skipped=0,
    tests=(TestCaseResult(test_id="test_oracle_calc::test_add", status="failed"),),
    stdout="1 failed in <duration>",
    stderr="",
)


def _trajectory(final_state) -> Trajectory:
    return Trajectory(
        turns=(MessageTurn(role="assistant", content="done"),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def _verdict(result: ExecutionResult, key: str) -> ExecutionVerdict:
    return ExecutionVerdict(result=result, execution_hash=key, displaced_paths=())


# --- overlay (ADR-0010) ---


def test_overlay_combines_disjoint_trees_with_no_displacement() -> None:
    overlaid = overlay_oracle(TREE, ORACLE)
    assert isinstance(overlaid, OverlaidTree)
    assert overlaid.files == {**TREE, **ORACLE}
    assert overlaid.displaced_paths == ()


def test_overlay_oracle_wins_exact_path_collision_and_reports_displacement() -> None:
    agent_tree = {**TREE, "test_oracle_calc.py": "def test_fake():\n    assert True\n"}
    overlaid = overlay_oracle(agent_tree, ORACLE)
    assert isinstance(overlaid, OverlaidTree)
    assert overlaid.files["test_oracle_calc.py"] == ORACLE["test_oracle_calc.py"]
    assert overlaid.displaced_paths == ("test_oracle_calc.py",)


def test_overlay_detects_casefold_prefix_collision() -> None:
    agent_tree = {"Tests/test_app.py": "def test_fake():\n    assert True\n"}
    oracle = {"tests/test_app.py": "def test_real():\n    assert True\n"}
    overlaid = overlay_oracle(agent_tree, oracle)
    assert overlaid == OverlayCollision(
        pairs=(("Tests/test_app.py", "tests/test_app.py"),)
    )


def test_overlay_detects_nfc_normalization_collision() -> None:
    # 'caf\u00e9.py' composed vs 'cafe\u0301.py' decomposed: same NFC form,
    # different spelling -- a collision, not a displacement.
    composed = "caf\u00e9.py"
    decomposed = "cafe\u0301.py"
    overlaid = overlay_oracle({composed: "x = 1\n"}, {decomposed: "x = 2\n"})
    assert isinstance(overlaid, OverlayCollision)
    assert overlaid.pairs == ((composed, decomposed),)


def test_overlay_never_mutates_its_inputs() -> None:
    agent_tree = {"test_oracle_calc.py": "agent\n", "calc.py": "x = 1\n"}
    oracle = dict(ORACLE)
    overlay_oracle(agent_tree, oracle)
    assert agent_tree == {"test_oracle_calc.py": "agent\n", "calc.py": "x = 1\n"}
    assert oracle == ORACLE
```

(Type the `\u00e9` / `\u0301` escape sequences LITERALLY — six characters each, interpreted by Python at compile time. Do NOT substitute rendered accented characters: an editor or clipboard may normalize both spellings to the same bytes and the test would lose its meaning. `PASSED_RESULT`/`FAILED_RESULT`/`_trajectory`/`_verdict` are used by tests appended in Tasks 5–6; they land now so the fixture block never changes again.)

- [ ] **Step 4.3: Run the tests to verify they fail**

Run: `uv run pytest tests/graders/test_execution.py`
Expected: FAIL — collection error, `ModuleNotFoundError: No module named 'agent_eval_lab.graders.execution'`.

- [ ] **Step 4.4: Write the records and the overlay**

Create `src/agent_eval_lab/graders/execution.py` with exactly:

```python
"""Pure Tier-2 execution grading core (ADR-0010, ADR-0011): no I/O, total.

The oracle edge (runners/oracle_edge.precompute_execution_verdicts) overlays
the oracle tests onto the trajectory's final tree, runs the sandboxed pytest,
and threads an immutable verdict map keyed by `execution_hash` into this pure
grader, which only reads it. This module imports no process or filesystem
machinery; importing it never executes anything.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.tools.code_world import prefix_collision

GRADER_ID = "execution"


@dataclass(frozen=True, kw_only=True)
class ExecutionVerdict:
    """The oracle run's record plus its hash and displaced paths (ADR-0011)."""

    result: ExecutionResult
    execution_hash: str
    displaced_paths: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class OverlaidTree:
    """Combined agent+oracle tree; the oracle wins exact-path collisions."""

    files: Mapping[str, str]
    displaced_paths: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class OverlayCollision:
    """Canonical-prefix collisions between agent and oracle paths (ADR-0010)."""

    pairs: tuple[tuple[str, str], ...]  # (agent_path, oracle_path), sorted


def overlay_oracle(
    final_tree: Mapping[str, str], held_out_tests: Mapping[str, str]
) -> OverlaidTree | OverlayCollision:
    """Pure oracle-wins overlay; detects collisions before materialization."""
    pairs = tuple(
        (agent_path, oracle_path)
        for agent_path in sorted(final_tree)
        for oracle_path in sorted(held_out_tests)
        if prefix_collision(agent_path, oracle_path)
    )
    if pairs:
        return OverlayCollision(pairs=pairs)
    displaced = tuple(sorted(set(final_tree) & set(held_out_tests)))
    return OverlaidTree(
        files={**final_tree, **held_out_tests}, displaced_paths=displaced
    )
```

- [ ] **Step 4.5: Run the tests to verify they pass**

Run: `uv run pytest tests/graders/test_execution.py tests/graders/test_judge.py && uv run ruff check .`
Expected: `5 passed` + the judge file's existing tests all passing, **no warnings**; `All checks passed!`

- [ ] **Step 4.6: Commit**

```bash
git add tests/graders/__init__.py tests/graders/test_judge.py tests/graders/test_execution.py src/agent_eval_lab/graders/execution.py
git commit -m "feat(graders): pure oracle-wins overlay with structured collision report (ADR-0010)"
```

---

### Task 5: `execution_hash` (`graders/execution.py`, part 2)

**Files:**
- Modify: `tests/graders/test_execution.py`
- Modify: `src/agent_eval_lab/graders/execution.py`

- [ ] **Step 5.1: Extend the test imports and append the failing tests**

In `tests/graders/test_execution.py`, replace exactly this block:

```python
from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    OverlaidTree,
    OverlayCollision,
    overlay_oracle,
)
```

with:

```python
from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    OverlaidTree,
    OverlayCollision,
    execution_hash,
    overlay_oracle,
)
```

Then append to the end of the file:

```python
# --- execution hash (ADR-0011) ---


def test_execution_hash_is_deterministic() -> None:
    assert execution_hash(SPEC, TREE) == execution_hash(SPEC, TREE)


def test_execution_hash_changes_with_oracle_path_content_tree_and_timeout() -> None:
    base = execution_hash(SPEC, TREE)
    other_path = ExecutionSpec(
        held_out_tests={"test_other.py": ORACLE["test_oracle_calc.py"]}
    )
    other_content = ExecutionSpec(held_out_tests={"test_oracle_calc.py": "changed\n"})
    other_timeout = ExecutionSpec(held_out_tests=ORACLE, timeout_s=10.0)
    assert execution_hash(other_path, TREE) != base
    assert execution_hash(other_content, TREE) != base
    assert execution_hash(SPEC, {**TREE, "extra.py": ""}) != base
    assert execution_hash(other_timeout, TREE) != base


def test_execution_hash_covers_raw_timeout_none_vs_explicit_default() -> None:
    # None and the edge default (10.0) hash apart: dedup is a non-goal.
    explicit = ExecutionSpec(held_out_tests=ORACLE, timeout_s=10.0)
    assert execution_hash(SPEC, TREE) != execution_hash(explicit, TREE)


def test_execution_hash_is_well_defined_when_overlay_would_collide() -> None:
    colliding_tree = {"Test_oracle_calc.py": "agent\n"}
    assert isinstance(overlay_oracle(colliding_tree, ORACLE), OverlayCollision)
    assert execution_hash(SPEC, colliding_tree) == execution_hash(
        SPEC, dict(colliding_tree)
    )
```

- [ ] **Step 5.2: Run the tests to verify they fail**

Run: `uv run pytest tests/graders/test_execution.py`
Expected: FAIL — collection error, `ImportError: cannot import name 'execution_hash'`.

- [ ] **Step 5.3: Implement the hash**

In `src/agent_eval_lab/graders/execution.py`, replace exactly this block:

```python
from collections.abc import Mapping
from dataclasses import dataclass

from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.tools.code_world import prefix_collision
```

with:

```python
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.tasks.schema import ExecutionSpec
from agent_eval_lab.tools.code_world import prefix_collision
```

Then append to the end of the file:

```python
def execution_hash(spec: ExecutionSpec, final_tree: Mapping[str, str]) -> str:
    """sha256 over canonical JSON of oracle tests + final tree + raw timeout_s.

    The `prompt_hash` convention (ADR-0011): computable on both sides of the
    boundary, well-defined even when the overlay would collide, and covering
    the RAW `timeout_s` field (null when None), never the edge default.
    """
    blob = json.dumps(
        {
            "held_out_tests": dict(spec.held_out_tests),
            "final_tree": dict(final_tree),
            "timeout_s": spec.timeout_s,
        },
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

- [ ] **Step 5.4: Run the tests to verify they pass**

Run: `uv run pytest tests/graders/test_execution.py && uv run ruff check .`
Expected: `9 passed`; `All checks passed!`

- [ ] **Step 5.5: Commit**

```bash
git add tests/graders/test_execution.py src/agent_eval_lab/graders/execution.py
git commit -m "feat(graders): execution_hash — canonical-JSON content hash (ADR-0011)"
```

---

### Task 6: Collector + pure grader (`graders/execution.py`, part 3)

**Files:**
- Modify: `tests/graders/test_execution.py`
- Modify: `src/agent_eval_lab/graders/execution.py`

- [ ] **Step 6.1: Finalize the test imports and append the failing tests**

In `tests/graders/test_execution.py`, replace exactly this block:

```python
"""Pure execution-grading core: overlay, hash, collector, grader (no sandbox)."""

from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    OverlaidTree,
    OverlayCollision,
    execution_hash,
    overlay_oracle,
)
from agent_eval_lab.records.execution import ExecutionResult, TestCaseResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import ExecutionSpec
```

with:

```python
"""Pure execution-grading core: overlay, hash, collector, grader (no sandbox)."""

import typing

from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    OverlaidTree,
    OverlayCollision,
    collect_execution_specs,
    execution_hash,
    grade_execution,
    overlay_oracle,
)
from agent_eval_lab.records.execution import ExecutionResult, TestCaseResult
from agent_eval_lab.records.grade import FailureCategory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import AllOf, ExecutionSpec, TrajectorySpec
```

Then append to the end of the file:

```python
# --- spec collector ---


def test_collect_execution_specs_finds_nested_specs_in_order() -> None:
    other = ExecutionSpec(held_out_tests={"test_b.py": "def test_b():\n    pass\n"})
    tree = AllOf(
        specs=(
            TrajectorySpec(constraints=()),
            AllOf(specs=(SPEC,)),
            other,
        )
    )
    assert collect_execution_specs(tree) == (SPEC, other)


def test_collect_execution_specs_returns_empty_for_non_execution_specs() -> None:
    assert collect_execution_specs(TrajectorySpec(constraints=())) == ()


# --- pure grader ---


def test_grade_execution_passes_when_suite_passed_with_full_evidence() -> None:
    key = execution_hash(SPEC, TREE)
    verdict = ExecutionVerdict(
        result=PASSED_RESULT, execution_hash=key, displaced_paths=("displaced.py",)
    )
    grade = grade_execution(
        spec=SPEC, trajectory=_trajectory({"files": TREE}), verdicts={key: verdict}
    )
    assert grade.grader_id == "execution"
    assert grade.passed is True
    assert grade.score == 1.0
    assert grade.failure_reason is None
    assert grade.evidence == {
        "execution": "run",
        "status": "passed",
        "exit_code": 0,
        "counts": {"passed": 1, "failed": 0, "errors": 0, "skipped": 0},
        "tests": [["test_oracle_calc::test_add", "passed"]],
        "stdout": "1 passed in <duration>",
        "stderr": "",
        "execution_hash": key,
        "displaced_paths": ["displaced.py"],
    }


def test_grade_execution_fails_on_failed_suite_with_no_failure_reason() -> None:
    key = execution_hash(SPEC, TREE)
    grade = grade_execution(
        spec=SPEC,
        trajectory=_trajectory({"files": TREE}),
        verdicts={key: _verdict(FAILED_RESULT, key)},
    )
    assert grade.passed is False
    assert grade.score == 0.0
    assert grade.failure_reason is None
    assert grade.evidence["execution"] == "run"
    assert grade.evidence["status"] == "failed"


def test_grade_execution_missing_final_state_short_circuits_before_lookup() -> None:
    grade = grade_execution(spec=SPEC, trajectory=_trajectory(None), verdicts={})
    assert grade.passed is False
    assert grade.evidence == {"execution": "not_run", "reason": "missing_final_state"}


def test_grade_execution_treats_missing_files_key_as_empty_tree() -> None:
    key = execution_hash(SPEC, {})
    grade = grade_execution(
        spec=SPEC,
        trajectory=_trajectory({"not_files": 1}),
        verdicts={key: _verdict(FAILED_RESULT, key)},
    )
    assert grade.passed is False
    assert grade.evidence["execution"] == "run"


def test_grade_execution_reports_verdict_missing_with_hash() -> None:
    key = execution_hash(SPEC, TREE)
    grade = grade_execution(
        spec=SPEC, trajectory=_trajectory({"files": TREE}), verdicts={}
    )
    assert grade.passed is False
    assert grade.evidence == {
        "execution": "not_run",
        "reason": "verdict_missing",
        "execution_hash": key,
    }


def test_grade_execution_is_total_over_foreign_values_at_the_key() -> None:
    from agent_eval_lab.graders.judge import JudgeVerdict

    key = execution_hash(SPEC, TREE)
    foreign = JudgeVerdict(
        score=5, rationale="r", raw="SCORE: 5", judge_model="m", prompt_hash=key
    )
    grade = grade_execution(
        spec=SPEC, trajectory=_trajectory({"files": TREE}), verdicts={key: foreign}
    )
    assert grade.passed is False
    assert grade.evidence["execution"] == "error"
    assert grade.evidence["execution_error"]["kind"] == "unknown"


def test_failure_category_member_set_is_unchanged() -> None:
    assert typing.get_args(FailureCategory) == (
        "malformed_call",
        "schema_violation",
        "wrong_tool",
        "wrong_args",
        "missing_call",
        "extra_call",
        "order_mismatch",
        "forbidden_action",
        "step_limit_exceeded",
    )


def test_execution_grader_module_imports_nothing_effectful() -> None:
    import agent_eval_lab.graders.execution as execution_mod

    src = open(execution_mod.__file__).read()
    assert "subprocess" not in src
    assert "from agent_eval_lab.runners" not in src
    assert "import agent_eval_lab.runners" not in src
```

- [ ] **Step 6.2: Run the tests to verify they fail**

Run: `uv run pytest tests/graders/test_execution.py`
Expected: FAIL — collection error, `ImportError: cannot import name 'collect_execution_specs'`.

- [ ] **Step 6.3: Implement collector and grader**

In `src/agent_eval_lab/graders/execution.py`, replace exactly this block:

```python
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.tasks.schema import ExecutionSpec
from agent_eval_lab.tools.code_world import prefix_collision
```

with:

```python
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.tasks.schema import AllOf, ExecutionSpec, VerificationSpec
from agent_eval_lab.tools.code_world import prefix_collision
```

Then append to the end of the file:

```python
def collect_execution_specs(
    verification: VerificationSpec,
) -> tuple[ExecutionSpec, ...]:
    """Pure walk of the spec tree (recurses AllOf, the judge-collector precedent)."""
    if isinstance(verification, ExecutionSpec):
        return (verification,)
    if isinstance(verification, AllOf):
        return tuple(
            spec for sub in verification.specs for spec in collect_execution_specs(sub)
        )
    return ()


def grade_execution(
    *,
    spec: ExecutionSpec,
    trajectory: Trajectory,
    verdicts: Mapping[str, Any],
) -> GradeResult:
    """Read the precomputed verdict and interpret it. No I/O, total."""
    if trajectory.final_state is None:
        return _non_pass({"execution": "not_run", "reason": "missing_final_state"})
    final_tree = trajectory.final_state.get("files", {})
    key = execution_hash(spec, final_tree)
    value = verdicts.get(key)
    if value is None:
        return _non_pass(
            {
                "execution": "not_run",
                "reason": "verdict_missing",
                "execution_hash": key,
            }
        )
    if not isinstance(value, ExecutionVerdict):
        return _non_pass(_error_evidence(key, value))
    return _interpret(value)


def _interpret(verdict: ExecutionVerdict) -> GradeResult:
    result = verdict.result
    passed = result.status == "passed"
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={
            "execution": "run",
            "status": result.status,
            "exit_code": result.exit_code,
            "counts": {
                "passed": result.passed,
                "failed": result.failed,
                "errors": result.errors,
                "skipped": result.skipped,
            },
            "tests": [[case.test_id, case.status] for case in result.tests],
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_hash": verdict.execution_hash,
            "displaced_paths": list(verdict.displaced_paths),
        },
        failure_reason=None,
    )


def _error_evidence(key: str, value: Any) -> dict[str, Any]:
    # An ExecutionError (or ANY foreign value, e.g. a JudgeVerdict on a
    # pathological hash collision) at the key: structured error evidence with
    # kind "unknown" as the getattr fallback — the judge precedent. The
    # three-valued evidence["execution"] ("run" | "not_run" | "error") is the
    # MECHANICAL DISCRIMINATOR item 004's classifier reads.
    return {
        "execution": "error",
        "execution_error": {
            "kind": getattr(value, "kind", "unknown"),
            "detail": getattr(value, "detail", repr(value)),
        },
        "execution_hash": key,
    }


def _non_pass(evidence: Mapping[str, Any]) -> GradeResult:
    # Every execution non-pass is an outcome miss or infra record, never a
    # policy breach: failure_reason stays None (the closed taxonomy untouched).
    return GradeResult(
        grader_id=GRADER_ID,
        passed=False,
        score=0.0,
        evidence=evidence,
        failure_reason=None,
    )
```

(The module is now complete at 175 lines — under the ~200-line budget.)

- [ ] **Step 6.4: Run the tests to verify they pass**

Run: `uv run pytest tests/graders/test_execution.py && uv run ruff check .`
Expected: `19 passed`; `All checks passed!`

- [ ] **Step 6.5: Commit**

```bash
git add tests/graders/test_execution.py src/agent_eval_lab/graders/execution.py
git commit -m "feat(graders): pure grade_execution + collect_execution_specs"
```

---

### Task 7: Hypothesis properties for overlay and hash

These properties verify behavior already specified by Tasks 4–6's unit tests, so they are expected GREEN on arrival. If any property fails, STOP and fix the core — never weaken the property.

**Files:**
- Create: `tests/graders/test_execution_properties.py`

- [ ] **Step 7.1: Write the property tests**

Create `tests/graders/test_execution_properties.py` with exactly:

```python
"""Hypothesis properties for the pure overlay and execution hash."""

import copy

from hypothesis import assume, given
from hypothesis import strategies as st

from agent_eval_lab.graders.execution import (
    OverlaidTree,
    execution_hash,
    overlay_oracle,
)
from agent_eval_lab.tasks.schema import ExecutionSpec

_SEGMENTS = st.text(alphabet="abcdefgh", min_size=1, max_size=6)
_PATHS = st.lists(_SEGMENTS, min_size=1, max_size=3).map("/".join)
_CONTENTS = st.text(max_size=50)
_TREES = st.dictionaries(_PATHS, _CONTENTS, max_size=4)
_ORACLES = st.dictionaries(_PATHS, _CONTENTS, min_size=1, max_size=4)
_TIMEOUTS = st.one_of(
    st.none(), st.floats(min_value=0.1, max_value=120.0, allow_nan=False)
)


@given(tree=_TREES, oracle=_ORACLES)
def test_overlay_never_mutates_inputs(
    tree: dict[str, str], oracle: dict[str, str]
) -> None:
    tree_snapshot = copy.deepcopy(tree)
    oracle_snapshot = copy.deepcopy(oracle)
    overlay_oracle(tree, oracle)
    assert tree == tree_snapshot
    assert oracle == oracle_snapshot


@given(tree=_TREES, oracle=_ORACLES)
def test_overlay_oracle_content_always_wins_and_displacement_is_the_overlap(
    tree: dict[str, str], oracle: dict[str, str]
) -> None:
    # Lowercase-only path alphabet => no canonical collisions are generable,
    # so the overlay always combines.
    overlaid = overlay_oracle(tree, oracle)
    assert isinstance(overlaid, OverlaidTree)
    assert overlaid.displaced_paths == tuple(sorted(set(tree) & set(oracle)))
    for path, content in oracle.items():
        assert overlaid.files[path] == content
    for path in set(tree) - set(oracle):
        assert overlaid.files[path] == tree[path]


@given(tree=_TREES, oracle=_ORACLES, timeout_s=_TIMEOUTS)
def test_execution_hash_is_deterministic(
    tree: dict[str, str], oracle: dict[str, str], timeout_s: float | None
) -> None:
    spec = ExecutionSpec(held_out_tests=oracle, timeout_s=timeout_s)
    again = ExecutionSpec(held_out_tests=dict(oracle), timeout_s=timeout_s)
    assert execution_hash(spec, tree) == execution_hash(again, dict(tree))


@given(tree=_TREES, oracle=_ORACLES, new_content=_CONTENTS)
def test_execution_hash_changes_when_any_oracle_content_changes(
    tree: dict[str, str], oracle: dict[str, str], new_content: str
) -> None:
    path = sorted(oracle)[0]
    assume(oracle[path] != new_content)
    spec = ExecutionSpec(held_out_tests=oracle)
    mutated = ExecutionSpec(held_out_tests={**oracle, path: new_content})
    assert execution_hash(spec, tree) != execution_hash(mutated, tree)


@given(tree=_TREES, oracle=_ORACLES, extra=_PATHS, content=_CONTENTS)
def test_execution_hash_changes_when_the_final_tree_changes(
    tree: dict[str, str], oracle: dict[str, str], extra: str, content: str
) -> None:
    changed = {**tree, extra: content}
    assume(changed != tree)
    spec = ExecutionSpec(held_out_tests=oracle)
    assert execution_hash(spec, tree) != execution_hash(spec, changed)
```

- [ ] **Step 7.2: Run the property tests**

Run: `uv run pytest tests/graders/test_execution_properties.py && uv run ruff check .`
Expected: `5 passed` (≈0.5 s); `All checks passed!`

- [ ] **Step 7.3: Commit**

```bash
git add tests/graders/test_execution_properties.py
git commit -m "test(graders): overlay + execution-hash hypothesis properties"
```

---

### Task 8: The oracle edge — `runners/oracle_edge.py`

**Files:**
- Create: `tests/runners/test_oracle_edge.py`
- Modify: `tests/graders/test_execution.py` (insert one test)
- Create: `src/agent_eval_lab/runners/oracle_edge.py`

- [ ] **Step 8.1: Write the failing edge tests**

Create `tests/runners/test_oracle_edge.py` with exactly:

```python
"""Oracle edge: precompute integration over real sandboxed pytest (ADR-0010/0011)."""

import dataclasses
import json

import pytest

from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    execution_hash,
    grade_execution,
)
from agent_eval_lab.records.serialize import grade_result_to_dict
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.oracle_edge import (
    ExecutionError,
    precompute_execution_verdicts,
)
from agent_eval_lab.tasks.schema import AllOf, ExecutionSpec, TrajectorySpec

ORACLE = {
    "test_oracle_calc.py": (
        "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
}

FIXED_TREE = {"calc.py": "def add(a, b):\n    return a + b\n"}
BROKEN_TREE = {"calc.py": "def add(a, b):\n    return a - b\n"}

SPEC = ExecutionSpec(held_out_tests=ORACLE)


def _trajectory(final_state) -> Trajectory:
    return Trajectory(
        turns=(MessageTurn(role="assistant", content="done"),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def _single_verdict(verification, final_state):
    verdicts = precompute_execution_verdicts(
        verification=verification, trajectory=_trajectory(final_state)
    )
    assert len(verdicts) == 1
    return next(iter(verdicts.values()))


def test_execution_error_is_frozen() -> None:
    error = ExecutionError(kind="harness", detail="boom", execution_hash="h")
    with pytest.raises(dataclasses.FrozenInstanceError):
        error.detail = "other"  # type: ignore[misc]


def test_precompute_returns_empty_map_when_no_execution_specs() -> None:
    verdicts = precompute_execution_verdicts(
        verification=TrajectorySpec(constraints=()),
        trajectory=_trajectory({"files": FIXED_TREE}),
    )
    assert verdicts == {}


def test_precompute_returns_empty_map_when_final_state_is_none() -> None:
    verdicts = precompute_execution_verdicts(
        verification=SPEC, trajectory=_trajectory(None)
    )
    assert verdicts == {}


def test_precompute_keys_the_verdict_by_the_grader_side_hash() -> None:
    verdicts = precompute_execution_verdicts(
        verification=SPEC, trajectory=_trajectory({"files": FIXED_TREE})
    )
    key = execution_hash(SPEC, FIXED_TREE)
    assert sorted(verdicts) == [key]
    assert verdicts[key].execution_hash == key


def test_oracle_pass_yields_passed_verdict() -> None:
    verdict = _single_verdict(SPEC, {"files": FIXED_TREE})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "passed"
    assert verdict.displaced_paths == ()


def test_oracle_fail_yields_failed_verdict() -> None:
    verdict = _single_verdict(SPEC, {"files": BROKEN_TREE})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "failed"
    assert verdict.result.failed == 1


def test_collection_error_yields_error_verdict() -> None:
    spec = ExecutionSpec(
        held_out_tests={
            "test_oracle_app.py": (
                "import missing_dependency\n\n\ndef test_app():\n    assert True\n"
            )
        }
    )
    verdict = _single_verdict(spec, {"files": {"app.py": "x = 1\n"}})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "error"
    assert verdict.result.exit_code == 2


def test_per_spec_timeout_yields_timeout_verdict() -> None:
    spec = ExecutionSpec(
        held_out_tests={
            "test_oracle_slow.py": (
                "from slow import busy\n\n\ndef test_busy():\n    assert busy() == 1\n"
            )
        },
        timeout_s=1.0,
    )
    tree = {
        "slow.py": ("import time\n\n\ndef busy():\n    time.sleep(30)\n    return 1\n")
    }
    verdict = _single_verdict(spec, {"files": tree})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "timeout"


def test_oracle_collecting_nothing_yields_no_tests_verdict() -> None:
    spec = ExecutionSpec(held_out_tests={"test_oracle_empty.py": "HELPER = 1\n"})
    verdict = _single_verdict(spec, {"files": FIXED_TREE})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "no_tests"


def test_displaced_oracle_path_runs_oracle_content() -> None:
    # The agent pre-wrote a trivial suite at the oracle's path over a BROKEN
    # repair: agent-wins would pass; oracle-wins fails — the reward-hack probe.
    tree = {
        **BROKEN_TREE,
        "test_oracle_calc.py": "def test_fake():\n    assert True\n",
    }
    verdict = _single_verdict(SPEC, {"files": tree})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "failed"
    assert verdict.displaced_paths == ("test_oracle_calc.py",)


def test_tree_collision_yields_structured_execution_error() -> None:
    spec = ExecutionSpec(
        held_out_tests={"tests/test_app.py": "def test_real():\n    assert True\n"}
    )
    tree = {"Tests/test_app.py": "def test_fake():\n    assert True\n"}
    verdict = _single_verdict(spec, {"files": tree})
    assert verdict == ExecutionError(
        kind="tree_collision",
        detail=(
            "canonical-prefix collision: "
            "agent 'Tests/test_app.py' vs oracle 'tests/test_app.py'"
        ),
        execution_hash=execution_hash(spec, tree),
    )


def test_agent_internal_collision_is_captured_as_harness_error() -> None:
    # A hand-authored fixture defect the pure tools would never produce:
    # two agent paths colliding with each other (not with the oracle) reach
    # the materializer's guard; the RuntimeError is captured, never raised.
    tree = {"Lib/a.py": "x = 1\n", "lib/b.py": "y = 2\n"}
    verdict = _single_verdict(SPEC, {"files": tree})
    assert isinstance(verdict, ExecutionError)
    assert verdict.kind == "harness"
    assert "collision" in verdict.detail


def test_all_of_precomputes_every_reachable_execution_spec() -> None:
    other = ExecutionSpec(
        held_out_tests={"test_oracle_other.py": "def test_ok():\n    assert True\n"}
    )
    verification = AllOf(specs=(SPEC, TrajectorySpec(constraints=()), other))
    verdicts = precompute_execution_verdicts(
        verification=verification, trajectory=_trajectory({"files": FIXED_TREE})
    )
    assert sorted(verdicts) == sorted(
        [execution_hash(SPEC, FIXED_TREE), execution_hash(other, FIXED_TREE)]
    )


def test_edge_plus_grader_pipeline_is_byte_identical_across_runs() -> None:
    # MASTER-SPEC hard constraint made executable: same (spec, trajectory)
    # twice through the full pipeline => byte-identical serialized GradeResult.
    def _grade_bytes() -> bytes:
        trajectory = _trajectory({"files": BROKEN_TREE})
        verdicts = precompute_execution_verdicts(
            verification=SPEC, trajectory=trajectory
        )
        grade = grade_execution(spec=SPEC, trajectory=trajectory, verdicts=verdicts)
        return json.dumps(grade_result_to_dict(grade), sort_keys=True).encode()

    assert _grade_bytes() == _grade_bytes()
```

- [ ] **Step 8.2: Insert the grader-side `ExecutionError` test**

In `tests/graders/test_execution.py`, replace exactly this block:

```python
def test_grade_execution_is_total_over_foreign_values_at_the_key() -> None:
```

with:

```python
def test_grade_execution_reports_structured_error_for_execution_error() -> None:
    from agent_eval_lab.runners.oracle_edge import ExecutionError

    key = execution_hash(SPEC, TREE)
    error = ExecutionError(kind="tree_collision", detail="boom", execution_hash=key)
    grade = grade_execution(
        spec=SPEC, trajectory=_trajectory({"files": TREE}), verdicts={key: error}
    )
    assert grade.passed is False
    assert grade.evidence == {
        "execution": "error",
        "execution_error": {"kind": "tree_collision", "detail": "boom"},
        "execution_hash": key,
    }


def test_grade_execution_is_total_over_foreign_values_at_the_key() -> None:
```

(This test could not exist before now: `ExecutionError` lives in the edge module, mirroring `JudgeError` in `judge_edge`. The pure grader itself still never imports it — it discriminates via `getattr`, which the foreign-value test pins.)

- [ ] **Step 8.3: Run the tests to verify they fail**

Run: `uv run pytest tests/runners/test_oracle_edge.py tests/graders/test_execution.py`
Expected: FAIL — both files error at collection with `ModuleNotFoundError: No module named 'agent_eval_lab.runners.oracle_edge'`.

- [ ] **Step 8.4: Implement the oracle edge**

Create `src/agent_eval_lab/runners/oracle_edge.py` with exactly:

```python
"""EDGE: the oracle precompute boundary (ADR-0010, ADR-0011).

Collect the reachable ExecutionSpecs, overlay each onto the trajectory's
final tree (pure, oracle-wins), run the execution edge's sandboxed pytest,
and emit a verdict map keyed by execution_hash — post-trajectory, because
the final tree is only knowable then. An exception never escapes into the
map: every failure is a serializable ExecutionError at the same key (the
judge-edge precedent). Distinct from the execution edge (pytest_edge), the
sandbox boundary this module calls.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    OverlayCollision,
    collect_execution_specs,
    execution_hash,
    overlay_oracle,
)
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.runners.pytest_edge import DEFAULT_TIMEOUT_S, run_pytest
from agent_eval_lab.tasks.schema import ExecutionSpec, VerificationSpec


@dataclass(frozen=True, kw_only=True)
class ExecutionError:
    """Serializable precompute failure at the verdict key (never an exception)."""

    kind: Literal["tree_collision", "harness"]
    detail: str
    execution_hash: str


def _collision_detail(collision: OverlayCollision) -> str:
    pairs = ", ".join(
        f"agent {agent!r} vs oracle {oracle!r}" for agent, oracle in collision.pairs
    )
    return f"canonical-prefix collision: {pairs}"


def _verdict_for(
    *, spec: ExecutionSpec, final_tree: Mapping[str, str], key: str
) -> ExecutionVerdict | ExecutionError:
    overlaid = overlay_oracle(final_tree, spec.held_out_tests)
    if isinstance(overlaid, OverlayCollision):
        return ExecutionError(
            kind="tree_collision",
            detail=_collision_detail(overlaid),
            execution_hash=key,
        )
    timeout_s = spec.timeout_s if spec.timeout_s is not None else DEFAULT_TIMEOUT_S
    try:
        result = run_pytest(overlaid.files, timeout_s=timeout_s)
    except Exception as exc:  # an exception never escapes into the map
        return ExecutionError(kind="harness", detail=repr(exc), execution_hash=key)
    return ExecutionVerdict(
        result=result,
        execution_hash=key,
        displaced_paths=overlaid.displaced_paths,
    )


def _entry(
    spec: ExecutionSpec, final_tree: Mapping[str, str]
) -> tuple[str, ExecutionVerdict | ExecutionError]:
    key = execution_hash(spec, final_tree)
    return key, _verdict_for(spec=spec, final_tree=final_tree, key=key)


def precompute_execution_verdicts(
    *, verification: VerificationSpec, trajectory: Trajectory
) -> dict[str, ExecutionVerdict | ExecutionError]:
    """Build the verdict-map contribution for every reachable ExecutionSpec.

    Returns {} when no ExecutionSpec is reachable or final_state is None —
    the grader then reports its own structured non-pass without any lookup.
    """
    specs = collect_execution_specs(verification)
    if not specs or trajectory.final_state is None:
        return {}
    final_tree = trajectory.final_state.get("files", {})
    return dict(_entry(spec, final_tree) for spec in specs)
```

- [ ] **Step 8.5: Run the tests to verify they pass**

Run: `uv run pytest tests/runners/test_oracle_edge.py tests/graders/test_execution.py && uv run ruff check .`
Expected: `34 passed` (14 edge + 20 grader; ≈2 s — nine real pytest subprocesses including the ~1.2 s timeout case); `All checks passed!`

- [ ] **Step 8.6: Commit**

```bash
git add tests/runners/test_oracle_edge.py tests/graders/test_execution.py src/agent_eval_lab/runners/oracle_edge.py
git commit -m "feat(runners): oracle edge — precompute execution verdicts (ADR-0010/0011)"
```

---

### Task 9: Serializer tags for the new verdict records

**Files:**
- Modify: `tests/records/test_serialize.py` (append)
- Modify: `src/agent_eval_lab/records/serialize.py`

- [ ] **Step 9.1: Append the failing tests**

Append to the end of `tests/records/test_serialize.py`:

```python
def test_execution_verdict_round_trips_under_its_own_tag() -> None:
    import json

    from agent_eval_lab.graders.execution import ExecutionVerdict
    from agent_eval_lab.records.execution import ExecutionResult, TestCaseResult
    from agent_eval_lab.records.serialize import verdict_from_dict, verdict_to_dict

    v = ExecutionVerdict(
        result=ExecutionResult(
            status="failed",
            exit_code=1,
            passed=1,
            failed=1,
            errors=0,
            skipped=0,
            tests=(
                TestCaseResult(test_id="test_calc::test_add", status="failed"),
                TestCaseResult(test_id="test_calc::test_zero", status="passed"),
            ),
            stdout="1 failed, 1 passed in <duration>",
            stderr="",
        ),
        execution_hash="deadbeef",
        displaced_paths=("tests/test_app.py",),
    )
    data = verdict_to_dict(v)
    assert data["type"] == "execution_verdict"
    assert json.loads(json.dumps(data)) == data
    assert verdict_from_dict(data) == v


def test_execution_error_round_trips_under_its_own_tag() -> None:
    import json

    from agent_eval_lab.records.serialize import verdict_from_dict, verdict_to_dict
    from agent_eval_lab.runners.oracle_edge import ExecutionError

    e = ExecutionError(
        kind="tree_collision",
        detail="agent 'Tests/a' vs oracle 'tests/a'",
        execution_hash="deadbeef",
    )
    data = verdict_to_dict(e)
    assert data["type"] == "execution_error"
    assert json.loads(json.dumps(data)) == data
    assert verdict_from_dict(data) == e


def test_judge_legacy_verdict_tag_is_frozen() -> None:
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.records.serialize import verdict_to_dict

    v = JudgeVerdict(
        score=4, rationale="r", raw="SCORE: 4", judge_model="m", prompt_hash="h"
    )
    # Renaming the legacy tag would break round-trips of existing artifacts.
    assert verdict_to_dict(v)["type"] == "verdict"
```

- [ ] **Step 9.2: Run the tests to verify they fail**

Run: `uv run pytest tests/records/test_serialize.py`
Expected: FAIL — `2 failed, 11 passed`. The two round-trip tests hit `ValueError: not a judge value: …`; the legacy-tag test passes already (it pins existing behavior so it can never silently change).

- [ ] **Step 9.3: Extend the serializer**

In `src/agent_eval_lab/records/serialize.py`, replace exactly this block (the whole `verdict_to_dict` + `verdict_from_dict` pair at the end of the file):

```python
def verdict_to_dict(value: Any) -> dict[str, Any]:
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.runners.judge_edge import JudgeError

    if isinstance(value, JudgeVerdict):
        return {
            "type": "verdict",
            "score": value.score,
            "rationale": value.rationale,
            "raw": value.raw,
            "judge_model": value.judge_model,
            "prompt_hash": value.prompt_hash,
        }
    if isinstance(value, JudgeError):
        return {
            "type": "judge_error",
            "kind": value.kind,
            "error": value.error,
            "prompt_hash": value.prompt_hash,
            "judge_model": value.judge_model,
        }
    raise ValueError(f"not a judge value: {value!r}")


def verdict_from_dict(data: Mapping[str, Any]) -> Any:
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.runners.judge_edge import JudgeError

    if data["type"] == "verdict":
        return JudgeVerdict(
            score=data["score"],
            rationale=data["rationale"],
            raw=data["raw"],
            judge_model=data["judge_model"],
            prompt_hash=data["prompt_hash"],
        )
    if data["type"] == "judge_error":
        return JudgeError(
            kind=data["kind"],
            error=data["error"],
            prompt_hash=data["prompt_hash"],
            judge_model=data["judge_model"],
        )
    raise ValueError(f"unknown judge value type: {data['type']!r}")
```

with:

```python
def verdict_to_dict(value: Any) -> dict[str, Any]:
    # The judge's legacy "verdict" tag is frozen as-is: renaming it would
    # break round-trips of existing artifacts (item 002 resolved decision 9).
    from agent_eval_lab.graders.execution import ExecutionVerdict
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.records.execution import execution_result_to_dict
    from agent_eval_lab.runners.judge_edge import JudgeError
    from agent_eval_lab.runners.oracle_edge import ExecutionError

    if isinstance(value, JudgeVerdict):
        return {
            "type": "verdict",
            "score": value.score,
            "rationale": value.rationale,
            "raw": value.raw,
            "judge_model": value.judge_model,
            "prompt_hash": value.prompt_hash,
        }
    if isinstance(value, JudgeError):
        return {
            "type": "judge_error",
            "kind": value.kind,
            "error": value.error,
            "prompt_hash": value.prompt_hash,
            "judge_model": value.judge_model,
        }
    if isinstance(value, ExecutionVerdict):
        return {
            "type": "execution_verdict",
            "result": execution_result_to_dict(value.result),
            "execution_hash": value.execution_hash,
            "displaced_paths": list(value.displaced_paths),
        }
    if isinstance(value, ExecutionError):
        return {
            "type": "execution_error",
            "kind": value.kind,
            "detail": value.detail,
            "execution_hash": value.execution_hash,
        }
    raise ValueError(f"not a verdict value: {value!r}")


def verdict_from_dict(data: Mapping[str, Any]) -> Any:
    from agent_eval_lab.graders.execution import ExecutionVerdict
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.records.execution import execution_result_from_dict
    from agent_eval_lab.runners.judge_edge import JudgeError
    from agent_eval_lab.runners.oracle_edge import ExecutionError

    if data["type"] == "verdict":
        return JudgeVerdict(
            score=data["score"],
            rationale=data["rationale"],
            raw=data["raw"],
            judge_model=data["judge_model"],
            prompt_hash=data["prompt_hash"],
        )
    if data["type"] == "judge_error":
        return JudgeError(
            kind=data["kind"],
            error=data["error"],
            prompt_hash=data["prompt_hash"],
            judge_model=data["judge_model"],
        )
    if data["type"] == "execution_verdict":
        return ExecutionVerdict(
            result=execution_result_from_dict(data["result"]),
            execution_hash=data["execution_hash"],
            displaced_paths=tuple(data["displaced_paths"]),
        )
    if data["type"] == "execution_error":
        return ExecutionError(
            kind=data["kind"],
            detail=data["detail"],
            execution_hash=data["execution_hash"],
        )
    raise ValueError(f"unknown verdict value type: {data['type']!r}")
```

(The imports stay function-local — the existing pattern that keeps `records/` free of import-time dependencies on `graders/`/`runners/`. Only the two `raise` messages change wording; no artifact tag changes.)

- [ ] **Step 9.4: Run the tests to verify they pass**

Run: `uv run pytest tests/records/test_serialize.py && uv run ruff check .`
Expected: `13 passed`; `All checks passed!`

- [ ] **Step 9.5: Commit**

```bash
git add tests/records/test_serialize.py src/agent_eval_lab/records/serialize.py
git commit -m "feat(records): serialize execution_verdict/execution_error tags"
```

---

### Task 10: Dispatch wiring

**Files:**
- Modify: `tests/graders/test_dispatch.py` (append)
- Modify: `src/agent_eval_lab/graders/dispatch.py`

- [ ] **Step 10.1: Append the failing tests**

Append to the end of `tests/graders/test_dispatch.py`:

```python
_EXEC_ORACLE = {
    "test_oracle_calc.py": (
        "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
}
_EXEC_TREE = {"calc.py": "def add(a, b):\n    return a + b\n"}


def _execution_fixture():
    from agent_eval_lab.graders.execution import ExecutionVerdict, execution_hash
    from agent_eval_lab.records.execution import ExecutionResult, TestCaseResult
    from agent_eval_lab.tasks.schema import ExecutionSpec

    spec = ExecutionSpec(held_out_tests=_EXEC_ORACLE)
    key = execution_hash(spec, _EXEC_TREE)
    verdict = ExecutionVerdict(
        result=ExecutionResult(
            status="passed",
            exit_code=0,
            passed=1,
            failed=0,
            errors=0,
            skipped=0,
            tests=(
                TestCaseResult(test_id="test_oracle_calc::test_add", status="passed"),
            ),
            stdout="1 passed in <duration>",
            stderr="",
        ),
        execution_hash=key,
        displaced_paths=(),
    )
    return spec, key, verdict


def test_dispatches_execution_spec_with_supplied_verdict() -> None:
    spec, key, verdict = _execution_fixture()
    trajectory = _state_trajectory({"files": _EXEC_TREE})

    result = grade_trajectory(
        verification=spec,
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        verdicts={key: verdict},
    )

    assert result.passed is True
    assert result.grader_id == "execution"


def test_all_of_grades_execution_leg_beside_policy_leg() -> None:
    spec, key, verdict = _execution_fixture()
    composite = AllOf(
        specs=(spec, TrajectorySpec(constraints=(NoToolCall(name="run_tests"),)))
    )
    trajectory = _state_trajectory({"files": _EXEC_TREE})

    result = grade_trajectory(
        verification=composite,
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        verdicts={key: verdict},
    )

    assert result.passed is True
    subs = result.evidence["sub_results"]
    assert [sub["grader_id"] for sub in subs] == ["execution", "trajectory_policy"]
    assert all(sub["passed"] for sub in subs)


def test_judge_and_execution_verdicts_coexist_in_one_map() -> None:
    from agent_eval_lab.graders.judge import (
        JudgeVerdict,
        build_judge_prompt,
        prompt_hash,
    )
    from agent_eval_lab.tasks.schema import LlmJudgeSpec

    exec_spec, exec_key, exec_verdict = _execution_fixture()
    judge_spec = LlmJudgeSpec(rubric="r", judge_model="m", scale=(1, 5))
    trajectory = _state_trajectory(
        {"files": _EXEC_TREE}, MessageTurn(role="assistant", content="Done.")
    )
    judge_key = prompt_hash(build_judge_prompt(spec=judge_spec, trajectory=trajectory))
    judge_verdict = JudgeVerdict(
        score=5,
        rationale="ok",
        raw="SCORE: 5",
        judge_model="m",
        prompt_hash=judge_key,
    )
    verdicts = {exec_key: exec_verdict, judge_key: judge_verdict}

    result = grade_trajectory(
        verification=AllOf(specs=(exec_spec, judge_spec)),
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        verdicts=verdicts,
    )

    assert result.passed is True
    subs = result.evidence["sub_results"]
    assert [sub["grader_id"] for sub in subs] == ["execution", "llm_judge"]
```

- [ ] **Step 10.2: Run the tests to verify they fail**

Run: `uv run pytest tests/graders/test_dispatch.py`
Expected: FAIL — `3 failed, 12 passed`; each new test hits `ValueError: unsupported verification spec: ExecutionSpec(…)`.

- [ ] **Step 10.3: Add the dispatch branch**

In `src/agent_eval_lab/graders/dispatch.py`, replace exactly this block:

```python
from agent_eval_lab.graders.composite import grade_all_of
from agent_eval_lab.graders.exact_match import grade_exact_match
from agent_eval_lab.graders.judge import grade_llm_judge
```

with:

```python
from agent_eval_lab.graders.composite import grade_all_of
from agent_eval_lab.graders.exact_match import grade_exact_match
from agent_eval_lab.graders.execution import grade_execution
from agent_eval_lab.graders.judge import grade_llm_judge
```

Then replace exactly this block:

```python
from agent_eval_lab.tasks.schema import (
    AllOf,
    FinalStateSpec,
    LlmJudgeSpec,
    OutputMatchSpec,
    ToolCallMatchSpec,
    TrajectorySpec,
    VerificationSpec,
)
```

with:

```python
from agent_eval_lab.tasks.schema import (
    AllOf,
    ExecutionSpec,
    FinalStateSpec,
    LlmJudgeSpec,
    OutputMatchSpec,
    ToolCallMatchSpec,
    TrajectorySpec,
    VerificationSpec,
)
```

Then replace exactly this block:

```python
    if isinstance(verification, LlmJudgeSpec):
        return grade_llm_judge(
            spec=verification, trajectory=trajectory, verdicts=verdicts
        )
```

with:

```python
    if isinstance(verification, LlmJudgeSpec):
        return grade_llm_judge(
            spec=verification, trajectory=trajectory, verdicts=verdicts
        )
    if isinstance(verification, ExecutionSpec):
        return grade_execution(
            spec=verification, trajectory=trajectory, verdicts=verdicts
        )
```

- [ ] **Step 10.4: Run the tests to verify they pass**

Run: `uv run pytest tests/graders/test_dispatch.py && uv run ruff check .`
Expected: `15 passed`; `All checks passed!` (Note `test_dispatch_module_imports_no_http_client` still passes: the dispatch module imports the pure grader only, never the edge.)

- [ ] **Step 10.5: Commit**

```bash
git add tests/graders/test_dispatch.py src/agent_eval_lab/graders/dispatch.py
git commit -m "feat(graders): dispatch ExecutionSpec through the shared verdict map"
```

---

### Task 11: Production call site — `multi_run.run_task_k`

**Files:**
- Modify: `tests/runners/test_multi_run.py` (append)
- Modify: `src/agent_eval_lab/runners/multi_run.py`

- [ ] **Step 11.1: Append the failing test**

Append to the end of `tests/runners/test_multi_run.py`:

```python
def _final_message_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": "done"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


def test_run_task_k_precomputes_and_threads_execution_verdicts() -> None:
    """Criterion 13: the oracle edge runs between run_single and grading.

    The model replies immediately, so final_state == initial_state's tree;
    the oracle edge then runs REAL sandboxed pytest over the overlay and the
    pure grader reads its verdict from the threaded map.
    """
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import ExecutionSpec

    task = Task(
        id="cw-001",
        capability="code_repair",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="Fix calc.add."),),
            available_tools=(),
        ),
        verification=ExecutionSpec(
            held_out_tests={
                "test_oracle_calc.py": (
                    "from calc import add\n"
                    "\n"
                    "\n"
                    "def test_add():\n"
                    "    assert add(1, 2) == 3\n"
                )
            }
        ),
        metadata=TaskMetadata(split="dev", version="2", provenance="hand_written"),
        initial_state={"files": {"calc.py": "def add(a, b):\n    return a + b\n"}},
    )

    results = run_task_k(
        task=task,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=httpx.Client(transport=httpx.MockTransport(_final_message_handler)),
        k=1,
        max_steps=2,
        temperature=0.0,
    )

    grade = results[0].grade
    assert grade.grader_id == "execution"
    assert grade.passed is True
    assert grade.evidence["execution"] == "run"
    assert grade.evidence["status"] == "passed"
```

- [ ] **Step 11.2: Run the test to verify it fails**

Run: `uv run pytest tests/runners/test_multi_run.py`
Expected: FAIL — `1 failed, 6 passed`. The new test reaches the dispatch branch but `run_task_k` threads no verdicts, so the grade is a `verdict_missing` non-pass (`assert grade.passed is True` fails).

- [ ] **Step 11.3: Wire the precompute into `run_task_k`**

In `src/agent_eval_lab/runners/multi_run.py`, replace exactly this block:

```python
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.runners.loop import run_single
```

with:

```python
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.runners.loop import run_single
from agent_eval_lab.runners.oracle_edge import precompute_execution_verdicts
```

Then replace exactly this block:

```python
        grade = grade_trajectory(
            verification=task.verification,
            trajectory=trajectory,
            registry=registry,
            initial_state=task.initial_state,
        )
```

with:

```python
        # ADR-0011: the oracle edge precomputes execution verdicts
        # post-trajectory; {} for tasks with no ExecutionSpec, so
        # non-execution tasks grade byte-identically to before.
        verdicts = precompute_execution_verdicts(
            verification=task.verification, trajectory=trajectory
        )
        grade = grade_trajectory(
            verification=task.verification,
            trajectory=trajectory,
            registry=registry,
            initial_state=task.initial_state,
            verdicts=verdicts,
        )
```

- [ ] **Step 11.4: Run the tests to verify they pass**

Run: `uv run pytest tests/runners/test_multi_run.py tests/runners/test_loop.py tests/graders && uv run ruff check .`
Expected: all pass (`7 passed` for multi_run; loop and grader suites unchanged — criterion 13's "existing tests pass unchanged"); `All checks passed!`

- [ ] **Step 11.5: Commit**

```bash
git add tests/runners/test_multi_run.py src/agent_eval_lab/runners/multi_run.py
git commit -m "feat(runners): multi_run threads oracle-edge verdicts into grading"
```

---

### Task 12: Golden conformance cases (a)–(i) + harness + security test

**Files:**
- Create: `tests/golden/24_execution_oracle_pass.json`
- Create: `tests/golden/25_execution_oracle_fail.json`
- Create: `tests/golden/26_execution_collection_error.json`
- Create: `tests/golden/27_execution_timeout.json`
- Create: `tests/golden/28_execution_no_tests.json`
- Create: `tests/golden/29_execution_oracle_displaces_agent_path.json`
- Create: `tests/golden/30_execution_tree_collision.json`
- Create: `tests/golden/31_execution_missing_final_state.json`
- Create: `tests/golden/32_execution_all_of_with_policy.json`
- Modify: `tests/test_golden_conformance.py` (full-file replacement)

- [ ] **Step 12.1: Write the nine golden cases**

Create `tests/golden/24_execution_oracle_pass.json` with exactly:

```json
{
  "name": "execution: oracle suite passes over the repaired tree",
  "registry": "code_world",
  "verification": {"type": "execution", "held_out_tests": {"test_oracle_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n"}},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "calc.add subtracts; fix it."},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "write_file", "arguments": {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"path": "calc.py", "created": false}}},
    {"type": "message", "role": "assistant", "content": "Fixed add to return a + b."}
  ], "final_state": {"files": {"calc.py": "def add(a, b):\n    return a + b\n"}}},
  "expected": {"passed": true, "failure_reason": null}
}
```

Create `tests/golden/25_execution_oracle_fail.json` with exactly:

```json
{
  "name": "execution: oracle suite fails — the repair is wrong (outcome miss, no failure category)",
  "registry": "code_world",
  "verification": {"type": "execution", "held_out_tests": {"test_oracle_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"}},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "calc.add subtracts; fix it."},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "write_file", "arguments": {"path": "calc.py", "content": "def add(a, b):\n    return a * b\n"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"path": "calc.py", "created": false}}},
    {"type": "message", "role": "assistant", "content": "Rewrote add."}
  ], "final_state": {"files": {"calc.py": "def add(a, b):\n    return a * b\n"}}},
  "expected": {"passed": false, "failure_reason": null}
}
```

Create `tests/golden/26_execution_collection_error.json` with exactly:

```json
{
  "name": "execution: oracle collection/import error — the agent deleted nothing but the module never existed",
  "registry": "code_world",
  "verification": {"type": "execution", "held_out_tests": {"test_oracle_app.py": "from app import handler\n\n\ndef test_handler():\n    assert handler() == 1\n"}},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "Create util.py."},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "write_file", "arguments": {"path": "util.py", "content": "x = 1\n"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"path": "util.py", "created": true}}},
    {"type": "message", "role": "assistant", "content": "Created util.py."}
  ], "final_state": {"files": {"util.py": "x = 1\n"}}},
  "expected": {"passed": false, "failure_reason": null}
}
```

Create `tests/golden/27_execution_timeout.json` with exactly:

```json
{
  "name": "execution: per-spec timeout_s of 1s kills the hung oracle run",
  "registry": "code_world",
  "verification": {"type": "execution", "timeout_s": 1.0, "held_out_tests": {"test_oracle_slow.py": "from slow import busy\n\n\ndef test_busy():\n    assert busy() == 1\n"}},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "Make slow.busy return 1."},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "write_file", "arguments": {"path": "slow.py", "content": "import time\n\n\ndef busy():\n    time.sleep(30)\n    return 1\n"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"path": "slow.py", "created": false}}},
    {"type": "message", "role": "assistant", "content": "busy now returns 1."}
  ], "final_state": {"files": {"slow.py": "import time\n\n\ndef busy():\n    time.sleep(30)\n    return 1\n"}}},
  "expected": {"passed": false, "failure_reason": null}
}
```

Create `tests/golden/28_execution_no_tests.json` with exactly:

```json
{
  "name": "execution: oracle file pytest collects nothing from — an oracle defect surfaced honestly",
  "registry": "code_world",
  "verification": {"type": "execution", "held_out_tests": {"test_oracle_empty.py": "HELPER = 1\n"}},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "calc.add subtracts; fix it."},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "write_file", "arguments": {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"path": "calc.py", "created": false}}},
    {"type": "message", "role": "assistant", "content": "Fixed."}
  ], "final_state": {"files": {"calc.py": "def add(a, b):\n    return a + b\n"}}},
  "expected": {"passed": false, "failure_reason": null}
}
```

Create `tests/golden/29_execution_oracle_displaces_agent_path.json` with exactly:

```json
{
  "name": "execution: agent pre-wrote the oracle path; oracle wins, verdict from oracle content",
  "registry": "code_world",
  "verification": {"type": "execution", "held_out_tests": {"test_oracle_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"}},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "calc.add subtracts; fix it."},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "write_file", "arguments": {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"path": "calc.py", "created": false}}},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c2", "name": "write_file", "arguments": {"path": "test_oracle_calc.py", "content": "def test_fake():\n    assert True\n"}}]},
    {"type": "tool_result", "call_id": "c2", "outcome": {"type": "success", "result": {"path": "test_oracle_calc.py", "created": true}}},
    {"type": "message", "role": "assistant", "content": "Fixed add and added a test."}
  ], "final_state": {"files": {"calc.py": "def add(a, b):\n    return a + b\n", "test_oracle_calc.py": "def test_fake():\n    assert True\n"}}},
  "expected": {"passed": true, "failure_reason": null}
}
```

Create `tests/golden/30_execution_tree_collision.json` with exactly:

```json
{
  "name": "execution: canonical-prefix collision between agent Tests/ and oracle tests/ is a structured non-pass",
  "registry": "code_world",
  "verification": {"type": "execution", "held_out_tests": {"tests/test_app.py": "from app import value\n\n\ndef test_value():\n    assert value() == 1\n"}},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "Make app.value return 1 and add a test."},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "write_file", "arguments": {"path": "app.py", "content": "def value():\n    return 1\n"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"path": "app.py", "created": false}}},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c2", "name": "write_file", "arguments": {"path": "Tests/test_app.py", "content": "def test_value_placeholder():\n    assert True\n"}}]},
    {"type": "tool_result", "call_id": "c2", "outcome": {"type": "success", "result": {"path": "Tests/test_app.py", "created": true}}},
    {"type": "message", "role": "assistant", "content": "Done; tests live in Tests/."}
  ], "final_state": {"files": {"app.py": "def value():\n    return 1\n", "Tests/test_app.py": "def test_value_placeholder():\n    assert True\n"}}},
  "expected": {"passed": false, "failure_reason": null}
}
```

(Note the agent's `Tests/test_app.py` content deliberately differs from the oracle's file — the security test below asserts oracle contents never appear in any turn.)

Create `tests/golden/31_execution_missing_final_state.json` with exactly:

```json
{
  "name": "execution: missing final_state is a structured not_run non-pass",
  "registry": "code_world",
  "verification": {"type": "execution", "held_out_tests": {"test_oracle_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"}},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "calc.add subtracts; fix it."},
    {"type": "message", "role": "assistant", "content": "I could not access the files."}
  ], "final_state": null},
  "expected": {"passed": false, "failure_reason": null}
}
```

Create `tests/golden/32_execution_all_of_with_policy.json` with exactly:

```json
{
  "name": "all_of: execution leg beside a trajectory policy leg — both graded, both pass",
  "registry": "code_world",
  "verification": {"type": "all_of", "specs": [
    {"type": "execution", "held_out_tests": {"test_oracle_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"}},
    {"type": "trajectory", "constraints": [{"type": "no_tool_call", "name": "run_tests"}]}
  ]},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "Fix calc.add without running the visible tests."},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "write_file", "arguments": {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"path": "calc.py", "created": false}}},
    {"type": "message", "role": "assistant", "content": "Fixed add without running tests."}
  ], "final_state": {"files": {"calc.py": "def add(a, b):\n    return a + b\n"}}},
  "expected": {"passed": true, "failure_reason": null}
}
```

(Every execution golden expects `failure_reason: null` — criterion 9/14. Cases 25/26/27/28 are outcome misses; 30/31 are infra records; none is a policy breach.)

- [ ] **Step 12.2: Run the conformance suite to verify it fails**

Run: `uv run pytest tests/test_golden_conformance.py`
Expected: FAIL — at minimum `test_golden_suite_is_present` (32 files ≠ the old asserted 23) and the three passing execution cases 24/29/32 (the old harness threads no verdicts, so they grade `verdict_missing` non-pass).

- [ ] **Step 12.3: Rewrite the harness**

Replace the entire content of `tests/test_golden_conformance.py` with exactly:

```python
"""Golden conformance suite: hand-verified trajectories with known grades.

Each JSON case carries a verification spec, a trajectory, and the
hand-verified expected grade. The harness must reproduce the oracle.
Execution cases (item 002) carry `"registry": "code_world"` and grade
through the PRODUCTION oracle edge — real sandboxed pytest per case,
deterministic by ADR-0009.
"""

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.graders.execution import collect_execution_specs
from agent_eval_lab.records.serialize import trajectory_from_dict
from agent_eval_lab.runners.oracle_edge import precompute_execution_verdicts
from agent_eval_lab.tasks.parse import verification_from_dict
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDEN_CASES = sorted(GOLDEN_DIR.glob("*.json"))

REGISTRIES = {"workspace": WORKSPACE_TOOLS, "code_world": CODE_WORLD_TOOLS}


def test_golden_suite_is_present() -> None:
    assert len(GOLDEN_CASES) == 32


@pytest.mark.parametrize("path", GOLDEN_CASES, ids=lambda p: p.stem)
def test_golden_conformance(path: Path) -> None:
    case = json.loads(path.read_text())
    verification = verification_from_dict(case["verification"])
    trajectory = trajectory_from_dict(case["trajectory"])

    grade = grade_trajectory(
        verification=verification,
        trajectory=trajectory,
        registry=REGISTRIES[case.get("registry", "workspace")],
        initial_state=case.get("initial_state"),
        verdicts=precompute_execution_verdicts(
            verification=verification, trajectory=trajectory
        ),
    )

    assert grade.passed == case["expected"]["passed"], (
        f"{case['name']}: passed={grade.passed!r}, "
        f"expected={case['expected']['passed']!r}"
    )
    assert grade.failure_reason == case["expected"]["failure_reason"], (
        f"{case['name']}: failure_reason={grade.failure_reason!r}, "
        f"expected={case['expected']['failure_reason']!r}"
    )


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def test_oracle_contents_never_appear_in_any_trajectory_turn() -> None:
    """Security constraint: held-out oracle tests are never agent-visible."""
    oracle_files_checked = 0
    for path in GOLDEN_CASES:
        case = json.loads(path.read_text())
        specs = collect_execution_specs(verification_from_dict(case["verification"]))
        turn_texts = _strings(case["trajectory"]["turns"])
        for spec in specs:
            for content in spec.held_out_tests.values():
                assert all(content not in text for text in turn_texts), path.stem
                oracle_files_checked += 1
    assert oracle_files_checked >= 9  # every execution golden was exercised
```

(`precompute_execution_verdicts` returns `{}` for the 23 workspace cases — no sandbox runs, byte-identical grading. The security test walks the *parsed* JSON string values, where oracle file contents would appear raw if they ever leaked into a turn — comparing against the escaped JSON source would be vacuously true.)

- [ ] **Step 12.4: Run the conformance suite to verify it passes**

Run: `uv run pytest tests/test_golden_conformance.py && uv run ruff check .`
Expected: `34 passed` in ≈1.6 s (1 count + 32 cases + 1 security; 10 real sandbox runs — the timeout case contributes ~1.2 s); `All checks passed!`

- [ ] **Step 12.5: Commit**

```bash
git add tests/golden/24_execution_oracle_pass.json tests/golden/25_execution_oracle_fail.json tests/golden/26_execution_collection_error.json tests/golden/27_execution_timeout.json tests/golden/28_execution_no_tests.json tests/golden/29_execution_oracle_displaces_agent_path.json tests/golden/30_execution_tree_collision.json tests/golden/31_execution_missing_final_state.json tests/golden/32_execution_all_of_with_policy.json tests/test_golden_conformance.py
git commit -m "test(golden): nine execution conformance cases through the production oracle edge"
```

---

### Task 13: Final verification gate

- [ ] **Step 13.1: Full suite**

Run: `uv run pytest`
Expected: `528 passed` (no failures, no warnings) in ≈9–12 s.
Count check: 450 baseline + 1 (code_world) + 1 (schema) + 20 (parse) + 20 (graders/test_execution) + 5 (properties) + 14 (oracle edge) + 3 (serialize) + 3 (dispatch) + 1 (multi_run) + 10 (golden: 9 new cases + 1 security) = 528.

- [ ] **Step 13.2: Lint and format gates**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: `All checks passed!` and `99 files already formatted`.

If `ruff format --check` reports a file would be reformatted, a code block was transcribed inexactly: run `uv run ruff format .`, re-run the full suite (`528 passed`), and amend the relevant commit or add a `style:` commit.

- [ ] **Step 13.3: Acceptance-criteria spot audit (no code changes expected)**

- `grep -n "expected_status" src/ -r` → no hits (criterion 1).
- `grep -n "ExecutionSpec extends this union later" src/agent_eval_lab/tasks/schema.py` → no hits (comment retired).
- `grep -rn "subprocess\|import agent_eval_lab.runners" src/agent_eval_lab/graders/execution.py` → no hits (criterion 6; the dedicated test also pins this).
- `git log --oneline` shows one red-green commit per task (criterion 17).

- [ ] **Step 13.4: Nothing to commit**

`git status` should be clean. Do NOT push.

---

## Spec-coverage map (criterion → task)

| Criterion | Task(s) |
|---|---|
| 1 schema variant | 2 |
| 2 parse + structural validation | 3 |
| 3 pure overlay (shared predicate) | 1, 4, 7 |
| 4 pure content hash | 5, 7 |
| 5 verdict channel records + round-trips | 4, 8, 9 |
| 6 pure grader | 6 |
| 7 grader edge cases structured | 6, 8 |
| 8 evidence contract | 6 |
| 9 taxonomy untouched | 6 (member-set test), 12 (`failure_reason: null` goldens) |
| 10 spec collector | 6 |
| 11 oracle edge + integration matrix | 8 |
| 12 dispatch wiring | 10 |
| 13 production call site | 11 |
| 14 golden conformance (a)–(i) | 12 |
| 15 reproducibility (byte-identical) | 8 |
| 16 ADR conformance | already recorded (ADR-0010/0011, commit `aa6e8ed`); implementation conforms by construction |
| 17 TDD evidence | every task |
| Security constraint (oracle secrecy) | 12 (security test); verification never passes through `runners/wire.py` (unchanged) |

## Judgment calls made by this plan (recorded for the reviewer)

1. **`prefix_collision` export is a rename, not an alias** (Task 1). The grill said "one additive public export"; a `prefix_collision = _prefix_collision` alias would leave two names for one function. The rename keeps one name, updates the single internal call site, and changes no behavior — "untouched" meant API stability, not zero diffs (grill resolved decision 8 rationale).
2. **`tests/graders/__init__.py` + `test_judge.py` raw-docstring fix** (Task 4). Not in the spec, but forced by measured collection mechanics: the test-file basename collision aborts pytest, and the package-ification surfaces a pre-existing SyntaxWarning. Both follow existing repo precedent (`tests/runners/__init__.py`) and keep the suite warning-free.
3. **`OverlayCollision.pairs` carries all colliding (agent, oracle) pairs** in sorted order, not just the first — deterministic, and richer `tree_collision` detail for item 004 at no extra cost (spec criterion 3 says "a structured collision report" without pinning arity).
4. **Evidence `counts` is a nested dict** `{"passed", "failed", "errors", "skipped"}` and `tests` is a list of `[test_id, status]` pairs — criterion 8 lists the fields without pinning a shape; the nested form avoids four loose top-level keys colliding with `status`/grade vocabulary, and both shapes are JSON-stable for the byte-identity constraint.
5. **The golden harness calls `precompute_execution_verdicts` unconditionally** (Task 12). For non-execution cases it returns `{}` without any sandbox work, so the 23 legacy cases grade byte-identically — simpler than a conditional and exactly criterion 14's "when the spec tree contains ExecutionSpecs" semantics.
6. **The grader-side `ExecutionError` test lands in Task 8, not Task 6** — the record lives in the edge module (criterion 5's `JudgeError` symmetry), which does not exist before Task 8; the pure grader itself stays import-free of `runners.*` (pinned by its own test).
