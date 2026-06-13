# Item 001 — Records + Runner Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the versioned, backward-compatible records to store rounds / cost-input tokens / wall-time / per-tool counts / cap-binding / env-health / run_uid; revise the runner to a censoring contract (natural completion under a 200-tool-call safety cap) with an injected health probe; add a replacement-trial loop that runs until exactly k valid trials; and add the fc-v3 `environment_failure` classifier category — all test-first.

**Architecture:** One `Trajectory` type, version-tagged (`schema_version: Literal["1","2"]`), never a separate V2 type. `trajectory_from_dict` becomes the single routing seam: artifacts lacking `schema_version` are hydrated through `Trajectory.v1_compat` with safe defaults so every committed v1 line keeps loading byte-faithfully. The runner stays env-agnostic — the health probe is an injected `Callable[[], EnvHealth] | None`, never a hard-wired HTTP call. Cost stays DERIVED in `metrics/cost.py` (tokens × pricing); the runner and records never touch pricing. The classifier stays pure / total / versioned (ADR-0013); fc-v3 inserts one new first-class category after the parse/harness checks and before execution grading, leaving every existing fc-v2 verdict identical except the version label.

**Tech Stack:** Python ≥3.11, frozen `@dataclass(kw_only=True)`, `typing.Literal`, `pytest`, `hypothesis`, `ruff`. Tests run with `uv run pytest`; lint with `uv run ruff check`.

---

## Pre-flight context (read before Task 1)

**Baseline:** `uv run pytest` is green at **664 passed** as of this plan. Keep it green at every commit.

**Existing shapes you are extending (do not break their fields):**

- `src/agent_eval_lab/records/trajectory.py` — `Trajectory` (frozen, kw_only) currently has:
  `turns`, `usage: Usage`, `run_index: int`, `stop_reason: Literal["completed","max_steps","parse_failure"]`,
  `parse_failure: ParseFailure | None = None`, `final_state: Mapping | None = None`, `max_tokens: int | None = None`.
  `Usage` has `prompt_tokens`, `completion_tokens`, `latency_s`. `NO_CHOICES_ERROR` constant lives here.
- `src/agent_eval_lab/records/serialize.py` — `trajectory_to_dict` (lines 81-105) / `trajectory_from_dict` (lines 108-127) are the JSONL round-trip. `trajectory_from_dict` is what `cli._load_run_results` (line 167) and the golden suite call — it MUST become the v1-compat routing seam.
- `src/agent_eval_lab/runners/loop.py` — `run_single` (lines 56-139) hard-loops `for _ in range(max_steps)` (line 83), seeds `stop_reason="max_steps"` (line 81), fulfills ADR-0008 effect-requests via `_fulfill` (lines 46-53), records parse failures (lines 96-108).
- `src/agent_eval_lab/runners/multi_run.py` — `run_task_k` (lines 24-78) loops `for run_index in range(k)`, calls `run_single`, precomputes verdicts, grades. `effective_max_steps` (lines 17-21) is ADR-0004 per-task budget resolution — KEEP it.
- `src/agent_eval_lab/runners/config.py` — `ProviderConfig`, `condition_id(config) -> f"{config.id}:{config.model_id}"` (line 18-20).
- `src/agent_eval_lab/reports/classify.py` — `CLASSIFIER_VERSION = "fc-v2"` (line 34), `Category` (line 36), `Subcategory` (16 values, lines 41-58), `classify_run` (lines 113-133) priority table, `first_execution_evidence` (lines 84-110).
- `src/agent_eval_lab/metrics/cost.py` — already derives cost from tokens × `TokenPrice`. **No change needed; do not couple records to pricing.**

**v1 on-disk shape (verified from `docs/2026-06-11-coding-agent-eval/runs/runs-*.jsonl`):** each `trajectory` dict has keys `{turns, usage, run_index, stop_reason, parse_failure, final_state}` — **no** `schema_version`, **no** `max_tokens`, and `stop_reason` is one of the legacy three. This is the exact shape `v1_compat` must hydrate.

**Critical reconciliations (where existing code forces a deviation from the item spec — decided here):**

1. **`max_steps` vs the 200-tool-call cap.** The old loop bounded *model turns* via `range(max_steps)` and emitted `stop_reason="max_steps"`. The new contract counts *cumulative tool calls* against a cap of 200 (§18.1) and emits `safety_cap`. These are different units. Resolution: `run_single` gains a new keyword `safety_cap: int = 200` (tool calls) and **removes** the `range(max_steps)` truncation, replacing it with a `while True` loop that breaks on natural completion, parse failure, or the tool-call count reaching `safety_cap`. The `max_steps` parameter is **removed** from `run_single`'s signature (it no longer has turn-bounded semantics). `multi_run.run_task_k` keeps accepting `max_steps` in its signature for CLI back-compat but **no longer forwards it to `run_single`** — see Task 6 for the byte-identical-default guarantee and the two existing `multi_run` tests that depend on `max_steps` driving iterations (those assertions change to count under the cap).

2. **Existing loop test `test_loop_enforces_max_steps` (tests/runners/test_loop.py:175-194)** asserts `stop_reason == "max_steps"` after 2 turns. The new contract never emits `max_steps`. Resolution: this test is **replaced** by `test_loop_stops_at_safety_cap` (Task 3, Step …) which drives the cap with a small injected `safety_cap` and asserts `stop_reason == "safety_cap"` + `safety_cap_bound is True`.

3. **`multi_run` tests `test_per_task_budget_drives_loop_iterations_over_cli_default` and `test_task_without_max_steps_uses_cli_default` (tests/runners/test_multi_run.py:240-273)** assert `range(max_steps)` iteration counts. Under the censoring contract these counts are wrong. Resolution: both are **replaced** in Task 6 by tests that assert the run completes naturally / under the cap; `effective_max_steps` and its two unit tests (`test_effective_max_steps_*`, lines 151-182) are **kept untouched** (still valid as the per-task budget resolver, now feeding nothing in the loop — see Task 6 note; the function stays for item 002's `ExperimentSpec` wiring and to avoid churning ADR-0004).

4. **`reports/validation.py` keys on `stop_reason == "max_steps"`** (`_budget_exhausted_count`, `_starvation_suspects`, lines 100-114). New runs emit `safety_cap`, not `max_steps`. Resolution: **out of scope for 001** — validation reporting is not in the item-001 acceptance criteria, and v1 artifacts still carry `max_steps` so those counters stay meaningful for historical files. Leave `validation.py` unchanged; new `safety_cap` runs simply won't be counted as `max_steps`-budget-exhausted (correct — they're a distinct stop reason). No test in `validation` asserts over a `safety_cap` artifact, so nothing breaks. (Flagged for a follow-up item, not this one.)

5. **fc-v3 version bump breaks five literal `"fc-v2"` assertions** across the suite (enumerated in the Backward-Compatibility section). The item spec explicitly mandates "bump fc-v2 → fc-v3" with "existing fc-v2 cases keep classifying identically." Resolution: those five assertions are updated to `fc-v3` as a mandated, plan-scripted edit in Task 8 — the *category/subcategory* of every pre-existing case is unchanged; only the version *label* moves.

**Decisions deferred to impl (genuinely free choices only):**

- Variable naming for loop-local accumulators (e.g. `tool_call_total` vs `cap_count`) — any clear name; the *recorded field names* are fixed below.
- Whether to extract the EnvHealth serialization helpers as `env_health_to_dict` / `_from_dict` module functions vs inline dict literals in `trajectory_to_dict` — prefer named helpers for symmetry with `outcome_to_dict`, but either is acceptable as long as the on-disk key names match Task 2.
- The exact one-line `detail` strings in the new fc-v3 classifier rows (must cite the discriminator; wording is free).

Everything load-bearing (field names, types, defaults, stop_reason values, run_uid format, cap value, signature shapes, classifier ordering) is fixed in the tasks below.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/agent_eval_lab/records/env_health.py` | New frozen `EnvHealth` value type (model-action-independent) | **Create** |
| `src/agent_eval_lab/records/trajectory.py` | Add `schema_version`, new defaulted fields, extend `stop_reason`, `v1_compat` classmethod | **Modify** |
| `src/agent_eval_lab/records/serialize.py` | Round-trip new fields; route v1 dicts through `v1_compat` | **Modify** |
| `src/agent_eval_lab/runners/loop.py` | Censoring contract: natural completion under 200-tool-call cap; rounds/counts/wall-time; injected health probe; thread `run_uid` | **Modify** |
| `src/agent_eval_lab/runners/multi_run.py` | Replacement-trial loop (`k_valid`/`validity_fn`/`max_invalid_rate`); back-compat `run_task_k` path | **Modify** |
| `src/agent_eval_lab/reports/classify.py` | fc-v3: `environment_failure` first-class category + 3 subcategories; bump version | **Modify** |
| `tests/records/test_env_health.py` | EnvHealth value-type tests | **Create** |
| `tests/records/test_trajectory.py` | New-field defaults, `schema_version`, `v1_compat` | **Modify** |
| `tests/records/test_serialize.py` | Round-trip new fields; v1 artifact loads via compat | **Modify** |
| `tests/runners/test_loop.py` | Natural completion, safety cap, health probe, rounds/counts/run_uid | **Modify** |
| `tests/runners/test_multi_run.py` | Replacement loop, VOID, back-compat | **Modify** |
| `tests/reports/test_classify.py` | `environment_failure` + subcategories; version bump | **Modify** |
| `tests/reports/test_classify_properties.py` | Version-label update; totality holds over new stop_reasons | **Modify** |
| `tests/test_committed_runs.py` | Version-label update | **Modify** |
| `tests/test_cli.py`, `tests/reports/test_final.py` | Regression only — `"fc-v2" in md` stays green (pinned narrative); NOT edited | **Run, do not modify** |

---

## Task 1: `EnvHealth` value type

**Files:**
- Create: `src/agent_eval_lab/records/env_health.py`
- Test: `tests/records/test_env_health.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/records/test_env_health.py
import dataclasses

import pytest

from agent_eval_lab.records.env_health import EnvHealth


def test_env_health_is_frozen_and_total() -> None:
    h = EnvHealth(pre_healthy=True, post_healthy=False, pre_status=200, post_status=503)
    assert h.pre_healthy is True
    assert h.post_healthy is False
    assert h.pre_status == 200
    assert h.post_status == 503
    with pytest.raises(dataclasses.FrozenInstanceError):
        h.pre_healthy = False  # type: ignore[misc]


def test_env_health_status_fields_are_nullable() -> None:
    h = EnvHealth(pre_healthy=True, post_healthy=True, pre_status=None, post_status=None)
    assert h.pre_status is None
    assert h.post_status is None


def test_env_health_equality_is_structural() -> None:
    a = EnvHealth(pre_healthy=True, post_healthy=True, pre_status=200, post_status=200)
    b = EnvHealth(pre_healthy=True, post_healthy=True, pre_status=200, post_status=200)
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/records/test_env_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.records.env_health'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/records/env_health.py
"""Environment health probe result (D21/D28 §18.5).

Model-action-INDEPENDENT: produced by a side-channel reachability/health check
the candidate cannot influence, so an agent cannot wedge the env to convert its
own failures into 'invalid'. Frozen and total; nullable status fields carry the
probe's HTTP status (2XX/3XX = healthy per §18.5) or None when no probe ran on
that side.
"""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class EnvHealth:
    pre_healthy: bool
    post_healthy: bool
    pre_status: int | None = None
    post_status: int | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/records/test_env_health.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/records/env_health.py tests/records/test_env_health.py
git commit -m "feat(records): add EnvHealth value type (D21/D28 health probe result)"
```

---

## Task 2: Extend `Trajectory` (new fields, schema_version, extended stop_reason, v1_compat)

**Files:**
- Modify: `src/agent_eval_lab/records/trajectory.py`
- Test: `tests/records/test_trajectory.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/records/test_trajectory.py`)

```python
# tests/records/test_trajectory.py  (append; keep existing tests + imports)
from agent_eval_lab.records.env_health import EnvHealth


def test_trajectory_schema_version_defaults_to_2() -> None:
    assert _trajectory().schema_version == "2"


def test_trajectory_new_fields_default_safely() -> None:
    t = _trajectory()
    assert t.rounds == 0
    assert t.wall_time_s == 0.0
    assert t.tool_call_counts == {}
    assert t.safety_cap_bound is False
    assert t.env_health is None
    assert t.run_uid is None


def test_trajectory_accepts_new_stop_reasons() -> None:
    for reason in ("completed_natural", "safety_cap", "env_unhealthy"):
        assert _trajectory(stop_reason=reason).stop_reason == reason


def test_trajectory_records_env_health_and_counts() -> None:
    health = EnvHealth(pre_healthy=True, post_healthy=False, pre_status=200, post_status=503)
    t = _trajectory(
        stop_reason="env_unhealthy",
        rounds=3,
        wall_time_s=12.5,
        tool_call_counts={"bash": 7, "search_docs": 2},
        safety_cap_bound=False,
        env_health=health,
        run_uid="deepseek:deepseek-v4-pro__0003",
    )
    assert t.rounds == 3
    assert t.wall_time_s == 12.5
    assert t.tool_call_counts == {"bash": 7, "search_docs": 2}
    assert t.env_health == health
    assert t.run_uid == "deepseek:deepseek-v4-pro__0003"


def test_v1_compat_hydrates_legacy_dict_with_defaults() -> None:
    # A pre-revision trajectory dict: no schema_version, no new fields, legacy stop_reason.
    legacy = {
        "turns": [{"type": "message", "role": "user", "content": "hi"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "latency_s": 0.5},
        "run_index": 0,
        "stop_reason": "completed",
        "parse_failure": None,
        "final_state": None,
    }
    t = Trajectory.v1_compat(legacy)
    assert t.schema_version == "1"          # tagged as v1
    assert t.stop_reason == "completed"     # legacy value preserved as-is
    assert t.rounds == 0
    assert t.wall_time_s == 0.0
    assert t.tool_call_counts == {}
    assert t.safety_cap_bound is False
    assert t.env_health is None
    assert t.run_uid is None
    assert t.max_tokens is None
    assert t.parse_failure is None
    assert t.final_state is None


def test_v1_compat_preserves_legacy_max_steps_stop_reason() -> None:
    legacy = {
        "turns": [],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "latency_s": 0.0},
        "run_index": 1,
        "stop_reason": "max_steps",
    }
    t = Trajectory.v1_compat(legacy)
    assert t.stop_reason == "max_steps"
    assert t.schema_version == "1"
```

Note: the existing `_trajectory(**overrides)` helper (lines 6-13) does NOT pass `schema_version`, so it must keep defaulting to `"2"`. The existing tests already exercise the legacy three stop_reasons; do not change them.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/records/test_trajectory.py -v`
Expected: FAIL — `schema_version` / `rounds` / `v1_compat` not defined (AttributeError / TypeError on unexpected kwargs).

- [ ] **Step 3: Write minimal implementation** (replace the `Trajectory` dataclass block in `src/agent_eval_lab/records/trajectory.py`)

Add the import at the top of the file (after the existing `from agent_eval_lab.records.turns import Turn`):

```python
from agent_eval_lab.records.env_health import EnvHealth
```

Replace the `Trajectory` dataclass (current lines 34-48) with:

```python
@dataclass(frozen=True, kw_only=True)
class Trajectory:
    turns: tuple[Turn, ...]
    usage: Usage
    run_index: int
    stop_reason: Literal[
        # legacy values — never emitted by the censoring runner, kept parseable
        # for v1 artifacts (records+runner revision §7 / item 001 scope A)
        "completed",
        "max_steps",
        "parse_failure",
        # censoring-contract values emitted by the new runner
        "completed_natural",
        "safety_cap",
        "env_unhealthy",
    ]
    schema_version: Literal["1", "2"] = "2"
    parse_failure: ParseFailure | None = None
    final_state: Mapping[str, Any] | None = None
    max_tokens: int | None = None
    """The completion budget requested for this run (explicit eval parameter).

    None for artifacts captured before fc-v2 (pre-explicit-budget runs); those
    artifacts keep classifying as before (no token_budget_exhausted for them).
    """
    rounds: int = 0
    """Model turns taken (each assistant reply, tool-call or final message)."""
    wall_time_s: float = 0.0
    """Cumulative wall-clock seconds across the run's provider calls."""
    tool_call_counts: Mapping[str, int] = field(default_factory=dict)
    """Per-tool-name cumulative tool-call counts."""
    safety_cap_bound: bool = False
    """True iff the run stopped because it reached the safety cap (D35)."""
    env_health: EnvHealth | None = None
    """Pre/post health-probe result; None for env-free (F-set) tasks (§18.5)."""
    run_uid: str | None = None
    """Per-run unique id: f"{condition_id}__{run_index:04d}" (§18.1)."""

    @classmethod
    def v1_compat(cls, mapping: Mapping[str, Any]) -> "Trajectory":
        """Hydrate a pre-revision artifact (no schema_version / new fields).

        Tags schema_version="1"; leaves stop_reason as-is (legacy values stay
        parseable); applies safe defaults for every field the revision added.
        Turns/usage/parse_failure hydration is delegated to serialize so the
        round-trip stays single-sourced — this method takes the ALREADY-parsed
        components and assembles a v1-tagged Trajectory.
        """
        return cls(
            turns=tuple(mapping["turns"]),
            usage=mapping["usage"],
            run_index=mapping["run_index"],
            stop_reason=mapping["stop_reason"],
            schema_version="1",
            parse_failure=mapping.get("parse_failure"),
            final_state=mapping.get("final_state"),
            max_tokens=mapping.get("max_tokens"),
        )
```

Add `field` to the dataclasses import at the top of the file:

```python
from dataclasses import dataclass, field
```

**Design note for the impl agent:** `v1_compat` here takes pre-parsed `turns`/`usage`/`parse_failure` objects (not raw sub-dicts), because the turn/usage/parse-failure parsing already lives in `serialize.py` and we must not duplicate it. The serialize layer (Task 3) calls `v1_compat` with those components already constructed. The test above passes already-plain `turns`/`usage` only to exercise field defaults and the `schema_version="1"` tagging — in the test, `usage` is a plain dict and `turns` a list; that is fine because the test only asserts on the defaulted/new fields and `schema_version`, not on `usage`/`turns` round-trip equality. (If the impl agent prefers, `v1_compat` may accept the raw dict and call `serialize` helpers — but that creates a circular import; keep `v1_compat` component-based and let `serialize` own parsing.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/records/test_trajectory.py -v`
Expected: PASS (existing tests + 6 new).

- [ ] **Step 5: Run ruff and the records suite**

Run: `uv run ruff check src/agent_eval_lab/records/ && uv run pytest tests/records/ -q`
Expected: clean + green.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/records/trajectory.py tests/records/test_trajectory.py
git commit -m "feat(records): version Trajectory + add rounds/wall-time/counts/cap/env-health/run_uid + v1_compat"
```

---

## Task 3: Serialize new fields + route v1 dicts through `v1_compat`

**Files:**
- Modify: `src/agent_eval_lab/records/serialize.py`
- Test: `tests/records/test_serialize.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/records/test_serialize.py`)

```python
# tests/records/test_serialize.py  (append; keep existing imports + tests)
from agent_eval_lab.records.env_health import EnvHealth


def test_trajectory_round_trips_all_new_fields() -> None:
    health = EnvHealth(pre_healthy=True, post_healthy=False, pre_status=200, post_status=503)
    trajectory = Trajectory(
        turns=TURNS,
        usage=Usage(prompt_tokens=12, completion_tokens=7, latency_s=0.25),
        run_index=2,
        stop_reason="env_unhealthy",
        rounds=4,
        wall_time_s=9.5,
        tool_call_counts={"bash": 3, "search_docs": 1},
        safety_cap_bound=False,
        env_health=health,
        run_uid="deepseek:deepseek-v4-pro__0002",
        max_tokens=4096,
    )
    restored = trajectory_from_dict(trajectory_to_dict(trajectory))
    assert restored == trajectory
    assert restored.schema_version == "2"


def test_safety_cap_trajectory_round_trips() -> None:
    trajectory = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0,
        stop_reason="safety_cap",
        rounds=200,
        tool_call_counts={"bash": 200},
        safety_cap_bound=True,
    )
    restored = trajectory_from_dict(trajectory_to_dict(trajectory))
    assert restored.stop_reason == "safety_cap"
    assert restored.safety_cap_bound is True


def test_v1_dict_without_schema_version_loads_as_v1_with_defaults() -> None:
    # Exactly the on-disk shape of docs/2026-06-11-coding-agent-eval/runs/*.jsonl.
    v1 = {
        "turns": [{"type": "message", "role": "user", "content": "hi"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "latency_s": 0.5},
        "run_index": 0,
        "stop_reason": "completed",
        "parse_failure": None,
        "final_state": None,
    }
    t = trajectory_from_dict(v1)
    assert t.schema_version == "1"
    assert t.rounds == 0
    assert t.tool_call_counts == {}
    assert t.env_health is None
    assert t.run_uid is None
    assert t.safety_cap_bound is False


def test_v2_dict_round_trip_is_idempotent_on_disk_keys() -> None:
    health = EnvHealth(pre_healthy=False, post_healthy=False, pre_status=None, post_status=503)
    trajectory = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="env_unhealthy",
        env_health=health,
        run_uid="local:qwen3-8b__0000",
    )
    d = trajectory_to_dict(trajectory)
    assert d["schema_version"] == "2"
    assert d["env_health"] == {
        "pre_healthy": False,
        "post_healthy": False,
        "pre_status": None,
        "post_status": 503,
    }
    assert d["run_uid"] == "local:qwen3-8b__0000"
    assert d["tool_call_counts"] == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/records/test_serialize.py -v`
Expected: FAIL — `restored != trajectory` (new fields dropped); `schema_version` KeyError on the dict; `env_health` not serialized.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_eval_lab/records/serialize.py`, add the import (with the other records imports near the top):

```python
from agent_eval_lab.records.env_health import EnvHealth
```

Add EnvHealth serialization helpers (place them above `trajectory_to_dict`):

```python
def env_health_to_dict(health: EnvHealth) -> dict[str, Any]:
    return {
        "pre_healthy": health.pre_healthy,
        "post_healthy": health.post_healthy,
        "pre_status": health.pre_status,
        "post_status": health.post_status,
    }


def env_health_from_dict(data: Mapping[str, Any]) -> EnvHealth:
    return EnvHealth(
        pre_healthy=data["pre_healthy"],
        post_healthy=data["post_healthy"],
        pre_status=data.get("pre_status"),
        post_status=data.get("post_status"),
    )
```

Replace the body of `trajectory_to_dict` (current lines 81-105) so it always emits the new keys and `schema_version`:

```python
def trajectory_to_dict(trajectory: Trajectory) -> dict[str, Any]:
    parse_failure = trajectory.parse_failure
    d: dict[str, Any] = {
        "schema_version": trajectory.schema_version,
        "turns": [turn_to_dict(t) for t in trajectory.turns],
        "usage": {
            "prompt_tokens": trajectory.usage.prompt_tokens,
            "completion_tokens": trajectory.usage.completion_tokens,
            "latency_s": trajectory.usage.latency_s,
        },
        "run_index": trajectory.run_index,
        "stop_reason": trajectory.stop_reason,
        "parse_failure": (
            None
            if parse_failure is None
            else {"raw": parse_failure.raw, "error": parse_failure.error}
        ),
        "final_state": (
            None
            if trajectory.final_state is None
            else _deep_to_plain(trajectory.final_state)
        ),
        "rounds": trajectory.rounds,
        "wall_time_s": trajectory.wall_time_s,
        "tool_call_counts": dict(trajectory.tool_call_counts),
        "safety_cap_bound": trajectory.safety_cap_bound,
        "env_health": (
            None
            if trajectory.env_health is None
            else env_health_to_dict(trajectory.env_health)
        ),
        "run_uid": trajectory.run_uid,
    }
    if trajectory.max_tokens is not None:
        d["max_tokens"] = trajectory.max_tokens
    return d
```

Replace `trajectory_from_dict` (current lines 108-127) to route v1 dicts through `v1_compat`:

```python
def trajectory_from_dict(data: Mapping[str, Any]) -> Trajectory:
    usage_data = data.get("usage", {})
    usage = Usage(
        prompt_tokens=usage_data.get("prompt_tokens", 0),
        completion_tokens=usage_data.get("completion_tokens", 0),
        latency_s=usage_data.get("latency_s", 0.0),
    )
    turns = tuple(turn_from_dict(t) for t in data["turns"])
    pf = data.get("parse_failure")
    parse_failure = (
        None if pf is None else ParseFailure(raw=pf["raw"], error=pf["error"])
    )
    # v1-compat routing seam: an artifact with no schema_version predates the
    # records+runner revision — hydrate it via Trajectory.v1_compat so every
    # new field gets a safe default and the run is tagged schema_version="1".
    if "schema_version" not in data:
        return Trajectory.v1_compat(
            {
                "turns": turns,
                "usage": usage,
                "run_index": data.get("run_index", 0),
                "stop_reason": data.get("stop_reason", "completed"),
                "parse_failure": parse_failure,
                "final_state": data.get("final_state"),
                "max_tokens": data.get("max_tokens"),
            }
        )
    env_health = data.get("env_health")
    return Trajectory(
        turns=turns,
        usage=usage,
        run_index=data.get("run_index", 0),
        stop_reason=data.get("stop_reason", "completed"),
        schema_version=data["schema_version"],
        parse_failure=parse_failure,
        final_state=data.get("final_state"),
        max_tokens=data.get("max_tokens"),
        rounds=data.get("rounds", 0),
        wall_time_s=data.get("wall_time_s", 0.0),
        tool_call_counts=data.get("tool_call_counts", {}),
        safety_cap_bound=data.get("safety_cap_bound", False),
        env_health=(None if env_health is None else env_health_from_dict(env_health)),
        run_uid=data.get("run_uid"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/records/test_serialize.py -v`
Expected: PASS (existing + 4 new). The existing `test_trajectory_from_dict_applies_defaults` (which passes a dict with no `schema_version`) now returns a v1-tagged trajectory with `stop_reason == "completed"` — still satisfies its assertions (it only checks usage/run_index/stop_reason/parse_failure defaults).

- [ ] **Step 5: Run the full records + golden-conformance + committed-runs suites**

Run: `uv run pytest tests/records/ tests/test_golden_conformance.py tests/test_committed_runs.py -q`
Expected: green. The golden cases (32 files) and committed runs load through `trajectory_from_dict`; v1 golden trajectories (no `schema_version`) now hydrate via `v1_compat`, grading identically.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/records/serialize.py tests/records/test_serialize.py
git commit -m "feat(records): round-trip new Trajectory fields + route v1 artifacts through v1_compat"
```

---

## Task 4: Runner — count rounds, per-tool counts, wall-time; emit `completed_natural`; thread `run_uid`

**Files:**
- Modify: `src/agent_eval_lab/runners/loop.py`
- Test: `tests/runners/test_loop.py`

This task lands the natural-completion contract + instrumentation, **except** the safety cap and health probe (Task 5), to keep steps bite-sized. The `range(max_steps)` truncation is replaced with `while True` here; the cap is added in Task 5.

- [ ] **Step 1: Write the failing tests** (append to `tests/runners/test_loop.py`; reuse the module's `_scripted_client`, `_tool_call_response`, `_final_response`, `CONFIG`, `TASK`)

```python
# tests/runners/test_loop.py  (append)
def test_loop_completes_naturally_emits_completed_natural() -> None:
    client = _scripted_client(
        [
            _tool_call_response("search_docs", {"query": "x"}, "c1"),
            _final_response("Done."),
        ]
    )
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )
    assert trajectory.stop_reason == "completed_natural"
    assert trajectory.safety_cap_bound is False


def test_loop_counts_rounds_and_per_tool_calls() -> None:
    client = _scripted_client(
        [
            _tool_call_response("create_ticket", {"title": "x", "priority": "low"}, "c1"),
            _tool_call_response("update_ticket", {"ticket_id": "T-1", "status": "closed"}, "c2"),
            _final_response("Done."),
        ]
    )
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )
    # 3 model turns: two tool-call turns + one final message.
    assert trajectory.rounds == 3
    assert trajectory.tool_call_counts == {"create_ticket": 1, "update_ticket": 1}


def test_loop_threads_run_uid() -> None:
    client = _scripted_client([_final_response("Done.")])
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=3,
        temperature=0.0,
        max_tokens=4096,
        run_uid="local:m__0003",
    )
    assert trajectory.run_uid == "local:m__0003"


def test_loop_records_wall_time_from_latency() -> None:
    client = _scripted_client([_final_response("Done.")])
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )
    # wall_time_s mirrors accumulated provider latency (usage.latency_s).
    assert trajectory.wall_time_s == trajectory.usage.latency_s
```

Also update the existing tests that call `run_single(..., max_steps=...)`. The `max_steps` parameter is being removed in Step 3. Edit these existing tests in `tests/runners/test_loop.py` to drop the `max_steps=` kwarg and to expect the new stop_reason:

- `test_loop_threads_state_and_stops_on_final_message` (line 91): remove `max_steps=6`; change `assert trajectory.stop_reason == "completed"` → `"completed_natural"`.
- `test_loop_records_parse_failure_and_stops` (line 135): remove `max_steps=6`. (stop_reason stays `"parse_failure"`.)
- `test_loop_records_missing_choices_as_parse_failure` (line 197): remove `max_steps=6`.
- `test_run_single_records_final_state` (line 218): remove `max_steps=4`. (asserts on final_state only.)
- `test_loop_rejects_task_referencing_unregistered_tool` (line 261): remove `max_steps=6`.
- `test_empty_choices_records_the_shared_constant_verbatim` (line 296): remove `max_steps=6`.
- `test_run_single_sends_max_tokens_in_every_request` (line 320): remove `max_steps=6`.
- `test_run_single_records_max_tokens_on_trajectory` (line 356): remove `max_steps=6`.
- **Delete** `test_loop_enforces_max_steps` (lines 175-195) entirely — its contract (`stop_reason == "max_steps"` after a turn bound) is retired; replaced by `test_loop_stops_at_safety_cap` in Task 5.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runners/test_loop.py -v`
Expected: FAIL — `run_single() got an unexpected keyword argument 'run_uid'` / `rounds`/`tool_call_counts` are 0 / `completed_natural` not emitted (still `completed`).

- [ ] **Step 3: Rewrite `run_single`** in `src/agent_eval_lab/runners/loop.py`

Replace the signature and body (current lines 56-139). Remove `max_steps`, add `run_uid` (and reserve the Task-5 params with placeholder defaults so the two tasks don't fight — but only implement counting here; the cap default is wired in Task 5). For this task, implement the `while True` loop with natural-completion + parse-failure exits, round/count/wall-time accumulation, and `run_uid` threading:

```python
def run_single(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    run_index: int,
    temperature: float,
    max_tokens: int,
    apply_fn: ApplyFn = apply,
    executor: Executor | None = None,
    run_uid: str | None = None,
    safety_cap: int = 200,
    health_probe_fn: "Callable[[], EnvHealth] | None" = None,
) -> Trajectory:
    state = dict(task.initial_state or {})
    turns: list[Turn] = list(task.input.messages)
    missing = tuple(n for n in task.input.available_tools if n not in registry)
    if missing:
        raise ValueError(f"tools not in registry: {missing}")
    tools = tuple(
        tooldef_to_openai(registry[name]) for name in task.input.available_tools
    )
    prompt_tokens = 0
    completion_tokens = 0
    latency_s = 0.0
    rounds = 0
    tool_call_counts: dict[str, int] = {}
    parse_failure: ParseFailure | None = None
    stop_reason = "completed_natural"
    safety_cap_bound = False

    # Health probe (pre) — Task 5 fills this in; default is a no-op (None).
    env_health = None  # replaced in Task 5

    while True:
        response = chat_completion(
            config=config,
            messages=tuple(turn_to_message(turn) for turn in turns),
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            http_client=http_client,
        )
        rounds += 1
        usage = response.payload.get("usage", {})
        prompt_tokens += usage.get("prompt_tokens", 0)
        completion_tokens += usage.get("completion_tokens", 0)
        latency_s += response.latency_s
        choices = response.payload.get("choices") or []
        if not choices:
            parse_failure = ParseFailure(
                raw=json.dumps(dict(response.payload)),
                error=NO_CHOICES_ERROR,
            )
            stop_reason = "parse_failure"
            break
        parsed = parse_assistant_payload(choices[0].get("message", {}))
        if isinstance(parsed, ParseFailure):
            parse_failure = parsed
            stop_reason = "parse_failure"
            break
        turns.append(parsed)
        if isinstance(parsed, MessageTurn):
            stop_reason = "completed_natural"
            break
        for call in parsed.tool_calls:
            tool_call_counts[call.name] = tool_call_counts.get(call.name, 0) + 1
            state, applied = apply_fn(
                registry=registry,
                name=call.name,
                arguments=call.arguments,
                state=state,
            )
            outcome = (
                _fulfill(applied, executor)
                if isinstance(applied, ExecutionRequest)
                else applied
            )
            turns.append(ToolResultTurn(call_id=call.call_id, outcome=outcome))
        # Task 5 inserts the safety-cap check here (cumulative tool calls >= cap).

    return Trajectory(
        turns=tuple(turns),
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_s=latency_s,
        ),
        run_index=run_index,
        stop_reason=stop_reason,
        parse_failure=parse_failure,
        final_state=state,
        max_tokens=max_tokens,
        rounds=rounds,
        wall_time_s=latency_s,
        tool_call_counts=tool_call_counts,
        safety_cap_bound=safety_cap_bound,
        env_health=env_health,
        run_uid=run_uid,
    )
```

Add the imports at the top of `loop.py`:

```python
from agent_eval_lab.records.env_health import EnvHealth
```

(`Callable` is already imported from `collections.abc`.)

**Note:** `safety_cap` and `health_probe_fn` are accepted now (so the signature is stable across Tasks 4-5) but the cap check and probe calls are wired in Task 5. `wall_time_s` mirrors accumulated `latency_s` (the deterministic, mockable observable — matching the existing `monotonic`-stubbed test discipline in `test_multi_run`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/runners/test_loop.py -v`
Expected: PASS (updated existing + 4 new).

- [ ] **Step 5: Run effects + multi_run regression**

Run: `uv run pytest tests/runners/test_loop_effects.py tests/runners/test_multi_run.py -q`
Expected: `test_loop_effects` green. `test_multi_run` will have **failures** in the two budget-iteration tests and any `max_steps`-forwarding path — those are fixed in Task 6. (If `run_task_k` still forwards `max_steps=...` to `run_single`, it now errors on the removed kwarg — Task 6 fixes the call site. To keep this task's commit green in isolation, complete Task 5 + Task 6 before the next full-suite run, OR temporarily run only `tests/runners/test_loop.py tests/runners/test_loop_effects.py`. Do NOT commit a red suite — sequence Tasks 4→5→6 and run the combined check at the end of Task 6.)

- [ ] **Step 6: Commit** (only after confirming `tests/runners/test_loop.py` + `test_loop_effects.py` are green)

```bash
git add src/agent_eval_lab/runners/loop.py tests/runners/test_loop.py
git commit -m "feat(runner): censoring loop — natural completion, rounds/per-tool counts/wall-time, run_uid"
```

---

## Task 5: Runner — 200-tool-call safety cap + injected health probe

**Files:**
- Modify: `src/agent_eval_lab/runners/loop.py`
- Test: `tests/runners/test_loop.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/runners/test_loop.py`)

```python
# tests/runners/test_loop.py  (append)
from agent_eval_lab.records.env_health import EnvHealth


def _always_tool_call_client():
    """A client that always returns a fresh tool call (never a final message),
    so the loop only stops at the safety cap."""
    counter = [0]

    def handler(request):
        counter[0] += 1
        return httpx.Response(200, json=_tool_call_response("search_docs", {"query": "x"}, f"c{counter[0]}"))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_loop_stops_at_safety_cap() -> None:
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=_always_tool_call_client(),
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
        safety_cap=3,  # small cap so the test is fast; production default is 200
    )
    assert trajectory.stop_reason == "safety_cap"
    assert trajectory.safety_cap_bound is True
    # Exactly the cap's worth of tool calls were recorded (one tool call per turn).
    assert sum(trajectory.tool_call_counts.values()) == 3


def test_safety_cap_default_is_200() -> None:
    import inspect

    sig = inspect.signature(run_single)
    assert sig.parameters["safety_cap"].default == 200


def test_health_probe_called_pre_and_post_records_env_health() -> None:
    calls = []

    def probe():
        calls.append("probe")
        # pre healthy, the test inspects only that it was recorded twice
        return EnvHealth(pre_healthy=True, post_healthy=True, pre_status=200, post_status=200)

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=_scripted_client([_final_response("Done.")]),
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
        health_probe_fn=probe,
    )
    assert len(calls) == 2  # pre + post
    assert trajectory.env_health is not None
    assert trajectory.env_health.pre_healthy is True
    assert trajectory.env_health.post_healthy is True
    # A healthy post-probe does not override a natural completion.
    assert trajectory.stop_reason == "completed_natural"


def test_post_probe_unhealthy_sets_env_unhealthy_stop_reason() -> None:
    results = iter(
        [
            EnvHealth(pre_healthy=True, post_healthy=True, pre_status=200, post_status=200),   # pre
            EnvHealth(pre_healthy=True, post_healthy=False, pre_status=200, post_status=503),  # post
        ]
    )

    def probe():
        return next(results)

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=_scripted_client([_final_response("Done.")]),
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
        health_probe_fn=probe,
    )
    assert trajectory.stop_reason == "env_unhealthy"
    assert trajectory.env_health is not None
    assert trajectory.env_health.post_healthy is False
    assert trajectory.env_health.pre_healthy is True


def test_no_health_probe_yields_none_env_health() -> None:
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=_scripted_client([_final_response("Done.")]),
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )
    assert trajectory.env_health is None
    assert trajectory.stop_reason == "completed_natural"
```

**Semantic decisions fixed here (so the impl agent does not improvise):**
- The probe is called **once pre-run** and **once post-run**. Both calls return a full `EnvHealth`; the runner composes the recorded `EnvHealth` from `pre_*` of the first call and `post_*` of the second call. (Each probe invocation reports both fields, but only the relevant half is used per side — this matches §18.5 "run pre- and post-run".)
- Composition rule: `recorded = EnvHealth(pre_healthy=pre.pre_healthy, pre_status=pre.pre_status, post_healthy=post.post_healthy, post_status=post.post_status)`.
- `env_unhealthy` is set **only** when the post-probe's `post_healthy is False`. It overrides `completed_natural`/`safety_cap` (a run that finished but whose env died is invalid). It does **not** override `parse_failure` (a parse failure is recorded before the post-probe path; keep parse-failure precedence — see ordering note below).
- Ordering: pre-probe → main loop → post-probe. If the loop already set `stop_reason="parse_failure"`, the post-probe still runs and records `env_health`, but `stop_reason` stays `parse_failure` (parse failure is a harness/agent signal independent of env). Only `completed_natural` and `safety_cap` are upgraded to `env_unhealthy` when the post-probe is unhealthy.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runners/test_loop.py -k "safety_cap or health_probe or env_unhealthy or env_health" -v`
Expected: FAIL — cap never triggers (`completed_natural` returned with no cap break); probe never called.

- [ ] **Step 3: Wire the cap + probe into `run_single`**

In `src/agent_eval_lab/runners/loop.py`, replace the placeholder `env_health = None` line and the cap-check comment with real logic. Concretely:

(a) Before the `while True` loop, add the pre-probe:

```python
    pre_health = health_probe_fn() if health_probe_fn is not None else None
```

(b) Track cumulative tool calls and break at the cap. Inside the `for call in parsed.tool_calls:` block, after recording each tool call, check the cap. Replace the trailing comment `# Task 5 inserts the safety-cap check here` with a post-inner-loop check:

```python
        if sum(tool_call_counts.values()) >= safety_cap:
            stop_reason = "safety_cap"
            safety_cap_bound = True
            break
```

(Place this `if` at the same indentation as the `for call ...` loop — i.e. after the inner for-loop completes, still inside `while True`. This stops the run once cumulative tool calls reach the cap, having recorded the calls from the current turn.)

(c) After the `while True` loop, add the post-probe and env-health composition:

```python
    post_health = health_probe_fn() if health_probe_fn is not None else None
    if pre_health is not None and post_health is not None:
        env_health = EnvHealth(
            pre_healthy=pre_health.pre_healthy,
            pre_status=pre_health.pre_status,
            post_healthy=post_health.post_healthy,
            post_status=post_health.post_status,
        )
        if not post_health.post_healthy and stop_reason in (
            "completed_natural",
            "safety_cap",
        ):
            stop_reason = "env_unhealthy"
    else:
        env_health = None
```

Remove the placeholder `env_health = None` assignment that was inside the function body in Task 4 (the post-loop block above now owns `env_health`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/runners/test_loop.py -v`
Expected: PASS (all loop tests, old + Task-4 + Task-5).

- [ ] **Step 5: Run ruff**

Run: `uv run ruff check src/agent_eval_lab/runners/loop.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/runners/loop.py tests/runners/test_loop.py
git commit -m "feat(runner): 200-tool-call safety cap + injected pre/post health probe -> env_unhealthy"
```

---

## Task 6: `multi_run` — fix back-compat call site + replacement-trial loop

**Files:**
- Modify: `src/agent_eval_lab/runners/multi_run.py`
- Test: `tests/runners/test_multi_run.py`

`run_single` no longer takes `max_steps`. First make `run_task_k` green again (drop the `max_steps` forward, thread `run_uid`), then add the D34 replacement-trial loop as a new function `run_task_k_valid`.

- [ ] **Step 1: Write the failing/updated tests** (`tests/runners/test_multi_run.py`)

First, update the existing tests that depend on `max_steps` driving iterations (reconciliation #3):

- **Replace** `test_per_task_budget_drives_loop_iterations_over_cli_default` (lines 240-255) and `test_task_without_max_steps_uses_cli_default` (lines 258-273) with one test that the runner completes naturally under the cap (the `_counting_tool_call_handler` always returns a tool call, so it now runs to the safety cap):

```python
def test_run_task_k_runs_to_safety_cap_when_model_never_finishes() -> None:
    counter = [0]
    handler = _counting_tool_call_handler(counter)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    results = run_task_k(
        task=_budget_task(None),
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k=1,
        max_steps=4,  # accepted for CLI back-compat; no longer bounds the loop
        temperature=0.0,
        max_tokens=4096,
    )
    # The model never emits a final message -> the run stops at the 200 cap.
    assert results[0].trajectory.stop_reason == "safety_cap"
    assert results[0].trajectory.safety_cap_bound is True
    assert sum(results[0].trajectory.tool_call_counts.values()) == 200
```

Keep `test_effective_max_steps_prefers_per_task_budget` and `test_effective_max_steps_falls_back_to_default_when_absent` (lines 151-182) **unchanged** — `effective_max_steps` stays as a pure resolver.

Then add the new run_uid + replacement-loop tests:

```python
def test_run_task_k_threads_run_uid_per_run() -> None:
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    results = run_task_k(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k=3,
        max_steps=6,
        temperature=0.0,
        max_tokens=4096,
    )
    uids = [r.trajectory.run_uid for r in results]
    assert uids == [
        "local:qwen3-8b__0000",
        "local:qwen3-8b__0001",
        "local:qwen3-8b__0002",
    ]


def test_run_task_k_valid_replaces_invalid_until_k_valid() -> None:
    from agent_eval_lab.runners.multi_run import run_task_k_valid

    client = httpx.Client(transport=httpx.MockTransport(_handler))
    # validity_fn: first call invalid, rest valid -> needs one replacement.
    seen = [0]

    def validity_fn(result):
        seen[0] += 1
        return seen[0] != 1  # run #1 invalid, runs #2.. valid

    outcome = run_task_k_valid(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k_valid=2,
        max_invalid_rate=0.6,
        validity_fn=validity_fn,
        max_steps=6,
        temperature=0.0,
        max_tokens=4096,
    )
    assert outcome.void is False
    assert len(outcome.valid_runs) == 2
    # 3 attempts total (1 invalid + 2 valid); attempt_index increments.
    assert [r.attempt_index for r in outcome.attempts] == [0, 1, 2]


def test_run_task_k_valid_voids_when_invalid_rate_exceeded() -> None:
    from agent_eval_lab.runners.multi_run import run_task_k_valid

    client = httpx.Client(transport=httpx.MockTransport(_handler))

    def validity_fn(result):
        return False  # every run invalid

    outcome = run_task_k_valid(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k_valid=2,
        max_invalid_rate=0.4,
        validity_fn=validity_fn,
        max_steps=6,
        temperature=0.0,
        max_tokens=4096,
    )
    assert outcome.void is True
    assert len(outcome.valid_runs) < 2  # never scored over fewer than k valid


def test_env_unhealthy_run_counts_as_invalid() -> None:
    from agent_eval_lab.runners.multi_run import run_task_k_valid

    # No validity_fn: invalidity is driven purely by stop_reason == env_unhealthy.
    # Use a health probe that reports post-unhealthy on the first run only.
    flips = [0]

    def probe():
        from agent_eval_lab.records.env_health import EnvHealth

        flips[0] += 1
        # pre always healthy; post unhealthy on the very first post-probe call.
        # Each run calls probe twice (pre, post); the 2nd call is run-1's post.
        post_ok = flips[0] != 2
        return EnvHealth(
            pre_healthy=True, post_healthy=post_ok, pre_status=200,
            post_status=200 if post_ok else 503,
        )

    client = httpx.Client(transport=httpx.MockTransport(_handler))
    outcome = run_task_k_valid(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k_valid=1,
        max_invalid_rate=0.9,
        health_probe_fn=probe,
        max_steps=6,
        temperature=0.0,
        max_tokens=4096,
    )
    assert outcome.void is False
    assert len(outcome.valid_runs) == 1
    assert any(
        r.run.trajectory.stop_reason == "env_unhealthy" for r in outcome.attempts
    )
```

Keep `test_runs_k_times_and_grades_each_run`, `test_run_task_k_grades_final_state_spec`, `test_run_task_k_precomputes_and_threads_execution_verdicts`, `test_run_task_k_threads_code_world_binding_to_run_single` — but **remove `max_steps=` is NOT removed from `run_task_k` calls** (the function keeps the param); these tests pass `max_steps=...` to `run_task_k` (not `run_single`), which is fine. The byte-identical test `test_run_task_k_defaults_yield_byte_identical_workspace_run` (line 357) must still pass — but the serialized dict now includes the new fields with default values on both sides, so equality holds. Verify it does after Step 3.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runners/test_multi_run.py -v`
Expected: FAIL — `run_task_k_valid` not importable; `run_uid` is None; the budget tests reference the deleted behavior; `run_task_k` errors forwarding `max_steps` to `run_single`.

- [ ] **Step 3: Rewrite `multi_run.py`**

Keep `effective_max_steps` exactly as-is. Add a frozen `TrialAttempt` + `ReplacementOutcome` result type and the two functions. Replace the `run_single(...)` call to drop `max_steps` and thread `run_uid`:

```python
"""EDGE: run a task k times (multi-run from day 1) and grade every run."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import httpx

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.env_health import EnvHealth
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.runners.loop import ApplyFn, Executor, run_single
from agent_eval_lab.runners.oracle_edge import precompute_execution_verdicts
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.workspace import ToolDef
from agent_eval_lab.tools.workspace import apply as workspace_apply


def effective_max_steps(task: Task, *, default: int) -> int:
    """ADR-0004: the per-task metadata.max_steps WINS when present; the CLI
    default is the fallback for tasks without one (a floor, never a cap).

    Retained as the per-task budget resolver for item-002 ExperimentSpec wiring;
    the censoring loop no longer turn-bounds on it (the safety cap governs)."""
    declared = task.metadata.max_steps
    return declared if declared is not None else default


def _grade_one(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    trajectory,
) -> RunResult:
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
    return grade


def _run_one(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    run_index: int,
    condition: str,
    temperature: float,
    max_tokens: int,
    apply_fn: ApplyFn,
    executor: Executor | None,
    health_probe_fn: "Callable[[], EnvHealth] | None",
) -> RunResult:
    trajectory = run_single(
        task=task,
        registry=registry,
        config=config,
        http_client=http_client,
        run_index=run_index,
        temperature=temperature,
        max_tokens=max_tokens,
        apply_fn=apply_fn,
        executor=executor,
        run_uid=f"{condition}__{run_index:04d}",
        health_probe_fn=health_probe_fn,
    )
    grade = _grade_one(task=task, registry=registry, trajectory=trajectory)
    return RunResult(
        task_id=task.id,
        condition_id=condition,
        run_index=run_index,
        trajectory=trajectory,
        grade=grade,
    )


def run_task_k(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    k: int,
    max_steps: int,
    temperature: float,
    max_tokens: int,
    apply_fn: ApplyFn = workspace_apply,
    executor: Executor | None = None,
) -> tuple[RunResult, ...]:
    """Backward-compatible multi-run: k runs, every run valid, no replacement.
    `max_steps` is accepted for CLI compatibility but no longer bounds the loop
    (the censoring contract's safety cap governs)."""
    condition = condition_id(config)
    return tuple(
        _run_one(
            task=task,
            registry=registry,
            config=config,
            http_client=http_client,
            run_index=run_index,
            condition=condition,
            temperature=temperature,
            max_tokens=max_tokens,
            apply_fn=apply_fn,
            executor=executor,
            health_probe_fn=None,
        )
        for run_index in range(k)
    )


@dataclass(frozen=True, kw_only=True)
class TrialAttempt:
    attempt_index: int
    valid: bool
    run: RunResult


@dataclass(frozen=True, kw_only=True)
class ReplacementOutcome:
    valid_runs: tuple[RunResult, ...]
    attempts: tuple[TrialAttempt, ...]
    void: bool  # True iff the max-invalid-rate threshold tripped before k valid


def _is_invalid(
    run: RunResult, validity_fn: "Callable[[RunResult], bool] | None"
) -> bool:
    """D34/D21: a trial is invalid iff its env was unhealthy OR validity_fn says so."""
    if run.trajectory.stop_reason == "env_unhealthy":
        return True
    if validity_fn is not None and validity_fn(run) is False:
        return True
    return False


def run_task_k_valid(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    k_valid: int,
    max_invalid_rate: float,
    max_steps: int,
    temperature: float,
    max_tokens: int,
    validity_fn: "Callable[[RunResult], bool] | None" = None,
    health_probe_fn: "Callable[[], EnvHealth] | None" = None,
    apply_fn: ApplyFn = workspace_apply,
    executor: Executor | None = None,
) -> ReplacementOutcome:
    """D34 replacement-trial loop: run until exactly k_valid valid trials.

    A trial is invalid if its env was unhealthy or validity_fn returns False; on
    invalid, a replacement runs immediately. If the running invalid-rate would
    exceed max_invalid_rate before k_valid valid trials are obtained, return a
    VOID outcome (never scored over fewer than k_valid valid runs)."""
    condition = condition_id(config)
    attempts: list[TrialAttempt] = []
    valid_runs: list[RunResult] = []
    invalid_count = 0
    attempt_index = 0
    while len(valid_runs) < k_valid:
        run = _run_one(
            task=task,
            registry=registry,
            config=config,
            http_client=http_client,
            run_index=attempt_index,
            condition=condition,
            temperature=temperature,
            max_tokens=max_tokens,
            apply_fn=apply_fn,
            executor=executor,
            health_probe_fn=health_probe_fn,
        )
        invalid = _is_invalid(run, validity_fn)
        attempts.append(
            TrialAttempt(attempt_index=attempt_index, valid=not invalid, run=run)
        )
        if invalid:
            invalid_count += 1
        else:
            valid_runs.append(run)
        attempt_index += 1
        # VOID when the invalid-rate over attempts so far exceeds the bound and
        # we have not yet reached k_valid (D28/D34).
        total = len(attempts)
        if (
            len(valid_runs) < k_valid
            and total > 0
            and (invalid_count / total) > max_invalid_rate
        ):
            return ReplacementOutcome(
                valid_runs=tuple(valid_runs),
                attempts=tuple(attempts),
                void=True,
            )
    return ReplacementOutcome(
        valid_runs=tuple(valid_runs), attempts=tuple(attempts), void=False
    )
```

**Note on `_grade_one`:** the helper returns the `GradeResult` from `grade_trajectory` (the existing `multi_run` flow); the inline `_run_one` builds the `RunResult`. This preserves the exact verdict-precompute → grade order from the current `run_task_k` (criterion 13). The byte-identical guarantee for `run_task_k` holds because the per-run path is unchanged except `run_uid` is now populated — and the existing byte-identical test compares default-vs-explicit on the SAME `run_task_k`, so both sides carry the same `run_uid`; equality still holds.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/runners/test_multi_run.py -v`
Expected: PASS (kept + replaced + new). Confirm `test_run_task_k_defaults_yield_byte_identical_workspace_run` is green (the `monotonic` stub pins latency; both sides now carry `run_uid="local:qwen3-8b__0000"` identically).

- [ ] **Step 5: Run the full runner + records + golden + committed suites**

Run: `uv run pytest tests/runners/ tests/records/ tests/test_golden_conformance.py tests/test_committed_runs.py -q`
Expected: green (Task 8's classifier version bump not yet done — `test_committed_runs` asserts `fc-v2`; it still passes because we have not bumped the version yet. The version bump + its assertion update happen together in Task 8.)

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/runners/multi_run.py tests/runners/test_multi_run.py
git commit -m "feat(runner): run_uid threading + D34 replacement-trial loop (run_task_k_valid)"
```

---

## Task 7: CLI call-site fix (`run_task_k` no longer forwards `max_steps` to `run_single`)

**Files:**
- Modify: `src/agent_eval_lab/cli.py` (only if needed — `run_baseline` calls `run_task_k`, which still accepts `max_steps`; no change should be required)
- Test: `tests/test_cli.py` (regression only)

- [ ] **Step 1: Verify whether any change is needed**

Run: `uv run pytest tests/test_cli.py -q`
Expected: If green, `cli.py` needs no edit (it calls `run_task_k`, whose signature is unchanged). If red on a `max_steps`/`run_single` path, inspect and fix the call site so it matches `run_task_k`'s kept signature. **Do not** change CLI flags.

- [ ] **Step 2: Commit (only if a fix was needed)**

```bash
git add src/agent_eval_lab/cli.py
git commit -m "fix(cli): align run_baseline with censoring-contract run_task_k signature"
```

(If no change was needed, skip this task's commit.)

---

## Task 8: fc-v3 — `environment_failure` first-class category + version bump

**Files:**
- Modify: `src/agent_eval_lab/reports/classify.py`
- Test: `tests/reports/test_classify.py`, `tests/reports/test_classify_properties.py`, `tests/test_committed_runs.py`, `tests/test_cli.py`, `tests/reports/test_final.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/reports/test_classify.py`)

The `_run` helper (lines 21-65) builds a `Trajectory` without `env_health`/`schema_version`; extend it with optional kwargs. First add the helper extension and new tests:

```python
# tests/reports/test_classify.py  (append; also extend the _run helper — see note)
from agent_eval_lab.records.env_health import EnvHealth


def _env_run(*, stop_reason="env_unhealthy", env_health=None, passed=False):
    """A run carrying env-health fields, for fc-v3 environment_failure rows."""
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage

    return RunResult(
        task_id="b-001",
        condition_id="deepseek:deepseek-v4-pro",
        run_index=0,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
            run_index=0,
            stop_reason=stop_reason,
            final_state={"files": {}},
            env_health=env_health,
        ),
        grade=GradeResult(
            grader_id="execution",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=None,
        ),
    )


def test_fc_v3_version_label() -> None:
    assert CLASSIFIER_VERSION == "fc-v3"


def test_environment_failure_is_a_category() -> None:
    from typing import get_args

    from agent_eval_lab.reports.classify import Category

    assert "environment_failure" in get_args(Category)


def test_env_unhealthy_post_probe_failed() -> None:
    health = EnvHealth(pre_healthy=True, post_healthy=False, pre_status=200, post_status=503)
    run = _env_run(stop_reason="env_unhealthy", env_health=health)
    c = classify_run(run)
    assert (c.category, c.subcategory) == ("environment_failure", "post_probe_failed")


def test_env_unhealthy_pre_probe_failed() -> None:
    health = EnvHealth(pre_healthy=False, post_healthy=False, pre_status=503, post_status=503)
    run = _env_run(stop_reason="env_unhealthy", env_health=health)
    c = classify_run(run)
    assert (c.category, c.subcategory) == ("environment_failure", "pre_probe_failed")


def test_env_unhealthy_runner_flagged_without_health_record() -> None:
    # stop_reason flags env failure but no EnvHealth was recorded.
    run = _env_run(stop_reason="env_unhealthy", env_health=None)
    c = classify_run(run)
    assert (c.category, c.subcategory) == ("environment_failure", "runner_flagged")


def test_passed_run_with_unhealthy_post_probe_still_passes() -> None:
    # Row 1 (passed) still wins first — a passed grade is not an env failure.
    health = EnvHealth(pre_healthy=True, post_healthy=False, pre_status=200, post_status=503)
    run = _env_run(stop_reason="env_unhealthy", env_health=health, passed=True)
    assert classify_run(run).category == "passed"


def test_env_check_runs_after_parse_but_before_execution_grading() -> None:
    # A parse failure still classifies as parse failure even if env is unhealthy
    # (parse/harness checks precede the env check; §6 ordering).
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage

    run = RunResult(
        task_id="b-001",
        condition_id="c",
        run_index=0,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
            run_index=0,
            stop_reason="parse_failure",
            parse_failure=ParseFailure(raw="{}", error=NO_CHOICES_ERROR),
            env_health=EnvHealth(pre_healthy=True, post_healthy=False),
        ),
        grade=GradeResult(grader_id="execution", passed=False, score=0.0, evidence={}),
    )
    # NO_CHOICES_ERROR -> harness/provider_response (parse check wins over env).
    c = classify_run(run)
    assert c.category == "harness_failure"
```

Then update the version-label assertions in the same file:
- Line 307 `test_classifier_version_is_fc_v2`: change `assert CLASSIFIER_VERSION == "fc-v2"` → `"fc-v3"` (or rely on the new `test_fc_v3_version_label` and delete the old assertion's body — but keep the function and just update the literal).
- `_is` helper (line 91) asserts `c.classifier_version == CLASSIFIER_VERSION` — stays correct (reads the constant).
- `test_subcategory_vocabulary_is_closed_at_16_after_fc_v2` (line 310): the closed vocabulary GROWS by 3 (pre/post/runner). Update to assert the new count and membership:

```python
def test_subcategory_vocabulary_is_closed_at_19_after_fc_v3() -> None:
    """fc-v3 adds pre_probe_failed | post_probe_failed | runner_flagged."""
    assert len(get_args(Subcategory)) == 19
    for sub in ("pre_probe_failed", "post_probe_failed", "runner_flagged"):
        assert sub in get_args(Subcategory)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/reports/test_classify.py -v`
Expected: FAIL — `environment_failure` not in `Category`; subcategories absent; version still `fc-v2`.

- [ ] **Step 3: Implement fc-v3 in `src/agent_eval_lab/reports/classify.py`**

(a) Bump the version and extend the types:

```python
CLASSIFIER_VERSION = "fc-v3"

Category = Literal[
    "passed",
    "task_failure",
    "agent_failure",
    "harness_failure",
    "environment_failure",  # fc-v3: env-validity failure (D21), peer to the rest
]
```

Append the three new subcategories to the `Subcategory` literal (now 19 values):

```python
    # fc-v3 environment_failure subcategories (D21/D28 §6)
    "pre_probe_failed",
    "post_probe_failed",
    "runner_flagged",
```

(b) Insert the env check into `classify_run` **after** the parse/harness checks and **before** execution-evidence grading. Replace the body of `classify_run` (lines 113-133):

```python
def classify_run(run: RunResult) -> RunClassification:
    """fc-v3: priority-ordered, first-match-wins, total — never raises."""
    if run.grade.passed:  # row 1 wins first, even over a recorded parse_failure
        return _classification("passed", None, "grade.passed")
    parse_failure = run.trajectory.parse_failure
    if run.trajectory.stop_reason == "parse_failure" and parse_failure is None:
        return _classification(
            "harness_failure",
            "sandbox_fault",
            "stop_reason=parse_failure but parse_failure record is None "
            "(harness wiring defect)",
        )
    if parse_failure is not None:  # rows 2-3 (+ token_budget_exhausted)
        return _classify_parse_failure(parse_failure.error, run)
    env = _classify_environment(run)  # fc-v3: after parse/harness, before execution
    if env is not None:
        return env
    exec_ev = first_execution_evidence(run.grade.evidence, run.grade.grader_id)
    early = _classify_execution_evidence(exec_ev)
    if early is not None:
        return early
    return _classify_grade_and_budget(run, exec_ev)
```

(c) Add the `_classify_environment` helper (place it just below `classify_run`):

```python
def _classify_environment(run: RunResult) -> RunClassification | None:
    """fc-v3 environment_failure (D21): driven by env_health / stop_reason.

    Pure/total: returns None when the run carries no env-failure signal, so the
    fc-v2 chain runs unchanged for env-free (F-set) runs and all legacy artifacts
    (which have stop_reason != 'env_unhealthy' and env_health is None)."""
    if run.trajectory.stop_reason != "env_unhealthy":
        return None
    health = run.trajectory.env_health
    if health is None:
        return _classification(
            "environment_failure",
            "runner_flagged",
            "stop_reason=env_unhealthy with no EnvHealth record",
        )
    if not health.pre_healthy:
        return _classification(
            "environment_failure",
            "pre_probe_failed",
            f"pre-probe unhealthy (pre_status={health.pre_status})",
        )
    return _classification(
        "environment_failure",
        "post_probe_failed",
        f"post-probe unhealthy (post_status={health.post_status})",
    )
```

Update the module docstring's "fc-v2 changes" header to add an "fc-v3 changes" note (one paragraph: environment_failure category checked after parse/harness, before execution grading; driven by env_health/stop_reason; pure/total/versioned).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/reports/test_classify.py -v`
Expected: PASS (every fc-v2 row test still green — their category/subcategory unchanged; `_is` reads the constant so version assertions pass; new fc-v3 rows pass).

- [ ] **Step 5: Update the property test + remaining version-label assertions**

In `tests/reports/test_classify_properties.py`:
- Line 10 `_CATEGORIES`: add `"environment_failure"`.
- Line 129: `assert classification.classifier_version == "fc-v2"` → `"fc-v3"`.
- The `_trajectories` strategy (lines 97-111) samples `stop_reason` from the legacy three (line 107). Extend it to include the new values so totality is exercised over `env_unhealthy`/`safety_cap`/`completed_natural`, and add `env_health` to the strategy:

```python
    stop_reason=st.sampled_from(
        [
            "completed",
            "max_steps",
            "parse_failure",
            "completed_natural",
            "safety_cap",
            "env_unhealthy",
        ]
    ),
```

Add an `env_health` strategy and pass it to `st.builds(Trajectory, ...)`:

```python
_env_healths = st.none() | st.builds(
    __import__("agent_eval_lab.records.env_health", fromlist=["EnvHealth"]).EnvHealth,
    pre_healthy=st.booleans(),
    post_healthy=st.booleans(),
    pre_status=st.none() | st.integers(min_value=100, max_value=599),
    post_status=st.none() | st.integers(min_value=100, max_value=599),
)
```

(Cleaner: add `from agent_eval_lab.records.env_health import EnvHealth` at the top and use `st.builds(EnvHealth, ...)`.) Then add `env_health=_env_healths` to the `_trajectories = st.builds(Trajectory, ...)` call. Update the totality assertion (`test_classify_run_is_total_and_closed`) `_CATEGORIES` membership and the `(category == "passed") == (subcategory is None)` invariant — that invariant still holds for environment_failure (it always has a subcategory).

In `tests/test_committed_runs.py` line 32: `assert classification.classifier_version == "fc-v2"` → `"fc-v3"`.

**Do NOT change `tests/test_cli.py` line 1040 or `tests/reports/test_final.py` line 99** (`assert "fc-v2" in md`). VERIFIED: those assertions stay green after the bump. The report renders `fc-v2` from TWO independent sources — (1) the header line `· classifier {report.classifier_version}` (`final.py:529`), which flips to `fc-v3` from the constant, AND (2) a pinned historical narrative block `_HARNESS_DEFECT_NARRATIVE` (`final.py:378-392`, rendered at line 593) whose prose intentionally cites `"### Harness defect found and fixed (fc-v1 → fc-v2)"` and `"the fc-v2 token_budget_exhausted subcategory"`. The narrative is a frozen record of history and keeps the literal `fc-v2`; therefore `"fc-v2" in md` remains true. These two tests are NOT in the edit set for Task 8. (If a future item rewrites the narrative, revisit — but item 001 leaves it untouched.)

- [ ] **Step 6: Run the classifier + property + committed + cli + final suites**

Run: `uv run pytest tests/reports/test_classify.py tests/reports/test_classify_properties.py tests/test_committed_runs.py tests/test_cli.py tests/reports/test_final.py -q`
Expected: green.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/reports/classify.py tests/reports/test_classify.py tests/reports/test_classify_properties.py tests/test_committed_runs.py
git commit -m "feat(classify): fc-v3 environment_failure category (pre/post/runner) + version bump"
```

---

## Task 9: Full-suite green + ruff clean (verification gate)

**Files:** none (verification only)

- [ ] **Step 1: Run the entire suite**

Run: `uv run pytest -q`
Expected: ALL green. Baseline was 664; the net count rises by the new tests (EnvHealth ×3, trajectory ×6, serialize ×4, loop ×8, multi_run ×~5, classify ×7) minus deletions (`test_loop_enforces_max_steps`, two multi_run budget tests). Do not assert an exact number; assert zero failures/errors.

- [ ] **Step 2: Lint**

Run: `uv run ruff check src/ tests/`
Expected: clean. Fix any unused-import / line-length issues introduced.

- [ ] **Step 3: Confirm backward-compat artifacts load**

Run: `uv run pytest tests/test_golden_conformance.py tests/test_committed_runs.py -q`
Expected: green — v1 golden + committed runs hydrate via `v1_compat`, classify under fc-v3.

- [ ] **Step 4: Final commit (if Step 2 required fixes)**

```bash
git add -A
git commit -m "chore: ruff clean after records+runner revision"
```

---

## Backward-Compatibility (every existing test/artifact that must stay green, and how)

| Existing test / artifact | Risk under this change | Guarantee |
|---|---|---|
| `tests/test_committed_runs.py` | Loads `docs/2026-06-11-coding-agent-eval/runs/runs-*.jsonl` (v1, no `schema_version`) and asserts `classifier_version`. | `trajectory_from_dict` routes the v1 dicts through `Trajectory.v1_compat` (Task 3) → all new fields default, `stop_reason` preserved. The version assertion is updated `fc-v2`→`fc-v3` (Task 8 Step 5). |
| `tests/test_golden_conformance.py` (32 cases) | Golden trajectories are v1-shaped; grading must reproduce. | v1 hydration preserves `turns`/`usage`/`final_state`/`parse_failure` exactly; grading reads only those — verdicts unchanged. |
| `tests/records/test_trajectory.py` (existing) | `_trajectory()` helper omits `schema_version`/new fields. | All new fields are defaulted; `schema_version` defaults `"2"`. Existing assertions untouched. |
| `tests/records/test_serialize.py` (existing) | `test_trajectory_from_dict_applies_defaults` passes a dict with no `schema_version`. | Now returns a v1-tagged trajectory; the test only asserts usage/run_index/stop_reason/parse_failure defaults — all still hold. |
| `tests/metrics/test_cost.py` | Cost derivation. | **No code change** to `metrics/cost.py`; records never gain a cost field. Tests untouched, stay green. |
| `tests/runners/test_loop.py` (existing) | Call `run_single(..., max_steps=...)`; one asserts `stop_reason=="completed"`/`"max_steps"`. | `max_steps` kwarg removed → those calls edited to drop it (Task 4 Step 1); `completed`→`completed_natural`; `test_loop_enforces_max_steps` deleted (superseded by safety-cap test). Reconciliation #1/#2. |
| `tests/runners/test_multi_run.py` (existing) | Two tests assert `range(max_steps)` iteration counts; byte-identical test. | Budget-iteration tests replaced with safety-cap completion test (Task 6); `effective_max_steps` unit tests kept; byte-identical test stays green (both sides carry identical `run_uid`). Reconciliation #3. |
| `tests/runners/test_loop_effects.py` | ADR-0008 effect-request fulfillment. | `_fulfill` and the effect-request branch are copied verbatim into the rewritten loop; no behavior change. |
| `tests/reports/test_classify.py` (fc-v2 rows 1-16) | Version bump + new category insertion. | Env check returns `None` for every fc-v2 run (`stop_reason != "env_unhealthy"`), so the fc-v2 chain runs unchanged; only the version label moves. Each row test's `(category, subcategory)` is identical. |
| `tests/reports/test_classify_properties.py` | Asserts version `"fc-v2"`; samples only legacy stop_reasons. | Version literal updated; strategy extended to the new stop_reasons + `env_health` so totality is proven over fc-v3's input space; `_CATEGORIES` gains `environment_failure`. |
| `tests/test_cli.py` (`fc-v2` in md) + `tests/reports/test_final.py` (`fc-v2` in md) | Rendered-report version string. | **Left unchanged — VERIFIED stay green.** The report renders `fc-v2` from a pinned historical narrative (`final.py:378-392`, rendered) independent of `CLASSIFIER_VERSION`; the header flips to `fc-v3` via the constant. Both literals coexist in `md`, so `"fc-v2" in md` stays true. Not in Task 8's edit set. |
| `reports/validation.py` (`stop_reason=="max_steps"` counters) | New runs emit `safety_cap`, not `max_steps`. | **Left unchanged** (out of 001 scope, reconciliation #4): v1 artifacts still carry `max_steps`; no validation test asserts over a `safety_cap` artifact. Flagged for a follow-up item. |
| `cli._load_run_results` / `run_baseline` | Loads via `trajectory_from_dict`; calls `run_task_k`. | Loader unchanged (routing is inside `trajectory_from_dict`); `run_task_k` keeps its signature. Task 7 verifies no CLI edit is needed. |

---

## Ordered checklist (for the drift-checker to diff against the final implementation)

1. [ ] `src/agent_eval_lab/records/env_health.py` exists with frozen `EnvHealth(pre_healthy, post_healthy, pre_status=None, post_status=None)`.
2. [ ] `Trajectory.schema_version: Literal["1","2"] = "2"`.
3. [ ] `Trajectory` has `rounds: int = 0`, `wall_time_s: float = 0.0`, `tool_call_counts: Mapping[str,int]` (default `{}`), `safety_cap_bound: bool = False`, `env_health: EnvHealth | None = None`, `run_uid: str | None = None`.
4. [ ] `Trajectory.stop_reason` literal includes `completed`, `max_steps`, `parse_failure`, `completed_natural`, `safety_cap`, `env_unhealthy`.
5. [ ] `Trajectory.v1_compat(mapping)` classmethod tags `schema_version="1"`, preserves `stop_reason`, defaults all new fields.
6. [ ] `trajectory_to_dict` emits `schema_version`, `rounds`, `wall_time_s`, `tool_call_counts`, `safety_cap_bound`, `env_health` (nullable), `run_uid`; still omits `max_tokens` when None.
7. [ ] `trajectory_from_dict` routes dicts WITHOUT `schema_version` through `v1_compat`; reads the new keys with safe defaults for v2 dicts.
8. [ ] `env_health_to_dict` / `env_health_from_dict` round-trip `EnvHealth`.
9. [ ] `run_single` signature: NO `max_steps`; has `run_uid: str | None = None`, `safety_cap: int = 200`, `health_probe_fn: Callable[[], EnvHealth] | None = None`.
10. [ ] `run_single` loop is `while True` (no `range(max_steps)`); natural completion → `stop_reason="completed_natural"`.
11. [ ] `run_single` counts `rounds` (per model turn), accumulates per-tool `tool_call_counts`, sets `wall_time_s` = accumulated latency.
12. [ ] Safety cap: cumulative tool calls `>= safety_cap` → `stop_reason="safety_cap"`, `safety_cap_bound=True`.
13. [ ] Health probe called pre + post; `env_health` composed from pre.pre_* and post.post_*; post-unhealthy upgrades `completed_natural`/`safety_cap` → `env_unhealthy`; never overrides `parse_failure`; `None` probe → `env_health=None`.
14. [ ] ADR-0008 effect-request fulfillment (`_fulfill`) and parse-failure handling are byte-for-byte preserved.
15. [ ] `run_task_k` keeps its signature (incl. `max_steps`), no longer forwards `max_steps` to `run_single`, threads `run_uid=f"{condition}__{run_index:04d}"`.
16. [ ] `run_task_k_valid(k_valid, max_invalid_rate, validity_fn=None, health_probe_fn=None, ...)` returns `ReplacementOutcome(valid_runs, attempts, void)`.
17. [ ] A trial is invalid iff `stop_reason=="env_unhealthy"` OR `validity_fn(run) is False`; replacement runs immediately; `attempt_index` increments per attempt.
18. [ ] VOID returned when running invalid-rate `> max_invalid_rate` before `k_valid` valid trials; never scored over `< k_valid`.
19. [ ] `run_task_k` with no `validity_fn` is behaviorally identical to before (every run valid; byte-identical serialization preserved).
20. [ ] `CLASSIFIER_VERSION == "fc-v3"`.
21. [ ] `Category` includes `environment_failure`; `Subcategory` includes `pre_probe_failed`, `post_probe_failed`, `runner_flagged` (19 total).
22. [ ] `classify_run` checks env (`_classify_environment`) AFTER parse/harness, BEFORE execution-evidence grading.
23. [ ] `_classify_environment` returns `None` unless `stop_reason=="env_unhealthy"`; maps `pre_healthy False → pre_probe_failed`, `env_health None → runner_flagged`, else `post_probe_failed`; passed runs still classify `passed`.
24. [ ] Classifier stays pure/total (Hypothesis property test green over the extended stop_reason + env_health space).
25. [ ] `metrics/cost.py` unchanged (cost stays derived; no pricing in records/runner).
26. [ ] `uv run pytest` fully green; `uv run ruff check src/ tests/` clean.
27. [ ] Backward-compat: golden-conformance (32) + committed-runs load via `v1_compat` and classify under fc-v3.

---

## Self-Review notes

- **Spec coverage:** Scope A (records) → Tasks 1-3 + checklist 1-8. Scope B (censoring runner) → Tasks 4-5 + checklist 9-14. Scope C (replacement loop) → Task 6 + checklist 15-19. Scope D (fc-v3) → Task 8 + checklist 20-24. Scope E (serialization compat) → Task 3 + Backward-Compat table. Acceptance criteria 1-4 each map to a task. §18.1 frozen params (cap=200, run_uid format, schema versioning, stop_reason values) are pinned in checklist 2-4, 9, 12, 15. §18.5 probe semantics (2XX/3XX healthy; pre+post; model-independent) honored by the injected callback + EnvHealth docstring.
- **Type consistency:** `EnvHealth` fields, `Trajectory` field names, `run_single`/`run_task_k_valid` signatures, `ReplacementOutcome`/`TrialAttempt` shapes, and classifier `Category`/`Subcategory` members are identical wherever referenced across tasks.
- **Cost decision justified:** records expose only token inputs (`Usage`); cost derives in `metrics/cost.py` — matches CLAUDE.md (pricing out of the runner) and the item spec's explicit "Cost stays DERIVED" with no strong counter-reason found.
- **No placeholders:** every code step shows full code; every test step shows assertions; commands and expected outcomes are explicit.
