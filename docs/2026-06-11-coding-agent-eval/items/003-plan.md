# Item 003 — code_repair_v1: 15 Reviewed Code-Repair Tasks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `code_repair_v1` — 15 hand-authored code-repair tasks over the code-world (`examples/datasets/code_repair_v1.jsonl` + tier sidecar + review-fixtures sidecar), the v2-bar quality docs (`taxonomy.md`, `rubric.md` v `cr-rubric-v1`, `review-ledger.md` in the run dir), and an anti-rote conformance suite (`tests/datasets/test_code_repair_v1.py`) that proves every quality claim mechanically on real sandboxed pytest through the **production** oracle edge — per `docs/2026-06-11-coding-agent-eval/items/003-spec.md` (strike-throughs + Resolved decisions authoritative) and ADR-0010/0011/0012.

**Architecture:** Pure DATA + conformance item — **zero `src/agent_eval_lab` changes** (a hard spec constraint). Every conformance check uses already-public APIs: `load_tasks`, `path_error`, `prefix_collision`, `run_pytest`, `precompute_execution_verdicts`, `grade_trajectory`, `collect_execution_specs`, `execution_hash`, `grade_result_to_dict`. Oracle paths are disjoint from every initial-tree path; breadth is proven by the stub-neutralization and hack-fixture checks, never claimed (ADR-0012). The dataset JSONL and both sidecars are emitted by a deterministic builder script that lives at `/tmp` (transcription tooling, **never committed** — its full source is preserved in this plan), so a one-character typo is caught by sha256 gates instead of corrupting a 15-line JSONL by hand.

**Tech Stack:** Python 3.11+ (project venv 3.13), stdlib-only fixture content, pytest 9.0.3 (dev), ruff (`E,F,I,UP`, line length 88). All commands run via `uv run` from the repo root.

**Branch:** stay on `autodev/coding-agent-eval-feature`. Commit after every task. NEVER push — the orchestrator handles pushes.

**Already done — do NOT recreate:** `docs/adr/0012-oracle-paths-disjoint-from-visible-tests-breadth-proven-mechanically.md` and all CONTEXT.md code-repair terms (*visible tests*, *distractor file*, *bug class*, *hack fixture*, *reference solution*, *sidecar (dataset)*, updated *Difficulty knob* / *world_template_id* / *version (dataset)* / *oracle tests*) exist since the grill (commit `62edaac`). No plan task touches ADRs or CONTEXT.md.

**Baseline:** `uv run pytest` currently reports `550 passed`. Expected count after this item: `582 passed` (the 32 new conformance tests).

**Pre-validated:** the final assembly of every artifact in this plan was executed in a scratch worktree on this machine during planning, end-to-end through the production oracle edge: conformance `32 passed` in ~6.3 s (≈83 real sandboxed pytest runs at ~0.07 s each — far under the ≤120 s CI budget), full suite `582 passed` in ~16 s, `ruff check .` clean, `ruff format --check .` reports `101 files already formatted`. The red-green sequence was measured: 32 failed (dataset missing) → exactly 2 named failures on the planted draft defects → 32 passed. Every code block below is exact — type it verbatim; if a step's outcome differs from the stated expectation, suspect a transcription slip first. The emitted artifacts' sha256 sums (stated in Task 4) gate transcription of the builder.

**Empirically verified facts this plan relies on** (measured in the scratch worktree):
- One sandboxed `run_pytest` over a one-test tree takes **~0.07 s** on this machine; the conformance suite performs ≈83 of them (15 initial + 15 reference-visible + 15 reference-oracle + 15 no-op + 13 stub + 4 hack-visible + 4 hack-oracle + 2 determinism).
- Every initial tree with visible tests yields suite status `failed`; both prose-only trees (cr-008, cr-009) yield `no_tests` (exit 5).
- Every reference tree passes its oracle (`ExecutionVerdict.result.status == "passed"`) AND the full composite `grade_trajectory` verdict, including the three `AllOf` policy tasks (a zero-tool-call synthetic trajectory passes `OnlyModifies`/`NoToolCall`/`MaxToolCalls` legs, so the execution leg is the discriminator — spec Resolved decision Q16).
- Stubbing every visible test file with `def test_stub(): pass` on the unrepaired tree still fails the oracle on all 13 visible-test tasks — each oracle independently detects its planted bug.
- All four hack fixtures (cr-011, cr-013, cr-014, cr-015) pass the visible suite alone (`passed`) and fail the oracle — strict breadth proven where the taxonomy claims it.
- The two planted draft defects fail **exactly** `test_metadata_contract_on_every_row` (cr-001 `'pending:cr-rubric-v1' == 'passed:cr-rubric-v1'`) and `test_reference_solution_passes_oracle_through_production_edge` (cr-009 `oracle status failed`), with the other 30 tests green — proving the metadata gate and the real-sandbox solvability gate both bite.
- `ruff` UP033 requires `@cache` (not `@lru_cache(maxsize=None)`) on the memoized per-task helpers; the suite below already uses `@cache`.
- Grading the same `(spec, reference tree)` twice yields byte-identical `json.dumps(grade_result_to_dict(...), sort_keys=True)` outputs (criterion 23, re-proven over real dataset content).

---

## File map

| Path | Action | Responsibility |
|---|---|---|
| `docs/2026-06-11-coding-agent-eval/taxonomy.md` | Create | 6 capabilities × 4 tiers × closed knob + bug-class vocabularies; tier × expected-failure rationale table (criterion 4). |
| `docs/2026-06-11-coding-agent-eval/rubric.md` | Create | `cr-rubric-v1` authoring rubric, checks a–h (criterion 21). |
| `docs/2026-06-11-coding-agent-eval/review-ledger.md` | Create | One row per task: tier, capability, knob, bug class, rubric verdict, evidence (criterion 21); conformance asserts id parity. |
| `tests/datasets/test_code_repair_v1.py` | Create | The 32-test anti-rote conformance suite — every acceptance criterion enforced mechanically (criterion 22). |
| `examples/datasets/code_repair_v1.jsonl` | Create (generated) | The 15 frozen task rows (criteria 1–2). |
| `examples/datasets/code_repair_v1_tiers.json` | Create (generated) | `{id: tier}` sidecar, T1=2/T2=4/T3=6/T4=3 (criterion 3). |
| `examples/datasets/code_repair_v1_review_fixtures.json` | Create (generated) | `{id: {bug_class, solution, hack, distractor_paths}}` (criteria 6, 9); joins the Weeks 9-10 never-train manifest. |
| `/tmp/build_code_repair_v1.py` | Create — **never `git add`** | Deterministic emitter for the three artifacts above; carries the planted criterion-24 draft defects behind a flag. |

Untouched (hard constraint): everything under `src/agent_eval_lab/` — a discovered API gap is a run-log finding, not an inline patch.

---

### Task 1: Run-dir quality docs — taxonomy + authoring rubric

No tests read these two files (the conformance suite reads only `review-ledger.md`, authored in Task 3), so they land first as pure docs.

**Files:**
- Create: `docs/2026-06-11-coding-agent-eval/taxonomy.md`
- Create: `docs/2026-06-11-coding-agent-eval/rubric.md`

- [ ] **Step 1.1: Write `docs/2026-06-11-coding-agent-eval/taxonomy.md`**

Exact content:

````markdown
# code_repair_v1 — capability taxonomy

The code_repair_v1 set (`examples/datasets/code_repair_v1.jsonl`, 15 tasks) is the
first dataset on the code-world: each task is a small broken Python program the
agent repairs with `read_file` / `write_file` / `list_files` / `run_tests`, graded
by held-out **oracle tests** through the production oracle edge (ADR-0010/0011),
with oracle paths disjoint from the visible tests and breadth proven mechanically
(ADR-0012). Capabilities split by **evidence source** (what tells the agent where
the bug is); fix *shape* (single-line vs multi-hunk vs cross-file) is a difficulty
mechanism and lives in the knob vocabulary — preserving the v2
capability/knob/tier orthogonality.

## Capabilities × evidence source × verification shape

| capability | isolated skill (evidence source) | verification shape | tasks |
|------------|----------------------------------|--------------------|-------|
| `visible_test_localization` | a failing visible test names the symptom; map it to the fault | `execution` | cr-001, cr-002, cr-005, cr-012 |
| `prose_localization` | no visible tests at all (`no_tests`); the bug exists only as a prose report | `execution` (+ policy leg on cr-009) | cr-008, cr-009 |
| `test_comprehension` | the contract is specified *only* by the visible tests; prose never states the rule | `execution` | cr-003, cr-004 |
| `cross_file_repair` | the symptom surfaces in a different file than the fault | `execution` | cr-006, cr-007 |
| `regression_preservation` | the tempting fix breaks behavior only the oracle's regression tests protect | `execution` (+ `max_tool_calls` on cr-014) | cr-010, cr-014 |
| `overfit_resistance` | the visible tests underdetermine the fix; the oracle is strictly broader (hack fixture proves it) | `execution` (+ `no_tool_call` on cr-013) | cr-011, cr-013, cr-015 |

## Tiers × expected-failure rationale

| tier | count | % | expected-failure rationale |
|------|-------|---|----------------------------|
| T1 sanity | 2 | 13% | Every frontier model repairs these one-line faults — the regression floor. A T1 failure indicts the harness or world wiring (item 004's classifier needs this separability), not the model. |
| T2 moderate | 4 | 27% | Occasional misses on tests-as-spec comprehension and the first cross-file hop. The visible gradient between floor and hard band. |
| T3 hard | 6 | 40% | Prose-only localization, two-import fault distance, distractor files, regression traps. **Strong models are expected to sometimes fail here** — wrong-file edits and visible-suite-only fixes that the oracle rejects. |
| T4 adversarial | 3 | 20% | Designed so ≥ 1 frontier model is expected to fail: multi-hunk repair under a no-run-tests policy, aliasing repair under a tool-call budget, and an overfit trap whose visible suite is deliberately narrow. |

T3 + T4 = 9 / 15 = **60%** (the hard-majority directive).

## Difficulty knobs (closed code dialect)

Declared by every T3/T4 task in `metadata.difficulty_knob`; the workspace dialect
names do not transfer (per-world dialects, CONTEXT.md **Difficulty knob**).

- `fault_distance` — the symptom and the fault are separated by ≥ 2 import hops (cr-007).
- `multi_hunk` — the defect is several related edits; a partial fix still fails (cr-013).
- `oracle_breadth` — the visible tests underdetermine the fix; only the held-out oracle pins it (cr-010, cr-011, cr-015).
- `spec_obliqueness` — no failing visible test; the contract arrives as oblique prose (cr-008, cr-009).
- `constraint_budget` — a policy leg (`TrajectorySpec`) budgets or forbids tool use (cr-014).
- `distractor_file` — a correct file plausibly looks at fault; the oracle regression-pins it (cr-012).

## Bug classes (closed vocabulary, sidecar + ledger only)

`off_by_one`, `logic_inversion`, `exception_handling`, `type_coercion`,
`boundary_condition`, `aliasing_mutation` — every task tags exactly one primary
class in `code_repair_v1_review_fixtures.json`; every class is represented.
`TaskMetadata` is unchanged (the v2 sidecar precedent).

## Determinism

Every program and test is pure stdlib computation: no clock, RNG, network, env,
filesystem, or subprocess surface — enforced mechanically by the 15-module import
banlist (`socket`, `http`, `urllib`, `requests`, `subprocess`, `multiprocessing`,
`threading`, `asyncio`, `random`, `secrets`, `uuid`, `time`, `datetime`, `os`,
`tempfile`) in `tests/datasets/test_code_repair_v1.py`. Dates in fixtures are
literal ISO strings compared lexicographically. Same task + same final tree ⇒
byte-identical verdict (proven by the determinism spot-check).
````

- [ ] **Step 1.2: Write `docs/2026-06-11-coding-agent-eval/rubric.md`**

Exact content:

````markdown
# code_repair_v1 — task validity rubric

**Version: `cr-rubric-v1`** — every shipped row carries
`metadata.review = "passed:cr-rubric-v1"`.

This is the **authoring rubric** (the author's task-validity checklist) — distinct
from a *judge* rubric (`LlmJudgeSpec.rubric`, unused here) and from the
`VerificationSpec` itself (CONTEXT.md, the three rubric senses). Every task in
`code_repair_v1.jsonl` must pass all eight checks; the per-task verdict is
recorded in `metadata.review` (source of truth, frozen with the append-only row)
and mirrored in `review-ledger.md` (regenerable audit view).

## Checklist (every task must pass a–h)

- **(a) Unambiguous, single defensible fix** — exactly one defect family with one
  defensible repair semantics; alternative spellings of the same fix pass the
  oracle (the **reference solution** witnesses solvability, never uniqueness).
- **(b) Single capability** — the task isolates exactly one of the six taxonomy
  capabilities; a secondary skill, if unavoidable, is noted in the ledger.
- **(c) Verification matches intent** — the oracle (`ExecutionSpec`) is the outcome
  authority; policy clauses ride `TrajectorySpec` legs inside `AllOf`, never prose;
  no `FinalStateSpec` byte-equality over repaired files (valid alternative fixes
  must pass).
- **(d) Deterministic, hermetic** — no clock/RNG/network/env/filesystem/subprocess
  surface in any fixture tree; the 15-module import banlist is the mechanical
  backstop; dates are literal ISO strings.
- **(e) Self-contained oracle, disjoint paths** — no `conftest.py` anywhere (the
  sandbox runs `--noconftest`; a file inert in the sandbox but live under plain
  pytest is an authoring trap); oracle paths are disjoint from every initial-tree
  path (ADR-0012); test-module basenames unique across visible + oracle;
  `*_test.py` basenames banned so the `test_*.py` convention equals collection;
  harness-reserved basenames banned at any depth.
- **(f) Solvable inside the budget** — the reference solution passes visible suite
  and oracle through the production oracle edge within the 10 s sandbox default
  (`timeout_s = None` on all 15) and within `metadata.max_steps`
  (≥ 6 all, ≥ 8 T3/T4, ≤ 16).
- **(g) No import-time-exploit surface** — graded modules run code at import inside
  the oracle process (ADR-0010 residual trust boundary); each task's import-time
  surface is plain defs/constants, screened per row.
- **(h) The knob is the hardness** — for T3/T4, the declared `difficulty_knob` is
  the thing that actually makes the task hard (the human gate the mechanical
  checks cannot prove).

## Mechanical backstop

`tests/datasets/test_code_repair_v1.py` enforces (c)-shape, (d), (e), (f), and the
breadth/anti-rote witnesses of (a) mechanically over all 15 tasks — including the
no-op zero, stub neutralization, hack-fixture breadth, anti-rote transcription and
oracle-leakage proxies, policy coherence, and the determinism spot-check — on real
sandboxed pytest through the production oracle edge. Checks (a)-full, (b), (g),
and (h) are human gates recorded in the ledger.

## Re-review

Re-reviewing under a new rubric is a **new dataset version** (new `version` +
`world_template_id` family), never an in-place row edit — `metadata.review` is
frozen with the append-only row, and the sidecars freeze with it. A ledger edit
can never un-gate a row. The review-fixtures sidecar carries solutions and joins
the Weeks 9-10 never-train manifest.
````

- [ ] **Step 1.3: Commit**

```bash
git add docs/2026-06-11-coding-agent-eval/taxonomy.md docs/2026-06-11-coding-agent-eval/rubric.md
git commit -m "docs(003): code-repair capability taxonomy + cr-rubric-v1 authoring rubric"
```

### Task 2: The conformance suite (red — dataset not yet authored)

The entire 32-test suite lands before any dataset row exists (TDD over data). Every check uses production APIs only. The memoized helpers (`@cache`) keep the sandboxed-run count at ≈83; ruff UP033 demands `@cache` over `@lru_cache(maxsize=None)`.

**Files:**
- Create: `tests/datasets/test_code_repair_v1.py`

- [ ] **Step 2.1: Write `tests/datasets/test_code_repair_v1.py`**

Exact content (678 lines):

```python
"""code_repair_v1 conformance: every quality claim is proven mechanically.

Runs the production oracle edge on real sandboxed pytest (ADR-0010/0011/0012):
shape/metadata/tier/capability/knob contracts, world validity over all four
fixture-tree kinds, oracle-path disjointness, symptom reality, solvability,
no-op zero, stub neutralization, hack breadth, anti-rote and oracle-leakage
proxies, policy coherence, distractor integrity, ledger parity, determinism.
"""

import json
import re
from collections import Counter
from collections.abc import Mapping
from functools import cache, lru_cache
from pathlib import Path

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    collect_execution_specs,
    execution_hash,
)
from agent_eval_lab.records.serialize import grade_result_to_dict
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.oracle_edge import precompute_execution_verdicts
from agent_eval_lab.runners.pytest_edge import run_pytest
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.schema import (
    AllOf,
    ExecutionSpec,
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    Task,
    TrajectorySpec,
)
from agent_eval_lab.tools.code_world import (
    CODE_WORLD_TOOLS,
    path_error,
    prefix_collision,
)

_REPO = Path(__file__).parent.parent.parent
DATASET = _REPO / "examples/datasets/code_repair_v1.jsonl"
TIERS_SIDECAR = _REPO / "examples/datasets/code_repair_v1_tiers.json"
FIXTURES_SIDECAR = _REPO / "examples/datasets/code_repair_v1_review_fixtures.json"
LEDGER = _REPO / "docs/2026-06-11-coding-agent-eval/review-ledger.md"

_CAPABILITIES = {
    "visible_test_localization",
    "prose_localization",
    "test_comprehension",
    "cross_file_repair",
    "regression_preservation",
    "overfit_resistance",
}
_KNOBS = {
    "fault_distance",
    "multi_hunk",
    "oracle_breadth",
    "spec_obliqueness",
    "constraint_budget",
    "distractor_file",
}
_BUG_CLASSES = {
    "off_by_one",
    "logic_inversion",
    "exception_handling",
    "type_coercion",
    "boundary_condition",
    "aliasing_mutation",
}
_BANNED_IMPORTS = {
    "socket",
    "http",
    "urllib",
    "requests",
    "subprocess",
    "multiprocessing",
    "threading",
    "asyncio",
    "random",
    "secrets",
    "uuid",
    "time",
    "datetime",
    "os",
    "tempfile",
}
_RESERVED_BASENAMES = {
    ".harness.ini",
    ".junit.xml",
    "sitecustomize.py",
    "usercustomize.py",
    "conftest.py",
}
_CODE_TOOLS = {"read_file", "write_file", "list_files", "run_tests"}
_TIER_ALLOCATION = {"T1": 2, "T2": 4, "T3": 6, "T4": 3}
_STUB = "def test_stub():\n    pass\n"


# ---- pure loaders and walkers -----------------------------------------------


@lru_cache(maxsize=1)
def _tasks() -> tuple[Task, ...]:
    return load_tasks(DATASET)


def _task(task_id: str) -> Task:
    return next(t for t in _tasks() if t.id == task_id)


@lru_cache(maxsize=1)
def _tiers() -> dict[str, str]:
    return json.loads(TIERS_SIDECAR.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _fixtures() -> dict[str, dict]:
    return json.loads(FIXTURES_SIDECAR.read_text(encoding="utf-8"))


def _initial_files(task: Task) -> dict[str, str]:
    return dict((task.initial_state or {}).get("files", {}))


def _oracle_spec(task: Task) -> ExecutionSpec:
    specs = collect_execution_specs(task.verification)
    assert len(specs) == 1, f"{task.id}: expected exactly one ExecutionSpec"
    return specs[0]


def _trajectory_specs(task: Task) -> tuple[TrajectorySpec, ...]:
    def walk(spec) -> tuple[TrajectorySpec, ...]:
        if isinstance(spec, TrajectorySpec):
            return (spec,)
        if isinstance(spec, AllOf):
            return tuple(t for sub in spec.specs for t in walk(sub))
        return ()

    return walk(task.verification)


def _basename(path: str) -> str:
    return path.split("/")[-1]


def _is_test_basename(path: str) -> bool:
    name = _basename(path)
    return name.startswith("test_") and name.endswith(".py")


def _visible_test_paths(task: Task) -> tuple[str, ...]:
    return tuple(p for p in sorted(_initial_files(task)) if _is_test_basename(p))


def _solution(task: Task) -> dict[str, str]:
    return dict(_fixtures()[task.id]["solution"])


def _hack(task: Task) -> dict[str, str] | None:
    raw = _fixtures()[task.id]["hack"]
    return None if raw is None else dict(raw)


def _fixture_trees(task: Task) -> dict[str, Mapping[str, str]]:
    """The four fixture-tree kinds this item ships (hack may be absent)."""
    trees: dict[str, Mapping[str, str]] = {
        "initial": _initial_files(task),
        "oracle": dict(_oracle_spec(task).held_out_tests),
        "solution": _solution(task),
    }
    hack = _hack(task)
    if hack is not None:
        trees["hack"] = hack
    return trees


def _imported_roots(content: str) -> set[str]:
    """Top-level module names named by import statements (mechanical scan)."""
    roots: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            for part in stripped[len("import ") :].split(","):
                roots.add(part.strip().split(" ")[0].split(".")[0])
        elif stripped.startswith("from "):
            roots.add(stripped.split()[1].split(".")[0])
    return roots


def _prompt_text(task: Task) -> str:
    return "\n".join(m.content for m in task.input.messages)


def _nontrivial_lines(content: str) -> set[str]:
    return {line.strip() for line in content.splitlines() if len(line.strip()) > 3}


# ---- synthetic trajectories + cached sandbox runs ---------------------------


def _trajectory(final_state: Mapping) -> Trajectory:
    return Trajectory(
        turns=(MessageTurn(role="assistant", content="Done."),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def _grade(task: Task, final_files: Mapping[str, str]):
    """Production path: oracle edge precompute, then the pure graders."""
    trajectory = _trajectory({"files": dict(final_files)})
    verdicts = precompute_execution_verdicts(
        verification=task.verification, trajectory=trajectory
    )
    grade = grade_trajectory(
        verification=task.verification,
        trajectory=trajectory,
        registry=CODE_WORLD_TOOLS,
        initial_state=task.initial_state,
        verdicts=verdicts,
    )
    key = execution_hash(_oracle_spec(task), dict(final_files))
    return grade, verdicts.get(key)


@cache
def _initial_run(task_id: str):
    return run_pytest(_initial_files(_task(task_id)))


@cache
def _reference_files(task_id: str) -> tuple[tuple[str, str], ...]:
    task = _task(task_id)
    return tuple(sorted({**_initial_files(task), **_solution(task)}.items()))


@cache
def _reference_visible_run(task_id: str):
    return run_pytest(dict(_reference_files(task_id)))


@cache
def _reference_grade(task_id: str):
    return _grade(_task(task_id), dict(_reference_files(task_id)))


@cache
def _noop_grade(task_id: str):
    task = _task(task_id)
    return _grade(task, _initial_files(task))


@cache
def _stub_grade(task_id: str):
    task = _task(task_id)
    stubbed = {
        **_initial_files(task),
        **{p: _STUB for p in _visible_test_paths(task)},
    }
    return _grade(task, stubbed)


@cache
def _hack_files(task_id: str) -> tuple[tuple[str, str], ...]:
    task = _task(task_id)
    hack = _hack(task)
    assert hack is not None
    return tuple(sorted({**_initial_files(task), **hack}.items()))


@cache
def _hack_visible_run(task_id: str):
    return run_pytest(dict(_hack_files(task_id)))


@cache
def _hack_grade(task_id: str):
    return _grade(_task(task_id), dict(_hack_files(task_id)))


# ---- criterion 1-2: dataset file, shape, metadata contract ------------------


def test_dataset_has_fifteen_uniquely_numbered_rows() -> None:
    ids = [t.id for t in _tasks()]
    assert len(ids) == 15
    assert sorted(ids) == [f"cr-{n:03d}" for n in range(1, 16)]
    assert all(re.fullmatch(r"cr-\d{3}", i) for i in ids)


def test_every_row_has_a_reachable_execution_spec() -> None:
    for task in _tasks():
        assert len(collect_execution_specs(task.verification)) == 1, task.id


def test_messages_are_one_shared_system_turn_plus_one_user_turn() -> None:
    systems = set()
    for task in _tasks():
        messages = task.input.messages
        assert len(messages) == 2, task.id
        assert messages[0].role == "system", task.id
        assert messages[1].role == "user", task.id
        systems.add(messages[0].content)
    assert len(systems) == 1, "system turn must be byte-identical across rows"


def test_metadata_contract_on_every_row() -> None:
    slugs = set()
    for task in _tasks():
        meta = task.metadata
        assert meta.split == "dev", task.id
        assert meta.version == "1", task.id
        assert meta.provenance == "hand_written", task.id
        assert meta.review == "passed:cr-rubric-v1", task.id
        assert meta.max_steps is not None, task.id
        assert meta.world_template_id is not None, task.id
        assert re.fullmatch(r"code-v1-[a-z0-9-]+", meta.world_template_id), task.id
        slugs.add(meta.world_template_id)
    assert len(slugs) == 15, "world_template_id must be unique per task"


def test_available_tools_are_exactly_the_code_world_tools() -> None:
    for task in _tasks():
        assert set(task.input.available_tools) == _CODE_TOOLS, task.id
        assert len(task.input.available_tools) == 4, task.id
        assert set(CODE_WORLD_TOOLS) == _CODE_TOOLS


# ---- criterion 3: tier sidecar ----------------------------------------------


def test_tier_sidecar_covers_every_id_with_declared_allocation() -> None:
    tiers = _tiers()
    assert set(tiers) == {t.id for t in _tasks()}
    assert Counter(tiers.values()) == Counter(_TIER_ALLOCATION)


# ---- criterion 4-5: capabilities and knobs ----------------------------------


def test_capabilities_closed_and_each_covers_at_least_two_tasks() -> None:
    counts = Counter(t.capability for t in _tasks())
    assert set(counts) == _CAPABILITIES
    assert all(n >= 2 for n in counts.values()), counts


def test_every_hard_task_declares_exactly_one_vocabulary_knob() -> None:
    tiers = _tiers()
    for task in _tasks():
        knob = task.metadata.difficulty_knob
        if tiers[task.id] in ("T3", "T4"):
            assert knob is not None, task.id
        if knob is not None:
            assert knob in _KNOBS, f"{task.id}: {knob}"


# ---- criterion 6 + 9: bug classes and review-fixtures sidecar ---------------


def test_fixtures_sidecar_shape_and_bug_class_coverage() -> None:
    fixtures = _fixtures()
    assert set(fixtures) == {t.id for t in _tasks()}
    classes = Counter()
    for task_id, entry in fixtures.items():
        assert set(entry) == {"bug_class", "solution", "hack", "distractor_paths"}
        assert entry["bug_class"] in _BUG_CLASSES, task_id
        classes[entry["bug_class"]] += 1
        assert isinstance(entry["solution"], dict) and entry["solution"], task_id
        assert entry["hack"] is None or (
            isinstance(entry["hack"], dict) and entry["hack"]
        ), task_id
        assert isinstance(entry["distractor_paths"], list), task_id
    assert set(classes) == _BUG_CLASSES, "every bug class represented at least once"


def test_solution_and_hack_paths_stay_inside_the_initial_tree() -> None:
    for task in _tasks():
        files = _initial_files(task)
        for kind in ("solution", "hack"):
            tree = _fixtures()[task.id][kind]
            for path in tree or {}:
                assert path in files, f"{task.id}: {kind} writes new path {path}"


# ---- criterion 7: world validity over every fixture tree --------------------


def test_every_fixture_tree_is_a_valid_code_world_tree() -> None:
    for task in _tasks():
        for kind, tree in _fixture_trees(task).items():
            paths = sorted(tree)
            for path in paths:
                assert path_error(path) is None, f"{task.id}/{kind}: {path}"
                name = _basename(path)
                assert name not in _RESERVED_BASENAMES, f"{task.id}/{kind}: {path}"
                assert not name.endswith("_test.py"), f"{task.id}/{kind}: {path}"
            for i, path_a in enumerate(paths):
                for path_b in paths[i + 1 :]:
                    assert not prefix_collision(path_a, path_b), (
                        f"{task.id}/{kind}: {path_a} vs {path_b}"
                    )


# ---- criterion 8: oracle invariants -----------------------------------------


def test_oracle_paths_are_disjoint_from_the_initial_tree() -> None:
    for task in _tasks():
        files = _initial_files(task)
        for oracle_path in _oracle_spec(task).held_out_tests:
            assert oracle_path not in files, f"{task.id}: {oracle_path}"
            for initial_path in files:
                assert not prefix_collision(oracle_path, initial_path), (
                    f"{task.id}: {oracle_path} vs {initial_path}"
                )


def test_oracle_is_collectible_with_unique_test_module_basenames() -> None:
    for task in _tasks():
        oracle = _oracle_spec(task)
        assert any(_is_test_basename(p) for p in oracle.held_out_tests), task.id
        assert oracle.timeout_s is None, task.id
        test_basenames = [
            _basename(p)
            for p in (*_visible_test_paths(task), *sorted(oracle.held_out_tests))
            if _is_test_basename(p)
        ]
        assert len(test_basenames) == len(set(test_basenames)), task.id


# ---- criterion 10: the symptom is real --------------------------------------


def test_initial_tree_fails_visible_suite_or_is_prose_only() -> None:
    for task in _tasks():
        result = _initial_run(task.id)
        if _visible_test_paths(task):
            assert result.status == "failed", f"{task.id}: {result.status}"
        else:
            assert result.status == "no_tests", f"{task.id}: {result.status}"


def test_prose_only_tasks_are_exactly_the_prose_localization_tasks() -> None:
    for task in _tasks():
        prose_only = not _visible_test_paths(task)
        assert prose_only == (task.capability == "prose_localization"), task.id


# ---- criterion 11 + 16-coherence: solvability through the oracle edge -------


def test_reference_solution_passes_oracle_through_production_edge() -> None:
    for task in _tasks():
        grade, verdict = _reference_grade(task.id)
        assert isinstance(verdict, ExecutionVerdict), f"{task.id}: {verdict!r}"
        assert verdict.result.status == "passed", (
            f"{task.id}: oracle status {verdict.result.status}"
        )
        assert grade.passed, f"{task.id}: composite verdict failed"


def test_reference_tree_passes_its_visible_suite() -> None:
    for task in _tasks():
        result = _reference_visible_run(task.id)
        expected = "passed" if _visible_test_paths(task) else "no_tests"
        assert result.status == expected, f"{task.id}: {result.status}"


# ---- criterion 12: no-op agent grades 0/15 -----------------------------------


def test_noop_agent_fails_every_task() -> None:
    for task in _tasks():
        grade, _ = _noop_grade(task.id)
        assert not grade.passed, f"{task.id}: verification pre-satisfied"


# ---- criterion 13: test-stubbing agent neutralized ---------------------------


def test_stubbing_visible_tests_cannot_pass_an_unrepaired_task() -> None:
    for task in _tasks():
        if not _visible_test_paths(task):
            continue
        grade, verdict = _stub_grade(task.id)
        assert isinstance(verdict, ExecutionVerdict), f"{task.id}: {verdict!r}"
        assert verdict.result.status != "passed", (
            f"{task.id}: oracle does not independently detect the bug"
        )
        assert not grade.passed, task.id


# ---- criterion 14: hardcode agent caught -------------------------------------


def _hack_required_ids() -> set[str]:
    tiers = _tiers()
    return {
        t.id
        for t in _tasks()
        if t.capability == "overfit_resistance"
        or (tiers[t.id] == "T4" and _visible_test_paths(t))
    }


def test_hack_fixtures_cover_overfit_and_t4_tasks() -> None:
    for task_id in sorted(_hack_required_ids()):
        assert _hack(_task(task_id)) is not None, f"{task_id}: hack fixture missing"


def test_hacked_tree_passes_visible_suite_but_fails_oracle() -> None:
    for task in _tasks():
        if _hack(task) is None:
            continue
        visible = _hack_visible_run(task.id)
        assert visible.status == "passed", f"{task.id}: hack must pass visible suite"
        grade, verdict = _hack_grade(task.id)
        assert isinstance(verdict, ExecutionVerdict), f"{task.id}: {verdict!r}"
        assert verdict.result.status != "passed", (
            f"{task.id}: oracle is not strictly broader than the visible suite"
        )
        assert not grade.passed, task.id


# ---- criterion 15 + 20: anti-rote and oracle-leakage proxies -----------------


def test_prompt_never_dictates_a_solution_line() -> None:
    for task in _tasks():
        prompt = _prompt_text(task)
        files = _initial_files(task)
        for path, content in _solution(task).items():
            changed = _nontrivial_lines(content) - _nontrivial_lines(
                files.get(path, "")
            )
            for line in sorted(changed):
                assert line not in prompt, f"{task.id}: prompt dictates {line!r}"


def test_prompt_never_leaks_an_oracle_line() -> None:
    for task in _tasks():
        prompt = _prompt_text(task)
        for content in _oracle_spec(task).held_out_tests.values():
            for line in sorted(_nontrivial_lines(content)):
                assert line not in prompt, f"{task.id}: prompt leaks {line!r}"


# ---- criterion 16: policy composition ----------------------------------------


def _policy_constraints(task: Task) -> tuple:
    return tuple(c for spec in _trajectory_specs(task) for c in spec.constraints)


def test_at_least_three_tasks_compose_execution_with_policy() -> None:
    composed = {t.id: _policy_constraints(t) for t in _tasks() if _trajectory_specs(t)}
    assert len(composed) >= 3, composed
    kinds = {type(c).__name__ for constraints in composed.values() for c in constraints}
    assert len(kinds) >= 2, kinds


def test_max_tool_calls_budgets_fit_inside_max_steps() -> None:
    for task in _tasks():
        for constraint in _policy_constraints(task):
            if isinstance(constraint, MaxToolCalls):
                assert task.metadata.max_steps is not None, task.id
                assert constraint.n <= task.metadata.max_steps, task.id


def test_no_tool_call_legs_name_a_registered_tool() -> None:
    for task in _tasks():
        for constraint in _policy_constraints(task):
            if isinstance(constraint, NoToolCall):
                assert constraint.name in _CODE_TOOLS, task.id


def test_only_modifies_allowlists_pass_the_dotted_path_ambiguity_guard() -> None:
    for task in _tasks():
        union: set[str] = set()
        for tree in _fixture_trees(task).values():
            union |= set(tree)
        for constraint in _policy_constraints(task):
            if not isinstance(constraint, OnlyModifies):
                continue
            for allowed in constraint.paths:
                assert allowed.startswith("files."), f"{task.id}: {allowed}"
                assert allowed[len("files.") :] in union, f"{task.id}: {allowed}"
                allowed_segments = allowed.split(".")
                for path in union:
                    dotted = f"files.{path}".split(".")
                    if dotted == allowed_segments:
                        continue
                    assert dotted[: len(allowed_segments)] != allowed_segments, (
                        f"{task.id}: {path} extends allowlisted {allowed}"
                    )


# ---- criterion 17: distractor files ------------------------------------------


def test_distractor_files_are_real_untouched_and_oracle_referenced() -> None:
    for task in _tasks():
        distractors = _fixtures()[task.id]["distractor_paths"]
        if task.metadata.difficulty_knob == "distractor_file":
            assert distractors, f"{task.id}: distractor_file task names no distractor"
        files = _initial_files(task)
        oracle = _oracle_spec(task).held_out_tests
        solution = _solution(task)
        for path in distractors:
            assert path in files, f"{task.id}: {path} not in initial tree"
            assert solution.get(path, files[path]) == files[path], (
                f"{task.id}: solution modifies distractor {path}"
            )
            stem = _basename(path).removesuffix(".py")
            referenced = any(
                stem in _imported_roots(content) for content in oracle.values()
            )
            assert referenced, f"{task.id}: oracle never references {path}"


# ---- criterion 18: max_steps floors ------------------------------------------


def test_max_steps_floors_and_cap() -> None:
    tiers = _tiers()
    for task in _tasks():
        steps = task.metadata.max_steps
        assert steps is not None and 6 <= steps <= 16, f"{task.id}: {steps}"
        if tiers[task.id] in ("T3", "T4"):
            assert steps >= 8, f"{task.id}: {steps}"


# ---- criterion 19: hermeticity banlist ---------------------------------------


def test_no_fixture_file_imports_a_banned_module() -> None:
    for task in _tasks():
        for kind, tree in _fixture_trees(task).items():
            for path, content in tree.items():
                roots = _imported_roots(content)
                banned = roots & _BANNED_IMPORTS
                assert not banned, f"{task.id}/{kind}/{path}: {sorted(banned)}"
                if "pytest" in roots:
                    assert _is_test_basename(path), (
                        f"{task.id}/{kind}/{path}: pytest outside a test file"
                    )


# ---- criterion 21: review ledger parity --------------------------------------


def test_review_ledger_has_exactly_one_block_of_ids_matching_dataset() -> None:
    text = LEDGER.read_text(encoding="utf-8")
    ids = {t.id for t in _tasks()}
    assert set(re.findall(r"cr-\d{3}", text)) == ids
    for task_id in sorted(ids):
        assert text.count(f"| {task_id} ") == 1, f"ledger row count for {task_id}"


# ---- criterion 23: determinism spot-check ------------------------------------


def test_grading_the_same_reference_tree_twice_is_byte_identical() -> None:
    task = _task("cr-001")
    final_files = dict(_reference_files(task.id))
    first, _ = _grade(task, final_files)
    second, _ = _grade(task, final_files)
    as_bytes = [
        json.dumps(grade_result_to_dict(g), sort_keys=True).encode("utf-8")
        for g in (first, second)
    ]
    assert as_bytes[0] == as_bytes[1]
```

- [ ] **Step 2.2: Run the suite to verify it is red for the right reason**

Run: `uv run pytest tests/datasets/test_code_repair_v1.py`
Expected: **`32 failed`** in well under 1 s — every test fails with `FileNotFoundError: ... examples/datasets/code_repair_v1.jsonl` (the dataset does not exist yet). Measured during planning: `32 failed in 0.45s`. If any test *passes* here, stop: the suite is not exercising the dataset.

- [ ] **Step 2.3: Lint the suite**

Run: `uv run ruff check tests/datasets/test_code_repair_v1.py && uv run ruff format --check tests/datasets/test_code_repair_v1.py`
Expected: `All checks passed!` and `1 file already formatted`.

- [ ] **Step 2.4: Commit (red by design — documented)**

```bash
git add tests/datasets/test_code_repair_v1.py
git commit -m "test(003): code_repair_v1 conformance suite — red, dataset not yet authored (TDD)"
```

### Task 3: The builder + DRAFT dataset (planted defects) + review ledger

The builder is **transcription tooling**: all 15 tasks' content is hand-written below as readable triple-quoted Python; the script only serializes it into JSONL + the two sidecars. It lives at `/tmp/build_code_repair_v1.py` and is **never committed** (this plan preserves its source; the emitted artifacts are the source of truth, re-verified by the conformance suite). It ships with `DRAFT_DEFECTS = True`, which plants the two deliberate criterion-24 defects; Task 4 corrects them.

**Files:**
- Create: `/tmp/build_code_repair_v1.py` (do **not** `git add`)
- Create (generated): `examples/datasets/code_repair_v1.jsonl`, `examples/datasets/code_repair_v1_tiers.json`, `examples/datasets/code_repair_v1_review_fixtures.json`
- Create: `docs/2026-06-11-coding-agent-eval/review-ledger.md`

- [ ] **Step 3.1: Write `/tmp/build_code_repair_v1.py`**

Exact content (note `DRAFT_DEFECTS = True` at this stage):

```python
"""Build code_repair_v1: dataset JSONL + tier sidecar + review-fixtures sidecar.

Transcription tooling only (the content below is hand-written); the emitted
artifacts are the source of truth. Run from the repo root:

    uv run python build_code_repair_v1.py

DRAFT_DEFECTS plants the two deliberate criterion-24 defects:
  (a) cr-001 review stamp "pending:cr-rubric-v1" (metadata check goes red)
  (b) cr-009 solution keeps the in-place sort (solvability via the real
      oracle edge goes red)
"""

import json
from pathlib import Path

DRAFT_DEFECTS = True

SYSTEM_PROMPT = (
    "You are a software repair agent working in a small Python project. "
    "Use the available tools to inspect the files, locate the defect, and "
    "repair it with a minimal change. Do not rewrite unrelated code. When "
    "the repair is complete, reply with a short summary of the fix."
)

CODE_TOOLS = ["read_file", "write_file", "list_files", "run_tests"]


# ---- cr-001 — T1 / visible_test_localization / off_by_one ------------------

CR_001_EVENS = '''\
"""Count even numbers in a list of ints."""


def count_evens(numbers):
    count = 0
    for i in range(1, len(numbers)):
        if numbers[i] % 2 == 0:
            count += 1
    return count
'''

CR_001_TEST = """\
from evens import count_evens


def test_counts_evens_in_mixed_list():
    assert count_evens([2, 3, 4, 5]) == 2


def test_all_odd_counts_zero():
    assert count_evens([1, 3, 5]) == 0
"""

CR_001_ORACLE = """\
from evens import count_evens


def test_first_element_even_is_counted():
    assert count_evens([2]) == 1


def test_empty_list_counts_zero():
    assert count_evens([]) == 0


def test_evens_at_both_ends():
    assert count_evens([4, 1, 1, 6]) == 2
"""

CR_001_SOLUTION = '''\
"""Count even numbers in a list of ints."""


def count_evens(numbers):
    count = 0
    for number in numbers:
        if number % 2 == 0:
            count += 1
    return count
'''

# ---- cr-002 — T1 / visible_test_localization / logic_inversion -------------

CR_002_ACCESS = '''\
"""Account access checks."""


def can_login(account):
    return account["active"] and account["locked"]
'''

CR_002_TEST = """\
from access import can_login


def test_active_unlocked_account_can_login():
    assert can_login({"active": True, "locked": False})
"""

CR_002_ORACLE = """\
from access import can_login


def test_locked_account_cannot_login():
    assert not can_login({"active": True, "locked": True})


def test_inactive_account_cannot_login():
    assert not can_login({"active": False, "locked": False})


def test_active_unlocked_account_is_allowed():
    assert can_login({"active": True, "locked": False})
"""

CR_002_SOLUTION = '''\
"""Account access checks."""


def can_login(account):
    return account["active"] and not account["locked"]
'''

# ---- cr-003 — T2 / test_comprehension / boundary_condition -----------------

CR_003_BANDS = '''\
"""Map a numeric score to a letter band."""


def band(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score > 70:
        return "C"
    return "D"
'''

CR_003_TEST = """\
from bands import band


def test_band_a_starts_at_ninety():
    assert band(90) == "A"


def test_band_c_starts_at_seventy():
    assert band(70) == "C"


def test_band_d_below_seventy():
    assert band(69) == "D"
"""

CR_003_ORACLE = """\
from bands import band


def test_every_band_boundary_is_inclusive():
    assert band(80) == "B"
    assert band(70) == "C"


def test_interior_values_keep_their_band():
    assert band(75) == "C"
    assert band(85) == "B"
    assert band(95) == "A"


def test_zero_is_band_d():
    assert band(0) == "D"
"""

CR_003_SOLUTION = '''\
"""Map a numeric score to a letter band."""


def band(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    return "D"
'''

# ---- cr-004 — T2 / test_comprehension / type_coercion -----------------------

CR_004_QTY = '''\
"""Parse quantity strings like "3" or "12"."""


def parse_qty(text):
    text = text.strip()
    if not text.isdigit():
        raise ValueError("not a quantity: " + text)
    return text
'''

CR_004_TEST = """\
import pytest

from qty import parse_qty


def test_parses_a_plain_number_to_an_int():
    assert parse_qty("3") == 3


def test_rejects_a_word():
    with pytest.raises(ValueError):
        parse_qty("three")
"""

CR_004_ORACLE = """\
import pytest

from qty import parse_qty


def test_result_supports_arithmetic():
    assert parse_qty("4") + 1 == 5


def test_strips_surrounding_spaces():
    assert parse_qty(" 12 ") == 12


def test_rejects_empty_text():
    with pytest.raises(ValueError):
        parse_qty("")
"""

CR_004_SOLUTION = '''\
"""Parse quantity strings like "3" or "12"."""


def parse_qty(text):
    text = text.strip()
    if not text.isdigit():
        raise ValueError("not a quantity: " + text)
    return int(text)
'''

# ---- cr-005 — T2 / visible_test_localization / exception_handling -----------

CR_005_SETTINGS = '''\
"""Read keys from a settings mapping with defaults."""


def get_setting(settings, key, default=None):
    try:
        return settings[key]
    except TypeError:
        return default
'''

CR_005_TEST = """\
from settings import get_setting


def test_missing_key_returns_default():
    assert get_setting({"theme": "dark"}, "lang", "en") == "en"


def test_present_key_returns_value():
    assert get_setting({"theme": "dark"}, "theme") == "dark"
"""

CR_005_ORACLE = """\
from settings import get_setting


def test_missing_key_with_no_default_returns_none():
    assert get_setting({}, "absent") is None


def test_default_unused_when_key_present():
    assert get_setting({"retries": 0}, "retries", 5) == 0
"""

CR_005_SOLUTION = '''\
"""Read keys from a settings mapping with defaults."""


def get_setting(settings, key, default=None):
    try:
        return settings[key]
    except KeyError:
        return default
'''

# ---- cr-006 — T2 / cross_file_repair / logic_inversion ----------------------

CR_006_FILTERS = '''\
"""Predicates over task records."""


def is_overdue(task, today):
    return task["due"] >= today
'''

CR_006_REPORT = '''\
"""Build the overdue-tasks report."""

from filters import is_overdue


def overdue_titles(tasks, today):
    return [task["title"] for task in tasks if is_overdue(task, today)]
'''

CR_006_TEST = """\
from report import overdue_titles

TASKS = [
    {"title": "file taxes", "due": "2026-04-01"},
    {"title": "renew passport", "due": "2026-12-01"},
]


def test_only_past_due_tasks_are_listed():
    assert overdue_titles(TASKS, "2026-06-01") == ["file taxes"]
"""

CR_006_ORACLE = """\
from filters import is_overdue
from report import overdue_titles


def test_task_due_yesterday_is_overdue():
    assert is_overdue({"title": "t", "due": "2026-06-10"}, "2026-06-11")


def test_task_due_today_is_not_overdue():
    assert not is_overdue({"title": "t", "due": "2026-06-11"}, "2026-06-11")


def test_report_keeps_task_order():
    tasks = [
        {"title": "b", "due": "2026-01-02"},
        {"title": "a", "due": "2026-01-01"},
    ]
    assert overdue_titles(tasks, "2026-02-01") == ["b", "a"]
"""

CR_006_SOLUTION = '''\
"""Predicates over task records."""


def is_overdue(task, today):
    return task["due"] < today
'''

# ---- cr-007 — T3 / cross_file_repair / fault_distance / boundary ------------

CR_007_TIERS = '''\
"""Weight tiers for parcel shipping."""

TIER_LIMITS = [
    (1, 3.00),
    (5, 7.50),
    (20, 15.00),
]


def tier_price(weight_kg):
    for limit, price in TIER_LIMITS:
        if weight_kg < limit:
            return price
    raise ValueError("parcel too heavy: " + str(weight_kg))
'''

CR_007_PRICING = '''\
"""Order pricing built on the shipping tiers."""

from tiers import tier_price


def shipping_cost(weights):
    return sum(tier_price(weight) for weight in weights)
'''

CR_007_CHECKOUT = '''\
"""Checkout total: items plus shipping."""

from pricing import shipping_cost


def order_total(item_total, weights):
    return round(item_total + shipping_cost(weights), 2)
'''

CR_007_TEST = """\
from checkout import order_total


def test_five_kilo_parcel_ships_at_the_five_kilo_tier():
    assert order_total(10.00, [5]) == 17.50


def test_light_parcel_ships_at_the_one_kilo_tier():
    assert order_total(1.00, [0.5]) == 4.00
"""

CR_007_ORACLE = """\
import pytest

from pricing import shipping_cost
from tiers import tier_price


def test_each_tier_limit_is_inclusive():
    assert tier_price(1) == 3.00
    assert tier_price(5) == 7.50
    assert tier_price(20) == 15.00


def test_just_over_a_limit_moves_up_a_tier():
    assert tier_price(1.1) == 7.50


def test_too_heavy_raises_value_error():
    with pytest.raises(ValueError):
        tier_price(21)


def test_shipping_cost_sums_tiers():
    assert shipping_cost([1, 5]) == 10.50
"""

CR_007_SOLUTION = '''\
"""Weight tiers for parcel shipping."""

TIER_LIMITS = [
    (1, 3.00),
    (5, 7.50),
    (20, 15.00),
]


def tier_price(weight_kg):
    for limit, price in TIER_LIMITS:
        if weight_kg <= limit:
            return price
    raise ValueError("parcel too heavy: " + str(weight_kg))
'''

# ---- cr-008 — T3 / prose_localization / spec_obliqueness / off_by_one -------

CR_008_PAGING = '''\
"""Split a list of row ids into fixed-size pages."""


def page_count(total_rows, page_size):
    if total_rows == 0:
        return 0
    return total_rows // page_size


def page_of(rows, page_size, page_index):
    start = page_index * page_size
    return rows[start : start + page_size]
'''

CR_008_ORACLE = """\
from paging import page_count, page_of


def test_partial_final_page_is_counted():
    assert page_count(11, 5) == 3


def test_exact_multiple_has_no_extra_page():
    assert page_count(10, 5) == 2


def test_zero_rows_is_zero_pages():
    assert page_count(0, 5) == 0


def test_page_of_returns_the_requested_window():
    assert page_of(list("abcdefgh"), 3, 2) == ["g", "h"]
"""

CR_008_SOLUTION = '''\
"""Split a list of row ids into fixed-size pages."""


def page_count(total_rows, page_size):
    if total_rows == 0:
        return 0
    return (total_rows + page_size - 1) // page_size


def page_of(rows, page_size, page_index):
    start = page_index * page_size
    return rows[start : start + page_size]
'''

# ---- cr-009 — T3 / prose_localization / spec_obliqueness / aliasing ---------

CR_009_WINDOW = '''\
"""Rolling-window statistics over a list of samples."""


def top_three(samples):
    samples.sort(reverse=True)
    return samples[:3]
'''

CR_009_ORACLE = """\
from window import top_three


def test_returns_three_largest_in_descending_order():
    assert top_three([4, 9, 1, 7, 3]) == [9, 7, 4]


def test_caller_list_is_not_reordered():
    samples = [4, 9, 1, 7, 3]
    top_three(samples)
    assert samples == [4, 9, 1, 7, 3]


def test_short_lists_are_returned_whole():
    assert top_three([2, 1]) == [2, 1]
"""

CR_009_SOLUTION = '''\
"""Rolling-window statistics over a list of samples."""


def top_three(samples):
    ordered = sorted(samples, reverse=True)
    return ordered[:3]
'''

# ---- cr-010 — T3 / regression_preservation / oracle_breadth / exceptions ----

CR_010_LEDGER = '''\
"""Apply a withdrawal to an account balance."""


def withdraw(balance, amount):
    if amount <= 0:
        raise ValueError("amount must be positive")
    if amount > balance:
        return balance
    return balance - amount
'''

CR_010_TEST = """\
import pytest

from ledger import withdraw


def test_overdraw_raises_value_error():
    with pytest.raises(ValueError):
        withdraw(50, 80)


def test_normal_withdrawal_reduces_balance():
    assert withdraw(100, 30) == 70
"""

CR_010_ORACLE = """\
import pytest

from ledger import withdraw


def test_overdraw_is_rejected():
    with pytest.raises(ValueError):
        withdraw(10, 11)


def test_withdrawing_the_exact_balance_empties_the_account():
    assert withdraw(50, 50) == 0


def test_zero_amount_is_rejected():
    with pytest.raises(ValueError):
        withdraw(100, 0)


def test_negative_amount_is_rejected():
    with pytest.raises(ValueError):
        withdraw(100, -5)
"""

CR_010_SOLUTION = '''\
"""Apply a withdrawal to an account balance."""


def withdraw(balance, amount):
    if amount <= 0:
        raise ValueError("amount must be positive")
    if amount > balance:
        raise ValueError("insufficient funds")
    return balance - amount
'''

# ---- cr-011 — T3 / overfit_resistance / oracle_breadth / boundary -----------

CR_011_LEAP = '''\
"""Leap-year rule for the Gregorian calendar."""


def is_leap(year):
    return year % 4 == 0
'''

CR_011_TEST = """\
from leap import is_leap


def test_year_divisible_by_four_is_leap():
    assert is_leap(2024)


def test_century_not_divisible_by_400_is_not_leap():
    assert not is_leap(1900)


def test_plain_year_is_not_leap():
    assert not is_leap(2023)
"""

CR_011_ORACLE = """\
from leap import is_leap


def test_other_centuries_follow_the_same_rule():
    assert not is_leap(2100)
    assert not is_leap(1800)


def test_year_divisible_by_400_is_leap():
    assert is_leap(2000)
    assert is_leap(1600)


def test_ordinary_leap_years_still_pass():
    assert is_leap(1996)
"""

CR_011_SOLUTION = '''\
"""Leap-year rule for the Gregorian calendar."""


def is_leap(year):
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    return year % 4 == 0
'''

CR_011_HACK = '''\
"""Leap-year rule for the Gregorian calendar."""


def is_leap(year):
    if year == 1900:
        return False
    return year % 4 == 0
'''

# ---- cr-012 — T3 / visible_test_localization / distractor_file / inversion --

CR_012_LEVELS = '''\
"""Numeric severity for each log level."""

SEVERITY = {
    "debug": 10,
    "info": 20,
    "warning": 30,
    "error": 40,
}


def severity_of(level):
    return SEVERITY[level]
'''

CR_012_LOGFILTER = '''\
"""Filter log records by minimum severity."""

from levels import severity_of


def at_least(records, minimum):
    return [r for r in records if severity_of(r["level"]) < severity_of(minimum)]
'''

CR_012_TEST = """\
from logfilter import at_least

RECORDS = [
    {"level": "debug", "message": "probe"},
    {"level": "error", "message": "boom"},
]


def test_keeps_records_at_or_above_the_minimum():
    assert at_least(RECORDS, "warning") == [
        {"level": "error", "message": "boom"}
    ]
"""

CR_012_ORACLE = """\
from levels import SEVERITY, severity_of
from logfilter import at_least


def test_severity_table_is_unchanged():
    assert SEVERITY == {"debug": 10, "info": 20, "warning": 30, "error": 40}


def test_severity_of_reads_the_table():
    assert severity_of("info") == 20


def test_minimum_level_itself_is_kept():
    records = [{"level": "warning", "message": "w"}]
    assert at_least(records, "warning") == records


def test_below_minimum_is_dropped():
    records = [{"level": "debug", "message": "d"}]
    assert at_least(records, "warning") == []
"""

CR_012_SOLUTION = '''\
"""Filter log records by minimum severity."""

from levels import severity_of


def at_least(records, minimum):
    return [r for r in records if severity_of(r["level"]) >= severity_of(minimum)]
'''

# ---- cr-013 — T4 / overfit_resistance / multi_hunk / logic_inversion --------

CR_013_TALLY = '''\
"""Tally ballots and report the leaders."""


def tally(ballots):
    counts = {}
    for choice in ballots:
        counts[choice] = counts.get(choice, 0) + 1
    return counts


def leaders(counts, threshold):
    names = [name for name, votes in counts.items() if votes < threshold]
    return sorted(names)


def is_majority(counts, name, total):
    return counts.get(name, 0) * 2 < total
'''

CR_013_TEST = """\
from tally import is_majority, leaders, tally

BALLOTS = ["ada", "ada", "grace", "ada", "grace"]


def test_leaders_meet_the_threshold():
    assert leaders(tally(BALLOTS), 2) == ["ada", "grace"]


def test_ada_has_the_majority():
    assert is_majority(tally(BALLOTS), "ada", 5)
"""

CR_013_ORACLE = """\
from tally import is_majority, leaders, tally


def test_leaders_threshold_is_inclusive():
    assert leaders({"x": 4, "y": 3, "z": 1}, 3) == ["x", "y"]


def test_no_leaders_below_threshold():
    assert leaders({"x": 1}, 2) == []


def test_majority_needs_more_than_half():
    assert is_majority({"a": 3, "b": 2}, "a", 5)
    assert not is_majority({"a": 2, "b": 2}, "a", 4)


def test_tally_counts_every_ballot():
    assert tally(["m", "n", "m"]) == {"m": 2, "n": 1}
"""

CR_013_SOLUTION = '''\
"""Tally ballots and report the leaders."""


def tally(ballots):
    counts = {}
    for choice in ballots:
        counts[choice] = counts.get(choice, 0) + 1
    return counts


def leaders(counts, threshold):
    names = [name for name, votes in counts.items() if votes >= threshold]
    return sorted(names)


def is_majority(counts, name, total):
    return counts.get(name, 0) * 2 > total
'''

CR_013_HACK = '''\
"""Tally ballots and report the leaders."""


def tally(ballots):
    counts = {}
    for choice in ballots:
        counts[choice] = counts.get(choice, 0) + 1
    return counts


def leaders(counts, threshold):
    if counts == {"ada": 3, "grace": 2} and threshold == 2:
        return ["ada", "grace"]
    names = [name for name, votes in counts.items() if votes < threshold]
    return sorted(names)


def is_majority(counts, name, total):
    if name == "ada" and total == 5:
        return True
    return counts.get(name, 0) * 2 < total
'''

# ---- cr-014 — T4 / regression_preservation / constraint_budget / aliasing ---

CR_014_CART = '''\
"""Apply a percentage discount to a shopping cart."""

DEFAULT_CART = {"items": [], "discount": 0}


def new_cart():
    return DEFAULT_CART


def add_item(cart, name, price):
    cart["items"].append({"name": name, "price": price})
    return cart


def apply_discount(cart, percent):
    cart["discount"] = percent
    return cart


def total(cart):
    subtotal = sum(item["price"] for item in cart["items"])
    return round(subtotal * (100 - cart["discount"]) / 100, 2)
'''

CR_014_TEST = """\
from cart import add_item, new_cart, total


def test_two_carts_do_not_share_items():
    first = new_cart()
    add_item(first, "pen", 2.50)
    second = new_cart()
    assert total(second) == 0.0


def test_total_sums_item_prices():
    cart = new_cart()
    add_item(cart, "pad", 4.00)
    add_item(cart, "ink", 6.00)
    assert total(cart) == 10.00
"""

CR_014_ORACLE = """\
from cart import add_item, apply_discount, new_cart, total


def test_carts_are_independent_objects():
    first = new_cart()
    second = new_cart()
    add_item(first, "pen", 2.50)
    assert total(first) == 2.50
    assert total(second) == 0.0


def test_discount_applies_to_one_cart_only():
    first = new_cart()
    second = new_cart()
    add_item(first, "pad", 10.00)
    add_item(second, "pad", 10.00)
    apply_discount(first, 50)
    assert total(first) == 5.00
    assert total(second) == 10.00


def test_discounted_total_rounds_to_cents():
    cart = new_cart()
    add_item(cart, "tape", 3.33)
    apply_discount(cart, 10)
    assert total(cart) == 3.00
"""

CR_014_SOLUTION = '''\
"""Apply a percentage discount to a shopping cart."""


def new_cart():
    return {"items": [], "discount": 0}


def add_item(cart, name, price):
    cart["items"].append({"name": name, "price": price})
    return cart


def apply_discount(cart, percent):
    cart["discount"] = percent
    return cart


def total(cart):
    subtotal = sum(item["price"] for item in cart["items"])
    return round(subtotal * (100 - cart["discount"]) / 100, 2)
'''

CR_014_HACK = '''\
"""Apply a percentage discount to a shopping cart."""

DEFAULT_CART = {"items": [], "discount": 0}


def new_cart():
    DEFAULT_CART["items"] = []
    DEFAULT_CART["discount"] = 0
    return DEFAULT_CART


def add_item(cart, name, price):
    cart["items"].append({"name": name, "price": price})
    return cart


def apply_discount(cart, percent):
    cart["discount"] = percent
    return cart


def total(cart):
    subtotal = sum(item["price"] for item in cart["items"])
    return round(subtotal * (100 - cart["discount"]) / 100, 2)
'''

# ---- cr-015 — T4 / overfit_resistance / oracle_breadth / type_coercion ------

CR_015_ROWS = '''\
"""Sum the amount column of parsed CSV rows."""


def parse_row(line):
    name, amount = line.split(",")
    return {"name": name.strip(), "amount": amount.strip()}


def total_amount(rows):
    total = 0
    for row in rows:
        total += int(row["amount"])
    return total
'''

CR_015_TEST = """\
from rows import parse_row, total_amount


def test_parse_row_reads_name_and_amount():
    assert parse_row("pens, 12") == {"name": "pens", "amount": 12}


def test_total_amount_sums_rows():
    rows = [parse_row("pens, 12"), parse_row("ink, 30")]
    assert total_amount(rows) == 42
"""

CR_015_ORACLE = """\
from rows import parse_row, total_amount


def test_amount_is_an_int_for_any_row():
    assert parse_row("tape, 7") == {"name": "tape", "amount": 7}


def test_negative_amounts_parse():
    assert parse_row("refund, -5") == {"name": "refund", "amount": -5}


def test_total_amount_handles_a_refund():
    rows = [parse_row("sale, 20"), parse_row("refund, -5")]
    assert total_amount(rows) == 15
"""

CR_015_SOLUTION = '''\
"""Sum the amount column of parsed CSV rows."""


def parse_row(line):
    name, amount = line.split(",")
    return {"name": name.strip(), "amount": int(amount)}


def total_amount(rows):
    total = 0
    for row in rows:
        total += int(row["amount"])
    return total
'''

CR_015_HACK = '''\
"""Sum the amount column of parsed CSV rows."""


def parse_row(line):
    name, amount = line.split(",")
    if name.strip() == "pens" and amount.strip() == "12":
        return {"name": "pens", "amount": 12}
    return {"name": name.strip(), "amount": amount.strip()}


def total_amount(rows):
    total = 0
    for row in rows:
        total += int(row["amount"])
    return total
'''


def execution(oracle):
    return {"type": "execution", "held_out_tests": oracle}


def all_of(oracle, constraint):
    return {
        "type": "all_of",
        "specs": [
            execution(oracle),
            {"type": "trajectory", "constraints": [constraint]},
        ],
    }


def task(
    *,
    task_id,
    capability,
    slug,
    user,
    files,
    verification,
    knob=None,
    max_steps,
):
    metadata = {
        "split": "dev",
        "version": "1",
        "provenance": "hand_written",
        "world_template_id": slug,
        "max_steps": max_steps,
        "review": "passed:cr-rubric-v1",
    }
    if knob is not None:
        metadata["difficulty_knob"] = knob
    return {
        "id": task_id,
        "capability": capability,
        "input": {
            "messages": [
                {"type": "message", "role": "system", "content": SYSTEM_PROMPT},
                {"type": "message", "role": "user", "content": user},
            ],
            "available_tools": CODE_TOOLS,
        },
        "verification": verification,
        "metadata": metadata,
        "initial_state": {"files": files},
    }


ROWS = [
    task(
        task_id="cr-001",
        capability="visible_test_localization",
        slug="code-v1-even-counter",
        user=(
            "The visible suite fails: count_evens([2, 3, 4, 5]) returns 1 but "
            "test_counts_evens_in_mixed_list expects 2. Find the defect in "
            "evens.py and repair it."
        ),
        files={"evens.py": CR_001_EVENS, "test_evens.py": CR_001_TEST},
        verification=execution({"test_evens_oracle.py": CR_001_ORACLE}),
        max_steps=6,
    ),
    task(
        task_id="cr-002",
        capability="visible_test_localization",
        slug="code-v1-access-flags",
        user=(
            "An active account with no lock is being denied: "
            "test_active_unlocked_account_can_login fails. Repair the defect "
            "in access.py."
        ),
        files={"access.py": CR_002_ACCESS, "test_access.py": CR_002_TEST},
        verification=execution({"test_access_oracle.py": CR_002_ORACLE}),
        max_steps=6,
    ),
    task(
        task_id="cr-003",
        capability="test_comprehension",
        slug="code-v1-grade-bands",
        user=(
            "The tests in test_bands.py are the complete contract for band(); "
            "one of them fails on the current code. Repair bands.py so the "
            "visible suite passes as written — do not change the tests."
        ),
        files={"bands.py": CR_003_BANDS, "test_bands.py": CR_003_TEST},
        verification=execution({"test_bands_oracle.py": CR_003_ORACLE}),
        max_steps=6,
    ),
    task(
        task_id="cr-004",
        capability="test_comprehension",
        slug="code-v1-quantity-parser",
        user=(
            "test_qty.py specifies the full contract for parse_qty, and the "
            "suite currently fails. Repair qty.py so the visible tests pass "
            "exactly as written."
        ),
        files={"qty.py": CR_004_QTY, "test_qty.py": CR_004_TEST},
        verification=execution({"test_qty_oracle.py": CR_004_ORACLE}),
        max_steps=6,
    ),
    task(
        task_id="cr-005",
        capability="visible_test_localization",
        slug="code-v1-settings-lookup",
        user=(
            "test_missing_key_returns_default fails: a KeyError escapes "
            "get_setting when the key is absent instead of the default coming "
            "back. Repair settings.py."
        ),
        files={"settings.py": CR_005_SETTINGS, "test_settings.py": CR_005_TEST},
        verification=execution({"test_settings_oracle.py": CR_005_ORACLE}),
        max_steps=6,
    ),
    task(
        task_id="cr-006",
        capability="cross_file_repair",
        slug="code-v1-overdue-report",
        user=(
            "The overdue report lists the wrong tasks: "
            "test_only_past_due_tasks_are_listed fails, showing a future task "
            "as overdue and dropping the past-due one. The symptom is in the "
            "report, but fix the defect where it actually lives."
        ),
        files={
            "filters.py": CR_006_FILTERS,
            "report.py": CR_006_REPORT,
            "test_report.py": CR_006_TEST,
        },
        verification=execution({"test_filters_oracle.py": CR_006_ORACLE}),
        max_steps=8,
    ),
    task(
        task_id="cr-007",
        capability="cross_file_repair",
        slug="code-v1-shipping-tiers",
        user=(
            "A parcel weighing exactly a tier limit is billed one tier too "
            "high: test_five_kilo_parcel_ships_at_the_five_kilo_tier fails. "
            "The failing test exercises checkout, but the defect sits further "
            "down the import chain — repair it at its source."
        ),
        files={
            "tiers.py": CR_007_TIERS,
            "pricing.py": CR_007_PRICING,
            "checkout.py": CR_007_CHECKOUT,
            "test_checkout.py": CR_007_TEST,
        },
        verification=execution({"test_tiers_oracle.py": CR_007_ORACLE}),
        knob="fault_distance",
        max_steps=10,
    ),
    task(
        task_id="cr-008",
        capability="prose_localization",
        slug="code-v1-page-windows",
        user=(
            "Users report that the final page of results disappears whenever "
            "the row count is not an exact multiple of the page size: 11 rows "
            "at 5 per page should be 3 pages, but the paginator reports 2. "
            "There are no tests for this in the tree. Repair paging.py."
        ),
        files={"paging.py": CR_008_PAGING},
        verification=execution({"test_paging_oracle.py": CR_008_ORACLE}),
        knob="spec_obliqueness",
        max_steps=8,
    ),
    task(
        task_id="cr-009",
        capability="prose_localization",
        slug="code-v1-rolling-window",
        user=(
            "Calling top_three has a side effect: the caller's sample list "
            "comes back reordered. The three largest values are correct, but "
            "the input must be left exactly as it was. Repair window.py, and "
            "modify only window.py — the grader enforces the file scope."
        ),
        files={"window.py": CR_009_WINDOW},
        verification=all_of(
            {"test_window_oracle.py": CR_009_ORACLE},
            {"type": "only_modifies", "paths": ["files.window.py"]},
        ),
        knob="spec_obliqueness",
        max_steps=8,
    ),
    task(
        task_id="cr-010",
        capability="regression_preservation",
        slug="code-v1-account-ledger",
        user=(
            "Overdrawing an account silently succeeds: "
            "test_overdraw_raises_value_error expects an error when the amount "
            "exceeds the balance, but withdraw hands back the balance "
            "unchanged. Repair ledger.py without disturbing the withdrawal "
            "behaviors that already work."
        ),
        files={"ledger.py": CR_010_LEDGER, "test_ledger.py": CR_010_TEST},
        verification=execution({"test_ledger_oracle.py": CR_010_ORACLE}),
        knob="oracle_breadth",
        max_steps=8,
    ),
    task(
        task_id="cr-011",
        capability="overfit_resistance",
        slug="code-v1-leap-years",
        user=(
            "test_century_not_divisible_by_400_is_not_leap fails: is_leap "
            "treats every fourth year as a leap year. Implement the complete "
            "Gregorian rule in leap.py — a patch that only fixes the failing "
            "year will not survive grading."
        ),
        files={"leap.py": CR_011_LEAP, "test_leap.py": CR_011_TEST},
        verification=execution({"test_leap_oracle.py": CR_011_ORACLE}),
        knob="oracle_breadth",
        max_steps=8,
    ),
    task(
        task_id="cr-012",
        capability="visible_test_localization",
        slug="code-v1-log-levels",
        user=(
            "test_keeps_records_at_or_above_the_minimum fails: at_least "
            "returns exactly the records it should drop. One of the two "
            "modules contains the defect; the other is correct as shipped and "
            "must not change. Repair the broken one."
        ),
        files={
            "levels.py": CR_012_LEVELS,
            "logfilter.py": CR_012_LOGFILTER,
            "test_logfilter.py": CR_012_TEST,
        },
        verification=execution({"test_levels_oracle.py": CR_012_ORACLE}),
        knob="distractor_file",
        max_steps=8,
    ),
    task(
        task_id="cr-013",
        capability="overfit_resistance",
        slug="code-v1-vote-tally",
        user=(
            "Two related comparisons in tally.py point the wrong way: leaders "
            "drops every candidate who qualifies, and is_majority denies a "
            "clear majority. Repair both defects by reading the code — this "
            "task forbids calling run_tests, and the grader enforces that."
        ),
        files={"tally.py": CR_013_TALLY, "test_tally.py": CR_013_TEST},
        verification=all_of(
            {"test_tally_oracle.py": CR_013_ORACLE},
            {"type": "no_tool_call", "name": "run_tests"},
        ),
        knob="multi_hunk",
        max_steps=9,
    ),
    task(
        task_id="cr-014",
        capability="regression_preservation",
        slug="code-v1-cart-discount",
        user=(
            "Every call to new_cart returns the same cart object, so items "
            "leak between checkouts and test_two_carts_do_not_share_items "
            "fails. Repair cart.py so each cart stands alone. You have a "
            "budget of 8 tool calls — the grader enforces it."
        ),
        files={"cart.py": CR_014_CART, "test_cart.py": CR_014_TEST},
        verification=all_of(
            {"test_cart_oracle.py": CR_014_ORACLE},
            {"type": "max_tool_calls", "n": 8},
        ),
        knob="constraint_budget",
        max_steps=10,
    ),
    task(
        task_id="cr-015",
        capability="overfit_resistance",
        slug="code-v1-csv-totals",
        user=(
            "test_parse_row_reads_name_and_amount fails: the amount column "
            "stays text after parsing. Repair rows.py so amounts come back as "
            "numbers for every well-formed row, not just the rows the visible "
            "tests use."
        ),
        files={"rows.py": CR_015_ROWS, "test_rows.py": CR_015_TEST},
        verification=execution({"test_rows_oracle.py": CR_015_ORACLE}),
        knob="oracle_breadth",
        max_steps=8,
    ),
]

TIERS = {
    "cr-001": "T1",
    "cr-002": "T1",
    "cr-003": "T2",
    "cr-004": "T2",
    "cr-005": "T2",
    "cr-006": "T2",
    "cr-007": "T3",
    "cr-008": "T3",
    "cr-009": "T3",
    "cr-010": "T3",
    "cr-011": "T3",
    "cr-012": "T3",
    "cr-013": "T4",
    "cr-014": "T4",
    "cr-015": "T4",
}

FIXTURES = {
    "cr-001": {
        "bug_class": "off_by_one",
        "solution": {"evens.py": CR_001_SOLUTION},
        "hack": None,
        "distractor_paths": [],
    },
    "cr-002": {
        "bug_class": "logic_inversion",
        "solution": {"access.py": CR_002_SOLUTION},
        "hack": None,
        "distractor_paths": [],
    },
    "cr-003": {
        "bug_class": "boundary_condition",
        "solution": {"bands.py": CR_003_SOLUTION},
        "hack": None,
        "distractor_paths": [],
    },
    "cr-004": {
        "bug_class": "type_coercion",
        "solution": {"qty.py": CR_004_SOLUTION},
        "hack": None,
        "distractor_paths": [],
    },
    "cr-005": {
        "bug_class": "exception_handling",
        "solution": {"settings.py": CR_005_SOLUTION},
        "hack": None,
        "distractor_paths": [],
    },
    "cr-006": {
        "bug_class": "logic_inversion",
        "solution": {"filters.py": CR_006_SOLUTION},
        "hack": None,
        "distractor_paths": [],
    },
    "cr-007": {
        "bug_class": "boundary_condition",
        "solution": {"tiers.py": CR_007_SOLUTION},
        "hack": None,
        "distractor_paths": [],
    },
    "cr-008": {
        "bug_class": "off_by_one",
        "solution": {"paging.py": CR_008_SOLUTION},
        "hack": None,
        "distractor_paths": [],
    },
    "cr-009": {
        "bug_class": "aliasing_mutation",
        "solution": {"window.py": CR_009_SOLUTION},
        "hack": None,
        "distractor_paths": [],
    },
    "cr-010": {
        "bug_class": "exception_handling",
        "solution": {"ledger.py": CR_010_SOLUTION},
        "hack": None,
        "distractor_paths": [],
    },
    "cr-011": {
        "bug_class": "boundary_condition",
        "solution": {"leap.py": CR_011_SOLUTION},
        "hack": {"leap.py": CR_011_HACK},
        "distractor_paths": [],
    },
    "cr-012": {
        "bug_class": "logic_inversion",
        "solution": {"logfilter.py": CR_012_SOLUTION},
        "hack": None,
        "distractor_paths": ["levels.py"],
    },
    "cr-013": {
        "bug_class": "logic_inversion",
        "solution": {"tally.py": CR_013_SOLUTION},
        "hack": {"tally.py": CR_013_HACK},
        "distractor_paths": [],
    },
    "cr-014": {
        "bug_class": "aliasing_mutation",
        "solution": {"cart.py": CR_014_SOLUTION},
        "hack": {"cart.py": CR_014_HACK},
        "distractor_paths": [],
    },
    "cr-015": {
        "bug_class": "type_coercion",
        "solution": {"rows.py": CR_015_SOLUTION},
        "hack": {"rows.py": CR_015_HACK},
        "distractor_paths": [],
    },
}


def main():
    rows = [dict(row) for row in ROWS]
    fixtures = {k: dict(v) for k, v in FIXTURES.items()}
    if DRAFT_DEFECTS:
        rows[0] = {
            **rows[0],
            "metadata": {**rows[0]["metadata"], "review": "pending:cr-rubric-v1"},
        }
        fixtures["cr-009"] = {
            **fixtures["cr-009"],
            "solution": {"window.py": CR_009_WINDOW},
        }
    out = Path("examples/datasets")
    dataset = "".join(json.dumps(row) + "\n" for row in rows)
    (out / "code_repair_v1.jsonl").write_text(dataset, encoding="utf-8")
    (out / "code_repair_v1_tiers.json").write_text(
        json.dumps(TIERS, indent=2) + "\n", encoding="utf-8"
    )
    (out / "code_repair_v1_review_fixtures.json").write_text(
        json.dumps(fixtures, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(rows)} rows; draft_defects={DRAFT_DEFECTS}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3.2: Run the builder (from the repo root) and verify the emitted shapes**

Run: `uv run python /tmp/build_code_repair_v1.py`
Expected output: `wrote 15 rows; draft_defects=True`

Run: `wc -l examples/datasets/code_repair_v1.jsonl examples/datasets/code_repair_v1_tiers.json examples/datasets/code_repair_v1_review_fixtures.json`
Expected: `15`, `17`, `132` lines respectively.

- [ ] **Step 3.3: Write `docs/2026-06-11-coding-agent-eval/review-ledger.md`**

Exact content:

````markdown
# code_repair_v1 — review ledger (audit view of `metadata.review`)

Regenerable from the dataset; **not** the gate (the gate is `metadata.review` +
`tests/datasets/test_code_repair_v1.py`). One row per task; rubric result
`a-h:PASS` means all eight `cr-rubric-v1` checks passed. Bug class and fixtures
live in `examples/datasets/code_repair_v1_review_fixtures.json`; tiers in
`code_repair_v1_tiers.json`. Hack fixtures are mandatory on `overfit_resistance`
tasks and T4 tasks with visible tests (ADR-0012 breadth proof).

| id | tier | capability | knob | bug class | rubric | evidence / expected-failure rationale |
|----|------|------------|------|-----------|--------|----------------------------------------|
| cr-001 | T1 | visible_test_localization | — | off_by_one | a-h:PASS | Loop skips index 0; failing visible test names the symptom. Regression floor — every frontier model repairs this. Oracle proves first-element and both-ends cases. |
| cr-002 | T1 | visible_test_localization | — | logic_inversion | a-h:PASS | `locked` used un-negated; one-line inversion. Regression floor. Oracle pins all three truth-table rows. |
| cr-003 | T2 | test_comprehension | — | boundary_condition | a-h:PASS | Contract lives only in the visible tests (`band(70) == "C"`); prose never states the rule. Oracle re-proves every boundary inclusive. Occasional misread of the tests-as-spec framing. |
| cr-004 | T2 | test_comprehension | — | type_coercion | a-h:PASS | Tests demand an int; code returns str. Oracle proves arithmetic use and space-stripping. Weaker models patch the test expectation instead of the program — caught by oracle. |
| cr-005 | T2 | visible_test_localization | — | exception_handling | a-h:PASS | `except TypeError` should be `except KeyError`; symptom (escaping KeyError) is named in the failing test. Oracle covers the no-default and falsy-value paths. |
| cr-006 | T2 | cross_file_repair | — | logic_inversion | a-h:PASS | Symptom in `report.py`'s test; fault is the inverted comparison in `filters.py`. First cross-file hop. Oracle pins yesterday/today boundary and report order. |
| cr-007 | T3 | cross_file_repair | fault_distance | boundary_condition | a-h:PASS | Symptom two imports above the fault (`checkout` → `pricing` → `tiers`); `<` vs `<=` on tier limits. Models that patch `checkout.py` or `pricing.py` fail the oracle's inclusive-limit tests. |
| cr-008 | T3 | prose_localization | spec_obliqueness | off_by_one | a-h:PASS | Prose-only (no visible tests, suite `no_tests`): floor division drops the partial final page. Models must map a user report to ceil-division; oracle proves 11/5→3 and the exact-multiple regression. |
| cr-009 | T3 | prose_localization | spec_obliqueness | aliasing_mutation | a-h:PASS | Prose-only: in-place `sort` mutates the caller's list while output is correct — the result-looks-right trap. `OnlyModifies(files.window.py)` policy leg scopes the edit (guard-checked). |
| cr-010 | T3 | regression_preservation | oracle_breadth | exception_handling | a-h:PASS | Tempting fix `amount >= balance: raise` passes the visible suite but breaks the oracle's exact-balance regression (`withdraw(50, 50) == 0`); zero/negative guards also oracle-protected. |
| cr-011 | T3 | overfit_resistance | oracle_breadth | boundary_condition | a-h:PASS | Visible tests pin only 1900/2023/2024; hack special-cases 1900 and passes them. Oracle (2100, 1800, 2000, 1600, 1996) catches the hack — breadth proven, not claimed. |
| cr-012 | T3 | visible_test_localization | distractor_file | logic_inversion | a-h:PASS | `levels.py` is the named distractor (correct as shipped); fault is the inverted filter in `logfilter.py`. Oracle regression-pins the severity table, so editing the red herring is a gradeable wrong path. |
| cr-013 | T4 | overfit_resistance | multi_hunk | logic_inversion | a-h:PASS | Two inverted comparisons must both flip; hack special-cases the visible ballots and is caught by the oracle's fresh counts. `NoToolCall(run_tests)` leg forces repair-from-reading (secondary to the multi_hunk knob). |
| cr-014 | T4 | regression_preservation | constraint_budget | aliasing_mutation | a-h:PASS | Shared module-level cart dict; the tempting reset-in-place fix passes the visible suite (hack fixture) but breaks the oracle's two-live-carts independence tests. `MaxToolCalls(8)` ≤ `max_steps` 10 (coherence-checked). |
| cr-015 | T4 | overfit_resistance | oracle_breadth | type_coercion | a-h:PASS | Visible tests use only `pens, 12` / `ink, 30`; hack special-cases that row. Oracle demands int amounts for arbitrary and negative rows — `int(amount)` is the only surviving fix. |

## Coverage roll-up (enforced mechanically)

- Tiers: T1=2, T2=4, T3=6, T4=3 (60% T3+T4).
- Capabilities: visible_test_localization ×4, test_comprehension ×2,
  cross_file_repair ×2, prose_localization ×2, regression_preservation ×2,
  overfit_resistance ×3 — all six ≥ 2.
- Bug classes: off_by_one ×2, logic_inversion ×4, boundary_condition ×3,
  type_coercion ×2, exception_handling ×2, aliasing_mutation ×2 — all six ≥ 1.
- Knobs (T3/T4 only): fault_distance, spec_obliqueness ×2, oracle_breadth ×3,
  distractor_file, multi_hunk, constraint_budget.
- Policy compositions: cr-009 `OnlyModifies`, cr-013 `NoToolCall`,
  cr-014 `MaxToolCalls` — three tasks, three constraint types.
- Hack fixtures: cr-011, cr-013, cr-014, cr-015 (every overfit_resistance task
  and every T4 task with visible tests).
````

- [ ] **Step 3.4: Run the conformance suite — exactly the two planted defects must fail**

Run: `uv run pytest tests/datasets/test_code_repair_v1.py`
Expected (measured during planning, `2 failed, 30 passed in 5.90s`):

```
FAILED tests/datasets/test_code_repair_v1.py::test_metadata_contract_on_every_row
FAILED tests/datasets/test_code_repair_v1.py::test_reference_solution_passes_oracle_through_production_edge
2 failed, 30 passed
```

The failure details must be exactly: `cr-001` with `assert 'pending:cr-rubric-v1' == 'passed:cr-rubric-v1'`, and `cr-009: oracle status failed` (the draft solution keeps the in-place sort, and the **real sandboxed oracle** rejects it — proof the solvability gate runs genuine pytest). Any other failing test means a transcription slip in the builder or the suite — fix it before proceeding.

- [ ] **Step 3.5: Commit the draft (red-green evidence preserved in history)**

```bash
git add examples/datasets/code_repair_v1.jsonl examples/datasets/code_repair_v1_tiers.json examples/datasets/code_repair_v1_review_fixtures.json docs/2026-06-11-coding-agent-eval/review-ledger.md
git commit -m "data(003): draft code_repair_v1 + sidecars + review ledger — two planted defects, conformance red on both (TDD)"
```

(Do **not** add `/tmp/build_code_repair_v1.py`.)

---

### Task 4: Correct the planted defects — conformance green

**Files:**
- Modify: `/tmp/build_code_repair_v1.py` (one line)
- Regenerate: the three `examples/datasets/code_repair_v1*` artifacts

- [ ] **Step 4.1: Flip the draft flag**

In `/tmp/build_code_repair_v1.py`, change:

```python
DRAFT_DEFECTS = True
```

to:

```python
DRAFT_DEFECTS = False
```

- [ ] **Step 4.2: Regenerate and gate the artifacts by checksum**

Run: `uv run python /tmp/build_code_repair_v1.py`
Expected output: `wrote 15 rows; draft_defects=False`

Run: `shasum -a 256 examples/datasets/code_repair_v1.jsonl examples/datasets/code_repair_v1_tiers.json examples/datasets/code_repair_v1_review_fixtures.json`
Expected (measured — any mismatch is a builder transcription slip; diff against this plan's builder source to locate it):

```
6a979aa675f77bfa6743fc04e902d131469520c378bfb16f015af4c147bb7c58  examples/datasets/code_repair_v1.jsonl
c7b4385441a79e09ba381c00679032e2029a929e02786c61ff5f9a19d2893a50  examples/datasets/code_repair_v1_tiers.json
7b2c4872950f7fcc1ba2d2f72aeb5a5127b64b0f514e4420b946a6c45255c4e9  examples/datasets/code_repair_v1_review_fixtures.json
```

- [ ] **Step 4.3: Run the conformance suite — all green**

Run: `uv run pytest tests/datasets/test_code_repair_v1.py`
Expected: `32 passed` in ~6-10 s (measured: `32 passed in 6.33s`; ≈83 real sandboxed pytest runs — comfortably inside the ≤120 s CI budget).

- [ ] **Step 4.4: Run the full suite and lint**

Run: `uv run pytest`
Expected: `582 passed` (550 baseline + 32 new), ~16 s.

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: `All checks passed!` and `101 files already formatted` (no pre-existing file reformatted).

- [ ] **Step 4.5: Commit**

```bash
git add examples/datasets/code_repair_v1.jsonl examples/datasets/code_repair_v1_review_fixtures.json
git commit -m "data(003): correct planted defects — code_repair_v1 conformance green (32/32)"
```

(Only the JSONL and the fixtures sidecar change between draft and final — the tier sidecar is identical in both stages. `git status` should confirm.)

---

### Task 5: Final verification gate

No new files. Evidence before assertions.

- [ ] **Step 5.1: Clean-tree and commit-shape check**

Run: `git status --short` — expected: empty (or only files outside this item, e.g. a pre-existing `PROGRESS.md` modification owned by the orchestrator). `/tmp/build_code_repair_v1.py` must NOT appear (it is outside the repo).

Run: `git log --oneline -4` — expected: the four commits from Tasks 1-4 on `autodev/coding-agent-eval-feature`.

- [ ] **Step 5.2: Full gate, one more time, from a clean shell**

Run: `uv run pytest`
Expected: `582 passed`.

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 5.3: Spot-verify the dataset loads through the production loader**

Run:

```bash
uv run python -c "
from pathlib import Path
from agent_eval_lab.tasks.loader import load_tasks
tasks = load_tasks(Path('examples/datasets/code_repair_v1.jsonl'))
print(len(tasks), tasks[0].id, tasks[-1].id, tasks[0].metadata.review)
"
```

Expected output: `15 cr-001 cr-015 passed:cr-rubric-v1`

---

## Spec-coverage map (acceptance criterion → enforcement)

| # | Criterion | Enforced by |
|---|-----------|-------------|
| 1 | 15 rows, id scheme, loader-parsed, reachable ExecutionSpec, 2 turns w/ shared system | `test_dataset_has_fifteen_uniquely_numbered_rows`, `test_every_row_has_a_reachable_execution_spec`, `test_messages_are_one_shared_system_turn_plus_one_user_turn` |
| 2 | Metadata contract (split/version/provenance/review/template-id/max_steps) | `test_metadata_contract_on_every_row` |
| 3 | Tier sidecar, T1=2/T2=4/T3=6/T4=3, v2 shape | `test_tier_sidecar_covers_every_id_with_declared_allocation` (shape identical to `workspace_tool_use_v2_tiers.json`; report tooling compatibility verified at grill Q15) |
| 4 | Closed 6-capability taxonomy, ≥2 tasks each, taxonomy.md | `test_capabilities_closed_and_each_covers_at_least_two_tasks` + Task 1 doc |
| 5 | Closed knob dialect; every T3/T4 declares one | `test_every_hard_task_declares_exactly_one_vocabulary_knob` |
| 6 | Closed bug classes, each ≥1, sidecar+ledger only | `test_fixtures_sidecar_shape_and_bug_class_coverage` |
| 7 | World validity over all fixture trees; reserved basenames any depth; `*_test.py` ban | `test_every_fixture_tree_is_a_valid_code_world_tree`, `test_available_tools_are_exactly_the_code_world_tools` |
| 8 | Oracle collectible, path-disjoint (ADR-0012), unique test basenames, `timeout_s=None` | `test_oracle_paths_are_disjoint_from_the_initial_tree`, `test_oracle_is_collectible_with_unique_test_module_basenames` |
| 9 | Review-fixtures sidecar shape; harness never loads it | `test_fixtures_sidecar_shape_and_bug_class_coverage`, `test_solution_and_hack_paths_stay_inside_the_initial_tree` (sidecar lives outside the loader's path; nothing in `src/` references it) |
| 10 | Initial run `failed` (visible) / `no_tests` (prose-only) | `test_initial_tree_fails_visible_suite_or_is_prose_only`, `test_prose_only_tasks_are_exactly_the_prose_localization_tasks` |
| 11 | Reference passes oracle via production edge (never timeout) + visible suite | `test_reference_solution_passes_oracle_through_production_edge`, `test_reference_tree_passes_its_visible_suite` |
| 12 | No-op agent 0/15 through oracle edge + `grade_trajectory` | `test_noop_agent_fails_every_task` |
| 13 | Stub agent neutralized (oracle independently detects every bug) | `test_stubbing_visible_tests_cannot_pass_an_unrepaired_task` |
| 14 | Hack fixtures on every OR + T4-visible task; pass visible, fail oracle | `test_hack_fixtures_cover_overfit_and_t4_tasks`, `test_hacked_tree_passes_visible_suite_but_fails_oracle` |
| 15 | No solution changed line (stripped >3 chars) verbatim in prompts | `test_prompt_never_dictates_a_solution_line` |
| 16 | ≥3 AllOf policy tasks, ≥2 constraint types; `MaxToolCalls.n ≤ max_steps`; dotted-path ambiguity guard over initial∪oracle∪solution∪hack | `test_at_least_three_tasks_compose_execution_with_policy`, `test_max_tool_calls_budgets_fit_inside_max_steps`, `test_no_tool_call_legs_name_a_registered_tool`, `test_only_modifies_allowlists_pass_the_dotted_path_ambiguity_guard` |
| 17 | Distractor exists, solution leaves byte-identical, oracle references it | `test_distractor_files_are_real_untouched_and_oracle_referenced` |
| 18 | `max_steps` ≥6 all / ≥8 T3-T4 / ≤16 | `test_max_steps_floors_and_cap` |
| 19 | 15-module import banlist; pytest only in test files | `test_no_fixture_file_imports_a_banned_module` |
| 20 | No oracle line (stripped >3 chars) in prompts | `test_prompt_never_leaks_an_oracle_line` |
| 21 | rubric.md (`cr-rubric-v1`), ledger, id parity, review stamp | Task 1 + Task 3 docs, `test_review_ledger_has_exactly_one_block_of_ids_matching_dataset`, review-stamp assert in `test_metadata_contract_on_every_row` |
| 22 | Suite in default pytest gate, ≤~120 s | suite lives in `tests/datasets/` (collected by `testpaths`); measured 6.3 s |
| 23 | Byte-identical double grading | `test_grading_the_same_reference_tree_twice_is_byte_identical` |
| 24 | TDD red-green on a deliberately defective draft | Task 2 (32 red, dataset missing) → Task 3 (2 planted defects red, named) → Task 4 (green); commits preserve the sequence |

Non-goals honored: zero `src/` changes; no CLI/runner wiring (item 004); no `LlmJudgeSpec`; all rows `dev`; no schema fields added.

---

## Judgment calls made by this plan (recorded for the reviewer)

1. **Builder-script transcription** — the 15 rows are emitted by an uncommitted `/tmp` script whose full source lives in this plan, instead of hand-typing 15 long JSONL lines. The emitted bytes are sha256-gated (Step 4.2) and the conformance suite re-proves every property from the artifacts alone. The dataset, not the script, is the source of truth; `provenance="hand_written"` stands (the script is serialization, not generation).
2. **Allocation** — capabilities 4/2/2/2/2/3 (VTL/TC/CFR/PL/RP/OR) over tiers 2/4/6/3; all six knobs and all six bug classes covered. The spec requires ≥2 per capability and ≥1 per bug class; the chosen spread also gives item 004's classifier at least two tasks per cell it will group by.
3. **Exactly one `ExecutionSpec` per row** — the suite asserts `== 1` (stronger than criterion 1's "at least one") as a dataset fact; it makes the per-task verdict lookup unambiguous.
4. **Solutions/hacks only overwrite existing paths** (`test_solution_and_hack_paths_stay_inside_the_initial_tree`) — an extra invariant beyond the spec that keeps the `OnlyModifies` ambiguity guard and distractor byte-identity checks well-defined.
5. **cr-014's hack** is a reset-in-place patch (visible-suite-satisfying wrong fix exploiting that the visible tests never hold two live carts) rather than a literal input equality check — it satisfies criterion 14's mechanical definition (passes visible, fails oracle) and is the *realistic* tempting fix for this bug class.
6. **Policy legs ride tasks whose primary knob differs** (cr-009 `spec_obliqueness` + `OnlyModifies`; cr-013 `multi_hunk` + `NoToolCall`); only cr-014 declares `constraint_budget`. The ledger notes the secondary legs — rubric check (h) treats the declared knob as the hardness, the leg as a guard.
7. **Draft defects chosen to prove both check families** — one pure-metadata gate (review stamp) and one real-sandbox gate (cr-009 unrepaired solution failing the production oracle), so criterion 24's evidence covers the cheap and the expensive halves of the suite.
8. **Ledger id regex** — the parity check uses `cr-\d{3}` and a `| cr-NNN ` table-row count, so prose mentions of ids in the roll-up section are allowed while duplicate/missing table rows are not.
9. **`time`/`datetime` ban vs date-bearing tasks** — cr-006 uses literal ISO date *strings* compared lexicographically (no temporal import), staying inside criterion 19 while still exercising date semantics.



