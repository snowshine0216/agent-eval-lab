from agent_eval_lab.metrics.pareto import ParetoPoint, pareto_frontier


def test_frontier_keeps_higher_success_lower_cost():
    pts = (
        ParetoPoint(condition_id="cheap_good", success=0.9, cost=1.0),
        ParetoPoint(condition_id="dear_good", success=0.9, cost=5.0),   # dominated
        # frontier (cheapest)
        ParetoPoint(condition_id="cheap_bad", success=0.4, cost=0.5),
        ParetoPoint(condition_id="dear_bad", success=0.4, cost=9.0),    # dominated
    )
    frontier = pareto_frontier(pts)
    ids = {p.condition_id for p in frontier}
    assert ids == {"cheap_good", "cheap_bad"}


def test_frontier_handles_ties_keeps_one_or_both_non_dominated():
    pts = (
        ParetoPoint(condition_id="a", success=0.8, cost=2.0),
        # identical -> neither dominates
        ParetoPoint(condition_id="b", success=0.8, cost=2.0),
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
