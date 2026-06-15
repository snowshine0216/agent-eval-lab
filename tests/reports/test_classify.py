"""fc-v1 mapping table: one dedicated test per row (item 004 criterion 7)."""

from typing import get_args

from agent_eval_lab.records.env_health import EnvHealth
from agent_eval_lab.records.grade import FailureCategory, GradeResult, RunResult
from agent_eval_lab.records.trajectory import (
    NO_CHOICES_ERROR,
    ParseFailure,
    Trajectory,
    Usage,
)
from agent_eval_lab.reports.classify import (
    CLASSIFIER_VERSION,
    RunClassification,
    Subcategory,
    classify_run,
    first_execution_evidence,
)


def _run(
    *,
    passed=False,
    grader_id="execution",
    evidence=None,
    failure_reason=None,
    stop_reason="completed",
    parse_error=None,
    completion_tokens=5,
    max_tokens=None,
    safety_cap_bound=False,
) -> RunResult:
    """Synthetic RunResult mimicking the JSONL round-trip (plain dicts).

    max_tokens mirrors the fc-v2 field added to RunResult for the
    token_budget_exhausted subcategory; None reproduces pre-fc-v2 artifacts.
    """
    return RunResult(
        task_id="cr-001",
        condition_id="deepseek:deepseek-v4-pro",
        run_index=0,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(
                prompt_tokens=10,
                completion_tokens=completion_tokens,
                latency_s=0.1,
            ),
            run_index=0,
            stop_reason=stop_reason,
            parse_failure=(
                None
                if parse_error is None
                else ParseFailure(raw="{}", error=parse_error)
            ),
            final_state={"files": {}},
            max_tokens=max_tokens,
            safety_cap_bound=safety_cap_bound,
        ),
        grade=GradeResult(
            grader_id=grader_id,
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence=evidence if evidence is not None else {},
            failure_reason=failure_reason,
        ),
    )


def _exec_run_evidence(status, counts=None):
    return {
        "execution": "run",
        "status": status,
        "exit_code": 1,
        "counts": counts or {"passed": 1, "failed": 2, "errors": 0, "skipped": 0},
        "tests": [],
        "stdout": "",
        "stderr": "",
        "execution_hash": "h",
        "displaced_paths": [],
    }


def _exec_error_evidence(kind, detail="boom"):
    return {
        "execution": "error",
        "execution_error": {"kind": kind, "detail": detail},
        "execution_hash": "h",
    }


def _is(c: RunClassification, category: str, subcategory) -> None:
    assert (c.category, c.subcategory) == (category, subcategory)
    assert c.classifier_version == CLASSIFIER_VERSION
    assert "\n" not in c.detail


# Row 1 — passed wins first, even over a recorded parse_failure (grill Q8).


def test_row_01_passed() -> None:
    _is(classify_run(_run(passed=True)), "passed", None)


def test_row_01_passed_wins_over_recorded_parse_failure() -> None:
    run = _run(passed=True, parse_error="unparseable", stop_reason="parse_failure")
    _is(classify_run(run), "passed", None)


# Rows 2-3 — parse failures split on the shared loop constant (grill Q3).


def test_row_02_empty_choices_parse_failure_is_harness() -> None:
    run = _run(parse_error=NO_CHOICES_ERROR, stop_reason="parse_failure")
    _is(classify_run(run), "harness_failure", "provider_response")


def test_row_03_any_other_parse_failure_is_agent() -> None:
    run = _run(
        parse_error="assistant message has neither content nor tool_calls",
        stop_reason="parse_failure",
    )
    _is(classify_run(run), "agent_failure", "malformed_reply")


# Rows 4-8 — execution not_run / error branch.


def test_row_04_not_run_missing_final_state_is_harness() -> None:
    ev = {"execution": "not_run", "reason": "missing_final_state"}
    _is(
        classify_run(_run(evidence=ev)),
        "harness_failure",
        "missing_final_state",
    )


def test_row_05_error_kind_harness_is_sandbox_fault() -> None:
    run = _run(evidence=_exec_error_evidence("harness"))
    _is(classify_run(run), "harness_failure", "sandbox_fault")


def test_row_06_error_kind_verdict_missing_is_harness() -> None:
    ev = {
        "execution": "error",
        "execution_error": {"kind": "verdict_missing", "execution_hash": "h"},
        "execution_hash": "h",
    }
    _is(classify_run(_run(evidence=ev)), "harness_failure", "verdict_missing")


def test_row_07_error_kind_tree_collision_is_agent() -> None:
    detail = "canonical-prefix collision: agent 'Tests/test_app.py' vs oracle"
    run = _run(evidence=_exec_error_evidence("tree_collision", detail))
    c = classify_run(run)
    _is(c, "agent_failure", "tree_collision")
    assert "Tests/test_app.py" in c.detail  # cites the colliding pair


def test_row_08_error_any_other_kind_is_foreign_verdict() -> None:
    # Grill Q1: a foreign value at a colliding hash carries its OWN kind
    # (e.g. a JudgeError's "transport"); the error branch closes by fallback.
    for kind in ("unknown", "transport", "parse", "weird-future-kind"):
        run = _run(evidence=_exec_error_evidence(kind))
        _is(classify_run(run), "harness_failure", "foreign_verdict")


def test_row_08_non_string_kind_is_foreign_verdict_not_a_crash() -> None:
    run = _run(evidence=_exec_error_evidence(["not", "hashable"]))
    _is(classify_run(run), "harness_failure", "foreign_verdict")


# Row 9 — empty oracle: the only mechanical post-conformance task defect.


def test_row_09_suite_no_tests_is_task_failure() -> None:
    ev = _exec_run_evidence("no_tests", {"passed": 0, "failed": 0})
    _is(classify_run(_run(evidence=ev)), "task_failure", "oracle_empty")


# Rows 10-11 — policy breaches from the grade taxonomy.


def test_row_10_forbidden_action_is_agent() -> None:
    run = _run(grader_id="trajectory", failure_reason="forbidden_action")
    _is(classify_run(run), "agent_failure", "forbidden_action")


def test_row_11_step_limit_exceeded_is_agent() -> None:
    run = _run(grader_id="trajectory", failure_reason="step_limit_exceeded")
    _is(classify_run(run), "agent_failure", "step_limit_exceeded")


# Row 12 — budget truncation outranks oracle statuses (grill Q13).


def test_row_12_max_steps_outranks_red_oracle() -> None:
    run = _run(evidence=_exec_run_evidence("failed"), stop_reason="max_steps")
    _is(classify_run(run), "agent_failure", "step_exhaustion")


# Rows 13-15 — oracle suite statuses on a full (untruncated) attempt.


def test_row_13_suite_timeout_is_oracle_timeout() -> None:
    ev = _exec_run_evidence("timeout", {"passed": 0, "failed": 0})
    _is(classify_run(_run(evidence=ev)), "agent_failure", "oracle_timeout")


def test_row_14_suite_failed_is_oracle_red() -> None:
    c = classify_run(_run(evidence=_exec_run_evidence("failed")))
    _is(c, "agent_failure", "oracle_red")
    assert "failed" in c.detail  # cites the suite counts/status


def test_row_15_suite_error_is_oracle_error() -> None:
    _is(
        classify_run(_run(evidence=_exec_run_evidence("error"))),
        "agent_failure",
        "oracle_error",
    )


# Row 16 — fallback: failed with no mapped discriminator.


def test_row_16_fallback_other_miss() -> None:
    run = _run(grader_id="final_state", evidence={"diff": []})
    _is(classify_run(run), "agent_failure", "other_miss")


# exec_ev walk: nested AllOf evidence, plain dicts (grill Q9).


def test_exec_evidence_found_through_nested_all_of_dicts() -> None:
    evidence = {
        "sub_results": [
            {"grader_id": "final_state", "passed": True, "evidence": {"diff": []}},
            {
                "grader_id": "all_of",
                "passed": False,
                "evidence": {
                    "sub_results": [
                        {
                            "grader_id": "execution",
                            "passed": False,
                            "evidence": _exec_run_evidence("failed"),
                        }
                    ]
                },
            },
        ]
    }
    run = _run(grader_id="all_of", evidence=evidence)
    _is(classify_run(run), "agent_failure", "oracle_red")


def test_first_execution_leg_wins_in_declared_order() -> None:
    evidence = {
        "sub_results": [
            {
                "grader_id": "execution",
                "passed": False,
                "evidence": _exec_run_evidence("failed"),
            },
            {
                "grader_id": "execution",
                "passed": False,
                "evidence": _exec_run_evidence("timeout"),
            },
        ]
    }
    found = first_execution_evidence(evidence, "all_of")
    assert found is not None and found["status"] == "failed"


def test_no_execution_leg_returns_none() -> None:
    assert first_execution_evidence({"diff": []}, "final_state") is None


# Criterion 8 — the grade-level taxonomy is untouched.


def test_failure_category_member_set_is_unchanged() -> None:
    assert set(get_args(FailureCategory)) == {
        "malformed_call",
        "schema_violation",
        "wrong_tool",
        "wrong_args",
        "missing_call",
        "extra_call",
        "order_mismatch",
        "forbidden_action",
        "step_limit_exceeded",
    }


def test_subcategory_vocabulary_is_closed_at_15() -> None:
    # Kept as a historical marker; the live count is asserted by
    # test_subcategory_vocabulary_is_closed_at_19_after_fc_v3.
    pass


# fc-v2 additions ──────────────────────────────────────────────────────────────


def test_classifier_version_is_fc_v3() -> None:
    """The classifier version label is fc-v3 after the env_failure bump (item 001)."""
    assert CLASSIFIER_VERSION == "fc-v3"


def test_token_budget_exhausted_classification() -> None:
    """parse_failure with completion_tokens >= declared max_tokens classifies
    as agent_failure/token_budget_exhausted, not malformed_reply."""
    run = _run(
        parse_error="assistant message has neither content nor tool_calls",
        stop_reason="parse_failure",
        completion_tokens=4096,
        max_tokens=4096,
    )
    _is(classify_run(run), "agent_failure", "token_budget_exhausted")


def test_token_budget_exhausted_at_exactly_budget() -> None:
    """Boundary: completion_tokens == max_tokens → token_budget_exhausted."""
    run = _run(
        parse_error="assistant message has neither content nor tool_calls",
        stop_reason="parse_failure",
        completion_tokens=512,
        max_tokens=512,
    )
    _is(classify_run(run), "agent_failure", "token_budget_exhausted")


def test_token_budget_not_exhausted_falls_through_to_malformed_reply() -> None:
    """completion_tokens < max_tokens: not budget-exhaustion, still malformed_reply."""
    run = _run(
        parse_error="assistant message has neither content nor tool_calls",
        stop_reason="parse_failure",
        completion_tokens=100,
        max_tokens=4096,
    )
    _is(classify_run(run), "agent_failure", "malformed_reply")


def test_parse_failure_no_max_tokens_field_classifies_as_before() -> None:
    """Old artifacts without max_tokens on the run record keep classifying as
    malformed_reply (no KeyError, no AttributeError)."""
    run = _run(
        parse_error="assistant message has neither content nor tool_calls",
        stop_reason="parse_failure",
        # no max_tokens kwarg → uses old default (None)
    )
    _is(classify_run(run), "agent_failure", "malformed_reply")


def test_parse_failure_none_record_classifies_as_harness_failure() -> None:
    """None-guard: stop_reason=parse_failure with parse_failure field None
    must NOT AttributeError — classify as harness_failure/sandbox_fault."""
    run = _run(stop_reason="parse_failure", parse_error=None)
    # parse_error=None => trajectory.parse_failure is None
    # but stop_reason is "parse_failure" — harness wiring defect
    c = classify_run(run)
    assert c.category == "harness_failure"
    # classify_run must never raise


# fc-v3 additions ──────────────────────────────────────────────────────────────


def _env_run(*, stop_reason="env_unhealthy", env_health=None, passed=False):
    """A run carrying env-health fields, for fc-v3 environment_failure rows."""
    return RunResult(
        task_id="b-001",
        condition_id="deepseek:deepseek-v4-pro",
        run_index=0,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
            run_index=0,
            stop_reason=stop_reason,
            final_state={"files": {}},
            env_health=env_health,
        ),
        grade=GradeResult(
            grader_id="execution",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=None,
        ),
    )


def test_fc_v3_version_label() -> None:
    assert CLASSIFIER_VERSION == "fc-v3"


def test_environment_failure_is_a_category() -> None:
    from typing import get_args

    from agent_eval_lab.reports.classify import Category

    assert "environment_failure" in get_args(Category)


def test_env_unhealthy_post_probe_failed() -> None:
    health = EnvHealth(
        pre_healthy=True, post_healthy=False, pre_status=200, post_status=503
    )
    run = _env_run(stop_reason="env_unhealthy", env_health=health)
    c = classify_run(run)
    assert (c.category, c.subcategory) == ("environment_failure", "post_probe_failed")


def test_env_unhealthy_pre_probe_failed() -> None:
    health = EnvHealth(
        pre_healthy=False, post_healthy=False, pre_status=503, post_status=503
    )
    run = _env_run(stop_reason="env_unhealthy", env_health=health)
    c = classify_run(run)
    assert (c.category, c.subcategory) == ("environment_failure", "pre_probe_failed")


def test_env_unhealthy_runner_flagged_without_health_record() -> None:
    # stop_reason flags env failure but no EnvHealth was recorded.
    run = _env_run(stop_reason="env_unhealthy", env_health=None)
    c = classify_run(run)
    assert (c.category, c.subcategory) == ("environment_failure", "runner_flagged")


def test_passed_run_with_unhealthy_post_probe_still_passes() -> None:
    # Row 1 (passed) still wins first — a passed grade is not an env failure.
    health = EnvHealth(
        pre_healthy=True, post_healthy=False, pre_status=200, post_status=503
    )
    run = _env_run(stop_reason="env_unhealthy", env_health=health, passed=True)
    assert classify_run(run).category == "passed"


def test_env_check_runs_after_parse_but_before_execution_grading() -> None:
    # A parse failure still classifies as parse failure even if env is unhealthy
    # (parse/harness checks precede the env check; §6 ordering).
    run = RunResult(
        task_id="b-001",
        condition_id="c",
        run_index=0,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
            run_index=0,
            stop_reason="parse_failure",
            parse_failure=ParseFailure(raw="{}", error=NO_CHOICES_ERROR),
            env_health=EnvHealth(pre_healthy=True, post_healthy=False),
        ),
        grade=GradeResult(grader_id="execution", passed=False, score=0.0, evidence={}),
    )
    # NO_CHOICES_ERROR -> harness/provider_response (parse check wins over env).
    c = classify_run(run)
    assert c.category == "harness_failure"


def test_subcategory_vocabulary_is_closed_at_19_after_fc_v3() -> None:
    """fc-v3 adds pre_probe_failed | post_probe_failed | runner_flagged."""
    assert len(get_args(Subcategory)) == 19
    for sub in ("pre_probe_failed", "post_probe_failed", "runner_flagged"):
        assert sub in get_args(Subcategory)


def test_provider_error_maps_to_harness_provider_response() -> None:
    """item 008: a PROVIDER_ERROR parse_failure (a /chat/completions call that
    raised — e.g. a context-length 400) classifies as harness/provider_response,
    the same honest bucket as NO_CHOICES_ERROR (no usable completion delivered)."""
    from agent_eval_lab.records.trajectory import PROVIDER_ERROR

    run = _run(stop_reason="parse_failure", parse_error=PROVIDER_ERROR)
    c = classify_run(run)
    assert c.category == "harness_failure"
    assert c.subcategory == "provider_response"


# fc-v4 Row E.1 — node_execution leaf fix ─────────────────────────────────────


def _node_exec_run_evidence(status, counts=None):
    # The node_execution grader emits the SAME evidence shape as the execution
    # grader (graders/node_execution.py::_interpret).
    return {
        "execution": "run",
        "status": status,
        "exit_code": 1,
        "counts": counts or {"passed": 1, "failed": 4, "errors": 0, "skipped": 0},
        "tests": [],
        "stdout": "",
        "stderr": "",
        "execution_hash": "h",
        "displaced_paths": [],
    }


def test_e1_failing_node_execution_leg_is_oracle_red() -> None:
    # Real node-F shape: top grade is all_of with one node_execution sub-result.
    evidence = {
        "sub_results": [
            {
                "grader_id": "node_execution",
                "passed": False,
                "failure_reason": None,
                "evidence": _node_exec_run_evidence("failed"),
            }
        ]
    }
    run = _run(grader_id="all_of", evidence=evidence)
    _is(classify_run(run), "agent_failure", "oracle_red")


def test_e1_top_level_node_execution_grader_is_found() -> None:
    # A top-level node_execution grade (not wrapped in all_of) is also matched.
    run = _run(grader_id="node_execution", evidence=_node_exec_run_evidence("failed"))
    _is(classify_run(run), "agent_failure", "oracle_red")


def test_e1_first_execution_evidence_matches_node_execution() -> None:
    ev = _node_exec_run_evidence("failed")
    assert first_execution_evidence(ev, "node_execution") is ev


# fc-v4 Rows E.2 + E.3 — budget-cap override + row-1 guard ──────────────────────


def test_e3_passed_but_safety_cap_bound_is_budget_exhausted() -> None:
    # Row-1 guard: a graded-pass that was budget-capped is NOT "passed".
    run = _run(passed=True, safety_cap_bound=True)
    _is(classify_run(run), "agent_failure", "budget_exhausted")


def test_e3_passed_but_max_rounds_stop_is_budget_exhausted() -> None:
    run = _run(passed=True, stop_reason="max_rounds")
    _is(classify_run(run), "agent_failure", "budget_exhausted")


def test_e2_failing_safety_cap_run_is_budget_exhausted() -> None:
    # A failing run that hit the safety cap outranks its red oracle.
    run = _run(evidence=_exec_run_evidence("failed"), stop_reason="safety_cap")
    _is(classify_run(run), "agent_failure", "budget_exhausted")


def test_e2_failing_safety_cap_bound_flag_is_budget_exhausted() -> None:
    run = _run(evidence=_exec_run_evidence("failed"), safety_cap_bound=True)
    _is(classify_run(run), "agent_failure", "budget_exhausted")


def test_e2_failing_max_rounds_run_is_budget_exhausted() -> None:
    run = _run(evidence=_exec_run_evidence("failed"), stop_reason="max_rounds")
    _is(classify_run(run), "agent_failure", "budget_exhausted")


def test_e2_legacy_max_steps_still_step_exhaustion() -> None:
    # D2: legacy max_steps keeps its truncation bucket (backward compatible).
    run = _run(evidence=_exec_run_evidence("failed"), stop_reason="max_steps")
    _is(classify_run(run), "agent_failure", "step_exhaustion")


def test_e3_passed_uncapped_still_passes() -> None:
    _is(classify_run(_run(passed=True)), "passed", None)
