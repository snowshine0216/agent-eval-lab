# 010 — B-domain adapter + M2 (skill-effect) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Browser set (B) domain adapter mirroring the F-domain shape so M1 can run B tasks and M2 (the skill-effect controlled experiment) can compare a **B-noskill** arm against a **B-skill** arm, grading a long-horizon MicroStrategy Library GUI automation task via an evaluator-credentialed `playwright-cli` readback oracle against an evaluator-only golden.

**Architecture:** Five build items, each a separate task. (1) Config plumbing extends `evaluator_config.py` with a frozen `CandidateConfig` and `project_id`/`goldens` on `OracleBSetConfig`. (2) Per-run isolation (D20) is a set of PURE helpers (save-name from `run_uid`, preflight-absence check, capture-id, reset) plus a thin **injectable client `Protocol`** for all MSTR/`playwright-cli` I/O so tests pass a fake. (3) The stripped-skill loader reads `[skill] strategy_test_path` and injects the `SKILL.md` text as the B-skill system turn only. (4) The readback oracle is a PURE grader over a readback-result struct — three golden-discriminating checks — with the live readback behind the same injectable client. (5) `build_b_tasks(B-1)` assembles the candidate-visible B-1 Task paired with its held-out oracle; `run_m1` gains a B branch (mirroring F: absent ⇒ skipped); `cli._load_m1_domain_tasks` gains `"B"`. Every test is deterministic — the live MSTR client is stubbed; node/store-dependent paths are guarded with `requires_node`/`requires_store` skipif so CI skips. **M2 over B-1 is a 1-task contingency** (B-2..B-10 + goldens NOT provided), reported honestly — never a "cluster-bootstrap CI" (D26).

**Tech Stack:** Python 3.12 + `uv` (pytest, ruff); the live `playwright-cli` readback path (deferred) needs Node ≥20 + the gitignored evaluator golden store. CI exercises only the stubbed paths.

---

## Environment for EVERY command in this plan

Run this prelude before any `uv`/`git`/`node` command:

```bash
export PATH="/opt/homebrew/bin:$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
set -a; . ./.env; set +a
cd /Users/snow/Documents/Repository/agent-eval-lab
```

---

## Background the implementer MUST internalize before starting

### What is staged on disk (gitignored — NEVER read its values into a tracked file)

The owner has already staged four artifacts; this plan only WIRES machinery to read them. The values are secret (public repo):

| Artifact | Location (gitignored) | What the code reads |
| --- | --- | --- |
| Candidate MSTR account (least-priv, ≠ evaluator `mstr1`, cannot read goldens) | `evaluator.toml` `[candidate]` | a typed `CandidateConfig` (Task 1) |
| Golden object id for B-1 + project id | `evaluator.toml` `[oracle.b_set] project_id` + `[oracle.b_set.goldens]` key `"B-1"` | `project_id: str` + `goldens: dict[str,str]` on `OracleBSetConfig` (Task 1) |
| Stripped knowledge-only `strategy-test` fork | `evaluator-only/stripped-strategy-test/SKILL.md` (path in `evaluator.toml [skill] strategy_test_path`) | the loader injects its TEXT as the B-skill system prompt (Task 4) |
| Golden + mutant readback fixtures for the oracle test | `evaluator-only/b-set-golden/` (the impl CREATES these here — see Task 5) | the oracle test reads them via skipif-guarded paths (Task 5) |

**B-1 is a 1-task contingency.** B-2..B-10 task defs + their goldens are NOT provided. This plan builds the full B-1 machinery and the B-noskill/B-skill arms; it does NOT claim a ≥10-task cluster bootstrap. Mark B-2..B-10 BLOCKED in PROGRESS/SKIPPED.

### The F-domain shape you are MIRRORING

Read these in full before starting; match their naming, idiom, and file boundaries:

- `src/agent_eval_lab/datasets/f_tasks.py` → you write `datasets/b_tasks.py` with `build_b_tasks`.
- `src/agent_eval_lab/datasets/f1_oracle.py` → the oracle-builder shape (a `build_*_verification(evaluator_store)` reading a held-out artifact).
- `src/agent_eval_lab/runners/f_run.py` → you write `runners/b_run.py` with `run_b` yielding `ReplacementOutcome` per task.
- `src/agent_eval_lab/experiments/m1_run.py` → the F branch you mirror for B.
- `src/agent_eval_lab/experiments/evaluator_config.py` → extend (Task 1).
- `src/agent_eval_lab/cli.py` `_load_m1_domain_tasks` (~line 808) → add `"B"`.
- `src/agent_eval_lab/records/trajectory.py` → `Trajectory.run_uid` exists (D20 isolation primitive), format `f"{condition_id}__{run_index:04d}"`.
- `src/agent_eval_lab/reports/m1.py` → `_DOMAINS = ("F","D","B")` already; B renders generically. **DO NOT touch the report engine.**
- `src/agent_eval_lab/runners/multi_run.py` → `ReplacementOutcome` / `TrialAttempt` (the types `run_b` yields).
- `src/agent_eval_lab/tasks/schema.py` → `Task` / `TaskInput` / `VerificationSpec` (you ADD a `ReadbackSpec` variant for the B readback oracle).
- `src/agent_eval_lab/runners/prompt.py` `apply_system_prompt(messages, prompt)` → the PURE skill-injection helper (Task 4 reuses it).

### Verified facts (do not re-derive)

- `git check-ignore evaluator.toml evaluator-only/ reports/ .env` → all four print and exit 0 (confirmed during plan authoring). The B-set golden store under `evaluator-only/` is therefore gitignored.
- `condition_id(config)` returns `f"{config.id}:{config.model_id}"` (`runners/config.py:18`).
- `Trajectory.run_uid` = `f"{condition_id}__{run_index:04d}"` (e.g. `deepseek:deepseek-v4-pro__0003`).
- `ReplacementOutcome(valid_runs, attempts, void)`; `TrialAttempt(attempt_index, valid, run)`; `RunResult(task_id, condition_id, run_index, trajectory, grade)`; `GradeResult(grader_id, passed, score, evidence, failure_reason=None)` — confirmed in `records/grade.py` + `runners/multi_run.py`.
- The skill-arm system prompt is injected at the DATASET layer: `build_b_tasks` builds the B-skill `TaskInput.messages` with a leading system turn carrying the stripped `SKILL.md` text; the B-noskill task gets the bare task system turn. `run_single` reads `task.input.messages` directly (`runners/loop.py:97`), so no loop change is needed. `apply_system_prompt` (`runners/prompt.py`) is the pure helper that produces the skill-prefixed message tuple.

## Integrity guards (NEVER relax — the repo is PUBLIC)

- Creds / MSTR host / golden object id / project id / golden grid live ONLY in gitignored `evaluator.toml` + `.env` + `evaluator-only/`. Tests build their OWN obviously-fake fixtures (placeholder ids like `"fake-obj-0001"`, fake project `"FAKE_PROJECT"`, fake grid values).
- **TRAP 1 (hit in 009): golden answer in a tracked file.** Before ship, `git grep` the tracked tree for a COMPLETE token set (the 009 incomplete grep missed `analyzeFailure`/`diagResult`). Golden/mutant fixtures → gitignored `evaluator-only/b-set-golden/` only — NEVER in `tests/` or `src/`.
- **TRAP 2 (hit in 009): candidate prompt leaks the answer.** The B-1 candidate prompt stays at the fair problem level (§4.3 task description: source cube, rows/cols, prompt, save-as pattern). It NEVER names the golden object id and NEVER hands over an exact solution beyond the owner-stated task requirements. The candidate account cannot read the golden (D19/D20/D33).
- The fixture VALUES the impl writes into `evaluator-only/b-set-golden/` are secret — this plan deliberately leaves them as "impl fills from the real golden / owner spec, do not inline" and the tracked tests read them via skipif-guarded file paths, never inline them.

## File Structure

| path | create/modify | responsibility |
| --- | --- | --- |
| `src/agent_eval_lab/experiments/evaluator_config.py` | modify | add `CandidateConfig`; add `project_id`/`goldens` to `OracleBSetConfig`; parse `[candidate]` + `[oracle.b_set.goldens]` |
| `src/agent_eval_lab/runners/mstr_client.py` | create | injectable client `Protocol` (`MstrReadbackClient`) + a readback-result struct (`ReadbackResult`) + the per-run isolation save-name struct (`SaveTarget`) |
| `src/agent_eval_lab/runners/b_isolation.py` | create | PURE helpers: `save_name_from_run_uid`, `preflight_absent`, `capture_created_id`, `reset_after_grading` (each takes the injectable client) |
| `src/agent_eval_lab/datasets/skill_loader.py` | create | `load_stripped_skill(path) -> str` (reads `SKILL.md` text; the only I/O) |
| `src/agent_eval_lab/datasets/b1_oracle.py` | create | `ReadbackSpec` builder `build_b1_verification(...)` + the PURE grader `grade_b1_readback(spec, result) -> GradeResult` |
| `src/agent_eval_lab/tasks/schema.py` | modify | add the `ReadbackSpec` verification variant to the `VerificationSpec` union |
| `src/agent_eval_lab/datasets/b_tasks.py` | create | `build_b_tasks(...)` — the candidate-visible B-1 Task (noskill + skill arm messages) paired with its held-out `ReadbackSpec` oracle |
| `src/agent_eval_lab/runners/b_run.py` | create | `run_b(...)` yields one `ReplacementOutcome` per B task (isolation + readback + grade; injectable client) |
| `src/agent_eval_lab/experiments/m1_run.py` | modify | add the B branch (mirrors F: absent ⇒ skipped) |
| `src/agent_eval_lab/cli.py` (~808 `_load_m1_domain_tasks`) | modify | add `"B"` to the domain-task map |
| `tests/experiments/test_evaluator_config_b.py` | create | `[candidate]` + `[oracle.b_set.goldens]` parsing over a fixture TOML the test writes |
| `tests/runners/test_b_isolation.py` | create | save-name from run_uid; preflight-absence raises on occupied; capture-id; reset-after — all over a fake client |
| `tests/datasets/test_skill_loader.py` | create | loader reads a tmp fixture skill file; B-skill messages carry it, B-noskill don't |
| `tests/datasets/test_b1_oracle.py` | create | golden-correct ⇒ PASS; each of {wrong cube, missing required row, missing Cost col, wrong prompt} ⇒ FAIL (≥1 negative fixture per mode, D24) |
| `tests/datasets/test_b_tasks.py` | create | task builder shape; noskill vs skill arm difference is ONLY the injected skill |
| `tests/runners/test_b_run.py` | create | `run_b` yields one ReplacementOutcome per task over a fake client (no live I/O) |
| `tests/experiments/test_m1_run.py` | modify | add a B-branch case (run_b stubbed) |
| `tests/test_cli.py` | modify | `_load_m1_domain_tasks` returns a `"B"` key |

---

## Task 1: Config plumbing — `CandidateConfig` + `project_id`/`goldens` on `OracleBSetConfig`

Extend `evaluator_config.py` to parse the B extras as frozen dataclasses, keeping the existing clear-`ValueError` discipline for missing sections/keys. Tests write their OWN fixture TOML with obviously-fake placeholders — NEVER the real gitignored `evaluator.toml`.

**Files:**
- Modify: `src/agent_eval_lab/experiments/evaluator_config.py`
- Test: `tests/experiments/test_evaluator_config_b.py`

- [ ] **Step 1: Write the failing test**

Create `tests/experiments/test_evaluator_config_b.py`:

```python
"""Config plumbing for the B-set extras ([candidate] + [oracle.b_set.goldens]).

Every value here is an OBVIOUSLY-FAKE placeholder written by the test into a
tmp TOML. NEVER read the real gitignored evaluator.toml — no real creds/ids in
a tracked file (public repo).
"""

from pathlib import Path

import pytest

from agent_eval_lab.experiments.evaluator_config import (
    CandidateConfig,
    load_evaluator_config,
)

_FIXTURE_TOML = """\
[store]
path = "/tmp/fake-store"

[health_probe]
url = "https://fake.example/auth"
username = "fake-user"
password = "fake-pass"

[skill]
strategy_test_path = "/tmp/fake-skill/SKILL.md"

[runner]
safety_cap = 200
k_valid = 5
max_invalid_rate = 0.4

[candidate]
url = "https://fake.example/MicroStrategyLibrary/app"
username = "fake-candidate"
password = "fake-candidate-pass"

[oracle.b_set]
readback = "playwright-cli"
project_id = "FAKE_PROJECT_ID"

[oracle.b_set.goldens]
"B-1" = "fake-golden-object-0001"
"""


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "fixture-evaluator.toml"
    p.write_text(_FIXTURE_TOML, encoding="utf-8")
    return p


def test_loads_candidate_config(tmp_path: Path) -> None:
    cfg = load_evaluator_config(_write(tmp_path))
    assert isinstance(cfg.candidate, CandidateConfig)
    assert cfg.candidate.url.endswith("/MicroStrategyLibrary/app")
    assert cfg.candidate.username == "fake-candidate"
    assert cfg.candidate.password == "fake-candidate-pass"


def test_loads_oracle_b_set_project_and_goldens(tmp_path: Path) -> None:
    cfg = load_evaluator_config(_write(tmp_path))
    assert cfg.oracle_b_set.readback == "playwright-cli"
    assert cfg.oracle_b_set.project_id == "FAKE_PROJECT_ID"
    assert cfg.oracle_b_set.goldens == {"B-1": "fake-golden-object-0001"}


def test_missing_candidate_section_raises_clear_value_error(tmp_path: Path) -> None:
    toml = _FIXTURE_TOML.replace(
        '[candidate]\n'
        'url = "https://fake.example/MicroStrategyLibrary/app"\n'
        'username = "fake-candidate"\n'
        'password = "fake-candidate-pass"\n',
        "",
    )
    p = tmp_path / "no-candidate.toml"
    p.write_text(toml, encoding="utf-8")
    with pytest.raises(ValueError, match=r"\[candidate\]"):
        load_evaluator_config(p)


def test_missing_project_id_raises_clear_value_error(tmp_path: Path) -> None:
    toml = _FIXTURE_TOML.replace('project_id = "FAKE_PROJECT_ID"\n', "")
    p = tmp_path / "no-project.toml"
    p.write_text(toml, encoding="utf-8")
    with pytest.raises(ValueError, match="project_id"):
        load_evaluator_config(p)


def test_missing_goldens_subtable_raises_clear_value_error(tmp_path: Path) -> None:
    toml = _FIXTURE_TOML.replace(
        '[oracle.b_set.goldens]\n"B-1" = "fake-golden-object-0001"\n', ""
    )
    p = tmp_path / "no-goldens.toml"
    p.write_text(toml, encoding="utf-8")
    with pytest.raises(ValueError, match=r"\[oracle\.b_set\.goldens\]"):
        load_evaluator_config(p)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/experiments/test_evaluator_config_b.py -q
```

Expected: FAIL with `ImportError: cannot import name 'CandidateConfig'`.

- [ ] **Step 3: Add `CandidateConfig` and extend `OracleBSetConfig`**

Edit `src/agent_eval_lab/experiments/evaluator_config.py`. Add a new dataclass after `SkillConfig` (before `RunnerConfig`):

```python
@dataclass(frozen=True, kw_only=True)
class CandidateConfig:
    """The least-privilege candidate MSTR account (D20). Distinct from the
    evaluator account used by health_probe / the readback oracle; this account
    CANNOT read the golden (D19/D33).

    `url` is optional (the Library base URL; if absent, the live client uses
    the health_probe URL root). Required fields for the execute phase are
    username + password."""

    url: str | None = None  # optional: real evaluator.toml [candidate] has no url key
    username: str
    password: str
```

> **PLAN AMENDMENT (drift audit 010):** `url` was made OPTIONAL (`str | None = None`)
> because the real gitignored `evaluator.toml [candidate]` section has no `url` key;
> making it required crashes `load_evaluator_config` on the live file. The live
> execute-phase client falls back to the health_probe URL root when `url` is absent.
> This is a legitimate plan-correction — accepted in 010-drift.md.

Replace the existing `OracleBSetConfig` with the extended version (the `readback` field stays; add `project_id` and `goldens`):

```python
@dataclass(frozen=True, kw_only=True)
class OracleBSetConfig:
    readback: str  # readback strategy, e.g. "playwright-cli" (§18.4/§18.7)
    project_id: str  # MSTR project the run folder + golden live in (§18.7)
    goldens: Mapping[str, str]  # task-id -> golden object id (evaluator-only, D19)
```

Add `Mapping` to the imports at the top of the file (the `from collections.abc import Mapping` import):

```python
from collections.abc import Mapping
```

(Place it directly under `from dataclasses import dataclass`.)

- [ ] **Step 4: Add `candidate` to `EvaluatorConfig` and parse it**

In the same file, add `candidate` to the `EvaluatorConfig` dataclass (after `skill`):

```python
@dataclass(frozen=True, kw_only=True)
class EvaluatorConfig:
    store: StoreConfig
    health_probe: HealthProbeConfig
    skill: SkillConfig
    candidate: CandidateConfig
    runner: RunnerConfig
    oracle_b_set: OracleBSetConfig
```

In `load_evaluator_config`, after the `skill_sec = _require_section(data, "skill")` line, add:

```python
    candidate_sec = _require_section(data, "candidate")
```

Then, in the `oracle_sec` block, after `oracle_sec = oracle_parent["b_set"]`, add the goldens sub-table requirement:

```python
    if "goldens" not in oracle_sec:
        raise ValueError(
            "evaluator.toml is missing required section [oracle.b_set.goldens]"
        )
    goldens_sec = oracle_sec["goldens"]
```

Finally, in the returned `EvaluatorConfig(...)`, add the `candidate=` block (after the `skill=...` block) and extend the `oracle_b_set=` block:

```python
        candidate=CandidateConfig(
            url=str(_require_key(candidate_sec, "url", "candidate")),
            username=str(_require_key(candidate_sec, "username", "candidate")),
            password=str(_require_key(candidate_sec, "password", "candidate")),
        ),
```

```python
        oracle_b_set=OracleBSetConfig(
            readback=str(_require_key(oracle_sec, "readback", "oracle.b_set")),
            project_id=str(_require_key(oracle_sec, "project_id", "oracle.b_set")),
            goldens={str(k): str(v) for k, v in goldens_sec.items()},
        ),
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest tests/experiments/test_evaluator_config_b.py -q
```

Expected: PASS (5 passed).

- [ ] **Step 6: Confirm no existing config test regressed**

```bash
uv run pytest tests/experiments/ -q -k "config or evaluator"
```

Expected: all pass (the existing evaluator-config tests still construct `EvaluatorConfig`; if any of them build a fixture TOML that now lacks `[candidate]`/`project_id`/`goldens`, update that fixture to add the three obviously-fake placeholder blocks — do NOT relax the new required-key checks).

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/experiments/evaluator_config.py \
        tests/experiments/test_evaluator_config_b.py
git commit -m "feat(010): config plumbing — CandidateConfig + b_set project_id/goldens"
```

---

## Task 2: Injectable MSTR client Protocol + readback/isolation structs

All MSTR/`playwright-cli` I/O goes through a thin injectable `Protocol` so every test passes a fake and NO test does live I/O. This task defines the boundary types only (no live implementation — that lands in the deferred execute phase).

**Files:**
- Create: `src/agent_eval_lab/runners/mstr_client.py`
- Test: covered indirectly by Tasks 3/6 (the structs are exercised through the isolation helpers + runner). This task adds one import-shape smoke test.

- [ ] **Step 1: Write the failing smoke test**

Create `tests/runners/test_mstr_client.py`:

```python
"""The MSTR client boundary is a Protocol + plain frozen structs. No live I/O.
A fake client (a plain object with the four methods) must satisfy the Protocol
shape used by the isolation helpers and the runner."""

from agent_eval_lab.runners.mstr_client import (
    MstrReadbackClient,
    ReadbackResult,
    SaveTarget,
)


def test_readback_result_is_a_frozen_struct() -> None:
    r = ReadbackResult(
        exists=True,
        cube="X",
        rows=("A", "B"),
        columns=("C",),
        prompt="South",
        grid=(("h",), ("v",)),
    )
    assert r.exists is True
    assert r.rows == ("A", "B")


def test_save_target_carries_folder_and_name() -> None:
    t = SaveTarget(project_id="P", folder="/runs", name="m-c-0001")
    assert t.name == "m-c-0001"


def test_fake_client_satisfies_protocol() -> None:
    class _Fake:
        def name_exists(self, target: SaveTarget) -> bool:
            return False

        def created_object_id(self, target: SaveTarget) -> str:
            return "fake-id"

        def readback(self, *, project_id: str, object_id: str, prompt: str):
            return ReadbackResult(
                exists=True, cube="X", rows=(), columns=(), prompt=prompt, grid=()
            )

        def delete_object(self, *, project_id: str, object_id: str) -> None:
            return None

    client: MstrReadbackClient = _Fake()  # structural check
    assert client.name_exists(SaveTarget(project_id="P", folder="/r", name="n")) is False
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/runners/test_mstr_client.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.runners.mstr_client'`.

- [ ] **Step 3: Write `mstr_client.py`**

Create `src/agent_eval_lab/runners/mstr_client.py`:

```python
"""The thin injectable MSTR / playwright-cli readback boundary (D20/§18.7).

ALL live MSTR I/O is behind MstrReadbackClient — a Protocol with four methods.
Tests pass a deterministic fake; the live implementation (evaluator-credentialed
playwright-cli readback) is built in the DEFERRED execute phase (EXECUTE-DEFERRED).
The structs are plain frozen dataclasses (immutable, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, kw_only=True)
class SaveTarget:
    """Where a run saves its created object: the project, the run's isolated
    folder, and the unique save-name derived from run_uid (D20)."""

    project_id: str
    folder: str
    name: str


@dataclass(frozen=True, kw_only=True)
class ReadbackResult:
    """The evaluator-credentialed readback of a created object (§18.7).

    `exists` is the captured object's presence in the run folder; the remaining
    fields are the object's definition + executed grid under the prompt. `grid`
    is a tuple of row-tuples (header row first), order-preserving."""

    exists: bool
    cube: str
    rows: tuple[str, ...]
    columns: tuple[str, ...]
    prompt: str
    grid: tuple[tuple[str, ...], ...]


class MstrReadbackClient(Protocol):
    """Injectable boundary for all MSTR/playwright-cli I/O (D20/§18.7).

    Implementations: a deterministic fake in tests; the evaluator-credentialed
    playwright-cli readback in the deferred execute phase."""

    def name_exists(self, target: SaveTarget) -> bool:
        """True iff an object with `target.name` already exists in the folder
        (the preflight-absence check, D20)."""
        ...

    def created_object_id(self, target: SaveTarget) -> str:
        """The object id created at `target` (captured on save, D20). The grader
        keys on THIS id, never a name search."""
        ...

    def readback(
        self, *, project_id: str, object_id: str, prompt: str
    ) -> ReadbackResult:
        """Open the captured object by id, run it under `prompt`, read it back."""
        ...

    def delete_object(self, *, project_id: str, object_id: str) -> None:
        """Delete/reset the created object after grading (D20)."""
        ...
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/runners/test_mstr_client.py -q
```

Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/mstr_client.py tests/runners/test_mstr_client.py
git commit -m "feat(010): injectable MSTR readback client Protocol + readback/save structs"
```

---

## Task 3: Per-run isolation helpers (D20) — PURE over the injectable client

Four small helpers: derive the save-name from `run_uid`; preflight-assert the target name is absent; capture the created object id; reset after grading. All take the injectable `MstrReadbackClient`; NO live I/O in any test.

**Files:**
- Create: `src/agent_eval_lab/runners/b_isolation.py`
- Test: `tests/runners/test_b_isolation.py`

- [ ] **Step 1: Write the failing test**

Create `tests/runners/test_b_isolation.py`:

```python
"""Per-run isolation (D20) over a deterministic FAKE client. No live MSTR I/O.

The save-name is derived from run_uid (f"{condition_id}__{run_index:04d}"); a `:`
or `/` in a condition_id (e.g. "deepseek:deepseek-v4-pro") must be slugged so the
save-name is a legal MSTR object name."""

import pytest

from agent_eval_lab.runners.b_isolation import (
    capture_created_id,
    preflight_absent,
    reset_after_grading,
    save_name_from_run_uid,
)
from agent_eval_lab.runners.mstr_client import ReadbackResult, SaveTarget


class _FakeClient:
    def __init__(self, *, exists: bool, object_id: str) -> None:
        self._exists = exists
        self._object_id = object_id
        self.deleted: list[str] = []

    def name_exists(self, target: SaveTarget) -> bool:
        return self._exists

    def created_object_id(self, target: SaveTarget) -> str:
        return self._object_id

    def readback(self, *, project_id, object_id, prompt) -> ReadbackResult:
        return ReadbackResult(
            exists=True, cube="X", rows=(), columns=(), prompt=prompt, grid=()
        )

    def delete_object(self, *, project_id, object_id) -> None:
        self.deleted.append(object_id)


def test_save_name_is_derived_from_run_uid_and_slugged() -> None:
    name = save_name_from_run_uid("deepseek:deepseek-v4-pro__0003")
    # the condition_id colon must not survive as a raw object-name char
    assert ":" not in name
    assert name.endswith("__0003") or name.endswith("-0003")
    assert "deepseek" in name


def test_save_name_rejects_empty_run_uid() -> None:
    with pytest.raises(ValueError):
        save_name_from_run_uid("")


def test_preflight_absent_passes_when_name_is_free() -> None:
    client = _FakeClient(exists=False, object_id="obj-1")
    target = SaveTarget(project_id="P", folder="/runs", name="m-c-0001")
    # does not raise
    preflight_absent(client, target)


def test_preflight_absent_raises_when_name_is_occupied() -> None:
    client = _FakeClient(exists=True, object_id="obj-1")
    target = SaveTarget(project_id="P", folder="/runs", name="m-c-0001")
    with pytest.raises(ValueError, match="already exists"):
        preflight_absent(client, target)


def test_capture_created_id_returns_the_clients_object_id() -> None:
    client = _FakeClient(exists=False, object_id="obj-xyz")
    target = SaveTarget(project_id="P", folder="/runs", name="m-c-0001")
    assert capture_created_id(client, target) == "obj-xyz"


def test_reset_after_grading_deletes_the_captured_object() -> None:
    client = _FakeClient(exists=False, object_id="obj-xyz")
    reset_after_grading(client, project_id="P", object_id="obj-xyz")
    assert client.deleted == ["obj-xyz"]
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/runners/test_b_isolation.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.runners.b_isolation'`.

- [ ] **Step 3: Write `b_isolation.py`**

Create `src/agent_eval_lab/runners/b_isolation.py`:

```python
"""Per-run isolation (D20): a unique save-name from run_uid, a preflight-absence
assert, capture-the-created-object-id on save, and reset after grading.

Pure orchestration over the injectable MstrReadbackClient — the helpers contain
NO I/O of their own beyond delegating to the client, so they unit-test against a
fake with zero live infra. The grader keys on the CAPTURED object id (never a
name search), so a name collision after capture cannot mis-grade."""

from __future__ import annotations

import re

from agent_eval_lab.runners.mstr_client import MstrReadbackClient, SaveTarget

_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def save_name_from_run_uid(run_uid: str) -> str:
    """Derive the isolated save-name `<model>-<condition>-<run_id>` from run_uid
    (D20). run_uid is f"{condition_id}__{run_index:04d}"; condition_id may carry a
    colon (provider:model), so non-name-safe chars are slugged to '-'. The result
    is unique per (condition, run_index) — the isolation guarantee."""
    if not run_uid:
        raise ValueError("run_uid must be non-empty to derive a save-name (D20)")
    return _SLUG_RE.sub("-", run_uid).strip("-")


def preflight_absent(client: MstrReadbackClient, target: SaveTarget) -> None:
    """Assert the target save-name is empty BEFORE the run writes (D20). Raises
    ValueError if occupied so a stale object never contaminates a fresh run."""
    if client.name_exists(target):
        raise ValueError(
            f"preflight: object name {target.name!r} already exists in "
            f"{target.folder!r} — refusing to run over an occupied save target (D20)"
        )


def capture_created_id(client: MstrReadbackClient, target: SaveTarget) -> str:
    """Capture the object id created at `target` on save (D20). The grader keys
    on THIS id, never a name search."""
    return client.created_object_id(target)


def reset_after_grading(
    client: MstrReadbackClient, *, project_id: str, object_id: str
) -> None:
    """Delete/reset the captured object after grading (D20)."""
    client.delete_object(project_id=project_id, object_id=object_id)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/runners/test_b_isolation.py -q
```

Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/b_isolation.py tests/runners/test_b_isolation.py
git commit -m "feat(010): per-run isolation helpers (D20) — save-name/preflight/capture/reset"
```

---

## Task 4: Stripped strategy-test skill loader (§18.9, D27)

A tiny I/O reader: `load_stripped_skill(path) -> str` returns the `SKILL.md` text. The B-skill arm injects it as the leading system turn (Task 6 wires this via `apply_system_prompt`); B-noskill gets nothing. Test against a tmp fixture skill file, NOT the real gitignored fork.

**Files:**
- Create: `src/agent_eval_lab/datasets/skill_loader.py`
- Test: `tests/datasets/test_skill_loader.py`

- [ ] **Step 1: Write the failing test**

Create `tests/datasets/test_skill_loader.py`:

```python
"""The stripped-skill loader reads SKILL.md text (§18.9/D27). Test against a
tmp fixture file the test writes — NEVER the real gitignored evaluator-only fork."""

from pathlib import Path

import pytest

from agent_eval_lab.datasets.skill_loader import load_stripped_skill


def test_load_stripped_skill_returns_the_file_text(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text("# FAKE stripped strategy-test\nTopic map: ...\n", encoding="utf-8")
    text = load_stripped_skill(skill)
    assert "FAKE stripped strategy-test" in text


def test_load_stripped_skill_raises_clear_error_when_absent(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_stripped_skill(tmp_path / "missing" / "SKILL.md")
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/datasets/test_skill_loader.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.datasets.skill_loader'`.

- [ ] **Step 3: Write `skill_loader.py`**

Create `src/agent_eval_lab/datasets/skill_loader.py`:

```python
"""Load the stripped knowledge-only strategy-test fork (§18.9/D27).

The fork is ALREADY stripped + staged on disk by the owner (gitignored
evaluator-only/stripped-strategy-test/SKILL.md; the path is evaluator.toml
[skill] strategy_test_path). This loader only READS it — no stripping logic
lives in the eval lab. Injected as the B-skill arm's system prompt; the
B-noskill arm gets nothing (D25/D37). The estimand is the BUNDLED stripped-skill
effect, never 'domain knowledge alone'."""

from pathlib import Path


def load_stripped_skill(path: Path) -> str:
    """Return the stripped SKILL.md text. Raises FileNotFoundError if absent
    (the caller — build_b_tasks — surfaces a clear error before any run)."""
    return Path(path).read_text(encoding="utf-8")
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/datasets/test_skill_loader.py -q
```

Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/datasets/skill_loader.py tests/datasets/test_skill_loader.py
git commit -m "feat(010): stripped strategy-test skill loader (read-only, §18.9/D27)"
```

---

## Task 5: `playwright-cli` readback oracle (§18.7) — `ReadbackSpec` + PURE grader

Add a `ReadbackSpec` verification variant and a PURE grader `grade_b1_readback(spec, result)` over a `ReadbackResult` struct. Three golden-discriminating checks. The live readback is the injectable client (Task 2), stubbed in tests. Golden/mutant fixtures live ONLY in gitignored `evaluator-only/b-set-golden/`.

**Files:**
- Modify: `src/agent_eval_lab/tasks/schema.py` (add `ReadbackSpec` to the union)
- Create: `src/agent_eval_lab/datasets/b1_oracle.py`
- Create (gitignored, by impl): `evaluator-only/b-set-golden/b1-golden.json` + `evaluator-only/b-set-golden/b1-mutants.json`
- Test: `tests/datasets/test_b1_oracle.py`

### 5a — Stage the gitignored golden + mutant fixtures (evaluator-only)

- [ ] **Step 1: Create the B-1 golden fixture (gitignored)**

Create the directory and `evaluator-only/b-set-golden/b1-golden.json`. This file holds the EXPECTED readback for the golden-correct B-1 object: the cube name `Query_CharacteristicValue_Mandatory`, rows including `Years Hierarchy` + `Region`, columns including `Cost`, prompt `South`, and the executed grid under prompt = South.

> **IMPL NOTE — secret values, do NOT inline in this plan (public repo):** fill `cube`, `rows`, `columns`, `prompt`, and the `grid` from the OWNER-STATED B-1 task (§4.3: source cube `Query_CharacteristicValue_Mandatory`, Rows `Years Hierarchy` + `Region`, Cols `Cost`, prompt `South`) and the real executed golden grid the evaluator-credentialed readback produces. The grid VALUES are the held-out golden — they must live ONLY in this gitignored file. Shape:

```json
{
  "exists": true,
  "cube": "Query_CharacteristicValue_Mandatory",
  "rows": ["Years Hierarchy", "Region"],
  "columns": ["Cost"],
  "prompt": "South",
  "grid": [["<header cells>"], ["<golden data cells>"]]
}
```

(The `cube`/`rows`/`columns`/`prompt` above match the owner-stated task and are NOT secret; the `grid` cell VALUES ARE the golden — fill them from the real readback and never copy them into a tracked file.)

- [ ] **Step 2: Create the B-1 mutant fixtures (gitignored)**

Create `evaluator-only/b-set-golden/b1-mutants.json` — one negative fixture per failure mode (D24). Each is a readback that should FAIL. Shape:

```json
{
  "wrong_cube": {"exists": true, "cube": "<a DIFFERENT cube>", "rows": ["Years Hierarchy", "Region"], "columns": ["Cost"], "prompt": "South", "grid": "<golden grid>"},
  "missing_required_row": {"exists": true, "cube": "Query_CharacteristicValue_Mandatory", "rows": ["Years Hierarchy"], "columns": ["Cost"], "prompt": "South", "grid": "<golden grid>"},
  "missing_cost_col": {"exists": true, "cube": "Query_CharacteristicValue_Mandatory", "rows": ["Years Hierarchy", "Region"], "columns": ["<a non-Cost col>"], "prompt": "South", "grid": "<golden grid>"},
  "wrong_prompt": {"exists": true, "cube": "Query_CharacteristicValue_Mandatory", "rows": ["Years Hierarchy", "Region"], "columns": ["Cost"], "prompt": "North", "grid": "<grid under North, != golden>"}
}
```

> **IMPL NOTE:** reuse the golden `grid` for `wrong_cube`/`missing_required_row`/`missing_cost_col` (their failure is the definition mismatch, not the grid); for `wrong_prompt`, the grid under a different prompt differs from the golden grid (so check 3 fails too). All grid values are secret — keep them ONLY in this gitignored file.

- [ ] **Step 3: Confirm the fixtures are gitignored**

```bash
git check-ignore evaluator-only/b-set-golden/b1-golden.json \
                 evaluator-only/b-set-golden/b1-mutants.json
```

Expected: both paths print (confirming gitignored). If either prints nothing, STOP — do not proceed (public-repo leak risk).

### 5b — `ReadbackSpec` verification variant

- [ ] **Step 4: Add `ReadbackSpec` to `tasks/schema.py`**

Edit `src/agent_eval_lab/tasks/schema.py`. Add the dataclass after `FactKeySpec` (before the `VerificationSpec = (...)` union):

```python
@dataclass(frozen=True, kw_only=True)
class ReadbackSpec:
    """B-set readback oracle (§18.7 / D24). The grader compares a ReadbackResult
    (evaluator-credentialed playwright-cli readback of the captured object) to a
    held-out golden. Three golden-discriminating checks: (1) the captured object
    exists; (2) definition matches (cube == expected_cube, rows superset of
    required_rows, columns superset of required_columns, prompt == expected_prompt);
    (3) the executed grid equals the golden grid under prompt = expected_prompt.

    The golden grid lives in the evaluator-only store, NOT in this spec text —
    `golden_grid` is loaded from the gitignored fixture by the builder, never
    authored into a tracked source file (D19)."""

    type: Literal["readback"] = "readback"
    expected_cube: str
    required_rows: tuple[str, ...]
    required_columns: tuple[str, ...]
    expected_prompt: str
    golden_grid: tuple[tuple[str, ...], ...]
```

Add `ReadbackSpec` to the `VerificationSpec` union:

```python
VerificationSpec = (
    OutputMatchSpec
    | ToolCallMatchSpec
    | FinalStateSpec
    | TrajectorySpec
    | AllOf
    | LlmJudgeSpec
    | ExecutionSpec
    | NodeExecutionSpec
    | FactKeySpec
    | ReadbackSpec
)
```

### 5c — the oracle builder + PURE grader

- [ ] **Step 5: Write the failing oracle test**

Create `tests/datasets/test_b1_oracle.py`:

```python
"""B-1 readback oracle (§18.7/D24). golden-correct => PASS; each failure mode =>
FAIL (>=1 negative fixture per mode). Golden/mutant fixtures are gitignored
evaluator-only JSON — this test READS them by path and SKIPS when absent (CI has
no golden store), and NEVER inlines a golden value into this tracked file."""

import json
from pathlib import Path

import pytest

from agent_eval_lab.datasets.b1_oracle import build_b1_verification, grade_b1_readback
from agent_eval_lab.runners.mstr_client import ReadbackResult

_GOLDEN_DIR = (
    Path.home()
    / "Documents/Repository/agent-eval-lab/evaluator-only/b-set-golden"
)
_GOLDEN = _GOLDEN_DIR / "b1-golden.json"
_MUTANTS = _GOLDEN_DIR / "b1-mutants.json"

requires_store = pytest.mark.skipif(
    not _GOLDEN.exists() or not _MUTANTS.exists(),
    reason="local b-set golden store required (gitignored evaluator-only)",
)


def _result_from(d: dict) -> ReadbackResult:
    return ReadbackResult(
        exists=d["exists"],
        cube=d["cube"],
        rows=tuple(d["rows"]),
        columns=tuple(d["columns"]),
        prompt=d["prompt"],
        grid=tuple(tuple(row) for row in d["grid"]),
    )


@requires_store
def test_golden_correct_readback_passes() -> None:
    spec = build_b1_verification(_GOLDEN_DIR)
    golden = _result_from(json.loads(_GOLDEN.read_text("utf-8")))
    g = grade_b1_readback(spec, golden)
    assert g.passed is True


@requires_store
def test_missing_object_fails() -> None:
    spec = build_b1_verification(_GOLDEN_DIR)
    golden = json.loads(_GOLDEN.read_text("utf-8"))
    gone = _result_from({**golden, "exists": False})
    assert grade_b1_readback(spec, gone).passed is False


@requires_store
@pytest.mark.parametrize(
    "mode",
    ["wrong_cube", "missing_required_row", "missing_cost_col", "wrong_prompt"],
)
def test_each_failure_mode_fails(mode: str) -> None:
    spec = build_b1_verification(_GOLDEN_DIR)
    mutants = json.loads(_MUTANTS.read_text("utf-8"))
    bad = _result_from(mutants[mode])
    g = grade_b1_readback(spec, bad)
    assert g.passed is False, f"mutant {mode!r} should FAIL but PASSED"
```

- [ ] **Step 6: Run it to verify it fails**

```bash
uv run pytest tests/datasets/test_b1_oracle.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.datasets.b1_oracle'` (or, if the gitignored store is absent on this machine, all cases SKIP — that is acceptable; the module-not-found failure is what you want once the store exists).

- [ ] **Step 7: Write `b1_oracle.py`**

Create `src/agent_eval_lab/datasets/b1_oracle.py`:

```python
"""B-1 readback oracle (§18.7 / D24): build the ReadbackSpec from the evaluator
golden, and grade a ReadbackResult against it. The grader is PURE — it takes the
already-read-back struct (the live readback I/O is the injectable MstrReadbackClient,
performed by the runner) and returns a GradeResult. Three golden-discriminating
checks (see ReadbackSpec). The golden grid is loaded from the gitignored
evaluator-only store, never authored into this tracked source (D19)."""

from __future__ import annotations

import json
from pathlib import Path

from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.runners.mstr_client import ReadbackResult
from agent_eval_lab.tasks.schema import ReadbackSpec

_GOLDEN_REL = "b1-golden.json"


def build_b1_verification(golden_dir: Path) -> ReadbackSpec:
    """Read the evaluator-only golden and assemble the B-1 ReadbackSpec. The cube
    name + required rows/cols + prompt come from the golden; the golden grid is
    the held-out executed grid under prompt = South (D19 — read here, never in a
    candidate-visible location)."""
    golden = json.loads((golden_dir / _GOLDEN_REL).read_text(encoding="utf-8"))
    return ReadbackSpec(
        expected_cube=golden["cube"],
        required_rows=tuple(golden["rows"]),
        required_columns=tuple(golden["columns"]),
        expected_prompt=golden["prompt"],
        golden_grid=tuple(tuple(row) for row in golden["grid"]),
    )


def grade_b1_readback(spec: ReadbackSpec, result: ReadbackResult) -> GradeResult:
    """Grade a ReadbackResult against the B-1 ReadbackSpec (PURE, total).

    PASS iff ALL of:
      (1) the captured object exists in the run folder;
      (2) definition matches: cube == expected, rows superset of required_rows,
          columns superset of required_columns, prompt == expected_prompt;
      (3) executed grid == golden grid (under prompt = expected_prompt).
    Any failure => FAIL, with the failing check recorded in evidence."""
    checks: dict[str, bool] = {}
    checks["exists"] = result.exists
    checks["cube"] = result.cube == spec.expected_cube
    checks["rows_superset"] = set(spec.required_rows).issubset(set(result.rows))
    checks["columns_superset"] = set(spec.required_columns).issubset(
        set(result.columns)
    )
    checks["prompt"] = result.prompt == spec.expected_prompt
    checks["grid"] = result.grid == spec.golden_grid
    passed = all(checks.values())
    failing = tuple(name for name, ok in checks.items() if not ok)
    return GradeResult(
        grader_id="b1_readback",
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={"checks": checks, "failing": failing},
    )
```

- [ ] **Step 8: Run the test to verify it passes**

```bash
uv run pytest tests/datasets/test_b1_oracle.py -q
```

Expected: PASS (golden ⇒ PASS, missing ⇒ FAIL, 4 mutants ⇒ FAIL) when the gitignored store is present; otherwise all SKIP (acceptable in CI). If a mutant PASSES, the fixture in Step 2 did not actually differ on its mode — fix the fixture (NOT the grader) so each mutant violates exactly one check.

- [ ] **Step 9: Commit**

```bash
git add src/agent_eval_lab/tasks/schema.py \
        src/agent_eval_lab/datasets/b1_oracle.py \
        tests/datasets/test_b1_oracle.py
git commit -m "feat(010): B-1 readback oracle — ReadbackSpec + pure golden-discriminating grader"
```

(Note: `evaluator-only/b-set-golden/*.json` are gitignored and will NOT be staged — that is correct.)

---

## Task 6: `build_b_tasks(B-1)` — candidate-visible B-1 Task (noskill + skill arms)

`build_b_tasks` assembles the B-1 Task paired with its held-out `ReadbackSpec` oracle. It builds BOTH arm message tuples: the noskill arm carries only the task system+user turns; the skill arm prepends the stripped `SKILL.md` text as the system turn (via `apply_system_prompt`). The candidate prompt stays at the fair problem level (§4.3) — NO golden object id, NO exact solution (TRAP 2).

**Files:**
- Create: `src/agent_eval_lab/datasets/b_tasks.py`
- Test: `tests/datasets/test_b_tasks.py`

- [ ] **Step 1: Write the failing test**

Create `tests/datasets/test_b_tasks.py`:

```python
"""build_b_tasks shape (§4.3). The noskill and skill arms differ ONLY by the
injected stripped-skill system prompt (M2/D25/D37). Golden store + skill fork are
gitignored; the test writes a tmp fake skill file and a tmp fake golden dir so it
is fully deterministic and never reads the real evaluator-only artifacts."""

import json
from pathlib import Path

from agent_eval_lab.datasets.b_tasks import build_b_tasks
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import ReadbackSpec


def _fake_golden_dir(tmp_path: Path) -> Path:
    d = tmp_path / "b-set-golden"
    d.mkdir()
    (d / "b1-golden.json").write_text(
        json.dumps(
            {
                "exists": True,
                "cube": "Query_CharacteristicValue_Mandatory",
                "rows": ["Years Hierarchy", "Region"],
                "columns": ["Cost"],
                "prompt": "South",
                "grid": [["h"], ["v"]],
            }
        ),
        encoding="utf-8",
    )
    return d


def _fake_skill(tmp_path: Path) -> Path:
    p = tmp_path / "SKILL.md"
    p.write_text("# FAKE stripped strategy-test\nTopic map: ...\n", encoding="utf-8")
    return p


def test_build_b_tasks_returns_the_two_b1_arms(tmp_path: Path) -> None:
    tasks = build_b_tasks(
        golden_dir=_fake_golden_dir(tmp_path),
        strategy_test_path=_fake_skill(tmp_path),
    )
    ids = {t.id for t in tasks}
    assert ids == {"b-b1-noskill", "b-b1-skill"}
    for t in tasks:
        assert t.capability == "browser_mstr"
        assert isinstance(t.verification, ReadbackSpec)
        assert t.metadata.split == "held_out"


def test_skill_arm_carries_the_stripped_skill_noskill_does_not(tmp_path: Path) -> None:
    tasks = {
        t.id: t
        for t in build_b_tasks(
            golden_dir=_fake_golden_dir(tmp_path),
            strategy_test_path=_fake_skill(tmp_path),
        )
    }
    skill_sys = tasks["b-b1-skill"].input.messages[0]
    noskill_sys = tasks["b-b1-noskill"].input.messages[0]
    assert isinstance(skill_sys, MessageTurn) and skill_sys.role == "system"
    assert "FAKE stripped strategy-test" in skill_sys.content
    assert "FAKE stripped strategy-test" not in noskill_sys.content


def test_candidate_prompt_does_not_leak_a_golden_object_id(tmp_path: Path) -> None:
    """TRAP 2: the candidate prompt must stay at problem level — it must never
    contain a golden object id token. (Fake golden uses a placeholder id; this
    asserts the prompt is task-level, not solution-level.)"""
    tasks = build_b_tasks(
        golden_dir=_fake_golden_dir(tmp_path),
        strategy_test_path=_fake_skill(tmp_path),
    )
    for t in tasks:
        user = t.input.messages[-1].content
        # the user turn names the cube/rows/cols/prompt (fair task level) but
        # never an object id or a literal grid value
        assert "object id" not in user.lower()
        assert "golden" not in user.lower()
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/datasets/test_b_tasks.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.datasets.b_tasks'`.

- [ ] **Step 3: Write `b_tasks.py`**

Create `src/agent_eval_lab/datasets/b_tasks.py`:

```python
"""Assemble the B-1 Task pair (§4.3): the candidate-visible MSTR Library
automation task paired with its held-out ReadbackSpec oracle. Mirrors
datasets/f_tasks.build_f_tasks (the F builder).

Two arms for M2 (D25/D37): b-b1-noskill (the model's own knowledge only) and
b-b1-skill (additionally injected the stripped strategy-test SKILL.md as the
system prompt). The arms differ ONLY by that injection — both are instrumented
identically by the harness (§7). The candidate prompt describes the task at a
fair problem level (§4.3) and NEVER names the golden object id or the exact
solution (TRAP 2 / D19/D33). B-2..B-10 are NOT provided — B-1 is a 1-task
contingency (D26); the >=10-task cluster bootstrap is NOT claimed here."""

from pathlib import Path

from agent_eval_lab.datasets.b1_oracle import build_b1_verification
from agent_eval_lab.datasets.skill_loader import load_stripped_skill
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.prompt import apply_system_prompt
from agent_eval_lab.tasks.schema import Task, TaskInput, TaskMetadata

_SYSTEM = (
    "You are automating the MicroStrategy Library web UI with a single tool: "
    "`bash` (you issue playwright-cli commands through it). Complete the "
    "owner-specified report build exactly; do not take shortcuts via APIs."
)

# Fair problem-level instruction (§4.3). Names the source cube, the row/column
# layout, the mandatory prompt, and the Save-As name pattern — NOT a golden
# object id, NOT a literal grid value (TRAP 2 / §4.1 withhold-localization).
_B1_USER = (
    "In the MicroStrategy Library app (Tutorial Project), create a new report in "
    "Design Mode from the source cube SAPBW > AV_TUTO > "
    "Query_CharacteristicValue_Mandatory. Place 'Years Hierarchy' and 'Region' on "
    "Rows and 'Cost' on Columns. Answer the mandatory prompt with 'South', then "
    "Apply. Save the report to your run's isolated folder under the unique name "
    "'<model>-<condition>-<run_id>' provided to you. Report when the saved report "
    "renders the prompted result."
)


def _task(*, task_id: str, messages: tuple[MessageTurn, ...], verification) -> Task:
    return Task(
        id=task_id,
        capability="browser_mstr",
        input=TaskInput(messages=messages, available_tools=("bash",)),
        verification=verification,
        metadata=TaskMetadata(
            split="held_out",
            version="b-domain-v1",
            provenance="source spec §4.3 exemplar B-1 (Tutorial Project)",
        ),
        initial_state={"task_key": "B-1"},
    )


def build_b_tasks(*, golden_dir: Path, strategy_test_path: Path) -> tuple[Task, ...]:
    """Return the B-1 arm pair (noskill, skill). The same held-out ReadbackSpec
    grades both arms; the only difference is the injected stripped skill."""
    verification = build_b1_verification(golden_dir)
    base_messages = (
        MessageTurn(role="system", content=_SYSTEM),
        MessageTurn(role="user", content=_B1_USER),
    )
    skill_text = load_stripped_skill(strategy_test_path)
    skill_system = f"{_SYSTEM}\n\n{skill_text}"
    skill_messages = apply_system_prompt(base_messages, skill_system)
    return (
        _task(
            task_id="b-b1-noskill",
            messages=base_messages,
            verification=verification,
        ),
        _task(
            task_id="b-b1-skill",
            messages=skill_messages,
            verification=verification,
        ),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/datasets/test_b_tasks.py -q
```

Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/datasets/b_tasks.py tests/datasets/test_b_tasks.py
git commit -m "feat(010): build_b_tasks — B-1 noskill/skill arms + held-out readback oracle"
```

---

## Task 7: `run_b` runner — yield one ReplacementOutcome per B task (injectable client)

`run_b` mirrors `run_f`: per B task, drive the run via an injectable producer (at execute time, the model; here a stubbed readback), grade via `grade_b1_readback`, wrap in a `ReplacementOutcome`. The isolation lifecycle (preflight → capture → readback → reset) goes through the injectable `MstrReadbackClient`. NO live I/O in any test.

**Files:**
- Create: `src/agent_eval_lab/runners/b_run.py`
- Test: `tests/runners/test_b_run.py`

- [ ] **Step 1: Write the failing test**

Create `tests/runners/test_b_run.py`:

```python
"""run_b yields one ReplacementOutcome per B task over a FAKE MstrReadbackClient
(no live MSTR I/O). The fake returns a configurable readback; the grader's verdict
flows into the outcome. The isolation lifecycle (preflight/capture/reset) is
exercised against the fake — preflight on an occupied name VOIDs/raises per D20."""

from agent_eval_lab.datasets.b1_oracle import build_b1_verification
from agent_eval_lab.runners.b_run import run_b
from agent_eval_lab.runners.mstr_client import ReadbackResult, SaveTarget
from agent_eval_lab.runners.multi_run import ReplacementOutcome
from agent_eval_lab.tasks.schema import ReadbackSpec, Task, TaskInput, TaskMetadata


def _golden_result() -> ReadbackResult:
    return ReadbackResult(
        exists=True,
        cube="Query_CharacteristicValue_Mandatory",
        rows=("Years Hierarchy", "Region"),
        columns=("Cost",),
        prompt="South",
        grid=(("h",), ("v",)),
    )


def _spec() -> ReadbackSpec:
    return ReadbackSpec(
        expected_cube="Query_CharacteristicValue_Mandatory",
        required_rows=("Years Hierarchy", "Region"),
        required_columns=("Cost",),
        expected_prompt="South",
        golden_grid=(("h",), ("v",)),
    )


class _FakeClient:
    def __init__(self, *, exists_before: bool, result: ReadbackResult) -> None:
        self._exists_before = exists_before
        self._result = result
        self.deleted: list[str] = []

    def name_exists(self, target: SaveTarget) -> bool:
        return self._exists_before

    def created_object_id(self, target: SaveTarget) -> str:
        return "obj-created-1"

    def readback(self, *, project_id, object_id, prompt) -> ReadbackResult:
        return self._result

    def delete_object(self, *, project_id, object_id) -> None:
        self.deleted.append(object_id)


def _b_task() -> Task:
    return Task(
        id="b-b1-skill",
        capability="browser_mstr",
        input=TaskInput(messages=(), available_tools=("bash",)),
        verification=_spec(),
        metadata=TaskMetadata(split="held_out", version="b-domain-v1", provenance="x"),
        initial_state={"task_key": "B-1"},
    )


def test_run_b_golden_readback_passes_and_resets() -> None:
    client = _FakeClient(exists_before=False, result=_golden_result())
    outcomes = list(
        run_b(
            tasks=(_b_task(),),
            client=client,
            project_id="FAKE_PROJECT",
            folder="/runs",
            condition_id="local:m",
            k=1,
        )
    )
    assert len(outcomes) == 1
    assert isinstance(outcomes[0], ReplacementOutcome)
    assert outcomes[0].valid_runs[0].grade.passed is True
    # the captured object was reset after grading (D20)
    assert client.deleted == ["obj-created-1"]


def test_run_b_wrong_cube_readback_fails() -> None:
    bad = ReadbackResult(
        exists=True,
        cube="SOME_OTHER_CUBE",
        rows=("Years Hierarchy", "Region"),
        columns=("Cost",),
        prompt="South",
        grid=(("h",), ("v",)),
    )
    client = _FakeClient(exists_before=False, result=bad)
    outcomes = list(
        run_b(
            tasks=(_b_task(),),
            client=client,
            project_id="FAKE_PROJECT",
            folder="/runs",
            condition_id="local:m",
            k=1,
        )
    )
    assert outcomes[0].valid_runs[0].grade.passed is False


def test_run_b_preflight_occupied_name_voids_outcome() -> None:
    client = _FakeClient(exists_before=True, result=_golden_result())
    outcomes = list(
        run_b(
            tasks=(_b_task(),),
            client=client,
            project_id="FAKE_PROJECT",
            folder="/runs",
            condition_id="local:m",
            k=1,
        )
    )
    # an occupied save target is an env/isolation invalidity -> VOID, never scored
    assert outcomes[0].void is True
    assert outcomes[0].valid_runs == ()
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/runners/test_b_run.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.runners.b_run'`.

- [ ] **Step 3: Write `b_run.py`**

Create `src/agent_eval_lab/runners/b_run.py`:

```python
"""EDGE: run the B-domain MSTR readback tasks and grade them via the readback
oracle. Mirrors runners/f_run.run_f.

Per B task, the per-run isolation lifecycle (D20) runs over the injectable
MstrReadbackClient: derive the save-name from run_uid, preflight-assert the name
is absent (occupied => VOID, never scored), capture the created object id on save,
read it back under the expected prompt, grade with grade_b1_readback, then reset.
The live readback is the injected client; tests pass a deterministic fake (no live
MSTR I/O). The grader keys on the CAPTURED object id, never a name search.

This is the WIRING + deterministic grade path. The LIVE model-driven build (the
candidate actually clicking through the Library UI) is the DEFERRED execute phase
(EXECUTE-DEFERRED); there, the client is the evaluator-credentialed playwright-cli
readback and the run_uid comes from the live Trajectory."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from agent_eval_lab.datasets.b1_oracle import grade_b1_readback
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.b_isolation import (
    capture_created_id,
    preflight_absent,
    reset_after_grading,
    save_name_from_run_uid,
)
from agent_eval_lab.runners.mstr_client import MstrReadbackClient, SaveTarget
from agent_eval_lab.tasks.schema import ReadbackSpec, Task


def _empty_trajectory(run_index: int, run_uid: str) -> Trajectory:
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=run_index,
        stop_reason="completed",
        run_uid=run_uid,
    )


def _void_outcome():
    from agent_eval_lab.runners.multi_run import ReplacementOutcome

    return ReplacementOutcome(valid_runs=(), attempts=(), void=True)


def run_b(
    *,
    tasks: Sequence[Task],
    client: MstrReadbackClient,
    project_id: str,
    folder: str,
    condition_id: str,
    k: int,
) -> Iterator["object"]:
    """Yield one ReplacementOutcome per B task (D20 isolation + readback grade).

    A preflight-occupied save target is an isolation invalidity -> VOID outcome
    (never scored over a contaminated run). Otherwise: capture the created object
    id, read it back, grade, reset, and wrap k identical valid runs (the readback
    of a fixed object is deterministic, so pass^k is well-defined here)."""
    from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

    for task in tasks:
        assert isinstance(task.verification, ReadbackSpec)
        run_uid = f"{condition_id}__0000"
        name = save_name_from_run_uid(run_uid)
        target = SaveTarget(project_id=project_id, folder=folder, name=name)
        try:
            preflight_absent(client, target)
        except ValueError:
            yield _void_outcome()
            continue
        object_id = capture_created_id(client, target)
        result = client.readback(
            project_id=project_id, object_id=object_id, prompt=task.verification.expected_prompt
        )
        grade = grade_b1_readback(task.verification, result)
        reset_after_grading(client, project_id=project_id, object_id=object_id)

        runs = tuple(
            RunResult(
                task_id=task.id,
                condition_id=condition_id,
                run_index=i,
                trajectory=_empty_trajectory(i, f"{condition_id}__{i:04d}"),
                grade=grade,
            )
            for i in range(k)
        )
        attempts = tuple(
            TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
        )
        yield ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)
```

> **IMPL NOTE — return annotation:** the function yields `ReplacementOutcome`, but importing it at module top would create no cycle (it's already a sibling). For clarity, move the `from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt` to the module top and annotate the return as `Iterator[ReplacementOutcome]` (mirroring `f_run.run_f`); the lazy imports above are only to keep the diff reviewable — prefer the top-level import to match the F-runner idiom. Update `_void_outcome` accordingly.

- [ ] **Step 4: Refactor imports to match the F-runner idiom**

Edit `src/agent_eval_lab/runners/b_run.py`: move `ReplacementOutcome` / `TrialAttempt` to the top-level imports, annotate `run_b` as `Iterator[ReplacementOutcome]`, and simplify `_void_outcome` to a plain `ReplacementOutcome(valid_runs=(), attempts=(), void=True)`. Final top imports:

```python
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest tests/runners/test_b_run.py -q
```

Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/runners/b_run.py tests/runners/test_b_run.py
git commit -m "feat(010): run_b — D20 isolation lifecycle + readback grade over injectable client"
```

---

## Task 8: Wire the B branch into `run_m1` (mirror F: absent ⇒ skipped)

Add a B branch to `run_m1` mirroring the F branch — a domain with no B tasks (or no client) is simply skipped, never a crash. The live B client/run is the deferred execute phase; this branch is the wiring + a deterministic grade path with a stubbed client.

**Files:**
- Modify: `src/agent_eval_lab/experiments/m1_run.py`
- Test: `tests/experiments/test_m1_run.py` (add a B-branch case)

- [ ] **Step 1: Add the failing B-branch test**

Read `tests/experiments/test_m1_run.py` first (the F-branch test `test_run_m1_f_branch_yields_outcomes` shows the stub idiom). Append this test:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/experiments/test_m1_run.py::test_run_m1_b_branch_yields_outcomes -q
```

Expected: FAIL — `run_m1` has no `run_b` attribute / no `b_client` parameter (`TypeError: run_m1() got an unexpected keyword argument 'b_client'`).

- [ ] **Step 3: Add the B branch to `run_m1`**

Edit `src/agent_eval_lab/experiments/m1_run.py`. Add the import near the existing `from agent_eval_lab.runners.f_run import ...` line:

```python
from agent_eval_lab.runners.b_run import run_b
from agent_eval_lab.runners.mstr_client import MstrReadbackClient
```

Add three optional B parameters to `run_m1`'s signature (after `f_repo: Path | None = None`):

```python
    f_repo: Path | None = None,
    b_client: MstrReadbackClient | None = None,
    b_project_id: str | None = None,
    b_folder: str | None = None,
```

Replace the trailing comment line `# B: no domain runner yet (item 010). Absent -> skipped, never a crash.` with the B branch:

```python
        b_tasks = domain_tasks.get("B")
        if b_tasks and b_client is not None and b_project_id is not None:
            out[cond]["B"] = tuple(
                run_b(
                    tasks=tuple(b_tasks),
                    client=b_client,
                    project_id=b_project_id,
                    folder=b_folder or "/runs",
                    condition_id=cond,
                    k=k_valid,
                )
            )
        # Absent B tasks/client -> skipped, never a crash (mirrors the F branch).
```

- [ ] **Step 4: Run the B-branch test to verify it passes**

```bash
uv run pytest tests/experiments/test_m1_run.py -q
```

Expected: PASS (existing D/F tests + the new B test; the absent-domains test still passes because B is skipped when `b_client` is None).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/experiments/m1_run.py tests/experiments/test_m1_run.py
git commit -m "feat(010): run_m1 B branch — readback grade over injectable client (absent => skipped)"
```

---

## Task 9: Wire B into `cli._load_m1_domain_tasks`

Add `"B"` to the domain-task map. The B tasks need the gitignored golden dir + skill path from the loaded config; when those are absent (CI / no evaluator-only store) the B builder must be skipped so the CLI still works D/F-only.

**Files:**
- Modify: `src/agent_eval_lab/cli.py` (`_load_m1_domain_tasks` ~808; pass `b_client`/`b_project_id`/`b_folder` in `_run_m1_command`)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add the failing test**

Read `tests/test_cli.py` for the existing `_load_m1_domain_tasks` test idiom. Add:

```python
def test_load_m1_domain_tasks_includes_b_when_store_present(tmp_path, monkeypatch):
    from pathlib import Path

    from agent_eval_lab import cli

    golden = (
        Path.home()
        / "Documents/Repository/agent-eval-lab/evaluator-only/b-set-golden"
    )
    if not (golden / "b1-golden.json").exists():
        import pytest

        pytest.skip("local b-set golden store required (gitignored)")

    # build a cfg stub exposing the store path, candidate, skill, oracle_b_set
    # exactly as load_evaluator_config would (read the real one only for the paths
    # it needs; the test SKIPS if absent so CI never reaches here).
    cfg = cli.load_evaluator_config(Path("evaluator.toml"))
    domain_tasks = cli._load_m1_domain_tasks(args=None, cfg=cfg)
    assert "B" in domain_tasks
    assert {t.id for t in domain_tasks["B"]} == {"b-b1-noskill", "b-b1-skill"}
```

> **IMPL NOTE:** this test is store-gated (SKIPS in CI). The existing F test in `tests/test_cli.py` is similarly gated — match its skip idiom.

- [ ] **Step 2: Run it to verify it fails (or skips locally)**

```bash
uv run pytest tests/test_cli.py::test_load_m1_domain_tasks_includes_b_when_store_present -q
```

Expected: FAIL with `assert 'B' in {'D': ..., 'F': ...}` when the store is present; SKIP when absent.

- [ ] **Step 3: Modify `_load_m1_domain_tasks`**

Edit `src/agent_eval_lab/cli.py`. In `_load_m1_domain_tasks`, add the B builder import and a guarded B entry. Replace the function body's return-construction with:

```python
    from agent_eval_lab.datasets.b_tasks import build_b_tasks
    from agent_eval_lab.datasets.cmc_dset import build_cmc_tasks
    from agent_eval_lab.datasets.f_tasks import build_f_tasks

    store = Path(cfg.store.path)
    tasks = build_cmc_tasks(
        evaluator_store=store,
        questions_path=Path("examples/datasets/cmc-docs-questions.txt"),
    )
    f_tasks = build_f_tasks(evaluator_store=store / "web-dossier-golden")
    domain_tasks: dict = {"D": tasks, "F": f_tasks}

    # B is gated on the gitignored golden store + the stripped skill fork. When
    # either is absent (CI / no evaluator-only), B is simply omitted (mirrors the
    # absent-domain skip in run_m1). B-1 is a 1-task contingency (D26).
    golden_dir = Path("evaluator-only/b-set-golden")
    skill_path = Path(cfg.skill.strategy_test_path)
    if (golden_dir / "b1-golden.json").exists() and skill_path.exists():
        domain_tasks["B"] = build_b_tasks(
            golden_dir=golden_dir, strategy_test_path=skill_path
        )
    return domain_tasks
```

Update the docstring to:

```python
    """Build the per-domain task map.
    D = CMC docs tasks; F = web-dossier repo-fix tasks (009); B = MSTR readback
    B-1 (010), present only when the gitignored b-set golden store + stripped
    skill fork are on disk (B-1 is a 1-task contingency — D26).
    cfg is the loaded EvaluatorConfig (passed so callers can stub this function
    in tests without touching load_evaluator_config)."""
```

- [ ] **Step 4: Pass the B client/project/folder in `_run_m1_command`**

Edit `src/agent_eval_lab/cli.py` `_run_m1_command`. The live B client is the DEFERRED execute phase, so for now pass `b_client=None` (B is skipped) but thread `b_project_id`/`b_folder` from config so the wiring is complete. In the `run_m1(...)` call, after `f_repo=...`, add:

```python
            f_repo=Path.home() / "Documents/Repository/web-dossier",
            b_client=None,  # DEFERRED: live playwright-cli readback client (EXECUTE-DEFERRED)
            b_project_id=cfg.oracle_b_set.project_id,
            b_folder="/runs",
```

> **IMPL NOTE:** `b_client=None` means `run_m1` skips B even when B tasks are present — that is correct for the code-only item (all live B runs are deferred). The deferred execute phase swaps in the real client (see Execute-phase follow-ups).

- [ ] **Step 5: Run the test to verify it passes (or skips)**

```bash
uv run pytest tests/test_cli.py::test_load_m1_domain_tasks_includes_b_when_store_present -q
```

Expected: PASS when the store is present; SKIP in CI.

- [ ] **Step 6: Run the full CLI test file**

```bash
uv run pytest tests/test_cli.py -q
```

Expected: all pass (existing D/F CLI tests unaffected; the new B test skips without the store).

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/test_cli.py
git commit -m "feat(010): wire B into _load_m1_domain_tasks + run-m1 (b_client deferred to execute)"
```

---

## Task 10: Full-suite green + ruff clean + integrity grep (refactor + ship-prep checkpoint)

**Files:** none new — verification only.

- [ ] **Step 1: Ruff over the WHOLE repo (CI parity — the #20 hotfix gap)**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: `All checks passed!` and `N files already formatted`. If format fails, run `uv run ruff format .` and re-stage. CRITICAL: run over `.` (the whole repo), NOT `src tests` — the #20 CI hotfix was caused by a `src tests`-only check missing a file elsewhere.

- [ ] **Step 2: Full test suite (CI parity)**

```bash
uv run pytest -q -p no:cacheprovider
```

Expected: all pass / skip. The B oracle, B-isolation, B-run, and config tests run fully (stubbed/fixture-based). The B-1 oracle store-gated cases SKIP without the gitignored golden store — that is correct CI behavior.

- [ ] **Step 3: Confirm the pre-existing oracle-subprocess timeout flakes reproduce on BASE (not introduced by 010)**

The `tests/runners/test_pytest_edge.py` oracle-subprocess timeout flakes are KNOWN and pre-existing. If you see one, confirm it reproduces WITHOUT the 010 diff before chasing it:

```bash
git stash
uv run pytest tests/runners/test_pytest_edge.py -q -p no:cacheprovider
git stash pop
```

Expected: the same flake (if any) is present on base. Do NOT chase a pre-existing timeout flake — note it and move on.

- [ ] **Step 4: COMPLETE-token integrity grep over the TRACKED tree (TRAP 1 — note the 009 incomplete-grep lesson)**

The 009 grep missed `analyzeFailure`/`diagResult`. Use a COMPLETE token set covering every B-set secret category. Run over the tracked tree only:

```bash
git grep -nIE \
  "b1-golden|b1-mutants|b-set-golden|FAKE_PROJECT_ID|fake-golden-object|fake-candidate" \
  -- src tests docs/2026-06-13-agentic-v1-domains-runs || echo "NO MATCHES (clean)"
```

Expected: the only matches are the obviously-FAKE placeholder tokens INSIDE the test files (`FAKE_PROJECT_ID`, `fake-golden-object-0001`, `fake-candidate` — these are intentionally fake) and the `b1-golden`/`b1-mutants`/`b-set-golden` PATH references in skipif markers + this plan. There must be ZERO real golden object ids, real project ids, real candidate creds, real MSTR host, or real golden grid values.

- [ ] **Step 5: Confirm NO real secret leaked — scan for the real-store contents explicitly**

```bash
# the real golden VALUES live only in the gitignored store; assert the tracked
# tree never contains them by confirming the store files are ignored and that no
# tracked file reads them inline.
git check-ignore evaluator-only/b-set-golden/b1-golden.json evaluator.toml .env
git grep -nI "Query_CharacteristicValue_Mandatory" -- src tests || echo "no tracked cube literal in src/tests"
```

Expected: `git check-ignore` prints all three paths (gitignored). The cube name `Query_CharacteristicValue_Mandatory` IS allowed to appear in `src/agent_eval_lab/datasets/b_tasks.py` (it is the owner-stated, non-secret task description per §4.3 / the artifacts doc — NOT a golden grid value) and in the test fixtures; it is NOT a secret. The golden GRID values must never appear in a tracked file — confirm by inspection that no tracked file contains literal grid cell values.

- [ ] **Step 6: Confirm no F3 / D / report-engine regression**

```bash
uv run pytest tests/datasets/test_f3_oracle.py tests/runners/test_node_oracle_edge.py \
              tests/reports/ tests/runners/test_dset_run.py -q -p no:cacheprovider
```

Expected: all pass (010 must not regress 004/005/008/009). The report engine already renders B generically (`_DOMAINS=("F","D","B")`) — confirm `tests/reports/` is green WITHOUT any report-engine change.

- [ ] **Step 7: Final commit (if ruff reformatted anything)**

```bash
git add -A
git commit -m "chore(010): ruff format + full-suite green for B-domain" || echo "nothing to commit"
```

---

## Self-Review (completed during authoring)

- **Spec coverage:**
  - Config plumbing (spec §"Config plumbing" + 010-spec items) → Task 1 (`CandidateConfig`, `project_id`, `goldens`, clear-`ValueError`, fixture-TOML test).
  - Per-run isolation D20 (spec item 1 / §4.3 "Isolation & capture") → Tasks 2 (client Protocol) + 3 (save-name/preflight/capture/reset over fake) + 7 (the lifecycle in `run_b`).
  - Stripped strategy-test loader §18.9/D27 (spec item 2) → Task 4 (loader) + Task 6 (B-skill injection; B-noskill gets nothing).
  - playwright-cli readback oracle §18.7 (spec item 3) → Task 5 (`ReadbackSpec` + 3 golden-discriminating checks + ≥1 negative fixture per mode in gitignored `evaluator-only/b-set-golden/`).
  - Wire B into run-m1 (spec item 4) → Task 6 (`build_b_tasks`) + Task 8 (`run_m1` B branch, absent⇒skipped) + Task 9 (`cli._load_m1_domain_tasks` `"B"`).
  - M2 D25/D37 (spec item 5) → Task 6 (noskill vs skill arms differ ONLY by the stripped-skill injection; both instrumented identically by the harness via the same Task/runner path).
- **Constraints:**
  - Deterministic tests: every MSTR/playwright-cli touch goes through the injected fake (Tasks 2/3/7/8); the B-1 oracle golden/mutant tests are `requires_store`-skipif-guarded so CI SKIPS (Task 5); no test needs live MSTR (the live readback is deferred — Execute-phase follow-ups).
  - Integrity (public repo): golden/mutant fixtures ONLY in gitignored `evaluator-only/b-set-golden/` (Task 5 5a + gitignore check); tests build obviously-fake placeholders; the candidate prompt stays problem-level (Task 6 + the `test_candidate_prompt_does_not_leak_a_golden_object_id` test); COMPLETE-token `git grep` over the tracked tree (Task 10 Steps 4-5).
  - B-1 1-task contingency: `build_b_tasks` builds ONLY B-1's two arms; the docstrings + this plan mark B-2..B-10 BLOCKED and never claim a cluster bootstrap (D26).
  - CI parity: ruff `check .` + `format --check .` over the WHOLE repo + `pytest -q -p no:cacheprovider` (Task 10 Steps 1-2); pre-existing `test_pytest_edge.py` flakes confirmed on base, not chased (Step 3).
  - Functional-programming discipline: every helper is a small pure function over immutable frozen dataclasses; I/O (file read, MSTR client) is at the edges (the loader, the client Protocol); no argument mutation; the grader is pure/total.
- **Type consistency:** `ReadbackResult`/`SaveTarget`/`MstrReadbackClient` (Task 2) are used unchanged in Tasks 3/5/7/8; `ReadbackSpec` (Task 5) is the verification carried by `build_b_tasks` (Task 6) and graded by `grade_b1_readback` (Task 5) inside `run_b` (Task 7); `ReplacementOutcome`/`TrialAttempt`/`RunResult`/`GradeResult` field names match `records/grade.py` + `runners/multi_run.py` (verified during authoring); `apply_system_prompt(messages, prompt)` signature matches `runners/prompt.py`.

## Judgment calls made (cite the spec section)

1. **A new `ReadbackSpec` verification variant, not a reuse of an existing spec** (spec §18.7 + item 3 "the oracle is a pure grader over a readback result struct"). None of the existing `VerificationSpec` variants (`OutputMatch`/`ToolCallMatch`/`FinalState`/`Trajectory`/`Execution`/`NodeExecution`/`FactKey`) models a 3-part definition-plus-grid readback. Adding `ReadbackSpec` to the union (Task 5) mirrors how `FactKeySpec` was added for the D-set and `NodeExecutionSpec` for F3 — the minimal, idiomatic extension. The grader stays pure/total/versioned (`grader_id="b1_readback"`), consistent with the ADR-0013 discipline cited in §6.

2. **A standalone injectable `MstrReadbackClient` Protocol module rather than threading the readback through the existing `bash_edge`/`browse` tooling** (spec item 2/3 "all MSTR/playwright-cli I/O goes through a thin injectable client Protocol so tests pass a fake"; §18.7 "the live readback I/O is a thin, injectable client (stubbed in tests)"). The D-set drives the model through `bash`/`apply_browse`, but the B-set ORACLE is an evaluator-credentialed readback distinct from the candidate's tool use — a separate boundary keeps the candidate path and the grading path isolated (D19/D20). The live implementation of the Protocol is explicitly deferred (§"Out of scope: all live MSTR runs").

3. **`run_b` grades a stubbed-client readback with `k` identical valid runs; the live model-driven build is deferred** (spec §"Out of scope: all live MSTR runs … DEFERRED"; §6 "objective grade but env-dependent → pass^k valid only over the validity mask"). Mirroring `run_f`, `run_b` takes the injectable client so this item wires + tests the isolation+grade path without live infra; the readback of a fixed captured object is deterministic, so `k` identical valid runs give a well-defined `pass^k`. The live env-validity mask (health probes, replacement-trial VOID on unhealthy env, D34) is exercised in the deferred execute phase via the same `ReplacementOutcome` shape; in this code-only item, a preflight-occupied save target is surfaced as a VOID outcome (the one isolation invalidity reachable without live infra).

4. **The skill-arm injection happens at the DATASET layer (`build_b_tasks` builds the skill-prefixed `TaskInput.messages`), not in the runner loop** (spec item 2 "inject the stripped SKILL.md as a system prompt for the B-skill arm only"; D25 "both arms instrumented identically by the harness"). `run_single` reads `task.input.messages` directly, and `apply_system_prompt` is the existing pure helper for exactly this. Building the injection into the two B-1 arm Tasks means both arms flow through the IDENTICAL runner/instrumentation path — the only difference is the message content — which is precisely the M2 control (D37: the estimand is the bundled stripped-skill effect).

5. **B is gated on the gitignored store in `_load_m1_domain_tasks` (omitted when absent), mirroring run_m1's absent-domain skip** (spec §"Out of scope" + the artifacts doc "if the remaining goldens/tasks don't arrive: ship 010's code … mark the rest BLOCKED"). Without the gitignored `evaluator-only/b-set-golden/` + stripped fork, the B builder cannot run; omitting B (rather than crashing) keeps the D/F CLI path working in CI and on machines without the evaluator-only store — the same partial-coverage discipline the report engine already encodes (`domains_not_run`).

---

## Execute-phase follow-ups (DEFERRED live run — for the owner)

The deferred live B run (`EXECUTE-DEFERRED.md`) needs the following, all intentionally left out of this code-only item:

1. **Implement the live `MstrReadbackClient`** — an evaluator-credentialed `playwright-cli` readback (§18.7): `name_exists`/`created_object_id`/`readback`/`delete_object` against the live Intelligence Server using the EVALUATOR account (`[health_probe]` creds), against `[oracle.b_set] project_id` and the run's isolated folder. This is the only piece with live MSTR I/O; it is built and exercised ONLY in the execute phase (no test in this item needs it).

2. **Swap `b_client=None` → the live client in `_run_m1_command`** (Task 9 Step 4) and pass the live `b_folder` (the run's isolated folder under the Tutorial Project). With `b_client` set, `run_m1`'s B branch runs the real readback grade.

3. **Drive the candidate arms live** — run b-b1-noskill and b-b1-skill with the CANDIDATE account (`[candidate]` creds) clicking through the Library UI; capture rounds/tokens/cost/wall-time on the `Trajectory` (the harness already records these). The `run_uid` for the live save-name comes from the live `Trajectory.run_uid` (this item's `run_b` synthesizes it from `condition_id` for the deterministic path; the live runner uses the real per-run uid).

4. **Report M2 over B-1 HONESTLY** — a 1-task contingency. NEVER label a 1-task percentile interval a "cluster-bootstrap CI" (D26/§8). Mark B-2..B-10 + their goldens BLOCKED in PROGRESS/SKIPPED. The ≥10-task cluster bootstrap is NOT claimed until those land.

5. **Env-validity mask for the live B run** — wire the §18.5 health probe + the D34 replacement-trial loop (VOID on env-unhealthy) into the live B runner, mirroring `run_dset`. This item's `run_b` uses `k` identical valid runs (deterministic readback of a fixed object); the LIVE run must use the env-masked replacement loop because the live Intelligence Server is not run-to-run reproducible (§6).

**Plan complete and saved to `docs/2026-06-13-agentic-v1-domains-runs/items/010-plan.md`.** A Sonnet impl agent will execute it verbatim via subagent-driven-development.
