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
`ToolSuccess`/`ToolFailure` on the trajectory, so trajectories stay self-contained
replay artifacts (ADR-0001) and the grading tiers downstream (item 002) read recorded
data without re-executing, per the ADR-0005 rule generalized to in-loop effects.

## Acceptance criteria

Each criterion is independently verifiable by a named test or inspection.

1. **World module exists.** `src/agent_eval_lab/tools/code_world.py` defines a
   `CODE_WORLD_TOOLS` registry of exactly four `ToolDef`s — `read_file`, `write_file`,
   `list_files`, `run_tests` — each with a JSON schema using
   `additionalProperties: false`, and an `apply()` whose keyword signature matches
   `tools/workspace.py`'s (`registry`, `name`, `arguments`, `state`).
2. **State shape and purity.** Code-world state is `{"files": Mapping[str, str]}` with
   POSIX-style relative paths. A property test (Hypothesis) shows `apply` never mutates
   the input state, and a determinism property shows same `(state, name, arguments)`
   ⇒ equal `(state', outcome)`.
3. **Editing tools behave.** Unit tests (no mocks): `read_file` returns file content,
   `ToolFailure` on a missing path; `write_file` returns a new state with the file
   created or fully overwritten; `list_files` returns the sorted tuple of all paths.
4. **Path safety in the pure core.** Absolute paths, paths containing `..` segments,
   and empty paths are rejected as `ToolFailure` by the pure tools — unit tested for
   each tool that takes a path.
5. **`run_tests` is pure.** `apply` on `run_tests` performs no I/O and returns the
   state **unchanged** plus an `ExecutionRequest` carrying an immutable snapshot of
   `files`. Unit tested without any filesystem or subprocess involvement.
6. **Bridge records.** `src/agent_eval_lab/records/execution.py` defines frozen,
   serializable `ExecutionRequest` and `ExecutionResult`. `ExecutionResult` carries:
   `outcome` literal (`"passed" | "failed" | "error" | "timeout" | "no_tests"`),
   `exit_code`, counts (passed/failed/errors), a per-test tuple sorted by test id with
   each test's status, and head-truncated `stdout`/`stderr` (fixed byte cap, explicit
   truncation marker). Both round-trip through the records serialization layer.
   Wall-clock duration is **excluded** from the record (it is the one nondeterministic
   observable).
7. **Execution edge exists.** `src/agent_eval_lab/runners/pytest_edge.py` exposes
   `run_pytest(files, timeout_s) -> ExecutionResult`: materializes the tree into a
   fresh temp dir (sorted path order, parents created, UTF-8), invokes
   `sys.executable -m pytest -q --junitxml=<tmp> -p no:cacheprovider` with
   `cwd=<root>`, parses the JUnit XML with stdlib `xml.etree` (pure helper function,
   unit-testable on captured XML), and removes the temp dir in a `finally`.
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
13. **Decision recorded.** A new ADR documents the effect-request bridge (options
    considered: edge name-interception, ADR-0005-style precompute, real-FS world;
    consequences), following the ADR-0005 precedent that names `ExecutionSpec` as the
    next edge-backed grader.
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
