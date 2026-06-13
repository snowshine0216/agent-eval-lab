# Code Review — Item 002: Experiment types + pre-registration plumbing

**Reviewer:** Claude Code (automated HIGH-effort gate)
**Date:** 2026-06-13
**Diff:** `autodev/agentic-v1-eval-foundation...feat/agentic-v1-002-experiment-types`
**Contract:** `002-experiment-types-spec.md` (§18.2/§18.3/§18.4/§18.10/§18.11)

---

## VERDICT: PASS-WITH-NITS

No blockers. One latent correctness bug (Nit-grade for this item but will bite item 007).
No coupling violations. All 76 new tests + 772 total tests green. ruff clean.

---

## Findings

### Blocker — ZERO

No blocking issues found.

---

### Latent Bug (must fix before item 007 consumes this API)

#### LB-1 — `condition_cost_usd` does not filter by `condition_id` (`pricing.py:64`)

**File:** `src/agent_eval_lab/experiments/pricing.py`, line 64–79

**Problem:** The function signature is
`condition_cost_usd(results, condition_id, snapshot) -> float`.
It calls `token_totals(results)` which sums tokens from **every run** in `results`
regardless of their `condition_id`. The `condition_id` parameter is used only to
look up the price point, not to filter the result set. The docstring says "all runs
*under* condition_id" but provides no guard.

**Consequence:** If a caller passes the full un-filtered experiment result list (which
item 007 — the report layer — plausibly will), costs for each condition will be
inflated by tokens from all other conditions. This is a silent correctness failure:
no exception, no warning, wrong number.

**Evidence:**
```python
# pricing.py token_totals call (line 74):
prompt_tokens, completion_tokens = token_totals(results)   # no filter
```

```python
# reliability.py token_totals (lines 45-47):
def token_totals(results):
    prompt = sum(run.trajectory.usage.prompt_tokens for run in results)
    completion = sum(run.trajectory.usage.completion_tokens for run in results)
    return prompt, completion
```

**Fix (two acceptable approaches):**

Option A — filter internally (self-defending API):
```python
def condition_cost_usd(
    results: Sequence[RunResult],
    condition_id: str,
    snapshot: PricingSnapshot,
) -> float:
    price = snapshot.prices[condition_id]
    filtered = [r for r in results if r.condition_id == condition_id]
    prompt_tokens, completion_tokens = token_totals(filtered)
    return (
        prompt_tokens * price.input_per_mtok
        + completion_tokens * price.output_per_mtok
    ) / 1_000_000
```

Option B — assert the invariant (fail-fast API, document the contract):
```python
def condition_cost_usd(
    results: Sequence[RunResult],
    condition_id: str,
    snapshot: PricingSnapshot,
) -> float:
    """Total cost in USD. CALLER MUST pre-filter results to condition_id only.
    Raises AssertionError if any result belongs to a different condition."""
    price = snapshot.prices[condition_id]
    assert all(r.condition_id == condition_id for r in results), (
        f"results contains runs from conditions other than {condition_id!r}"
    )
    ...
```

Option A is safer for item 007. The existing tests pass single-condition result
lists so they do not catch this bug.

---

### Nits (no correctness impact; fix opportunistically)

#### N-1 — `_run_freeze_spec` does not catch `json.JSONDecodeError` (`cli.py:612`)

**File:** `src/agent_eval_lab/cli.py`, line 612

**Problem:** The first `try/except` only catches `FileNotFoundError`. A malformed
input JSON causes `json.JSONDecodeError` (a `ValueError` subclass) to escape the
first block, bypass the second `try/except`, and propagate to the user as an
unhandled Python traceback instead of a clean `[FAIL]` diagnostic.

**Reproduction:**
```
echo '{bad json}' > /tmp/bad.json
eval-lab freeze-spec --spec /tmp/bad.json --out /tmp/out.json
# → JSONDecodeError traceback instead of "[FAIL] spec validation error: ..."
```

**Fix:** Add `json.JSONDecodeError` (or equivalently `ValueError`) to the first
`except` clause, or merge both `try` blocks:
```python
    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"[FAIL] spec file not found: {spec_path}", file=sys.stderr)
        return 1
    except ValueError as exc:          # catches JSONDecodeError
        print(f"[FAIL] spec validation error: {exc}", file=sys.stderr)
        return 1
```

#### N-2 — `canonical_json` docstring overstates the float handling (`spec_hash.py:45`)

**File:** `src/agent_eval_lab/experiments/spec_hash.py`, line 45–48

**Problem:** The docstring says "Float values are round-tripped through Python's
repr so 0.05 stays 0.05 (no format drift)" but the code does nothing special —
floats pass through `_to_plain` as-is and are serialized by `json.dumps` directly.
In practice `json.dumps` on CPython 3.1+ uses the same David Gay dtoa algorithm as
`repr()`, so the behaviour described is correct, but the mechanism is implicit and
the comment misleads maintainers into thinking an explicit `repr()` call exists.

**Severity:** Documentation only. The hash IS deterministic and platform-stable.

**Fix:** Replace the parenthetical with an accurate description:
```
Float values are serialized by json.dumps using Python's standard shortest
round-trip representation (IEEE 754 dtoa, same as repr(float) on CPython 3.1+),
which is deterministic and platform-stable.
```

#### N-3 — `_load_run_results_from_jsonl` in `hydrate.py` accesses `g["failure_reason"]` without `.get()` (`hydrate.py:55`)

**File:** `src/agent_eval_lab/experiments/hydrate.py`, line 55

**Problem:**
```python
grade=GradeResult(
    ...
    failure_reason=g["failure_reason"],   # KeyError if key absent
```

`grade_result_to_dict` always emits the key (even as `None`), so artifacts written
by this codebase are safe. However, a hand-crafted or externally-produced JSONL
artifact that omits `failure_reason` would raise an opaque `KeyError` instead of a
descriptive error message.

**Fix:**
```python
failure_reason=g.get("failure_reason"),
```

This matches the defensive pattern used throughout `serialize.py` and aligns with
`GradeResult.failure_reason` having a default of `None`.

#### N-4 — `run_uid=None` silently means "never matches" in hydration (`hydrate.py:70`)

**File:** `src/agent_eval_lab/experiments/hydrate.py`, line 70

**Observation:** `hydrate_run_record` matches on `run.trajectory.run_uid == ref.run_uid`.
`Trajectory.run_uid` is `str | None`. A v1-compat artifact (pre-§18.1) has
`run_uid=None`. If such an artifact ends up in `artifact_paths`, it will never match
any `ref.run_uid` (which should always be a string), and the hydration will correctly
raise `LookupError` ("No record found"). This is a benign outcome, but:

- A `ref.run_uid = None` would silently match ALL v1 artifacts — the first one would
  be taken and the SHA mismatch would catch it, but the error message would be
  confusing.

No fix strictly required (SHA check provides the backstop), but adding a guard
`assert ref.run_uid is not None` or enforcing `run_uid: str` (non-Optional) on
`ExperimentRunRef` would make the contract explicit.

---

## Detailed analysis by scrutiny area

### 1. `spec_hash` determinism (spec_hash.py)

**PASS.** Verified by execution:

- `canonical_json` uses `json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=True)` — key
  ordering is stable regardless of insertion order (confirmed `{"z":1,"a":2}` == `{"a":2,"z":1}`).
- `_to_plain` recursively projects dataclasses → dict, Mappings → dict, tuples → list; all fresh
  allocations (no aliasing from the original spec object). Mutation of `plain["spec_hash"] = ""`
  in `compute_spec_hash` does not affect the original frozen spec.
- Float encoding: Python's `json.dumps` uses dtoa (same as `repr()`) — deterministic across
  platforms on all CPython 3.1+. The spec-relevant values (0.05, 0.25, 1.74, etc.) round-trip
  perfectly.
- `compute_spec_hash` blanks `spec_hash` in a fresh plain dict before hashing — it correctly
  excludes the field. Two specs differing only in `spec_hash` hash identically (test
  `test_compute_spec_hash_excludes_spec_hash_field` verified).
- Idempotency: `freeze_spec(freeze_spec(draft)).spec_hash == freeze_spec(draft).spec_hash`
  confirmed both by test and by live execution.
- Semantic-collision risk: none beyond the normal SHA256 preimage resistance; different `k`,
  different `conditions`, different `spec_hash` all produce different hashes.

### 2. Pre-registration validation

**PASS.** `_validate_spec` enforces:

- `conditions` non-empty
- `metrics` non-empty
- Exactly one `primary=True` metric per non-composite domain (D38) — both 0-primary and 2-primary
  raise `ValueError` with a specific message
- Every `PlannedComparison.family_id` exists in `families` — dangling refs raise `ValueError`

All four paths are covered by distinct tests. The validation runs inside `freeze_spec`, so
no invalid spec can be frozen. `verify_spec_hash` re-validates the hash post-freeze.

Note: `PlannedComparison.condition_a/b` and `metric_name` are NOT cross-validated against
`conditions` and `metrics` respectively. This is out of scope for item 002 per the spec
("validation: exactly one primary metric per domain; every family_id in families;
conditions/metrics non-empty"). Flagged for item 007's awareness.

### 3. Hydration hard-fails (hydrate.py)

**PASS.** All three failure modes raise without swallowing:

- Zero matches → `LookupError` with artifact paths in message
- Duplicate `run_uid` → `LookupError` with count in message
- SHA256 mismatch → `ValueError` with expected/got hex in message

The canonical bytes are computed as `json.dumps(run_result_to_dict(run), sort_keys=True, ...)`.
This is stable across JSONL round-trips: confirmed by writing unsorted JSON, reading back, and
recomputing — identical SHA256. The `sort_keys=True` neutralizes any dict ordering variation
in `evidence`, `tool_call_counts`, `final_state`, etc.

One nit: `g["failure_reason"]` (N-3 above). No broad `except` clauses anywhere.

### 4. evaluator_config.py

**PASS.** The `[oracle.b_set]` nested table is correctly parsed via `data["oracle"]["b_set"]`
(matching TOML's actual parse tree). The fix in commit `b36daaf` is faithful to §18.4.
`readback` is typed as `str`. All required sections raise clear `ValueError` on absence.
Password is read verbatim with no logging. No secrets leak.

The `health_probe` function takes an injected `httpx.Client`, making it testable without
real network calls. `verify=False` is scoped only to the `check-env` fallback client in
`cli.py:675`, not to `health_probe` itself — appropriate for the self-signed cert case
(§18.5 "reachability/auth, not a trusted chain").

### 5. pricing.py

**PASS-WITH-NITS.** Math correct: `(prompt × input_per_mtok + completion × output_per_mtok) / 1_000_000`.
Verified by test `test_condition_cost_usd_correct_math`: 1M+1M tokens at 1.74+3.48 = 5.22 USD, matches.
`pricing_snapshot_hash` hashes raw file bytes — stable and order-independent.

The `condition_cost_usd` no-filtering issue is LB-1 above.

### 6. No coupling

**PASS.** Verified: `grep -rn "from agent_eval_lab.experiments" src/agent_eval_lab/records/ src/agent_eval_lab/runners/` returns no matches. `experiments/` imports from `records/` and `metrics/` only; the dependency flows correctly downward.

The `TYPE_CHECKING` guard for `RunResult` in `schema.py` correctly avoids a circular import at
runtime while still type-checking. `isinstance(record.run, RunResult)` works at runtime.

### 7. Silent failures / broad except / mutable defaults

**PASS.** No broad `except Exception` or bare `except` anywhere in the new package. No
mutable default arguments. All dataclasses are `frozen=True`. The `_to_plain` helper allocates
fresh dicts and lists — no shared mutable state.

The one escape-hatch for unhandled exceptions is the `json.JSONDecodeError` in `_run_freeze_spec`
(N-1 above), which produces a traceback rather than a clean `[FAIL]` message.

---

## Test coverage summary

| Module | Test file | Tests | Coverage assessment |
|---|---|---|---|
| schema.py | test_schema.py | 17 | Frozen checks, defaults, equality, all 8 types |
| spec_hash.py | test_spec_hash.py | 19 | Determinism, exclusion, idempotency, all 4 validation paths |
| evaluator_config.py | test_evaluator_config.py | 10 | Happy path, missing section, nested oracle, frozen |
| pricing.py | test_pricing.py | 9 | Load, hash stable, math verified, unknown condition KeyError |
| hydrate.py | test_hydrate.py | 6 | Zero/dupe/SHA-mismatch hard-fails, multi-file search |
| cli.py (new cmds) | test_cli_experiments.py | 15 | freeze-spec round-trip, idempotency, check-env all paths |

**Gap:** No test exercises `freeze-spec` on a malformed JSON file (N-1). All other acceptance
criteria from `002-experiment-types-spec.md` are covered.

---

## Summary

**VERDICT: PASS-WITH-NITS**

- **ZERO blockers.**
- **ONE latent bug (LB-1):** `condition_cost_usd` does not filter by `condition_id` internally.
  Harmless only if every caller pre-filters. Must fix before item 007 uses this API; otherwise
  multi-condition cost reports will silently overstate costs by summing all conditions.
- **THREE nits (N-1/N-2/N-3):** `JSONDecodeError` escape from `freeze-spec` (N-1, easy one-liner),
  docstring inaccuracy on float handling (N-2), and `.get()` for `failure_reason` (N-3).
- Core correctness areas — spec_hash determinism, idempotency, validation enforcement, hydration
  hard-fails, evaluator config parsing, no coupling — all **PASS** with no issues.
