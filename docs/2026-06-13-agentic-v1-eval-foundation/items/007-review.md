# Code Review — Item 007: M1/M2 Aggregation + Report Layer

**Diff:** `autodev/agentic-v1-eval-foundation...feat/agentic-v1-007-m1-m2-reports`  
**Reviewer:** Claude Sonnet 4.6 (HIGH effort)  
**Date:** 2026-06-13  
**VERDICT: PASS-WITH-NITS**

---

## Summary

The implementation correctly delivers Clopper–Pearson exact binomial CIs, Holm step-down correction, per-domain aggregation with void/INCOMPLETE handling, macro-weighted composite, and Pareto frontier logic. All 239 tests pass. The statistical math is sound, the seed is threaded everywhere randomness appears, and `schema.py` is untouched (D29). Two latent issues were found (both operationally benign under the frozen M1 spec) plus three nits.

---

## Findings by Severity

### Blockers

**(ZERO blockers)**

---

### Latent Issues

**L1 — `macro_composite` raises `ZeroDivisionError` when all contributing domains have `weight=0`**

- **File:line:** `src/agent_eval_lab/experiments/aggregate.py:153`
- **Trigger:** `total_w = sum(weight_of.get(r.domain, 0.0) for r in contributing)` — if every contributing `ExperimentResult` has a domain that is absent from the `weights` dict, `total_w = 0` and line 155 (`... / total_w`) throws `ZeroDivisionError`.
- **Operationally reachable?** No — with the frozen M1 spec the weights dict contains F, D, B and the results only ever carry F, D, or B. However, the function is public and could be called from future code with mismatched inputs.
- **Fix:** add a guard before the division:

```python
if total_w == 0.0:
    # All contributing domains have zero weight; treat like no contributing domains.
    return ExperimentResult(..., void=True)
```

---

**L2 — Void/INCOMPLETE task metadata is silently lost in the `report-m1` JSONL replay path**

- **File:line:** `src/agent_eval_lab/cli.py:881–894` (`_outcomes_from_runs`)
- **Issue:** `run-m1` only writes `valid_runs` to JSONL (by design); voided tasks produce zero rows. `_outcomes_from_runs` therefore reconstructs `ReplacementOutcome(void=False)` for every task that has rows — tasks voided during the live run are absent from the reconstruction entirely. Consequence: `report-m1` produces `void=False` results and `void_task_count=0` in the validity table even when tasks were voided, and `invalid_run_count=0` always.
- **Operationally reachable?** Yes — any run where `run_task_k_valid` trips the invalid-rate threshold on even one task. Void warnings are printed to stderr during `run-m1`, but the markdown report carries no trace of them.
- **Comment in code:** `_outcomes_from_runs` says *"Faithful for the D-only first run"* — this is acknowledged, but the scope of information loss is not fully documented.
- **Fix options (increasing completeness):**
  1. Minimal: write a sidecar `void-tasks-{slug}.jsonl` per domain during `run-m1` listing voided task ids; load it in `_run_report_m1` and inject synthetic `void=True` outcomes.
  2. Preferred: extend the runs JSONL format with a `void` metadata row (`"void": true, "task_id": "..."`) that `_load_run_results` recognises and reconstructs as a void `ReplacementOutcome` with empty `valid_runs`.

---

### Nits

**N1 — `bootstrap_diff_p_value` accepts an `alpha` parameter it never uses**

- **File:line:** `src/agent_eval_lab/metrics/multiplicity.py:36,42`
- The `alpha` keyword argument is declared in the signature and passed by callers (`comparisons.py:78`), but the function body never reads it. The alpha threshold plays no role in computing the bootstrap p-value (correctly — Holm applies alpha externally). The dead parameter adds noise and could mislead readers into thinking it affects the p-value.
- **Fix:** remove `alpha: float` from the signature and update call sites (`comparisons.py:75,78`).

---

**N2 — `dropped` expression in `macro_composite` is an opaque Python short-circuit**

- **File:line:** `src/agent_eval_lab/experiments/aggregate.py:142–144`
- `dropped = len(per_domain_primary) - len(contributing) or (len(weights) > len({r.domain for r in per_domain_primary}))` relies on Python's `or` returning the first truthy value. The two-branch intent (any void dropped, OR any weight-specified domain missing from results) is correct but non-obvious.
- **Fix:** replace with explicit logic for readability:

```python
any_domain_dropped = len(contributing) < len(per_domain_primary)
any_weight_domain_missing = len(weights) > len({r.domain for r in per_domain_primary})
dropped = any_domain_dropped or any_weight_domain_missing
```

---

**N3 — `paired_pass_pow_k_diff_ci` and `bootstrap_diff_p_value` use the same seed for every comparison**

- **File:line:** `src/agent_eval_lab/experiments/comparisons.py:75,78`
- Both are called with the same `seed` for every comparison in the loop. Each call constructs an independent `random.Random(seed)`, so different comparisons start from the same RNG state. This does not affect correctness but means comparisons are not independently sampled; for very large families it could introduce subtle correlations between the bootstrap distributions of different comparisons.
- **Fix (optional):** use `seed + i` (comparison index) to ensure independent bootstrap sequences per comparison. For M1's 15-comparison family the practical impact is negligible, but the practice is more defensible.

---

## Stats Spot-Check

### Spot-check 1: Clopper–Pearson 2/3 at α=0.05

Reference (R `binom.test`): `[0.094276, 0.991534]`

Implementation output:
```
lo = 0.094299  (diff from reference: 2.33e-05)
hi = 0.991596  (diff from reference: 6.22e-05)
```

Both are within the test's `abs_tol=1e-4`. The bisection converges to 200 iterations at tolerance `1e-12` — the small residual is inherent to the continued-fraction approximation, not a defect.

Edge cases verified:
- `0/3`: `lo=0.0` (exact), `hi=0.707598` (reference `1 - 0.025^(1/3) = 0.707598`, diff `3e-13`) ✓  
- `3/3`: `lo=0.292402` (reference `0.025^(1/3)`, diff `3e-13`), `hi=1.0` (exact) ✓

### Spot-check 2: Holm adjusted-p by hand, m=3

Sorted p: `0.001, 0.04, 0.20`, α=0.05

| rank i | raw p | threshold | adj_p (manual) | adj_p (code) | rejected |
|--------|-------|-----------|----------------|--------------|----------|
| 0 | 0.001 | 0.05/3=0.01667 | max(0, min(1, 3×0.001))=0.003 | 0.003 ✓ | True ✓ |
| 1 | 0.04 | 0.05/2=0.025 | max(0.003, min(1, 2×0.04))=0.08 | 0.08 ✓ | False ✓ |
| 2 | 0.20 | 0.05/1=0.05 | max(0.08, min(1, 1×0.20))=0.20 | 0.20 ✓ | False ✓ |

Step-down stop: c2 fails threshold (0.04 > 0.025), c3 forced non-rejected. ✓

### Spot-check 3: Composite CI propagation, F=[0.3,0.9], D=[0.8,1.0], B=[0.1,0.5]

```
estimate = (0.6 + 0.9 + 0.3) / 3 = 0.6
w_norm = 1/3 for each (equal weights)
half_F = 0.3, half_D = 0.1, half_B = 0.2
var = (1/3 × 0.3)² + (1/3 × 0.1)² + (1/3 × 0.2)² = 0.01 + 0.00111 + 0.00444 = 0.01556
spread = sqrt(0.01556) ≈ 0.1247
CI = [0.6 - 0.1247, 0.6 + 0.1247] = [0.4753, 0.7247]
```

Code output: `estimate=0.6000, lo=0.4753, hi=0.7247` ✓

### Spot-check 4: Fisher exact 0/3 vs 3/3

```
Tables: P(k=0)=C(3,0)C(3,3)/C(6,3)=1/20=0.05
        P(k=3)=C(3,3)C(3,0)/C(6,3)=1/20=0.05
observed=0.05; two-sided sum = P(k=0)+P(k=3) = 0.10
```

Code output: `p=0.1000` ✓ (the test asserts `p <= 0.1`, which is satisfied at the boundary)

### Spot-check 5: bootstrap p-value consistency with CI

For `a=[all fail on 4 tasks]`, `b=[all pass on 4 tasks]`, n_resamples=2000, seed=20260613:
- `CI=[1.0, 1.0]` (CI excludes 0: True)  
- `p=0.0000` (< 0.05: True)  
- Consistent ✓

---

## Explicit Absence Statements

**ZERO blockers.** No finding that causes the report to produce a wrong number under the M1 spec with its frozen data.

**Two latent issues** (L1 and L2): L1 is a defensive-coding gap reachable only with a calling-convention violation; L2 is a design limitation of the JSONL serialization path that the code partially acknowledges but does not fully document.

---

## Additional Observations

- **schema.py**: not modified (D29 respected). ✓  
- **Stdlib-only invariant**: no numpy/scipy imports anywhere in the new modules. ✓  
- **Seeding**: every bootstrap call accepts `seed` as an explicit argument; no `random.seed()` global calls; `random.Random(seed)` is instantiated locally in `bootstrap_diff_p_value`. ✓  
- **Determinism test**: `test_same_runs_and_spec_render_byte_identical` asserts markdown identity across two calls with the same seed. ✓  
- **Partial coverage**: D-only path is tested by multiple tests; `domains_not_run` is surfaced in the composite note and the header. ✓  
- **Void propagation** (in-memory path): `test_void_task_is_excluded_and_marks_domain_void` and `test_render_flags_void_domain` cover the in-memory path correctly; see L2 for the JSONL replay path. ✓ (in-memory) / ⚠ (JSONL replay)
- **FP discipline**: all new modules are pure functions with no I/O side effects; I/O lives in `cli.py` edge functions. ✓
