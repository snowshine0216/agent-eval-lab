# M1/M2 Aggregation + Report Layer Implementation Plan (item 007)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn recorded runs into the owner's deliverable — per-domain scores (F/D/B) each with the CI method its design demands, a pre-registered macro-weighted composite, Holm-corrected planned comparisons, per-domain Pareto frontiers, an fc-v3 failure taxonomy, and an explicit validity/void/INCOMPLETE mask — emitted as `ExperimentResult`s and a markdown report, with an M1 orchestration entrypoint that runs conditions × domains over the existing runners.

**Architecture:** Pure metrics layer + pure report builder/renderer + thin I/O edges, mirroring the existing `reports/final.py` (build → render, no I/O) and `metrics/reliability.py` (seeded bootstrap, RNG as an argument) idioms. Three new pure metrics modules (`metrics/binomial.py` Clopper–Pearson, `metrics/multiplicity.py` Holm + Δpass^k p-value, `metrics/pareto.py` frontier), one new pure aggregation module (`experiments/aggregate.py` → `ExperimentResult`s + composite), an M1 spec builder (`experiments/m1_spec.py`) + a frozen JSON the run reads, an M1 run orchestrator (`experiments/m1_run.py`, edge — calls `run_task_k_valid`), a new report builder/renderer (`reports/m1.py`), and two CLI subcommands (`run-m1`, `report-m1`). **The actual multi-model run is downstream and OUT OF SCOPE** — this item ships the orchestration entrypoint plus a unit test with a stubbed `run_task_k_valid`. **The report layer must render PARTIAL coverage gracefully** (D present, F/B absent) because the first real run is D-only.

**Tech Stack:** Python 3.11 (frozen dataclasses; pure core / I/O edge split; stdlib only — `random`, `math`, `json`, `hashlib`; NO numpy/scipy — the entire `src/` tree is stdlib-only and that invariant is preserved). pytest. New code under `src/agent_eval_lab/{metrics,experiments,reports}/` + `cli.py`; tests under `tests/{metrics,experiments,reports}/`. Synthetic `RunResult`s for every unit test (no live models, no network).

---

## Design decisions (recorded before tasks — these are the answers to the spec's open questions)

### DEC-1 — F-domain CI is Clopper–Pearson exact binomial, NOT cluster bootstrap (D38, §18.2)

F has exactly 3 tasks. A cluster bootstrap over 3 clusters is near-degenerate (the percentile interval takes ≤4 distinct values), and the spec explicitly forbids it (D38: "cluster bootstrap is inapplicable; F-score reports a point estimate with a binomial/exact CI"). The pass^k estimand on F is "x of n=3 tasks reliable" — a binomial proportion. The **exact** (Clopper–Pearson) interval is the defensible choice for tiny n: it never produces the nonsensical degenerate-width interval a normal approximation gives at n=3, and it has guaranteed ≥(1−α) coverage.

**Implementation (stdlib, no scipy):** Clopper–Pearson bounds are quantiles of Beta distributions, which equal roots of the regularized incomplete beta function `I_x(a,b)`. We compute `I_x(a,b)` with the standard continued-fraction `betacf` (Numerical Recipes `betai`) — pure Python, deterministic — and invert it by **bisection** on `x ∈ [0,1]` to a fixed tolerance (1e-10). For x successes of n trials at two-sided level α:
- `lower = 0.0` if x == 0, else the x s.t. `I_x(x_succ, n−x_succ+1) = α/2`
- `upper = 1.0` if x == n, else the x s.t. `I_x(x_succ+1, n−x_succ) = 1−α/2`

This is ~40 lines of pure stdlib, fully deterministic (no RNG → no seed needed), and unit-testable against hand-computed reference values (e.g. 2/3 at α=0.05 → [0.0943, 0.9915]).

### DEC-2 — Holm uses a bootstrap two-sided p-value for Δpass^k (defensible + reuses existing machinery)

Each `PlannedComparison` tests Δ = metric(b) − metric(a). For D/B the metric is pass^k with a cluster-bootstrap CI already implemented (`paired_pass_pow_k_diff_ci`). The simplest *defensible* per-comparison p-value that is consistent with the CI we already report is a **bootstrap two-sided p-value derived from the same paired cluster-bootstrap distribution** — we do not introduce a second, possibly-contradictory inferential method (a normal-approx proportion test could declare significance where the reported bootstrap CI includes 0). Concretely, from the sorted bootstrap Δ samples we compute the one-sided tail proportion on the side of 0 the point estimate is NOT on, and double it (clamped to ≤1.0):

```
p_one = (#samples with sign opposite to point, plus half the #samples == 0) / n_resamples
p_two = min(1.0, 2 * p_one)
```

This is the percentile-bootstrap analogue of a two-sided test and is **monotone-consistent with the percentile CI** (CI excludes 0 ⇔ p_two < α before correction). For F-domain comparisons (if any are planned), the p-value comes from a **Fisher exact test** on the 2×(reliable/not) table (pure stdlib via `math.comb`) — because F has no bootstrap. The spec's frozen M1 comparison set is "pairwise model comparisons on the D-domain primary metric" (item prompt §item-5), so the bootstrap path is the one M1 actually exercises; the Fisher path exists so a future F-domain family does not crash.

Then **Holm step-down** within each `MultiplicityFamily`: sort the family's comparisons by ascending p, reject `p_(i) ≤ alpha / (m − i)` (i = 0-based) and **stop at the first non-rejection** (step-down: once one fails, all larger p's are retained). Output a per-comparison `holm_adjusted_p = max over j≤i of min(1, (m−j) * p_(j))` (the standard monotone adjusted-p form) plus a boolean `rejected`. No post-hoc anything; the family alpha comes from the frozen spec.

### DEC-3 — Macro composite = equal-weighted mean of per-domain PRIMARY-metric point estimates; CI is bootstrap-over-domains, reported with an explicit small-K caveat

Per D23/§18.2 the composite is a **weighted mean of per-domain scores**, weighted **by domain** (default equal F=D=B=1.0), explicitly **NOT** a raw pool over the 15+3+n tasks. The point estimate is unambiguous:

```
composite = Σ_d (weight_d * primary_estimate_d) / Σ_d weight_d   over domains present & non-void
```

For the composite **CI method** the spec (§18.2) lists per-domain CI methods but leaves the composite CI to "decide". Decision: **bootstrap over domains is meaningless at K=3 domains** (same degeneracy that bans the F cluster bootstrap). So the composite reports the **point estimate plus a transparent analytic note** and a CI computed as the **weighted combination of the per-domain interval half-widths under independence** — i.e. `ci = composite ± sqrt(Σ (w_d_norm * half_d)^2)` where `half_d = (ci_upper_d − ci_lower_d)/2` and `w_d_norm` is the normalized weight — clamped to [0,1]. This is a conservative, deterministic propagation that (a) never claims a tighter interval than its components, (b) requires no extra RNG, (c) widens honestly when a domain is missing or void (that domain is dropped from the mean and the note records it). The renderer states the method verbatim so the composite is "transparent and never a docs-QA ranking in disguise" (D23). **This is recorded as the frozen `composite_ci` method string `"weighted_halfwidth_propagation"` in the report** — it does not need to be in `ExperimentSpec.metrics` (the composite is a derived metric, domain="composite").

> If a reviewer prefers "estimate + note, no CI", the propagation is trivially disabled by emitting `ci_lower=ci_upper=None` and the renderer already handles None (mirrors `final.py`). Keep the propagation; it is strictly more informative and still honest.

### DEC-4 — p-value/CI seeds are threaded explicitly; the composite and Holm reuse the SAME bootstrap draws as the per-domain CIs

`reliability.py` seeds via `random.Random(seed)` passed as an argument (never global). Every new bootstrap path follows that: `seed` is a required keyword argument on every function that draws, and the **same `(seed, n_resamples)` produces byte-identical reports** for the same runs+spec (a regression test asserts this). The Holm p-values are derived from a paired bootstrap that takes the same seed family — so the CI and its p-value cannot disagree.

### DEC-5 — INCOMPLETE/void is first-class in every `ExperimentResult` and never silently scored

A `(condition, domain)` cell is built from `ReplacementOutcome`s (one per task). Aggregation rules, in priority order:
1. If the metric has `validity_mask=True`, env-invalid trials are already excluded by `run_task_k_valid` (they never reach the valid_runs set). The aggregator scores **only the valid runs**.
2. A task whose outcome is `void=True` (D28/D34: max-invalid-rate tripped before k valid) is **INCOMPLETE** — excluded from pass^k entirely (never scored over <k). It is counted in `invalid_run_count` accounting and listed by id.
3. If **any** task in the domain is void, the domain-level `ExperimentResult.void = True` and `estimate`/CI still report over the complete tasks BUT the renderer flags the domain VOID and lists the incomplete task ids (we do not fabricate a clean number). *(Rationale: the spec voids a CONDITION when its invalid-rate trips; at the domain-aggregate level we surface void rather than swallow it.)*
4. `safety_cap` runs are **failures** for pass^k success metrics (D35) — `_is_pass(run)` reads `run.grade.passed`, and a safety-capped run has `passed=False`, so this is automatic; the plan adds an assertion test. For **efficiency** metrics (rounds/tokens/wall-time) a safety-capped run is **right-censored** (D35) — the efficiency aggregate notes the censored count and never treats the capped value as the true value.

### DEC-6 — Efficiency metrics (rounds/tokens/cost/wall-time) are descriptive medians over valid runs, with censored-count annotation

Pareto needs success vs each of cost / rounds / tokens. Cost reuses `experiments/pricing.py::condition_cost_usd`. Rounds = `trajectory.rounds`; tokens = `token_totals`; wall-time = `trajectory.wall_time_s`. These are summarized as **medians over valid runs** (robust to the heavy right tail of agentic runs) and each carries `n_censored` = count of valid runs with `trajectory.safety_cap_bound=True`. The renderer prints "median (n censored=X; ≥ values are lower bounds)". No CI on efficiency (descriptive, censored) — `ci_method="none"`.

### DEC-7 — Partial coverage: a domain with zero recorded runs renders "not yet run", never an error

The M1 run produces one runs-JSONL per (condition, domain) that actually ran. The report builder receives a map of `{(condition_id, domain): [RunResult,...]}` (empty/absent for domains not run). A `(condition, domain)` with no runs contributes **no `ExperimentResult`** and renders as `not yet run` in the per-domain table. The composite is computed **over present, non-void domains only** and the renderer states which domains contributed. This is the D-only first-run path and has a dedicated test (Task 13).

---

## File structure (what each new file owns)

- `src/agent_eval_lab/metrics/binomial.py` — pure Clopper–Pearson exact binomial CI (DEC-1) + Fisher exact two-sided p (DEC-2 F-path). Stdlib only.
- `src/agent_eval_lab/metrics/multiplicity.py` — pure Holm step-down (DEC-2) + the bootstrap two-sided Δpass^k p-value. Imports `paired_pass_pow_k_diff_ci`.
- `src/agent_eval_lab/metrics/pareto.py` — pure Pareto frontier over `(condition, success, cost_or_rounds_or_tokens)` points (DEC-6).
- `src/agent_eval_lab/experiments/aggregate.py` — pure: `ReplacementOutcome`s + spec → `tuple[ExperimentResult, ...]` (per-domain per-metric) + the composite `ExperimentResult` (DEC-3, DEC-5, DEC-6). The single place that knows the validity/void/censoring rules.
- `src/agent_eval_lab/experiments/m1_spec.py` — pure builder assembling the real M1 `ExperimentSpec` (roster, metrics, comparisons, families, equal weights) (item §item-5).
- `src/agent_eval_lab/experiments/m1_run.py` — EDGE: `run_m1(...)` orchestrates conditions × domains over `run_task_k_valid` (D path via `run_dset`; F/B absent-tolerant). Stub-tested.
- `src/agent_eval_lab/reports/m1.py` — pure build + render of the M1 markdown report (per-domain tables, composite, Pareto, fc-v3 taxonomy, validity mask, provenance). Reuses `classify.py`, `pricing.py`, the `final.py` rendering idioms.
- `src/agent_eval_lab/cli.py` — add `run-m1` and `report-m1` subcommands (thin edges).
- `examples/experiments/m1-agentic-v1.draft.json` — the draft M1 spec the builder emits (committed, candidate-visible; freeze it with `eval-lab freeze-spec`).

---

## Task 1: Clopper–Pearson exact binomial CI (F-domain, DEC-1)

**Files:**
- Create: `src/agent_eval_lab/metrics/binomial.py`
- Test: `tests/metrics/test_binomial.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/metrics/test_binomial.py
import math

from agent_eval_lab.metrics.binomial import clopper_pearson_ci, fisher_exact_two_sided


def test_clopper_pearson_2_of_3_reference():
    # Reference (R binom.test / scipy): 2/3 at 95% two-sided -> [0.0943, 0.9915].
    ci = clopper_pearson_ci(successes=2, n=3, alpha=0.05)
    assert ci.point == 2 / 3
    assert math.isclose(ci.lo, 0.094276, abs_tol=1e-4)
    assert math.isclose(ci.hi, 0.991534, abs_tol=1e-4)


def test_clopper_pearson_all_success_upper_is_one():
    ci = clopper_pearson_ci(successes=3, n=3, alpha=0.05)
    assert ci.point == 1.0
    assert ci.hi == 1.0
    # lower bound for 3/3 at 95% two-sided is 0.2924 (1 - 0.025**(1/3))
    assert math.isclose(ci.lo, 0.292376, abs_tol=1e-4)


def test_clopper_pearson_zero_success_lower_is_zero():
    ci = clopper_pearson_ci(successes=0, n=3, alpha=0.05)
    assert ci.point == 0.0
    assert ci.lo == 0.0
    assert math.isclose(ci.hi, 0.707624, abs_tol=1e-4)


def test_clopper_pearson_rejects_bad_inputs():
    import pytest

    with pytest.raises(ValueError):
        clopper_pearson_ci(successes=4, n=3, alpha=0.05)
    with pytest.raises(ValueError):
        clopper_pearson_ci(successes=0, n=0, alpha=0.05)


def test_fisher_exact_two_sided_clear_separation():
    # a: 0/3 reliable, b: 3/3 reliable -> small p (clear separation).
    p = fisher_exact_two_sided(a_success=0, a_n=3, b_success=3, b_n=3)
    assert 0.0 < p <= 0.1


def test_fisher_exact_two_sided_no_difference_is_one():
    p = fisher_exact_two_sided(a_success=2, a_n=3, b_success=2, b_n=3)
    assert math.isclose(p, 1.0, abs_tol=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/metrics/test_binomial.py -v`
Expected: FAIL with `ModuleNotFoundError: agent_eval_lab.metrics.binomial`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/metrics/binomial.py
"""Pure exact-binomial inference for the F-domain (3 tasks; D38).

Cluster bootstrap is inapplicable at n=3 (near-degenerate); the F-score is a
point estimate with a Clopper-Pearson EXACT binomial CI. Fisher's exact test
supplies an F-domain comparison p-value. Stdlib only (no scipy): the regularized
incomplete beta I_x(a,b) is computed by the Numerical-Recipes continued fraction
and inverted by bisection. Deterministic (no RNG -> no seed).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class BinomialCI:
    point: float
    lo: float
    hi: float
    alpha: float
    successes: int
    n: int


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Numerical Recipes)."""
    max_iter = 200
    eps = 3.0e-12
    fpmin = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """I_x(a, b) in [0, 1]. Pure stdlib."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(ln_beta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _beta_quantile(p: float, a: float, b: float) -> float:
    """Invert I_x(a,b)=p by bisection on x in [0,1] (monotone in x)."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if regularized_incomplete_beta(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1.0e-12:
            break
    return (lo + hi) / 2.0


def clopper_pearson_ci(*, successes: int, n: int, alpha: float) -> BinomialCI:
    if n <= 0:
        raise ValueError(f"n must be positive; got {n}")
    if not (0 <= successes <= n):
        raise ValueError(f"successes {successes} out of range [0, {n}]")
    lo = 0.0 if successes == 0 else _beta_quantile(alpha / 2.0, successes, n - successes + 1)
    hi = 1.0 if successes == n else _beta_quantile(1.0 - alpha / 2.0, successes + 1, n - successes)
    return BinomialCI(
        point=successes / n, lo=lo, hi=hi, alpha=alpha, successes=successes, n=n
    )


def _hypergeom_pmf(k: int, a_n: int, b_n: int, total_success: int) -> float:
    """P(a-group has k successes | margins fixed) — Fisher's null distribution."""
    n = a_n + b_n
    return (
        math.comb(a_n, k)
        * math.comb(b_n, total_success - k)
        / math.comb(n, total_success)
    )


def fisher_exact_two_sided(*, a_success: int, a_n: int, b_success: int, b_n: int) -> float:
    """Two-sided Fisher exact p over the 2x2 reliable/not table (F-domain path)."""
    total_success = a_success + b_success
    observed = _hypergeom_pmf(a_success, a_n, b_n, total_success)
    k_min = max(0, total_success - b_n)
    k_max = min(a_n, total_success)
    # Two-sided: sum probabilities of tables no more likely than the observed one.
    p = sum(
        prob
        for k in range(k_min, k_max + 1)
        if (prob := _hypergeom_pmf(k, a_n, b_n, total_success)) <= observed + 1e-12
    )
    return min(1.0, p)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/metrics/test_binomial.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/metrics/binomial.py tests/metrics/test_binomial.py
git commit -m "feat(metrics): Clopper-Pearson exact binomial CI + Fisher exact p (F-domain, D38)"
```

---

## Task 2: Holm step-down + bootstrap Δpass^k p-value (DEC-2)

**Files:**
- Create: `src/agent_eval_lab/metrics/multiplicity.py`
- Test: `tests/metrics/test_multiplicity.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/metrics/test_multiplicity.py
import math

from agent_eval_lab.metrics.multiplicity import (
    PValue,
    bootstrap_diff_p_value,
    holm_step_down,
)
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn


def _run(task_id: str, condition_id: str, passed: bool) -> RunResult:
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0,
        stop_reason="completed_natural",
    )
    return RunResult(
        task_id=task_id,
        condition_id=condition_id,
        run_index=0,
        trajectory=traj,
        grade=GradeResult(
            grader_id="g", passed=passed, score=1.0 if passed else 0.0, evidence={}
        ),
    )


def test_holm_step_down_orders_and_stops_at_first_non_reject():
    # Three p-values at alpha=0.05, m=3 -> thresholds 0.0167, 0.025, 0.05.
    ps = (
        PValue(name="c1", p=0.001),
        PValue(name="c2", p=0.04),
        PValue(name="c3", p=0.20),
    )
    decisions = holm_step_down(ps, alpha=0.05)
    by_name = {d.name: d for d in decisions}
    assert by_name["c1"].rejected is True   # 0.001 <= 0.0167
    assert by_name["c2"].rejected is False  # 0.04 > 0.025 -> stop
    assert by_name["c3"].rejected is False  # step-down: retained after c2 fails
    # Adjusted p is monotone non-decreasing in the sorted order.
    assert by_name["c1"].adjusted_p <= by_name["c2"].adjusted_p <= by_name["c3"].adjusted_p


def test_holm_adjusted_p_is_min_one_times_rank():
    ps = (PValue(name="a", p=0.02), PValue(name="b", p=0.03))
    decisions = {d.name: d for d in holm_step_down(ps, alpha=0.05)}
    # m=2: a is smallest -> 2*0.02=0.04; b -> max(0.04, 1*0.03)=0.04 (enforced monotone)
    assert math.isclose(decisions["a"].adjusted_p, 0.04, abs_tol=1e-9)
    assert math.isclose(decisions["b"].adjusted_p, 0.04, abs_tol=1e-9)


def test_bootstrap_diff_p_consistent_with_clear_separation():
    # a fails all 4 tasks, b passes all 4 -> Δ=+1.0, p should be small.
    tasks = ["t1", "t2", "t3", "t4"]
    a = [_run(t, "a", passed=False) for t in tasks]
    b = [_run(t, "b", passed=True) for t in tasks]
    p = bootstrap_diff_p_value(a, b, n_resamples=2000, seed=20260613, alpha=0.05)
    assert p < 0.05


def test_bootstrap_diff_p_no_effect_is_large():
    tasks = ["t1", "t2", "t3", "t4"]
    a = [_run(t, "a", passed=True) for t in tasks]
    b = [_run(t, "b", passed=True) for t in tasks]
    p = bootstrap_diff_p_value(a, b, n_resamples=2000, seed=20260613, alpha=0.05)
    assert math.isclose(p, 1.0, abs_tol=1e-9)


def test_bootstrap_diff_p_is_deterministic():
    tasks = ["t1", "t2", "t3"]
    a = [_run(t, "a", passed=(i == 0)) for i, t in enumerate(tasks)]
    b = [_run(t, "b", passed=True) for t in tasks]
    p1 = bootstrap_diff_p_value(a, b, n_resamples=500, seed=7, alpha=0.05)
    p2 = bootstrap_diff_p_value(a, b, n_resamples=500, seed=7, alpha=0.05)
    assert p1 == p2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/metrics/test_multiplicity.py -v`
Expected: FAIL with `ModuleNotFoundError: agent_eval_lab.metrics.multiplicity`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/metrics/multiplicity.py
"""Holm step-down family correction + a bootstrap two-sided Delta pass^k p-value.

The p-value is the percentile-bootstrap analogue of a two-sided test on
Delta = pass^k(b) - pass^k(a), derived from the SAME paired cluster-bootstrap
draws reliability.py uses for the CI, so the p-value and the reported CI are
monotone-consistent (CI excludes 0 <=> p < alpha pre-correction). Seeded; no
global RNG. Stdlib only.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from agent_eval_lab.metrics.reliability import task_reliability
from agent_eval_lab.records.grade import RunResult


@dataclass(frozen=True, kw_only=True)
class PValue:
    name: str
    p: float


@dataclass(frozen=True, kw_only=True)
class HolmDecision:
    name: str
    p: float
    adjusted_p: float
    rejected: bool
    rank: int  # 0-based ascending


def bootstrap_diff_p_value(
    results_a: Sequence[RunResult],
    results_b: Sequence[RunResult],
    *,
    n_resamples: int,
    seed: int,
    alpha: float,
) -> float:
    """Two-sided percentile-bootstrap p for Delta = pass^k(b) - pass^k(a), PAIRED
    by task. Mirrors paired_pass_pow_k_diff_ci's resampling exactly (one task-id
    multiset applied to both arms) so p and CI cannot disagree."""
    rel_a = task_reliability(results_a)
    rel_b = task_reliability(results_b)
    if set(rel_a) != set(rel_b):
        raise ValueError(
            "paired p-value requires identical task-id universe; "
            f"got {sorted(rel_a)} vs {sorted(rel_b)}"
        )
    ids = list(rel_a)
    n = len(ids)
    rng = random.Random(seed)
    point = (sum(rel_b.values()) - sum(rel_a.values())) / n
    n_opposite = 0
    n_zero = 0
    for _ in range(n_resamples):
        drawn = [ids[rng.randrange(n)] for _ in range(n)]
        delta = (
            sum(rel_b[t] for t in drawn) - sum(rel_a[t] for t in drawn)
        ) / n
        # Tail mass on the side of 0 OPPOSITE the point estimate.
        if point > 0 and delta < 0:
            n_opposite += 1
        elif point < 0 and delta > 0:
            n_opposite += 1
        elif delta == 0:
            n_zero += 1
    if point == 0:
        return 1.0  # no observed effect -> maximal p
    p_one = (n_opposite + 0.5 * n_zero) / n_resamples
    return min(1.0, 2.0 * p_one)


def holm_step_down(
    pvalues: Sequence[PValue], *, alpha: float
) -> tuple[HolmDecision, ...]:
    """Holm-Bonferroni step-down within one family. Sort ascending; reject while
    p_(i) <= alpha/(m-i); STOP at the first non-rejection (all larger p retained).
    adjusted_p is the standard monotone form: cumulative-max of (m-i)*p_(i)."""
    m = len(pvalues)
    if m == 0:
        return ()
    ordered = sorted(enumerate(pvalues), key=lambda pair: pair[1].p)
    decisions: list[HolmDecision] = []
    still_rejecting = True
    running_max_adj = 0.0
    for i, (_, pv) in enumerate(ordered):
        threshold = alpha / (m - i)
        if still_rejecting and pv.p <= threshold:
            rejected = True
        else:
            still_rejecting = False
            rejected = False
        running_max_adj = max(running_max_adj, min(1.0, (m - i) * pv.p))
        decisions.append(
            HolmDecision(
                name=pv.name,
                p=pv.p,
                adjusted_p=running_max_adj,
                rejected=rejected,
                rank=i,
            )
        )
    return tuple(decisions)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/metrics/test_multiplicity.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/metrics/multiplicity.py tests/metrics/test_multiplicity.py
git commit -m "feat(metrics): Holm step-down + bootstrap two-sided Delta pass^k p-value"
```

---

## Task 3: Pareto frontier over conditions (DEC-6)

**Files:**
- Create: `src/agent_eval_lab/metrics/pareto.py`
- Test: `tests/metrics/test_pareto.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/metrics/test_pareto.py
from agent_eval_lab.metrics.pareto import ParetoPoint, pareto_frontier


def test_frontier_keeps_higher_success_lower_cost():
    pts = (
        ParetoPoint(condition_id="cheap_good", success=0.9, cost=1.0),
        ParetoPoint(condition_id="dear_good", success=0.9, cost=5.0),   # dominated
        ParetoPoint(condition_id="cheap_bad", success=0.4, cost=0.5),   # frontier (cheapest)
        ParetoPoint(condition_id="dear_bad", success=0.4, cost=9.0),    # dominated
    )
    frontier = pareto_frontier(pts)
    ids = {p.condition_id for p in frontier}
    assert ids == {"cheap_good", "cheap_bad"}


def test_frontier_handles_ties_keeps_one_or_both_non_dominated():
    pts = (
        ParetoPoint(condition_id="a", success=0.8, cost=2.0),
        ParetoPoint(condition_id="b", success=0.8, cost=2.0),  # identical -> neither dominates
    )
    frontier = pareto_frontier(pts)
    assert {p.condition_id for p in frontier} == {"a", "b"}


def test_frontier_is_sorted_by_cost_ascending():
    pts = (
        ParetoPoint(condition_id="hi", success=1.0, cost=10.0),
        ParetoPoint(condition_id="lo", success=0.5, cost=1.0),
    )
    frontier = pareto_frontier(pts)
    assert [p.condition_id for p in frontier] == ["lo", "hi"]


def test_empty_input_returns_empty():
    assert pareto_frontier(()) == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/metrics/test_pareto.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/metrics/pareto.py
"""Pure Pareto frontier over conditions: maximize success, minimize a cost axis
(cost_usd | rounds | tokens). A point is dominated iff another has success >=
AND cost <= with at least one strict. Identical points never dominate each other.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ParetoPoint:
    condition_id: str
    success: float  # higher is better (pass^k)
    cost: float     # lower is better (usd | rounds | tokens)


def _dominates(p: ParetoPoint, q: ParetoPoint) -> bool:
    """p dominates q iff p is >= on success AND <= on cost, with >=1 strict."""
    no_worse = p.success >= q.success and p.cost <= q.cost
    strictly_better = p.success > q.success or p.cost < q.cost
    return no_worse and strictly_better


def pareto_frontier(points: Sequence[ParetoPoint]) -> tuple[ParetoPoint, ...]:
    frontier = [
        p for p in points if not any(_dominates(q, p) for q in points if q is not p)
    ]
    frontier.sort(key=lambda p: (p.cost, -p.success, p.condition_id))
    return tuple(frontier)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/metrics/test_pareto.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/metrics/pareto.py tests/metrics/test_pareto.py
git commit -m "feat(metrics): Pareto frontier over conditions (success vs cost axis)"
```

---

## Task 4: Per-domain aggregation → ExperimentResult (DEC-1, DEC-5, DEC-6)

**Files:**
- Create: `src/agent_eval_lab/experiments/aggregate.py`
- Test: `tests/experiments/test_aggregate.py`

This task builds the core: given a domain's `ReplacementOutcome`s and the spec, produce one `ExperimentResult` per (condition, domain, metric), choosing the CI method off `MetricDef.ci_method`, honoring void/INCOMPLETE, and threading the seed.

- [ ] **Step 1: Write the failing test**

```python
# tests/experiments/test_aggregate.py
from agent_eval_lab.experiments.aggregate import aggregate_domain_metric
from agent_eval_lab.experiments.schema import MetricDef
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt


def _run(task_id, passed, *, rounds=3, safety_cap=False, cond="m1"):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
        run_index=0,
        stop_reason="safety_cap" if safety_cap else "completed_natural",
        rounds=rounds,
        safety_cap_bound=safety_cap,
    )
    return RunResult(
        task_id=task_id, condition_id=cond, run_index=0, trajectory=traj,
        grade=GradeResult(grader_id="g", passed=passed, score=1.0 if passed else 0.0,
                          evidence={}),
    )


def _outcome(task_id, passes, *, void=False, cond="m1"):
    runs = tuple(_run(task_id, p, cond=cond) for p in passes)
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=void)


PASS_POW_K = MetricDef(
    name="pass_pow_k", domain="D", primary=True, aggregation="pass_pow_k",
    ci_method="cluster_bootstrap", validity_mask=True, censoring_policy="failure",
)
F_PASS_POW_K = MetricDef(
    name="pass_pow_k", domain="F", primary=True, aggregation="pass_pow_k",
    ci_method="binomial_exact", validity_mask=True, censoring_policy="failure",
)


def test_d_domain_uses_cluster_bootstrap_ci():
    # 3 tasks, all reliable -> pass^k = 1.0, cluster_bootstrap CI.
    outcomes = (_outcome("t1", [True]*3), _outcome("t2", [True]*3), _outcome("t3", [True]*3))
    r = aggregate_domain_metric(
        outcomes=outcomes, metric=PASS_POW_K, condition_id="m1",
        experiment_id="M1", spec_hash="abc", seed=1, n_resamples=200, alpha=0.05,
    )
    assert r.estimate == 1.0
    assert r.ci_method == "cluster_bootstrap"
    assert r.ci_lower is not None and r.ci_upper is not None
    assert r.valid_run_count == 9
    assert r.invalid_run_count == 0
    assert r.void is False


def test_f_domain_uses_binomial_exact_not_bootstrap():
    # 3 tasks, 2 reliable -> Clopper-Pearson on 2/3 (D38).
    outcomes = (
        _outcome("f1", [True]*5), _outcome("f2", [True]*5), _outcome("f3", [False]*5),
    )
    r = aggregate_domain_metric(
        outcomes=outcomes, metric=F_PASS_POW_K, condition_id="m1",
        experiment_id="M1", spec_hash="abc", seed=1, n_resamples=200, alpha=0.05,
    )
    assert r.estimate == 2 / 3
    assert r.ci_method == "binomial_exact"
    assert 0.09 < r.ci_lower < 0.10
    assert 0.99 < r.ci_upper < 1.0


def test_void_task_is_excluded_and_marks_domain_void():
    # t2 voided (INCOMPLETE): scored over the 2 complete tasks, domain.void True.
    outcomes = (
        _outcome("t1", [True]*3),
        _outcome("t2", [True, False], void=True),  # <k valid -> INCOMPLETE
        _outcome("t3", [False]*3),
    )
    r = aggregate_domain_metric(
        outcomes=outcomes, metric=PASS_POW_K, condition_id="m1",
        experiment_id="M1", spec_hash="abc", seed=1, n_resamples=200, alpha=0.05,
    )
    # complete tasks: t1 reliable, t3 not -> 1/2 = 0.5; t2 NOT scored.
    assert r.estimate == 0.5
    assert r.void is True


def test_safety_cap_run_counts_as_pass_pow_k_failure():
    # A safety-capped run has grade.passed=False -> task not reliable (D35).
    outcomes = (_outcome_with_cap(),)
    r = aggregate_domain_metric(
        outcomes=outcomes, metric=PASS_POW_K, condition_id="m1",
        experiment_id="M1", spec_hash="abc", seed=1, n_resamples=200, alpha=0.05,
    )
    assert r.estimate == 0.0


def _outcome_with_cap():
    runs = (
        _run("tc", True), _run("tc", True),
        _run("tc", False, safety_cap=True),  # capped = failed -> task not all-pass
    )
    attempts = tuple(TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs))
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)


def test_all_void_domain_returns_void_result_with_none_estimate():
    outcomes = (_outcome("t1", [True], void=True),)
    r = aggregate_domain_metric(
        outcomes=outcomes, metric=PASS_POW_K, condition_id="m1",
        experiment_id="M1", spec_hash="abc", seed=1, n_resamples=200, alpha=0.05,
    )
    assert r.void is True
    assert r.estimate == 0.0  # no scoreable task -> 0.0 estimate, CI None, void flagged
    assert r.ci_lower is None and r.ci_upper is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/experiments/test_aggregate.py -v`
Expected: FAIL with `ModuleNotFoundError: agent_eval_lab.experiments.aggregate`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/experiments/aggregate.py
"""Pure aggregation: ReplacementOutcomes + MetricDef -> ExperimentResult.

The single place that knows the validity/void/INCOMPLETE/censoring rules (D34,
D35, D38, §6, §18.2). Chooses the CI method off MetricDef.ci_method:
cluster_bootstrap (D/B), binomial_exact (F, Clopper-Pearson), none (efficiency).
Never scores a void task; flags the domain void if any task voided. Seeded
bootstrap (RNG argument, no global). Stdlib only.
"""

from __future__ import annotations

from collections.abc import Sequence

from agent_eval_lab.experiments.schema import ExperimentResult, MetricDef
from agent_eval_lab.metrics.binomial import clopper_pearson_ci
from agent_eval_lab.metrics.reliability import (
    pass_pow_k,
    pass_pow_k_bootstrap_ci,
    task_reliability,
)
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.runners.multi_run import ReplacementOutcome


def _complete_runs(outcomes: Sequence[ReplacementOutcome]) -> list[RunResult]:
    """All valid runs from NON-void outcomes (a void task is INCOMPLETE -> dropped)."""
    runs: list[RunResult] = []
    for o in outcomes:
        if o.void:
            continue
        runs.extend(o.valid_runs)
    return runs


def aggregate_domain_metric(
    *,
    outcomes: Sequence[ReplacementOutcome],
    metric: MetricDef,
    condition_id: str,
    experiment_id: str,
    spec_hash: str,
    seed: int,
    n_resamples: int,
    alpha: float,
) -> ExperimentResult:
    any_void = any(o.void for o in outcomes)
    complete = _complete_runs(outcomes)
    invalid_run_count = sum(
        sum(1 for a in o.attempts if not a.valid) for o in outcomes
    )
    if not complete:
        # Every task voided / no scoreable run: never invent a number.
        return ExperimentResult(
            experiment_id=experiment_id, spec_hash=spec_hash,
            condition_id=condition_id, domain=metric.domain,
            metric_name=metric.name, estimate=0.0,
            ci_lower=None, ci_upper=None, ci_method=metric.ci_method,
            valid_run_count=0, invalid_run_count=invalid_run_count, void=True,
        )
    estimate = pass_pow_k(complete)
    ci_lower: float | None = None
    ci_upper: float | None = None
    if metric.ci_method == "cluster_bootstrap":
        ci = pass_pow_k_bootstrap_ci(
            complete, n_resamples=n_resamples, seed=seed, alpha=alpha
        )
        ci_lower, ci_upper = ci.lo, ci.hi
    elif metric.ci_method == "binomial_exact":
        reliable = task_reliability(complete)
        n = len(reliable)
        x = sum(reliable.values())
        bci = clopper_pearson_ci(successes=x, n=n, alpha=alpha)
        ci_lower, ci_upper = bci.lo, bci.hi
    # ci_method == "none": leave both None.
    return ExperimentResult(
        experiment_id=experiment_id, spec_hash=spec_hash,
        condition_id=condition_id, domain=metric.domain, metric_name=metric.name,
        estimate=estimate, ci_lower=ci_lower, ci_upper=ci_upper,
        ci_method=metric.ci_method, valid_run_count=len(complete),
        invalid_run_count=invalid_run_count, void=any_void,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/experiments/test_aggregate.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/experiments/aggregate.py tests/experiments/test_aggregate.py
git commit -m "feat(experiments): per-domain ExperimentResult aggregation (CI-by-method, void/censoring)"
```

---

## Task 5: Efficiency aggregates (median + censored count, DEC-6)

**Files:**
- Modify: `src/agent_eval_lab/experiments/aggregate.py`
- Test: `tests/experiments/test_aggregate_efficiency.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/experiments/test_aggregate_efficiency.py
import math

from agent_eval_lab.experiments.aggregate import EfficiencySummary, efficiency_summary
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt


def _run(rounds, prompt, completion, wall, safety_cap=False):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=prompt, completion_tokens=completion, latency_s=wall),
        run_index=0,
        stop_reason="safety_cap" if safety_cap else "completed_natural",
        rounds=rounds, wall_time_s=wall, safety_cap_bound=safety_cap,
    )
    return RunResult(
        task_id="t", condition_id="m1", run_index=0, trajectory=traj,
        grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}),
    )


def _outcome(runs):
    attempts = tuple(TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs))
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)


def test_efficiency_summary_medians_and_token_total():
    runs = [_run(3, 10, 5, 1.0), _run(5, 20, 10, 2.0), _run(7, 30, 15, 3.0)]
    s = efficiency_summary(outcomes=(_outcome(runs),))
    assert s.median_rounds == 5
    assert s.total_tokens == (10 + 20 + 30) + (5 + 10 + 15)
    assert math.isclose(s.median_wall_time_s, 2.0)
    assert s.n_censored == 0


def test_efficiency_summary_counts_safety_cap_as_censored():
    runs = [_run(3, 10, 5, 1.0), _run(200, 99, 99, 60.0, safety_cap=True)]
    s = efficiency_summary(outcomes=(_outcome(runs),))
    assert s.n_censored == 1  # the capped run is right-censored (D35), counted not hidden
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/experiments/test_aggregate_efficiency.py -v`
Expected: FAIL with `ImportError: cannot import name 'efficiency_summary'`

- [ ] **Step 3: Write minimal implementation (append to aggregate.py)**

```python
# Append to src/agent_eval_lab/experiments/aggregate.py

from dataclasses import dataclass
from statistics import median

from agent_eval_lab.metrics.reliability import token_totals


@dataclass(frozen=True, kw_only=True)
class EfficiencySummary:
    median_rounds: float
    total_tokens: int
    median_wall_time_s: float
    n_censored: int  # valid runs with safety_cap_bound=True (right-censored, D35)
    n_runs: int


def efficiency_summary(*, outcomes: Sequence[ReplacementOutcome]) -> EfficiencySummary:
    runs = _complete_runs(outcomes)
    if not runs:
        return EfficiencySummary(
            median_rounds=0.0, total_tokens=0, median_wall_time_s=0.0,
            n_censored=0, n_runs=0,
        )
    prompt, completion = token_totals(runs)
    return EfficiencySummary(
        median_rounds=median(r.trajectory.rounds for r in runs),
        total_tokens=prompt + completion,
        median_wall_time_s=median(r.trajectory.wall_time_s for r in runs),
        n_censored=sum(1 for r in runs if r.trajectory.safety_cap_bound),
        n_runs=len(runs),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/experiments/test_aggregate_efficiency.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/experiments/aggregate.py tests/experiments/test_aggregate_efficiency.py
git commit -m "feat(experiments): efficiency summary (median rounds/wall, token total, censored count)"
```

---

## Task 6: Macro-weighted composite (DEC-3)

**Files:**
- Modify: `src/agent_eval_lab/experiments/aggregate.py`
- Test: `tests/experiments/test_composite.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/experiments/test_composite.py
import math

from agent_eval_lab.experiments.aggregate import macro_composite
from agent_eval_lab.experiments.schema import DomainWeight, ExperimentResult


def _per_domain(domain, estimate, lo, hi, void=False):
    return ExperimentResult(
        experiment_id="M1", spec_hash="abc", condition_id="m1", domain=domain,
        metric_name="pass_pow_k", estimate=estimate, ci_lower=lo, ci_upper=hi,
        ci_method="cluster_bootstrap", valid_run_count=10, invalid_run_count=0,
        void=void,
    )


EQUAL = (DomainWeight(domain="F", weight=1.0), DomainWeight(domain="D", weight=1.0),
         DomainWeight(domain="B", weight=1.0))


def test_composite_is_equal_weighted_mean_of_present_domains():
    per_domain = (
        _per_domain("F", 0.6, 0.3, 0.9),
        _per_domain("D", 0.9, 0.8, 1.0),
        _per_domain("B", 0.3, 0.1, 0.5),
    )
    comp = macro_composite(
        per_domain_primary=per_domain, weights=EQUAL, condition_id="m1",
        experiment_id="M1", spec_hash="abc",
    )
    assert math.isclose(comp.estimate, (0.6 + 0.9 + 0.3) / 3)
    assert comp.domain == "composite"
    assert comp.ci_method == "weighted_halfwidth_propagation"
    assert comp.ci_lower is not None and comp.ci_upper is not None


def test_composite_drops_missing_domain_and_renormalizes():
    # Only D present (the D-only first run) -> composite == D estimate.
    comp = macro_composite(
        per_domain_primary=(_per_domain("D", 0.7, 0.5, 0.9),), weights=EQUAL,
        condition_id="m1", experiment_id="M1", spec_hash="abc",
    )
    assert math.isclose(comp.estimate, 0.7)


def test_composite_excludes_void_domain():
    per_domain = (
        _per_domain("D", 0.8, 0.6, 1.0),
        _per_domain("B", 0.0, None, None, void=True),  # void -> excluded
    )
    comp = macro_composite(
        per_domain_primary=per_domain, weights=EQUAL, condition_id="m1",
        experiment_id="M1", spec_hash="abc",
    )
    assert math.isclose(comp.estimate, 0.8)  # only D contributes
    assert comp.void is True  # a contributing domain was dropped due to void
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/experiments/test_composite.py -v`
Expected: FAIL with `ImportError: cannot import name 'macro_composite'`

- [ ] **Step 3: Write minimal implementation (append to aggregate.py)**

```python
# Append to src/agent_eval_lab/experiments/aggregate.py

import math as _math

from agent_eval_lab.experiments.schema import DomainWeight

COMPOSITE_CI_METHOD = "weighted_halfwidth_propagation"


def macro_composite(
    *,
    per_domain_primary: Sequence[ExperimentResult],
    weights: Sequence[DomainWeight],
    condition_id: str,
    experiment_id: str,
    spec_hash: str,
) -> ExperimentResult:
    """Weighted mean of per-domain PRIMARY estimates (D23/§18.2), weighted by
    DOMAIN (default equal), never a raw task pool. Missing or void domains are
    dropped and the remaining weights renormalized; any drop sets void=True so
    the renderer discloses the reduced coverage. CI = conservative half-width
    propagation under independence (DEC-3); deterministic, no RNG."""
    weight_of = {w.domain: w.weight for w in weights}
    contributing = [
        r for r in per_domain_primary if not r.void and r.estimate is not None
    ]
    dropped = len(per_domain_primary) - len(contributing) or (
        len(weights) > len({r.domain for r in per_domain_primary})
    )
    if not contributing:
        return ExperimentResult(
            experiment_id=experiment_id, spec_hash=spec_hash,
            condition_id=condition_id, domain="composite", metric_name="composite",
            estimate=0.0, ci_lower=None, ci_upper=None,
            ci_method=COMPOSITE_CI_METHOD, valid_run_count=0, invalid_run_count=0,
            void=True,
        )
    total_w = sum(weight_of.get(r.domain, 0.0) for r in contributing)
    estimate = sum(weight_of.get(r.domain, 0.0) * r.estimate for r in contributing) / total_w
    # Propagate half-widths under independence; missing per-domain CI -> 0 contribution.
    var = 0.0
    for r in contributing:
        w_norm = weight_of.get(r.domain, 0.0) / total_w
        if r.ci_lower is not None and r.ci_upper is not None:
            half = (r.ci_upper - r.ci_lower) / 2.0
            var += (w_norm * half) ** 2
    spread = _math.sqrt(var)
    return ExperimentResult(
        experiment_id=experiment_id, spec_hash=spec_hash, condition_id=condition_id,
        domain="composite", metric_name="composite", estimate=estimate,
        ci_lower=max(0.0, estimate - spread), ci_upper=min(1.0, estimate + spread),
        ci_method=COMPOSITE_CI_METHOD, valid_run_count=sum(r.valid_run_count for r in contributing),
        invalid_run_count=sum(r.invalid_run_count for r in contributing),
        void=bool(dropped),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/experiments/test_composite.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/experiments/aggregate.py tests/experiments/test_composite.py
git commit -m "feat(experiments): macro-weighted composite (equal weights, half-width CI, void-aware)"
```

---

## Task 7: M1 ExperimentSpec builder + draft JSON (item §item-5)

**Files:**
- Create: `src/agent_eval_lab/experiments/m1_spec.py`
- Create: `examples/experiments/m1-agentic-v1.draft.json` (emitted by the builder)
- Test: `tests/experiments/test_m1_spec.py`

The builder assembles the frozen-able M1 spec: conditions = the reachable roster (deepseek, glm, minimax, local; plus provisional SiliconFlow Qwen ladder marked via label), one primary `pass_pow_k` metric per domain (F=binomial_exact, D/B=cluster_bootstrap) + efficiency metrics (ci_method="none"), equal macro weights, planned comparisons = pairwise model comparisons on the **D-domain** primary metric, one Holm family. The spec is left with `spec_hash=""` (freeze-spec writes it). `dataset_snapshot_hash`/`pricing_snapshot_hash` are passed in (the builder does not do I/O).

- [ ] **Step 1: Write the failing test**

```python
# tests/experiments/test_m1_spec.py
from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.spec_hash import freeze_spec, verify_spec_hash


def test_build_m1_spec_has_one_primary_per_domain():
    spec = build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    primaries = [m for m in spec.metrics if m.primary]
    domains = {m.domain for m in primaries}
    assert domains == {"F", "D", "B"}
    assert len(primaries) == 3


def test_f_primary_is_binomial_exact_d_and_b_are_cluster_bootstrap():
    spec = build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    by = {(m.domain, m.primary): m for m in spec.metrics if m.primary}
    assert by[("F", True)].ci_method == "binomial_exact"
    assert by[("D", True)].ci_method == "cluster_bootstrap"
    assert by[("B", True)].ci_method == "cluster_bootstrap"


def test_frozen_params_match_18_2():
    spec = build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    assert spec.k == 5
    assert spec.repeats == 1
    assert spec.safety_cap == 200
    assert spec.max_invalid_rate == 0.40
    weights = {w.domain: w.weight for w in spec.macro_weights}
    assert weights == {"F": 1.0, "D": 1.0, "B": 1.0}
    assert all(f.correction == "holm" for f in spec.families)


def test_planned_comparisons_are_pairwise_on_d_primary():
    spec = build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    assert spec.planned_comparisons  # non-empty
    for c in spec.planned_comparisons:
        assert c.domain == "D"
        assert c.metric_name == "pass_pow_k"
        # effect = metric(b) - metric(a): both endpoints are real condition ids
        ids = {cond.condition_id for cond in spec.conditions}
        assert c.condition_a in ids and c.condition_b in ids
        assert c.family_id in {f.id for f in spec.families}


def test_m1_spec_freezes_and_verifies():
    spec = build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    frozen = freeze_spec(spec)  # runs the §18.3 validators
    assert verify_spec_hash(frozen)
    assert frozen.spec_hash != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/experiments/test_m1_spec.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/experiments/m1_spec.py
"""Builder for the real M1 ExperimentSpec (§8 / §18.2). Pure (no I/O): callers
pass the dataset/pricing snapshot hashes. spec_hash is left "" — freeze-spec
writes it. Conditions = the reachable roster (config.py PROVIDERS) plus the
PROVISIONAL SiliconFlow Qwen ladder (labelled provisional; condition ids stay
provisional until config.py gains the entries, §18.11). gpt-5.5 is omitted (the
network block is recorded in reports/final.EXCLUDED_CONDITIONS).
"""

from __future__ import annotations

from itertools import combinations

from agent_eval_lab.experiments.schema import (
    ConditionDef,
    DomainWeight,
    ExperimentSpec,
    MetricDef,
    MultiplicityFamily,
    PlannedComparison,
)

# Reachable roster (condition_id = provider:model). The Qwen ladder ids are
# PROVISIONAL (siliconflow provider not yet in config.py) — labelled as such.
_CONDITIONS: tuple[ConditionDef, ...] = (
    ConditionDef(condition_id="deepseek:deepseek-v4-pro", label="deepseek"),
    ConditionDef(condition_id="glm:Pro/zai-org/GLM-5.1", label="glm"),
    ConditionDef(condition_id="minimax:MiniMax-M3", label="minimax"),
    ConditionDef(condition_id="local:qwen3-8b", label="local-qwen3-8b"),
    ConditionDef(
        condition_id="siliconflow:Qwen/Qwen3.5-397B-A17B",
        label="qwen3.5-397b (PROVISIONAL)",
    ),
    ConditionDef(
        condition_id="siliconflow:Qwen/Qwen3.6-35B-A3B",
        label="qwen3.6-35b (PROVISIONAL)",
    ),
)

_FAMILY_ID = "m1-pairwise-D-primary"


def _metrics() -> tuple[MetricDef, ...]:
    def primary(domain, ci):
        return MetricDef(
            name="pass_pow_k", domain=domain, primary=True, aggregation="pass_pow_k",
            ci_method=ci, validity_mask=True, censoring_policy="failure",
        )

    def efficiency(name, domain):
        return MetricDef(
            name=name, domain=domain, primary=False, aggregation="median",
            ci_method="none", validity_mask=True, censoring_policy="right_censored",
        )

    metrics: list[MetricDef] = [
        primary("F", "binomial_exact"),
        primary("D", "cluster_bootstrap"),
        primary("B", "cluster_bootstrap"),
    ]
    for domain in ("F", "D", "B"):
        for name in ("rounds", "tokens", "cost_usd", "wall_time_s"):
            metrics.append(efficiency(name, domain))
    return tuple(metrics)


def build_m1_spec(*, dataset_snapshot_hash: str, pricing_snapshot_hash: str) -> ExperimentSpec:
    family = MultiplicityFamily(
        id=_FAMILY_ID,
        description="Pairwise model comparisons on the D-domain primary pass^k.",
        correction="holm", alpha=0.05,
    )
    comparisons = tuple(
        PlannedComparison(
            name=f"{a.label}_vs_{b.label}", family_id=_FAMILY_ID, domain="D",
            condition_a=a.condition_id, condition_b=b.condition_id,
            metric_name="pass_pow_k",
        )
        for a, b in combinations(_CONDITIONS, 2)
    )
    return ExperimentSpec(
        experiment_id="M1-agentic-v1", k=5, repeats=1, safety_cap=200,
        max_invalid_rate=0.40, conditions=_CONDITIONS, metrics=_metrics(),
        macro_weights=(
            DomainWeight(domain="F", weight=1.0),
            DomainWeight(domain="D", weight=1.0),
            DomainWeight(domain="B", weight=1.0),
        ),
        families=(family,), planned_comparisons=comparisons,
        dataset_snapshot_hash=dataset_snapshot_hash,
        pricing_snapshot_hash=pricing_snapshot_hash, spec_hash="",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/experiments/test_m1_spec.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Emit the committed draft JSON**

Run (uses the existing `freeze-spec` plumbing path indirectly — write the draft, then a follow-up `freeze-spec` produces the frozen file at run time):

```bash
mkdir -p examples/experiments
uv run python -c "
import json
from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.cli import _spec_to_dict
spec = build_m1_spec(dataset_snapshot_hash='TBD-at-freeze', pricing_snapshot_hash='TBD-at-freeze')
open('examples/experiments/m1-agentic-v1.draft.json','w').write(
    json.dumps(_spec_to_dict(spec), sort_keys=True, indent=2, ensure_ascii=True) + chr(10))
print('wrote examples/experiments/m1-agentic-v1.draft.json')
"
```

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/experiments/m1_spec.py tests/experiments/test_m1_spec.py examples/experiments/m1-agentic-v1.draft.json
git commit -m "feat(experiments): M1 ExperimentSpec builder + committed draft JSON"
```

---

## Task 8: Holm correction over the spec's planned comparisons (DEC-2 wiring)

**Files:**
- Create: `src/agent_eval_lab/experiments/comparisons.py`
- Test: `tests/experiments/test_comparisons.py`

This wires the spec's `PlannedComparison`s to the per-comparison p-value (bootstrap for D/B, Fisher for F) and applies Holm per family. Input is a `{condition_id: {domain: [RunResult,...]}}` map (the valid runs by condition/domain). Output is per-comparison `HolmDecision` + the Δ CI for the report.

- [ ] **Step 1: Write the failing test**

```python
# tests/experiments/test_comparisons.py
from agent_eval_lab.experiments.comparisons import run_planned_comparisons
from agent_eval_lab.experiments.schema import (
    MultiplicityFamily, PlannedComparison,
)
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn


def _run(task_id, cond, passed):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0, stop_reason="completed_natural",
    )
    return RunResult(task_id=task_id, condition_id=cond, run_index=0, trajectory=traj,
                     grade=GradeResult(grader_id="g", passed=passed,
                                       score=1.0 if passed else 0.0, evidence={}))


def _arm(cond, pass_by_task):
    return [_run(t, cond, p) for t, p in pass_by_task.items()]


def test_run_planned_comparisons_applies_holm_and_reports_ci():
    tasks_pass_a = {f"t{i}": False for i in range(6)}
    tasks_pass_b = {f"t{i}": True for i in range(6)}
    runs_by = {
        "a": {"D": _arm("a", tasks_pass_a)},
        "b": {"D": _arm("b", tasks_pass_b)},
    }
    comps = (
        PlannedComparison(name="a_vs_b", family_id="F1", domain="D",
                          condition_a="a", condition_b="b", metric_name="pass_pow_k"),
    )
    family = MultiplicityFamily(id="F1", description="d", correction="holm", alpha=0.05)
    out = run_planned_comparisons(
        comparisons=comps, families=(family,), runs_by_condition_domain=runs_by,
        seed=20260613, n_resamples=2000, alpha_default=0.05,
    )
    assert len(out) == 1
    row = out[0]
    assert row.comparison_name == "a_vs_b"
    assert row.delta_point == 1.0          # pass^k(b)-pass^k(a) = 1 - 0 = 1
    assert row.decision.rejected is True   # clear separation survives Holm at m=1
    assert row.ci_lower is not None        # paired bootstrap CI populated


def test_missing_arm_is_reported_not_crashed():
    # Partial coverage: condition b has no D runs -> the comparison is SKIPPED.
    runs_by = {"a": {"D": _arm("a", {"t0": True})}, "b": {}}
    comps = (
        PlannedComparison(name="a_vs_b", family_id="F1", domain="D",
                          condition_a="a", condition_b="b", metric_name="pass_pow_k"),
    )
    family = MultiplicityFamily(id="F1", description="d", correction="holm", alpha=0.05)
    out = run_planned_comparisons(
        comparisons=comps, families=(family,), runs_by_condition_domain=runs_by,
        seed=1, n_resamples=100, alpha_default=0.05,
    )
    assert len(out) == 1
    assert out[0].skipped is True
    assert out[0].decision is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/experiments/test_comparisons.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/experiments/comparisons.py
"""Wire PlannedComparisons to per-comparison p-values + Holm per family (DEC-2).

D/B comparisons use the bootstrap two-sided Delta pass^k p (and the paired
cluster-bootstrap CI); F comparisons use Fisher exact (no bootstrap). Holm is
applied WITHIN each family. Missing arms (partial coverage) are reported as
skipped, never crashed. Seeded; stdlib only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_eval_lab.experiments.schema import MultiplicityFamily, PlannedComparison
from agent_eval_lab.metrics.binomial import fisher_exact_two_sided
from agent_eval_lab.metrics.multiplicity import (
    HolmDecision,
    PValue,
    bootstrap_diff_p_value,
    holm_step_down,
)
from agent_eval_lab.metrics.reliability import paired_pass_pow_k_diff_ci, task_reliability
from agent_eval_lab.records.grade import RunResult


@dataclass(frozen=True, kw_only=True)
class ComparisonRow:
    comparison_name: str
    family_id: str
    domain: str
    skipped: bool
    delta_point: float | None
    ci_lower: float | None
    ci_upper: float | None
    decision: HolmDecision | None


def _arm(runs_by, condition_id, domain) -> list[RunResult]:
    return list(runs_by.get(condition_id, {}).get(domain, []))


def run_planned_comparisons(
    *,
    comparisons: Sequence[PlannedComparison],
    families: Sequence[MultiplicityFamily],
    runs_by_condition_domain: Mapping[str, Mapping[str, Sequence[RunResult]]],
    seed: int,
    n_resamples: int,
    alpha_default: float,
) -> tuple[ComparisonRow, ...]:
    alpha_of = {f.id: f.alpha for f in families}
    # 1) compute per-comparison p + CI; gather p-values per family.
    pre: dict[str, tuple[PlannedComparison, float | None, float | None, float | None, float | None]] = {}
    family_pvalues: dict[str, list[PValue]] = {}
    for comp in comparisons:
        a = _arm(runs_by_condition_domain, comp.condition_a, comp.domain)
        b = _arm(runs_by_condition_domain, comp.condition_b, comp.domain)
        if not a or not b or set(task_reliability(a)) != set(task_reliability(b)):
            pre[comp.name] = (comp, None, None, None, None)  # skipped
            continue
        if comp.domain == "F":
            rel_a, rel_b = task_reliability(a), task_reliability(b)
            p = fisher_exact_two_sided(
                a_success=sum(rel_a.values()), a_n=len(rel_a),
                b_success=sum(rel_b.values()), b_n=len(rel_b),
            )
            point = sum(rel_b.values()) / len(rel_b) - sum(rel_a.values()) / len(rel_a)
            lo = hi = None  # F CI is the per-domain Clopper-Pearson, not a Delta CI
        else:
            ci = paired_pass_pow_k_diff_ci(
                a, b, n_resamples=n_resamples, seed=seed, alpha=alpha_default
            )
            p = bootstrap_diff_p_value(
                a, b, n_resamples=n_resamples, seed=seed, alpha=alpha_default
            )
            point, lo, hi = ci.point, ci.lo, ci.hi
        pre[comp.name] = (comp, point, lo, hi, p)
        family_pvalues.setdefault(comp.family_id, []).append(PValue(name=comp.name, p=p))
    # 2) Holm per family.
    decisions: dict[str, HolmDecision] = {}
    for fid, pvs in family_pvalues.items():
        for d in holm_step_down(pvs, alpha=alpha_of.get(fid, alpha_default)):
            decisions[d.name] = d
    # 3) assemble rows in declared order.
    rows: list[ComparisonRow] = []
    for comp in comparisons:
        c, point, lo, hi, p = pre[comp.name]
        rows.append(
            ComparisonRow(
                comparison_name=comp.name, family_id=comp.family_id, domain=comp.domain,
                skipped=(p is None), delta_point=point, ci_lower=lo, ci_upper=hi,
                decision=decisions.get(comp.name),
            )
        )
    return tuple(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/experiments/test_comparisons.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/experiments/comparisons.py tests/experiments/test_comparisons.py
git commit -m "feat(experiments): planned comparisons + Holm per family (bootstrap D/B, Fisher F)"
```

---

## Task 9: M1 report builder (pure) — assemble the full report model (DEC-3, DEC-5, DEC-6, DEC-7)

**Files:**
- Create: `src/agent_eval_lab/reports/m1.py`
- Test: `tests/reports/test_m1_build.py`

The builder takes: the frozen `ExperimentSpec`, `runs_by_condition_domain` (Mapping[condition_id → Mapping[domain → tuple[ReplacementOutcome,...]]]), the loaded `PricingSnapshot`, and the seed/n_resamples/alpha. It produces a frozen `M1Report` dataclass holding per-domain `ExperimentResult`s, composites, Pareto frontiers, fc-v3 classification counts per condition, validity/invalid-rate stats, comparison rows, and provenance (spec_hash, dataset/pricing hashes). **No I/O.**

> Note on the input shape: the builder consumes `ReplacementOutcome`s (so it can see void) for aggregation, and derives the flat `runs_by_condition_domain` valid-run map (Mapping → Sequence[RunResult]) internally for the comparison layer + fc-v3 + Pareto.

- [ ] **Step 1: Write the failing test**

```python
# tests/reports/test_m1_build.py
from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1 import build_m1_report
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt


def _run(task_id, cond, passed, rounds=3):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
        run_index=0, stop_reason="completed_natural", rounds=rounds,
    )
    return RunResult(task_id=task_id, condition_id=cond, run_index=0, trajectory=traj,
                     grade=GradeResult(grader_id="g", passed=passed,
                                       score=1.0 if passed else 0.0, evidence={}))


def _outcome(task_id, cond, passes):
    runs = tuple(_run(task_id, cond, p) for p in passes)
    attempts = tuple(TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs))
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)


def _spec():
    return freeze_spec(build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr"))


def _pricing():
    return PricingSnapshot(
        snapshot_date="2026-06-13",
        prices={"deepseek:deepseek-v4-pro": PricePoint(input_per_mtok=1.74, output_per_mtok=3.48)},
    )


def test_d_only_first_run_renders_d_and_marks_f_b_not_run():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": tuple(_outcome(f"t{i}", cond, [True]*5) for i in range(3))}}
    report = build_m1_report(
        spec=_spec(), outcomes_by_condition_domain=outcomes, pricing=_pricing(),
        seed=20260613, n_resamples=200, alpha=0.05,
    )
    d_results = [r for r in report.per_domain_results if r.domain == "D"]
    assert d_results and d_results[0].estimate == 1.0
    # F and B were not run -> no per-domain result for them under this condition
    assert not any(r.domain == "F" for r in report.per_domain_results)
    assert "F" in report.domains_not_run and "B" in report.domains_not_run
    assert "D" not in report.domains_not_run


def test_composite_over_present_domains_only():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": tuple(_outcome(f"t{i}", cond, [True]*5) for i in range(3))}}
    report = build_m1_report(
        spec=_spec(), outcomes_by_condition_domain=outcomes, pricing=_pricing(),
        seed=20260613, n_resamples=200, alpha=0.05,
    )
    comp = [r for r in report.composites if r.condition_id == cond][0]
    assert comp.estimate == 1.0  # only D present -> composite == D
    assert comp.void is True     # F/B dropped -> reduced coverage disclosed


def test_spec_hash_and_provenance_carried():
    spec = _spec()
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": (_outcome("t0", cond, [True]*5),)}}
    report = build_m1_report(
        spec=spec, outcomes_by_condition_domain=outcomes, pricing=_pricing(),
        seed=20260613, n_resamples=100, alpha=0.05,
    )
    assert report.spec_hash == spec.spec_hash
    assert report.dataset_snapshot_hash == "ds"
    assert report.classifier_version == "fc-v3"


def test_deterministic_for_same_inputs():
    spec = _spec()
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": tuple(_outcome(f"t{i}", cond, [i % 2 == 0]*5) for i in range(4))}}
    r1 = build_m1_report(spec=spec, outcomes_by_condition_domain=outcomes,
                         pricing=_pricing(), seed=7, n_resamples=300, alpha=0.05)
    r2 = build_m1_report(spec=spec, outcomes_by_condition_domain=outcomes,
                         pricing=_pricing(), seed=7, n_resamples=300, alpha=0.05)
    d1 = [r for r in r1.per_domain_results if r.domain == "D"][0]
    d2 = [r for r in r2.per_domain_results if r.domain == "D"][0]
    assert (d1.estimate, d1.ci_lower, d1.ci_upper) == (d2.estimate, d2.ci_lower, d2.ci_upper)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/reports/test_m1_build.py -v`
Expected: FAIL with `ModuleNotFoundError: agent_eval_lab.reports.m1`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/reports/m1.py  (build half — renderer added in Task 10)
"""Pure M1 report: build + render, no I/O (mirrors reports/final.py).

Per-domain ExperimentResults (CI-by-method), macro composites, per-domain Pareto
frontiers, fc-v3 taxonomy per condition, validity/invalid-rate + void/INCOMPLETE,
Holm-corrected planned comparisons, and provenance (spec_hash + snapshot hashes).
Partial coverage is first-class: a (condition, domain) with no runs contributes
no result and is listed in domains_not_run. Deterministic for fixed seed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_eval_lab.experiments.aggregate import (
    EfficiencySummary,
    aggregate_domain_metric,
    efficiency_summary,
    macro_composite,
)
from agent_eval_lab.experiments.comparisons import ComparisonRow, run_planned_comparisons
from agent_eval_lab.experiments.pricing import PricingSnapshot, condition_cost_usd
from agent_eval_lab.experiments.schema import (
    Domain,
    ExperimentResult,
    ExperimentSpec,
    MetricDef,
)
from agent_eval_lab.metrics.pareto import ParetoPoint, pareto_frontier
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.reports.classify import (
    CLASSIFIER_VERSION,
    RunClassification,
    classify_run,
)
from agent_eval_lab.runners.multi_run import ReplacementOutcome

_DOMAINS: tuple[Domain, ...] = ("F", "D", "B")


@dataclass(frozen=True, kw_only=True)
class DomainEfficiency:
    condition_id: str
    domain: Domain
    summary: EfficiencySummary
    cost_usd: float | None


@dataclass(frozen=True, kw_only=True)
class ParetoChart:
    domain: Domain
    axis: str  # "cost_usd" | "rounds" | "tokens"
    frontier: tuple[ParetoPoint, ...]
    all_points: tuple[ParetoPoint, ...]


@dataclass(frozen=True, kw_only=True)
class ConditionFailureTaxonomy:
    condition_id: str
    counts: Mapping[tuple[str, str], int]


@dataclass(frozen=True, kw_only=True)
class ValidityRow:
    condition_id: str
    domain: Domain
    valid: int
    invalid: int
    invalid_rate: float
    void_task_count: int


@dataclass(frozen=True, kw_only=True)
class M1Report:
    experiment_id: str
    spec_hash: str
    dataset_snapshot_hash: str
    pricing_snapshot_hash: str
    pricing_snapshot_date: str
    k: int
    max_invalid_rate: float
    seed: int
    n_resamples: int
    alpha: float
    classifier_version: str
    macro_weights: Mapping[str, float]
    per_domain_results: tuple[ExperimentResult, ...]   # primary metric only
    composites: tuple[ExperimentResult, ...]
    efficiency: tuple[DomainEfficiency, ...]
    pareto_charts: tuple[ParetoChart, ...]
    failure_taxonomy: tuple[ConditionFailureTaxonomy, ...]
    validity: tuple[ValidityRow, ...]
    comparisons: tuple[ComparisonRow, ...]
    conditions_present: tuple[str, ...]
    domains_not_run: tuple[str, ...]


def _primary_for(spec: ExperimentSpec, domain: Domain) -> MetricDef:
    for m in spec.metrics:
        if m.domain == domain and m.primary:
            return m
    raise ValueError(f"no primary metric for domain {domain}")


def _valid_runs(outcomes: Sequence[ReplacementOutcome]) -> list[RunResult]:
    runs: list[RunResult] = []
    for o in outcomes:
        if not o.void:
            runs.extend(o.valid_runs)
    return runs


def _classification_counts(runs: Sequence[RunResult]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for run in runs:
        if run.grade.passed:
            continue
        c: RunClassification = classify_run(run)
        key = (c.category, c.subcategory or "—")
        counts[key] = counts.get(key, 0) + 1
    return counts


def build_m1_report(
    *,
    spec: ExperimentSpec,
    outcomes_by_condition_domain: Mapping[str, Mapping[str, Sequence[ReplacementOutcome]]],
    pricing: PricingSnapshot,
    seed: int,
    n_resamples: int,
    alpha: float,
) -> M1Report:
    conditions_present = tuple(sorted(outcomes_by_condition_domain))
    per_domain: list[ExperimentResult] = []
    efficiency: list[DomainEfficiency] = []
    validity: list[ValidityRow] = []
    taxonomy: list[ConditionFailureTaxonomy] = []
    # valid-run map for comparisons / Pareto / fc-v3
    runs_by: dict[str, dict[str, list[RunResult]]] = {}
    domains_seen: set[str] = set()

    for cond in conditions_present:
        per_cond_runs: list[RunResult] = []
        runs_by[cond] = {}
        for domain in _DOMAINS:
            outcomes = tuple(outcomes_by_condition_domain[cond].get(domain, ()))
            if not outcomes:
                continue
            domains_seen.add(domain)
            primary = _primary_for(spec, domain)
            result = aggregate_domain_metric(
                outcomes=outcomes, metric=primary, condition_id=cond,
                experiment_id=spec.experiment_id, spec_hash=spec.spec_hash,
                seed=seed, n_resamples=n_resamples, alpha=alpha,
            )
            per_domain.append(result)
            valid = _valid_runs(outcomes)
            runs_by[cond][domain] = valid
            per_cond_runs.extend(valid)
            eff = efficiency_summary(outcomes=outcomes)
            cost = (
                condition_cost_usd(valid, cond, pricing)
                if cond in pricing.prices and valid
                else None
            )
            efficiency.append(
                DomainEfficiency(condition_id=cond, domain=domain, summary=eff, cost_usd=cost)
            )
            invalid = result.invalid_run_count
            total = result.valid_run_count + invalid
            validity.append(
                ValidityRow(
                    condition_id=cond, domain=domain, valid=result.valid_run_count,
                    invalid=invalid, invalid_rate=(invalid / total if total else 0.0),
                    void_task_count=sum(1 for o in outcomes if o.void),
                )
            )
        taxonomy.append(
            ConditionFailureTaxonomy(
                condition_id=cond, counts=_classification_counts(per_cond_runs)
            )
        )

    composites = tuple(
        macro_composite(
            per_domain_primary=[r for r in per_domain if r.condition_id == cond],
            weights=spec.macro_weights, condition_id=cond,
            experiment_id=spec.experiment_id, spec_hash=spec.spec_hash,
        )
        for cond in conditions_present
    )

    pareto_charts = tuple(
        _pareto_for(per_domain, efficiency, domain, axis)
        for domain in sorted(domains_seen)
        for axis in ("cost_usd", "rounds", "tokens")
    )

    comparisons = run_planned_comparisons(
        comparisons=spec.planned_comparisons, families=spec.families,
        runs_by_condition_domain=runs_by, seed=seed, n_resamples=n_resamples,
        alpha_default=alpha,
    )
    domains_not_run = tuple(d for d in _DOMAINS if d not in domains_seen)

    return M1Report(
        experiment_id=spec.experiment_id, spec_hash=spec.spec_hash,
        dataset_snapshot_hash=spec.dataset_snapshot_hash,
        pricing_snapshot_hash=spec.pricing_snapshot_hash,
        pricing_snapshot_date=pricing.snapshot_date, k=spec.k,
        max_invalid_rate=spec.max_invalid_rate, seed=seed, n_resamples=n_resamples,
        alpha=alpha, classifier_version=CLASSIFIER_VERSION,
        macro_weights={w.domain: w.weight for w in spec.macro_weights},
        per_domain_results=tuple(per_domain), composites=composites,
        efficiency=tuple(efficiency), pareto_charts=pareto_charts,
        failure_taxonomy=tuple(taxonomy), validity=tuple(validity),
        comparisons=comparisons, conditions_present=conditions_present,
        domains_not_run=domains_not_run,
    )


def _pareto_for(
    per_domain: Sequence[ExperimentResult],
    efficiency: Sequence[DomainEfficiency],
    domain: str,
    axis: str,
) -> ParetoChart:
    success_of = {
        r.condition_id: r.estimate for r in per_domain if r.domain == domain
    }
    points: list[ParetoPoint] = []
    for eff in efficiency:
        if eff.domain != domain or eff.condition_id not in success_of:
            continue
        if axis == "cost_usd":
            cost = eff.cost_usd
            if cost is None:
                continue
        elif axis == "rounds":
            cost = eff.summary.median_rounds
        else:  # tokens
            cost = float(eff.summary.total_tokens)
        points.append(
            ParetoPoint(condition_id=eff.condition_id, success=success_of[eff.condition_id], cost=cost)
        )
    return ParetoChart(
        domain=domain, axis=axis, frontier=pareto_frontier(tuple(points)),
        all_points=tuple(points),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/reports/test_m1_build.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/reports/m1.py tests/reports/test_m1_build.py
git commit -m "feat(reports): M1 report builder (per-domain + composite + Pareto + fc-v3 + validity, partial-coverage-safe)"
```

---

## Task 10: M1 report renderer (markdown) — including partial-coverage section

**Files:**
- Modify: `src/agent_eval_lab/reports/m1.py`
- Test: `tests/reports/test_m1_render.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/reports/test_m1_render.py
from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1 import build_m1_report, render_markdown
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt


def _outcome(task_id, cond, passes, void=False):
    runs = tuple(
        RunResult(task_id=task_id, condition_id=cond, run_index=i,
                  trajectory=Trajectory(
                      turns=(MessageTurn(role="assistant", content="x"),),
                      usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
                      run_index=i, stop_reason="completed_natural", rounds=3),
                  grade=GradeResult(grader_id="g", passed=p, score=1.0 if p else 0.0,
                                    evidence={}))
        for i, p in enumerate(passes)
    )
    attempts = tuple(TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs))
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=void)


def _report(outcomes):
    spec = freeze_spec(build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr"))
    pricing = PricingSnapshot(snapshot_date="2026-06-13",
                              prices={"deepseek:deepseek-v4-pro": PricePoint(input_per_mtok=1.0, output_per_mtok=2.0)})
    return spec, render_markdown(build_m1_report(
        spec=spec, outcomes_by_condition_domain=outcomes, pricing=pricing,
        seed=20260613, n_resamples=200, alpha=0.05))


def test_render_includes_spec_hash_and_per_domain_and_composite():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": tuple(_outcome(f"t{i}", cond, [True]*5) for i in range(3))}}
    spec, md = _report(outcomes)
    assert spec.spec_hash in md
    assert "Per-domain scores" in md
    assert "Macro composite" in md
    assert "Pareto" in md
    assert "fc-v3" in md or "Failure taxonomy" in md


def test_render_marks_f_and_b_not_yet_run():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": (_outcome("t0", cond, [True]*5),)}}
    _, md = _report(outcomes)
    assert "not yet run" in md.lower()
    assert "| F |" in md or "F (not yet run)" in md


def test_render_flags_void_domain():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": (_outcome("t0", cond, [True]*5),
                             _outcome("t1", cond, [True, False], void=True))}}
    _, md = _report(outcomes)
    assert "VOID" in md or "INCOMPLETE" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/reports/test_m1_render.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_markdown'`

- [ ] **Step 3: Write minimal implementation (append renderer to m1.py)**

```python
# Append to src/agent_eval_lab/reports/m1.py

def _ci_cell(r: ExperimentResult) -> str:
    if r.void and r.valid_run_count == 0:
        return "INCOMPLETE (VOID)"
    if r.ci_lower is None or r.ci_upper is None:
        base = f"{r.estimate:.3f} (no CI)"
    else:
        base = f"{r.estimate:.3f} [{r.ci_lower:.3f}, {r.ci_upper:.3f}]"
    return base + (" — VOID (incomplete tasks present)" if r.void else "")


def _per_domain_lines(report: M1Report) -> list[str]:
    lines = [
        "## Per-domain scores (primary metric: pass^k)",
        "",
        "| condition | domain | pass^k [95% CI] | CI method | valid | invalid |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in report.per_domain_results:
        lines.append(
            f"| {r.condition_id} | {r.domain} | {_ci_cell(r)} | {r.ci_method} "
            f"| {r.valid_run_count} | {r.invalid_run_count} |"
        )
    if report.domains_not_run:
        for d in report.domains_not_run:
            lines.append(f"| (all conditions) | {d} | not yet run | — | 0 | 0 |")
    return lines + [""]


def _composite_lines(report: M1Report) -> list[str]:
    weights = ", ".join(f"{d}={w}" for d, w in sorted(report.macro_weights.items()))
    lines = [
        "## Macro composite",
        "",
        f"Equal-weighted mean of per-domain primary estimates (weights: {weights}); "
        "weighted by DOMAIN, never a raw task pool (D23). CI method: "
        "`weighted_halfwidth_propagation` (conservative half-width propagation under "
        "independence; the composite over K=3 domains has no defensible bootstrap CI).",
        "",
        "| condition | composite | note |",
        "| --- | --- | --- |",
    ]
    for c in report.composites:
        note = (
            "reduced coverage (some domains not run / void)" if c.void else "all domains present"
        )
        ci = (
            f" [{c.ci_lower:.3f}, {c.ci_upper:.3f}]"
            if c.ci_lower is not None and c.ci_upper is not None else ""
        )
        lines.append(f"| {c.condition_id} | {c.estimate:.3f}{ci} | {note} |")
    if report.domains_not_run:
        lines.append("")
        lines.append(
            f"> Composite computed over present domains only; not yet run: "
            f"{', '.join(report.domains_not_run)}."
        )
    return lines + [""]


def _pareto_lines(report: M1Report) -> list[str]:
    lines = ["## Pareto frontiers (success vs efficiency, per domain)", ""]
    if not report.pareto_charts:
        return lines + ["(no domains run)", ""]
    for chart in report.pareto_charts:
        lines += [
            f"### {chart.domain} — pass^k vs {chart.axis}",
            "",
            "| condition | pass^k | " + chart.axis + " | on frontier |",
            "| --- | --- | --- | --- |",
        ]
        frontier_ids = {p.condition_id for p in chart.frontier}
        for p in sorted(chart.all_points, key=lambda x: (x.cost, -x.success)):
            mark = "yes" if p.condition_id in frontier_ids else "—"
            lines.append(f"| {p.condition_id} | {p.success:.3f} | {p.cost:.4g} | {mark} |")
        lines.append("")
    return lines


def _taxonomy_lines(report: M1Report) -> list[str]:
    lines = [f"## Failure taxonomy ({report.classifier_version}) per condition", ""]
    for t in report.failure_taxonomy:
        lines += [f"### {t.condition_id}", "", "| category | subcategory | count |",
                  "| --- | --- | --- |"]
        if not t.counts:
            lines.append("| (no failures) | — | 0 |")
        else:
            for (cat, sub), n in sorted(t.counts.items(), key=lambda kv: (-kv[1], kv[0])):
                lines.append(f"| {cat} | {sub} | {n} |")
        lines.append("")
    return lines


def _validity_lines(report: M1Report) -> list[str]:
    lines = [
        "## Validity mask / invalid-rate / void",
        "",
        f"Max invalid-rate (VOID threshold): {report.max_invalid_rate:.2f}; "
        f"k={report.k} valid trials required per task (D34). A task that voids before "
        "k valid trials is INCOMPLETE and excluded from pass^k — never scored over <k.",
        "",
        "| condition | domain | valid | invalid | invalid-rate | void tasks |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for v in report.validity:
        flag = " ⚠ over threshold" if v.invalid_rate > report.max_invalid_rate else ""
        lines.append(
            f"| {v.condition_id} | {v.domain} | {v.valid} | {v.invalid} "
            f"| {v.invalid_rate:.3f}{flag} | {v.void_task_count} |"
        )
    return lines + [""]


def _comparison_lines(report: M1Report) -> list[str]:
    lines = [
        "## Planned comparisons (Holm-corrected, two-sided; effect = metric(b) − metric(a))",
        "",
        "| comparison | domain | Δ pass^k [CI] | p | Holm-adj p | rejected |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in report.comparisons:
        if c.skipped or c.decision is None:
            lines.append(f"| {c.comparison_name} | {c.domain} | (skipped — arm not run) | — | — | — |")
            continue
        ci = (
            f"{c.delta_point:+.3f} [{c.ci_lower:+.3f}, {c.ci_upper:+.3f}]"
            if c.ci_lower is not None else f"{c.delta_point:+.3f}"
        )
        lines.append(
            f"| {c.comparison_name} | {c.domain} | {ci} | {c.decision.p:.4f} "
            f"| {c.decision.adjusted_p:.4f} | {'yes' if c.decision.rejected else 'no'} |"
        )
    return lines + [""]


def _header_lines(report: M1Report) -> list[str]:
    return [
        f"# M1 model characterization report — {report.experiment_id}",
        "",
        f"- spec_hash: `{report.spec_hash}` · dataset_snapshot_hash: "
        f"`{report.dataset_snapshot_hash}` · pricing_snapshot_hash: "
        f"`{report.pricing_snapshot_hash}` (snapshot {report.pricing_snapshot_date})",
        f"- k={report.k} valid trials · bootstrap seed={report.seed} "
        f"· n_resamples={report.n_resamples} · alpha={report.alpha} "
        f"· classifier {report.classifier_version}",
        f"- conditions present: {', '.join(report.conditions_present) or '(none)'}",
        (
            f"- domains not yet run: {', '.join(report.domains_not_run)} "
            "(rendered as 'not yet run', not as failures)"
            if report.domains_not_run else "- all domains (F/D/B) present"
        ),
        "",
    ]


def render_markdown(report: M1Report) -> str:
    lines = (
        _header_lines(report)
        + _per_domain_lines(report)
        + _composite_lines(report)
        + _pareto_lines(report)
        + _comparison_lines(report)
        + _taxonomy_lines(report)
        + _validity_lines(report)
    )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/reports/test_m1_render.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/reports/m1.py tests/reports/test_m1_render.py
git commit -m "feat(reports): M1 markdown renderer (per-domain/composite/Pareto/comparisons/taxonomy/validity)"
```

---

## Task 11: M1 run orchestration entrypoint (EDGE, stub-tested)

**Files:**
- Create: `src/agent_eval_lab/experiments/m1_run.py`
- Test: `tests/experiments/test_m1_run.py`

`run_m1` iterates conditions × domains and, for the domains wired today (D via `run_dset`), runs the tasks via `run_task_k_valid`, returning `outcomes_by_condition_domain` for the report builder. F/B are absent-tolerant: if a domain has no task provider, it is simply skipped (no crash). **The actual provider calls are NOT exercised here** — the test stubs `run_dset` so this is a pure-wiring test (the multi-model RUN is downstream, out of scope per the item).

- [ ] **Step 1: Write the failing test**

```python
# tests/experiments/test_m1_run.py
import httpx

from agent_eval_lab.experiments.m1_run import run_m1
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
from agent_eval_lab.tasks.schema import FactKeySpec, Task, TaskInput, TaskMetadata


def _task(tid):
    return Task(
        id=tid, capability="docs_qa",
        input=TaskInput(messages=(MessageTurn(role="user", content="q"),),
                        available_tools=("bash",)),
        verification=FactKeySpec(required=("x",), forbidden=(), page_snapshot="x",
                                 page_snapshot_sha256="s", level=1),
        metadata=TaskMetadata(split="held_out", version="v", provenance="t"),
    )


def _outcome(tid, cond):
    r = RunResult(task_id=tid, condition_id=cond, run_index=0,
                  trajectory=Trajectory(turns=(MessageTurn(role="assistant", content="x"),),
                                        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
                                        run_index=0, stop_reason="completed_natural"),
                  grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}))
    return ReplacementOutcome(valid_runs=(r,)*5,
                              attempts=(TrialAttempt(attempt_index=0, valid=True, run=r),),
                              void=False)


def test_run_m1_threads_dset_per_condition(monkeypatch):
    from agent_eval_lab.experiments import m1_run

    calls = []

    def fake_run_dset(*, config, tasks, k_valid, **kw):
        calls.append((config.model_id, tuple(t.id for t in tasks), k_valid))
        cond = f"{config.id}:{config.model_id}"
        return tuple(_outcome(t.id, cond) for t in tasks)

    monkeypatch.setattr(m1_run, "run_dset", fake_run_dset)

    configs = (
        ProviderConfig(id="deepseek", base_url="u", api_key_env="K", model_id="deepseek-v4-pro"),
        ProviderConfig(id="minimax", base_url="u", api_key_env="K", model_id="MiniMax-M3"),
    )
    out = run_m1(
        configs=configs,
        domain_tasks={"D": (_task("t0"), _task("t1"))},  # F/B absent -> skipped
        http_client=httpx.Client(), k_valid=5, max_invalid_rate=0.40,
        temperature=0.0, max_tokens=4096, health_probe_fn=None, reference_sha256=None,
        evaluator_store=None,
    )
    assert len(calls) == 2  # one per condition
    assert set(out) == {"deepseek:deepseek-v4-pro", "minimax:MiniMax-M3"}
    assert set(out["deepseek:deepseek-v4-pro"]) == {"D"}  # only D ran
    assert len(out["deepseek:deepseek-v4-pro"]["D"]) == 2  # two tasks


def test_run_m1_skips_absent_domains_without_crashing(monkeypatch):
    from agent_eval_lab.experiments import m1_run

    monkeypatch.setattr(m1_run, "run_dset", lambda **kw: ())
    out = run_m1(
        configs=(ProviderConfig(id="local", base_url="u", api_key_env="", model_id="qwen3-8b"),),
        domain_tasks={},  # no domains at all
        http_client=httpx.Client(), k_valid=5, max_invalid_rate=0.40,
        temperature=0.0, max_tokens=4096, health_probe_fn=None, reference_sha256=None,
        evaluator_store=None,
    )
    assert out == {"local:qwen3-8b": {}}  # present condition, no domains, no crash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/experiments/test_m1_run.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/experiments/m1_run.py
"""EDGE: M1 run orchestration — conditions × domains over the runners.

For each ProviderConfig and each domain with task definitions, run the domain's
tasks and collect ReplacementOutcomes. D uses runners/dset_run.run_dset (the
template domain path). F and B are WIRED WHEN ITEMS 004/006 LAND: a domain with
no task definitions is simply skipped (absent, not a crash) so the D-only first
run works today. The actual provider/network calls happen here; this module is
unit-tested with run_dset STUBBED (the real multi-model run is downstream, out
of scope for this item).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import httpx

from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.runners.dset_run import run_dset
from agent_eval_lab.runners.multi_run import ReplacementOutcome
from agent_eval_lab.tasks.schema import Task


def run_m1(
    *,
    configs: Sequence[ProviderConfig],
    domain_tasks: Mapping[str, Sequence[Task]],
    http_client: httpx.Client,
    k_valid: int,
    max_invalid_rate: float,
    temperature: float,
    max_tokens: int,
    health_probe_fn: Callable | None,
    reference_sha256: str | None,
    evaluator_store: Path | None,
) -> dict[str, dict[str, tuple[ReplacementOutcome, ...]]]:
    out: dict[str, dict[str, tuple[ReplacementOutcome, ...]]] = {}
    for config in configs:
        cond = condition_id(config)
        out[cond] = {}
        d_tasks = domain_tasks.get("D")
        if d_tasks:
            out[cond]["D"] = run_dset(
                evaluator_store=evaluator_store, tasks=tuple(d_tasks), config=config,
                http_client=http_client, k_valid=k_valid,
                max_invalid_rate=max_invalid_rate, temperature=temperature,
                max_tokens=max_tokens, health_probe_fn=health_probe_fn,
                reference_sha256=reference_sha256,
            )
        # F / B: no domain runner yet (items 004/006). Absent -> skipped, never a crash.
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/experiments/test_m1_run.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/experiments/m1_run.py tests/experiments/test_m1_run.py
git commit -m "feat(experiments): run_m1 orchestration entrypoint (D wired, F/B absent-tolerant; stub-tested)"
```

---

## Task 12: CLI `report-m1` (aggregate recorded runs → report)

**Files:**
- Modify: `src/agent_eval_lab/cli.py`
- Test: `tests/experiments/test_cli_report_m1.py`

`report-m1` reads the frozen spec JSON, a set of `--runs DOMAIN:condition=path/to/runs.jsonl` specs (so the edge knows which runs belong to which domain), the pricing.json, and writes the rendered M1 markdown. Each runs file is a JSONL of `RunResult`s (one (condition, domain)); since the file holds **only valid recorded runs** (the run path streams `outcome.valid_runs`), the edge reconstructs one **non-void** `ReplacementOutcome` per task (void/INCOMPLETE tasks were never written, so they are absent — the edge surfaces a `--incomplete-tasks` note path is out of scope; partial coverage is by-domain, which IS handled). Reuse `_load_run_results` and `load_pricing`.

> Reconstruction rule: group a domain's RunResults by `task_id`; each group becomes a `ReplacementOutcome(valid_runs=<the group>, attempts=<valid attempts>, void=False)`. This is faithful because the run path only ever wrote valid runs; a voided task simply has no rows. (If a future run path also emits a void manifest, extend the edge to read it; not needed for the D-only first run.)

- [ ] **Step 1: Write the failing test**

```python
# tests/experiments/test_cli_report_m1.py
import json
from pathlib import Path

from agent_eval_lab.cli import main
from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.serialize import run_result_to_dict
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn


def _runs_jsonl(path: Path, cond: str):
    rows = []
    for ti in range(3):
        for ri in range(5):
            r = RunResult(
                task_id=f"t{ti}", condition_id=cond, run_index=ri,
                trajectory=Trajectory(turns=(MessageTurn(role="assistant", content="x"),),
                                      usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
                                      run_index=ri, stop_reason="completed_natural", rounds=3),
                grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}))
            rows.append(json.dumps(run_result_to_dict(r)))
    path.write_text("\n".join(rows) + "\n")


def test_report_m1_writes_markdown(tmp_path):
    spec = freeze_spec(build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr"))
    spec_path = tmp_path / "spec.json"
    from agent_eval_lab.cli import _spec_to_dict
    spec_path.write_text(json.dumps(_spec_to_dict(spec)))
    cond = "deepseek:deepseek-v4-pro"
    runs = tmp_path / "runs-d.jsonl"
    _runs_jsonl(runs, cond)
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"snapshot_date": "2026-06-13",
                                  "prices": {cond: {"input_per_mtok": 1.0, "output_per_mtok": 2.0}}}))
    out = tmp_path / "m1.md"
    rc = main([
        "report-m1", "--spec", str(spec_path),
        "--runs", f"D:{cond}={runs}",
        "--prices", str(prices), "--out", str(out),
        "--seed", "20260613", "--n-resamples", "200", "--alpha", "0.05",
    ])
    assert rc == 0
    md = out.read_text()
    assert spec.spec_hash in md
    assert "Per-domain scores" in md
    assert "not yet run" in md.lower()  # F and B absent in this D-only report
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/experiments/test_cli_report_m1.py -v`
Expected: FAIL with `SystemExit: 2` (`invalid choice: 'report-m1'`)

- [ ] **Step 3: Write minimal implementation**

Add to `cli.py` (import the new pieces at top, add the parser, add the handler, dispatch it):

```python
# cli.py — add to imports
from agent_eval_lab.experiments.pricing import load_pricing
from agent_eval_lab.reports.m1 import build_m1_report
from agent_eval_lab.reports.m1 import render_markdown as render_m1
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
```

```python
# cli.py — new handler
def _parse_domain_runs_spec(spec: str) -> tuple[str, str, Path]:
    """'DOMAIN:condition_id=path' -> (domain, condition_id, path). condition_id
    may contain '=' (openrouter-style), so split domain off the left then path
    off the right."""
    if ":" not in spec:
        raise ValueError(f"bad --runs spec {spec!r}; want DOMAIN:condition_id=path")
    domain, rest = spec.split(":", 1)
    cond, *tail = rest.rsplit("=", 1)
    if not tail:
        raise ValueError(f"bad --runs spec {spec!r}; missing '=path'")
    return domain, cond, Path(tail[0])


def _outcomes_from_runs(results: Sequence[RunResult]) -> tuple[ReplacementOutcome, ...]:
    """One non-void ReplacementOutcome per task_id (the run path only writes valid
    runs; voided tasks have no rows). Faithful for the D-only first run."""
    by_task: dict[str, list[RunResult]] = {}
    for r in results:
        by_task.setdefault(r.task_id, []).append(r)
    outcomes = []
    for tid in sorted(by_task):
        runs = tuple(by_task[tid])
        attempts = tuple(
            TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
        )
        outcomes.append(ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False))
    return tuple(outcomes)


def _run_report_m1(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    spec = _spec_from_dict(data)
    if not spec.spec_hash:
        print("error: spec is not frozen (run freeze-spec first)", file=sys.stderr)
        return 1
    pricing = load_pricing(args.prices)
    outcomes: dict[str, dict[str, tuple[ReplacementOutcome, ...]]] = {}
    for spec_str in args.runs:
        try:
            domain, cond, path = _parse_domain_runs_spec(spec_str)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        results = _load_run_results(path) if path.exists() else []
        outcomes.setdefault(cond, {})[domain] = _outcomes_from_runs(results)
    report = build_m1_report(
        spec=spec, outcomes_by_condition_domain=outcomes, pricing=pricing,
        seed=args.seed, n_resamples=args.n_resamples, alpha=args.alpha,
    )
    _atomic_write(args.out, render_m1(report))
    print(args.out)
    return 0
```

```python
# cli.py — in _build_parser(), add the subparser
    rm = subparsers.add_parser(
        "report-m1",
        help="aggregate recorded M1 runs into the per-domain + macro report (pure)",
    )
    rm.add_argument("--spec", required=True, type=Path, help="frozen ExperimentSpec JSON")
    rm.add_argument(
        "--runs", required=True, nargs="+",
        help="one per (domain,condition): DOMAIN:condition_id=path/to/runs.jsonl",
    )
    rm.add_argument("--prices", required=True, type=Path)
    rm.add_argument("--out", required=True, type=Path)
    rm.add_argument("--seed", type=int, default=20260613)
    rm.add_argument("--n-resamples", type=int, default=2000)
    rm.add_argument("--alpha", type=float, default=0.05)
```

```python
# cli.py — in main(), add dispatch BEFORE the run-dset / baseline fallthrough
    if args.command == "report-m1":
        return _run_report_m1(args)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/experiments/test_cli_report_m1.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/experiments/test_cli_report_m1.py
git commit -m "feat(cli): report-m1 — aggregate recorded runs into the M1 per-domain+macro report"
```

---

## Task 13: CLI `run-m1` (orchestration entrypoint)

**Files:**
- Modify: `src/agent_eval_lab/cli.py`
- Test: `tests/experiments/test_cli_run_m1.py`

`run-m1` is the thin edge over `run_m1`: it reads the frozen spec to get k_valid/max_invalid_rate, builds the D-domain CMC tasks (reusing `build_cmc_tasks` + the evaluator store, exactly as `run-dset` does), resolves the roster of `ProviderConfig`s (from `--provider` repeated, or all reachable from PROVIDERS by default), runs `run_m1`, and streams one runs-JSONL per (condition, domain). It does NOT call the report (that is `report-m1`). The test stubs `run_m1` so no network is touched.

- [ ] **Step 1: Write the failing test**

```python
# tests/experiments/test_cli_run_m1.py
import json
from pathlib import Path

from agent_eval_lab.cli import main


def test_run_m1_streams_runs_per_condition_domain(tmp_path, monkeypatch):
    # Stub run_m1 so no provider/network is touched.
    from agent_eval_lab import cli
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

    def _outcome(tid, cond):
        r = RunResult(task_id=tid, condition_id=cond, run_index=0,
                      trajectory=Trajectory(turns=(MessageTurn(role="assistant", content="x"),),
                                            usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
                                            run_index=0, stop_reason="completed_natural"),
                      grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}))
        return ReplacementOutcome(valid_runs=(r,)*5,
                                  attempts=(TrialAttempt(attempt_index=0, valid=True, run=r),), void=False)

    def fake_run_m1(*, configs, **kw):
        return {f"{c.id}:{c.model_id}": {"D": (_outcome("cmc-q01", f"{c.id}:{c.model_id}"),)}
                for c in configs}

    monkeypatch.setattr(cli, "run_m1", fake_run_m1)
    # Stub the task + config loading so the edge is exercised without an evaluator store.
    monkeypatch.setattr(cli, "_load_m1_domain_tasks", lambda args, cfg: {"D": ()})

    # Minimal frozen spec on disk.
    from agent_eval_lab.cli import _spec_to_dict
    from agent_eval_lab.experiments.m1_spec import build_m1_spec
    from agent_eval_lab.experiments.spec_hash import freeze_spec
    spec = freeze_spec(build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr"))
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec_to_dict(spec)))

    out = tmp_path / "runs"
    rc = main([
        "run-m1", "--spec", str(spec_path), "--provider", "deepseek",
        "--evaluator-config", str(tmp_path / "evaluator.toml"),
        "--out", str(out),
    ])
    assert rc == 0
    written = list(out.glob("runs-m1-*-D.jsonl"))
    assert len(written) == 1
    assert written[0].read_text().strip()  # non-empty JSONL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/experiments/test_cli_run_m1.py -v`
Expected: FAIL with `SystemExit: 2` (`invalid choice: 'run-m1'`)

- [ ] **Step 3: Write minimal implementation**

Add to `cli.py`:

```python
# cli.py — import
from agent_eval_lab.experiments.m1_run import run_m1
```

```python
# cli.py — task loader (factored so the test can stub it)
def _load_m1_domain_tasks(args, cfg) -> dict:
    """Build the per-domain task map. D = CMC docs tasks (reused from run-dset).
    F/B return no tasks until items 004/006 land — absent, not a crash."""
    from agent_eval_lab.datasets.cmc_dset import build_cmc_tasks

    store = Path(cfg.store.path)
    tasks = build_cmc_tasks(
        evaluator_store=store,
        questions_path=Path("examples/datasets/cmc-docs-questions.txt"),
    )
    return {"D": tasks}


def _run_m1_command(args: argparse.Namespace, http_client: httpx.Client | None) -> int:
    data = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    spec = _spec_from_dict(data)
    if not spec.spec_hash:
        print("error: spec is not frozen (run freeze-spec first)", file=sys.stderr)
        return 1
    cfg = load_evaluator_config(args.evaluator_config)
    store = Path(cfg.store.path)
    reference_sha256 = None
    factkeys = store / "cmc-docs-factkeys.json"
    if factkeys.exists():
        reference_sha256 = json.loads(factkeys.read_text())["snapshot_sha256"]

    providers = args.provider or sorted(PROVIDERS)
    configs = tuple(PROVIDERS[p] for p in providers)
    domain_tasks = _load_m1_domain_tasks(args, cfg)

    client = http_client or httpx.Client(timeout=120.0, trust_env=False)

    def health_probe_fn():
        from agent_eval_lab.records.env_health import EnvHealth

        hp = cfg.health_probe
        probe_client = httpx.Client(timeout=10.0, verify=False)
        try:
            r = health_probe(hp.url, hp.username, hp.password, client=probe_client)
        finally:
            probe_client.close()
        return EnvHealth(pre_healthy=r.healthy, post_healthy=r.healthy,
                         pre_status=r.status_code, post_status=r.status_code)

    try:
        outcomes = run_m1(
            configs=configs, domain_tasks=domain_tasks, http_client=client,
            k_valid=cfg.runner.k_valid, max_invalid_rate=cfg.runner.max_invalid_rate,
            temperature=args.temperature, max_tokens=args.max_tokens,
            health_probe_fn=health_probe_fn, reference_sha256=reference_sha256,
            evaluator_store=store,
        )
    finally:
        if http_client is None:
            client.close()

    args.out.mkdir(parents=True, exist_ok=True)
    for cond, by_domain in outcomes.items():
        for domain, domain_outcomes in by_domain.items():
            path = args.out / f"runs-m1-{_slug(cond)}-{domain}.jsonl"
            with path.open("w") as fh:
                for o in domain_outcomes:
                    _append_runs(fh, o.valid_runs)
                    if o.void:
                        tid = o.attempts[0].run.task_id if o.attempts else "?"
                        print(f"[void] {cond}/{domain} task {tid}: INCOMPLETE (D34)",
                              file=sys.stderr)
            print(path)
    return 0
```

```python
# cli.py — parser
    rmm = subparsers.add_parser(
        "run-m1", help="orchestrate M1 conditions × domains over the runners"
    )
    rmm.add_argument("--spec", required=True, type=Path, help="frozen ExperimentSpec JSON")
    rmm.add_argument(
        "--provider", action="append", choices=sorted(PROVIDERS),
        help="repeatable; default = all reachable providers",
    )
    rmm.add_argument("--evaluator-config", required=True, type=Path, metavar="TOML")
    rmm.add_argument("--out", type=Path, default=Path("reports"))
    rmm.add_argument("--temperature", type=float, default=0.0)
    rmm.add_argument("--max-tokens", type=int, default=4096)
```

```python
# cli.py — main() dispatch
    if args.command == "run-m1":
        return _run_m1_command(args, http_client)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/experiments/test_cli_run_m1.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/experiments/test_cli_run_m1.py
git commit -m "feat(cli): run-m1 — orchestrate conditions × domains, stream runs per (condition, domain)"
```

---

## Task 14: Full-suite regression + determinism gate

**Files:**
- Test: `tests/experiments/test_m1_determinism.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/experiments/test_m1_determinism.py
from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1 import build_m1_report, render_markdown
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt


def _outcome(tid, cond, passes):
    runs = tuple(
        RunResult(task_id=tid, condition_id=cond, run_index=i,
                  trajectory=Trajectory(turns=(MessageTurn(role="assistant", content="x"),),
                                        usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
                                        run_index=i, stop_reason="completed_natural", rounds=3),
                  grade=GradeResult(grader_id="g", passed=p, score=1.0 if p else 0.0, evidence={}))
        for i, p in enumerate(passes))
    attempts = tuple(TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs))
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)


def test_same_runs_and_spec_render_byte_identical():
    spec = freeze_spec(build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr"))
    pricing = PricingSnapshot(snapshot_date="2026-06-13",
                              prices={"deepseek:deepseek-v4-pro": PricePoint(input_per_mtok=1.0, output_per_mtok=2.0),
                                      "minimax:MiniMax-M3": PricePoint(input_per_mtok=0.5, output_per_mtok=1.0)})
    outcomes = {
        "deepseek:deepseek-v4-pro": {"D": tuple(_outcome(f"t{i}", "deepseek:deepseek-v4-pro", [i % 2 == 0]*5) for i in range(6))},
        "minimax:MiniMax-M3": {"D": tuple(_outcome(f"t{i}", "minimax:MiniMax-M3", [True]*5) for i in range(6))},
    }
    kw = dict(spec=spec, outcomes_by_condition_domain=outcomes, pricing=pricing,
              seed=20260613, n_resamples=1000, alpha=0.05)
    md1 = render_markdown(build_m1_report(**kw))
    md2 = render_markdown(build_m1_report(**kw))
    assert md1 == md2
```

- [ ] **Step 2: Run test to verify it fails (then passes — it should pass immediately if determinism holds)**

Run: `uv run pytest tests/experiments/test_m1_determinism.py -v`
Expected: PASS (determinism already designed in; this test PINS it so a future RNG regression is caught).

- [ ] **Step 3: Run the full suite + lint**

```bash
uv run pytest -q
uv run ruff check src/agent_eval_lab/{metrics,experiments,reports} tests/{metrics,experiments,reports}
```
Expected: all green, no lint errors.

- [ ] **Step 4: Commit**

```bash
git add tests/experiments/test_m1_determinism.py
git commit -m "test(experiments): pin M1 report determinism (same runs+spec+seed -> byte-identical)"
```

---

## Drift checklist (run before declaring done)

- [ ] **Type names match across tasks.** `aggregate_domain_metric`, `efficiency_summary`, `EfficiencySummary`, `macro_composite`, `COMPOSITE_CI_METHOD`, `clopper_pearson_ci`, `BinomialCI`, `fisher_exact_two_sided`, `bootstrap_diff_p_value`, `holm_step_down`, `PValue`, `HolmDecision`, `pareto_frontier`, `ParetoPoint`, `run_planned_comparisons`, `ComparisonRow`, `build_m1_spec`, `run_m1`, `build_m1_report`, `M1Report`, `render_markdown` — each spelled identically everywhere it appears.
- [ ] **`ExperimentResult` is constructed with the EXACT §18.3 field set** (experiment_id, spec_hash, condition_id, domain, metric_name, estimate, ci_lower, ci_upper, ci_method, valid_run_count, invalid_run_count, void) — no extra fields, no missing ones. `schema.py` is NOT modified (D29 froze the shape).
- [ ] **No numpy/scipy import** anywhere in the new code (grep `src/agent_eval_lab/{metrics,experiments,reports}` — stdlib-only invariant).
- [ ] **Every bootstrap/p-value/CI takes `seed` as a keyword arg** and uses `random.Random(seed)` (never `random.random()` / global RNG). Mirrors `reliability.py`.
- [ ] **F-domain primary metric uses `binomial_exact`, never `cluster_bootstrap`** (D38) — asserted by `test_f_domain_uses_binomial_exact_not_bootstrap` AND `test_f_primary_is_binomial_exact_...`.
- [ ] **safety_cap → pass^k failure** (D35): `grade.passed` is the only success signal; capped runs are `passed=False`. Pinned by `test_safety_cap_run_counts_as_pass_pow_k_failure`.
- [ ] **safety_cap → right-censored for efficiency** (D35): `efficiency_summary.n_censored` counts `safety_cap_bound` runs; the renderer prints the censored count.
- [ ] **Void/INCOMPLETE never silently scored** (D34): a void task is dropped from pass^k; if any task voids, the domain `ExperimentResult.void=True` and the renderer prints VOID/INCOMPLETE. Pinned by `test_void_task_is_excluded_and_marks_domain_void`.
- [ ] **Macro weights come from the frozen spec, never overridden** (D38/§18.2): `macro_composite` reads `spec.macro_weights`; there is no CLI flag to change weights.
- [ ] **Composite is by-DOMAIN, never a raw task pool** (D23): pinned by `test_composite_is_equal_weighted_mean_of_present_domains` (the pool of tasks differs in size per domain but each domain contributes its weight, not its count).
- [ ] **Partial coverage renders, never crashes** (DEC-7): D-only run shows D + "not yet run" for F/B. Pinned by `test_d_only_first_run_...` + `test_render_marks_f_and_b_not_yet_run` + `test_run_m1_skips_absent_domains_...`.
- [ ] **spec_hash + provenance present in every report** (§18.2): pinned by `test_spec_hash_and_provenance_carried` + `test_render_includes_spec_hash_...`.
- [ ] **The actual multi-model RUN is NOT executed in tests** — `run_dset`/`run_m1` are stubbed in Tasks 11/13 (item scope: orchestration entrypoint + stubbed unit test only).
- [ ] **`reports/final.py` / `reports/comparison.py` are NOT duplicated** — the M1 renderer reuses `classify.classify_run`, `pricing.condition_cost_usd`, and mirrors `final.py`'s `_*_lines` build idioms; it does not re-implement them.

---

## Partial-coverage subsection (how a D-only run renders)

The first real M1 run is **D-only** (F needs item 004's wdio edge runner; B needs item 006's MSTR oracle). The pipeline handles this end-to-end without special-casing:

1. **`run-m1`** builds only `{"D": cmc_tasks}` (`_load_m1_domain_tasks` returns no F/B tasks today). `run_m1` runs D via `run_dset` and skips F/B (no tasks → not in the output map). Output: `runs-m1-<cond>-D.jsonl` per condition; no F/B files.
2. **`report-m1`** receives only `D:<cond>=...` runs specs. `build_m1_report` iterates `_DOMAINS = (F, D, B)` but `outcomes_by_condition_domain[cond].get("F")` is empty → that domain contributes **no `ExperimentResult`** and lands in `domains_not_run`.
3. **Per-domain table** shows the D rows with real pass^k + cluster-bootstrap CI; an extra row `| (all conditions) | F | not yet run | — | 0 | 0 |` (and one for B).
4. **Macro composite** is computed over present domains only (D), so `composite == D estimate`, and `void=True` flags the reduced coverage; the renderer prints `> Composite computed over present domains only; not yet run: F, B.`
5. **Pareto** charts are emitted only for D (the `domains_seen` loop). F/B Pareto sections are simply absent.
6. **Planned comparisons** on the D primary run normally (all conditions have D); any comparison whose arm lacks D runs is reported `(skipped — arm not run)`, never crashed.
7. **fc-v3 taxonomy** + **validity mask** tables cover the D runs only. The validity table still prints the max-invalid-rate threshold + k so the reader sees the void contract even before B (the env-masked domain) is wired.

When F lands (item 004) the run path gains an F task provider and an F edge runner call inside `run_m1`; when B lands (item 006) the same for B. **No change to `aggregate.py`, `m1.py`, or the CLI report path is required** — they already iterate all three domains and key off presence. That is the whole point of the absent-tolerant design.

---

## Self-review (spec coverage)

- **§8 M1 per-domain + macro + Pareto** → Tasks 4, 6, 9, 10 (per-domain `ExperimentResult`, composite, Pareto charts, render).
- **§8 M1 roster + frozen spec** → Task 7 (`build_m1_spec` + draft JSON; `freeze_spec` reused).
- **§8/§18.2 Holm over planned comparisons** → Tasks 2, 8 (Holm + per-comparison p; wired per family).
- **§18.2 frozen params** (k=5, repeats=1, max_invalid_rate=0.40, equal weights, Holm, F=binomial, D/B=cluster bootstrap, two-sided, effect=b−a) → Task 7 asserts every value.
- **§18.3 ExperimentResult/MetricDef** → consumed verbatim; `schema.py` untouched (drift checklist).
- **§6 validity mask / void / INCOMPLETE / fc-v3** → Tasks 4 (void), 5 (censoring), 9 (validity rows + `classify_run` reuse), 10 (render).
- **D34 (k valid / INCOMPLETE)**, **D35 (safety_cap dual role)**, **D38 (F exact CI; no post-hoc weights)** → Tasks 4, 5, 7 + drift checklist.
- **§11 success criteria — "M1 publishes per-domain scores + a pre-registered macro composite — never a raw pool"** → Tasks 6, 9, 10 + the D23 drift item.
- **Item scope — orchestration entrypoint + stubbed unit test; real RUN out of scope** → Tasks 11, 13 (stubbed); no test makes a network call.
- **Partial coverage (D-only first run)** → Tasks 9, 10, 11, 13 + the dedicated subsection above.

**Placeholder scan:** every code step contains complete, runnable code (no TBD/TODO). Reference CI values in Task 1 are exact (verifiable against `scipy.stats.beta.ppf` offline, but the impl is stdlib).

**Type consistency:** the `ExperimentResult`/`MetricDef`/`DomainWeight`/`PlannedComparison`/`MultiplicityFamily` field names match `schema.py` verbatim; the new dataclass names are used identically across builder, report, and tests.
