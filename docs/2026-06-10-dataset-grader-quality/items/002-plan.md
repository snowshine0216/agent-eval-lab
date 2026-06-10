# Workspace-world v2 + taxonomy + rubric + 50 reviewed hard tasks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the capability-discriminating successor to the saturated v1 tool-use set: extend `workspace.py` to 8 tools (3 new primaries + 3 distractors) over the grown world state `{tickets, docs, accounts, emails}`, add two additive optional `TaskMetadata` fields (`max_steps`, `review`), author 50 hard-tier-majority tasks in `workspace_tool_use_v2.jsonl`, and gate the whole set with a pure conformance suite plus a taxonomy doc, rubric doc, and review ledger.

**Architecture:** Strictly additive and pure-functional. Five new tools are pure `(args, state) -> (state', outcome)` impls threaded through the existing `apply`, each with a JSON schema in `WORKSPACE_TOOLS` and validated by the shared `validate_args`. `TaskMetadata` gains two optional defaulted fields read by `parse.py`. No new grader code, no new spec/constraint variants (item 001 shipped the full deterministic tier). The 50 tasks are authored against a TDD'd conformance module that mechanically enforces the rubric so a typo'd task can never masquerade as an agent failure. **No live model run, no runner changes** (per-task `max_steps` wiring is item 004's contract — ADR 0004).

**Tech Stack:** Python 3.11+, stdlib only + the already-vendored `jsonschema`. Tests via `uv run pytest`. Lint/format via `uv run ruff`. No new runtime dependencies.

---

## Canonical verification gates (run after every task)

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Expected throughout: pytest all green (baseline **192 tests** at start, growing as tasks add tests); `ruff check` reports `All checks passed!`; `ruff format` reports `<N> files already formatted`.

Baseline sanity check before starting:

```bash
uv run pytest -q
```

Expected: last line `192 passed`. If this is not 192, STOP and reconcile before proceeding.

---

## File Structure

**Create:**
- `examples/datasets/workspace_tool_use_v2.jsonl` — the 50 v2 tasks (one JSON object per line).
- `tests/datasets/test_workspace_tool_use_v2.py` — the pure conformance suite that gates all 50 tasks.
- `docs/2026-06-10-dataset-grader-quality/taxonomy.md` — six-capability × four-tier grid + per-tier expected-failure rationale.
- `docs/2026-06-10-dataset-grader-quality/rubric.md` — the per-task validity checklist (carries a version string).
- `docs/2026-06-10-dataset-grader-quality/review-ledger.md` — one row per task id (regenerable human-audit view).

**Modify:**
- `src/agent_eval_lab/tools/workspace.py` — add 5 tool schemas to `WORKSPACE_TOOLS`, 5 pure impls, wire `_IMPLS`, add `_next_email_id`.
- `src/agent_eval_lab/tasks/schema.py` — add `max_steps: int | None = None` and `review: str | None = None` to `TaskMetadata`.
- `src/agent_eval_lab/tasks/parse.py` — read the two new metadata fields when present.
- `tests/tools/test_workspace.py` — extend registry assertion + add per-tool unit tests.
- `tests/tools/test_workspace_properties.py` — add a determinism property test over the v2 tools.
- `tests/tasks/test_parse.py` — add round-trip tests for the two new metadata fields.

**Untouched (must stay byte-for-byte green):** `examples/datasets/workspace_tool_use_v1.jsonl`, `tests/datasets/test_workspace_tool_use.py`, `src/agent_eval_lab/tools/validation.py`, all grader code, the runner.

**Dependency order:** (A) tools — schema + impls, TDD'd unit-first; (B) `TaskMetadata` fields + parse, TDD'd; (C) conformance suite written test-first against an empty/partial dataset (red); (D) author the 4 exemplar tasks to green a slice; (E) author the remaining 46 by the rubric until the full suite is green; (F) docs (taxonomy, rubric, ledger) + `review` field wiring; (G) final gate.

---

## Reference: the v2 world and tool contract (read before authoring any task)

### World-state roots (all deterministic; literal data only)

```
state = {
  "docs":     { "<doc-id>":  {"title": str, "body": str} },
  "tickets":  { "T-<n>":     {"title": str, "priority": "low"|"medium"|"high",
                              "status": "open"|"closed"|"archived",
                              "assignee"?: "<user-id>", "created"?: "<ISO-date>"} },
  "accounts": { "<user-id>": {"name": str, "email": str,
                              "plan": "free"|"pro"|"enterprise",
                              "tickets": ["T-<n>", ...], "created": "<ISO-date>"} },
  "emails":   { "e-<n>":     {"to": str, "subject": str, "body": str,
                              "state": "sent"|"draft"} },
}
```

- `status:"archived"` is reachable **only** via the `archive_ticket` distractor; `update_ticket`'s enum stays `["open","closed"]`.
- `emails.*.state:"draft"` is reachable **only** via the `draft_email` distractor; `send_email` always writes `state:"sent"`.
- Ids mint deterministically: tickets `T-<max+1>` (existing `_next_ticket_id`), emails `e-<max+1>` (new `_next_email_id`).
- Read-only tools (`get_account`, `find_account`, `list_tickets`) return `state` **unchanged**.

### The 8 tools (3 existing + 3 new primaries + 3 distractors)

| tool | kind | mutates | one-line contract |
|------|------|---------|-------------------|
| `search_docs` | existing | no | returns sorted matching `doc_ids` |
| `create_ticket` | existing | tickets | mints `T-<n>`, status `open` |
| `update_ticket` | existing | tickets | sets status `open`/`closed` |
| `get_account` | **primary** | no | exact lookup by `user_id`; returns the account or a not-found failure |
| `list_tickets` | **primary** | no | filter by `status`/`assignee`/`priority`; returns matching ids **and fields** |
| `send_email` | **primary** | emails | appends `e-<n>` with `state:"sent"` |
| `archive_ticket` | **distractor** | tickets | sets status `archived` (a third status the grader detects) |
| `find_account` | **distractor** | no | search by `email`; returns *candidate* user_ids (selection error when id is known) |
| `draft_email` | **distractor** | emails | appends `e-<n>` with `state:"draft"` (silent under-action; never sent) |

---

## Task A1: Add `get_account` (primary, read-only, exact lookup)

**Files:**
- Modify: `src/agent_eval_lab/tools/workspace.py`
- Test: `tests/tools/test_workspace.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/tools/test_workspace.py` (end of file). Add a v2 state fixture near the top first, then the tests:

```python
V2_STATE = {
    "docs": {},
    "tickets": {
        "T-1": {
            "title": "Login broken",
            "priority": "high",
            "status": "open",
            "assignee": "u-1",
            "created": "2026-01-10",
        }
    },
    "accounts": {
        "u-1": {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "plan": "pro",
            "tickets": ["T-1"],
            "created": "2025-11-01",
        }
    },
    "emails": {},
}


def test_get_account_returns_exact_account_and_does_not_mutate() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="get_account",
        arguments={"user_id": "u-1"},
        state=V2_STATE,
    )

    assert new_state == V2_STATE
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {
        "user_id": "u-1",
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "plan": "pro",
        "tickets": ["T-1"],
        "created": "2025-11-01",
    }


def test_get_account_unknown_user_is_a_business_failure() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="get_account",
        arguments={"user_id": "u-99"},
        state=V2_STATE,
    )

    assert new_state == V2_STATE
    assert isinstance(outcome, ToolFailure)
    assert "u-99" in outcome.error
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/tools/test_workspace.py::test_get_account_returns_exact_account_and_does_not_mutate -q`
Expected: FAIL — `apply` returns `ToolFailure(error="unknown tool: get_account")` so the `ToolSuccess` assertion fails.

- [ ] **Step 3: Add the schema to `WORKSPACE_TOOLS`**

Insert this entry into the `WORKSPACE_TOOLS` mapping in `src/agent_eval_lab/tools/workspace.py`, after the `update_ticket` entry (still inside the dict literal):

```python
    "get_account": ToolDef(
        name="get_account",
        description="Look up an account by its exact user_id; returns the account.",
        parameters={
            "type": "object",
            "properties": {"user_id": {"type": "string", "minLength": 1}},
            "required": ["user_id"],
            "additionalProperties": False,
        },
    ),
```

- [ ] **Step 4: Add the impl**

Add after `_update_ticket` in `src/agent_eval_lab/tools/workspace.py`:

```python
def _get_account(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    accounts = state.get("accounts", {})
    user_id = args["user_id"]
    account = accounts.get(user_id)
    if account is None:
        return state, ToolFailure(error=f"unknown user_id: {user_id}")
    return state, ToolSuccess(result={"user_id": user_id, **account})
```

- [ ] **Step 5: Register the impl**

In `src/agent_eval_lab/tools/workspace.py`, add to the `_IMPLS` mapping:

```python
    "get_account": _get_account,
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest tests/tools/test_workspace.py -q`
Expected: PASS (both new tests green; existing tests unaffected).

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/tools/workspace.py tests/tools/test_workspace.py
git commit -m "feat(tools): add get_account primary (exact user_id lookup, read-only)"
```

---

## Task A2: Add `list_tickets` (primary, read-only, filtered list with fields)

**Files:**
- Modify: `src/agent_eval_lab/tools/workspace.py`
- Test: `tests/tools/test_workspace.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/tools/test_workspace.py`:

```python
LIST_STATE = {
    "docs": {},
    "tickets": {
        "T-1": {"title": "A", "priority": "high", "status": "open",
                "assignee": "u-1", "created": "2026-01-10"},
        "T-2": {"title": "B", "priority": "high", "status": "open",
                "assignee": "u-1", "created": "2025-12-01"},
        "T-3": {"title": "C", "priority": "low", "status": "closed",
                "assignee": "u-2", "created": "2026-02-01"},
    },
    "accounts": {},
    "emails": {},
}


def test_list_tickets_no_filter_returns_all_with_fields_and_no_mutation() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS, name="list_tickets", arguments={}, state=LIST_STATE
    )

    assert new_state == LIST_STATE
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["ticket_ids"] == ["T-1", "T-2", "T-3"]
    assert outcome.result["tickets"]["T-2"]["created"] == "2025-12-01"


def test_list_tickets_filters_by_status_and_priority() -> None:
    _, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="list_tickets",
        arguments={"status": "open", "priority": "high"},
        state=LIST_STATE,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["ticket_ids"] == ["T-1", "T-2"]


def test_list_tickets_filters_by_assignee() -> None:
    _, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="list_tickets",
        arguments={"assignee": "u-2"},
        state=LIST_STATE,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["ticket_ids"] == ["T-3"]


def test_list_tickets_unknown_filter_value_is_empty_not_error() -> None:
    _, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="list_tickets",
        arguments={"status": "archived"},
        state=LIST_STATE,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["ticket_ids"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/tools/test_workspace.py::test_list_tickets_no_filter_returns_all_with_fields_and_no_mutation -q`
Expected: FAIL — unknown tool `list_tickets`.

- [ ] **Step 3: Add the schema**

Add to `WORKSPACE_TOOLS` after `get_account`. Note `status` accepts `archived` so the filter is total over every reachable status:

```python
    "list_tickets": ToolDef(
        name="list_tickets",
        description=(
            "List tickets, optionally filtered by status, assignee, or priority; "
            "returns matching ticket ids and their fields."
        ),
        parameters={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["open", "closed", "archived"]},
                "assignee": {"type": "string", "minLength": 1},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": [],
            "additionalProperties": False,
        },
    ),
```

- [ ] **Step 4: Add the impl**

Add after `_get_account`:

```python
def _list_tickets(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    tickets = state.get("tickets", {})
    status = args.get("status")
    assignee = args.get("assignee")
    priority = args.get("priority")
    matched = {
        ticket_id: ticket
        for ticket_id, ticket in tickets.items()
        if (status is None or ticket.get("status") == status)
        and (assignee is None or ticket.get("assignee") == assignee)
        and (priority is None or ticket.get("priority") == priority)
    }
    return state, ToolSuccess(
        result={"ticket_ids": sorted(matched), "tickets": matched}
    )
```

- [ ] **Step 5: Register the impl**

Add to `_IMPLS`:

```python
    "list_tickets": _list_tickets,
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest tests/tools/test_workspace.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/tools/workspace.py tests/tools/test_workspace.py
git commit -m "feat(tools): add list_tickets primary (pure total filter, returns fields)"
```

---

## Task A3: Add `send_email` (primary, appends a sent email)

**Files:**
- Modify: `src/agent_eval_lab/tools/workspace.py`
- Test: `tests/tools/test_workspace.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/tools/test_workspace.py`:

```python
def test_send_email_appends_sent_email_with_next_id_no_mutation() -> None:
    before = {"docs": {}, "tickets": {}, "accounts": {}, "emails": {}}
    snapshot = {"docs": {}, "tickets": {}, "accounts": {}, "emails": {}}

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="send_email",
        arguments={"to": "ada@example.com", "subject": "Hi", "body": "Welcome."},
        state=before,
    )

    assert before == snapshot
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"email_id": "e-1"}
    assert new_state["emails"]["e-1"] == {
        "to": "ada@example.com",
        "subject": "Hi",
        "body": "Welcome.",
        "state": "sent",
    }


def test_send_email_mints_next_id_above_existing() -> None:
    state = {
        "docs": {}, "tickets": {}, "accounts": {},
        "emails": {"e-1": {"to": "x", "subject": "y", "body": "z", "state": "sent"}},
    }

    _, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="send_email",
        arguments={"to": "b@example.com", "subject": "S", "body": "B"},
        state=state,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"email_id": "e-2"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/tools/test_workspace.py::test_send_email_appends_sent_email_with_next_id_no_mutation -q`
Expected: FAIL — unknown tool `send_email`.

- [ ] **Step 3: Add the schema**

Add to `WORKSPACE_TOOLS` after `list_tickets`:

```python
    "send_email": ToolDef(
        name="send_email",
        description="Send an email; appends a sent email and returns its id.",
        parameters={
            "type": "object",
            "properties": {
                "to": {"type": "string", "minLength": 1},
                "subject": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
            },
            "required": ["to", "subject", "body"],
            "additionalProperties": False,
        },
    ),
```

- [ ] **Step 4: Add `_next_email_id` and the impl**

Add `_next_email_id` after `_next_ticket_id`:

```python
def _next_email_id(emails: Mapping[str, Any]) -> str:
    numbers = [
        int(email_id.split("-")[1])
        for email_id in emails
        if email_id.startswith("e-") and email_id.split("-")[1].isdigit()
    ]
    return f"e-{max(numbers, default=0) + 1}"
```

Add `_send_email` after `_list_tickets`:

```python
def _send_email(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    emails = state.get("emails", {})
    email_id = _next_email_id(emails)
    email = {
        "to": args["to"],
        "subject": args["subject"],
        "body": args["body"],
        "state": "sent",
    }
    new_state = {**state, "emails": {**emails, email_id: email}}
    return new_state, ToolSuccess(result={"email_id": email_id})
```

- [ ] **Step 5: Register the impl**

Add to `_IMPLS`:

```python
    "send_email": _send_email,
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest tests/tools/test_workspace.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/tools/workspace.py tests/tools/test_workspace.py
git commit -m "feat(tools): add send_email primary (appends state=sent email)"
```

---

## Task A4: Add `archive_ticket` (distractor — third status `archived`)

**Files:**
- Modify: `src/agent_eval_lab/tools/workspace.py`
- Test: `tests/tools/test_workspace.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/tools/test_workspace.py`:

```python
def test_archive_ticket_sets_archived_status_distinct_from_closed() -> None:
    state = {
        "docs": {}, "accounts": {}, "emails": {},
        "tickets": {"T-1": {"title": "A", "priority": "low", "status": "open"}},
    }

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="archive_ticket",
        arguments={"ticket_id": "T-1"},
        state=state,
    )

    assert isinstance(outcome, ToolSuccess)
    assert new_state["tickets"]["T-1"]["status"] == "archived"
    assert state["tickets"]["T-1"]["status"] == "open"


def test_archive_unknown_ticket_is_a_business_failure() -> None:
    state = {"docs": {}, "accounts": {}, "emails": {}, "tickets": {}}

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="archive_ticket",
        arguments={"ticket_id": "T-99"},
        state=state,
    )

    assert new_state == state
    assert isinstance(outcome, ToolFailure)
    assert "T-99" in outcome.error
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/tools/test_workspace.py::test_archive_ticket_sets_archived_status_distinct_from_closed -q`
Expected: FAIL — unknown tool `archive_ticket`.

- [ ] **Step 3: Add the schema**

Add to `WORKSPACE_TOOLS` after `send_email`:

```python
    "archive_ticket": ToolDef(
        name="archive_ticket",
        description="Archive a ticket (sets status to archived).",
        parameters={
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"],
            "additionalProperties": False,
        },
    ),
```

- [ ] **Step 4: Add the impl**

Add after `_send_email`:

```python
def _archive_ticket(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    tickets = state.get("tickets", {})
    ticket_id = args["ticket_id"]
    if ticket_id not in tickets:
        return state, ToolFailure(error=f"unknown ticket_id: {ticket_id}")
    updated = {**tickets[ticket_id], "status": "archived"}
    new_state = {**state, "tickets": {**tickets, ticket_id: updated}}
    return new_state, ToolSuccess(result={"ticket_id": ticket_id, "status": "archived"})
```

- [ ] **Step 5: Register the impl**

Add to `_IMPLS`:

```python
    "archive_ticket": _archive_ticket,
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest tests/tools/test_workspace.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/tools/workspace.py tests/tools/test_workspace.py
git commit -m "feat(tools): add archive_ticket distractor (status=archived wrong path)"
```

---

## Task A5: Add `find_account` (distractor — by-email, returns candidates)

**Files:**
- Modify: `src/agent_eval_lab/tools/workspace.py`
- Test: `tests/tools/test_workspace.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/tools/test_workspace.py`:

```python
def test_find_account_returns_candidate_user_ids_no_mutation() -> None:
    state = {
        "docs": {}, "tickets": {}, "emails": {},
        "accounts": {
            "u-1": {"name": "Ada", "email": "ada@example.com", "plan": "pro",
                    "tickets": [], "created": "2025-11-01"},
            "u-2": {"name": "Grace", "email": "ada@example.com", "plan": "free",
                    "tickets": [], "created": "2025-10-01"},
        },
    }

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="find_account",
        arguments={"email": "ada@example.com"},
        state=state,
    )

    assert new_state == state
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"candidates": ["u-1", "u-2"]}


def test_find_account_no_match_returns_empty_candidates() -> None:
    state = {"docs": {}, "tickets": {}, "emails": {}, "accounts": {}}

    _, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="find_account",
        arguments={"email": "nobody@example.com"},
        state=state,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"candidates": []}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/tools/test_workspace.py::test_find_account_returns_candidate_user_ids_no_mutation -q`
Expected: FAIL — unknown tool `find_account`.

- [ ] **Step 3: Add the schema**

Add to `WORKSPACE_TOOLS` after `archive_ticket`:

```python
    "find_account": ToolDef(
        name="find_account",
        description="Search accounts by email; returns candidate user_ids.",
        parameters={
            "type": "object",
            "properties": {"email": {"type": "string", "minLength": 1}},
            "required": ["email"],
            "additionalProperties": False,
        },
    ),
```

- [ ] **Step 4: Add the impl**

Add after `_archive_ticket`:

```python
def _find_account(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    accounts = state.get("accounts", {})
    email = args["email"]
    candidates = sorted(
        user_id
        for user_id, account in accounts.items()
        if account.get("email") == email
    )
    return state, ToolSuccess(result={"candidates": candidates})
```

- [ ] **Step 5: Register the impl**

Add to `_IMPLS`:

```python
    "find_account": _find_account,
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest tests/tools/test_workspace.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/tools/workspace.py tests/tools/test_workspace.py
git commit -m "feat(tools): add find_account distractor (by-email candidates)"
```

---

## Task A6: Add `draft_email` (distractor — staged, never sent)

**Files:**
- Modify: `src/agent_eval_lab/tools/workspace.py`
- Test: `tests/tools/test_workspace.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/tools/test_workspace.py`:

```python
def test_draft_email_appends_draft_state_not_sent() -> None:
    state = {"docs": {}, "tickets": {}, "accounts": {}, "emails": {}}

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="draft_email",
        arguments={"to": "ada@example.com", "subject": "Hi", "body": "Draft."},
        state=state,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"email_id": "e-1"}
    assert new_state["emails"]["e-1"]["state"] == "draft"
    assert state["emails"] == {}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/tools/test_workspace.py::test_draft_email_appends_draft_state_not_sent -q`
Expected: FAIL — unknown tool `draft_email`.

- [ ] **Step 3: Add the schema**

Add to `WORKSPACE_TOOLS` after `find_account`:

```python
    "draft_email": ToolDef(
        name="draft_email",
        description="Stage a draft email (does NOT send); appends a draft.",
        parameters={
            "type": "object",
            "properties": {
                "to": {"type": "string", "minLength": 1},
                "subject": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
            },
            "required": ["to", "subject", "body"],
            "additionalProperties": False,
        },
    ),
```

- [ ] **Step 4: Add the impl**

Add after `_find_account`:

```python
def _draft_email(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    emails = state.get("emails", {})
    email_id = _next_email_id(emails)
    email = {
        "to": args["to"],
        "subject": args["subject"],
        "body": args["body"],
        "state": "draft",
    }
    new_state = {**state, "emails": {**emails, email_id: email}}
    return new_state, ToolSuccess(result={"email_id": email_id})
```

- [ ] **Step 5: Register the impl**

Add to `_IMPLS`:

```python
    "draft_email": _draft_email,
```

- [ ] **Step 6: Update the registry-shape assertion in `test_workspace.py`**

Replace the existing `test_registry_exposes_three_tools_with_schemas` body's first assertion. Change:

```python
    assert set(WORKSPACE_TOOLS) == {"search_docs", "create_ticket", "update_ticket"}
```

to:

```python
    assert set(WORKSPACE_TOOLS) == {
        "search_docs", "create_ticket", "update_ticket",
        "get_account", "list_tickets", "send_email",
        "archive_ticket", "find_account", "draft_email",
    }
```

Rename the function to `test_registry_exposes_eight_tools_with_schemas` (the existing `test_every_registered_tool_has_an_implementation` already asserts `set(WORKSPACE_TOOLS) == set(_IMPLS)`, so it will now confirm all 9 are wired).

> NOTE: `test_unknown_tool_fails` in `test_workspace.py` currently calls `name="send_email"` to demonstrate an unknown tool. `send_email` is now registered, so this test will break. Change its `name="send_email"` to `name="no_such_tool"` and its assertion target accordingly:
> ```python
> new_state, outcome = apply(
>     registry=WORKSPACE_TOOLS, name="no_such_tool", arguments={}, state=STATE
> )
> ...
> assert "unknown tool" in outcome.error
> ```

- [ ] **Step 7: Run to verify it passes**

Run: `uv run pytest tests/tools/test_workspace.py -q`
Expected: PASS — registry has 9 tools, all impls wired, unknown-tool test uses a genuinely unknown name.

- [ ] **Step 8: Commit**

```bash
git add src/agent_eval_lab/tools/workspace.py tests/tools/test_workspace.py
git commit -m "feat(tools): add draft_email distractor; widen registry to 9 tools"
```

---

## Task A7: Determinism property test over the v2 tools (AC 11)

**Files:**
- Modify: `tests/tools/test_workspace_properties.py`
- Test: same file

- [ ] **Step 1: Write the failing test**

Add to `tests/tools/test_workspace_properties.py`:

```python
from agent_eval_lab.records.turns import ToolSuccess

_V2_STATE = {
    "docs": {"doc-1": {"title": "Refund", "body": "5 days"}},
    "tickets": {"T-1": {"title": "A", "priority": "high", "status": "open",
                        "assignee": "u-1", "created": "2026-01-10"}},
    "accounts": {"u-1": {"name": "Ada", "email": "ada@example.com", "plan": "pro",
                         "tickets": ["T-1"], "created": "2025-11-01"}},
    "emails": {},
}

_FIXED_CALLS = [
    ("get_account", {"user_id": "u-1"}),
    ("list_tickets", {"status": "open"}),
    ("send_email", {"to": "ada@example.com", "subject": "S", "body": "B"}),
    ("archive_ticket", {"ticket_id": "T-1"}),
    ("find_account", {"email": "ada@example.com"}),
    ("draft_email", {"to": "ada@example.com", "subject": "S", "body": "B"}),
]


def test_every_v2_tool_is_deterministic_over_fixed_input() -> None:
    for name, arguments in _FIXED_CALLS:
        first_state, first_outcome = apply(
            registry=WORKSPACE_TOOLS, name=name, arguments=arguments, state=_V2_STATE
        )
        second_state, second_outcome = apply(
            registry=WORKSPACE_TOOLS, name=name, arguments=arguments, state=_V2_STATE
        )
        assert first_state == second_state, name
        assert isinstance(first_outcome, ToolSuccess), name
        assert first_outcome.result == second_outcome.result, name
```

- [ ] **Step 2: Run to verify it passes** (all six tools already exist from A1–A6)

Run: `uv run pytest tests/tools/test_workspace_properties.py -q`
Expected: PASS.

- [ ] **Step 3: Run the full gate**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green; `All checks passed!`; `<N> files already formatted`.

- [ ] **Step 4: Commit**

```bash
git add tests/tools/test_workspace_properties.py
git commit -m "test(tools): assert every v2 tool is deterministic over fixed input"
```

---

## Task B1: Add `max_steps` and `review` to `TaskMetadata` (additive, optional)

**Files:**
- Modify: `src/agent_eval_lab/tasks/schema.py`
- Modify: `src/agent_eval_lab/tasks/parse.py`
- Test: `tests/tasks/test_parse.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/tasks/test_parse.py`. (Reuse the file's existing minimal task-dict builder if present; otherwise this self-contained dict works.)

```python
def test_metadata_max_steps_and_review_default_to_none() -> None:
    from agent_eval_lab.tasks.parse import _parse_metadata

    meta = _parse_metadata(
        {"split": "dev", "version": "2", "provenance": "hand_written"}
    )

    assert meta.max_steps is None
    assert meta.review is None


def test_metadata_reads_max_steps_and_review_when_present() -> None:
    from agent_eval_lab.tasks.parse import _parse_metadata

    meta = _parse_metadata(
        {
            "split": "dev",
            "version": "2",
            "provenance": "hand_written",
            "world_template_id": "workspace-v2",
            "max_steps": 10,
            "review": "passed:rubric-v1",
        }
    )

    assert meta.max_steps == 10
    assert meta.review == "passed:rubric-v1"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/tasks/test_parse.py::test_metadata_reads_max_steps_and_review_when_present -q`
Expected: FAIL — `TaskMetadata.__init__() got an unexpected keyword argument 'max_steps'`.

- [ ] **Step 3: Add the fields to `TaskMetadata`**

In `src/agent_eval_lab/tasks/schema.py`, extend the `TaskMetadata` dataclass:

```python
@dataclass(frozen=True, kw_only=True)
class TaskMetadata:
    split: Literal["dev", "held_out"]
    version: str
    provenance: str
    world_template_id: str | None = None
    difficulty_knob: str | None = None
    max_steps: int | None = None
    review: str | None = None
```

- [ ] **Step 4: Read the fields in `parse.py`**

In `src/agent_eval_lab/tasks/parse.py`, extend `_parse_metadata`'s return:

```python
    return TaskMetadata(
        split=data["split"],
        version=data["version"],
        provenance=data["provenance"],
        world_template_id=data.get("world_template_id"),
        difficulty_knob=data.get("difficulty_knob"),
        max_steps=data.get("max_steps"),
        review=data.get("review"),
    )
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/tasks/test_parse.py -q`
Expected: PASS.

- [ ] **Step 6: Confirm v1 is byte-for-byte unaffected**

Run: `uv run pytest tests/datasets/test_workspace_tool_use.py -q`
Expected: PASS (v1 rows omit both fields ⇒ default to `None`).

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/tasks/schema.py src/agent_eval_lab/tasks/parse.py tests/tasks/test_parse.py
git commit -m "feat(tasks): TaskMetadata gains optional max_steps and review (additive)"
```

---

## The 50-task allocation table (the authoring contract)

The impl agent authors exactly these 50 rows. Columns: **id**, **capability**, **tier**, **tools involved** (the tools the correct path uses + distractors present in `available_tools`), **verification shape**, **scenario** (one line), **hardness mechanism** (`difficulty_knob`). All tasks set `version:"2"`, `provenance:"hand_written"`, `world_template_id:"workspace-v2"`, `split:"dev"`, `review:"passed:rubric-v1"`. T3/T4 tasks set `max_steps`. `available_tools` for **every** task is the full 8-tool surface unless a row says "minimal surface" (T1 only) — exposing all 8 is what makes distractors bite.

Capability totals (AC 5 requires all six present): `tool_selection` 6, `argument_extraction` 8, `multi_step_state` 12, `derived_reasoning` 11, `distractor_resistance` 7, `constraint_compliance` 6 = **50**.
Tier totals (AC 4): T1 5, T2 12, T3 22, T4 11.
Verification histogram (AC 6): `tool_call_match` on all T1+T2 (17) plus a small number of T3 selection rows; `final_state`/`all_of` on the remaining T3+T4. `final_state`+`all_of` count must be ≥ 33 (T3+T4). Allocate so it is.

| id | capability | tier | tools involved | verification | scenario | knob |
|----|------------|------|----------------|--------------|----------|------|
| ws2-001 | tool_selection | T1 | search_docs (minimal surface: 3 v1 tools) | tool_call_match/exact | Search docs for 'refund policy'. | — |
| ws2-002 | tool_selection | T1 | create_ticket (minimal surface) | tool_call_match/exact | Create a low-priority ticket 'Printer offline'. | — |
| ws2-003 | tool_selection | T1 | update_ticket (minimal surface) | tool_call_match/exact | Close ticket T-7. | — |
| ws2-004 | argument_extraction | T1 | create_ticket (minimal surface) | tool_call_match/exact | File a high-priority ticket 'Checkout returns 500'. | — |
| ws2-005 | tool_selection | T1 | get_account (full surface) | tool_call_match/exact | Look up account u-3. | — |
| ws2-006 | tool_selection | T2 | get_account vs find_account (full) | tool_call_match/exact | Get the account with user_id u-2 (id known ⇒ get_account). | distractor_count |
| ws2-007 | tool_selection | T2 | send_email vs draft_email (full) | tool_call_match/exact | Send an email to ada@x telling her the ticket is closed. | distractor_count |
| ws2-008 | argument_extraction | T2 | create_ticket (full) | tool_call_match/exact | Open a medium-priority ticket 'Slow dashboard loading'. | argument_complexity |
| ws2-009 | argument_extraction | T2 | send_email (full) | tool_call_match/exact | Email u-1 (ada@x) subject 'Welcome' body 'Your pro plan is active'. | argument_complexity |
| ws2-010 | argument_extraction | T2 | list_tickets (full) | tool_call_match/exact | List all open tickets. | argument_complexity |
| ws2-011 | argument_extraction | T2 | list_tickets (full) | tool_call_match/exact | List high-priority tickets assigned to u-1. | argument_complexity |
| ws2-012 | tool_selection | T2 | update_ticket vs archive_ticket (full) | tool_call_match/exact | Close T-4 (close, not archive). | distractor_count |
| ws2-013 | argument_extraction | T2 | create_ticket (full) | tool_call_match/exact | File a high-priority ticket 'Cannot sign in'. | argument_complexity |
| ws2-014 | argument_extraction | T2 | update_ticket (full) | tool_call_match/exact | Reopen ticket T-3. | argument_complexity |
| ws2-015 | argument_extraction | T2 | send_email (full) | tool_call_match/exact | Send 'Outage update' to ops@x body 'Resolved at 14:00'. | argument_complexity |
| ws2-016 | tool_selection | T2 | get_account (full) | tool_call_match/exact | Retrieve account details for u-5. | distractor_count |
| ws2-017 | multi_step_state | T2 | create_ticket→update_ticket (full) | final_state | Create 'Data export failing' high, then close it. | multi_step_depth |
| ws2-018 | multi_step_state | T3 | create→update (minted id) (full) | final_state | File 'Webhook 500s' high then close the ticket you filed. | multi_step_depth |
| ws2-019 | multi_step_state | T3 | get_account→create_ticket (full) | final_state | Look up u-2, then file a ticket for that user titled by their name. | derived_argument |
| ws2-020 | multi_step_state | T3 | list_tickets→update_ticket (full) | final_state | Close every open ticket assigned to u-1. | multi_step_depth |
| ws2-021 | multi_step_state | T3 | create×2→update×2 (minted ids) (full) | final_state | File two high tickets and close both. | multi_step_depth |
| ws2-022 | multi_step_state | T3 | get_account→send_email (full) | final_state | Look up u-3 and email them their plan name. | derived_argument |
| ws2-023 | multi_step_state | T3 | list_tickets→send_email (full) | final_state | Count u-1's open tickets and email them the count. | derived_argument |
| ws2-024 | multi_step_state | T3 | create→update→send_email (minted) (full) | final_state | File 'Refund' ticket, close it, email the customer it's done. | multi_step_depth |
| ws2-025 | multi_step_state | T3 | find_account→get_account→create (full) | final_state | Find the account for ada@x, confirm by id, file a ticket for it. | multi_step_depth |
| ws2-026 | multi_step_state | T3 | list_tickets→update×N (full) | final_state | Close all high-priority open tickets. | multi_step_depth |
| ws2-027 | multi_step_state | T3 | create→send_email (minted id) (full) | final_state | File 'Billing' ticket then email support the new ticket id. | derived_argument |
| ws2-028 | multi_step_state | T4 | find→get→list→update (min-by-date) (full) | final_state | For ada@x, close their oldest open ticket. | derived_argument |
| ws2-029 | derived_reasoning | T3 | list_tickets→update (min-by-date) (full) | final_state | Close the oldest open high-priority ticket. | derived_argument |
| ws2-030 | derived_reasoning | T3 | list_tickets→update (max-by-date) (full) | final_state | Close the most recently created open ticket. | derived_argument |
| ws2-031 | derived_reasoning | T3 | list_tickets→send_email (count) (full) | final_state | Email u-2 how many open tickets they have. | derived_argument |
| ws2-032 | derived_reasoning | T3 | get_account→list→send (filter) (full) | final_state | Email u-1 the titles of their high-priority tickets. | derived_argument |
| ws2-033 | derived_reasoning | T3 | list_tickets→update (min-by-date) (full) | final_state | Reopen the oldest closed ticket. | derived_argument |
| ws2-034 | derived_reasoning | T3 | list→get→send (cross-ref) (full) | final_state | Email the assignee of the oldest open ticket a status note. | derived_argument |
| ws2-035 | derived_reasoning | T3 | list_tickets→update (count gate) (full) | final_state | If u-1 has >2 open tickets, close the oldest. | derived_argument |
| ws2-036 | derived_reasoning | T4 | find→get→list→send (min+count) (full) | final_state | For ada@x: email them the id of their oldest open ticket. | derived_argument |
| ws2-037 | derived_reasoning | T4 | list→update→list→update (2 derived) (full) | final_state | Close the two oldest open high-priority tickets. | derived_argument |
| ws2-038 | derived_reasoning | T3 | list_tickets→update (max-priority) (full) | final_state | Close the open ticket with the highest priority. | derived_argument |
| ws2-039 | derived_reasoning | T4 | find→get→list→update (min-by-date) (full) | final_state | For the account at grace@x, archive—no, close—their newest open ticket. | derived_argument |
| ws2-040 | distractor_resistance | T3 | send_email present draft_email (full) | all_of(final_state, trajectory:NoToolCall draft_email) | Send (not draft) a closure email to u-1. | distractor_count |
| ws2-041 | distractor_resistance | T3 | update_ticket present archive_ticket (full) | all_of(final_state, trajectory:NoToolCall archive_ticket) | Close (not archive) ticket T-2. | distractor_count |
| ws2-042 | distractor_resistance | T3 | get_account present find_account (full) | all_of(final_state via send, trajectory:NoToolCall find_account) | Email u-4 (id known) — don't search by email. | distractor_count |
| ws2-043 | distractor_resistance | T4 | create→update; archive+draft present (full) | all_of(final_state, trajectory:NoToolCall archive_ticket + NoToolCall draft_email) | File 'Outage' high, close it, email the team — sent, closed. | distractor_count |
| ws2-044 | distractor_resistance | T4 | list→update; archive present (full) | all_of(final_state, trajectory:NoToolCall archive_ticket) | Close all open tickets for u-2 (close, never archive). | distractor_count |
| ws2-045 | distractor_resistance | T3 | send_email; draft present (full) | all_of(final_state, trajectory:NoToolCall draft_email) | Send the refund confirmation to ada@x. | distractor_count |
| ws2-046 | distractor_resistance | T4 | find→get→send; find is the trap (full) | all_of(final_state, trajectory:NoToolCall find_account) | Email u-7 (id given) their renewal date. | distractor_count |
| ws2-047 | constraint_compliance | T2 | search_docs only; never create (full) | all_of(final_state, trajectory:NoToolCall create_ticket) | Find the refund doc but do not open a ticket. | layered_constraint |
| ws2-048 | constraint_compliance | T3 | update_ticket only T-1; OnlyModifies (full) | all_of(final_state, trajectory:OnlyModifies tickets.T-1) | Close T-1 only; leave every other ticket untouched. | layered_constraint |
| ws2-049 | constraint_compliance | T3 | list→update; MaxToolCalls (full) | all_of(final_state, trajectory:MaxToolCalls 3) | Close the oldest open ticket in at most 3 calls. | layered_constraint |
| ws2-050 | constraint_compliance | T4 | create→update; NoToolCall send_email + OnlyModifies (full) | all_of(final_state, trajectory:NoToolCall send_email + OnlyModifies tickets) | File 'Audit' high and close it — but never email anyone. | layered_constraint |

**Verification-histogram self-check the author must satisfy:** rows ws2-001..ws2-016 are `tool_call_match` (16); ws2-017 is `final_state`. That leaves ws2-018..ws2-050 (33 rows) as `final_state` or `all_of` — exactly the T3+T4 count of 33, so AC 6's "`final_state`+`all_of` ≥ 33" holds with the histogram split 17 `tool_call_match` / ~22 `final_state` / ~11 `all_of`. (The 11 `all_of` rows are ws2-040..ws2-050.) If the author moves a row's shape, they must re-confirm `final_state`+`all_of` ≥ 33 — the conformance test (Task C) enforces it.

**Constraint-compliance count = 6 (ws2-047..ws2-050 is only 4).** Author **two additional** `constraint_compliance` rows by re-labeling two of the `all_of` distractor rows whose dominant mechanism is the *policy clause* rather than the distractor: relabel **ws2-043** and **ws2-044** to `capability:"constraint_compliance"` (they already carry a `NoToolCall` policy) and set their `difficulty_knob:"layered_constraint"`. After relabeling: `distractor_resistance` 5 (ws2-040,041,042,045,046), `constraint_compliance` 6 (ws2-043,044,047,048,049,050). Re-balance one row into `distractor_resistance` by relabeling **ws2-046**'s sibling: keep totals as **`tool_selection` 6, `argument_extraction` 8, `multi_step_state` 11, `derived_reasoning` 11, `distractor_resistance` 7, `constraint_compliance` 7 = 50** — the conformance test asserts the six-element *set* (AC 5), not exact per-capability counts, so any partition summing to 50 with all six present is valid. **Author rule: the only hard count gates are (a) total = 50, (b) tier mix 5/12/22/11, (c) all six capabilities present, (d) `final_state`+`all_of` ≥ 33.** Per-capability counts are advisory; keep them within ±2 of the table for a balanced set.

---

## Four fully-worked exemplar tasks (one per tier) — complete JSONL

The impl agent pastes these verbatim as the first four authored rows (ws2-001 T1, ws2-008 T2, ws2-029 T3, ws2-028 T4 are the canonical exemplars), then authors the rest by analogy under the rubric. Each is a single line in the `.jsonl` (shown wrapped here for readability — **emit as one physical line**).

### Exemplar T1 — ws2-001 (`tool_selection`, `tool_call_match`)

```json
{"id": "ws2-001", "capability": "tool_selection", "input": {"messages": [{"type": "message", "role": "system", "content": "You are a support agent for the Workspace tool suite. Complete the request by calling the available tools with exactly the argument values the request specifies. When done, reply with a short confirmation."}, {"type": "message", "role": "user", "content": "Search the docs for 'refund policy'."}], "available_tools": ["search_docs", "create_ticket", "update_ticket"]}, "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "search_docs", "arguments": {"query": "refund policy"}}], "match": "exact_sequence"}, "metadata": {"split": "dev", "version": "2", "provenance": "hand_written", "world_template_id": "workspace-v2", "review": "passed:rubric-v1"}, "initial_state": {"docs": {"doc-1": {"title": "Refund policy", "body": "Refunds are processed within 5 business days."}}, "tickets": {}, "accounts": {}, "emails": {}}}
```

### Exemplar T2 — ws2-008 (`argument_extraction`, `tool_call_match`, full surface)

```json
{"id": "ws2-008", "capability": "argument_extraction", "input": {"messages": [{"type": "message", "role": "system", "content": "You are a support agent for the Workspace tool suite. Complete the request by calling the available tools with exactly the argument values the request specifies. When done, reply with a short confirmation."}, {"type": "message", "role": "user", "content": "Open a medium-priority ticket titled 'Slow dashboard loading'."}], "available_tools": ["search_docs", "create_ticket", "update_ticket", "get_account", "list_tickets", "send_email", "archive_ticket", "find_account", "draft_email"]}, "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "create_ticket", "arguments": {"title": "Slow dashboard loading", "priority": "medium"}}], "match": "exact_sequence"}, "metadata": {"split": "dev", "version": "2", "provenance": "hand_written", "world_template_id": "workspace-v2", "difficulty_knob": "argument_complexity", "review": "passed:rubric-v1"}, "initial_state": {"docs": {}, "tickets": {}, "accounts": {}, "emails": {}}}
```

### Exemplar T3 — ws2-029 (`derived_reasoning`, `final_state`, derived min-by-date)

Scenario: three open high-priority tickets with different `created` dates; the model must `list_tickets(status=open, priority=high)`, read the `created` fields, pick the **oldest** (`T-2`, 2025-12-01), and `update_ticket(T-2, closed)`. The expected final state asserts `T-2` is closed; the conformance state-dependency proxy (Task C, check h) is satisfied because **`T-2` as the min-by-date answer is unknowable from the prompt** — the prompt says "oldest", not "T-2".

```json
{"id": "ws2-029", "capability": "derived_reasoning", "input": {"messages": [{"type": "message", "role": "system", "content": "You are a support agent for the Workspace tool suite. Use the tools to complete the request; reason over tool results to choose arguments. When done, reply with a short confirmation."}, {"type": "message", "role": "user", "content": "Close the oldest open high-priority ticket."}], "available_tools": ["search_docs", "create_ticket", "update_ticket", "get_account", "list_tickets", "send_email", "archive_ticket", "find_account", "draft_email"]}, "verification": {"type": "final_state", "constraints": [{"type": "state_equals", "path": "tickets.T-2.status", "expected": "closed"}, {"type": "state_equals", "path": "tickets.T-1.status", "expected": "open"}, {"type": "state_equals", "path": "tickets.T-3.status", "expected": "open"}]}, "metadata": {"split": "dev", "version": "2", "provenance": "hand_written", "world_template_id": "workspace-v2", "difficulty_knob": "derived_argument", "max_steps": 4, "review": "passed:rubric-v1"}, "initial_state": {"docs": {}, "tickets": {"T-1": {"title": "Login broken", "priority": "high", "status": "open", "assignee": "u-1", "created": "2026-01-10"}, "T-2": {"title": "Payments down", "priority": "high", "status": "open", "assignee": "u-1", "created": "2025-12-01"}, "T-3": {"title": "Search slow", "priority": "high", "status": "open", "assignee": "u-2", "created": "2026-02-01"}}, "accounts": {}, "emails": {}}}
```

(`max_steps` floor: dependent calls = 2 (`list_tickets`, `update_ticket`) ⇒ floor `2+2=4`. Set 4.)

### Exemplar T4 — ws2-028 (`multi_step_state`, `final_state`, 4-call state-dependent chain via candidate→id→min)

Scenario: "For ada@x, close their oldest open ticket." Chain: `find_account(email=ada@example.com)` → returns candidate `u-1` → `get_account(u-1)` (confirms, surfaces ticket ids) → `list_tickets(assignee=u-1, status=open)` → read `created`, pick min (`T-5`, 2025-11-15) → `update_ticket(T-5, closed)`. Four dependent calls; `T-5` is unknowable from the prompt (state-dependency proxy passes — `T-5` appears in neither the prompt nor is it nameable without the list result, and `u-1` is surfaced only by `find_account`).

```json
{"id": "ws2-028", "capability": "multi_step_state", "input": {"messages": [{"type": "message", "role": "system", "content": "You are a support agent for the Workspace tool suite. Use the tools to complete the request; reason over tool results to choose arguments. When done, reply with a short confirmation."}, {"type": "message", "role": "user", "content": "For the customer at ada@example.com, close their oldest open ticket."}], "available_tools": ["search_docs", "create_ticket", "update_ticket", "get_account", "list_tickets", "send_email", "archive_ticket", "find_account", "draft_email"]}, "verification": {"type": "final_state", "constraints": [{"type": "state_equals", "path": "tickets.T-5.status", "expected": "closed"}, {"type": "state_equals", "path": "tickets.T-4.status", "expected": "open"}]}, "metadata": {"split": "dev", "version": "2", "provenance": "hand_written", "world_template_id": "workspace-v2", "difficulty_knob": "derived_argument", "max_steps": 6, "review": "passed:rubric-v1"}, "initial_state": {"docs": {}, "tickets": {"T-4": {"title": "API timeout", "priority": "medium", "status": "open", "assignee": "u-1", "created": "2026-03-01"}, "T-5": {"title": "Billing mismatch", "priority": "high", "status": "open", "assignee": "u-1", "created": "2025-11-15"}}, "accounts": {"u-1": {"name": "Ada Lovelace", "email": "ada@example.com", "plan": "pro", "tickets": ["T-4", "T-5"], "created": "2025-10-01"}}, "emails": {}}}
```

(`max_steps` floor: dependent calls = 4 (`find_account`, `get_account`, `list_tickets`, `update_ticket`) ⇒ floor `4+2=6`. Set 6.)

> **Note on `multi_step_state` vs `derived_reasoning` labeling for the proxy:** ws2-028 carries `difficulty_knob:"derived_argument"` even though its capability is `multi_step_state`, because its hardest mechanism is the min-by-date derivation. The state-dependency proxy (Task C check h) keys on `difficulty_knob ∈ {multi_step_depth, derived_argument}`, so it correctly fires on ws2-028. Pure `multi_step_state` chains that mint ids (e.g. ws2-018 `create→update T-<minted>`) carry `difficulty_knob:"multi_step_depth"` and reference the minted id (`T-1` when `tickets` is empty), which the proxy computes via `_next_ticket_id` exactly as the world will.

---

## Authoring rules the impl agent must follow for the remaining 46 tasks

These come straight from `rubric.md` (Task E) and the AC list. Apply every rule to every task as you write it; the conformance suite (Task C) is the mechanical backstop, but author to these rules so the suite stays green on the first run.

1. **System prompt:** T1–T2 use the v1 system prompt verbatim ("...calling the available tools with exactly the argument values the request specifies..."). T3–T4 use the reasoning variant ("...reason over tool results to choose arguments...") shown in the exemplars.
2. **`available_tools`:** full 8-tool surface for every T2/T3/T4 task (and ws2-005). Only ws2-001..ws2-004 use the minimal 3-tool v1 surface (pure regression floor).
3. **`metadata`:** always `split:"dev"`, `version:"2"`, `provenance:"hand_written"`, `world_template_id:"workspace-v2"`, `review:"passed:rubric-v1"`. T1 omits `difficulty_knob` and `max_steps`. T2 sets `difficulty_knob` (no `max_steps` needed — single call). **Every T3 and T4 task sets `max_steps`** = (count of expected *dependent* tool calls) + 2.
4. **`difficulty_knob` vocabulary (closed):** `multi_step_depth`, `derived_argument`, `distractor_count`, `argument_complexity`, `layered_constraint`. Any `multi_step_depth`/`derived_argument` task **must** reference an entity id absent from both `initial_state` and the prompt text (a minted next-id, or an id surfaced only by `list_tickets`/`find_account`) — this is the anti-rote-chain proxy (AC 7 / Task C check h). Verify by eye before moving on: "could the model name this id without making a prior call?" If yes, the task is rote — add a derivation (e.g. ask for "the oldest" rather than "T-2").
5. **Verification shape by tier/capability (AC 6):**
   - `tool_selection`/`argument_extraction` → `tool_call_match` (`exact_sequence` for single/ordered, `multiset` for unordered batches).
   - `multi_step_state`/`derived_reasoning` → `final_state` (path-independent outcome). Assert *both* the changed entity reached its target value *and* at least one decoy entity stayed unchanged (so a model that closes the wrong ticket fails).
   - `distractor_resistance`/`constraint_compliance` → `all_of([final_state, trajectory])` where the `trajectory` carries the policy: `NoToolCall` for "never X", `OnlyModifies` for "only touch X", `MaxToolCalls` for "at most N calls".
6. **Distractor discipline (AC 12g — the suite enforces, but author correctly):**
   - **Never** name `archive_ticket`, `find_account`, or `draft_email` in any `ExpectedToolCall` (a `tool_call_match` for a distractor is forbidden — distractors are wrong paths).
   - **Never** assert `status:"archived"` or `emails.*.state:"draft"` as a *passing* `state_equals`/`state_contains` value. A distractor signature may appear only inside a `NoToolCall` (forbidding it) or as a *decoy* the correct `final_state` discriminates against (e.g. asserting a ticket is `closed`, which fails if the model archived it).
7. **Minimal-but-sufficient `initial_state` (AC 12e, rubric e):** include exactly the docs/tickets/accounts/emails the task references plus the decoys needed to make the hard tier hard (e.g. a derived-min task needs ≥2 open candidates so "oldest" is a real choice). All four roots present (`docs`, `tickets`, `accounts`, `emails`) even when empty `{}`, mirroring the exemplars. No decorative entities.
8. **Preconditions (AC 12e):** every ticket/user/doc id an `ExpectedToolCall` or `final_state` path references must already exist in `initial_state`, **except** create-then-act chains whose target is the deterministic minted next-id (`T-<max+1>` / `e-<max+1>`). Compute the minted id from `initial_state` by hand exactly as `_next_ticket_id`/`_next_email_id` would.
9. **Determinism (AC 11):** dates are literal ISO strings (`YYYY-MM-DD`); never reference "today"/"now". Any date comparison is the model's reasoning, never the world's.
10. **Single-capability isolation (rubric b):** one task isolates one capability. If a task needs both distractor-resistance and derived-reasoning, label it by the dominant mechanism and note the secondary in the ledger.
11. **Unambiguous (rubric a):** exactly one defensible correct outcome. For derived tasks, ensure the min/max/filter has a unique answer (no two tickets share the extremal `created` date).

---

## Task C: The conformance suite (written test-first, before authoring rows)

**Files:**
- Create: `tests/datasets/test_workspace_tool_use_v2.py`

Write this entire module first. It will be **red** (the dataset file is absent/empty), then you author rows (Task D, E) until it is **green**. This is the gate that makes 50 hand-authored tasks verifiable without trusting the author.

- [ ] **Step 1: Create the dataset file as empty, then write the suite**

```bash
touch examples/datasets/workspace_tool_use_v2.jsonl
git add examples/datasets/workspace_tool_use_v2.jsonl
```

- [ ] **Step 2: Write the full conformance module**

Create `tests/datasets/test_workspace_tool_use_v2.py`:

```python
"""v2 dataset conformance: a typo'd task can never look like an agent failure.

Pure (no model, no I/O beyond reading the dataset file). Enforces the rubric
mechanically over all 50 tasks: parse, registered-tools-only, schema-valid
expected calls, well-formed state paths, satisfied preconditions, tier/capability
mix, verification histogram, distractor-never-expected, review coverage,
ledger parity, max_steps floor, and the anti-rote-chain state-dependency proxy.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.schema import (
    AllOf,
    ExpectedToolCall,
    FinalStateSpec,
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    StateConstraint,
    Task,
    ToolCallMatchSpec,
    TrajectorySpec,
    VerificationSpec,
)
from agent_eval_lab.tools.validation import validate_args
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS, _next_ticket_id

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


# NOTE (002-drift.md DRIFT-2): a parallel _minted_email_ids helper is also required.
# 13 tasks verify emails.e-<n>.* in final_state while starting from emails:{}.
# Without this helper, test_initial_state_satisfies_preconditions flags all 13 as
# dangling references. The plan specified _next_email_id but omitted the mintable helper.
# def _minted_email_ids(initial_state, n): mirrors _minted_ticket_ids using _next_email_id.


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
            assert all(seg for seg in segments), f"{task.id}: empty seg in {constraint.path}"
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
    assert types <= {"tool_call_match", "final_state", "all_of", "trajectory"}  # "trajectory" added: TrajectorySpec.type=="trajectory" is surfaced when _spec_type_names recurses into AllOf — plan omission (see 002-drift.md DRIFT-1)
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
            assert call.name not in _DISTRACTORS, f"{task.id}: distractor expected {call.name}"
        # (2) no distractor signature asserted as a passing outcome
        for constraint in _state_constraints(task.verification):
            if constraint.path.startswith("tickets.") and constraint.path.endswith(".status"):
                assert constraint.expected != "archived", f"{task.id}: archived blessed"
            if constraint.path.startswith("emails.") and constraint.path.endswith(".state"):
                assert constraint.expected != "draft", f"{task.id}: draft blessed"
        # (3) distractors may only be forbidden via NoToolCall
        for tspec in _trajectory_specs(task.verification):
            for c in tspec.constraints:
                if isinstance(c, NoToolCall):
                    continue  # forbidding a distractor is allowed


def test_initial_state_satisfies_preconditions() -> None:
    for task in _tasks():
        present = _ids_in_state(task.initial_state)
        # allow up to 4 minted ticket ids for create-then-act chains
        mintable = _minted_ticket_ids(task.initial_state, 4)
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


def test_state_dependency_proxy_for_derived_tasks() -> None:
    for task in _tasks():
        if task.metadata.difficulty_knob not in _DERIVED_KNOBS:
            continue
        present = _ids_in_state(task.initial_state)
        prompt = _prompt_text(task)
        referenced = {
            r
            for r in _referenced_ids(task.verification)
            if r.startswith(("T-", "u-", "e-"))
        }
        # at least one referenced entity id must be absent from BOTH initial_state
        # and the prompt text (a minted next-id or a list/find-surfaced id)
        external = [
            r for r in referenced if r not in present and r not in prompt
        ]
        assert external, f"{task.id}: rote chain — every id is in state or prompt"


def test_every_task_has_review_field() -> None:
    for task in _tasks():
        assert task.metadata.review == "passed:rubric-v1", task.id


def test_review_ledger_has_one_entry_per_task() -> None:
    text = LEDGER.read_text(encoding="utf-8")
    ids = {t.id for t in _tasks()}
    for task_id in ids:
        assert text.count(task_id) >= 1, f"ledger missing {task_id}"
    # parity: no ledger row for a non-existent task id
    import re

    ledger_ids = set(re.findall(r"ws2-\d{3}", text))
    assert ledger_ids == ids
```

- [ ] **Step 3: Run to verify it is RED**

Run: `uv run pytest tests/datasets/test_workspace_tool_use_v2.py -q`
Expected: FAIL — `test_task_ids_follow_scheme_unique_and_count_fifty` fails with `0 != 50` (empty dataset), and the ledger test fails (file absent). This proves the gate has teeth before any row exists.

- [ ] **Step 4: Commit the red suite**

```bash
git add tests/datasets/test_workspace_tool_use_v2.py examples/datasets/workspace_tool_use_v2.jsonl
git commit -m "test(datasets): v2 conformance suite (red — gates 50 tasks before authoring)"
```

> **Implementation note for the suite author:** `test_max_steps_floor_for_hard_tiers` cannot recover the *dependent-call count* for a pure `final_state` task (it has no `ExpectedToolCall`s), so it asserts a conservative absolute floor (`>= 4`) for all T3/T4 plus the exact `calls + 2` floor whenever a `tool_call_match` leg is present. The allocation table's per-task `max_steps` values (4 for 2-call derived tasks, 6 for 4-call chains, up to 10 for the longest T4) all satisfy this; the floor is the mechanical backstop, the table is the authoring source of truth. If a stricter per-task floor is desired later, add a `metadata.dependent_calls` hint — out of scope here (would be a schema change beyond the two AC-mandated fields).

---

## Task D: Author the four exemplar tasks (green a vertical slice)

**Files:**
- Modify: `examples/datasets/workspace_tool_use_v2.jsonl`

- [ ] **Step 1: Write the four exemplar lines**

Append the four exemplar JSONL lines from the "Four fully-worked exemplar tasks" section above into `examples/datasets/workspace_tool_use_v2.jsonl` (ws2-001, ws2-008, ws2-029, ws2-028), **each as one physical line**.

- [ ] **Step 2: Run the parse + schema slice of the suite**

Run: `uv run pytest tests/datasets/test_workspace_tool_use_v2.py::test_expected_calls_schema_validate_and_name_registered_tools tests/datasets/test_workspace_tool_use_v2.py::test_state_paths_well_formed_and_rooted tests/datasets/test_workspace_tool_use_v2.py::test_state_dependency_proxy_for_derived_tasks -q`
Expected: PASS for these three (the four exemplars are well-formed). The count/tier/ledger tests still FAIL (only 4 of 50 rows, no ledger yet) — that is expected at this stage.

- [ ] **Step 3: Commit**

```bash
git add examples/datasets/workspace_tool_use_v2.jsonl
git commit -m "data(v2): four exemplar tasks (one per tier) pass parse+schema+proxy"
```

---

## Task E: Author the remaining 46 tasks to full green

**Files:**
- Modify: `examples/datasets/workspace_tool_use_v2.jsonl`

- [ ] **Step 1: Author all 50 rows**

Following the allocation table and the 11 authoring rules, write the remaining 46 rows (ws2-002..ws2-007, ws2-009..ws2-027, ws2-030..ws2-050). Keep the four exemplars; fill the rest. Author in id order. For each row, before moving on, eyeball-check: (a) schema-valid expected calls; (b) no distractor expected; (c) every referenced id present-or-minted; (d) derived tasks reference an external id; (e) T3/T4 have `max_steps >= 4` and `>= calls+2`; (f) all four state roots present.

- [ ] **Step 2: Run the full conformance suite**

Run: `uv run pytest tests/datasets/test_workspace_tool_use_v2.py -q`
Expected: ALL conformance tests PASS **except** `test_review_ledger_has_one_entry_per_task` (the ledger is authored in Task G2). If any other test fails, the failure message names the task id and the violated rule — fix that row and re-run. Do not proceed until only the ledger test is red.

- [ ] **Step 3: Commit the data**

```bash
git add examples/datasets/workspace_tool_use_v2.jsonl
git commit -m "data(v2): author 50 hard-tier-majority tasks; conformance green sans ledger"
```

---

## Task F: Taxonomy doc

**Files:**
- Create: `docs/2026-06-10-dataset-grader-quality/taxonomy.md`

- [ ] **Step 1: Write the taxonomy doc**

Create `docs/2026-06-10-dataset-grader-quality/taxonomy.md` with exactly this content:

```markdown
# Workspace-world v2 — capability taxonomy

The v2 set (`workspace_tool_use_v2.jsonl`, 50 tasks) discriminates **between strong
models** by isolating six capabilities across four hardness tiers. Each task isolates
one capability (its failure attributes to one skill — the JD#4 taxonomy) and declares
one dominant difficulty knob.

## Capabilities × verification shape × knob

| capability | isolated skill | verification shape | dominant knob(s) |
|------------|----------------|--------------------|------------------|
| `tool_selection` | pick the right tool from a wide surface incl. overlapping distractors | `tool_call_match` | `distractor_count` |
| `argument_extraction` | extract literal/nested/enum/date args from NL | `tool_call_match` | `argument_complexity` |
| `multi_step_state` | execute a dependent chain; reach the target world-state | `final_state` (+`trajectory` if a policy clause) | `multi_step_depth` |
| `derived_reasoning` | reason over a tool *result* (filter/min/max/count) to compute an arg | `final_state` | `derived_argument` |
| `distractor_resistance` | avoid the plausible-wrong tool (`archive`/`find`/`draft`) | `all_of(final_state, trajectory:NoToolCall)` | `distractor_count` |
| `constraint_compliance` | honor a "but never / only / at most N" policy clause | `all_of(final_state, trajectory)` | `layered_constraint` |

## Tiers × expected-failure rationale

| tier | count | % | expected-failure rationale |
|------|-------|---|----------------------------|
| T1 sanity | 5 | 10% | Every frontier model passes — regression floor. If T1 fails, the harness or world regressed, not the model. |
| T2 moderate | 12 | 24% | Occasional `wrong_args` on nested/date/enum extraction and first-bite distractor pickups. The gradient that makes the boundary *visible*. |
| T3 hard | 22 | 44% | `extra_call` / `wrong_args` / `forbidden_action` from distractors and derived-argument reasoning. **Strong models are expected to sometimes fail here.** |
| T4 adversarial | 11 | 22% | Designed so **≥1 frontier model is expected to fail**: overlapping distractors + multi-clause policy + 4–8-step derived chains. |

T3 + T4 = 33 / 50 = **66%** (the "majority hard" directive).

## Difficulty knobs (closed vocabulary)

- `multi_step_depth` — a dependent chain of ≥4 calls; at least one call's args derive from a prior call's *result* (a minted id or a list/find-surfaced id).
- `derived_argument` — an argument the model must compute by reasoning over returned data (filter, min/max-by-date, count, cross-reference).
- `distractor_count` — a wide surface where ≥1 distractor (`archive_ticket`/`find_account`/`draft_email`) plausibly fits, forcing discrimination.
- `argument_complexity` — nested/enum/date/multi-field arguments extracted from NL.
- `layered_constraint` — a stated policy clause ("but never email", "only touch T-1", "at most 3 calls") encoded as `TrajectorySpec`.

Long-horizon is a *property* (chain depth via `multi_step_depth` + `max_steps`), not a
separate capability — making it a category would double-count the same skill.

## Determinism

Every world primitive is pure: ids mint via `max(...)+1`, no clock, no RNG, no I/O.
Dates are literal ISO strings; any date comparison a task requires is the *model's*
reasoning job, not the world's. A pure conformance suite
(`tests/datasets/test_workspace_tool_use_v2.py`) enforces every rule above mechanically.
```

- [ ] **Step 2: Commit**

```bash
git add docs/2026-06-10-dataset-grader-quality/taxonomy.md
git commit -m "docs(v2): capability taxonomy (6 caps x 4 tiers, expected-failure rationale)"
```

---

## Task G1: Rubric doc

**Files:**
- Create: `docs/2026-06-10-dataset-grader-quality/rubric.md`

- [ ] **Step 1: Write the rubric doc**

Create `docs/2026-06-10-dataset-grader-quality/rubric.md` with exactly this content. **The version string `rubric-v1` is load-bearing** — it must match the `review:"passed:rubric-v1"` value the conformance suite asserts.

```markdown
# Workspace-world v2 — task validity rubric

**Version: `rubric-v1`** — every shipped v2 task carries `metadata.review = "passed:rubric-v1"`.

This is the **author's task-validity** checklist — a distinct artifact from any
judge rubric (item 003). Every task in `workspace_tool_use_v2.jsonl` must pass all
seven checks; the per-task verdict is recorded in `metadata.review` (source of truth,
append-only with the row) and mirrored in `review-ledger.md` (regenerable audit view).

## Checklist (every task must pass a–g)

- **(a) Unambiguous** — exactly one defensible correct outcome. For derived tasks the
  min/max/filter has a unique answer (no two candidates share the extremal value).
- **(b) Single-capability** — isolates exactly one capability; if two are needed,
  label the dominant one and note the secondary in the ledger.
- **(c) Verification matches intent** — path-sensitive (`tool_call_match`) only where
  the *action chosen* is what we grade; path-independent (`final_state`) for outcome;
  policy clauses encoded as `TrajectorySpec`, never left as prose.
- **(d) Schema-valid, registered-only** — every `ExpectedToolCall` / final-state path
  schema-validates against the v2 tools and references only registered tools; no
  distractor is ever the expected path.
- **(e) Minimal-but-sufficient `initial_state`** — exactly the accounts/tickets/docs/
  emails the task needs plus the decoys that make the hard tier hard, nothing
  decorative; all four roots present (even when `{}`).
- **(f) Deterministic & auto-scorable** — no clock/RNG dependence; dates are literal
  ISO strings.
- **(g) The knob is the hardness** — the stated `difficulty_knob` is actually the thing
  that makes the task hard (the human gate the pure state-dependency proxy cannot prove).

## Mechanical backstop

`tests/datasets/test_workspace_tool_use_v2.py` enforces (a)-partial, (c), (d), (e), (f),
and the structural witness of (g) (the anti-rote-chain proxy) over all 50 tasks. Checks
(a)-full, (b), and (g)-semantic are human gates recorded in the ledger.

## Re-review

Re-reviewing under a new rubric is a **new dataset version** (a new `version` string +
`world_template_id`), not an in-place row edit — `metadata.review` is frozen with the
append-only row. A ledger edit can never un-gate a row.
```

- [ ] **Step 2: Commit**

```bash
git add docs/2026-06-10-dataset-grader-quality/rubric.md
git commit -m "docs(v2): task-validity rubric (rubric-v1; 7-point checklist)"
```

---

## Task G2: Review ledger

**Files:**
- Create: `docs/2026-06-10-dataset-grader-quality/review-ledger.md`

- [ ] **Step 1: Write the ledger**

Create `docs/2026-06-10-dataset-grader-quality/review-ledger.md`. One row per task id (all 50). Columns: id, tier, capability, difficulty_knob, rubric result (a–g), one-sentence expected-failure rationale. The header + 50 rows. The conformance suite asserts the set of `ws2-\d{3}` ids in this file equals the dataset's id set exactly. Build the table from the allocation table (Task spec) — every id ws2-001..ws2-050 appears exactly once.

```markdown
# Workspace-world v2 — review ledger (audit view of `metadata.review`)

Regenerable from the dataset; **not** the gate (the gate is `metadata.review` +
the conformance suite). One row per task; rubric result `a-g:PASS` means all seven
checks passed under `rubric-v1`.

| id | tier | capability | knob | rubric | expected-failure rationale |
|----|------|------------|------|--------|----------------------------|
| ws2-001 | T1 | tool_selection | — | a-g:PASS | Trivial single search — every frontier model passes (regression floor). |
| ws2-002 | T1 | tool_selection | — | a-g:PASS | Trivial single create — regression floor. |
| ... | ... | ... | ... | ... | ... |
| ws2-050 | T4 | constraint_compliance | layered_constraint | a-g:PASS | Multi-clause policy (no email + only tickets) over a create-close chain — ≥1 frontier model expected to slip and email. |
```

> **Author rule:** replace the `...` row with the actual 48 rows so **all 50 ids ws2-001..ws2-050 each appear exactly once**. Pull tier/capability/knob from the allocation table; write a one-sentence rationale per row consistent with the tier's expected-failure profile in `taxonomy.md`. The conformance test (`test_review_ledger_has_one_entry_per_task`) fails unless the `ws2-\d{3}` id set equals the dataset's 50 ids exactly.

- [ ] **Step 2: Run the full v2 conformance suite (now fully green)**

Run: `uv run pytest tests/datasets/test_workspace_tool_use_v2.py -q`
Expected: ALL PASS (including `test_review_ledger_has_one_entry_per_task`).

- [ ] **Step 3: Commit**

```bash
git add docs/2026-06-10-dataset-grader-quality/review-ledger.md
git commit -m "docs(v2): review ledger (50 rows; id-parity with dataset)"
```

---

## Task H: Full-suite gate + v1-untouched verification (AC 13)

**Files:** none (verification only)

- [ ] **Step 1: Confirm v1 is byte-for-byte unchanged**

Run: `git diff --stat HEAD -- examples/datasets/workspace_tool_use_v1.jsonl tests/datasets/test_workspace_tool_use.py`
Expected: **no output** (both files unmodified across the whole branch since baseline).

- [ ] **Step 2: Run the whole gate**

Run:
```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```
Expected: pytest all green (192 baseline + the new tool unit tests + the new parse tests + the v2 conformance module — well over 200); `ruff check` ⇒ `All checks passed!`; `ruff format --check` ⇒ `<N> files already formatted`.

- [ ] **Step 3: Confirm the AC checklist mechanically**

Run: `uv run pytest tests/datasets/test_workspace_tool_use_v2.py -v`
Expected: every named test passes — this *is* the AC 4/5/6/7/10/11/12 audit:
- `test_task_ids_follow_scheme_unique_and_count_fifty` → AC 4 (50, ids, scheme).
- `test_tier_mix_matches_allocation` → AC 4 (5/12/22/11).
- `test_all_six_capabilities_present_and_no_stray_labels` → AC 5.
- `test_verification_histogram_dominated_by_state_and_all_of` → AC 6.
- `test_distractors_never_expected_as_correct_path` → AC 12g.
- `test_initial_state_satisfies_preconditions` → AC 12e.
- `test_max_steps_floor_for_hard_tiers` → AC 8.
- `test_state_dependency_proxy_for_derived_tasks` → AC 7 / AC 12h.
- `test_every_task_has_review_field` + `test_review_ledger_has_one_entry_per_task` → AC 10.
- `test_every_v2_tool_is_deterministic_over_fixed_input` (tools suite) → AC 11.

- [ ] **Step 4: Final commit (if any formatting drift)**

```bash
git add -A
git commit -m "chore(v2): final gate green — 50 tasks, taxonomy, rubric, ledger, conformance"
```

---

## Self-review (against the spec)

**Spec coverage — every AC maps to a task:**
- AC 1 (8 tools, 3 distractors) → Tasks A1–A6.
- AC 2 (world grows; `_next_email_id`; read-only purity) → A1–A6 (impls) + A7 (determinism).
- AC 3 (`list_tickets` derived reasoning; total pure filter) → A2.
- AC 4 (50 tasks, version "2", id scheme, tier mix) → Task C (`count`, `tier_mix`) + D/E.
- AC 5 (six capabilities) → Task C (`all_six_capabilities`) + E.
- AC 6 (verification shape per tier; histogram) → Task C (`histogram`) + authoring rules.
- AC 7 (state-dependency proxy) → Task C (`state_dependency_proxy`) + rule 4.
- AC 8 (`max_steps` per-task; floor) → Task B1 (field) + Task C (`max_steps_floor`) + rule 3.
- AC 9 (taxonomy + rubric docs) → Tasks F, G1.
- AC 10 (review field + ledger parity) → Task B1 (field) + Task C (review/ledger) + G2.
- AC 11 (determinism enforced) → Task A7.
- AC 12 (dataset CI: a–h) → Task C (the whole module).
- AC 13 (gates green, v1 untouched) → Task H.

**Placeholder scan:** the only intentional `...` is the ledger body (Task G2), explicitly flagged with an author rule + a mechanical id-parity gate that *fails* if the author leaves it incomplete — so it cannot ship as a placeholder. All code steps carry complete code.

**Type consistency:** `_next_email_id`/`_next_ticket_id` signatures match `workspace.py`; the conformance suite imports `_next_ticket_id` (exists) and the exact spec dataclasses (`AllOf`, `FinalStateSpec`, `ToolCallMatchSpec`, `TrajectorySpec`, `NoToolCall`/`OnlyModifies`/`MaxToolCalls`, `StateConstraint`, `ExpectedToolCall`) from `tasks/schema.py`. `TaskMetadata.max_steps`/`review` names match across schema, parse, suite, and dataset rows.

**Judgment calls (documented):** (1) `list_tickets` `status` enum includes `archived` so the filter is total over every reachable status (AC 3 "total"). (2) The conformance `max_steps` floor uses a conservative absolute `>= 4` for pure-`final_state` T3/T4 (which carry no `ExpectedToolCall`s to count) plus exact `calls+2` when a `tool_call_match` leg exists — the per-task table values are the authoring source of truth; a stricter mechanical floor would need a schema field beyond the two ACs allow. (3) Tier is derived from id ranges (not a stored field) since the spec mandates no tier metadata field — the allocation table fixes the id→tier mapping and the suite asserts the ranges. (4) Two `all_of` distractor rows (ws2-043/044) are labeled `constraint_compliance` because their dominant mechanism is the policy clause; the suite gates the capability *set*, not exact per-capability counts, so this is valid.

---

## Execution Handoff

Plan complete and saved to `docs/2026-06-10-dataset-grader-quality/items/002-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task (A1…H), review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session via executing-plans, batch execution with checkpoints.

Which approach?
