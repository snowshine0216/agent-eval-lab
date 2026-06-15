Verdict: PASS

## Subagent
claude-sonnet-4-6 (smoke-test dispatch, 2026-06-15)

## Source
Branch: `claude/harness-rounds-f-ablation-005`
Last commit: c38826a chore(005): ship artifacts (PR #30) + review PASS-WITH-NITS (security)

## Entry points
- `src/agent_eval_lab/runners/sandboxed_node_edge.py` — new confined-execution module
- `src/agent_eval_lab/records/node_feedback.py` — distinct versioned record class
- `src/agent_eval_lab/runners/f_candidate.py` — V-arm wiring (`make_f_run_fn`)
- `src/agent_eval_lab/tools/code_world.py` — `AUTHORED_RUN_TESTS_TOOLDEF` + `CODE_WORLD_TOOLS_V`
- `tests/runners/test_sandboxed_node_edge.py` — 22 tests (19 unit + 3 macOS integration)

## Observed behavior per criterion

### Confined-execution boundary (P0)
`sandboxed_node_edge.py` exists with a deny-default + explicit read-allowlist seatbelt profile.
The `seatbelt_profile()` function is a pure function of `(temp_tree, node_dir) → str`. The profile:
- starts with `(version 1)\n(deny default)\n(import "system.sb")`
- enumerates read subpaths: temp tree, node install dir, `/usr/lib`, `/usr/bin`, `/bin`, `/System`, `/private/var/db/dyld`
- uses `file-read-metadata` for `/private`, `/var` (stat-only, no content read)
- contains `(deny network*)`
- scopes writes to temp tree only
- does NOT contain a broad `(allow file-read*)` — confirmed by `'(allow file-read*)' not in prof: True`

### Security smoke evidence (step 3 output, load-bearing):
```
darwin_sandbox_available: True
read(golden): BLOCKED EPERM
stat(golden): BLOCKED EPERM
no broad read in profile: True
```
Both `readFileSync` and `statSync` on `evaluator-only/web-dossier-golden/golden-files/report-to-allure.js.golden` return `EPERM`. The stdout-leak channel is closed.

### Trusted oracle node_edge.py untouched
`git diff autodev/harness-rounds-f-ablation-feature..HEAD -- src/agent_eval_lab/runners/node_edge.py` produces empty output. The oracle path is byte-stable.

### make_authored_test_executor
`make_authored_test_executor` builds an executor that always runs `node --test tests/authored/` regardless of `ExecutionRequest` contents. Model-supplied commands are rejected by construction (fixed command list). `tests/authored/` is a reserved constant (`AUTHORED_TEST_DIR = "tests/authored/"`). F3 seeded tests are not run as feedback.

### V-arm wiring in make_f_run_fn
`make_f_run_fn` in `f_candidate.py`:
- Detects V arm via `edit_task.initial_state.get("factor_v")`
- On non-Darwin: raises `NotImplementedError` (guard stays)
- On Darwin: calls `node_install_paths()` + `make_authored_test_executor(...)`, sets `registry = CODE_WORLD_TOOLS_V`
- `bare`/`prompt` arms: `executor=None`, `registry = CODE_WORLD_TOOLS`

### Darwin probe
`darwin_sandbox_available()` checks `sys.platform == "darwin"` AND `os.access(SANDBOX_EXEC, os.X_OK)` — mirrors `node_supports_junit` probe shape. Returns `True` on this host.

### NODE_BIN trust-boundary guard
`node_install_paths()` raises `RuntimeError` if `install_dir` is an ancestor of `evaluator-only/`, preventing a node install in the repo from widening the sandbox allowlist to cover the golden.

### V-specific ToolDef
`AUTHORED_RUN_TESTS_TOOLDEF` (code_world.py:285–294) has node-accurate description: "Run your authored JavaScript tests in tests/authored/ with `node --test`…". `CODE_WORLD_TOOLS_V` overrides the shared `run_tests` entry with it. The original pytest-worded ToolDef is untouched for all other consumers.

### Distinct versioned record class
`NodeFeedbackResult` (records/node_feedback.py) is a separate `@dataclass(frozen=True)` with `record="node_feedback"`, `schema_version=1`, and tail-aware `render_feedback_tail()` that keeps the END of the output (node failure summary at tail). Entirely distinct from `ExecutionResult` (oracle's head-truncated record, ADR-0009).

### truncate_output unchanged
`sandboxed_node_edge.py` and `node_feedback.py` do not import or call `truncate_output`. The oracle's truncation is untouched (confirmed by grep — only a docstring reference in node_feedback.py).

### macOS integration tests — RAN AND PASSED (not skipped)
```
tests/runners/test_sandboxed_node_edge.py::test_sandbox_blocks_evaluator_only_read  PASSED
tests/runners/test_sandboxed_node_edge.py::test_sandbox_blocks_network              PASSED
tests/runners/test_sandboxed_node_edge.py::test_sandbox_starts_node_and_runs_benign_authored_test PASSED
```
All 3 ran (not skipped). Total: 22 passed, 0 failed, 0 skipped in test_sandboxed_node_edge.py.

### Full test suite (005 surface)
```
python -m pytest tests/runners/test_sandboxed_node_edge.py tests/runners/test_f_candidate.py \
  tests/runners/test_loop.py tests/tools/test_code_world.py -o addopts="" -rs -q
137 passed, 5 skipped in 0.70s
```
The 5 skips are unrelated `test_f_candidate.py` integration tests gated on a local web-dossier golden store.

## Failures
None. All acceptance criteria met.
