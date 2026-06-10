# Workspace-world v2 — review ledger (audit view of `metadata.review`)

Regenerable from the dataset; **not** the gate (the gate is `metadata.review` +
the conformance suite). One row per task; rubric result `a-g:PASS` means all seven
checks passed under `rubric-v1`.

| id | tier | capability | knob | rubric | expected-failure rationale |
|----|------|------------|------|--------|----------------------------|
| ws2-001 | T1 | tool_selection | — | a-g:PASS | Trivial single search — every frontier model passes (regression floor). |
| ws2-002 | T1 | tool_selection | — | a-g:PASS | Trivial single create — regression floor. |
| ws2-003 | T1 | tool_selection | — | a-g:PASS | Trivial single update — regression floor. |
| ws2-004 | T1 | argument_extraction | — | a-g:PASS | Trivial priority extraction — regression floor. |
| ws2-005 | T1 | tool_selection | — | a-g:PASS | Trivial get_account on full surface — regression floor. |
| ws2-006 | T2 | tool_selection | distractor_count | a-g:PASS | get_account vs find_account when id is known — occasional selection error by weaker models. |
| ws2-007 | T2 | tool_selection | distractor_count | a-g:PASS | send_email vs draft_email — first-bite distractor pickup possible on weaker models. |
| ws2-008 | T2 | argument_extraction | argument_complexity | a-g:PASS | Medium priority extraction with full surface — occasional wrong_args on priority enum. |
| ws2-009 | T2 | argument_extraction | argument_complexity | a-g:PASS | Multi-field email extraction — occasional wrong_args on subject/body fields. |
| ws2-010 | T2 | argument_extraction | argument_complexity | a-g:PASS | list_tickets with status filter — occasional omission of status argument. |
| ws2-011 | T2 | argument_extraction | argument_complexity | a-g:PASS | list_tickets with two filters — occasional missing filter or wrong combination. |
| ws2-012 | T2 | tool_selection | distractor_count | a-g:PASS | update_ticket vs archive_ticket — archive distractor present, close must be chosen. |
| ws2-013 | T2 | argument_extraction | argument_complexity | a-g:PASS | High-priority ticket creation — occasional wrong priority value. |
| ws2-014 | T2 | argument_extraction | argument_complexity | a-g:PASS | Reopen ticket (status open) — occasional wrong status direction. |
| ws2-015 | T2 | argument_extraction | argument_complexity | a-g:PASS | Multi-field email extraction with timestamp in body — field extraction error possible. |
| ws2-016 | T2 | tool_selection | distractor_count | a-g:PASS | get_account vs find_account — distractor present, weaker models may pick find_account. |
| ws2-017 | T2 | multi_step_state | multi_step_depth | a-g:PASS | Create then close — straightforward 2-step chain; T2 floor for multi_step_state. |
| ws2-018 | T3 | multi_step_state | multi_step_depth | a-g:PASS | Create then close the just-filed ticket (minted id) — state-dependency on minted T-1; strong models may slip on id tracking. |
| ws2-019 | T3 | multi_step_state | derived_argument | a-g:PASS | get_account then file ticket titled with account name — argument derives from result; wrong_args if name not read correctly. |
| ws2-020 | T3 | multi_step_state | distractor_count | a-g:PASS | list_tickets → close each for u-1 while archive_ticket is present — multi-step with distractor pressure; extra_call or forbidden_action possible. |
| ws2-021 | T3 | multi_step_state | multi_step_depth | a-g:PASS | Create two tickets then close both (two minted ids) — minted id tracking over 4 calls; extra_call or missing_call possible. |
| ws2-022 | T3 | multi_step_state | derived_argument | a-g:PASS | get_account → email with plan name — derived argument from account result; wrong body if plan misread. |
| ws2-023 | T3 | multi_step_state | derived_argument | a-g:PASS | list_tickets → count → email count — derived count argument; wrong body if count logic fails. |
| ws2-024 | T3 | multi_step_state | multi_step_depth | a-g:PASS | Create, close, email (3-step with minted id) — minted id threading and send vs draft distractor. |
| ws2-025 | T3 | multi_step_state | multi_step_depth | a-g:PASS | find_account → get_account → create ticket — 3-step where u-1 is surfaced by find_account result. |
| ws2-026 | T3 | multi_step_state | distractor_count | a-g:PASS | list_tickets → close all high-priority; archive_ticket present — multi-step with persistent distractor; forbidden_action possible. |
| ws2-027 | T3 | multi_step_state | derived_argument | a-g:PASS | Create ticket then email the minted id — derived argument (ticket id from create result); wrong_args if id not tracked. |
| ws2-028 | T3 | multi_step_state | argument_complexity | a-g:PASS | find_account → list_tickets → pick oldest → close — 4-step with date reasoning; wrong ticket if min-date not computed; strong models expected to sometimes fail. |
| ws2-029 | T3 | derived_reasoning | argument_complexity | a-g:PASS | list_tickets → pick oldest open high-priority by date — min-by-date reasoning; wrong ticket if dates not compared. |
| ws2-030 | T3 | derived_reasoning | argument_complexity | a-g:PASS | list_tickets → pick newest open ticket — max-by-date reasoning; wrong ticket if dates not compared correctly. |
| ws2-031 | T3 | derived_reasoning | derived_argument | a-g:PASS | list_tickets → count open for u-2 → email count — derived count; wrong body if count miscomputed. |
| ws2-032 | T3 | derived_reasoning | derived_argument | a-g:PASS | list_tickets(high, u-1) → email titles — cross-reference; wrong body if titles not aggregated. |
| ws2-033 | T3 | derived_reasoning | argument_complexity | a-g:PASS | list_tickets → pick oldest closed — min-by-date on closed status; wrong ticket if date logic fails. |
| ws2-034 | T3 | derived_reasoning | derived_argument | a-g:PASS | list_tickets → oldest open → get_account(assignee) → email — 3-step cross-reference; wrong email address if assignee not fetched. |
| ws2-035 | T3 | derived_reasoning | argument_complexity | a-g:PASS | list_tickets → count gate (>2?) → close oldest — conditional reasoning; wrong ticket or no action if gate misread. |
| ws2-036 | T3 | derived_reasoning | derived_argument | a-g:PASS | find_account → list_tickets → pick oldest → email id — 3-step with min-by-date id to email; wrong id if date reasoning fails. |
| ws2-037 | T3 | derived_reasoning | argument_complexity | a-g:PASS | list_tickets → pick two oldest high-priority → close both — rank-2 min-by-date; wrong pair if ordering misread. |
| ws2-038 | T3 | derived_reasoning | argument_complexity | a-g:PASS | list_tickets → pick highest priority open ticket — priority hierarchy reasoning; wrong ticket if ordering logic fails. |
| ws2-039 | T3 | derived_reasoning | argument_complexity | a-g:PASS | find_account → list_tickets → pick newest — max-by-date for grace@x; wrong ticket if find_account result misread. |
| ws2-040 | T4 | distractor_resistance | distractor_count | a-g:PASS | send_email vs draft_email under direct instruction — draft_email distractor; forbidden_action if draft chosen. |
| ws2-041 | T4 | distractor_resistance | distractor_count | a-g:PASS | update_ticket vs archive_ticket under explicit constraint — archive distractor; forbidden_action if archived. |
| ws2-042 | T4 | distractor_resistance | distractor_count | a-g:PASS | send_email with id known; find_account forbidden explicitly — strong models may still call find_account as a confirm step. |
| ws2-043 | T4 | constraint_compliance | layered_constraint | a-g:PASS | Create, close, email; never archive, never draft — two NoToolCall constraints; ≥1 frontier model expected to slip on one. |
| ws2-044 | T4 | constraint_compliance | layered_constraint | a-g:PASS | list → close all for u-2; never archive — policy + multi-step; forbidden_action if archive used for any ticket. |
| ws2-045 | T4 | distractor_resistance | distractor_count | a-g:PASS | send_email (not draft) with explicit instruction — draft_email distractor under "make sure it is sent" framing. |
| ws2-046 | T4 | distractor_resistance | distractor_count | a-g:PASS | Email u-7 with id given; find_account explicitly forbidden — models that habitually confirm by email-search fail. |
| ws2-047 | T4 | constraint_compliance | layered_constraint | a-g:PASS | search_docs only; create_ticket forbidden — no-ticket policy; models that open a ticket in response fail. |
| ws2-048 | T4 | constraint_compliance | layered_constraint | a-g:PASS | Close T-1 only; OnlyModifies T-1 — constraint on scope; models that also touch T-2 fail. |
| ws2-049 | T4 | constraint_compliance | layered_constraint | a-g:PASS | Close oldest open ticket in ≤3 calls — MaxToolCalls 3 constraint; models that over-call fail. |
| ws2-050 | T4 | constraint_compliance | layered_constraint | a-g:PASS | Create + close ticket; no email, only tickets — multi-clause policy (NoToolCall send_email + OnlyModifies tickets); ≥1 frontier model expected to slip and email. |
