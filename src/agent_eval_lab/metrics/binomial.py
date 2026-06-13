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
    lo = (
        0.0
        if successes == 0
        else _beta_quantile(alpha / 2.0, successes, n - successes + 1)
    )
    hi = (
        1.0
        if successes == n
        else _beta_quantile(1.0 - alpha / 2.0, successes + 1, n - successes)
    )
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


def fisher_exact_two_sided(
    *, a_success: int, a_n: int, b_success: int, b_n: int
) -> float:
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
