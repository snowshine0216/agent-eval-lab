# Item 001 — Code-world: isolated, reproducible task environments

Run: `coding-agent-eval` (Weeks 5-6) · Source row: MASTER-SPEC item 001 · Date: 2026-06-11
Brainstormed autonomously (no user in loop); every question auto-resolved with the
recommended answer, recorded in §Open questions below.

## Goal

Deliver the foundation of the coding-agent slice: a **code-world** whose state is an
in-memory file tree (`{"files": {posix-relative-path: text-content}}`) with four
schema-validated tools the agent drives through the existing pure
`apply(registry, name, arguments, state) -> (state', outcome)` pattern
(`read_file`, `write_file`, `list_files`, `run_tests`), plus a **sandboxed execution
edge** that materializes a file tree into a fresh temp directory and runs pytest in a
subprocess with a hard timeout, a scrubbed from-scratch environment, a pinned
interpreter (`sys.executable`), and deterministic structured results. The `run_tests`
tool bridges to the edge via an **effect-request**: the pure `apply` returns a
serializable `ExecutionRequest` (an immutable snapshot of the current tree) instead of
a `ToolOutcome`; the imperative runner loop — the only place subprocess/filesystem I/O
happens — fulfills the request through the pytest edge and records the fulfilled
~~`ToolSuccess`/`ToolFailure` on the trajectory~~ — corrected by grill: a fulfilled
request is **always** recorded as `ToolSuccess` carrying the serialized
`ExecutionResult`, whatever the suite status; `ToolFailure` stays reserved for pure
validation (Resolved decision 2, ADR-0008) — on the trajectory, so trajectories stay
self-contained
replay artifacts (ADR-0001) and the grading tiers downstream (item 002) read recorded
data without re-executing, per the ADR-0005 rule generalized to in-loop effects.

## Acceptance criteria

Each criterion is independently verifiable by a named test or inspection.

1. **World module exists.** `src/agent_eval_lab/tools/code_world.py` defines a
   `CODE_WORLD_TOOLS` registry of exactly four `ToolDef`s — `read_file`, `write_file`,
   `list_files`, `run_tests` — each with a JSON schema using
   `additionalProperties: false`, and an `apply()` whose keyword signature matches
   `tools/workspace.py`'s (`registry`, `name`, `arguments`, `state`). *Sharpened by
   grill (Resolved decision 1):* the keyword parameters match; the return type widens
   explicitly to `tuple[State, ToolOutcome | ExecutionRequest]` — the union is the
   documented contract the loop discriminates on by `isinstance`.
2. **State shape and purity.** Code-world state is `{"files": Mapping[str, str]}` with
   POSIX-style relative paths. A property test (Hypothesis) shows `apply` never mutates
   the input state, and a determinism property shows same `(state, name, arguments)`
   ⇒ equal `(state', outcome)`.
3. **Editing tools behave.** Unit tests (no mocks): `read_file` returns file content,
   `ToolFailure` on a missing path; `write_file` returns a new state with the file
   created or fully overwritten; `list_files` returns the sorted tuple of all paths.
   *Sharpened by grill (Resolved decision 12):* results follow the workspace mapping
   convention — `read_file` → `{"path", "content"}`, `write_file` →
   `{"path", "created": <bool>}`, `list_files` → `{"paths": [...]}`, `run_tests` →
   the serialized `ExecutionResult` dict.
4. **Path safety in the pure core.** Absolute paths, paths containing `..` segments,
   and empty paths are rejected as `ToolFailure` by the pure tools — unit tested for
   each tool that takes a path. *Extended by grill (Resolved decisions 7-8):* the
   canonical-form rule also rejects `.` segments, empty segments (`a//b`), trailing
   `/`, backslashes, and NUL — one canonical spelling per path — and `write_file`
   rejects file/directory prefix collisions in both directions (writing `a` when
   `a/b` exists; writing `a/b` when `a` is a file), so every reachable state is
   materializable by construction.
5. **`run_tests` is pure.** `apply` on `run_tests` performs no I/O and returns the
   state **unchanged** plus an `ExecutionRequest` carrying an immutable snapshot of
   `files`. Unit tested without any filesystem or subprocess involvement.
6. **Bridge records.** `src/agent_eval_lab/records/execution.py` defines frozen,
   serializable `ExecutionRequest` and `ExecutionResult`. `ExecutionResult` carries:
   ~~`outcome` literal (`"passed" | "failed" | "error" | "timeout" | "no_tests"`),~~
   ~~`exit_code`, counts (passed/failed/errors), a per-test tuple sorted by test id with~~
   ~~each test's status, and head-truncated `stdout`/`stderr` (fixed byte cap, explicit~~
   ~~truncation marker).~~ — corrected by grill: field renamed `status` ("outcome"
   already carries two CONTEXT.md senses); counts and per-test vocabulary gain
   `skipped`; test id pinned to `classname::name`; output is canonicalized (ADR-0009)
   and the cap pinned (Resolved decisions 3-4, 9-11) —
   a `status` literal (`"passed" | "failed" | "error" | "timeout" | "no_tests"`),
   `exit_code`, counts (`passed`/`failed`/`errors`/`skipped`), a per-test tuple sorted
   by test id (`classname::name` from the JUnit XML; per-test status
   `passed | failed | error | skipped`), and head-truncated **canonicalized**
   `stdout`/`stderr` (8 KiB byte cap per stream, explicit truncation marker). Both
   round-trip through the records serialization layer.
   Wall-clock duration is **excluded** from the record (it is the one nondeterministic
   observable).
7. **Execution edge exists.** `src/agent_eval_lab/runners/pytest_edge.py` exposes
   `run_pytest(files, timeout_s) -> ExecutionResult`: materializes the tree into a
   fresh temp dir (sorted path order, parents created, UTF-8), invokes
   `sys.executable -m pytest -q --junitxml=<tmp> -p no:cacheprovider` with
   `cwd=<root>`, parses the JUnit XML with stdlib `xml.etree` (pure helper function,
   unit-testable on captured XML), canonicalizes the captured output via a pure helper
   (temp-root occurrences → the fixed `<sandbox>` placeholder; pytest timing token
   normalized — *added by grill, Resolved decision 4 / ADR-0009: criterion 11 is
   unsatisfiable over verbatim output*), and removes the temp dir in a `finally`.
8. **Hermetic environment.** The subprocess env is constructed from scratch (never
   inherited from `os.environ`): `PYTHONHASHSEED=0`,
   `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONDONTWRITEBYTECODE=1`,
   `PYTHONIOENCODING=utf-8`, `LC_ALL`/`LANG` pinned, `TZ=UTC`, `HOME=<temp dir>`,
   `PYTHONPATH=<root>`, minimal `PATH`. An integration test plants a sentinel variable
   (and a fake `OPENROUTER_API_KEY`-style secret) in the parent environment and proves
   the sandboxed test process cannot see either.
9. **Timeout is structured, processes are reaped.** A fixture suite that sleeps past a
   small `timeout_s` yields `ExecutionResult(outcome="timeout")`; the subprocess is
   started in its own session and the whole process group is killed on timeout. The
   edge never raises for timeout, crash, or missing JUnit XML — those map to
   `"timeout"`/`"error"` outcomes with pytest exit-code classification
   (0 passed, 1 failed, 2-4 error, 5 no_tests).
10. **Edge integration matrix.** Integration tests cover fixture trees for: all tests
    passing, some failing, a collection/import error, timeout, and no tests collected —
    each asserting the structured `outcome` and per-test statuses.
11. **Reproducibility.** An integration test runs `run_pytest` twice on the same
    fixture tree and asserts the two serialized `ExecutionResult`s are byte-identical.
12. **Loop fulfills requests generically.** The runner loop gains additive, defaulted
    parameters (world `apply` function and an executor callable); when `apply` returns
    an `ExecutionRequest` the loop fulfills it via the executor and appends a
    `ToolResultTurn` with the fulfilled `ToolSuccess(result=<serialized
    ExecutionResult>)` — matched on the request type, never on the tool-name string.
    All existing workspace-world runner tests pass unchanged with the defaults.
    *Extended by grill (Resolved decisions 2, 6):* the fulfilled turn is **always**
    `ToolSuccess`, whatever the suite `status`; an `ExecutionRequest` reaching a loop
    with no executor raises `RuntimeError` (harness misconfiguration, mirroring
    `workspace.apply`'s registered-but-unimplemented guard) — never a `ToolFailure`
    shown to the agent.
13. **Decision recorded.** A new ADR documents the effect-request bridge (options
    considered: edge name-interception, ADR-0005-style precompute, real-FS world;
    consequences), following the ADR-0005 precedent that names `ExecutionSpec` as the
    next edge-backed grader. *Satisfied by grill:* ADR-0008 (effect-request bridge);
    ADR-0009 additionally records the output-canonicalization decision.
14. **TDD evidence.** Every behavior above lands red-green (test commit precedes or
    accompanies implementation in the same commit series); pure-core tests use no
    mocks; subprocess behavior is tested only at the edge.

## Non-goals

- **Grading.** No `ExecutionSpec` variant, no execution grader, no verdict threading
  into `grade_trajectory` — that is item 002.
- **Dataset.** No code-repair tasks, no held-out oracle tests, no
  `code_repair_v1` world template id — item 003. (The `run_tests` tool runs only the
  *visible* tests present in the tree.)
- **Failure classification / reporting** — item 004.
- **Kernel-level sandboxing.** No containers, no network namespaces, no seccomp;
  isolation is temp-dir + scrubbed env + convention (see Constraints).
- **Dependency installation.** The sandbox never runs pip/uv; task programs must be
  stdlib-only (enforced by item 003's dataset rubric, enabled here by design).
- **Binary files**, file deletion/rename, patch/diff-style editing tools, a
  path-selector argument on `run_tests`, execution-result caching, per-task
  interpreter versions. All deferrable without API breakage.

## Constraints

- **Reproducibility (hard).** Same file tree + same command ⇒ byte-identical
  serialized `ExecutionResult` within a pinned environment (the project venv;
  `pytest>=9.0.0` pinned via `uv.lock`, interpreter = `sys.executable`).
- **Functional core / imperative shell.** All subprocess and filesystem I/O lives in
  `runners/pytest_edge.py` and the loop; `tools/code_world.py` and
  `records/execution.py` stay pure and import nothing effectful. Records are frozen
  dataclasses; no mutation of caller-owned data.
- **Public-API stability.** `records/turns.py` (`Turn`, `ToolOutcome`) and
  `records/trajectory.py` are untouched; `tools/workspace.py` is untouched; the loop's
  new parameters are additive with defaults preserving current behavior.
- **Dependencies.** No new runtime dependencies — stdlib `subprocess`, `tempfile`,
  `xml.etree`, `os`, `signal` only. JUnit XML is core pytest (no plugin).
- **Security.** (1) Secrets never leak into the sandbox: env built from scratch, so
  provider API keys in the harness process are invisible to executed task code.
  (2) Path traversal rejected twice — pure validation in tools, and the materializer
  independently refuses any resolved path outside the temp root (defense in depth).
  (3) No network enforcement at the OS level on macOS without containers; mitigated by
  env scrub (no proxy vars), a tight default timeout, and the item-003 rubric banning
  network-touching tasks. Documented as a known limitation.
- **Performance.** Default `timeout_s=10`; a small fixture tree's full
  materialize-run-parse-cleanup cycle should complete in single-digit seconds; temp
  dirs always cleaned (`finally`), no orphan processes (process-group kill).
- **Size/style.** Each new module stays under ~200 lines; functions small and pure per
  CLAUDE.md; ruff-clean (`E,F,I,UP`).

## Open questions resolved during brainstorming

Autonomous mode: each question was answered with the recommended option; rationale
recorded here in lieu of user confirmation.

1. **Flat vs nested file-tree state?** → Flat mapping `path -> content`. Mirrors the
   workspace state shape, serializes trivially, and materialization is a single sorted
   loop; nesting buys nothing for small repair programs.
2. **Tool surface?** → Exactly the four named in the MASTER-SPEC row. `write_file` is
   create-or-overwrite of full content — simplest deterministic edit primitive; patch
   tools and deletion add failure modes without serving the repair tasks.
3. **How does pure `apply` trigger execution?** → Effect-request (`ExecutionRequest`
   returned in the outcome position; loop fulfills). ADR-0005's literal precompute
   cannot work — the mid-trajectory tree is unknowable before the run — so this is the
   faithful generalization: the effectful input is still produced at the edge and the
   pure code only describes *what* to execute. Name-based loop interception was
   rejected (couples the loop to world vocabulary, splits validation from `apply`);
   real-FS tools were rejected (breaks purity, `final_state`, replayability/ADR-0001).
4. **Does `run_tests` change state?** → No; it is read-only over the tree. Same tree
   ⇒ same request ⇒ (hermetic edge) same result.
5. **How are pytest results parsed?** → `--junitxml` (core pytest, stdlib XML parse,
   pure helper) with exit-code classification as fallback when XML is absent
   (pre-collection crash). Parsing stdout is fragile; `--report-log` needs a plugin.
6. **What is "deterministic" in the result?** → Everything recorded: outcome, exit
   code, counts, sorted per-test statuses, head-truncated output. Wall-time is
   excluded from the record entirely rather than carried as "informational".
7. **Where do the bridge records live?** → `records/execution.py`, beside the other
   shared serializable records, avoiding a `tools` ↔ `runners` import cycle.
8. **Zero-arg or selector-arg `run_tests`?** → Zero-arg in v1. Task programs are
   small; a whole-tree run is cheap and removes a nondeterminism/argument-validation
   surface. Selector is additive later.
9. **Default timeout?** → 10 s, edge parameter. Judgment call (not derivable from
   MASTER-SPEC): generous for stdlib-only micro-programs, small enough that a hung
   test costs little.
10. **Network isolation mechanism?** → Env scrub + convention only; kernel-level
    isolation needs containers, out of scope on this macOS host. Recorded as a known
    limitation to be restated in item 004's report.
11. **Does the loop change land in this item?** → Yes, minimally (criterion 12): a
    world whose `run_tests` cannot be fulfilled is dead code; the additive defaulted
    parameters keep every existing test green.
12. **Interpreter pinning?** → `sys.executable` (the harness venv, where pytest is
    pinned by `uv.lock`). Reproducibility is claimed *within* a pinned environment,
    not across machines; recording interpreter/pytest versions in run-level metadata
    is left to item 004's report.

## Resolved decisions

Grill session (grill-with-docs, autonomous, 2026-06-11) against CONTEXT.md,
ADRs 0001-0007, and the current code (`tools/workspace.py`, `runners/loop.py`,
`records/turns.py`, `records/serialize.py`, `records/grade.py`). No user in loop;
every recommendation auto-accepted.

1. **Q:** Criterion 1 says code-world `apply`'s signature "matches" workspace's —
   but `run_tests` returns a non-`ToolOutcome`. What is the honest type?
   **A:** `tuple[State, ToolOutcome | ExecutionRequest]`: keyword parameters match
   exactly; the return type widens *explicitly* in the union, and the loop
   discriminates by `isinstance` on the request type.
   *Rationale:* type honesty over signature cosplay; the union is the documented
   contract.

2. **Q:** A fulfilled `run_tests` whose suite failed — `ToolSuccess` or
   `ToolFailure`? (Goal said "`ToolSuccess`/`ToolFailure`"; criterion 12 said only
   `ToolSuccess`.)
   **A:** Always `ToolSuccess(result=<serialized ExecutionResult>)`, whatever the
   suite `status` (including `timeout`/`error`). `ToolFailure` is reserved for the
   pure validation layer.
   *Rationale:* the tool did its job — it ran the tests and reported; conflating a
   failing suite with tool breakage would confound item 004's failure taxonomy.
   → ADR-0008 consequence; Goal line struck.

3. **Q:** `ExecutionResult.outcome` would be a *third* sense of "outcome"
   (`ToolOutcome`, *outcome verification* already exist). Rename?
   **A:** Yes — the field is `status` (`passed | failed | error | timeout |
   no_tests`); per-test entries also carry `status`. Also avoid "result" (taken by
   `ToolSuccess.result` and `RunResult`).
   *Rationale:* CONTEXT.md's prime directive is one meaning per word.
   → CONTEXT.md term **status (execution)**; criterion 6 struck and corrected.

4. **Q:** Criterion 11 demands byte-identical serialized `ExecutionResult`s — but
   tracebacks embed the per-run random temp-dir root and pytest's `-q` summary
   prints wall-clock seconds (`1 failed in 0.03s`). Unsatisfiable as written?
   **A:** Yes — record **canonicalized output**: a pure helper replaces the temp
   root with the `<sandbox>` placeholder and normalizes the pytest timing token
   before truncation; byte-identity is claimed over the canonicalized record.
   *Rationale:* the only repair that keeps tracebacks and assertion details (needed
   by the agent and item 004) while making the MASTER-SPEC hard constraint hold.
   → ADR-0009; criterion 7 extended.

5. **Q:** Does `ExecutionRequest` carry `timeout_s` or the interpreter?
   **A:** No — it carries only the immutable file-tree snapshot; timeout and
   interpreter are edge/executor policy.
   *Rationale:* keeps the request a pure function of state (the determinism
   property stays clean) and keeps execution policy out of agent-reachable data.
   → CONTEXT.md term **ExecutionRequest**.

6. **Q:** The loop receives an `ExecutionRequest` but no executor was configured —
   `ToolFailure` or crash?
   **A:** `RuntimeError`: harness misconfiguration, mirroring `workspace.apply`'s
   registered-but-unimplemented guard.
   *Rationale:* a harness bug must crash loudly, not gaslight the agent with a fake
   tool error that then gets graded. → criterion 12 extended.

7. **Q:** Criterion 4 rejects absolute/`..`/empty paths — what about `.` segments,
   `a//b`, trailing `/`, backslashes, NUL?
   **A:** Reject them all: POSIX-relative, one canonical spelling per path.
   *Rationale:* aliasing spellings make two states for one tree and break
   determinism/state equality; backslash is a legal macOS filename char but a
   separator on Windows — ban the ambiguity. → criterion 4 extended.

8. **Q:** `write_file("a/b")` when `a` is a file (or `write_file("a")` when `a/b`
   exists) materializes to an OSError mid-edge — who prevents it?
   **A:** Pure `write_file` rejects file/directory prefix collisions in both
   directions as `ToolFailure`.
   *Rationale:* every reachable state stays materializable by construction (illegal
   states unrepresentable); the materializer's outside-root refusal remains
   defensive depth only. → criterion 4 extended.

9. **Q:** JUnit XML reports skipped tests; the spec counted only
   passed/failed/errors. Drop skips silently?
   **A:** No — add `skipped` to the counts and the per-test status vocabulary
   (`passed | failed | error | skipped`). Suite-level mapping unchanged (exit 0
   with skips ⇒ `passed`).
   *Rationale:* stdlib task programs may legitimately skip; silent omission
   misrepresents the run. → criterion 6 corrected.

10. **Q:** "Sorted by test id" — what exactly is the id?
    **A:** `classname::name` from the JUnit XML testcase attributes — a
    deterministic reconstruction of the pytest nodeid, used as the sort key.
    *Rationale:* pins the sort order to data actually present in the XML.
    → criterion 6 corrected.

11. **Q:** "Fixed byte cap" on stdout/stderr — what number?
    **A:** 8 KiB (8192 bytes) per stream, head-truncated, explicit truncation
    marker; a named constant in `records/execution.py`.
    *Rationale:* generous for `-q` micro-suite output, bounded for record size and
    the agent's context budget. → criterion 6 corrected.

12. **Q:** Tool result shapes — bare strings or mappings?
    **A:** The workspace mapping convention: `read_file` → `{"path", "content"}`,
    `write_file` → `{"path", "created": <bool>}`, `list_files` → `{"paths":
    [...]}`, `run_tests` → the serialized `ExecutionResult` dict.
    *Rationale:* every existing tool returns a mapping; uniformity keeps wire
    rendering and grader evidence consistent. → criterion 3 sharpened.

**Doc impact summary:** CONTEXT.md gains the "Code-world & execution" term cluster
(code-world, file tree, effect-request, ExecutionRequest, ExecutionResult,
status (execution), execution edge, sandbox, canonicalized output) plus dialogue
exchanges; ADR-0008 (effect-request bridge), ADR-0009 (canonicalized output).
