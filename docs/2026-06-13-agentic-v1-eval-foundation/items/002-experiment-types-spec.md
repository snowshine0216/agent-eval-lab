# Item 002 — Experiment types + pre-registration plumbing

**Source:** spec §18.3 (net-new types, verbatim), §18.4 (`evaluator.toml`), §18.2 (frozen params),
§18.10 (`check-env`), §18.11 (pricing). §16 Package 1's "experiment types are net-new (D29)".
This is a **plan-grade spec** (the §18.3 dataclasses ARE the contract) — go straight to TDD impl.

## Why
`MetricDef`/`ExperimentSpec`/`ExperimentResult` do not exist in `src/` (D29). The M1/M2 report
layer (item 007) and the live arms (003–006) all consume them. Pre-registration immutability
(`spec_hash`) and the `evaluator.toml` loader are the backbone of the run.

## Acceptance criteria
1. `src/agent_eval_lab/experiments/schema.py` defines every §18.3 type, frozen, importable.
2. `eval-lab freeze-spec` computes a deterministic `spec_hash` (SHA256 over canonical JSON
   excluding `spec_hash`) and writes the frozen spec; re-freezing the same spec is idempotent.
3. `eval-lab check-env` runs the two §18.10 preflights (playwright-cli + MSTR health probe).
4. `evaluator.toml` loads into a typed config; pricing.json loads + hashes; per-condition cost derivable.
5. Content-verified `ExperimentRunRecord` hydration (SHA256 + exactly-one run_uid; hard-fail otherwise).
6. TDD throughout; `uv run pytest` green, `ruff` clean. No coupling of records/runner to experiments.

## New package: `src/agent_eval_lab/experiments/`

### `schema.py` — net-new types (§18.3, VERBATIM contract)
```python
from dataclasses import dataclass
from typing import Literal

Domain = Literal["F", "D", "B"]

@dataclass(frozen=True, kw_only=True)
class DomainWeight:
    domain: Domain
    weight: float

@dataclass(frozen=True, kw_only=True)
class ConditionDef:
    condition_id: str            # provider:model
    label: str                   # e.g. "deepseek-noskill", "deepseek-skill"
    skill_variant: Literal["none", "strategy_test_stripped"] = "none"
    system_prompt_hash: str | None = None   # SHA256 of injected system prompt at freeze time

@dataclass(frozen=True, kw_only=True)
class MetricDef:
    name: str
    domain: Domain | Literal["composite"]
    primary: bool                # exactly one per domain (D38)
    aggregation: Literal["pass_pow_k", "mean", "median", "point_estimate"]
    ci_method: Literal["cluster_bootstrap", "binomial_exact", "none"]
    validity_mask: bool
    censoring_policy: Literal["failure", "right_censored"]

@dataclass(frozen=True, kw_only=True)
class MultiplicityFamily:
    id: str
    description: str
    correction: Literal["holm"]
    alpha: float

@dataclass(frozen=True, kw_only=True)
class PlannedComparison:
    name: str
    family_id: str               # joins to MultiplicityFamily.id
    domain: Domain
    condition_a: str             # condition_id
    condition_b: str             # condition_id; effect = metric(b) − metric(a)
    metric_name: str

@dataclass(frozen=True, kw_only=True)
class ExperimentSpec:
    experiment_id: str
    k: int
    repeats: int
    safety_cap: int
    max_invalid_rate: float
    conditions: tuple[ConditionDef, ...]
    metrics: tuple[MetricDef, ...]
    macro_weights: tuple[DomainWeight, ...]
    families: tuple[MultiplicityFamily, ...]
    planned_comparisons: tuple[PlannedComparison, ...]
    dataset_snapshot_hash: str   # SHA256 over sorted canonical JSON of all task defs
    pricing_snapshot_hash: str   # SHA256 over evaluator-only/pricing.json
    spec_hash: str               # SHA256 of spec excluding this field; written by freeze-spec

@dataclass(frozen=True, kw_only=True)
class ExperimentResult:
    experiment_id: str
    spec_hash: str
    condition_id: str
    domain: Domain | Literal["composite"]
    metric_name: str
    estimate: float
    ci_lower: float | None
    ci_upper: float | None
    ci_method: str
    valid_run_count: int
    invalid_run_count: int
    void: bool

@dataclass(frozen=True, kw_only=True)
class ExperimentRunRef:
    run_uid: str
    artifact_sha256: str
    domain: Domain
    repeat_index: int
    attempt_index: int           # 0 = first attempt; increments on invalid replacement trials

@dataclass(frozen=True, kw_only=True)
class ExperimentRunRecord:
    ref: ExperimentRunRef
    run: "RunResult"             # canonical owner of task_id/condition_id/Trajectory/GradeResult
```

### `spec_hash.py` — pre-registration immutability (§18.2/D38)
- `canonical_json(obj) -> str`: deterministic JSON (sorted keys, no whitespace ambiguity) over a
  dataclass→dict projection. Used for `spec_hash`, `dataset_snapshot_hash`, `pricing_snapshot_hash`.
- `compute_spec_hash(spec: ExperimentSpec) -> str`: SHA256 over canonical JSON of the spec **with
  `spec_hash` excluded/blanked**.
- `freeze_spec(draft: ExperimentSpec) -> ExperimentSpec`: returns a new spec with `spec_hash` set;
  **idempotent** (freezing a frozen spec yields the same hash). Validation: exactly one `primary`
  metric per domain (D38); every `PlannedComparison.family_id` ∈ families; conditions/metrics non-empty.
- `verify_spec_hash(spec) -> bool`: recompute and compare (harness asserts at run start).

### `evaluator_config.py` — `evaluator.toml` loader (§18.4)
- Use `tomllib` (3.11 stdlib). Typed frozen dataclasses: `StoreConfig(path)`,
  `HealthProbeConfig(url, username, password)`, `SkillConfig(strategy_test_path)`,
  `RunnerConfig(safety_cap, k_valid, max_invalid_rate)`, `OracleBSetConfig(readback)`,
  `EvaluatorConfig(store, health_probe, skill, runner, oracle_b_set)`.
- `load_evaluator_config(path: Path) -> EvaluatorConfig`. Hard-fail with a clear error on a missing
  required section/key. The file is NOT in the candidate repo (D33) — loader takes an explicit path.

### `pricing.py` — pricing snapshot (§18.11)
- `PricePoint(input_per_mtok, output_per_mtok)`, `PricingSnapshot(snapshot_date, prices: Mapping[str, PricePoint])`.
- `load_pricing(path) -> PricingSnapshot`; `pricing_snapshot_hash(path) -> str` (SHA256 over the file bytes).
- `condition_cost_usd(usage_or_results, condition_id, snapshot) -> float` — reuse/relocate the
  tokens×price math (`metrics/cost.py` `TokenPrice`/`total_cost_usd`); experiments layer derives
  per-condition cost. Do NOT modify the runner; cost stays derived.

### `hydrate.py` — content-verified run hydration (§18.3)
- `hydrate_run_record(*, ref: ExperimentRunRef, artifact_paths: Sequence[Path]) -> ExperimentRunRecord`:
  read the given run-artifact files, select the **exactly one** record whose `run_uid == ref.run_uid`,
  compute SHA256 over that artifact's canonical bytes and assert `== ref.artifact_sha256`;
  **hard-fail** on missing / duplicate run_uid / SHA mismatch. Never silently pick one.

## CLI (`cli.py`) — two new subcommands
- `eval-lab freeze-spec --spec <draft.json> --out <frozen.json>`: load a draft ExperimentSpec
  (JSON), `freeze_spec`, write with `spec_hash`. Print the hash. Idempotent.
- `eval-lab check-env [--evaluator-config evaluator.toml]` (§18.10):
  1. `playwright-cli --version` → non-zero exit + diagnostic if absent.
  2. If `--evaluator-config` given: MSTR health probe (POST to `[health_probe] url`, 2XX/3XX = healthy).
  Exit 0 iff all checks pass; print a per-check report. (The probe is the §18.5 single-level check;
  reuse a shared `health_probe(url, user, pw) -> EnvHealth`-shaped result so item 006 can call it.)

## Tests (TDD, `tests/experiments/test_*.py`)
- `test_schema.py` — every type frozen, defaults, equality; `ExperimentRunRecord.run` is the canonical owner.
- `test_spec_hash.py` — canonical_json determinism (key order independence); spec_hash excludes itself;
  freeze idempotent; verify; validation rejects 0/2 primary-per-domain, dangling family_id, empty conditions.
- `test_evaluator_config.py` — load a fixture toml; missing-section hard-fail; password read verbatim.
- `test_pricing.py` — load pricing.json; hash stable; per-condition cost matches tokens×price.
- `test_hydrate.py` — exactly-one run_uid; SHA mismatch hard-fail; missing hard-fail; duplicate hard-fail.
- `test_cli.py` (extend) — `freeze-spec` writes a hash + is idempotent; `check-env` reports playwright/probe
  (mock the probe + a fake playwright-cli on PATH or via an injected runner; do NOT hit the real network in unit tests).

## Out of scope for 002
- The aggregation math (pass_pow_k/bootstrap/Holm) → item 007 consumes these types but the metric
  COMPUTATION lives in `metrics/` (extended in 007). 002 defines `MetricDef`/`ExperimentResult` shapes only.
- Building the actual M1 ExperimentSpec instance → item 007 (it needs the real condition roster + datasets).
