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
