import math

from agent_eval_lab.experiments.aggregate import macro_composite
from agent_eval_lab.experiments.schema import DomainWeight, ExperimentResult


def _per_domain(domain, estimate, lo, hi, void=False):
    return ExperimentResult(
        experiment_id="M1",
        spec_hash="abc",
        condition_id="m1",
        domain=domain,
        metric_name="pass_pow_k",
        estimate=estimate,
        ci_lower=lo,
        ci_upper=hi,
        ci_method="cluster_bootstrap",
        valid_run_count=10,
        invalid_run_count=0,
        void=void,
    )


EQUAL = (
    DomainWeight(domain="F", weight=1.0),
    DomainWeight(domain="D", weight=1.0),
    DomainWeight(domain="B", weight=1.0),
)


def test_composite_is_equal_weighted_mean_of_present_domains():
    per_domain = (
        _per_domain("F", 0.6, 0.3, 0.9),
        _per_domain("D", 0.9, 0.8, 1.0),
        _per_domain("B", 0.3, 0.1, 0.5),
    )
    comp = macro_composite(
        per_domain_primary=per_domain,
        weights=EQUAL,
        condition_id="m1",
        experiment_id="M1",
        spec_hash="abc",
    )
    assert math.isclose(comp.estimate, (0.6 + 0.9 + 0.3) / 3)
    assert comp.domain == "composite"
    assert comp.ci_method == "weighted_halfwidth_propagation"
    assert comp.ci_lower is not None and comp.ci_upper is not None


def test_composite_drops_missing_domain_and_renormalizes():
    # Only D present (the D-only first run) -> composite == D estimate.
    comp = macro_composite(
        per_domain_primary=(_per_domain("D", 0.7, 0.5, 0.9),),
        weights=EQUAL,
        condition_id="m1",
        experiment_id="M1",
        spec_hash="abc",
    )
    assert math.isclose(comp.estimate, 0.7)


def test_composite_excludes_void_domain():
    per_domain = (
        _per_domain("D", 0.8, 0.6, 1.0),
        _per_domain("B", 0.0, None, None, void=True),  # void -> excluded
    )
    comp = macro_composite(
        per_domain_primary=per_domain,
        weights=EQUAL,
        condition_id="m1",
        experiment_id="M1",
        spec_hash="abc",
    )
    assert math.isclose(comp.estimate, 0.8)  # only D contributes
    assert comp.void is True  # a contributing domain was dropped due to void
