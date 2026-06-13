# Item 003 — F3 Oracle Code Review

**Branch:** `feat/agentic-v1-003-f3-oracle`
**Reviewer:** Claude Sonnet 4.6 (code-review skill, HIGH effort)
**Date:** 2026-06-13
**Suite result:** 799 passed, 0 failed (node v22.22.2 on PATH)

---

## VERDICT: PASS-WITH-NITS

**ZERO Blockers. ONE Latent. FOUR Nits.**

The oracle is structurally sound. The discrimination logic is correct and all four
sentinel cases (golden PASS / base FAIL / mutant FAIL / causal-tamper FAIL) are
exercised by live node execution. The D19 no-leak boundary holds. The suite-status
classifier is correctly implemented for the probe-confirmed semantics. No false-PASS
path was found for the primary oracle path.

---

## Findings

### Latent (1)

**L1 — `ET.ParseError` unhandled in `node_edge.run_node_tests`**

- File: `src/agent_eval_lab/runners/node_edge.py`, line 119–121
- `pytest_edge.py` wraps `_read_cases` in a `try/except ET.ParseError` and returns a
  structured error record. `node_edge.run_node_tests` calls `parse_junit_xml` (line 119)
  with no such guard. If node writes a malformed or partial JUnit XML (e.g., disk-full,
  OS interruption, or a future node regression), `ET.ParseError` (which inherits from
  `SyntaxError`, not `RuntimeError` or `OSError`) propagates past `_verdict_for`'s
  `(RuntimeError, OSError)` catch in `node_oracle_edge.py` and becomes an unhandled
  exception that crashes the grading run.
- This does not fire in normal test execution (node 22's JUnit output is well-formed),
  which is why it is latent rather than a blocker.
- **Fix:** Wrap the `xml_path.read_text` + `parse_junit_xml` call in a try/except
  `ET.ParseError`, mirroring `pytest_edge._xml_parse_error_result`:
  ```python
  try:
      cases = parse_junit_xml(xml_path.read_text(encoding="utf-8")) if xml_path.exists() else ()
  except ET.ParseError as exc:
      cases = ()
      # return an error result analogous to pytest_edge._xml_parse_error_result
  ```
  Also add `import xml.etree.ElementTree as ET` to the imports in `node_edge.py`
  (currently imported only implicitly via `junit.py`). Alternatively, expose a
  `parse_junit_xml_safe` from `junit.py` that returns `()` on parse error and add
  a test in `test_junit.py`.

---

### Nits (4)

**N1 — `NodeExecutionRequest` record is dead code**

- File: `src/agent_eval_lab/records/node_execution.py`
- `NodeExecutionRequest`, `node_execution_request_to_dict`, and
  `node_execution_request_from_dict` are unused by the oracle pipeline.
  `node_oracle_edge.py` calls `run_node_tests(overlaid.files, spec.test_paths, ...)` 
  directly. This record was planned in the architecture table but the implementation
  wires around it. The associated test (`tests/records/test_node_execution.py`) is
  also testing dead surface.
- Impact: none — extra code, no correctness risk.
- Suggestion: Either wire `run_node_tests` to accept `NodeExecutionRequest` (for
  symmetry with `execute_request` in `pytest_edge`) or remove the record and its test.

**N2 — `WDIO_PKG_CONTENT` content inconsistency between `f3_oracle.py` and inline test helpers**

- Files: `src/agent_eval_lab/datasets/f3_oracle.py` line 22 vs
  `tests/runners/test_node_oracle_edge.py` lines 57, 66, 80.
- `WDIO_PKG_CONTENT = '{"type":"module"}\n'` (trailing newline) in `f3_oracle.py`.
  The inline `_f3_allof()` helper in `test_node_oracle_edge.py` uses
  `'{"type":"module"}'` (no trailing newline) for the same file path.
  The two test modules therefore exercise subtly different oracle specs
  (different `held_out_files` content → different `node_execution_hash`).
- Impact: none for item 004 (which uses `build_f3_verification`), but the oracle
  test in `test_node_oracle_edge.py` does not exercise the exact same spec as
  `test_f3_oracle.py`. Both JSON variants are valid and work correctly.
- Suggestion: Import and reuse `WDIO_PKG_CONTENT` from `f3_oracle.py` in
  `test_node_oracle_edge.py` so both test modules exercise the same held-out spec.

**N3 — `canonicalize_node_output` silently adds a colon to the summary duration line**

- File: `src/agent_eval_lab/runners/node_edge.py`, `canonicalize_node_output`
- The summary line from node is `# duration_ms 46.712583` (space, no colon).
  The regex `r"duration_ms:?\s+\d+(?:\.\d+)?"` matches it (`:?` makes colon
  optional) but replaces it with `"duration_ms: <duration>"` (adds a colon).
  So `# duration_ms 46.712583` becomes `# duration_ms: <duration>` in the
  canonical output. This is harmless for determinism (both forms collapse to
  the same token) but is a lossy/inaccurate transformation.
- Impact: none for correctness; the canonical output is deterministic.
- Suggestion: Use two patterns or a format-preserving replacement if output
  fidelity for debugging is valued. Current behavior is explicitly acceptable.

**N4 — `_node_env` calls `_node_bin()` to build the PATH string**

- File: `src/agent_eval_lab/runners/node_edge.py`, `_node_env` function
- `_node_env(root)` calls `_node_bin()` internally to extract the node binary's
  parent dir for the `PATH` env var. `run_node_tests` also calls `_node_bin()` to
  build the command. This is a double-resolution of the same binary on every run.
  On an environment where `shutil.which` is slow or where `NODE_BIN` changes
  between calls (not realistic), this could be surprising.
- Impact: negligible — `shutil.which` is cheap and `NODE_BIN` is stable per process.
- Suggestion: Resolve once and thread the resolved path through:
  `node_bin = _node_bin(); env = _node_env_with_bin(root, node_bin); command = [node_bin, ...]`.

---

## Scrutiny responses (per-checklist)

### 1. Discrimination soundness

**Suite-status classifier:** Correct. `exit_code=0` → `passed`; `exit_code=1` with
≥1 parsed testcase → `failed`; `exit_code=1` with 0 testcases → `error`. This
matches the probe-confirmed node 22 semantics documented in §18.6.

**Import crash / missing ESM marker → ERROR (not PASS):** Confirmed. When node
fails to parse/import the test file, it exits 1 with no `<testcase>` elements in
the JUnit XML (XML not written at all or written empty). `xml_path.exists()` check
returns `()` for the cases tuple; `node_suite_status(1, 0)` → `"error"` → `passed
is False`. This is correct: a candidate whose edit breaks imports does NOT pass.

**False PASS via exit-0 with no XML:** Technically possible if node exits 0 but
the JUnit file is not written (reporter failure). Current code:
`cases = parse_junit_xml(...) if xml_path.exists() else ()` → `node_suite_status(0, 0)`
→ `"passed"`. In practice, node 22 with `--test-reporter=junit
--test-reporter-destination=<file>` always writes the XML before exiting 0. This
risk is accepted by the design (analogous to pytest's exit-0 with no output file).
The golden test file is oracle-controlled and has 35 tests, so this path would
only fire on a reporter bug, not on a candidate cheat.

### 2. Contradiction checks real (§18.6)

Confirmed by probe A in the plan: the mutant that filters `e.status >= 600` (keeps
2xx) fails tests `not ok 6` and `not ok 7` ("no network attachment when all
requests are 2XX" / "network attachment only includes non-2XX entries"). The golden
test file covers both sides of the contradiction. The oracle does not hardcode
fixture counts — it runs the entire 35-test file, which includes the all-2XX→no-attachment
and 503-retained subtests. `test_mutant_surfaces_2xx_fails_f3` confirms the mutant
direction; `test_golden_fix_passes_both_specs` confirms the golden direction.

### 3. D31 causal guard

The `AllOf` has exactly two `NodeExecutionSpec`s. The second (causal) spec
`held_out_files` contains ONLY the ESM marker (`package.json`); all causal test
files (`correlate.test.js`, `signal.test.js`, `compose.test.js`, `index.test.js`)
come from the candidate's `base_tree`. A candidate that tampers with `signal.js`
will run the oracle-unmodified causal tests against their tampered source and fail.
`test_causal_tamper_passes_f3_but_fails_causal_guard` in both
`test_node_oracle_edge.py` and `test_f3_oracle.py` confirm this live.
The causal guard is NOT a no-op: probe B (plan §FEASIBILITY-PROBE) and the live
test both demonstrate it fires on `signal.js` tamper.

### 4. D19 integrity

`build_f3_verification` reads the golden TEST from `evaluator_store /
golden-files/report-to-allure.test.js.golden` and puts it in `held_out_files`.
The golden SOURCE (`report-to-allure.js.golden`) is NEVER read or included.
`F3_SOURCE_REL` (`tests/wdio/utils/failure-analysis/report-to-allure.js`) is
absent from both specs' `held_out_files` — confirmed by the static structure of
`build_f3_verification` and asserted by `test_build_f3_does_not_leak_golden_source_into_held_out`.
This assertion is non-trivial: `F3_SOURCE_REL` and `F3_TEST_REL` are distinct paths.
The golden source is never written into any candidate-visible location.

### 5. `junit.py` extraction / parser parity

The extraction is a pure lift: `parse_junit_xml` and `case_status_of` are identical
in logic to the old `pytest_edge` implementations. `pytest_edge.py` now imports
from `junit.py` and removes the local definitions. The existing `pytest_edge` test
suite passes unchanged (799 tests green). Node's JUnit XML uses the same
`<testcase classname name>` structure as pytest's (probe-confirmed); `.iter("testcase")`
handles both flat and nested `<testsuite>` wrapper shapes.

One asymmetry remains (see L1): `pytest_edge` guards `parse_junit_xml` with a
`try/except ET.ParseError`; `node_edge` does not.

### 6. Sandboxing / subprocess

- **Process group kill:** `start_new_session=True` + `os.killpg` pattern mirrors
  `pytest_edge` ✓
- **Timeout:** `process.communicate(timeout=timeout_s)` → `TimeoutExpired` →
  `_kill_process_group` → `_timeout_result()` ✓
- **Env isolation:** `_node_env` builds from scratch (no `os.environ` inheritance);
  `TZ=UTC`, `LC_ALL=C.UTF-8`, `NO_COLOR=1`, `NODE_OPTIONS=""` ✓
- **Path traversal:** `materialize_tree` (reused from `pytest_edge`) resolves each
  path against `root.resolve()` and checks `is_relative_to(resolved_root)` ✓
- **Reserved names:** `.junit.xml` is in `_HARNESS_RESERVED_ROOTS`; a candidate
  who injects it into `base_tree` gets `RuntimeError` → `NodeExecutionError` →
  not passed ✓
- **Temp dir cleanup:** `finally: shutil.rmtree(root, ignore_errors=True)` ✓
- **No shell injection:** `subprocess.Popen` called with a list (not `shell=True`);
  test_paths are POSIX-relative strings from the frozen spec ✓
- **`_node_env` double-calls `_node_bin()`** (see N4, nit only)

### 7. Silent failures / broad excepts / mutable state / FP adherence

- No broad `except Exception` catches. `(RuntimeError, OSError)` in
  `_verdict_for` is intentional and documented.
- `ET.ParseError` gap is the only silent-failure risk (see L1).
- All new dataclasses use `frozen=True, kw_only=True` ✓
- Pure functions are side-effect free ✓
- No module-level mutable state ✓
- `overlay_node_oracle` returns a new immutable `OverlaidNodeTree`; does not mutate
  `base_tree` ✓
- `{**base_tree, **held_out_files}` (oracle-wins spread) is the correct immutable
  merge ✓
- `grade_node_execution` is pure (no I/O; reads from the precomputed verdicts map) ✓
- CLAUDE.md FP principles adhered to: no `let`/mutation, spread-based builders,
  small focused functions, separated effects at edges ✓

---

## What looks good

- **Architecture clarity:** the three-layer separation (spec → grader → edge) mirrors
  the existing pytest oracle with clean seams. Item 004 calls exactly one function
  (`build_f3_verification`) and gets a wired `AllOf`.
- **`materialize_tree` reuse:** no duplication of the escape/collision logic. The
  oracle imports it from `pytest_edge` with explicit attribution.
- **`prefix_collision` reuse:** `overlay_node_oracle` uses the project's canonical
  predicate from `code_world`, not a private reimplementation.
- **Test discriminability is empirically verified:** all four oracle cases (golden
  PASS, base FAIL, mutant FAIL, causal-tamper FAIL) are live node executions, not
  mocks. The suite runs them on node 22 in 23 seconds.
- **Graceful node-absent degradation:** `pytest.mark.skipif(_NODE is None)` gates
  all subprocess tests; pure-helper tests always run.
- **Content-addressed hashing:** `node_execution_hash` serializes
  `held_out_files + test_paths + base_tree + timeout_s` with `sort_keys=True` —
  deterministic under all Python dict iteration orders.
