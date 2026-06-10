# Item 002 — Workspace-world v2 + taxonomy + rubric + 50 reviewed hard tasks

- **Run:** `docs/2026-06-10-dataset-grader-quality`
- **Date:** 2026-06-10
- **Realizes:** design doc §5 (synthetic tool-world: full tool lineup + difficulty
  knobs), §1 (the reframe: capability-discriminating, contamination-free), §4.4
  (Task shape), §4.3 (verification union, consumed not extended here), §6 (the two
  deterministic verification modes)
- **Depends on (already merged):** item 001 — `FinalStateSpec`, `TrajectorySpec`,
  `AllOf`, the five constraint variants, the pure state/policy/composite graders,
  `final_state` threading, and JSONL parsing of all of the above. This item authors
  *data* that exercises that grader; it ships no new grader code.
- **Extends (current checkout):** `tools/workspace.py` (+ `tools/validation.py`
  unchanged; world state grows `accounts`, `emails`), `tasks/parse.py` (only if a
  parse gap is found — see AC), `examples/datasets/workspace_tool_use_v2.jsonl`
  (new), `tests/datasets/test_workspace_tool_use.py` (extend with a v2 conformance
  module), plus three new docs: a taxonomy doc, a scoring-rubric doc, and a
  per-task review ledger.

## Goal

Build the capability-discriminating successor to the saturated v1 set. v1 (20 tasks,
3 tools, `tool_call_match` only) put three hosted frontier models at pass@1 = pass^3
= 1.000 — it separates models on cost and latency, not accuracy. v2 must draw a
capability boundary *between strong models* by raising the five design-doc difficulty
knobs simultaneously: a wider tool surface with deliberate distractors (≥6 tools incl.
similar-sounding/overlapping schemas), nested/enum/date argument complexity,
multi-step depth (chains of 4–8+ dependent calls where step N's arguments derive from
step N-1's *result*, not from a memorized sequence), layered instruction constraints
expressed as `TrajectorySpec` policy (do X but never email; touch only T-1; at most N
calls), and computed/derived arguments the model must *reason* over returned data to
produce (filter, compare dates, pick max/min, aggregate counts). The hard tiers form
the majority of the set; every task carries a documented expected-failure rationale by
tier so "designed not to saturate" is an auditable property, not a hope. Verification
for the hard multi-step tiers is mostly `FinalStateSpec` (path-independent outcome) +
`TrajectorySpec` policy via `AllOf`; `tool_call_match` survives only for the
selection/extraction tiers; **no `LlmJudgeSpec`** (item 003). The world stays a pure
`apply(tool, args, state) -> (state', outcome)` over `{tickets, docs, accounts,
emails}` with the shared JSON-schema validator, so the dataset is fully deterministic
and auto-scorable, and a fast pure CI check guarantees a typo'd task can never
masquerade as an agent failure.

## Acceptance criteria

Each criterion is independently verifiable by a test, a command, or a documented
artifact.

1. **Tool surface — exactly 8 tools, 3 of them distractors.** `tools/workspace.py`
   registers, in addition to the existing `search_docs`, `create_ticket`,
   `update_ticket`: `get_account`, `list_tickets`, `send_email` (the three §5
   primaries), plus three **distractor** tools chosen to force discrimination, not
   filler: `archive_ticket` (overlaps `update_ticket`; sets `status:"archived"`, a
   *third* status the grader can detect as a wrong path), `find_account` (overlaps
   `get_account` but searches by email and returns *candidates*, so picking it when an
   exact `user_id` is known is a selection error), and `draft_email` (overlaps
   `send_email` but only stages to `emails[*].state="draft"` and does **not** send —
   choosing it when the user said "send" is a silent under-action a `FinalStateSpec`
   catches). Each new tool is a pure impl threaded through `apply`; args validate
   against its JSON schema and a violation returns `ToolFailure` exactly as today. No
   tool performs I/O, randomness, or time reads (see AC 11).

2. **World state grows to `{tickets, docs, accounts, emails}`, all deterministic.**
   `accounts[user_id] = {name, email, plan: enum, tickets: [ids], created: ISO-date}`;
   `emails` is an append-addressed map `{e-1: {to, subject, body, state:
   "sent"|"draft"}}` with a `_next_email_id` helper mirroring `_next_ticket_id`.
   `tickets` gains optional `assignee` (a `user_id`) and `created` (ISO-date) fields so
   date/owner reasoning tasks have data to reason over. `send_email`/`draft_email`
   append to `emails`; `get_account`/`find_account`/`list_tickets` are read-only and do
   not mutate state (their `apply` returns `state` unchanged). All ids are
   deterministic (`max(...)+1`); no `uuid`, no clock.

3. **`list_tickets` enables derived-reasoning tasks.** `list_tickets(status?,
   assignee?, priority?)` returns the matching ticket ids **and their fields** so the
   model can filter/sort/aggregate over the *returned result* (e.g. "close the
   oldest open high-priority ticket" requires reading `created` dates from the list
   result and picking the min — a step-N-depends-on-step-N-1 chain). The filter
   semantics are pure and total (unknown filter value ⇒ empty result, never an error).

4. **`workspace_tool_use_v2.jsonl` has exactly 50 tasks, version `"2"`, hard-tier
   majority.** Every line parses via `tasks/loader.load_tasks` into a `Task`; every
   `metadata.version == "2"`, ~~`metadata.provenance == "hand_authored"`~~
   **`metadata.provenance == "hand_written"`** (see Resolved decision Q7 — match v1's
   canonical value; a synonym would fracture the §9 provenance count),
   `metadata.world_template_id == "workspace-v2"`, `metadata.split == "dev"`. **Task
   ids follow the `ws2-001`…`ws2-050` scheme** (distinct prefix from v1's `ws-NNN`,
   so v1 and v2 task ids never collide when their runs/traces coexist in one report —
   see Resolved decision Q6). The tier
   mix is **T1 sanity 5 (10%), T2 moderate 12 (24%), T3 hard 22 (44%), T4 adversarial
   11 (22%)** — T3+T4 = 33/50 = 66% (the "majority hard" directive). The mix is
   asserted by the conformance test, not merely documented.

5. **Capability taxonomy — six categories, each represented.** Every task's
   `capability` is one of exactly: `tool_selection`, `argument_extraction`,
   `multi_step_state`, `constraint_compliance`, `distractor_resistance`,
   `derived_reasoning`. The conformance test asserts the set of capabilities present
   equals this six-element set (no orphan category, no stray label). The taxonomy doc
   (AC 9) defines each category, the single capability it isolates, and which
   verification shape it uses.

6. **Verification shape matches tier and capability (the design's two modes).**
   - `tool_selection` / `argument_extraction` (T1–T2) use `ToolCallMatchSpec`
     (`exact_sequence` or `multiset`) — path-sensitive, grading the action chosen.
   - `multi_step_state` / `derived_reasoning` / `distractor_resistance` (T3–T4) use
     `FinalStateSpec` (path-independent outcome) and, where a policy constraint is
     stated, an `AllOf(FinalStateSpec, TrajectorySpec)`.
   - `constraint_compliance` uses `AllOf` pairing the outcome the task asks for with a
     `TrajectorySpec` (`NoToolCall` / `OnlyModifies` / `MaxToolCalls`) encoding the
     "but never…/only…/at most…" clause.
   - **No task uses `LlmJudgeSpec` or `OutputMatchSpec`** (judge is item 003;
     output-match has no role in a tool-world hard set). The conformance test asserts
     the verification-type histogram: every spec type present is in
     `{tool_call_match, final_state, all_of}` and `final_state`+`all_of` dominate
     (≥ the T3+T4 count).

7. **Long-horizon depth is real and bounded.** At least 15 tasks require a *dependent*
   chain of ≥4 tool calls where at least one call's arguments are unknowable without a
   prior call's **result** (e.g. `find_account → get_account → list_tickets →
   update_ticket(min-by-date)`). Each such task's `metadata.difficulty_knob` names the
   knob (`multi_step_depth`, `derived_argument`, `distractor_count`,
   `argument_complexity`, `layered_constraint` — a closed vocabulary the taxonomy doc
   defines). Tasks declare a `metadata.max_steps` hint (see AC 8) high enough for the
   intended chain plus the model's read/confirm turns; the harness already streams per
   task, so longer chains are a wall-clock cost, not a correctness risk.

   **State-dependency is enforced, not asserted (anti–rote-chain proxy).** A task can
   be *long yet easy* (eight independent `create_ticket` calls is a rote chain, not a
   capability boundary). To make "step N derives from step N-1's result" an *auditable*
   property rather than prose, the conformance test (AC 12) applies a pure structural
   proxy: **every task whose `difficulty_knob` is `multi_step_depth` or
   `derived_argument` must reference at least one entity id that exists in neither
   `initial_state` nor the user-message text** — i.e. an id that is only obtainable as
   the deterministic minted next-id of a prior create, or as an id/field surfaced by a
   `list_tickets`/`find_account` result. A rote chain (all args present up front) fails
   this proxy; a genuinely state-dependent chain passes it. This is a *necessary*
   structural witness of dependence (a pure test cannot prove the *sufficient* semantic
   property without a live model — that is item 004's job), and the rubric (AC 9) adds
   the human gate "the stated `difficulty_knob` is actually the thing that makes the
   task hard" (rubric item g).

8. **`max_steps` is per-task data, not a global.** `TaskMetadata` gains an optional
   `max_steps: int | None = None` (additive, defaulted ⇒ every existing v1 task and
   call site is unaffected; `tasks/parse.py` reads it when present). The v2 conformance
   test asserts every T3/T4 task sets `max_steps` and that it is ≥ the number of
   expected dependent calls + 2 (headroom for the model's reasoning/confirm turns).
   The runner already takes a *global* `max_steps` (CLI default `6`, consumed by
   `runners/loop.py` as `for _ in range(max_steps)`); wiring the per-task value through
   `runners/multi_run.py`/`cli.py` is a **blocking contract for item 004**, *not*
   implemented here unless the conformance test cannot otherwise be satisfied — this
   item ships the *data* and the schema field, not runner changes. **Item 002's verify
   gate is scoped to parse + schema + conformance (pure, no live model)**; the T3/T4
   chains exceed the global default of 6 and so *cannot* be exercised end-to-end until
   004 threads the per-task budget. Without that wiring every T3/T4 task would stop at
   `max_steps` and grade as a step-limit failure that *looks like* an agent failure but
   is harness starvation — the exact confound AC 12 exists to prevent. The conformance
   floor (`max_steps >= dependent_calls + 2`) proves the dataset is *runnable once
   wired* without running it. Recorded as ADR 0004 and Resolved decision Q2.

9. **Taxonomy doc and rubric doc exist and are self-consistent with the data.** Two
   committed docs under the run dir:
   - `taxonomy.md` — the six capabilities × four tiers grid; for each capability: the
     isolated skill, its verification shape, the difficulty knobs it exercises; for
     each tier: the per-tier **expected-failure rationale** (T1: every frontier model
     passes — sanity/regression floor; T2: occasional `wrong_args` on nested/date
     extraction; T3: `extra_call`/`wrong_args`/`forbidden_action` from distractors and
     derived-argument reasoning — *strong models expected to sometimes fail here*; T4:
     designed so ≥1 frontier model is expected to fail — overlapping distractors +
     multi-clause policy + 6–8-step derived chains). The tier-count table in the doc
     matches AC 4 exactly.
   - `rubric.md` — the per-task **validity** checklist every shipped task must pass:
     (a) unambiguous (exactly one defensible correct outcome); (b) isolates a single
     capability; (c) verification matches intent (path-sensitive vs path-independent
     chosen correctly; policy clauses encoded as `TrajectorySpec`, not prose);
     (d) every `ExpectedToolCall` / final-state path schema-validates against the v2
     tools and references only registered tools; (e) `initial_state` is
     *minimal-but-sufficient* (contains exactly the accounts/tickets/docs the task
     needs and the distractors needed to make the hard tiers hard, nothing decorative);
     (f) deterministic and auto-scorable (no clock/random dependence); (g) the stated
     `difficulty_knob` is actually the thing that makes the task hard.

10. **Per-task review evidence is recorded.** Each of the 50 tasks gains a
    `metadata.review` value (additive optional field on `TaskMetadata`, e.g.
    `review: str | None = None`) set to `"passed:<rubric-version>"` (the rubric doc
    carries a version string), **and** a one-line entry in a committed review ledger
    `review-ledger.md` keyed by task id recording: tier, capability, difficulty_knob,
    the rubric checklist result, and the one-sentence expected-failure rationale. The
    conformance test asserts every task carries `review` and that the ledger has one
    entry per task id (count and id-set match the dataset). Format chosen:
    metadata-field-plus-ledger (both), so the dataset is self-describing *and* the
    review is human-auditable in one place. **The `metadata.review` field — riding the
    append-only row — is the source of truth for review coverage; the `review-ledger.md`
    is a regenerable human-audit view, never the gate.** This keeps the binding record
    inside the append-only dataset row (§9: "provenance on every item; append-only
    versions"): re-reviewing under a new rubric version is a *new dataset version*, not
    an in-place row edit, and a ledger edit can never silently un-gate a row (see
    Resolved decision Q4).

11. **Determinism is enforced, not asserted in prose.** Every new tool impl is a pure
    function of `(args, state)`; a property/conformance test feeds each v2 tool a fixed
    `(args, state)` twice and asserts identical `(state', outcome)`. No tool reads the
    clock, the filesystem, the network, or a RNG. Dates in `initial_state` are literal
    ISO strings; any date comparison the *task* requires is the model's reasoning job,
    not the world's.

12. **Dataset CI — a typo'd task can never look like an agent failure.** A new pure
    conformance module (extending `tests/datasets/test_workspace_tool_use.py` or a
    sibling `test_workspace_tool_use_v2.py`) asserts, over every v2 task: (a) it parses;
    (b) every `available_tools` name is in the v2 `WORKSPACE_TOOLS` registry; (c) every
    `ExpectedToolCall` (including those nested inside `AllOf`) schema-validates against
    its tool via the shared `validate_args`; (d) every `FinalStateSpec` /
    `TrajectorySpec` dot-path is well-formed (non-empty dot-segments) and its leading
    segment names a known state root (`tickets|docs|accounts|emails`); (e) each task's
    `initial_state` already *satisfies its own preconditions* — every ticket id, user
    id, or doc id the expected calls/final-state reference exists in `initial_state`
    (or, for create-then-act chains, is the deterministic next id the world will mint);
    (f) the tier-mix, capability-set, verification-histogram, `review`-present, and
    ledger-parity assertions from AC 4/5/6/10;
    (g) **distractor-never-expected** — no distractor tool name
    (`archive_ticket`, `find_account`, `draft_email`) appears in any
    `ExpectedToolCall` (including those nested inside `AllOf`), **and** no
    `StateEquals`/`StateContains` asserts a distractor's signature value
    (`status:"archived"`, `emails.*.state:"draft"`) as a *passing* outcome; a
    distractor may appear only inside a `NoToolCall` (forbidding it) or as the
    wrong-path state a correct `FinalStateSpec` discriminates against — so a
    task-author slip can never bless a distractor path (see Resolved decision Q3);
    (h) **state-dependency proxy** (AC 7) — every `multi_step_depth`/`derived_argument`
    task references at least one entity id absent from both `initial_state` and the
    user-message text, computing the minted next-id from `initial_state` exactly as the
    world will (reusing the AC 12e precondition machinery). The module is pure (no
    network, no model), runs in CI, and is written test-first.

13. **Harness gates stay green and v1 is untouched.** `uv run pytest -q`,
    `uv run ruff check .`, `uv run ruff format --check .` are all clean. `v1.jsonl`,
    its loader test, and all 130+ existing tests are unchanged. The two additive
    `TaskMetadata` fields (`max_steps`, `review`) are optional/defaulted so no existing
    construction site or v1 row breaks. No live model run happens in this item (that is
    item 004).

## Non-goals

- **`LlmJudgeSpec` and any model-based grading** — item 003. No judge prompt, no κ, no
  rubric-as-judge-input here; `rubric.md` is the *author's task-validity* checklist, a
  distinct artifact from the judge rubric (CONTEXT.md flags this naming hazard).
- **Live evaluation / the failure-mode report / the 2-config comparison** — item 004.
  This item produces the *instrument* (tasks + world), not measurements. The
  expected-failure rationale is a design prediction to be tested in 004, not a result.
- **Runner / `multi_run.py` changes to consume per-task `max_steps`** — flagged as an
  item-004 downstream need (AC 8). This item ships the schema field and the data, not
  the runner wiring, unless the conformance test forces it.
- **New grader code, new `VerificationSpec` variants, new constraint variants** — item
  001 shipped the full deterministic tier; v2 *uses* it. If authoring reveals a true
  parser gap (e.g. an `AllOf` nesting depth the parser mishandles), fixing that gap is
  in scope (AC accept "only if a parse gap is found"), but no new spec/constraint type
  is designed here.
- **`ask_user` / `ScriptedUser` / multi-turn clarification and the ambiguity knob** —
  Weeks 9-10, explicitly OUT per MASTER-SPEC. v2 tasks are single-user-turn; ambiguity
  is *removed* (AC 9 rubric item a), not exploited.
- **Synthetic generation / parametrized world templates** — Weeks 13-14. v2 is
  hand-authored (provenance `hand_authored`); a generator is out of scope.
- **Held-out split / never-train manifest / leakage checks** — Weeks 9-10. Every v2
  task is `split: "dev"`; the isolation boundary work is deferred.
- **Cost/latency or metrics changes** — unaffected; v2 feeds the existing pipeline.

## Constraints

- **Purity / FP discipline.** Every new tool impl is a pure
  `(args, state) -> (state', outcome)`; state grows via spread
  (`{**state, "emails": {**emails, new_id: ...}}`), never mutation. Read-only tools
  return `state` unchanged. The conformance module is pure (no model, no I/O beyond
  reading the dataset file). Records stay frozen and serializable; `TaskMetadata`'s two
  new fields are immutable optionals.
- **World/grader agreement (design §5).** A tool that the grader can detect as a wrong
  path (e.g. `archive_ticket` leaving `status:"archived"`) must produce exactly that
  detectable state, so a `FinalStateSpec` distinguishes the right path from the
  plausible-wrong one. Schema-invalid args surface as `ToolFailure` in the world *and*
  as `schema_violation` in the grader — the world and grader never disagree on "valid".
- **Additive, non-breaking schema change.** `TaskMetadata` gains only optional
  defaulted fields (`max_steps`, `review`); `Task`, `TaskInput`, and every spec type
  are unchanged. v1 rows and the v1 loader test must pass byte-for-byte.
- **Determinism.** No clock, no RNG, no network, no filesystem in any tool or task.
  Dates are literal ISO strings; id minting is `max(...)+1`. Same `(seed, input)` ⇒
  same trajectory is a runner property already; v2 must not introduce a nondeterministic
  world primitive that would break it.
- **Single-capability isolation.** Each task isolates exactly one capability (rubric
  item b). A task that needs distractor-resistance *and* derived-reasoning to pass is
  split or relabeled to its dominant capability with the secondary noted in the ledger,
  so a failure attributes to one capability for the JD#4 taxonomy.
- **Minimal-but-sufficient `initial_state`.** `initial_state` carries exactly the
  accounts/tickets/docs/emails the task and its distractors require — enough to make the
  hard tiers hard, nothing decorative (rubric item e; enforced by AC 12e preconditions).
- **TDD.** The conformance module is written test-first (red) against an empty/partial
  dataset, then tasks are authored to green; the rubric checklist is applied per task as
  it is authored, with evidence recorded in the ledger.
- **No new runtime dependencies.** Tools use only the stdlib + the already-vendored
  `jsonschema`; the conformance module uses only stdlib + existing loaders.
- **Security.** No new I/O surface; dot-paths in specs are mapping keys only (already
  guaranteed by item 001's grader). Email bodies/subjects in `initial_state` are inert
  data, never executed.

## Open questions resolved during brainstorming (with rationale)

1. **Exact v2 tool lineup and which are distractors?** → **8 tools: the 3 v1 tools +
   `get_account`, `list_tickets`, `send_email` (§5 primaries) + 3 distractors
   `archive_ticket`, `find_account`, `draft_email`.** Considered (a) the literal §5
   list minus `ask_user` = 6 tools with no distractors, and (b) inventing many shallow
   distractors. (a) is rejected because the MASTER-SPEC binding directive *requires*
   distractor tools that "force discrimination"; six non-overlapping tools do not
   discriminate — a strong model trivially picks the only matching name. (b) is rejected
   as filler. The chosen three distractors each create a *specific, gradeable* wrong
   path: `archive_ticket` vs `update_ticket(status:closed)` (a third status the
   final-state grader catches), `find_account`(by-email, returns candidates) vs
   `get_account`(by-id, exact) (selection error when the id is known), `draft_email` vs
   `send_email` (silent under-action: the email never reaches `state:"sent"`, which a
   `StateEquals` on `emails.e-1.state` catches). This is the minimal lineup that makes
   `distractor_resistance` a real, scorable capability rather than a label.

2. **Tier mix given "majority hard"?** → **T1 5 / T2 12 / T3 22 / T4 11 (10/24/44/22%);
   T3+T4 = 66%.** The brief offered ~10/30/40/20 as a starting point. I shifted mass
   from T2 (30→24) into T3 (40→44) and kept T4 at ~22 because the binding directive says
   tasks every frontier model trivially passes are "filler" and "the majority of the set
   must be the hard tiers" — 66% in T3+T4 satisfies "majority" with margin while keeping
   a 5-task T1 floor (regression sanity: if even T1 starts failing, the harness or world
   regressed, not the model) and a 12-task T2 band (the gradient that makes the
   capability boundary *visible*, not a cliff). T4 at 11 is large enough to reliably
   surface ≥1 frontier failure (the directive's "expected to sometimes fail") without
   the set becoming uniformly adversarial and thus uninformative about the boundary's
   *location*.

3. **Final capability taxonomy (the six categories)?** → **`tool_selection`,
   `argument_extraction`, `multi_step_state`, `constraint_compliance`,
   `distractor_resistance`, `derived_reasoning`** — exactly the brief's candidate list,
   adopted whole. Each maps to one verification shape (AC 6) and one dominant difficulty
   knob, so a failure attributes cleanly. Rejected adding a separate `long_horizon`
   category: long-horizon is a *property* (chain depth) cutting across `multi_step_state`
   and `derived_reasoning`, captured by `difficulty_knob=multi_step_depth` + `max_steps`,
   not a distinct capability — making it a category would double-count the same skill.

4. **Verification mix per the brief's directive?** → **`tool_call_match` for T1–T2
   selection/extraction; `FinalStateSpec` (path-independent) for T3–T4 outcome;
   `AllOf(FinalStateSpec, TrajectorySpec)` wherever a policy clause is stated; no
   `LlmJudgeSpec`, no `OutputMatchSpec`.** Directly follows design §5/§6 (the two
   deterministic modes) and the MASTER-SPEC verification-mix directive. Hard multi-step
   tasks are graded path-independently so multiple valid tool orderings pass, *but*
   harmful side-effects (an unwanted `send_email`, touching the wrong ticket, exceeding a
   call budget) are forbidden via `TrajectorySpec` — exactly the "outcome AND policy"
   decision (design §14.6). `tool_call_match` is retained for the selection/extraction
   tiers because *there* the action chosen is precisely what we mean to grade.

5. **Where is `max_steps` carried — global, per-tier, or per-task?** → **Per-task,
   as an optional `TaskMetadata.max_steps`.** A global ceiling either starves the 8-step
   T4 chains or over-budgets the T1 single-call tasks (and a too-high global lets
   over-calling models wander, masking `extra_call` signal). Per-tier is a coarse proxy
   for what is really a per-task property (a 4-step and an 8-step task can share a tier).
   Per-task is the precise, additive, defaulted choice; it also lets a `MaxToolCalls`
   policy constraint and the run budget be authored coherently from one place. Wiring it
   through the runner is item 004's job (AC 8) — this item ships the field and the data.

6. **How is per-task review evidence recorded — metadata field, ledger, or both?** →
   **Both: a `metadata.review` field on each task *and* a `review-ledger.md`.** The
   field makes the dataset self-describing and lets the conformance test assert review
   coverage mechanically (no task ships unreviewed); the ledger makes the review
   *human-auditable* in one scannable place (tier, capability, knob, checklist result,
   expected-failure rationale per id). A field alone is not auditable; a ledger alone is
   not machine-checkable for coverage. Both, cross-checked for id-parity by the
   conformance test, is the rigorous choice and costs one optional field.

7. **Does v2 need new `VerificationSpec` or constraint variants?** → **No.** Item 001
   shipped the full deterministic tier (`FinalStateSpec`/`TrajectorySpec`/`AllOf` +
   `StateEquals`/`StateContains`/`NoToolCall`/`OnlyModifies`/`MaxToolCalls`). Every v2
   hard pattern — derived-min-by-date close, no-email policy, only-modify-one-ticket,
   at-most-N-calls, presence-of-sent-email — expresses in those variants. If authoring
   surfaces a genuine *parser* gap (e.g. deeply nested `AllOf`), fixing the parser is in
   scope; designing a new spec type is not (that would be a design-doc change, out of
   this item).

8. **`max_steps` derivation rule (how high)?** → **≥ (number of expected dependent
   calls) + 2.** The +2 is headroom for the model's optional read/confirm turns (a
   model may take an extra turn to inspect a `list_tickets` result before acting, and a
   final assistant-message turn to confirm). Too tight a budget would manufacture
   `step_limit`/`max_steps` stops that look like agent failures but are harness
   starvation — exactly the "agent vs harness failure" confound the dataset CI exists to
   prevent (AC 12). The conformance test enforces the floor so no task is mis-budgeted.

### Not resolvable from MASTER-SPEC alone

None that block authoring. One item is **deferred by design, not unresolved**: whether
`runners/multi_run.py` should consume per-task `max_steps` from metadata or keep taking
a single run-level `max_steps` argument. It is resolved *for this item* (ship the data
+ field; do not change the runner) and explicitly handed to item 004, which performs the
live v2 runs and will need to thread the per-task budget. Recording it here so item 004
inherits the decision rather than rediscovering it.

## Resolved decisions

Output of the `grill-with-docs` pass (subagent: opus) hardening this spec against the
domain model *before* the plan phase. Autonomy override in effect: each question is
auto-resolved to the reviewer's recommended answer. Corrections are applied as inline
strike-throughs above; nothing is deleted.

**Q1 — Does the hard-tier design *actually* discriminate, or can a task be "long yet
easy"?** A rote chain (e.g. eight independent `create_ticket` calls) is long but
trivially parallelizable and discriminates nothing. The spec's prose demanded
state-dependence but the original AC 12 did *not* check it.
- **A:** AC 7 now mandates a pure **anti–rote-chain proxy** and AC 12(h) enforces it:
  every `multi_step_depth`/`derived_argument` task must reference ≥1 entity id absent
  from both `initial_state` and the user-message text (a minted next-id or a
  `list_tickets`/`find_account`-surfaced id). Rubric item (g) adds the human gate.
- **Rationale:** A pure test cannot prove the *sufficient* semantic property (needs a
  live model — item 004), but it *can* enforce a *necessary* structural witness that
  every rote chain fails. This converts "designed to discriminate" from assertion to
  auditable property using machinery AC 12e already needs (deterministic next-id).
- **Doc impact:** spec AC 7 + AC 12(h); CONTEXT.md adds **State-dependent chain**,
  **Difficulty knob**, **Tier**.

**Q2 — `max_steps`: does deferring runner wiring to item 004 leave T3/T4 unrunnable for
002's verify gate?** Confirmed the runner's loop budget is a *global* `max_steps`,
defaulting to `6` (`cli.py --max-steps`; `runners/loop.py` `for _ in range(max_steps)`).
A dependent 8-call chain needs ≥8 iterations + a confirm turn ⇒ 9–10, far above 6.
- **A:** **Defer wiring to 004; scope item 002's verify gate to parse + schema +
  conformance (pure, no live model).** Item 002 ships the `metadata.max_steps` field +
  data + a conformance floor (`max_steps >= dependent_calls + 2`) that *proves the
  dataset is runnable once wired* without running it. Wiring per-task `max_steps`
  through `multi_run.py`/`cli.py` is a **blocking contract for item 004** (which owns
  the live v2 runs and needs it regardless).
- **Rationale:** AC 13 already forbids a live run in 002, so there is no live gate to
  fail; wiring now would ship untestable runner code (violating TDD). The danger — if
  004 forgets the contract, every T3/T4 task stops at `max_steps` and grades as a
  *step-limit* failure masquerading as an agent failure — is mitigated structurally by
  the conformance floor in 002 + the blocking note to 004.
- **Doc impact:** **ADR 0004** (per-task `max_steps` is data; wiring deferred); spec
  AC 8 rewritten; CONTEXT.md adds **max_steps (task hint)**.

**Q3 — Can a task-author slip bless a distractor path?** Original AC 12 checked tools
are registered and args valid, but *not* that a distractor is never the correct path.
- **A:** AC 12(g) now asserts **distractor-never-expected**: no distractor name
  (`archive_ticket`/`find_account`/`draft_email`) in any `ExpectedToolCall` (incl.
  nested in `AllOf`), and no `StateEquals`/`StateContains` asserting a distractor's
  signature value (`status:"archived"`, `emails.*.state:"draft"`) as a *passing*
  outcome. A distractor may appear only inside a `NoToolCall` or as the wrong-path
  state a correct `FinalStateSpec` discriminates against.
- **Rationale:** The distractor signature set is closed and enumerable, so the check is
  pure and total; it makes `distractor_resistance` a scorable capability that a typo
  cannot silently invert. No ADR (the obvious correct check, no real alternative).
- **Doc impact:** spec AC 12(g); CONTEXT.md adds **Distractor tool**.

**Q4 — Review evidence: metadata field, ledger, or both — against §9 append-only?**
- **A:** **Both**, with the **`metadata.review` field (riding the append-only row) as
  the source of truth** and the `review-ledger.md` as a regenerable human-audit view,
  never the gate.
- **Rationale:** §9 append-only governs the *rows*; the field is part of the row, so it
  is frozen-with-the-row and re-review under a new rubric is a *new version*, not an
  in-place edit. The ledger is a doc, not versioned data — its only obligation is
  id-parity (already asserted). A ledger edit can never un-gate a row.
- **Doc impact:** spec AC 10 hardened; CONTEXT.md adds **review (task)**.

**Q5 — Does `world_template_id` need adding for the Weeks 9-10 splits?** **No — it
already exists** on `TaskMetadata` and v1 populates it (`workspace-v1`); v2 sets
`workspace-v2`. Zero retrofit. §7 confirms it is the isolation boundary.
- **Doc impact:** CONTEXT.md adds **world_template_id** (records it as the §7 isolation
  boundary so future split work does not reinvent it). No spec change.

**Q6 — Task-id scheme / file name / `version` semantics.** Spec fixed the file name and
`version:"2"` but was silent on the *task-id scheme*.
- **A:** Task ids are **`ws2-001`…`ws2-050`** (distinct prefix from v1's `ws-NNN`);
  file `workspace_tool_use_v2.jsonl` (unchanged); `metadata.version` is the
  **dataset/world generation string**, co-varying with `world_template_id`, NOT a
  per-row revision number.
- **Rationale:** Reusing `ws-NNN` would collide v1 and v2 ids when their runs/traces
  coexist in one report or the §9 flywheel — task id is the join key. A distinct prefix
  is the cheap, sortable fix.
- **Doc impact:** spec AC 4 (id scheme added); CONTEXT.md adds **version (dataset)**.

**Q7 — `provenance`: spec said `"hand_authored"`, but v1 + every test use
`"hand_written"`.** A second spelling for "a human wrote it".
- **A:** v2 uses **`provenance:"hand_written"`** (match v1); `"hand_authored"` struck.
- **Rationale:** Provenance values are *counted* in the dataset card (§9 "provenance
  counts"); a synonym fractures the aggregate and forces every counter to know both
  spellings. One concept, one canonical term — glossary discipline.
- **Doc impact:** spec AC 4 (strike-through correction); CONTEXT.md adds **provenance**
  with `hand_authored`/`hand-authored`/`manual` listed under _Avoid_.

**Q8 — Does v2 need new `VerificationSpec`/constraint variants?** **No** (confirmed
against item 001's shipped union and the grader code). Unchanged from brainstorming;
the parser-gap escape hatch stands.
- **Doc impact:** none.
