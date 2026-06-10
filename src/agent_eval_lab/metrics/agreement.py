"""Pure inter-rater agreement: Cohen's kappa (binary headline, ADR 0006),
quadratic-weighted kappa (secondary), and a seeded percentile bootstrap CI
resampling items (spec §4.6). Stdlib only; the bootstrap RNG seed is an argument.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass

Label = object  # any hashable; in practice "faithful"/"unfaithful" or an int score


@dataclass(frozen=True, kw_only=True)
class KappaResult:
    kappa: float
    observed_agreement: float
    expected_agreement: float
    degenerate: bool


@dataclass(frozen=True, kw_only=True)
class BootstrapCI:
    point: float
    lo: float
    hi: float
    alpha: float
    n_resamples: int
    n_degenerate: int
    seed: int


def _require_pair(a: Sequence[Label], b: Sequence[Label]) -> None:
    if len(a) != len(b):
        raise ValueError("rater sequences must be of equal length")
    if not a:
        raise ValueError("rater sequences must not be empty")


def confusion_matrix(a: Sequence[Label], b: Sequence[Label]) -> dict[tuple, int]:
    _require_pair(a, b)
    cm: dict[tuple, int] = {}
    for x, y in zip(a, b):
        cm[(x, y)] = cm.get((x, y), 0) + 1
    return cm


def observed_agreement(a: Sequence[Label], b: Sequence[Label]) -> float:
    _require_pair(a, b)
    return sum(1 for x, y in zip(a, b) if x == y) / len(a)


def expected_agreement(a: Sequence[Label], b: Sequence[Label]) -> float:
    _require_pair(a, b)
    n = len(a)
    categories = set(a) | set(b)
    return sum(
        (sum(1 for x in a if x == c) / n) * (sum(1 for y in b if y == c) / n)
        for c in categories
    )


def cohens_kappa(a: Sequence[Label], b: Sequence[Label]) -> KappaResult:
    p_o = observed_agreement(a, b)
    p_e = expected_agreement(a, b)
    if 1.0 - p_e == 0.0:
        return KappaResult(
            kappa=0.0, observed_agreement=p_o, expected_agreement=p_e, degenerate=True
        )
    return KappaResult(
        kappa=(p_o - p_e) / (1.0 - p_e),
        observed_agreement=p_o,
        expected_agreement=p_e,
        degenerate=False,
    )


def _quadratic_weight(i: int, j: int, k: int) -> float:
    return 1.0 - ((i - j) ** 2) / ((k - 1) ** 2)


def weighted_kappa(
    a: Sequence[Label], b: Sequence[Label], *, categories: tuple
) -> float:
    """Quadratic-weighted kappa over ORDERED `categories` (secondary stat, ADR 0006).

    Disagreement weight scales with squared ordinal distance: near-misses cost
    less than gross disagreements. Returns 0.0 on the degenerate (1 - p_e == 0)
    path, matching cohens_kappa.
    """
    _require_pair(a, b)
    n = len(a)
    k = len(categories)
    index = {c: idx for idx, c in enumerate(categories)}
    cm = confusion_matrix(a, b)
    row = {i: sum(1 for x in a if index[x] == i) / n for i in range(k)}
    col = {j: sum(1 for y in b if index[y] == j) / n for j in range(k)}
    p_o = sum(
        _quadratic_weight(index[x], index[y], k) * count / n
        for (x, y), count in cm.items()
    )
    p_e = sum(
        _quadratic_weight(i, j, k) * row[i] * col[j] for i in range(k) for j in range(k)
    )
    if 1.0 - p_e == 0.0:
        return 0.0
    return (p_o - p_e) / (1.0 - p_e)


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation percentile (q in [0, 1]); inputs pre-sorted ascending."""
    if not sorted_values:
        raise ValueError("no values to take a percentile of")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo_idx = int(pos)
    frac = pos - lo_idx
    if lo_idx + 1 >= len(sorted_values):
        return sorted_values[-1]
    return sorted_values[lo_idx] + frac * (
        sorted_values[lo_idx + 1] - sorted_values[lo_idx]
    )


def kappa_bootstrap_ci(
    a: Sequence[Label],
    b: Sequence[Label],
    *,
    n_resamples: int,
    seed: int,
    alpha: float,
) -> BootstrapCI:
    """Percentile bootstrap CI for Cohen's kappa, resampling ITEMS (the annotated
    trajectory is the unit, spec §4.6). RNG is seeded => deterministic. A resample
    whose kappa hits the degenerate (1 - p_e == 0) path contributes kappa=0.0 and
    is COUNTED in n_degenerate (D7) — never silently dropped, never a crash.
    """
    _require_pair(a, b)
    pairs = list(zip(a, b))
    n = len(pairs)
    rng = random.Random(seed)
    point = cohens_kappa(a, b).kappa
    kappas: list[float] = []
    n_degenerate = 0
    for _ in range(n_resamples):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        ra = [p[0] for p in sample]
        rb = [p[1] for p in sample]
        result = cohens_kappa(ra, rb)
        if result.degenerate:
            n_degenerate += 1
        kappas.append(result.kappa)
    kappas.sort()
    return BootstrapCI(
        point=point,
        lo=_percentile(kappas, alpha / 2),
        hi=_percentile(kappas, 1 - alpha / 2),
        alpha=alpha,
        n_resamples=n_resamples,
        n_degenerate=n_degenerate,
        seed=seed,
    )
