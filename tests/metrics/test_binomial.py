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
