# Item 001 — Records + runner revision (precondition)

**Source:** spec §7 (records+runner revision) + §18.1 (frozen params) + §6 fc-v3 + §18.5 health probe.
**Derived from a thrice-reviewed + grilled spec — brainstorm/grill PRE-COMPLETED ⏭️.**

## Why
The current `Trajectory` cannot store the promised metrics and the runner always truncates
(`loop.py` hard-loops `range(max_steps)`). Nothing measured can be recorded until this lands.
This is the precondition for every other item.

## Goal
Extend the records (append-only, versioned, backward-compatible) to store rounds / cost-inputs /
wall-time / tool-call-counts / cap-binding / env-health / run_uid, revise the runner to a
**censoring contract** (run to natural completion under a generous safety cap), add the
**replacement-trial loop**, and add the **fc-v3 `environment_failure`** category. TDD throughout.

## Acceptance criteria
1. A run records: `rounds`, `wall_time_s`, `tool_call_counts` (per tool name), `safety_cap_bound`,
   `env_health` (pre/post probe, nullable), `run_uid`, plus existing token usage — and can
   **complete naturally** (no forced truncation).
2. Existing v1 run artifacts (`reports/runs-*.jsonl`, `tests/test_committed_runs.py`,
   `tests/test_golden_conformance.py`) still load byte-faithfully via a v1-compat path.
3. The classifier is fc-v3: `environment_failure` is a first-class category; remains pure/total/versioned.
4. `pytest` green; `ruff` clean. New behavior is test-first (red→green).

## Scope / decisions (frozen — §18.1 + grill memory)

### A. Records (`records/trajectory.py`, `records/serialize.py`)
- `Trajectory.schema_version: Literal["1","2"] = "2"` + `Trajectory.v1_compat(mapping)` classmethod
  that hydrates a pre-revision artifact (no new fields → safe defaults; `stop_reason` left as-is).
  **No separate V2 type** — one `Trajectory`, version-tagged.
- New `Trajectory` fields (all defaulted so v1 loads): `rounds: int = 0`,
  `wall_time_s: float = 0.0`, `tool_call_counts: Mapping[str, int] = {}`,
  `safety_cap_bound: bool = False`, `env_health: EnvHealth | None = None`, `run_uid: str | None = None`.
- `stop_reason` literal **extended** with `completed_natural`, `safety_cap`, `env_unhealthy`
  (keep `completed`/`max_steps`/`parse_failure` for v1-compat). New runs emit
  `completed_natural` (model ended) / `safety_cap` (cap hit) / `env_unhealthy` (post-probe failed) /
  `parse_failure` (unchanged). Legacy values never emitted by the new runner but still parseable.
- **Cost stays DERIVED, not stored** (CLAUDE.md: keep records pure / pricing out of the runner):
  `Usage` keeps `prompt_tokens`/`completion_tokens`/`latency_s`; cost (`tokens×pricing`) is computed
  in the metrics layer from the pricing snapshot. (If the plan finds a strong reason to store it,
  it must be a derived/optional field that does not couple the runner to pricing.json — justify in the plan.)
- New `EnvHealth` value type (`records/`): `pre_healthy: bool`, `post_healthy: bool`,
  `pre_status: int | None`, `post_status: int | None`. Frozen, total. Model-action-INDEPENDENT (§18.5).
- `run_uid` format: `f"{condition_id}__{run_index:04d}"` (e.g. `deepseek:deepseek-v4-pro__0003`).

### B. Runner censoring (`runners/loop.py`)
- Replace the `for _ in range(max_steps)` truncation with: **run to natural completion**, bounded
  only by a **generous safety cap of 200 tool calls** (§18.1). Count cumulative **tool calls**;
  when the count reaches the cap, set `stop_reason="safety_cap"` + `safety_cap_bound=True`.
- Count `rounds` (model turns), accumulate per-tool `tool_call_counts`, measure `wall_time_s`.
- **Health probe via injected callback** (runner stays env-agnostic): optional
  `health_probe_fn: Callable[[], EnvHealth] | None`. When provided, call pre-run and post-run; if the
  post probe is unhealthy set `stop_reason="env_unhealthy"`; store the `EnvHealth`. Env-free tasks
  (F-set) pass no probe → `env_health=None`, behaves like a normal completion.
- Thread `run_uid` (built from `condition_id` + `run_index`).
- Keep the ADR-0008 effect-request fulfillment + parse-failure handling exactly as today.

### C. Replacement-trial loop (`runners/multi_run.py`, D34)
- Extend `run_task_k` (or a new `run_task_k_valid`) with `k_valid: int`, `validity_fn:
  Callable[[RunResult], bool] | None`, and `max_invalid_rate: float`. Loop: run trials; a trial is
  **invalid** if `stop_reason=="env_unhealthy"` or `validity_fn(result) is False`; on invalid, run a
  replacement immediately; track `attempt_index`. Stop at **exactly k valid** trials. If the
  running invalid-rate would exceed `max_invalid_rate` before k valid are obtained, return a
  result flagged **INCOMPLETE/VOID** (do NOT score over < k). Backward-compat: the existing
  `run_task_k(k=...)` path with no `validity_fn` treats every run as valid (k_valid == k) → identical behavior.

### D. fc-v3 (`reports/classify.py`)
- Add `environment_failure` as a first-class category (peer to harness/agent/task failures),
  **checked after parse/harness, before execution grading**, driven by the new `env_health` /
  `stop_reason=="env_unhealthy"` record fields. Subcategories: `pre_probe_failed` |
  `post_probe_failed` | `runner_flagged`. Keep the classifier **pure / total / versioned**
  (ADR-0013 discipline); bump fc-v2 → fc-v3; existing fc-v2 cases keep classifying identically.

### E. Serialization & compat (`records/serialize.py`)
- Round-trip every new field. Loading a v1 artifact (missing the fields / `schema_version` absent)
  routes through `v1_compat` and yields defaults; `test_committed_runs` / `test_golden_conformance`
  must stay green.

## Out of scope for 001
- Experiment types (`MetricDef`/`ExperimentSpec`/…) → item 002.
- Pricing→cost numbers in reports → item 002/007 (records only expose token inputs).
- Any live MSTR/docs probe wiring → items 005/006 (001 only adds the callback seam + EnvHealth type).

## Test plan (TDD, tests mirror src)
- `tests/records/test_trajectory.py` — new fields default; `schema_version` default "2"; `v1_compat`.
- `tests/records/test_serialize.py` — round-trip new fields; v1 artifact loads.
- `tests/runners/test_loop.py` — natural completion → `completed_natural`; 200-tool-call cap →
  `safety_cap` + `safety_cap_bound`; health_probe_fn pre/post; `env_unhealthy`; rounds/tool counts/run_uid.
- `tests/runners/test_multi_run.py` — replacement until k valid; VOID when invalid-rate exceeded; back-compat path.
- `tests/reports/test_classify.py` — `environment_failure` + 3 subcategories; fc-v2 cases unchanged; total/pure.
- Back-compat: `tests/test_committed_runs.py`, `tests/test_golden_conformance.py` stay green.
