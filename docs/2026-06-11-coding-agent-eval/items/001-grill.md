Verdict: PASS

Subagent: fable
Questions resolved: 12
Docs touched:
  - CONTEXT.md (commit bcaa522)
  - docs/adr/0008-mid-trajectory-effects-bridge-through-effect-requests.md (commit bcaa522)
  - docs/adr/0009-recorded-execution-output-is-canonicalized-never-verbatim.md (commit bcaa522)
Spec refined: items/001-spec.md (commit bcaa522)

## Resolved decisions

- Q: Code-world `apply`'s "signature matches workspace's" — but `run_tests` returns a non-`ToolOutcome`; what is the honest type?
  A: `tuple[State, ToolOutcome | ExecutionRequest]` — keyword params match, return type widens explicitly; loop discriminates by `isinstance`.
  Rationale: type honesty over signature cosplay; the union is the documented contract.
  Doc impact: none (spec criterion 1 sharpened)

- Q: A fulfilled `run_tests` whose suite failed — `ToolSuccess` or `ToolFailure`? (Goal line was ambiguous.)
  A: Always `ToolSuccess` carrying the serialized `ExecutionResult`, whatever the suite status; `ToolFailure` reserved for pure validation.
  Rationale: the tool did its job; conflating a failing suite with tool breakage confounds item 004's failure taxonomy.
  Doc impact: ADR-0008; CONTEXT.md term effect-request

- Q: `ExecutionResult.outcome` would be a third sense of "outcome" (after `ToolOutcome` and outcome verification) — rename?
  A: Field is `status` (`passed | failed | error | timeout | no_tests`); also avoid "result" (taken by `ToolSuccess.result` and `RunResult`).
  Rationale: one meaning per word is CONTEXT.md's prime directive.
  Doc impact: CONTEXT.md term status (execution)

- Q: Criterion 11's byte-identical `ExecutionResult` is unsatisfiable: tracebacks embed the random temp-dir root and pytest's summary prints wall-clock seconds.
  A: Record canonicalized output — pure helper replaces the temp root with `<sandbox>` and normalizes the pytest timing token before truncation.
  Rationale: only repair that keeps tracebacks/assertion detail while making the MASTER-SPEC hard constraint actually hold.
  Doc impact: ADR-0009; CONTEXT.md term canonicalized output

- Q: Does `ExecutionRequest` carry `timeout_s` or the interpreter?
  A: No — only the immutable file-tree snapshot; timeout/interpreter are edge policy.
  Rationale: keeps the request a pure function of state and execution policy out of agent-reachable data.
  Doc impact: CONTEXT.md term ExecutionRequest

- Q: Loop receives an `ExecutionRequest` but no executor configured?
  A: `RuntimeError` — harness misconfiguration, mirroring `workspace.apply`'s registered-but-unimplemented guard; never a `ToolFailure`.
  Rationale: a harness bug must crash loudly, not gaslight the agent with a gradeable fake tool error.
  Doc impact: ADR-0008 consequence

- Q: Path rules beyond absolute/`..`/empty — `.` segments, `a//b`, trailing `/`, backslashes, NUL?
  A: Reject all; POSIX-relative, one canonical spelling per path.
  Rationale: aliasing spellings make two states for one tree and break determinism/state equality.
  Doc impact: none (spec criterion 4 extended)

- Q: `write_file("a/b")` when `a` is a file materializes to an OSError mid-edge — who prevents it?
  A: Pure `write_file` rejects file/directory prefix collisions in both directions as `ToolFailure`.
  Rationale: every reachable state stays materializable by construction; materializer refusal remains defensive depth only.
  Doc impact: CONTEXT.md term file tree (materializable-by-construction)

- Q: JUnit reports skipped tests; spec counted only passed/failed/errors?
  A: Add `skipped` to counts and per-test vocabulary; suite-level mapping unchanged.
  Rationale: stdlib task programs may legitimately skip; silent omission misrepresents the run.
  Doc impact: none (spec criterion 6 corrected)

- Q: "Sorted by test id" — what exactly is the id?
  A: `classname::name` from the JUnit XML testcase attributes (deterministic nodeid reconstruction), used as sort key.
  Rationale: pins the sort order to data actually present in the XML.
  Doc impact: none (spec criterion 6 corrected)

- Q: "Fixed byte cap" on stdout/stderr — what number?
  A: 8 KiB (8192 bytes) per stream, head-truncated, explicit marker; named constant in `records/execution.py`.
  Rationale: generous for `-q` micro-suite output, bounded for record size and context budget.
  Doc impact: ADR-0009 (cap recorded); spec criterion 6 corrected

- Q: Tool result shapes — bare strings or mappings?
  A: Workspace mapping convention: `read_file` → `{"path","content"}`, `write_file` → `{"path","created"}`, `list_files` → `{"paths":[...]}`, `run_tests` → serialized `ExecutionResult` dict.
  Rationale: every existing tool returns a mapping; uniformity keeps wire rendering and grader evidence consistent.
  Doc impact: none (spec criterion 3 sharpened)
