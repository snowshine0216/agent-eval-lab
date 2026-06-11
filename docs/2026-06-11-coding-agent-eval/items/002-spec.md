# Item 002 — Execution-based graders: tests as the oracle

Run: `coding-agent-eval` (Weeks 5-6) · Source row: MASTER-SPEC item 002 · Date: 2026-06-11
Brainstormed autonomously (no user in loop); every question auto-resolved with the
recommended answer, recorded in §Open questions below. Builds directly on item 001
(merged): `records/execution.py`, `runners/pytest_edge.py`, `tools/code_world.py`,
ADR-0008/0009.

## Goal

Deliver the Tier-2 grading leg the MASTER-SPEC names: a new `ExecutionSpec`
`VerificationSpec` variant carrying the task's **held-out oracle tests** (a file-tree
fragment the agent never sees) plus an optional per-task `timeout_s`, and a pure
`grade_execution` grader that — following the ADR-0005 rule ADR-0008 explicitly named
as this item's contract — never executes anything itself: a new **grading edge**
(`runners/execution_edge.py`) overlays the oracle tests onto the trajectory's
`final_state` file tree (oracle wins on exact-path collisions; a canonical-prefix
collision is a structured error, never a crash), runs item 001's hermetic
`run_pytest`, and threads the resulting `ExecutionVerdict` into the **existing**
`verdicts` map keyed by a pure content hash `execution_hash(spec, final_tree)`; the
pure grader reads the verdict and maps suite `status == "passed"` to a passing
`GradeResult` with self-describing evidence. All execution non-passes are outcome
misses or infra records — `failure_reason=None`, the closed `FailureCategory`
taxonomy is untouched — with a mechanical evidence discriminator item 004's
task/agent/harness classifier reads. Golden conformance cases drive the full
edge-plus-grader pipeline on real sandboxed pytest runs, deterministic by ADR-0009.

## Acceptance criteria

Each criterion is independently verifiable by a named test or inspection.

1. **Schema variant.** `tasks/schema.py` gains a frozen `ExecutionSpec` with exactly:
   `type: Literal["execution"] = "execution"`, `held_out_tests: Mapping[str, str]`
   (POSIX-relative path → text content), and `timeout_s: float | None = None`
   (`None` ⇒ the edge's `DEFAULT_TIMEOUT_S`). It is added to the `VerificationSpec`
   union, and the union's "ExecutionSpec extends this later" comment is retired.
   No `expected_status` field exists: pass means suite `status == "passed"`, period.
2. **Parse with structural validation.** `tasks/parse.verification_from_dict` gains an
   `"execution"` branch. It rejects with a descriptive `ValueError`: empty
   `held_out_tests`; any oracle path failing code-world's canonical POSIX-relative
   form (reuse the `path_error` rules — no `..`/`.`/empty segments, no leading `/`,
   no backslash/NUL); the reserved `.junit.xml` key; any *oracle-internal*
   canonical-prefix collision (the 001 injective invariant); and a non-positive or
   non-numeric `timeout_s`. Each rejection is unit-tested. A valid execution task row
   parses from JSONL into an equal `ExecutionSpec` record.
3. **Pure overlay.** A pure `overlay_oracle(final_tree, held_out_tests)` helper
   (in `graders/execution.py`) returns either a combined tree plus the tuple of
   **displaced agent paths** (exact-path collisions where the oracle file replaced an
   agent-written file — oracle always wins), or a structured collision report when
   any agent path and oracle path collide on canonical prefix (NFC+casefold) without
   being spelled identically. The collision predicate is shared with the existing
   pure predicate from item 001 (one implementation, not a third copy). Unit and
   property tests: oracle-wins replacement, displaced-path reporting, collision
   detection symmetric to 001's `_prefix_collision` semantics, no input mutation.
4. **Pure content hash.** A pure `execution_hash(spec, final_tree) -> str` (sha256
   over the canonical-JSON rendering of `held_out_tests`, the final tree, and
   `timeout_s`) keys the verdict map, computable even when the overlay would collide.
   Property tests: deterministic; changes to any oracle path, any oracle content, any
   final-tree entry, or `timeout_s` change the hash; the same inputs hash identically
   from grader and edge.
5. **Verdict channel records.** `graders/execution.py` defines a frozen
   `ExecutionVerdict` (`result: ExecutionResult`, `execution_hash: str`,
   `displaced_paths: tuple[str, ...]`); `runners/execution_edge.py` defines a frozen
   `ExecutionError` (`kind: Literal["tree_collision", "harness"]`, `detail: str`,
   `execution_hash: str`) — mirroring the `JudgeVerdict` / `JudgeError` split.
   `records/serialize.verdict_to_dict` / `verdict_from_dict` are extended with
   distinct tags for both, and a round-trip test proves
   `from_dict(to_dict(x)) == x` for each.
6. **Pure grader.** `graders/execution.py` exposes
   `grade_execution(*, spec, trajectory, verdicts) -> GradeResult` with
   `grader_id="execution"`. It performs no I/O and imports nothing effectful
   (no subprocess, no `runners.*`): it computes the hash, reads the map, and
   interprets. `passed` iff the verdict's suite `status == "passed"`; `score` is
   binary `1.0`/`0.0` (counts ride in evidence). Unit-tested entirely with
   hand-built verdict maps, no sandbox.
7. **Grader edge cases are structured, never raised.** With `final_state=None` the
   grader returns a non-pass *before* any hash lookup
   (`evidence={"execution": "not_run", "reason": "missing_final_state"}`). With a
   `final_state` lacking a `"files"` key, the final tree is the empty mapping (the
   oracle then runs and fails honestly at the edge). With no value at the hash key,
   non-pass with `{"execution": "not_run", "reason": "verdict_missing",
   "execution_hash": …}` — the pure grader never executes as a fallback. With an
   `ExecutionError` at the key, non-pass with
   `{"execution": "error", "execution_error": {"kind", "detail"}, "execution_hash"}`.
   Each path unit-tested.
8. **Evidence contract.** A passing or status-failing run carries
   `evidence["execution"] == "run"` plus: `status`, `exit_code`, counts
   (`passed`/`failed`/`errors`/`skipped`), the per-test `(test_id, status)` list,
   canonicalized `stdout`/`stderr` (already capped by item 001), `execution_hash`,
   and `displaced_paths`. The three-valued `evidence["execution"]`
   (`"run" | "not_run" | "error"`) is the mechanical discriminator item 004 reads —
   the execution analogue of the judge's `"judge_error"` key. Asserted by tests.
9. **Taxonomy untouched.** `FailureCategory` gains no new values; every execution
   non-pass carries `failure_reason=None` (outcome miss / infra record, never a
   policy breach — per CONTEXT.md's "None is the category for 'the answer was
   wrong'"). Verified by the golden expectations and a test asserting the literal's
   member set is unchanged.
10. **Spec collector.** A pure `collect_execution_specs(verification)` walks the spec
    tree exactly as `collect_judge_specs` does (recursing `AllOf`), returning every
    reachable `ExecutionSpec`. Unit-tested on nested `AllOf` trees.
11. **Grading edge.** `runners/execution_edge.py` exposes
    `precompute_execution_verdicts(*, verification, trajectory) ->
    dict[str, ExecutionVerdict | ExecutionError]`: collects specs; returns `{}` when
    none are reachable or `final_state is None`; otherwise overlays (pure), runs
    item 001's `run_pytest` on the combined tree with the spec's effective timeout,
    and stores the verdict at its hash. A pure-overlay collision yields
    `ExecutionError(kind="tree_collision")`; any unexpected exception at the edge is
    captured as `ExecutionError(kind="harness")` — an exception never escapes into
    the verdict map (judge-edge precedent). Integration tests cover: oracle pass,
    oracle fail, collection/import error, timeout (small `timeout_s`), `no_tests`,
    and tree collision.
12. **Dispatch wiring.** `graders/dispatch.grade_trajectory` gains an
    `isinstance(verification, ExecutionSpec)` branch calling `grade_execution`. No
    signature change: the existing `verdicts` parameter is the channel (values
    discriminated by `isinstance`, so judge and execution verdicts coexist in one
    map). An `AllOf` nesting an execution leg beside a `TrajectorySpec` policy leg
    grades both — tested.
13. **Production call site.** `runners/multi_run.run_task_k` builds the verdict map
    via `precompute_execution_verdicts` between `run_single` and `grade_trajectory`
    and threads it in. Tasks with no `ExecutionSpec` produce an empty map and grade
    byte-identically to today; all existing multi_run and dispatch tests pass
    unchanged.
14. **Golden conformance cases.** The golden harness gains an optional per-case
    `"registry"` field (`"workspace"` default, `"code_world"` for execution cases)
    and, when the parsed spec tree contains `ExecutionSpec`s, builds verdicts through
    the production `precompute_execution_verdicts` (real sandboxed pytest — the
    harness reproduces the oracle end to end; deterministic per ADR-0009). At least
    nine new cases: (a) oracle suite passes; (b) oracle suite fails (repair wrong);
    (c) collection/import error; (d) timeout via per-spec `timeout_s`; (e) `no_tests`
    (oracle file pytest collects nothing from); (f) oracle-path displacement —
    agent pre-wrote the oracle path, oracle wins, verdict from oracle content;
    (g) tree collision → `ExecutionError` non-pass; (h) missing `final_state`;
    (i) `AllOf(execution, trajectory)` composition. The suite-count assertion in
    `test_golden_conformance.py` is updated. Every execution golden expects
    `failure_reason: null`.
15. **Reproducibility.** An integration test grades the same `(spec, trajectory)`
    twice through the full edge-plus-grader pipeline and asserts the two serialized
    `GradeResult`s are byte-identical (`grade_result_to_dict` → canonical JSON) —
    the MASTER-SPEC "same task + same final file tree ⇒ byte-identical verdict"
    constraint made executable.
16. **Decision recorded.** ADR-0010 documents: oracle-wins overlay with structured
    collision handling (options considered: agent-wins — rejected as a reward-hack
    vector; error-on-exact-collision — rejected for punishing unknowable hidden
    paths), and the single content-hash-keyed verdict map shared across edge-backed
    graders (options considered: a separate `executions` parameter; in-grader
    execution).
17. **TDD evidence.** Every behavior lands red-green; pure-core tests use no mocks;
    subprocess behavior is tested only at the edge and in the golden/integration
    suites.

## Non-goals

- **Dataset.** No code-repair tasks, no `code_repair_v1`, no authoring rubric or
  oracle-vs-initial-tree conformance checks — item 003 (that suite also owns the
  "oracle contains at least one collectible `test_*.py`" check, deliberately kept
  out of the structural parser).
- **Failure classification / report.** No task/agent/harness classifier, no report
  command — item 004 consumes the evidence contract this item pins.
- **`expected_status` knob, partial credit, or fractional scores.** Pass is suite
  `status == "passed"`; counts are evidence, not score.
- **Re-using the agent's mid-run `run_tests` results as the oracle.** Those cover
  only the *visible* tests; the oracle runs post-hoc at the grading edge. (This
  clarifies ADR-0008's closing sentence: "reads the recorded results" means the
  edge-precomputed verdict threaded in as data.)
- **Wiring judge-verdict precompute into `multi_run`.** Discovered gap: no
  production call site builds judge verdicts today (`collect_judge_specs` has no
  caller outside tests; live `LlmJudgeSpec` legs grade as `not_run`). The new
  helper returns a plain hash-keyed dict so a future judge precompute merges into
  the same map, but fixing the judge wiring is out of scope here.
- **Execution caching, test-selector arguments, per-task interpreters, container
  isolation** — all unchanged from item 001's non-goals.

## Constraints

- **Reproducibility (hard).** Same `ExecutionSpec` + same final file tree ⇒
  identical `execution_hash` ⇒ byte-identical serialized `ExecutionVerdict`
  (guaranteed by item 001/ADR-0009) ⇒ byte-identical `GradeResult` (criterion 15).
- **Functional core / imperative shell.** `graders/execution.py` stays pure (no
  subprocess/filesystem imports; importing it never executes anything); all
  execution I/O lives in `runners/execution_edge.py` atop the existing
  `runners/pytest_edge.run_pytest`. Records frozen; no caller-data mutation.
- **Public-API stability.** `grade_trajectory` / `grade_all_of` signatures
  unchanged (the existing `verdicts` mapping is the channel); `records/execution.py`,
  `records/turns.py`, `tools/code_world.py`, `runners/pytest_edge.py` untouched;
  the `multi_run` change is internal and behavior-preserving for non-execution
  tasks; `FailureCategory` unchanged.
- **Dependencies.** None added — stdlib `hashlib`/`json` plus existing modules.
- **Security.** Held-out oracle tests must never reach agent-visible data: the
  verification spec is never rendered into prompts or tool results (it never
  passes through `runners/wire.py`), and a test asserts the oracle file contents
  do not appear in any trajectory turn of an execution-graded run fixture. The
  sandbox security posture (scrubbed env, temp-dir isolation, no-network-by-
  convention) is item 001's, inherited unchanged; oracle-wins overlay closes the
  agent-overwrites-the-oracle reward-hack vector.
- **Performance.** The grading edge adds one sandboxed pytest run per execution
  task per run (single-digit seconds for the item-003 micro-programs); the new
  golden cases add roughly ten sandbox runs to the suite — the timeout case pins
  `timeout_s` at ~1 s so the whole golden suite stays under ~20 s.
- **Size/style.** Each new module under ~200 lines; small pure functions, early
  returns; ruff-clean (`E,F,I,UP`).

## Open questions resolved during brainstorming

Autonomous mode: each question was answered with the recommended option; rationale
recorded here in lieu of user confirmation.

1. **Variant name and shape?** → `ExecutionSpec(type="execution", held_out_tests,
   timeout_s=None)`. The name was forward-declared by ADR-0005, ADR-0008, CONTEXT.md,
   and the schema comment; the fields are the minimum the grading edge needs.
   No `expected_status`: "tests are the oracle" means the oracle passing *is* the
   verdict, and a configurable expectation would let `no_tests` or `failed` be
   declared a pass — an oracle-defect hole.
2. **Does the spec carry a timeout?** → Yes, optional (`None` ⇒ edge default 10 s).
   Item 001 (resolved decision 5) excluded timeout from `ExecutionRequest` to keep
   execution policy out of *agent-reachable* data; a `VerificationSpec` is task-author
   data the agent never sees, so the objection does not transfer. Mirrors
   `metadata.max_steps`-as-data (ADR-0004), and the timeout golden case needs an
   authorable small value.
3. **How do oracle tests combine with the agent's tree?** → Pure overlay, **oracle
   wins** on exact-path collision, displaced agent paths recorded in evidence.
   Agent-wins is disqualifying (the agent could pre-write trivial tests at the oracle
   path and mask the oracle — reward hacking); failing the run on exact collision
   punishes the agent for paths it cannot know exist. Displacement is evidence, not
   an automatic fail — the oracle's verdict stays the verdict.
4. **What about canonical-prefix collisions (001's injective invariant)?** → The
   pure overlay detects them *before* materialization, reusing the item-001 collision
   predicate; the edge records `ExecutionError(kind="tree_collision")` and the grader
   produces a structured non-pass. The agent can legally create such a path (its own
   tree is valid in isolation), so this must be a graded record for item 004 to
   classify — never a harness crash. The materializer's own `RuntimeError` checks
   remain defense-in-depth.
5. **How does subprocess execution thread into the pure grader?** → ADR-0005's rule,
   exactly as its closing sentence prescribes for `ExecutionSpec`: the edge
   pre-computes (post-trajectory, since the final tree is only knowable then),
   keyed by a deterministic pure hash, threaded as immutable data; the grader only
   reads. In-grader execution was rejected (collapses the functional core);
   a second `executions` parameter was rejected (signature churn through
   dispatch/composite for no semantic gain — `isinstance` discrimination on the
   existing map's values is already the judge pattern).
6. **What keys the verdict?** → `execution_hash(spec, final_tree)`: sha256 over
   canonical JSON of `held_out_tests` + final tree + `timeout_s` — the execution
   analogue of the judge's `prompt_hash` (a pure function of every
   interpretation-affecting input, computable on both sides of the boundary, and
   well-defined even when the overlay collides, unlike a hash of the combined tree).
7. **How do suite statuses map to `GradeResult` / `FailureCategory`?** → `passed`
   iff `status == "passed"`; *every* non-pass carries `failure_reason=None`.
   `failed`/`error`/`timeout` are outcome misses (the repair is wrong, broken, or
   hung); `no_tests` after overlay signals an oracle defect; `tree_collision` and
   `verdict_missing` are infra records — none are policy breaches, and CONTEXT.md
   explicitly forbids new categories for plain misses. Item 004's task/agent/harness
   classification is a separate axis fed by the mechanical evidence discriminator
   (`evidence["execution"]` ∈ `"run" | "not_run" | "error"`), so extending the
   closed 9-value enum now would preempt 004's design with a worse vocabulary.
8. **Binary or fractional score?** → Binary `1.0`/`0.0`, uniform with every existing
   grader; per-test counts ride in evidence for any fractional reporting item 004
   wants. A fractional headline invites partial-credit gaming and contradicts
   "verdict from test results".
9. **Golden conformance format?** → Existing case shape plus an optional
   `"registry"` field; the conformance harness calls the *production* precompute
   helper, running real sandboxed pytest per case. Embedding precomputed verdicts
   keyed by hand-maintained hashes was rejected (brittle, hostile to authors);
   skipping the edge in goldens was rejected (the MASTER-SPEC asks the goldens to
   conform the *execution grading* pipeline, and ADR-0009 makes the real run
   deterministic enough to be a golden oracle).
10. **Where does production grading get its verdicts?** → `multi_run.run_task_k`,
    between `run_single` and `grade_trajectory` — the only place that holds both the
    trajectory and the grading call. Exploration found judge verdicts are *not*
    wired there today; this item ships the execution wiring with a mergeable
    map-shaped helper and leaves the judge gap explicitly out of scope (see
    Non-goals).
11. **Module placement?** → Pure half in `graders/execution.py`, edge in
    `runners/execution_edge.py`, mirroring `graders/judge.py` /
    `runners/judge_edge.py`. The package-path collision with `records/execution.py`
    is acceptable (fully-qualified imports disambiguate; precedent: three modules
    already share the "judge" stem).
12. **What if `final_state` is `None` or not a code-world state?** → `None` ⇒
    grader-side structured non-pass before any lookup (`missing_final_state`);
    present-but-no-`"files"` ⇒ empty tree, oracle runs and fails honestly at the
    edge (the import error is real signal, and inventing a third "wrong world"
    evidence path adds vocabulary without a consumer).
13. **Parser strictness on oracle paths?** → Structural checks only (canonical form,
    reserved key, non-empty, internal collisions) — fail fast at load time, where a
    bad oracle file is unambiguously a task defect. The "contains a collectible
    pytest file" heuristic belongs to item 003's authoring conformance, not the
    parser: `conftest.py` and helper modules are legitimate oracle files.
