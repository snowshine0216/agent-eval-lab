import pytest

from agent_eval_lab.metrics.agreement import (
    cohens_kappa,
    confusion_matrix,
    expected_agreement,
    observed_agreement,
)


def _labels(a, b, c, d):
    """Build two rater sequences realizing a 2x2 (pos/neg) table."""
    pos, neg = "faithful", "unfaithful"
    la = [pos] * (a + b) + [neg] * (c + d)
    lb = [pos] * a + [neg] * b + [pos] * c + [neg] * d
    return la, lb


def test_confusion_matrix_counts_pairs() -> None:
    la, lb = _labels(20, 5, 10, 15)
    cm = confusion_matrix(la, lb)
    assert cm[("faithful", "faithful")] == 20
    assert cm[("faithful", "unfaithful")] == 5
    assert cm[("unfaithful", "faithful")] == 10
    assert cm[("unfaithful", "unfaithful")] == 15


def test_v1_textbook_kappa_is_0_40() -> None:
    la, lb = _labels(20, 5, 10, 15)
    assert observed_agreement(la, lb) == pytest.approx(0.70)
    assert expected_agreement(la, lb) == pytest.approx(0.50)
    r = cohens_kappa(la, lb)
    assert r.kappa == pytest.approx(0.40)
    assert r.degenerate is False


def test_v2_perfect_agreement_kappa_is_1() -> None:
    la, lb = _labels(10, 0, 0, 10)
    assert cohens_kappa(la, lb).kappa == pytest.approx(1.0)


def test_v3_chance_agreement_kappa_is_0() -> None:
    la, lb = _labels(25, 25, 25, 25)
    assert cohens_kappa(la, lb).kappa == pytest.approx(0.0)


def test_v4_cohen1960_kappa() -> None:
    la, lb = _labels(88, 14, 10, 88)
    assert cohens_kappa(la, lb).kappa == pytest.approx(0.7601, abs=1e-4)


def test_degenerate_single_category_is_kappa_0_flagged() -> None:
    # Both raters label every item the same single category -> 1 - p_e == 0.
    la = ["faithful"] * 10
    lb = ["faithful"] * 10
    r = cohens_kappa(la, lb)
    assert r.kappa == 0.0
    assert r.degenerate is True


def test_mismatched_lengths_raises() -> None:
    with pytest.raises(ValueError, match="equal length"):
        cohens_kappa(["a"], ["a", "b"])


def test_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        cohens_kappa([], [])


# Task 12: weighted_kappa


def test_weighted_kappa_ordinal_vector_is_two_thirds() -> None:
    from agent_eval_lab.metrics.agreement import weighted_kappa

    # 3x3 table [[10,5,0],[5,20,5],[0,5,10]] over ordered categories 0,1,2.
    table = [[10, 5, 0], [5, 20, 5], [0, 5, 10]]
    la, lb = [], []
    for i, row in enumerate(table):
        for j, count in enumerate(row):
            la.extend([i] * count)
            lb.extend([j] * count)
    assert weighted_kappa(la, lb, categories=(0, 1, 2)) == pytest.approx(
        2 / 3, abs=1e-9
    )


def test_weighted_kappa_perfect_agreement_is_1() -> None:
    from agent_eval_lab.metrics.agreement import weighted_kappa

    seq = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
    assert weighted_kappa(seq, seq, categories=(1, 2, 3, 4, 5)) == pytest.approx(1.0)


def test_weighted_kappa_degenerate_is_0() -> None:
    from agent_eval_lab.metrics.agreement import weighted_kappa

    assert weighted_kappa([2, 2, 2], [2, 2, 2], categories=(1, 2, 3)) == 0.0


# Task 13: kappa_bootstrap_ci


def test_bootstrap_is_deterministic_under_seed() -> None:
    from agent_eval_lab.metrics.agreement import kappa_bootstrap_ci

    la, lb = _labels(20, 5, 10, 15)
    a = kappa_bootstrap_ci(la, lb, n_resamples=500, seed=7, alpha=0.05)
    b = kappa_bootstrap_ci(la, lb, n_resamples=500, seed=7, alpha=0.05)
    assert (a.lo, a.hi, a.point) == (b.lo, b.hi, b.point)
    assert a.point == pytest.approx(0.40)
    assert a.lo <= a.point <= a.hi
    assert a.n_resamples == 500
    assert a.seed == 7


def test_bootstrap_different_seed_differs() -> None:
    from agent_eval_lab.metrics.agreement import kappa_bootstrap_ci

    la, lb = _labels(20, 5, 10, 15)
    a = kappa_bootstrap_ci(la, lb, n_resamples=200, seed=1, alpha=0.05)
    b = kappa_bootstrap_ci(la, lb, n_resamples=200, seed=2, alpha=0.05)
    assert (a.lo, a.hi) != (b.lo, b.hi)


def test_bootstrap_counts_degenerate_resamples() -> None:
    from agent_eval_lab.metrics.agreement import kappa_bootstrap_ci

    # A heavily imbalanced sample makes many resamples draw a single category.
    la = ["faithful"] * 19 + ["unfaithful"]
    lb = ["faithful"] * 19 + ["unfaithful"]
    ci = kappa_bootstrap_ci(la, lb, n_resamples=300, seed=3, alpha=0.05)
    assert (
        ci.n_degenerate > 0
    )  # some resamples drew all-faithful -> counted, not dropped
    assert ci.n_resamples == 300
    # Degenerate resamples contribute kappa=0.0; the CI is still finite (no crash).
    assert ci.lo <= ci.hi
