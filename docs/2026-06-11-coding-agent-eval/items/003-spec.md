# Item 003 — code_repair_v1: 10-20 reviewed code-repair tasks

Run: `coding-agent-eval` (Weeks 5-6) · Source row: MASTER-SPEC item 003 · Date: 2026-06-11
Brainstormed autonomously (no user in loop); every question auto-resolved with the
recommended answer, recorded in §Open questions below. Builds directly on items 001
(code-world + hermetic execution edge, merged #10) and 002 (`ExecutionSpec` +
oracle-overlay grading, merged #11): `tools/code_world.py`, `runners/pytest_edge.py`,
`runners/oracle_edge.py`, `graders/execution.py`, ADR-0008/0009/0010/0011. Follows the
Weeks 3-4 v2 dataset quality bar (taxonomy, authoring rubric, per-task review ledger,
anti-rote conformance suite in CI).

## Goal

Deliver `code_repair_v1`: **15 hand-authored, reviewed code-repair tasks**
(`examples/datasets/code_repair_v1.jsonl`) over the code-world — each task's
`initial_state` is a small broken Python program (stdlib-only file tree, visible
pytest tests for most tasks), the agent repairs it with the four code-world tools
(`read_file` / `write_file` / `list_files` / `run_tests`), and verification is an
`ExecutionSpec` carrying **held-out oracle tests** (composed via `AllOf` with
policy `TrajectorySpec` legs on at least three tasks) — plus the v2-bar quality
apparatus: a code-repair capability taxonomy (6 capabilities × 4 tiers ×
closed difficulty-knob and bug-class vocabularies, in `taxonomy.md`), an authoring
rubric (`rubric.md`, stamped `passed:cr-rubric-v1` per row), a per-task review
ledger, tier/attribute sidecars, and an **anti-rote conformance suite in CI**
(`tests/datasets/test_code_repair_v1.py`) that proves mechanically, through the
*production* oracle edge on real sandboxed pytest runs: a no-op agent grades 0/15;
an agent that stubs out the visible tests cannot pass an unrepaired task (the
oracle independently detects every planted bug); a hardcode-the-visible-expectations
agent passes the visible suite but fails the oracle on every tier that claims
overfit resistance; and every task is solvable — the reference repair passes both
suites inside the default sandbox timeout. No runner or `src/` changes: this item
is dataset + conformance + docs; live baseline runs and the world-selection CLI
wiring are item 004's.

## Acceptance criteria

Each criterion is independently verifiable by a named conformance test or inspection.

1. **Dataset file and shape.** `examples/datasets/code_repair_v1.jsonl` holds exactly
   15 rows with ids `cr-001` … `cr-015` (regex `^cr-\d{3}$`, unique, count in the
   roadmap's 10-20 band). Every row parses via the production `tasks/loader.load_tasks`
   into a `Task` whose verification tree contains at least one reachable
   `ExecutionSpec` (alone, or inside `AllOf`). Each task's `input.messages` is a
   shared code-repair system turn plus one user turn carrying the bug report /
   repair request (exactly two message turns; the system turn is byte-identical
   across all 15 rows — Resolved decisions Q13).
2. **Metadata contract.** Every row: `split="dev"`, `version="1"`,
   `provenance="hand_written"`, `review="passed:cr-rubric-v1"`,
   `world_template_id` matching `^code-v1-[a-z0-9-]+$` and **unique per task** (one
   program family per task — the Weeks 9-10 split-isolation boundary), and
   `metadata.max_steps` present.
3. **Tier sidecar.** `examples/datasets/code_repair_v1_tiers.json` maps every task id
   to its tier with the declared allocation **T1=2, T2=4, T3=6, T4=3** (60% T3+T4) —
   same `{id: tier}` shape as `workspace_tool_use_v2_tiers.json` so the existing
   `report-validation` / `compare-configs` tooling reads it unchanged.
4. **Capability taxonomy.** Closed 6-value vocabulary; every task declares exactly
   one capability; every capability covers ≥ 2 tasks:
   `visible_test_localization` (failing visible test names the symptom),
   `prose_localization` (no failing visible test; the bug is described in prose),
   `test_comprehension` (the contract is specified only by the visible tests),
   `cross_file_repair` (fault in a different file than the symptom),
   `regression_preservation` (the tempting fix breaks behavior the oracle's
   regression tests protect), `overfit_resistance` (visible tests underdetermine
   the fix; the oracle is strictly broader). Documented in the run dir's
   `taxonomy.md` with the tier × expected-failure rationale table.
5. **Difficulty knobs (code dialect).** Closed 6-value vocabulary —
   `fault_distance`, `multi_hunk`, `oracle_breadth`, `spec_obliqueness`,
   `constraint_budget`, `distractor_file` — every T3/T4 task declares exactly one
   `metadata.difficulty_knob`; any declared knob is in the vocabulary.
6. **Bug-class tags.** Closed 6-value vocabulary — `off_by_one`, `logic_inversion`,
   `exception_handling`, `type_coercion`, `boundary_condition`,
   `aliasing_mutation` — recorded per task in the review-fixtures sidecar
   (criterion 9) and the ledger; every task tagged exactly one primary class; every
   class represented ≥ 1×. (Tags ride sidecar + ledger; `TaskMetadata` is unchanged.)
7. **World validity.** Every task: `available_tools` is exactly the four code-world
   tools; `initial_state` is a valid code-world tree — every path passes
   `code_world.path_error`, no harness-reserved names, no `conftest.py` at any
   depth, no canonical-prefix collisions (via the public `prefix_collision`).
   Sharpened (Resolved decisions Q14, Q2): harness-reserved *basenames*
   (`.harness.ini`, `.junit.xml`, `sitecustomize.py`, `usercustomize.py`,
   `conftest.py`) are banned at **any depth**, and basenames matching `*_test.py`
   are banned everywhere (so the `test_*.py` convention equals pytest collection);
   the same world-validity checks run over every fixture tree this item ships
   (initial, oracle, solution, hack).
8. **Oracle invariants.** Every `ExecutionSpec`: contains ≥ 1 pytest-collectible
   test file (basename `test_*.py`); oracle paths are **disjoint** from every
   initial-tree path (no exact-path or canonical-prefix overlap with the initial
   tree — the dataset-lineage policy, ADR-0012); test-module basenames are unique
   across visible + oracle files (pytest
   module-collision guard); `timeout_s` is `None` on every task (edge default 10 s).
9. **Review-fixtures sidecar.** `examples/datasets/code_repair_v1_review_fixtures.json`
   maps every task id to `{bug_class, solution: {path: content}, hack: {path:
   content} | null, distractor_paths: [path, ...]}`. It is conformance/review
   input only — never loaded by the harness, never rendered into any prompt.
10. **Symptom is real.** For every task with visible tests, `run_pytest` over the
    *initial* tree has suite status `failed`; for prose-only tasks it is `no_tests`.
    Definitions pinned (Resolved decisions Q1, Q2): a *visible test file* is any
    initial-tree file whose basename matches `test_*.py`; a *prose-only* task has
    zero visible test files. The third symptom shape — a green visible suite plus
    a prose bug report — is deliberately unrepresentable in v1 (it would break
    this binary mechanical check; a future version may add it as its own
    capability variant).
11. **Solvability.** For every task, the reference tree (initial tree ⊕ solution
    files) passes the **oracle** through the production
    `precompute_execution_verdicts` + `grade_execution` path (status `passed`,
    never `timeout`) ~~and passes the visible suite via `run_pytest`~~ and the
    visible-suite run (`run_pytest` over the reference tree alone) reports
    `passed` for tasks with visible tests and `no_tests` for prose-only tasks.
    *(Struck: prose-only tasks have no visible suite to pass — the original
    wording was unsatisfiable for them. Resolved decisions Q3.)*
12. **No-op agent grades 0/15.** A synthetic no-op trajectory
    (`final_state = initial_state`, zero tool calls) graded through the production
    oracle edge + `grade_trajectory` fails every task — no verification is
    pre-satisfied (the v2 P0 check, executed on real sandboxed pytest).
13. **Test-stubbing agent neutralized.** For every task with visible tests: the tree
    with every visible test file overwritten by a trivially-passing stub
    (`def test_stub(): pass`) and the program *unrepaired* still fails the oracle —
    proving the oracle files independently detect each planted bug (the code-world
    analog of "deleting failing tests cannot pass"; code-world has no delete, so
    overwrite-with-stub is the realizable attack, and ADR-0010's oracle-wins overlay
    plus path disjointness close the rest).
14. **Hardcode agent caught.** Every `overfit_resistance` task and every T4 task
    with visible tests carries a `hack` fixture — the minimal patch that satisfies
    the visible tests by special-casing their inputs. Conformance asserts the hacked
    tree **passes the visible suite** (`run_pytest`, status `passed`) and **fails
    the oracle** — oracle breadth is proven, not claimed.
15. **Anti-rote transcription proxy.** No non-trivial changed line of the reference
    solution (diff vs the initial tree; stripped lines > 3 chars) appears verbatim
    in any prompt message — the prompt may describe the bug, never dictate the
    patch (the code-world analog of v2's state-dependency proxy).
16. **Policy composition.** ≥ 3 tasks verify via `AllOf(ExecutionSpec,
    TrajectorySpec)` covering ≥ 2 distinct trajectory-constraint types (e.g. a
    `MaxToolCalls` efficiency budget; `NoToolCall("run_tests")` repair-from-reading;
    `OnlyModifies` scoped edits). Coherence checks: every `MaxToolCalls.n` ≤ the
    task's `max_steps`; every `OnlyModifies` allowlist passes the dotted-path
    ambiguity guard — no other path in ~~initial ∪ oracle ∪ solution trees~~
    initial ∪ oracle ∪ solution ∪ hack trees whose
    dotted form (`files.<path>`) extends an allowlisted path's dotted form, so the
    leaf-diff prefix match in `graders/policy.py` cannot false-allow (e.g.
    `app.py` vs `app.py.bak`). *(Struck: the hack fixture is also a tree this
    item ships and materializes; it joins the guarded union. Resolved decisions
    Q8.)* Known residual (Resolved decisions Q8): the guard covers only
    fixture-shipped trees — an agent can mint a fresh extension path at run time
    (e.g. write `app.py.bak` itself) and be silently covered by an `app.py`
    allowlist entry; that is a `graders/policy.py` property out of this item's
    scope, recorded here so item 004's classifier attributes it to the harness,
    not the task.
17. **Distractor files.** Every `distractor_file` task names its distractor path(s)
    in the sidecar; the distractor exists in the initial tree, the reference
    solution leaves it byte-identical, and the oracle suite references the
    distractor module (modifying the red herring is a *gradeable* wrong path —
    an oracle regression test breaks — mirroring v2's "distractor never expected").
18. **max_steps floors.** Every task `max_steps` ≥ 6 (read → run → write → run →
    confirm + headroom); every T3/T4 task ≥ 8; every task ≤ 16.
19. **Hermeticity banlist.** No file in any initial tree, oracle, solution, or hack
    fixture imports `socket`, `http`, `urllib`, `requests`, `subprocess`,
    `multiprocessing`, `threading`, `asyncio`, `random`, `secrets`, `uuid`, `time`,
    ~~or `datetime`~~ `datetime`, `os`, or `tempfile` (mechanical import-statement
    scan); `pytest` is imported only in
    test files. *(Struck/extended: `os` carries `os.urandom`/`os.environ`/
    `os.system` — randomness, env, and subprocess surfaces in one import — and
    `tempfile` is RNG-named filesystem I/O; stdlib micro-programs need neither.
    Resolved decisions Q9.)* Determinism and no-network are properties of the dataset by
    construction, not just rubric promises.
20. **Oracle leakage.** No non-trivial line of any oracle test file appears in any
    prompt message of its task (the item-002 security constraint, re-asserted at
    the dataset level). *Non-trivial* uses the criterion-15 threshold: stripped
    lines > 3 chars (one definition for both leakage proxies — Resolved
    decisions Q12).
21. **Authoring rubric + review ledger.** `docs/2026-06-11-coding-agent-eval/rubric.md`
    (version `cr-rubric-v1`) adapts the Weeks 3-4 checklist to code repair —
    unambiguous single defensible fix; single capability; verification matches
    intent; deterministic (no clock/RNG/network/env); no conftest dependence
    (oracle self-contained per `pytest_edge` hermeticity); solvable within
    `max_steps` and the 10 s sandbox timeout; no import-time-exploit surface in
    graded modules (ADR-0010 residual trust boundary screened per task).
    `docs/2026-06-11-coding-agent-eval/review-ledger.md` carries one entry per task
    id (rubric verdict per checklist letter, bug class, tier, knob, evidence);
    conformance asserts ledger ↔ dataset id parity and the `review` stamp on every
    row.
22. **Conformance suite in CI.** All of the above checks live in
    `tests/datasets/test_code_repair_v1.py`, run under the default pytest gate
    (no new CI lane, no model calls; subprocess only through `run_pytest`), and the
    suite completes within the CI wall-time budget (≤ ~120 s for the ~70 sandboxed
    runs; oracle suites are authored to finish in single-digit seconds each).
23. **Determinism spot-check.** One task's `(spec, reference tree)` graded twice
    end-to-end yields byte-identical serialized `GradeResult`s (the item-002
    reproducibility property re-proven over real dataset content).
24. **TDD evidence.** Conformance tests land red-green against the dataset (a check
    is written, shown failing on a deliberately defective draft row or fixture,
    then the dataset is corrected); no `src/agent_eval_lab` production change is
    needed or made.

## Non-goals

- **Live baseline runs, failure classification, the report command** — item 004.
- **Runner/CLI world-selection wiring.** `cli.run_baseline` hardwires
  `registry=WORKSPACE_TOOLS`, and `run_task_k` does not thread
  `apply_fn`/`executor` into `run_single` (both already parameterized there).
  Item 004 owns that plumbing — it cannot run live baselines without it. This
  item's conformance grades through synthetic trajectories + the oracle edge, which
  needs none of it.
- **Task generation, dataset cards, contamination checks** — Weeks 13-14
  (`provenance="generated"` arrives there; this set is `hand_written`).
- **Splits and the never-train manifest** — Weeks 9-10; all 15 rows are `dev`, and
  per-task `world_template_id`s keep future partitioning free.
- **Schema changes.** No `tier`/`bug_class` fields on `TaskMetadata`; sidecars and
  the ledger carry them (the v2 precedent).
- **`LlmJudgeSpec` legs on code tasks** — execution + policy grading only;
  summary-fidelity judging of code repairs is unscoped.
- **A `delete_file` tool, multi-language programs, third-party dependencies,
  per-test process isolation, kernel-level network isolation** — all inherited
  001/002 non-goals; the rubric and banlist mitigate inside the accepted
  trust boundary.
- **Frontier-separating hardness.** The Weeks 3-4 takeaway scopes frontier
  separation to later levers (multi-turn, generated scale); this set's job is a
  sound, classification-ready execution-grading slice, hence the small sanity band.

## Constraints

- **Append-only dataset.** Once merged, rows of `code_repair_v1.jsonl` are frozen
  (the v1/v2 version convention); fixes ship as a new dataset version, never an
  edit. Review stamps (`passed:cr-rubric-v1`) are frozen with their rows.
  Sidecars freeze with the dataset version too (`code_repair_v1_tiers.json`,
  `code_repair_v1_review_fixtures.json` — they are keyed by frozen row ids), and
  the review-fixtures sidecar joins the Weeks 9-10 never-train manifest: it
  carries solutions (Resolved decisions Q10).
- **Zero production-code changes.** The item touches `examples/datasets/`,
  `tests/datasets/`, and `docs/2026-06-11-coding-agent-eval/` only; every
  conformance check uses already-public APIs (`load_tasks`, `path_error`,
  `prefix_collision`, `run_pytest`, `precompute_execution_verdicts`,
  `grade_trajectory`, serializers). A discovered API gap is a finding for the run
  log, not an inline patch.
- **Hermetic sandbox inherited.** `--noconftest`, `-c .harness.ini`, scrubbed env,
  no network, 10 s default timeout — tasks must be authored inside these
  semantics (oracle self-contained; no conftest fixtures anywhere).
- **Reproducibility (hard).** Same task + same final tree ⇒ byte-identical verdict
  (criterion 23); nothing in any program or test may read clocks, RNG, env, or the
  network (criterion 19 enforces mechanically).
- **Security.** Oracle test content never reaches agent-visible data (criterion 20);
  harness-reserved paths never appear in any tree; the review rubric screens each
  task's import-time code surface (ADR-0010 residual).
- **Performance.** The conformance suite's sandboxed runs (~15 no-op + ~12 stub +
  ~2×8 hack + ~2×15 solvability ≈ 70 `run_pytest` invocations) stay under ~120 s
  total; per-program oracle suites are authored to run in ≪ 10 s.
- **Style.** Conformance module mirrors `test_workspace_tool_use_v2.py` (pure
  helpers, spec-tree walkers, one assertion concern per test); ruff-clean
  (`E,F,I,UP`); functional patterns per CLAUDE.md.

## Open questions resolved during brainstorming

Autonomous mode: each question was answered with the recommended option; rationale
recorded here in lieu of user confirmation.

1. **How many tasks, and what tier mix?** → 15 tasks: T1=2, T2=4, T3=6, T4=3.
   Mid-band of the roadmap's 10-20; 60% T3/T4 follows the v2 hard-majority
   directive while keeping a small T1 sanity band — this is the *first* dataset on
   a new world, and item 004's failure classifier needs known-easy tasks to
   separate harness defects from agent limits. 20 tasks was rejected (CI sandbox
   cost and authoring/review time grow linearly; 15 already gives ≥ 2 tasks per
   capability); 10 was rejected (one capability would drop to a single task —
   no within-capability signal).
2. **What capabilities does CODE-REPAIR isolate?** → The closed 6-set of criterion 4,
   mirroring v2's 6-capability shape. Bug localization splits by *evidence source*
   (visible failing test vs prose vs tests-as-spec) because that is what changes
   the skill exercised; fix *shape* (single-line vs multi-hunk vs cross-file) is a
   difficulty mechanism, not a skill, so it lives in the knob vocabulary —
   preserving v2's capability/knob/tier orthogonality.
3. **How do the v2 difficulty knobs translate?** → A code dialect, closed 6-set:
   `fault_distance` (symptom→fault separation), `multi_hunk`, `oracle_breadth`
   (visible underdetermination), `spec_obliqueness` (prose-only / tests-as-spec),
   `constraint_budget` (policy leg), `distractor_file`. The v2 names
   (`derived_argument`, `distractor_count`, …) describe workspace mechanics and do
   not transfer; reusing them with mutated meanings would fracture the glossary.
4. **Where do tier and bug-class tags live?** → Tier in a sidecar with the exact v2
   `{id: tier}` shape (the report CLI consumes it unchanged); bug class +
   solution/hack/distractor fixtures in one review-fixtures sidecar; `TaskMetadata`
   untouched. Adding schema fields was rejected: optional-field churn on a frozen
   record for data only the conformance suite and ledger read.
5. **Visible vs held-out tests — superset or disjoint?** → Disjoint *paths*, with
   semantic breadth proven mechanically instead of asserted: the oracle run
   collects the combined tree (so visible tests still count at grading time), the
   stub check (criterion 13) proves every oracle independently detects its planted
   bug, and the hack fixtures (criterion 14) prove strict breadth exactly where
   the taxonomy claims it. Literal-superset duplication was rejected (untestable
   as a semantic claim; duplicated content drifts). *Grill upgrade: this policy
   constrains every future code-repair generation and is now ADR-0012.*
6. **What is the "deletes failing tests" anti-rote check here?** → Code-world has no
   delete tool, so the realizable attack is overwriting visible tests with trivial
   stubs; criterion 13 neutralizes it. The oracle-wins overlay (ADR-0010) plus
   oracle-path disjointness (criterion 8) close the overwrite-the-oracle and
   shadow-the-oracle variants — the conformance suite proves the guarantee per
   task rather than trusting it.
7. **Must the no-op check run real pytest?** → Yes. v2's no-op check graded pure
   specs cheaply; here pass/fail *is* a sandbox run, and a stubbed oracle edge
   would prove nothing about the shipping pipeline. CI cost is bounded by
   criterion 22's budget. Marking these tests slow-but-skipped was rejected — the
   MASTER-SPEC says conformance **in CI**.
8. **Hardcode check on which tasks?** → Required for every `overfit_resistance`
   task and every T4 task with visible tests ("at least the tiers claiming it");
   permitted anywhere. Requiring a hack fixture for all 15 was rejected: authoring
   a *convincing* minimal hack for tasks whose visible suite already pins the fix
   is busywork that proves nothing the solvability + stub checks don't.
9. **`world_template_id` granularity?** → One program family per task,
   `code-v1-<program-slug>`, unique across the 15. The template is the Weeks 9-10
   isolation boundary; a single shared id would force the whole dataset into one
   split partition. Hand-authoring 15 distinct micro-programs is the cost, and it
   also kills cross-task solution leakage.
10. **Hand-authored or generated?** → Hand-authored (`provenance="hand_written"`,
    the v1/v2 canonical value). Weeks 13-14 owns generation; a one-off generator
    here would be unreviewed scope with its own quality bar.
11. **Verification shapes?** → `ExecutionSpec` alone for most tasks; ≥ 3 `AllOf`
    compositions with `TrajectorySpec` legs (criterion 16) because the MASTER-SPEC
    names the composition and item 004's classifier needs at least one live
    policy-breach path. `FinalStateSpec` legs over file contents were rejected —
    byte-equality on repaired files would forbid valid alternative fixes; the
    oracle is the outcome authority.
12. **Does `OnlyModifies` even work over file-tree state?** → Yes with care: leaf
    paths become `files.<path>`, and `graders/policy.py` splits on dots, so a file
    named `app.py.bak` would be silently covered by an allowlist entry for
    `app.py`. Rather than touching the grader (out of scope, workspace-frozen),
    the conformance suite enforces the dotted-path ambiguity guard (criterion 16)
    ~~over every tree the task can reach~~ over every fixture-shipped tree
    (initial ∪ oracle ∪ solution ∪ hack) — the dataset stays inside the grader's
    sound region for all authored content. *(Struck: "every tree the task can
    reach" overclaimed — the agent can mint fresh extension paths at run time
    that no static check can enumerate; that residual is the grader's, recorded
    in criterion 16. Resolved decisions Q8.)*
13. **Per-task `timeout_s`?** → `None` everywhere (edge default 10 s). The
    micro-programs run in milliseconds; a tighter per-task value buys nothing and
    creates 15 chances to author a flaky timeout. The knob exists (item 002) for
    the day a task needs it.
14. **`max_steps` budgets?** → Floor 6 for all (read → run → write → run → confirm
    + headroom), ≥ 8 for T3/T4, cap 16 to bound live-run cost. Per-task
    `max_steps` is wired through `run_task_k` (`effective_max_steps`, ADR-0004
    closed), so budgets are honored today — unlike v2, which shipped the contract
    before the wiring.
15. **Import banlist vs rubric-only hermeticity?** → Both. The rubric promises
    no-network/deterministic; criterion 19's mechanical scan makes the promise a
    CI property (`pytest_edge`'s docstring explicitly delegates the network ban to
    "the item-003 rubric"). `conftest.py` is banned outright even though
    `--noconftest` makes it inert — a file that silently does nothing in the
    sandbox but something under plain pytest is an authoring trap.
16. **An agent that fixes the bug AND stubs the visible tests passes — acceptable?**
    → Yes for v1: the outcome (repaired program, oracle-verified) is genuinely
    achieved; weakening visible tests en route is a policy concern, policed only
    on tasks that carry an `OnlyModifies` leg. A blanket
    tests-must-not-change policy on all 15 tasks was rejected — it would forbid
    legitimate test-driven workflows (adding a reproduction test) and overload
    this item with item 004's failure-taxonomy decisions.
17. **Where do the quality-bar docs live?** → The run dir
    (`docs/2026-06-11-coding-agent-eval/{taxonomy,rubric,review-ledger}.md`),
    mirroring Weeks 3-4's run-dir placement exactly; the sidecars live beside the
    dataset in `examples/datasets/`. A `docs/datasets/` restructure was rejected as
    gratuitous divergence from the established layout.
18. **Discovered boundary: who wires code-world into live runs?** → Item 004.
    Exploration found `run_task_k` does not pass `apply_fn`/`executor` to
    `run_single`, and the CLI hardwires `WORKSPACE_TOOLS`; recorded here so 004's
    spec inherits it as a known, named gap instead of rediscovering it mid-run.

## Resolved decisions

Grill session 2026-06-11 (autonomous; every question auto-resolved with the
recommended answer). Q-numbers are referenced from the criteria above.

1. **Q: Criterion 10 admits only `failed` | `no_tests` — a green visible suite
   plus a prose bug report is unrepresentable. Gap or deliberate?**
   A: Deliberate for v1. *Prose-only* = zero visible test files; the
   green-suite-plus-prose-bug shape is deferred to a future version.
   Rationale: a third symptom state breaks the binary mechanical check; 15
   tasks cannot also carry a new capability variant. Doc impact: criterion 10
   sharpened; CONTEXT.md term **visible tests**.
2. **Q: What exactly is a "visible test file", given pytest's default
   `python_files` collects both `test_*.py` and `*_test.py`?**
   A: Basename matching `test_*.py` only; `*_test.py` basenames are banned in
   every fixture tree. Rationale: the conformance suite's notion of "visible
   test" must equal what the sandbox actually collects, or a `foo_test.py`
   silently escapes the stub/symptom checks. Doc impact: criteria 7/10;
   CONTEXT.md term **visible tests**.
3. **Q: Criterion 11 required every reference tree to "pass the visible suite"
   — what does a prose-only task pass?**
   A: `passed` where visible tests exist; `no_tests` for prose-only tasks.
   Rationale: the original wording was unsatisfiable for prose-only tasks.
   Doc impact: criterion 11 struck + corrected.
4. **Q: Is the visible/oracle disjointness policy ADR-worthy?**
   A: Yes — ADR-0012 (disjoint paths; breadth proven mechanically via stub +
   hack checks; literal superset rejected). Rationale: three-of-three — frozen
   append-only rows make it hard to reverse, oracle ⊇ visible is the surprising
   default expectation, and the trade-off was real; it constrains item 004's
   classifier and the Weeks 13-14 generator. Doc impact: ADR-0012; criterion 8
   cross-ref; CONTEXT.md **oracle tests** updated.
5. **Q: CONTEXT.md defined the difficulty knob as "a closed vocabulary" listing
   only the five workspace knobs — the code dialect contradicts the glossary.**
   A: Knob vocabularies are per-world *dialects*; names are never reused across
   dialects with mutated meanings. Rationale: the spec's Q3 already chose a code
   dialect; the glossary had to say so or every future reader trips on it.
   Doc impact: CONTEXT.md term **Difficulty knob**.
6. **Q: CONTEXT.md's `world_template_id` reads as one-template-per-dataset
   (`workspace-v1`/`-v2`); 15 per-task templates breaks that reading.**
   A: Granularity is a per-dataset declaration; code_repair_v1 declares one
   template (program family) per task. Rationale: the template is the split
   isolation boundary — one shared id would force the dataset into a single
   partition. Doc impact: CONTEXT.md term **world_template_id**.
7. **Q: Is `version="1"` a regression while workspace sits at `"2"`?**
   A: No — the version counter is scoped to its dataset lineage;
   `workspace_tool_use` and `code_repair` count independently.
   Doc impact: CONTEXT.md term **version (dataset)**.
8. **Q: The dotted-path ambiguity guard claimed coverage of "every tree the
   task can reach" — can it?**
   A: No. The guard covers fixture-shipped trees only (and now includes hack
   trees in the union); an agent minting a fresh extension path at run time
   (writing `app.py.bak` itself) is silently covered by an `app.py` allowlist
   entry — a `graders/policy.py` residual, named in criterion 16 so item 004
   classifies it as harness, not task. Rationale: a static dataset check cannot
   enumerate agent-created paths; overclaiming soundness would corrupt the
   failure taxonomy downstream. Doc impact: criterion 16 + Open-questions 12
   struck/corrected.
9. **Q: The hermeticity banlist omits `os` (`os.urandom`/`os.environ`/
   `os.system`) and `tempfile` (RNG-named I/O) — floor too low?**
   A: Add both; the list stays closed at 15 modules. Rationale: they are the
   two remaining one-import nondeterminism/subprocess surfaces, and stdlib
   micro-programs need neither. Doc impact: criterion 19 extended.
10. **Q: Does append-only freezing cover the sidecars, and do solutions in the
    review-fixtures sidecar threaten the eventual finetune data boundary?**
    A: Sidecars freeze with the dataset version, and the review-fixtures
    sidecar joins the Weeks 9-10 never-train manifest. Rationale: sidecars are
    keyed by frozen row ids; the fixtures file carries solutions, which must
    never leak into training data in the 16-week eval→data→finetune program.
    Doc impact: Constraints extended; CONTEXT.md term **sidecar (dataset)**.
11. **Q: Do the code-repair fixture concepts get canonical names, or stay
    spec-local prose?**
    A: Canonical glossary terms: **visible tests**, **distractor file**,
    **bug class**, **hack fixture**, **reference solution**, **sidecar
    (dataset)**. Rationale: item 004's report and the Weeks 13-14 generator
    will all need these words; naming them once prevents v2's
    "rubric"-style overload. Doc impact: CONTEXT.md, six terms added.
12. **Q: Criterion 20's "non-trivial line" had no definition — same as
    criterion 15's or different?**
    A: Same: stripped lines > 3 chars. Rationale: two leakage proxies, one
    threshold; divergent definitions invite a check that passes one and fails
    the other on identical content. Doc impact: criterion 20 sharpened.
13. **Q: "Shared system turn" — how shared, and how many turns?**
    A: Exactly two message turns per task; the system turn is byte-identical
    across all 15 rows. Rationale: mechanically checkable, mirrors the v2
    convention, and keeps prompt-config comparisons (item 004) clean.
    Doc impact: criterion 1 sharpened.
14. **Q: code_world's `_HARNESS_RESERVED` rejects reserved names at the root
    only — is a nested `pkg/sitecustomize.py` acceptable in fixtures?**
    A: No — the dataset bans reserved basenames at any depth, in all four
    fixture-tree kinds. Rationale: nested copies are inert today by mechanism
    (site imports root-level only, `-c .harness.ini` pins config), but a file
    that does nothing in the sandbox and something under plain pytest is the
    same authoring trap the spec already bans for `conftest.py`.
    Doc impact: criterion 7 sharpened.
15. **Q: Does the tier-sidecar shape claim hold against the report tooling?**
    A: Yes — verified: `cli.py` loads the sidecar via `json.loads` as a flat
    `{task_id: tier}` mapping and `reports/validation.py` + `comparison.py`
    consume it through `tier_of`; criterion 3's "reads it unchanged" stands.
    Doc impact: none.
16. **Q: A no-op trajectory trivially *passes* every policy leg
    (`MaxToolCalls`, `NoToolCall`, `OnlyModifies` see zero calls/changes) — does
    criterion 12's "fails every task" still hold on `AllOf` tasks?**
    A: Yes — `AllOf` ANDs all legs and evaluates every one (ADR-0003); the
    `ExecutionSpec` leg fails because the planted bug is present, so the
    composite fails. The conformance test asserts the composite verdict, not
    per-leg failure. Rationale: verified against `grade_trajectory`/
    `grade_all_of` semantics. Doc impact: none.
