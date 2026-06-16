"""Pure, total fc-v4 failure classification (ADR-0013): derived, never stored.

Maps every graded RunResult to exactly one of passed | task_failure |
agent_failure | harness_failure | environment_failure plus one closed
subcategory, reading only the mechanical discriminators already on the record:
the trajectory's parse_failure, stop_reason, env_health, and max_tokens, the
grade's failure_reason, and the first execution leg's evidence — the plain
dicts the JSONL round-trip yields, never reconstructed dataclasses (grill Q9).
The priority-ordered, first-match-wins table is frozen with its version.

fc-v2 changes from fc-v1
-------------------------
- ``token_budget_exhausted`` (agent_failure) is a new subcategory for
  parse_failure runs where ``usage.completion_tokens >= trajectory.max_tokens``
  (the completion budget was exhausted inside the reasoning channel — a known
  behaviour of thinking models such as Qwen3-8B under the MLX server's default
  512-token limit). This is an agent limitation under declared conditions, not
  a malformed response, and must NOT be lumped with ``malformed_reply``. Old
  artifacts without the ``max_tokens`` field (``trajectory.max_tokens is None``)
  keep classifying as before.
- None-guard: ``stop_reason == "parse_failure"`` with ``parse_failure is None``
  is a harness wiring defect; fc-v1 raised AttributeError on this path. fc-v2
  classifies it as ``harness_failure/sandbox_fault`` so the function remains
  total (never raises) as advertised.

fc-v3 changes from fc-v2
-------------------------
- ``environment_failure`` is a new first-class category (peer to harness/agent/
  task failures), checked AFTER parse/harness checks and BEFORE execution
  grading. Driven by ``env_health`` / ``stop_reason == "env_unhealthy"`` record
  fields. Subcategories: ``pre_probe_failed`` | ``post_probe_failed`` |
  ``runner_flagged``. Env-free (F-set) runs and all legacy v1 artifacts are
  unaffected (``stop_reason != "env_unhealthy"`` → ``_classify_environment``
  returns None → fc-v2 chain runs unchanged). Pure/total/versioned (ADR-0013).

fc-v4 changes from fc-v3
-------------------------
- ``node_execution`` leaf: ``first_execution_evidence`` now matches the
  ``"node_execution"`` grader_id (the F-set node oracle, same evidence shape as
  ``"execution"``), so a failing node-F run classifies as ``agent_failure /
  oracle_red`` instead of the catch-all ``other_miss`` (Part E.1).
- ``budget_exhausted`` (agent_failure): a NEW subcategory for runs that hit a
  budget cap — ``stop_reason in {safety_cap, max_rounds}`` or the
  ``safety_cap_bound`` / ``max_rounds_bound`` flags. It outranks the row-1
  ``passed`` short-circuit (a graded-pass that was capped is NOT a reliable
  pass — consistent with §D.1) and the oracle-status rows. Legacy ``max_steps``
  keeps its ``step_exhaustion`` bucket (a truncation, not a budget cap).
  ``max_rounds_bound`` is read via direct attribute access on the Trajectory
  dataclass (a real field as of item 002); old records without the field are
  unaffected via the dataclass default False (Part E.2/E.3).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.records.trajectory import NO_CHOICES_ERROR, PROVIDER_ERROR

CLASSIFIER_VERSION = "fc-v4"

Category = Literal[
    "passed",
    "task_failure",
    "agent_failure",
    "harness_failure",
    "environment_failure",  # fc-v3: env-validity failure (D21), peer to the rest
]

# Closed at 20 values (fc-v4 adds budget_exhausted; fc-v3 added pre_probe_failed,
# post_probe_failed, runner_flagged); versioned with the classifier.  Downstream
# Weeks 9-10 mining joins on (classifier_version, category, subcategory) (ADR-0013).
Subcategory = Literal[
    "provider_response",
    "malformed_reply",
    "token_budget_exhausted",
    "missing_final_state",
    "sandbox_fault",
    "verdict_missing",
    "tree_collision",
    "foreign_verdict",
    "oracle_empty",
    "forbidden_action",
    "step_limit_exceeded",
    "step_exhaustion",
    "budget_exhausted",  # fc-v4: run hit a budget cap (safety_cap / max_rounds)
    "oracle_timeout",
    "oracle_red",
    "oracle_error",
    "other_miss",
    # fc-v3 environment_failure subcategories (D21/D28 §6)
    "pre_probe_failed",
    "post_probe_failed",
    "runner_flagged",
]


@dataclass(frozen=True, kw_only=True)
class RunClassification:
    """One run's derived task/agent/harness interpretation (never a grade)."""

    category: Category
    subcategory: Subcategory | None  # None iff category == "passed"
    detail: str  # one-line evidence citation
    classifier_version: str = CLASSIFIER_VERSION


def _one_line(text: object, limit: int = 200) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _classification(
    category: Category, subcategory: Subcategory | None, detail: object
) -> RunClassification:
    return RunClassification(
        category=category, subcategory=subcategory, detail=_one_line(detail)
    )


_CAP_STOP_REASONS = frozenset({"safety_cap", "max_rounds"})


def _cap_bound(run: RunResult) -> bool:
    """fc-v4: did the run hit a budget cap? (safety_cap / max_rounds, §D.1/§E).

    Reads the safety_cap_bound and max_rounds_bound flags (both real Trajectory
    fields as of item 002) and the two cap stop reasons. Legacy max_steps is a
    TRUNCATION (step_exhaustion), NOT a budget cap (D2), so it is deliberately
    excluded here.
    """
    traj = run.trajectory
    return (
        traj.safety_cap_bound
        or traj.max_rounds_bound
        or traj.stop_reason in _CAP_STOP_REASONS
    )


def first_execution_evidence(
    evidence: Mapping[str, Any], grader_id: object
) -> Mapping[str, Any] | None:
    """The first execution leg's evidence, in declared order (grill Q9; fc-v4 node).

    Walks the plain dicts the JSONL round-trip yields: the grade's own
    evidence when it is the execution grader's, recursing `sub_results`
    entries (each a {"grader_id", "evidence", ...} dict) for all_of —
    including nested all_of, walked in declared order.
    """
    if grader_id in ("execution", "node_execution"):
        return evidence
    if grader_id != "all_of":
        return None
    subs = evidence.get("sub_results")
    if not isinstance(subs, Sequence) or isinstance(subs, (str, bytes)):
        return None
    for sub in subs:
        if not isinstance(sub, Mapping):
            continue
        sub_evidence = sub.get("evidence")
        if not isinstance(sub_evidence, Mapping):
            continue
        found = first_execution_evidence(sub_evidence, sub.get("grader_id"))
        if found is not None:
            return found
    return None


def classify_run(run: RunResult) -> RunClassification:
    """fc-v4: priority-ordered, first-match-wins, total — never raises."""
    cap_bound = _cap_bound(run)
    if run.grade.passed and not cap_bound:  # row 1; fc-v4 E.3: capped ≠ "passed"
        return _classification("passed", None, "grade.passed")
    parse_failure = run.trajectory.parse_failure
    if run.trajectory.stop_reason == "parse_failure" and parse_failure is None:
        # None-guard: harness wiring defect — the loop set stop_reason=parse_failure
        # but did not record the ParseFailure object.  Never AttributeError.
        return _classification(
            "harness_failure",
            "sandbox_fault",
            "stop_reason=parse_failure but parse_failure record is None "
            "(harness wiring defect)",
        )
    if parse_failure is not None:  # rows 2-3 (+ fc-v2 token_budget_exhausted)
        return _classify_parse_failure(parse_failure.error, run)
    env = _classify_environment(run)  # fc-v3: after parse/harness, before execution
    if env is not None:
        return env
    exec_ev = first_execution_evidence(run.grade.evidence, run.grade.grader_id)
    early = _classify_execution_evidence(exec_ev)  # rows 4-9
    if early is not None:
        return early
    return _classify_grade_and_budget(run, exec_ev, cap_bound)  # rows 10-16


def _classify_environment(run: RunResult) -> RunClassification | None:
    """fc-v3 environment_failure (D21): driven by env_health / stop_reason.

    Pure/total: returns None when the run carries no env-failure signal, so the
    fc-v2 chain runs unchanged for env-free (F-set) runs and all legacy artifacts
    (which have stop_reason != 'env_unhealthy' and env_health is None)."""
    if run.trajectory.stop_reason != "env_unhealthy":
        return None
    # NOTE: the runner only stops as env_unhealthy when the POST-probe is unhealthy
    # (loop.py). So a run reaching here always had post_healthy=False; the
    # pre_probe_failed branch below therefore fires only when BOTH probes were
    # unhealthy (pre AND post). A pre-only failure that later recovers completes
    # naturally and never reaches this classifier.
    health = run.trajectory.env_health
    if health is None:
        return _classification(
            "environment_failure",
            "runner_flagged",
            "stop_reason=env_unhealthy with no EnvHealth record",
        )
    if not health.pre_healthy:
        return _classification(
            "environment_failure",
            "pre_probe_failed",
            f"pre-probe unhealthy (pre_status={health.pre_status})",
        )
    return _classification(
        "environment_failure",
        "post_probe_failed",
        f"post-probe unhealthy (post_status={health.post_status})",
    )


def _classify_parse_failure(error: str, run: RunResult) -> RunClassification:
    if error == NO_CHOICES_ERROR:  # row 2: the provider delivered no completion
        return _classification(
            "harness_failure", "provider_response", f"parse_failure: {error}"
        )
    if error == PROVIDER_ERROR:  # fc-v3: /chat/completions raised (status/transport)
        # Same honest bucket as NO_CHOICES_ERROR — the provider delivered no usable
        # completion. The status + body snippet live in ParseFailure.raw; surface
        # them so a context-length 400 vs a 5xx is legible in the taxonomy detail.
        pf = run.trajectory.parse_failure
        return _classification(
            "harness_failure",
            "provider_response",
            f"provider request failed: {pf.raw if pf is not None else ''}",
        )
    # fc-v2 row 3a: completion budget exhausted in the reasoning channel.
    # completion_tokens >= max_tokens means the provider stopped the stream at
    # the explicit budget ceiling.  Only applicable when max_tokens is recorded
    # (trajectory.max_tokens is not None); old artifacts without the field keep
    # classifying as malformed_reply (row 3b) for backward compatibility.
    max_tokens = run.trajectory.max_tokens
    if max_tokens is not None and run.trajectory.usage.completion_tokens >= max_tokens:
        return _classification(
            "agent_failure",
            "token_budget_exhausted",
            f"parse_failure: completion_tokens={run.trajectory.usage.completion_tokens}"
            f" >= max_tokens={max_tokens}",
        )
    # row 3b: the model emitted an unparseable payload (envelope was well-formed)
    return _classification(
        "agent_failure", "malformed_reply", f"parse_failure: {error}"
    )


_ERROR_KIND_ROWS: Mapping[str, tuple[Category, Subcategory]] = {
    "harness": ("harness_failure", "sandbox_fault"),  # row 5
    "verdict_missing": ("harness_failure", "verdict_missing"),  # row 6
    "tree_collision": ("agent_failure", "tree_collision"),  # row 7
}


def _classify_execution_evidence(
    exec_ev: Mapping[str, Any] | None,
) -> RunClassification | None:
    if exec_ev is None:
        return None
    execution = exec_ev.get("execution")
    if execution == "not_run":  # row 4: the runner always seeds final_state
        return _classification(
            "harness_failure",
            "missing_final_state",
            f"execution=not_run reason={exec_ev.get('reason')!r}",
        )
    if execution == "error":  # rows 5-8
        return _classify_execution_error(exec_ev)
    if execution == "run" and exec_ev.get("status") == "no_tests":  # row 9
        return _classification(
            "task_failure",
            "oracle_empty",
            f"oracle suite status=no_tests counts={exec_ev.get('counts')!r}",
        )
    return None


def _classify_execution_error(exec_ev: Mapping[str, Any]) -> RunClassification:
    error = exec_ev.get("execution_error")
    error_map = error if isinstance(error, Mapping) else {}
    kind = error_map.get("kind")
    # Row 8 closes the branch by construction (grill Q1): the kind is an OPEN
    # string, so any unrecognized (foreign) kind is a verdict-plumbing fault —
    # harness, never an agent miss. Non-string kinds fall through likewise.
    named = _ERROR_KIND_ROWS.get(kind) if isinstance(kind, str) else None
    category, subcategory = (
        named
        if named is not None
        else (
            "harness_failure",
            "foreign_verdict",
        )
    )
    return _classification(
        category,
        subcategory,
        f"execution_error kind={kind!r} detail={error_map.get('detail')!r}",
    )


_SUITE_STATUS_ROWS: Mapping[str, Subcategory] = {
    "timeout": "oracle_timeout",  # row 13
    "failed": "oracle_red",  # row 14
    "error": "oracle_error",  # row 15
}


def _classify_grade_and_budget(
    run: RunResult, exec_ev: Mapping[str, Any] | None, cap_bound: bool
) -> RunClassification:
    reason = run.grade.failure_reason
    if reason == "forbidden_action":  # row 10
        return _classification(
            "agent_failure", "forbidden_action", "failure_reason=forbidden_action"
        )
    if reason == "step_limit_exceeded":  # row 11
        return _classification(
            "agent_failure",
            "step_limit_exceeded",
            "failure_reason=step_limit_exceeded",
        )
    if cap_bound:  # fc-v4 E.2: budget cap (safety_cap / max_rounds) outranks oracle
        return _classification(
            "agent_failure",
            "budget_exhausted",
            f"budget cap hit (stop_reason={run.trajectory.stop_reason!r}, "
            f"safety_cap_bound={run.trajectory.safety_cap_bound})",
        )
    if run.trajectory.stop_reason == "max_steps":  # row 12 outranks rows 13-15
        return _classification(
            "agent_failure", "step_exhaustion", "stop_reason=max_steps"
        )
    if exec_ev is not None and exec_ev.get("execution") == "run":  # rows 13-15
        status = exec_ev.get("status")
        named = _SUITE_STATUS_ROWS.get(status) if isinstance(status, str) else None
        if named is not None:
            return _classification(
                "agent_failure",
                named,
                f"oracle suite status={status} counts={exec_ev.get('counts')!r}",
            )
    return _classification(  # row 16: total without an unknown bucket
        "agent_failure",
        "other_miss",
        "failed with no mapped discriminator "
        f"(grader_id={run.grade.grader_id!r}, "
        f"stop_reason={run.trajectory.stop_reason!r})",
    )
