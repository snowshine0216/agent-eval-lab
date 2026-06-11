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
   repair request.
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
8. **Oracle invariants.** Every `ExecutionSpec`: contains ≥ 1 pytest-collectible
   test file (basename `test_*.py`); oracle paths are **disjoint** from every
   initial-tree path (no exact-path or canonical-prefix overlap with the initial
   tree); test-module basenames are unique across visible + oracle files (pytest
   module-collision guard); `timeout_s` is `None` on every task (edge default 10 s).
9. **Review-fixtures sidecar.** `examples/datasets/code_repair_v1_review_fixtures.json`
   maps every task id to `{bug_class, solution: {path: content}, hack: {path:
   content} | null, distractor_paths: [path, ...]}`. It is conformance/review
   input only — never loaded by the harness, never rendered into any prompt.
10. **Symptom is real.** For every task with visible tests, `run_pytest` over the
    *initial* tree has suite status `failed`; for prose-only tasks it is `no_tests`.
11. **Solvability.** For every task, the reference tree (initial tree ⊕ solution
    files) passes the **oracle** through the production
    `precompute_execution_verdicts` + `grade_execution` path (status `passed`,
    never `timeout`) and passes the visible suite via `run_pytest`.
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
    ambiguity guard — no other path in initial ∪ oracle ∪ solution trees whose
    dotted form (`files.<path>`) extends an allowlisted path's dotted form, so the
    leaf-diff prefix match in `graders/policy.py` cannot false-allow (e.g.
    `app.py` vs `app.py.bak`).
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
    or `datetime` (mechanical import-statement scan); `pytest` is imported only in
    test files. Determinism and no-network are properties of the dataset by
    construction, not just rubric promises.
20. **Oracle leakage.** No non-trivial line of any oracle test file appears in any
    prompt message of its task (the item-002 security constraint, re-asserted at
    the dataset level).
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
   as a semantic claim; duplicated content drifts).
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
    over every tree the task can reach — the dataset stays inside the grader's
    sound region.
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
