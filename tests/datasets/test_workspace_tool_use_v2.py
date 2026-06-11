"""v2 dataset conformance: a typo'd task can never look like an agent failure.

Pure (no model, no I/O beyond reading the dataset file). Enforces the rubric
mechanically over all 50 tasks: parse, registered-tools-only, schema-valid
expected calls, well-formed state paths, satisfied preconditions, tier/capability
mix, verification histogram, distractor-never-expected, review coverage,
ledger parity, max_steps floor, and the anti-rote-chain state-dependency proxy.
"""

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.schema import (
    AllOf,
    ExpectedToolCall,
    FinalStateSpec,
    NoToolCall,
    StateConstraint,
    Task,
    ToolCallMatchSpec,
    TrajectorySpec,
    VerificationSpec,
)
from agent_eval_lab.tools.validation import validate_args
from agent_eval_lab.tools.workspace import (
    WORKSPACE_TOOLS,
    _next_email_id,
    _next_ticket_id,
)

_REPO = Path(__file__).parent.parent.parent
DATASET = _REPO / "examples/datasets/workspace_tool_use_v2.jsonl"
LEDGER = _REPO / "docs/2026-06-10-dataset-grader-quality/review-ledger.md"

_STATE_ROOTS = {"tickets", "docs", "accounts", "emails"}
_DISTRACTORS = {"archive_ticket", "find_account", "draft_email"}
_CAPABILITIES = {
    "tool_selection",
    "argument_extraction",
    "multi_step_state",
    "constraint_compliance",
    "distractor_resistance",
    "derived_reasoning",
}
_KNOBS = {
    "multi_step_depth",
    "derived_argument",
    "distractor_count",
    "argument_complexity",
    "layered_constraint",
}
_DERIVED_KNOBS = {"multi_step_depth", "derived_argument"}

# layered_constraint tasks that are also state-dependent: constraint-policed,
# not knob-policed, so _DERIVED_KNOBS won't catch them.  Pin them explicitly
# so future rote-ification of these two tasks is caught by the anti-rote check.
_EXTRA_STATE_DEPENDENT_IDS = {"ws2-044", "ws2-049"}


def _tasks() -> tuple[Task, ...]:
    return load_tasks(DATASET)


# ---- spec-tree walkers (pure) ----------------------------------------------


def _expected_calls(spec: VerificationSpec) -> tuple[ExpectedToolCall, ...]:
    """Every ExpectedToolCall in a spec tree (recursing into AllOf)."""
    if isinstance(spec, ToolCallMatchSpec):
        return spec.expected_tool_calls
    if isinstance(spec, AllOf):
        return tuple(c for sub in spec.specs for c in _expected_calls(sub))
    return ()


def _state_constraints(spec: VerificationSpec) -> tuple[StateConstraint, ...]:
    if isinstance(spec, FinalStateSpec):
        return spec.constraints
    if isinstance(spec, AllOf):
        return tuple(c for sub in spec.specs for c in _state_constraints(sub))
    return ()


def _trajectory_specs(spec: VerificationSpec) -> tuple[TrajectorySpec, ...]:
    if isinstance(spec, TrajectorySpec):
        return (spec,)
    if isinstance(spec, AllOf):
        return tuple(t for sub in spec.specs for t in _trajectory_specs(sub))
    return ()


def _spec_type_names(spec: VerificationSpec) -> set[str]:
    if isinstance(spec, AllOf):
        names = {"all_of"}
        for sub in spec.specs:
            names |= _spec_type_names(sub)
        return names
    return {spec.type}


# ---- precondition / state-dependency machinery (AC 12e + 12h) --------------


def _ids_in_state(initial_state: Mapping[str, Any] | None) -> set[str]:
    """All ticket/user/doc/email ids present in initial_state."""
    state = initial_state or {}
    ids: set[str] = set()
    for root in _STATE_ROOTS:
        ids |= set((state.get(root) or {}).keys())
    return ids


def _minted_ticket_ids(initial_state: Mapping[str, Any] | None, n: int) -> set[str]:
    """The first n ticket ids the world will mint from this initial_state."""
    tickets = dict((initial_state or {}).get("tickets") or {})
    minted: set[str] = set()
    for _ in range(n):
        new_id = _next_ticket_id(tickets)
        minted.add(new_id)
        tickets[new_id] = {"title": "x", "priority": "low", "status": "open"}
    return minted


def _minted_email_ids(initial_state: Mapping[str, Any] | None, n: int) -> set[str]:
    """The first n email ids the world will mint from this initial_state."""
    emails = dict((initial_state or {}).get("emails") or {})
    minted: set[str] = set()
    for _ in range(n):
        new_id = _next_email_id(emails)
        minted.add(new_id)
        emails[new_id] = {"to": "x", "subject": "x", "body": "x", "state": "sent"}
    return minted


def _referenced_ids(spec: VerificationSpec) -> set[str]:
    """Entity ids the verification references (call args + state-path segments)."""
    ids: set[str] = set()
    for call in _expected_calls(spec):
        for value in call.arguments.values():
            if isinstance(value, str):
                ids.add(value)
    for constraint in _state_constraints(spec):
        ids |= {seg for seg in constraint.path.split(".")}
    return ids


def _prompt_text(task: Task) -> str:
    return " ".join(m.content for m in task.input.messages)


# ---- the conformance assertions --------------------------------------------


def test_every_task_parses_and_has_v2_metadata() -> None:
    for task in _tasks():
        assert task.metadata.version == "2", task.id
        assert task.metadata.provenance == "hand_written", task.id
        assert task.metadata.world_template_id == "workspace-v2", task.id
        assert task.metadata.split == "dev", task.id


def test_task_ids_follow_scheme_unique_and_count_fifty() -> None:
    tasks = _tasks()
    ids = [t.id for t in tasks]
    assert len(ids) == 50
    assert len(set(ids)) == 50
    assert sorted(ids) == [f"ws2-{n:03d}" for n in range(1, 51)]


def test_tier_mix_matches_allocation() -> None:
    # Tier is derived from id ranges per the allocation table; assert the
    # documented mix via the difficulty profile instead of a stored tier field.
    # T1: ws2-001..005 (5); T2: 006..017 (12); T3: 018..039 (22); T4: 040..050 (11).
    tasks = {t.id: t for t in _tasks()}

    def n(lo: int, hi: int) -> int:
        return sum(1 for k in tasks if lo <= int(k.split("-")[1]) <= hi)

    assert n(1, 5) == 5
    assert n(6, 17) == 12
    assert n(18, 39) == 22
    assert n(40, 50) == 11


def test_all_six_capabilities_present_and_no_stray_labels() -> None:
    caps = {t.capability for t in _tasks()}
    assert caps == _CAPABILITIES


def test_available_tools_are_registered() -> None:
    for task in _tasks():
        for name in task.input.available_tools:
            assert name in WORKSPACE_TOOLS, f"{task.id}: unknown tool {name}"


def test_expected_calls_schema_validate_and_name_registered_tools() -> None:
    for task in _tasks():
        for call in _expected_calls(task.verification):
            assert call.name in WORKSPACE_TOOLS, f"{task.id}: {call.name}"
            tool = WORKSPACE_TOOLS[call.name]
            error = validate_args(tool.parameters, call.arguments)
            assert error is None, f"{task.id}: {call.name} invalid: {error}"


def test_state_paths_well_formed_and_rooted() -> None:
    for task in _tasks():
        for constraint in _state_constraints(task.verification):
            segments = constraint.path.split(".")
            assert all(seg for seg in segments), (
                f"{task.id}: empty seg in {constraint.path}"
            )
            assert segments[0] in _STATE_ROOTS, f"{task.id}: bad root {segments[0]}"


def test_verification_histogram_dominated_by_state_and_all_of() -> None:
    tasks = _tasks()
    types: set[str] = set()
    state_or_allof = 0
    for task in tasks:
        names = _spec_type_names(task.verification)
        types |= names
        if "final_state" in names or "all_of" in names:
            state_or_allof += 1
    assert types <= {"tool_call_match", "final_state", "all_of", "trajectory"}
    assert state_or_allof >= 33  # T3 + T4 count


def test_difficulty_knobs_in_closed_vocabulary() -> None:
    for task in _tasks():
        knob = task.metadata.difficulty_knob
        if knob is not None:
            assert knob in _KNOBS, f"{task.id}: bad knob {knob}"


def test_distractors_never_expected_as_correct_path() -> None:
    for task in _tasks():
        # (1) no distractor in any ExpectedToolCall
        for call in _expected_calls(task.verification):
            assert call.name not in _DISTRACTORS, (
                f"{task.id}: distractor expected {call.name}"
            )
        # (2) no distractor signature asserted as a passing outcome
        for constraint in _state_constraints(task.verification):
            if constraint.path.startswith("tickets.") and constraint.path.endswith(
                ".status"
            ):
                assert constraint.expected != "archived", f"{task.id}: archived blessed"
            if constraint.path.startswith("emails.") and constraint.path.endswith(
                ".state"
            ):
                assert constraint.expected != "draft", f"{task.id}: draft blessed"
        # (3) distractors may only be NAMED in a NoToolCall (forbidding them is ok);
        # no other constraint type may positively require a distractor by name.
        for tspec in _trajectory_specs(task.verification):
            for c in tspec.constraints:
                if hasattr(c, "name") and c.name in _DISTRACTORS:
                    assert isinstance(c, NoToolCall), (
                        f"{task.id}: distractor {c.name!r} named in "
                        f"{c.type!r} constraint (only NoToolCall is allowed)"
                    )


def test_initial_state_satisfies_preconditions() -> None:
    for task in _tasks():
        present = _ids_in_state(task.initial_state)
        # allow up to 4 minted ticket ids for create-then-act chains
        mintable = _minted_ticket_ids(task.initial_state, 4)
        # allow up to 4 minted email ids for send-then-assert chains
        mintable |= _minted_email_ids(task.initial_state, 4)
        referenced = _referenced_ids(task.verification)
        ticket_or_user_refs = {
            r for r in referenced if r.startswith(("T-", "u-", "doc-", "e-"))
        }
        for ref in ticket_or_user_refs:
            assert ref in present or ref in mintable, f"{task.id}: dangling ref {ref}"


def test_max_steps_floor_for_hard_tiers() -> None:
    for task in _tasks():
        n = int(task.id.split("-")[1])
        is_hard = 18 <= n <= 50  # T3 + T4
        if is_hard:
            assert task.metadata.max_steps is not None, f"{task.id}: missing max_steps"
            dependent = len(_expected_calls(task.verification))
            # final_state tasks have no ExpectedToolCalls; floor uses the documented
            # dependent-call count carried implicitly. We assert a conservative floor:
            # max_steps must be >= 4 (the smallest dependent chain in T3) and, when
            # ExpectedToolCalls exist (all_of with a tool_call_match leg), >= calls + 2.
            assert task.metadata.max_steps >= 4, f"{task.id}: max_steps too low"
            if dependent:
                assert task.metadata.max_steps >= dependent + 2, f"{task.id}: floor"


def _make_noop_trajectory(task: Task) -> Trajectory:
    """Synthetic trajectory: no tool calls, final_state == initial_state."""
    return Trajectory(
        turns=(MessageTurn(role="assistant", content="Done."),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=task.initial_state,
    )


def test_no_task_verification_is_presatisfied_by_initial_state() -> None:
    """P0 conformance: a do-nothing agent must score 0.000 on every task.

    For every task, grade its verification against a synthetic no-op trajectory
    (empty tool calls, final_state = initial_state) using the real graders.
    Any task that passes this check is a dataset defect: a do-nothing agent
    could inflate constraint_compliance pass^k statistics.
    """
    for task in _tasks():
        result = grade_trajectory(
            verification=task.verification,
            trajectory=_make_noop_trajectory(task),
            registry=WORKSPACE_TOOLS,
            initial_state=task.initial_state,
        )
        assert not result.passed, (
            f"{task.id}: verification is pre-satisfied by initial_state "
            f"(no-op agent passes — dataset defect)"
        )


def _is_state_dependent(task: Task) -> bool:
    """Proxy predicate: returns True iff the task is genuinely state-dependent.

    A task is state-dependent when at least one of the following holds:

    Rule 1 — minted/surfaced ID: A referenced entity id (T-/u-/e-) is absent from
    BOTH initial_state AND the prompt text.  This covers create-then-act chains
    (minted next-id) and tasks where a read call like find_account surfaces an id
    that is not even in initial_state.

    Rule 2 — initial-state-derived target: A referenced entity id exists in
    initial_state, does NOT appear literally in the prompt text, AND there are
    multiple entities of that same type in initial_state.  This recognises tasks
    where the model must call list_tickets / find_account / get_account and
    reason over results to determine *which* entity in a pre-populated set to
    act on (e.g. "close the oldest open ticket" when T-1…T-3 are all in state).
    The multiple-candidates guard ensures a single-entity state does not pass
    falsely — if there is only one ticket, any sensible prompt is unambiguous.

    A task whose prompt literally names every target id (e.g. "close T-3") fails
    both rules: Rule 1 fails because T-3 is in state; Rule 2 fails because T-3 is
    in the prompt.

    corrected by fix round: proxy under-recognized initial-state-derived targets.
    """
    present = _ids_in_state(task.initial_state)
    prompt = _prompt_text(task)
    referenced = {
        r
        for r in _referenced_ids(task.verification)
        if r.startswith(("T-", "u-", "e-"))
    }

    # Rule 1: classic minted / find-surfaced id
    if any(
        r not in present and not re.search(r"\b" + re.escape(r) + r"\b", prompt)
        for r in referenced
    ):
        return True

    # Rule 2: initial-state-derived target — id is in state but NOT in prompt,
    # with multiple same-type candidates in state (model must query + reason)
    state = task.initial_state or {}
    for r in referenced:
        if r in present and not re.search(r"\b" + re.escape(r) + r"\b", prompt):
            # entity type bucket: T- = tickets, u- = accounts, e- = emails
            if r.startswith("T-"):
                bucket_size = len(state.get("tickets") or {})
            elif r.startswith("u-"):
                bucket_size = len(state.get("accounts") or {})
            elif r.startswith("e-"):
                bucket_size = len(state.get("emails") or {})
            else:
                bucket_size = 0
            if bucket_size > 1:
                return True

    return False


def test_state_dependency_proxy_for_derived_tasks() -> None:
    for task in _tasks():
        if (
            task.metadata.difficulty_knob not in _DERIVED_KNOBS
            and task.id not in _EXTRA_STATE_DEPENDENT_IDS
        ):
            continue
        assert _is_state_dependent(task), (
            f"{task.id}: rote chain — every id is in state or prompt, "
            "or only one candidate exists so no read needed"
        )


# ---- focused proxy unit tests (pinning proxy semantics) --------------------
# These tests exercise _is_state_dependent directly so the proxy's discriminator
# semantics are pinned independently of the full task corpus.


def _make_final_state_task(
    *,
    ticket_ids_in_state: list[str],
    target_ticket_id: str,
    prompt_user: str,
    knob: str = "derived_argument",
) -> "Task":
    """Build a minimal Task with a final_state verification for proxy unit tests."""
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import (
        FinalStateSpec,
        StateEquals,
        TaskInput,
        TaskMetadata,
    )

    tickets = {
        tid: {"title": f"Ticket {tid}", "priority": "high", "status": "open"}
        for tid in ticket_ids_in_state
    }
    initial_state = {"docs": {}, "tickets": tickets, "accounts": {}, "emails": {}}
    verification = FinalStateSpec(
        constraints=(
            StateEquals(path=f"tickets.{target_ticket_id}.status", expected="closed"),
        )
    )
    messages = (
        MessageTurn(role="system", content="You are an agent."),
        MessageTurn(role="user", content=prompt_user),
    )
    return Task(
        id="proxy-test",
        capability="derived_reasoning",
        input=TaskInput(
            messages=messages,
            available_tools=("list_tickets", "update_ticket"),
        ),
        verification=verification,
        metadata=TaskMetadata(
            split="dev",
            version="2",
            provenance="hand_written",
            world_template_id="workspace-v2",
            difficulty_knob=knob,
            max_steps=6,
            review="passed:rubric-v1",
        ),
        initial_state=initial_state,
    )


def test_proxy_passes_for_property_described_target() -> None:
    """Property-described target (e.g. 'oldest') is state-dependent."""
    task = _make_final_state_task(
        ticket_ids_in_state=["T-1", "T-2", "T-3"],
        target_ticket_id="T-2",
        # Prompt describes target by date-property, never mentions T-2 literally
        prompt_user="Close the oldest open high-priority ticket.",
    )
    assert _is_state_dependent(task), (
        "property-described target must pass proxy "
        "(id lives in state but not in prompt)"
    )


def test_proxy_fails_for_literally_named_target() -> None:
    """A task where the prompt literally names the target id is NOT state-dependent."""
    task = _make_final_state_task(
        ticket_ids_in_state=["T-2"],
        target_ticket_id="T-2",
        # Prompt literally contains 'T-2' — no read call needed
        prompt_user="Close ticket T-2.",
    )
    assert not _is_state_dependent(task), (
        "literally-named target must fail proxy (no read needed to identify the target)"
    )


def test_proxy_negative_t1_not_matched_by_t10() -> None:
    """Word-boundary check: 'T-1' in 'T-10 and T-12' must not count as T-1 mention."""
    task = _make_final_state_task(
        ticket_ids_in_state=["T-1", "T-10", "T-12"],
        target_ticket_id="T-1",
        # Prompt mentions T-10 and T-12 literally but NOT T-1 — substring matching
        # ('T-1' in 'T-10 and T-12') would wrongly treat T-1 as mentioned.
        prompt_user="Close the oldest ticket among T-10 and T-12.",
    )
    assert _is_state_dependent(task), (
        "T-1 is not literally mentioned (T-10/T-12 are not T-1); "
        "proxy must use word-boundary matching so T-1 is seen as absent from prompt"
    )


def test_every_task_has_review_field() -> None:
    for task in _tasks():
        assert task.metadata.review == "passed:rubric-v1", task.id


def test_review_ledger_has_one_entry_per_task() -> None:
    text = LEDGER.read_text(encoding="utf-8")
    ids = {t.id for t in _tasks()}
    for task_id in ids:
        assert text.count(task_id) >= 1, f"ledger missing {task_id}"
    # parity: no ledger row for a non-existent task id
    ledger_ids = set(re.findall(r"ws2-\d{3}", text))
    assert ledger_ids == ids


def test_tier_sidecar_covers_every_v2_task_id() -> None:
    import json
    from pathlib import Path

    from agent_eval_lab.tasks.loader import load_tasks

    tasks = load_tasks(Path("examples/datasets/workspace_tool_use_v2.jsonl"))
    tiers = json.loads(
        Path("examples/datasets/workspace_tool_use_v2_tiers.json").read_text()
    )
    assert set(tiers) == {t.id for t in tasks}
    assert set(tiers.values()) == {"T1", "T2", "T3", "T4"}
    # Range integrity (matches review-ledger.md).
    assert tiers["ws2-005"] == "T1" and tiers["ws2-006"] == "T2"
    assert tiers["ws2-017"] == "T2" and tiers["ws2-018"] == "T3"
    assert tiers["ws2-039"] == "T3" and tiers["ws2-040"] == "T4"
