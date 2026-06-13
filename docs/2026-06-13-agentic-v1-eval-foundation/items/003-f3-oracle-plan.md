# Item 003 — F3 Oracle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the F3 oracle (§18.6 / §4.1 / D31): a pure, env-free, deterministic `AllOf` grader that runs the staged golden `report-to-allure.test.js` (≥3 non-2XX fixtures + contradiction checks) from the **evaluator store** against a candidate's edited `report-to-allure.js` inside a checked-out web-dossier tree, AND runs the causal/signal tests to confirm the candidate did not regress the `>=500` causal layer — passing on the golden fix, failing on the pre-fix base, failing a "surfaces a 2xx" mutant, and failing a candidate that tampers with `signal.js`/`correlate.js`.

**Architecture:** F3 is the `node --test` analogue of the existing pytest oracle. The Python-pytest pipeline (`ExecutionSpec` → `execution_hash` → `run_pytest`) is bound to pytest semantics and to overlaying held-out tests onto the *agent's* tree, so it is **not** reused verbatim. Instead a **parallel, structurally-mirrored** node pipeline is added: a new `NodeExecutionSpec` schema variant, a `node_edge.py` runner (subprocess `node --test --test-reporter=junit`, scrubbed env, hard timeout, JUnit parse, canonicalization — mirroring `pytest_edge.py`), a `node_oracle_edge.py` precompute boundary, and a `grade_node_execution` interpreter. The pure JUnit-parsing + output-canonicalization helpers shared by both pytest and node are factored into a new `runners/junit.py` so neither edge re-implements them. The candidate's web-dossier tree is supplied by the caller (item 004's repo adapter) as the `base_tree`; the oracle overlays the evaluator-store golden test + dependency files **oracle-wins** over it (D19: the golden test never lives in the candidate tree). The oracle is wired as an `AllOf([NodeExecutionSpec(golden F3 test), NodeExecutionSpec(causal guard tests)])`; the F3 fixtures and all contradiction asserts already live *inside* the staged golden test file — they are NOT re-extracted into separate runs.

**Tech Stack:** Python ≥3.11, frozen `@dataclass(kw_only=True)`, `typing.Literal`, `pytest`, `ruff`; subprocess to `node` v22 (`node --test`). Tests run with `uv run pytest`; lint with `uv run ruff check`. The node binary is resolved from `NODE_BIN` env or PATH at the edge (policy lives at the edge, never in the spec).

---

## Pre-flight context (read before Task 1)

**Baseline:** `uv run pytest` must be green before you start and at every commit. Run it once first to record the count; keep it ≥ that.

**Node prerequisite:** the edge shells out to node v22. On this machine: `export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"` puts `node` v22.22.2 on PATH. The edge resolves the binary via `shutil.which(os.environ.get("NODE_BIN", "node"))`; tests that actually invoke node are marked so they can be skipped where node is absent (see Task 7). **All pure-helper tasks (Tasks 1-5) require no node** and are the bulk of the TDD.

### Evaluator-store artifacts (the oracle reference — already staged, do NOT copy into any candidate tree)

Under `evaluator-only/web-dossier-golden/` (gitignored evaluator store, D19):

- `golden-files/report-to-allure.test.js.golden` — the GOLDEN F3 test (35 `node:test` tests; the +27 lines vs base add the two discriminating non-2XX subtests: `no network attachment when all requests are 2XX`, `network attachment only includes non-2XX entries`). **These ARE the F3 fixtures** (§18.6). It imports `../report-to-allure.js` (candidate-supplied), `../redact.js`, and report-to-allure imports `./failure-analysis.config.js`.
- `golden-files/report-to-allure.js.golden` — the golden FIXED source (`buildNetworkText` filters `e.status < 200 || e.status >= 300`). Used by the oracle's OWN regression tests (Task 7), never shipped to the candidate.
- `meta.json` — `candidate_base_sha = 5b0c13a6bc9e7b9a3c60083da511f3efd0d39505`, `golden_head_sha = ebdfcbea…`, `repo = mstr-kiai/web-dossier`, `base_ref = m2021`. Confirms D31: "correlate.js/signal.js untouched."
- `F-golden.patch`, `golden-files/MANIFEST.txt` — the 5-file golden diff (report-to-allure.js +5/−1 ; its test +27 ; plus LibraryNotification.js / Snapshots_SendBackground.spec.js / wdio.conf.ts which are F1/F2, out of scope here).

### Candidate web-dossier repo (the substrate the oracle runs against)

`~/Documents/Repository/web-dossier` (branch `m2021`). Relevant dir: `tests/wdio/utils/failure-analysis/`. It is self-contained ESM:

- **No `package.json` at the repo root.** The only `package.json` governing ESM resolution for the failure-analysis dir is `tests/wdio/package.json` (`"type": "module"`). A materialized oracle tree MUST therefore carry a `tests/wdio/package.json` containing at least `{"type":"module"}` or the `import` statements fail to resolve. **Probe-confirmed: a minimal `{"type":"module"}` suffices** (no devDeps needed) — inject that, not the 7.3 KB real one.
- The PRE-FIX base source is `git show 5b0c13a6:tests/wdio/utils/failure-analysis/report-to-allure.js` (its `buildNetworkText` is **unfiltered** — dumps every request).
- The causal layer the oracle must protect (D31): `signal.js` (`derive` → emits `backend-error-present`), `correlate.js` (`relevant`, filters network entries at `>=500`), `failure-analysis.config.js` (`serverErrorStatus: 500`). The `backend-error-present` 5xx assertions live across `__tests__/signal.test.js`, `__tests__/correlate.test.js`, `__tests__/compose.test.js`, `__tests__/index.test.js`.

### FEASIBILITY-PROBE EVIDENCE (run by the planner on a temp copy; the real repo was confirmed `git status --porcelain` clean afterwards)

All probes used `node v22.22.2`, a temp dir mirroring `tests/wdio/utils/failure-analysis/…` with `tests/wdio/package.json = {"type":"module"}`.

| # | Tree | Command | Result | Meaning |
|---|---|---|---|---|
| 1 | GOLDEN source + GOLDEN test | `node --test …/report-to-allure.test.js` | **exit 0**, `# pass 35 # fail 0` | Golden fix PASSES. |
| 2 | BASE (`5b0c13a6`) source + GOLDEN test | same | **exit 1**, `# pass 33 # fail 2` — `not ok 6 - no network attachment when all requests are 2XX`, `not ok 7 - network attachment only includes non-2XX entries` | Pre-fix base FAILS on exactly the two non-2XX subtests. **THIS IS THE DISCRIMINATION.** |
| 3a | GOLDEN source + causal tests (`correlate.test.js signal.test.js`) | `node --test …` | exit 0, `# pass 19 # fail 0` | Causal layer green with golden attachment. |
| 3b | BASE source + causal tests | same | exit 0, `# pass 19 # fail 0` | Causal tests are independent of `report-to-allure.js` (D31): green either way. |
| A (mutant) | GOLDEN test + source mutated so filter keeps 2xx (`e.status >= 600`) | `node --test …/report-to-allure.test.js` | **exit 1**, `# fail 3` — incl. `not ok 7 - network attachment only includes non-2XX entries` | "surfaces a 2xx" mutant FAILS. |
| B (causal tamper) | golden attachment fix + `signal.js` renamed `backend-error-present`→`…-BROKEN` | F3 attach test: exit 0 `# fail 0`; causal tests (`correlate signal compose index`): **exit 1 `# fail 3`** | The F3 attachment test ALONE does NOT catch a causal regression — **only the causal-guard ExecutionSpec does.** This is the empirical justification for the AllOf having a second spec. |

**JUnit reporter parity (decisive for reuse):** `node --test --test-reporter=junit --test-reporter-destination=<file>` writes XML whose per-test element is `<testcase name="…" classname="test"><failure type="testCodeFailure" message="…"/></testcase>` — **structurally identical** to pytest's JUnit (`<testcase classname name>` with nested `<failure>`/`<error>`/`<skipped>`). On probe 2 the file held `testcases: 35  failures: 2`. So `pytest_edge.parse_junit_xml` / `_case_status` parse node output unchanged. Node v22.22.2 emits NO experimental/flag warnings on stderr for these reporters.

**node `--test` exit-code semantics (the edge classifier reads these):**

- `0` = all tests passed.
- `1` = at least one test failed, OR the test file is missing (`Could not find '…'` on stderr, no `<testcase>` in XML), OR the candidate source has a syntax/import error (`SyntaxError…` then `error: 'test failed'`, no/partial `<testcase>`).
- There is **no distinct "no tests" code** like pytest's `5`. So the edge classifies: `exit 0` → `passed`; `exit 1` with ≥1 `<testcase>` parsed → `failed`; `exit 1` with `0` `<testcase>` parsed → `error` (missing file / import crash); any other code → `error`.

### Critical reconciliations (decided here — do not re-litigate)

1. **Why a new `NodeExecutionSpec`, not reuse `ExecutionSpec`.** `ExecutionSpec` + `execution_hash` + `precompute_execution_verdicts` are welded to (a) pytest (`run_pytest`, exit codes 0/1/5), and (b) overlaying `held_out_tests` onto `trajectory.final_state["files"]` (the agent's whole tree). F3 needs (a) `node --test`, and (b) overlay onto a caller-supplied **base_tree** (the candidate's checked-out web-dossier sub-tree) where the evaluator's golden test wins — the candidate never holds the golden test (D19). Forcing this through `ExecutionSpec` would either leak the golden test into the candidate world or fork its semantics with flags. A parallel, narrowly-scoped node spec keeps each runner total and readable (CLAUDE.md: small focused modules; one responsibility).

2. **One golden-test ExecutionSpec, NOT three fixture-extracted runs.** §18.6 says "fixtures generated programmatically from the golden PR's test file." The staged golden test file *already is* that artifact — its 35 subtests include all three required fixtures (non-2XX-only / mixed 2XX+503 contradiction / 503-retained) plus the all-2XX→no-attachment and cap cases. Re-extracting them into 3 separate node runs would (a) duplicate the fixtures (drift risk: a fixture edit in the golden test would silently diverge from the oracle), and (b) re-implement assertions the owner already reviewed (D24). The simplest faithful design runs the golden file once. The "≥3 fixtures so a one-fixture hardcode fails" requirement is satisfied *inside* the file (5 network subtests over distinct status mixes), confirmed by probe A: a hardcode that surfaces 2xx fails subtest 7; a hardcode that drops the 503 fails subtest 7's `includes('503')` and subtest "only includes non-2XX". **So the AllOf has exactly two NodeExecutionSpecs: (1) the F3 golden attachment test, (2) the causal-guard tests.**

3. **Causal-guard test set.** Probe B proves the F3 attachment test cannot see a `signal.js` tamper. The guard spec runs `correlate.test.js`, `signal.test.js`, `compose.test.js`, `index.test.js` — every file carrying a `backend-error-present`/5xx-causal assertion (grep-confirmed). It runs them in the SAME materialized tree, so it also exercises the candidate's `signal.js`/`correlate.js`/`config.js`. If a candidate "fixed" F3 by mutating the causal rule (the D31 anti-pattern), this spec fails. The base and golden both pass it (probe 3) — it only fires on a regression.

4. **What the candidate supplies vs what the oracle overlays.** Caller (item 004) passes a `base_tree: Mapping[str,str]` = the candidate's final `tests/wdio/utils/failure-analysis/**` sub-tree (POSIX-relative keys rooted so that `tests/wdio/package.json` is included). The oracle's `held_out_files` (from the evaluator store) overlay **oracle-wins**: the golden `__tests__/report-to-allure.test.js` and a minimal `tests/wdio/package.json`. The candidate's `report-to-allure.js`, `signal.js`, `correlate.js`, etc. are the candidate's own — the oracle does NOT overlay golden source over them (that would mask a broken candidate). Result: oracle controls the *tests* and the *ESM marker*; candidate controls the *source under test*.

5. **Determinism / env-free (§6).** node runs in a from-scratch env (no `os.environ` inheritance, `TZ=UTC`, `LC_ALL=C.UTF-8`), a fresh temp dir resolved once, a hard timeout, output canonicalized (sandbox root → `<sandbox>`, node's `duration_ms: <float>` token → `<duration>`). The grader keys on a content hash of (held-out files + base_tree + timeout) so the same inputs always map to the same precomputed verdict, exactly like `execution_hash`.

### Decisions deferred to impl (genuinely free)

- Local accumulator variable names; the *recorded field names* and *spec field names* are fixed below.
- Whether `canonicalize_node_output`'s duration regex is one combined pattern or two — must collapse both `duration_ms: <float>` and any `# duration_ms <float>` summary line to `<duration>`.
- The exact wording of `detail` strings in error verdicts (must name the discriminator).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/agent_eval_lab/runners/junit.py` | Pure shared JUnit parse (`parse_junit_xml`, `_case_status`) + generic `truncate`-aware helpers, lifted from `pytest_edge` so both edges share one impl | **Create** |
| `src/agent_eval_lab/runners/pytest_edge.py` | Import the shared helpers from `junit.py` instead of defining them locally (no behavior change) | **Modify** |
| `src/agent_eval_lab/records/node_execution.py` | `NodeExecutionRequest` (frozen base_tree + test globs) and reuse of `ExecutionResult` for the record out | **Create** |
| `src/agent_eval_lab/runners/node_edge.py` | EDGE: materialize tree → `node --test --test-reporter=junit` in scrubbed env under timeout → parse JUnit → canonicalize → `ExecutionResult`; pure helpers (`canonicalize_node_output`, `node_suite_status`, `_node_env`) | **Create** |
| `src/agent_eval_lab/tasks/schema.py` | Add `NodeExecutionSpec` variant; extend `VerificationSpec` union | **Modify** |
| `src/agent_eval_lab/graders/node_execution.py` | `NodeExecutionVerdict`, `node_execution_hash`, `collect_node_execution_specs`, `overlay_node_oracle` (oracle-wins over base_tree), `grade_node_execution` (pure, reads precomputed verdict) | **Create** |
| `src/agent_eval_lab/runners/node_oracle_edge.py` | EDGE: collect `NodeExecutionSpec`s, overlay each onto base_tree, run `node_edge`, emit verdict map keyed by `node_execution_hash` | **Create** |
| `src/agent_eval_lab/graders/dispatch.py` | Route `NodeExecutionSpec` → `grade_node_execution` | **Modify** |
| `src/agent_eval_lab/graders/composite.py` | (no change — `grade_all_of` recurses `grade` which now handles the node variant) | — |
| `src/agent_eval_lab/datasets/f3_oracle.py` | Build the F3 `AllOf` task verification from a passed-in evaluator-store path (loads golden test + minimal package.json into `held_out_files`); the single seam item 004 calls | **Create** |
| `tests/runners/test_junit.py` | Shared JUnit parser tests (moved/extended from pytest_edge tests) | **Create** |
| `tests/records/test_node_execution.py` | `NodeExecutionRequest` round-trip / immutability | **Create** |
| `tests/runners/test_node_edge.py` | Pure helpers + (node-marked) integration: golden PASS, base FAIL, missing-file error | **Create** |
| `tests/tasks/test_schema.py` | `NodeExecutionSpec` in the union | **Modify** |
| `tests/graders/test_node_execution.py` | hash determinism, overlay oracle-wins, verdict interpretation, collector recursion | **Create** |
| `tests/runners/test_node_oracle_edge.py` | precompute map; (node-marked) end-to-end golden/base/mutant/causal-tamper discrimination | **Create** |
| `tests/graders/test_dispatch.py` | dispatch routes the node variant | **Modify** |
| `tests/datasets/test_f3_oracle.py` | the assembled AllOf passes on golden, fails on base / mutant / causal-tamper (the headline acceptance test) | **Create** |

---

## Task 1: Factor the shared JUnit parser into `runners/junit.py`

**Files:**
- Create: `src/agent_eval_lab/runners/junit.py`
- Create: `tests/runners/test_junit.py`
- Modify: `src/agent_eval_lab/runners/pytest_edge.py`

Rationale: node's JUnit XML uses the same `<testcase classname name>`/`<failure>`/`<error>`/`<skipped>` shape pytest uses (probe-confirmed). Lift the pure parser so the node edge reuses it verbatim — DRY, and any future fix lands once.

- [ ] **Step 1: Write the failing test**

```python
# tests/runners/test_junit.py
from agent_eval_lab.records.execution import TestCaseResult
from agent_eval_lab.runners.junit import parse_junit_xml, case_status_of

_NODE_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
\t<testcase name="alpha pass" time="0.000688" classname="test"/>
\t<testcase name="beta fail" time="0.000072" classname="test">
\t\t<failure type="testCodeFailure" message="should not include 200"/>
\t</testcase>
</testsuites>
"""

def test_parse_node_junit_sorts_and_maps_statuses() -> None:
    assert parse_junit_xml(_NODE_XML) == (
        TestCaseResult(test_id="test::alpha pass", status="passed"),
        TestCaseResult(test_id="test::beta fail", status="failed"),
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_junit.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.runners.junit`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/runners/junit.py
"""Pure JUnit-XML parsing shared by the pytest and node test edges."""

import xml.etree.ElementTree as ET

from agent_eval_lab.records.execution import TestCaseResult, TestStatus


def case_status_of(case: ET.Element) -> TestStatus:
    if case.find("failure") is not None:
        return "failed"
    if case.find("error") is not None:
        return "error"
    if case.find("skipped") is not None:
        return "skipped"
    return "passed"


def parse_junit_xml(xml_text: str) -> tuple[TestCaseResult, ...]:
    """Extract per-test entries sorted by `classname::name`. Pure."""
    cases = (
        TestCaseResult(
            test_id=f"{case.get('classname', '')}::{case.get('name', '')}",
            status=case_status_of(case),
        )
        for case in ET.fromstring(xml_text).iter("testcase")
    )
    return tuple(sorted(cases, key=lambda case: case.test_id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_junit.py -q`
Expected: PASS.

- [ ] **Step 5: Repoint `pytest_edge` at the shared helper (no behavior change)**

In `src/agent_eval_lab/runners/pytest_edge.py`: delete the local `_case_status` and `parse_junit_xml` definitions; add `from agent_eval_lab.runners.junit import parse_junit_xml`. Internal callers (`_read_cases`) already call `parse_junit_xml` — leave them. The local `_case_status` had no external callers.

- [ ] **Step 6: Run the full suite to verify nothing broke**

Run: `uv run pytest tests/runners/test_pytest_edge.py tests/runners/test_junit.py -q`
Expected: PASS (the pytest_edge tests that imported `parse_junit_xml` still pass; if a test imported `_case_status`, repoint it to `junit.case_status_of`).

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/runners/junit.py tests/runners/test_junit.py src/agent_eval_lab/runners/pytest_edge.py
git commit -m "refactor: share JUnit parser between pytest and node edges"
```

---

## Task 2: `NodeExecutionRequest` record

**Files:**
- Create: `src/agent_eval_lab/records/node_execution.py`
- Create: `tests/records/test_node_execution.py`

The node request carries the **base_tree** (candidate sub-tree, oracle-overlaid before this point) and the **test globs** to run. The result reuses the existing `ExecutionResult` (status/exit_code/counts/tests/stdout/stderr) — no new result type.

- [ ] **Step 1: Write the failing test**

```python
# tests/records/test_node_execution.py
import pytest

from agent_eval_lab.records.node_execution import (
    NodeExecutionRequest,
    node_execution_request_from_dict,
    node_execution_request_to_dict,
)


def test_request_round_trips() -> None:
    req = NodeExecutionRequest(
        files={"tests/wdio/package.json": '{"type":"module"}'},
        test_paths=("tests/wdio/utils/failure-analysis/__tests__/report-to-allure.test.js",),
    )
    assert node_execution_request_from_dict(node_execution_request_to_dict(req)) == req


def test_request_is_frozen() -> None:
    req = NodeExecutionRequest(files={}, test_paths=())
    with pytest.raises(Exception):
        req.files = {"x": "y"}  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/records/test_node_execution.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/records/node_execution.py
"""Effect-request record for node --test execution (mirrors records/execution.py)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, kw_only=True)
class NodeExecutionRequest:
    """Frozen file-tree to run node --test over, plus the test paths to run."""

    files: Mapping[str, str]
    test_paths: tuple[str, ...]


def node_execution_request_to_dict(request: NodeExecutionRequest) -> dict[str, Any]:
    return {"files": dict(request.files), "test_paths": list(request.test_paths)}


def node_execution_request_from_dict(data: Mapping[str, Any]) -> NodeExecutionRequest:
    return NodeExecutionRequest(
        files=dict(data["files"]), test_paths=tuple(data["test_paths"])
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/records/test_node_execution.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/records/node_execution.py tests/records/test_node_execution.py
git commit -m "feat: NodeExecutionRequest effect-request record"
```

---

## Task 3: `node_edge.py` pure helpers — canonicalization + suite-status

**Files:**
- Create: `src/agent_eval_lab/runners/node_edge.py` (helpers only this task)
- Create: `tests/runners/test_node_edge.py` (helper tests this task)

Mirror `pytest_edge`'s pure surface: `canonicalize_node_output` (sandbox root + node duration token), `node_suite_status` (the exit-code + testcase-count classifier from the probe findings).

- [ ] **Step 1: Write the failing test**

```python
# tests/runners/test_node_edge.py
from agent_eval_lab.runners.node_edge import (
    canonicalize_node_output,
    node_suite_status,
)


def test_canonicalize_replaces_root_and_duration() -> None:
    raw = (
        "ok 1 - emits\n  ---\n  duration_ms: 0.04175\n  ...\n"
        "# duration_ms 46.712583\n/private/var/folders/x/agent-eval-node-1/out\n"
    )
    out = canonicalize_node_output(raw, "/private/var/folders/x/agent-eval-node-1")
    assert "0.04175" not in out
    assert "46.712583" not in out
    assert "duration_ms: <duration>" in out
    assert out.endswith("<sandbox>/out\n")


def test_suite_status_passed_when_exit_zero() -> None:
    assert node_suite_status(exit_code=0, testcase_count=35) == "passed"


def test_suite_status_failed_when_exit_one_with_cases() -> None:
    assert node_suite_status(exit_code=1, testcase_count=35) == "failed"


def test_suite_status_error_when_exit_one_no_cases() -> None:
    # missing test file / import crash: exit 1 but zero <testcase> parsed
    assert node_suite_status(exit_code=1, testcase_count=0) == "error"


def test_suite_status_error_on_other_codes() -> None:
    assert node_suite_status(exit_code=2, testcase_count=0) == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_node_edge.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation (helpers only)**

```python
# src/agent_eval_lab/runners/node_edge.py
"""EDGE: sandboxed `node --test` execution boundary (F3 oracle, §18.6).

The node analogue of pytest_edge: materialize a file tree into a fresh temp
dir, run pinned-`node --test` with the JUnit reporter in a scrubbed
from-scratch environment under a hard timeout, parse the JUnit XML (shared
parser), canonicalize output, clean up in a finally. Deterministic, env-free.
"""

import os
import re
import shutil
import signal
import subprocess
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path

from agent_eval_lab.records.execution import (
    ExecutionResult,
    SuiteStatus,
    TestCaseResult,
    truncate_output,
)
from agent_eval_lab.runners.junit import parse_junit_xml
from agent_eval_lab.runners.pytest_edge import (
    SANDBOX_PLACEHOLDER,
    materialize_tree,
)

DEFAULT_TIMEOUT_S = 30.0
_TIMEOUT_EXIT_CODE = -9
# node prints both `  duration_ms: 0.04175` (per-test YAML) and `# duration_ms 46.7` (summary).
_NODE_DURATION = re.compile(r"duration_ms:?\s+\d+(?:\.\d+)?")


def canonicalize_node_output(text: str, root: str) -> str:
    """Replace the sandbox root and node duration tokens. Pure."""
    return _NODE_DURATION.sub("duration_ms: <duration>", text.replace(root, SANDBOX_PLACEHOLDER))


def node_suite_status(*, exit_code: int, testcase_count: int) -> SuiteStatus:
    """Classify a node --test run (probe-derived: no pytest-style code 5).

    0 -> passed; 1 with >=1 parsed testcase -> failed; 1 with zero testcases
    (missing file / import crash) -> error; anything else -> error.
    """
    if exit_code == 0:
        return "passed"
    if exit_code == 1 and testcase_count > 0:
        return "failed"
    return "error"
```

Note: reuse `SANDBOX_PLACEHOLDER` and `materialize_tree` from `pytest_edge` (already total, escape-safe, collision-checked — DRY). If importing `materialize_tree` from `pytest_edge` reads oddly, that is acceptable for v1; a later refactor can move it to a `sandbox.py`. Do NOT duplicate it.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_node_edge.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/node_edge.py tests/runners/test_node_edge.py
git commit -m "feat: node_edge pure helpers (canonicalize + suite status)"
```

---

## Task 4: `node_edge.run_node_tests` — the subprocess integration

**Files:**
- Modify: `src/agent_eval_lab/runners/node_edge.py`
- Modify: `tests/runners/test_node_edge.py`

This step shells out to node. Gate the integration tests behind a node-availability skip so the suite stays green on machines without node.

- [ ] **Step 1: Write the failing test (node-gated)**

```python
# append to tests/runners/test_node_edge.py
import os
import shutil
import pytest

from agent_eval_lab.runners.node_edge import run_node_tests

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
requires_node = pytest.mark.skipif(_NODE is None, reason="node not on PATH")

# Tiny self-contained ESM fixture: one passing node:test, no external imports.
_PASS_TEST = (
    "import test from 'node:test';\n"
    "import assert from 'node:assert/strict';\n"
    "test('one plus one', () => { assert.equal(1 + 1, 2); });\n"
)
_FAIL_TEST = (
    "import test from 'node:test';\n"
    "import assert from 'node:assert/strict';\n"
    "test('always fails', () => { assert.equal(1, 2); });\n"
)


@requires_node
def test_run_node_tests_passes_on_green_suite() -> None:
    res = run_node_tests(
        files={"pkg/package.json": '{"type":"module"}', "pkg/x.test.js": _PASS_TEST},
        test_paths=("pkg/x.test.js",),
    )
    assert res.status == "passed"
    assert res.exit_code == 0
    assert res.passed == 1 and res.failed == 0


@requires_node
def test_run_node_tests_fails_on_red_suite() -> None:
    res = run_node_tests(
        files={"pkg/package.json": '{"type":"module"}', "pkg/x.test.js": _FAIL_TEST},
        test_paths=("pkg/x.test.js",),
    )
    assert res.status == "failed"
    assert res.exit_code == 1
    assert res.failed == 1


@requires_node
def test_run_node_tests_errors_on_missing_file() -> None:
    res = run_node_tests(
        files={"pkg/package.json": '{"type":"module"}'},
        test_paths=("pkg/does-not-exist.test.js",),
    )
    assert res.status == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH" uv run pytest tests/runners/test_node_edge.py -q`
Expected: FAIL — `run_node_tests` not defined (or all three node tests fail/error).

- [ ] **Step 3: Write the integration code**

```python
# append to src/agent_eval_lab/runners/node_edge.py

def _node_bin() -> str:
    resolved = shutil.which(os.environ.get("NODE_BIN", "node"))
    if resolved is None:
        raise RuntimeError("node binary not found (set NODE_BIN or add node to PATH)")
    return resolved


def _node_env(root: str) -> dict[str, str]:
    """From-scratch env: never inherits os.environ (no secrets, no proxies)."""
    return {
        "TZ": "UTC",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "HOME": root,
        "PATH": "/usr/bin:/bin:" + str(Path(_node_bin()).parent),
        "NODE_OPTIONS": "",
        "NO_COLOR": "1",
    }


def _count(cases: tuple[TestCaseResult, ...], status: str) -> int:
    return sum(1 for case in cases if case.status == status)


def _kill_process_group(process: subprocess.Popen) -> None:
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    with suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=2.0)


def _timeout_result() -> ExecutionResult:
    return ExecutionResult(
        status="timeout", exit_code=_TIMEOUT_EXIT_CODE,
        passed=0, failed=0, errors=0, skipped=0, tests=(), stdout="", stderr="",
    )


def run_node_tests(
    files: Mapping[str, str],
    test_paths: tuple[str, ...],
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> ExecutionResult:
    """Run `node --test` over a materialized tree; deterministic record out."""
    root = Path(tempfile.mkdtemp(prefix="agent-eval-node-")).resolve()
    try:
        materialize_tree(files, root)
        xml_path = root / ".junit.xml"
        command = [
            _node_bin(), "--test",
            "--test-reporter=junit", f"--test-reporter-destination={xml_path}",
            *test_paths,
        ]
        process = subprocess.Popen(
            command, cwd=root, env=_node_env(str(root)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            return _timeout_result()
        cases = parse_junit_xml(xml_path.read_text(encoding="utf-8")) if xml_path.exists() else ()
        return ExecutionResult(
            status=node_suite_status(exit_code=process.returncode, testcase_count=len(cases)),
            exit_code=process.returncode,
            passed=_count(cases, "passed"),
            failed=_count(cases, "failed"),
            errors=_count(cases, "error"),
            skipped=_count(cases, "skipped"),
            tests=cases,
            stdout=truncate_output(canonicalize_node_output(
                stdout.decode("utf-8", "replace"), str(root))),
            stderr=truncate_output(canonicalize_node_output(
                stderr.decode("utf-8", "replace"), str(root))),
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH" uv run pytest tests/runners/test_node_edge.py -q`
Expected: PASS (all three node-gated tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/node_edge.py tests/runners/test_node_edge.py
git commit -m "feat: run_node_tests sandboxed node --test integration"
```

---

## Task 5: `NodeExecutionSpec` schema variant

**Files:**
- Modify: `src/agent_eval_lab/tasks/schema.py`
- Modify: `tests/tasks/test_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/tasks/test_schema.py
from agent_eval_lab.tasks.schema import NodeExecutionSpec, VerificationSpec


def test_node_execution_spec_is_a_verification_spec() -> None:
    spec = NodeExecutionSpec(
        held_out_files={"tests/wdio/package.json": '{"type":"module"}'},
        test_paths=("tests/wdio/utils/failure-analysis/__tests__/report-to-allure.test.js",),
    )
    assert isinstance(spec, VerificationSpec)
    assert spec.type == "node_execution"
    assert spec.timeout_s is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tasks/test_schema.py -q`
Expected: FAIL — `ImportError: cannot import name 'NodeExecutionSpec'`.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_eval_lab/tasks/schema.py`, after `ExecutionSpec`:

```python
@dataclass(frozen=True, kw_only=True)
class NodeExecutionSpec:
    """Tier-2 oracle that runs `node --test` over a candidate-supplied base tree
    with evaluator-store test files overlaid oracle-wins (F3, §18.6 / D31).

    `held_out_files` maps POSIX-relative path -> text (the golden test file and
    a minimal `tests/wdio/package.json`); these overlay the caller's base_tree.
    `test_paths` are the POSIX-relative test files passed to `node --test`.
    `timeout_s` None => the node edge's DEFAULT_TIMEOUT_S.
    """

    type: Literal["node_execution"] = "node_execution"
    held_out_files: Mapping[str, str]
    test_paths: tuple[str, ...]
    timeout_s: float | None = None
```

Extend the union:

```python
VerificationSpec = (
    OutputMatchSpec
    | ToolCallMatchSpec
    | FinalStateSpec
    | TrajectorySpec
    | AllOf
    | LlmJudgeSpec
    | ExecutionSpec
    | NodeExecutionSpec
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tasks/test_schema.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/tasks/schema.py tests/tasks/test_schema.py
git commit -m "feat: NodeExecutionSpec verification variant"
```

---

## Task 6: `grade_node_execution` + overlay + hash + collector (pure)

**Files:**
- Create: `src/agent_eval_lab/graders/node_execution.py`
- Create: `tests/graders/test_node_execution.py`

Mirror `graders/execution.py`: `NodeExecutionVerdict`, `node_execution_hash`, `overlay_node_oracle` (oracle-wins over base_tree, reuses `prefix_collision`), `collect_node_execution_specs` (recurses `AllOf`), `grade_node_execution` (reads precomputed verdict; pass == suite status `passed`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/graders/test_node_execution.py
from agent_eval_lab.graders.node_execution import (
    NodeExecutionVerdict,
    collect_node_execution_specs,
    grade_node_execution,
    node_execution_hash,
    overlay_node_oracle,
)
from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec


def _spec(**kw):
    base = dict(
        held_out_files={"tests/wdio/package.json": '{"type":"module"}'},
        test_paths=("a.test.js",),
    )
    base.update(kw)
    return NodeExecutionSpec(**base)


def _traj(base_tree):
    return Trajectory(
        turns=(), usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0, stop_reason="completed", final_state={"files": base_tree},
    )


def test_overlay_is_oracle_wins() -> None:
    base = {"src.js": "candidate", "tests/wdio/package.json": "BASE"}
    held = {"tests/wdio/package.json": '{"type":"module"}', "a.test.js": "T"}
    overlaid = overlay_node_oracle(base, held)
    assert overlaid.files["tests/wdio/package.json"] == '{"type":"module"}'  # oracle wins
    assert overlaid.files["src.js"] == "candidate"  # candidate source preserved
    assert "tests/wdio/package.json" in overlaid.displaced_paths


def test_hash_is_deterministic_and_input_sensitive() -> None:
    s = _spec()
    h1 = node_execution_hash(s, {"src.js": "v1"})
    h2 = node_execution_hash(s, {"src.js": "v1"})
    h3 = node_execution_hash(s, {"src.js": "v2"})
    assert h1 == h2 and h1 != h3


def test_collect_recurses_all_of() -> None:
    a, b = _spec(test_paths=("a.test.js",)), _spec(test_paths=("b.test.js",))
    assert collect_node_execution_specs(AllOf(specs=(a, b))) == (a, b)


def test_grade_reads_passed_verdict() -> None:
    spec, base = _spec(), {"src.js": "v1"}
    key = node_execution_hash(spec, base)
    verdict = NodeExecutionVerdict(
        result=ExecutionResult(status="passed", exit_code=0, passed=1, failed=0,
                               errors=0, skipped=0, tests=(), stdout="", stderr=""),
        execution_hash=key, displaced_paths=(),
    )
    res = grade_node_execution(spec=spec, trajectory=_traj(base), verdicts={key: verdict})
    assert res.passed is True and res.score == 1.0


def test_grade_fails_on_failed_verdict() -> None:
    spec, base = _spec(), {"src.js": "v1"}
    key = node_execution_hash(spec, base)
    verdict = NodeExecutionVerdict(
        result=ExecutionResult(status="failed", exit_code=1, passed=33, failed=2,
                               errors=0, skipped=0, tests=(), stdout="", stderr=""),
        execution_hash=key, displaced_paths=(),
    )
    res = grade_node_execution(spec=spec, trajectory=_traj(base), verdicts={key: verdict})
    assert res.passed is False


def test_grade_non_pass_when_verdict_missing() -> None:
    spec, base = _spec(), {"src.js": "v1"}
    res = grade_node_execution(spec=spec, trajectory=_traj(base), verdicts={})
    assert res.passed is False
    assert res.evidence["execution"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_node_execution.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/graders/node_execution.py
"""Pure node-execution grading core (F3 oracle). Mirrors graders/execution.py.

No I/O, total. The node oracle edge precomputes verdicts keyed by
node_execution_hash; this module only reads them.
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec, VerificationSpec
from agent_eval_lab.tools.code_world import prefix_collision

GRADER_ID = "node_execution"


@dataclass(frozen=True, kw_only=True)
class NodeExecutionVerdict:
    result: ExecutionResult
    execution_hash: str
    displaced_paths: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class OverlaidNodeTree:
    files: Mapping[str, str]
    displaced_paths: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class NodeOverlayCollision:
    pairs: tuple[tuple[str, str], ...]


def overlay_node_oracle(
    base_tree: Mapping[str, str], held_out_files: Mapping[str, str]
) -> OverlaidNodeTree | NodeOverlayCollision:
    """Oracle-wins overlay of held-out files over the candidate base tree."""
    pairs = tuple(
        (base_path, oracle_path)
        for base_path in sorted(base_tree)
        for oracle_path in sorted(held_out_files)
        if prefix_collision(base_path, oracle_path)
    )
    if pairs:
        return NodeOverlayCollision(pairs=pairs)
    displaced = tuple(sorted(set(base_tree) & set(held_out_files)))
    return OverlaidNodeTree(
        files={**base_tree, **held_out_files}, displaced_paths=displaced
    )


def node_execution_hash(spec: NodeExecutionSpec, base_tree: Mapping[str, str]) -> str:
    blob = json.dumps(
        {
            "held_out_files": dict(spec.held_out_files),
            "test_paths": list(spec.test_paths),
            "base_tree": dict(base_tree),
            "timeout_s": spec.timeout_s,
        },
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def collect_node_execution_specs(
    verification: VerificationSpec,
) -> tuple[NodeExecutionSpec, ...]:
    if isinstance(verification, NodeExecutionSpec):
        return (verification,)
    if isinstance(verification, AllOf):
        return tuple(
            spec
            for sub in verification.specs
            for spec in collect_node_execution_specs(sub)
        )
    return ()


def grade_node_execution(
    *, spec: NodeExecutionSpec, trajectory: Trajectory, verdicts: Mapping[str, Any]
) -> GradeResult:
    if trajectory.final_state is None:
        return _non_pass({"execution": "not_run", "reason": "missing_final_state"})
    base_tree = trajectory.final_state.get("files", {})
    key = node_execution_hash(spec, base_tree)
    value = verdicts.get(key)
    if value is None:
        return _non_pass(
            {
                "execution": "error",
                "execution_error": {"kind": "verdict_missing", "execution_hash": key},
                "execution_hash": key,
            }
        )
    if not isinstance(value, NodeExecutionVerdict):
        return _non_pass(
            {
                "execution": "error",
                "execution_error": {
                    "kind": getattr(value, "kind", "unknown"),
                    "detail": getattr(value, "detail", repr(value)),
                },
                "execution_hash": key,
            }
        )
    return _interpret(value)


def _interpret(verdict: NodeExecutionVerdict) -> GradeResult:
    result = verdict.result
    passed = result.status == "passed"
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={
            "execution": "run",
            "status": result.status,
            "exit_code": result.exit_code,
            "counts": {
                "passed": result.passed,
                "failed": result.failed,
                "errors": result.errors,
                "skipped": result.skipped,
            },
            "tests": [[case.test_id, case.status] for case in result.tests],
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_hash": verdict.execution_hash,
            "displaced_paths": list(verdict.displaced_paths),
        },
        failure_reason=None,
    )


def _non_pass(evidence: Mapping[str, Any]) -> GradeResult:
    return GradeResult(
        grader_id=GRADER_ID, passed=False, score=0.0,
        evidence=evidence, failure_reason=None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_node_execution.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/node_execution.py tests/graders/test_node_execution.py
git commit -m "feat: pure node_execution grader (overlay + hash + interpret)"
```

---

## Task 7: `node_oracle_edge.precompute_node_verdicts`

**Files:**
- Create: `src/agent_eval_lab/runners/node_oracle_edge.py`
- Create: `tests/runners/test_node_oracle_edge.py`

Mirror `runners/oracle_edge.py`: collect specs, overlay each onto the trajectory's `final_state["files"]` (the candidate base_tree), run `node_edge.run_node_tests`, emit `{hash: NodeExecutionVerdict | NodeExecutionError}`. Known harness faults (`RuntimeError`, `OSError`) → serializable error at the key; programming errors propagate.

- [ ] **Step 1: Write the failing tests (pure map + node-gated discrimination)**

```python
# tests/runners/test_node_oracle_edge.py
import os
import shutil
from pathlib import Path

import pytest

from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts
from agent_eval_lab.graders.node_execution import (
    NodeExecutionVerdict, node_execution_hash,
)
from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
requires_node = pytest.mark.skipif(_NODE is None, reason="node not on PATH")
_FA = "tests/wdio/utils/failure-analysis"
_REPO = Path.home() / "Documents/Repository/web-dossier"
_EVAL = Path.home() / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden/golden-files"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _base_tree(report_to_allure_src: str) -> dict[str, str]:
    """A candidate base tree: real failure-analysis dir, with report-to-allure.js
    swapped to the given source. Excludes the golden test (oracle overlays it)."""
    tree = {"tests/wdio/package.json": '{"type":"module"}'}
    src_dir = _REPO / _FA
    for path in src_dir.rglob("*.js"):
        rel = f"{_FA}/{path.relative_to(src_dir).as_posix()}"
        # exclude the F3 attachment test (oracle supplies the golden one)
        if rel.endswith("__tests__/report-to-allure.test.js"):
            continue
        tree[rel] = _read(path)
    tree[f"{_FA}/report-to-allure.js"] = report_to_allure_src
    return tree


def _f3_allof() -> AllOf:
    golden_test = _read(_EVAL / "report-to-allure.test.js.golden")
    held = {
        "tests/wdio/package.json": '{"type":"module"}',
        f"{_FA}/__tests__/report-to-allure.test.js": golden_test,
    }
    f3 = NodeExecutionSpec(
        held_out_files=held,
        test_paths=(f"{_FA}/__tests__/report-to-allure.test.js",),
    )
    causal = NodeExecutionSpec(
        held_out_files={"tests/wdio/package.json": '{"type":"module"}'},
        test_paths=tuple(
            f"{_FA}/__tests__/{n}"
            for n in ("correlate.test.js", "signal.test.js",
                      "compose.test.js", "index.test.js")
        ),
    )
    return AllOf(specs=(f3, causal))


def _traj(base_tree):
    return Trajectory(
        turns=(), usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0, stop_reason="completed", final_state={"files": base_tree},
    )


def test_returns_empty_when_no_node_spec() -> None:
    from agent_eval_lab.tasks.schema import OutputMatchSpec
    out = precompute_node_verdicts(
        verification=OutputMatchSpec(expected_output="x"), trajectory=_traj({}))
    assert out == {}


@requires_node
def test_golden_fix_passes_both_specs() -> None:
    allof = _f3_allof()
    golden_src = _read(_EVAL / "report-to-allure.js.golden")
    base = _base_tree(golden_src)
    verdicts = precompute_node_verdicts(verification=allof, trajectory=_traj(base))
    for spec in allof.specs:
        v = verdicts[node_execution_hash(spec, base)]
        assert isinstance(v, NodeExecutionVerdict)
        assert v.result.status == "passed", v.result.stderr


@requires_node
def test_prefix_base_fails_the_f3_spec_but_passes_causal() -> None:
    import subprocess
    allof = _f3_allof()
    base_src = subprocess.run(
        [_NODE, "-e", "process.stdout.write('')"], check=True, capture_output=True
    ) and (Path.home() / "Documents/Repository/web-dossier")
    # get pre-fix source from the pinned base SHA
    base_js = subprocess.run(
        ["git", "-C", str(_REPO), "show",
         "5b0c13a6:tests/wdio/utils/failure-analysis/report-to-allure.js"],
        check=True, capture_output=True, text=True,
    ).stdout
    base = _base_tree(base_js)
    verdicts = precompute_node_verdicts(verification=allof, trajectory=_traj(base))
    f3, causal = allof.specs
    assert verdicts[node_execution_hash(f3, base)].result.status == "failed"
    assert verdicts[node_execution_hash(causal, base)].result.status == "passed"


@requires_node
def test_mutant_surfaces_2xx_fails_f3() -> None:
    allof = _f3_allof()
    golden_src = _read(_EVAL / "report-to-allure.js.golden")
    mutant = golden_src.replace("e.status < 200 || e.status >= 300", "e.status >= 600")
    assert mutant != golden_src
    base = _base_tree(mutant)
    verdicts = precompute_node_verdicts(verification=allof, trajectory=_traj(base))
    f3 = allof.specs[0]
    assert verdicts[node_execution_hash(f3, base)].result.status == "failed"


@requires_node
def test_causal_tamper_passes_f3_but_fails_causal_guard() -> None:
    allof = _f3_allof()
    golden_src = _read(_EVAL / "report-to-allure.js.golden")
    base = _base_tree(golden_src)
    tampered = base[f"{_FA}/signal.js"].replace(
        "backend-error-present", "backend-error-BROKEN")
    assert tampered != base[f"{_FA}/signal.js"]
    base[f"{_FA}/signal.js"] = tampered
    verdicts = precompute_node_verdicts(verification=allof, trajectory=_traj(base))
    f3, causal = allof.specs
    assert verdicts[node_execution_hash(f3, base)].result.status == "passed"
    assert verdicts[node_execution_hash(causal, base)].result.status == "failed"
```

(Trim the stray `subprocess.run([_NODE,...])` no-op in `test_prefix_base_…` to just the git `show` call when implementing — it is shown verbose only to make the SHA extraction explicit.)

- [ ] **Step 2: Run test to verify it fails**

Run: `PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH" uv run pytest tests/runners/test_node_oracle_edge.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/runners/node_oracle_edge.py
"""EDGE: the node oracle precompute boundary (F3, §18.6). Mirrors oracle_edge.py."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from agent_eval_lab.graders.node_execution import (
    NodeExecutionVerdict,
    NodeOverlayCollision,
    collect_node_execution_specs,
    node_execution_hash,
    overlay_node_oracle,
)
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.runners.node_edge import DEFAULT_TIMEOUT_S, run_node_tests
from agent_eval_lab.tasks.schema import NodeExecutionSpec, VerificationSpec


@dataclass(frozen=True, kw_only=True)
class NodeExecutionError:
    kind: Literal["tree_collision", "harness"]
    detail: str
    execution_hash: str


def _collision_detail(collision: NodeOverlayCollision) -> str:
    pairs = ", ".join(
        f"base {b!r} vs oracle {o!r}" for b, o in collision.pairs
    )
    return f"canonical-prefix collision: {pairs}"


def _verdict_for(
    *, spec: NodeExecutionSpec, base_tree: Mapping[str, str], key: str
) -> NodeExecutionVerdict | NodeExecutionError:
    overlaid = overlay_node_oracle(base_tree, spec.held_out_files)
    if isinstance(overlaid, NodeOverlayCollision):
        return NodeExecutionError(
            kind="tree_collision", detail=_collision_detail(overlaid), execution_hash=key
        )
    timeout_s = spec.timeout_s if spec.timeout_s is not None else DEFAULT_TIMEOUT_S
    try:
        result = run_node_tests(overlaid.files, spec.test_paths, timeout_s=timeout_s)
    except (RuntimeError, OSError) as exc:
        return NodeExecutionError(kind="harness", detail=repr(exc), execution_hash=key)
    return NodeExecutionVerdict(
        result=result, execution_hash=key, displaced_paths=overlaid.displaced_paths
    )


def _entry(spec: NodeExecutionSpec, base_tree: Mapping[str, str]):
    key = node_execution_hash(spec, base_tree)
    return key, _verdict_for(spec=spec, base_tree=base_tree, key=key)


def precompute_node_verdicts(
    *, verification: VerificationSpec, trajectory: Trajectory
) -> dict[str, NodeExecutionVerdict | NodeExecutionError]:
    specs = collect_node_execution_specs(verification)
    if not specs or trajectory.final_state is None:
        return {}
    base_tree = trajectory.final_state.get("files", {})
    return dict(_entry(spec, base_tree) for spec in specs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH" uv run pytest tests/runners/test_node_oracle_edge.py -q`
Expected: PASS — `test_returns_empty_when_no_node_spec` always; the four node-gated tests prove golden→pass, base→F3 fail/causal pass, mutant→F3 fail, causal-tamper→F3 pass/causal fail.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/node_oracle_edge.py tests/runners/test_node_oracle_edge.py
git commit -m "feat: node oracle edge precompute (F3 discrimination)"
```

---

## Task 8: Dispatch routing for the node variant

**Files:**
- Modify: `src/agent_eval_lab/graders/dispatch.py`
- Modify: `tests/graders/test_dispatch.py`

`grade_all_of` recurses `grade_trajectory`; once `grade_trajectory` routes `NodeExecutionSpec`, the whole `AllOf` grades.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/graders/test_dispatch.py
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.graders.node_execution import NodeExecutionVerdict, node_execution_hash
from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.tasks.schema import NodeExecutionSpec


def test_dispatch_routes_node_execution_spec() -> None:
    spec = NodeExecutionSpec(held_out_files={}, test_paths=("a.test.js",))
    base = {"src.js": "v"}
    traj = Trajectory(
        turns=(), usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0, stop_reason="completed", final_state={"files": base})
    key = node_execution_hash(spec, base)
    verdict = NodeExecutionVerdict(
        result=ExecutionResult(status="passed", exit_code=0, passed=1, failed=0,
                               errors=0, skipped=0, tests=(), stdout="", stderr=""),
        execution_hash=key, displaced_paths=())
    res = grade_trajectory(
        verification=spec, trajectory=traj, registry={}, verdicts={key: verdict})
    assert res.grader_id == "node_execution" and res.passed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_dispatch.py::test_dispatch_routes_node_execution_spec -q`
Expected: FAIL — `ValueError: unsupported verification spec: NodeExecutionSpec(...)`.

- [ ] **Step 3: Write minimal implementation**

In `dispatch.py`: import `grade_node_execution` and `NodeExecutionSpec`, then add the branch before the `AllOf` branch:

```python
    if isinstance(verification, NodeExecutionSpec):
        return grade_node_execution(
            spec=verification, trajectory=trajectory, verdicts=verdicts
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_dispatch.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/dispatch.py tests/graders/test_dispatch.py
git commit -m "feat: dispatch NodeExecutionSpec to node_execution grader"
```

---

## Task 9: `datasets/f3_oracle.py` — the assembled F3 AllOf (the item-004 seam)

**Files:**
- Create: `src/agent_eval_lab/datasets/f3_oracle.py`
- Create: `tests/datasets/test_f3_oracle.py`

The single function item 004 calls: `build_f3_verification(evaluator_store: Path) -> AllOf`. It reads the golden test from the **passed-in evaluator-store path** (NEVER hard-coded into the candidate tree — D19), assembles `held_out_files` (golden test + minimal `tests/wdio/package.json`) and the causal-guard spec, and returns the `AllOf`. This task's test is the **headline acceptance test**: it builds the real AllOf, runs the precompute against golden/base/mutant/causal-tamper base trees, grades via `grade_trajectory`, and asserts pass/fail.

The F3 path constants live here so item 004 imports one symbol:

```python
FAILURE_ANALYSIS_DIR = "tests/wdio/utils/failure-analysis"
F3_SOURCE_REL = f"{FAILURE_ANALYSIS_DIR}/report-to-allure.js"
F3_TEST_REL = f"{FAILURE_ANALYSIS_DIR}/__tests__/report-to-allure.test.js"
CAUSAL_TEST_RELS = tuple(
    f"{FAILURE_ANALYSIS_DIR}/__tests__/{n}"
    for n in ("correlate.test.js", "signal.test.js", "compose.test.js", "index.test.js")
)
WDIO_PKG_REL = "tests/wdio/package.json"
WDIO_PKG_CONTENT = '{"type":"module"}\n'
```

- [ ] **Step 1: Write the failing test (headline acceptance)**

```python
# tests/datasets/test_f3_oracle.py
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_eval_lab.datasets.f3_oracle import (
    FAILURE_ANALYSIS_DIR, F3_SOURCE_REL, build_f3_verification,
)
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
requires_node = pytest.mark.skipif(_NODE is None, reason="node not on PATH")
_REPO = Path.home() / "Documents/Repository/web-dossier"
_STORE = Path.home() / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden"


def _candidate_base(report_src: str) -> dict[str, str]:
    tree = {"tests/wdio/package.json": '{"type":"module"}'}
    src_dir = _REPO / FAILURE_ANALYSIS_DIR
    for p in src_dir.rglob("*.js"):
        rel = f"{FAILURE_ANALYSIS_DIR}/{p.relative_to(src_dir).as_posix()}"
        if rel.endswith("__tests__/report-to-allure.test.js"):
            continue  # oracle overlays the golden test; candidate never holds it
        tree[rel] = p.read_text(encoding="utf-8")
    tree[F3_SOURCE_REL] = report_src
    return tree


def _grade(verification, base) -> bool:
    traj = Trajectory(
        turns=(), usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0, stop_reason="completed", final_state={"files": base})
    verdicts = precompute_node_verdicts(verification=verification, trajectory=traj)
    return grade_trajectory(
        verification=verification, trajectory=traj, registry={}, verdicts=verdicts
    ).passed


def test_build_f3_does_not_leak_golden_source_into_held_out() -> None:
    v = build_f3_verification(_STORE)
    # the held-out files must contain the golden TEST, never the golden SOURCE
    all_held = {p for spec in v.specs for p in spec.held_out_files}
    assert any(p.endswith("__tests__/report-to-allure.test.js") for p in all_held)
    assert F3_SOURCE_REL not in all_held  # oracle never supplies the source under test


@requires_node
def test_f3_passes_golden_fails_base_mutant_and_causal_tamper() -> None:
    v = build_f3_verification(_STORE)
    golden_src = (_STORE / "golden-files/report-to-allure.js.golden").read_text("utf-8")
    base_src = subprocess.run(
        ["git", "-C", str(_REPO), "show",
         "5b0c13a6:tests/wdio/utils/failure-analysis/report-to-allure.js"],
        check=True, capture_output=True, text=True).stdout
    mutant_src = golden_src.replace("e.status < 200 || e.status >= 300", "e.status >= 600")

    assert _grade(v, _candidate_base(golden_src)) is True       # golden fix PASSES
    assert _grade(v, _candidate_base(base_src)) is False        # pre-fix base FAILS
    assert _grade(v, _candidate_base(mutant_src)) is False      # surfaces-2xx mutant FAILS

    tampered = _candidate_base(golden_src)
    sig = f"{FAILURE_ANALYSIS_DIR}/signal.js"
    tampered[sig] = tampered[sig].replace("backend-error-present", "backend-error-BROKEN")
    assert _grade(v, tampered) is False                          # causal tamper FAILS (D31 guard)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH" uv run pytest tests/datasets/test_f3_oracle.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/datasets/f3_oracle.py
"""Assemble the F3 oracle verification (§18.6 / §4.1 / D31).

build_f3_verification(evaluator_store) returns the AllOf item 004 attaches to
the F3 task. The golden TEST file is read from the evaluator store and shipped
as a held-out oracle file; the golden SOURCE is never included (the candidate's
own report-to-allure.js is the source under test). D19: nothing here writes into
a candidate-visible location.
"""

from pathlib import Path

from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec

FAILURE_ANALYSIS_DIR = "tests/wdio/utils/failure-analysis"
F3_SOURCE_REL = f"{FAILURE_ANALYSIS_DIR}/report-to-allure.js"
F3_TEST_REL = f"{FAILURE_ANALYSIS_DIR}/__tests__/report-to-allure.test.js"
CAUSAL_TEST_RELS = tuple(
    f"{FAILURE_ANALYSIS_DIR}/__tests__/{n}"
    for n in ("correlate.test.js", "signal.test.js", "compose.test.js", "index.test.js")
)
WDIO_PKG_REL = "tests/wdio/package.json"
WDIO_PKG_CONTENT = '{"type":"module"}\n'

_GOLDEN_TEST_REL = "golden-files/report-to-allure.test.js.golden"


def build_f3_verification(evaluator_store: Path) -> AllOf:
    """Return the F3 AllOf: golden attachment test + causal-layer guard."""
    golden_test = (evaluator_store / _GOLDEN_TEST_REL).read_text(encoding="utf-8")
    f3_spec = NodeExecutionSpec(
        held_out_files={
            WDIO_PKG_REL: WDIO_PKG_CONTENT,
            F3_TEST_REL: golden_test,
        },
        test_paths=(F3_TEST_REL,),
    )
    causal_spec = NodeExecutionSpec(
        held_out_files={WDIO_PKG_REL: WDIO_PKG_CONTENT},
        test_paths=CAUSAL_TEST_RELS,
    )
    return AllOf(specs=(f3_spec, causal_spec))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH" uv run pytest tests/datasets/test_f3_oracle.py -q`
Expected: PASS — `test_build_f3_does_not_leak_golden_source_into_held_out` always; the node-gated headline test proves golden→PASS, base→FAIL, mutant→FAIL, causal-tamper→FAIL.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/datasets/f3_oracle.py tests/datasets/test_f3_oracle.py
git commit -m "feat: build_f3_verification — assembled F3 oracle (golden+causal guard)"
```

---

## Task 10: Full-suite green + lint + drift checklist

- [ ] **Step 1: Run the whole suite (with node on PATH so the gated tests actually run)**

Run: `PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH" uv run pytest -q`
Expected: PASS, count ≥ the recorded baseline + the new tests. Confirm NONE of the F3 node tests were skipped (grep the summary for `skipped` — should be the pre-existing skip count only).

- [ ] **Step 2: Run the suite WITHOUT node to confirm graceful skip**

Run: `env -u NODE_BIN PATH="/usr/bin:/bin" uv run pytest tests/runners/test_node_edge.py tests/runners/test_node_oracle_edge.py tests/datasets/test_f3_oracle.py -q`
Expected: the node-gated tests report `skipped` (not failed); pure tests still pass. (This proves the edge degrades cleanly where node is absent.)

- [ ] **Step 3: Lint**

Run: `uv run ruff check src/agent_eval_lab/runners/node_edge.py src/agent_eval_lab/runners/node_oracle_edge.py src/agent_eval_lab/graders/node_execution.py src/agent_eval_lab/runners/junit.py src/agent_eval_lab/records/node_execution.py src/agent_eval_lab/datasets/f3_oracle.py src/agent_eval_lab/tasks/schema.py src/agent_eval_lab/graders/dispatch.py`
Expected: no findings.

- [ ] **Step 4: Confirm the real web-dossier repo and the evaluator store were not mutated**

Run: `git -C "$HOME/Documents/Repository/web-dossier" status --porcelain` → expected EMPTY.
Run: `git -C "$HOME/Documents/Repository/agent-eval-lab" status --porcelain -- evaluator-only/` → expected EMPTY (no golden artifact was edited).

- [ ] **Step 5: Final commit (if any lint fixes were applied)**

```bash
git add -A && git commit -m "chore: F3 oracle — lint + suite green"
```

---

## How the oracle is wired (so item 004's repo adapter can call it)

Item 004 builds the isolated candidate workspace at base SHA `5b0c13a6` and runs the wdio repo task. To grade F3 it does exactly this:

1. **Attach the verification at task-build time:**
   ```python
   from agent_eval_lab.datasets.f3_oracle import build_f3_verification
   verification = build_f3_verification(EVALUATOR_STORE)  # = .../evaluator-only/web-dossier-golden
   ```
   `EVALUATOR_STORE` is the evaluator-only path; it is NEVER written into the candidate workspace (D19). The candidate workspace only ever holds the pre-fix base checkout (D32).

2. **Capture the candidate's edited sub-tree into `trajectory.final_state["files"]`** with POSIX-relative keys rooted so `tests/wdio/package.json` and `tests/wdio/utils/failure-analysis/**` are present (the adapter reads them back from the candidate checkout after the agent finishes). The candidate's `report-to-allure.js` is its own; the candidate's `__tests__/report-to-allure.test.js` (if present) is harmless — the oracle's golden test overlays it oracle-wins.

3. **Precompute the node verdicts then grade** (same two-phase contract as the pytest oracle):
   ```python
   from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts
   from agent_eval_lab.graders.dispatch import grade_trajectory
   verdicts = precompute_node_verdicts(verification=verification, trajectory=traj)
   grade = grade_trajectory(verification=verification, trajectory=traj, registry={}, verdicts=verdicts)
   # grade.passed is the F3 outcome; grade.evidence["sub_results"] carries per-spec detail.
   ```
   The `AllOf` short-circuits to `passed` only when BOTH the golden attachment test AND the causal-guard tests pass — so a candidate that surfaces a 2xx, drops the 503, or tampers with the causal layer all fail.

4. **Pre-registration:** the F3 `NodeExecutionSpec` `held_out_files` + `test_paths` are part of the frozen spec (item 002 `spec_hash`). The node binary, timeout, and env scrub are edge policy and are NOT in the hash — same separation as `pytest_edge`/`execution_hash`.

If item 004 prefers per-domain harness wiring (a dedicated F-domain runner rather than the generic `grade_trajectory`), it still calls `precompute_node_verdicts` + `grade_node_execution` directly; `build_f3_verification` remains the single source of the spec.

---

## Drift checklist (run before declaring done)

- [ ] **Discrimination preserved.** `test_f3_passes_golden_fails_base_mutant_and_causal_tamper` (Task 9) asserts all four cases. If the golden test file is ever re-staged, re-run probes 1+2 by hand and confirm `# pass 35/fail 0` (golden) vs `# pass 33/fail 2` (base) before trusting the suite.
- [ ] **No golden-source leak (D19).** `test_build_f3_does_not_leak_golden_source_into_held_out` asserts `F3_SOURCE_REL` is NOT in any spec's `held_out_files`. The oracle ships only the golden TEST + the ESM marker.
- [ ] **Causal layer guarded (D31).** The `AllOf` includes the causal-guard `NodeExecutionSpec`; `test_causal_tamper_passes_f3_but_fails_causal_guard` proves a `signal.js` tamper fails the overall grade even though the attachment test passes.
- [ ] **ESM resolves.** Every materialized tree carries `tests/wdio/package.json` = `{"type":"module"}`. Without it the imports throw and the run becomes `error`, not `passed`.
- [ ] **Determinism / env-free (§6).** `_node_env` never reads `os.environ` for anything but the resolved node dir; `TZ=UTC`, `LC_ALL=C.UTF-8`, `NO_COLOR=1`. `canonicalize_node_output` strips both duration tokens and the sandbox root. `node_execution_hash` is content-addressed.
- [ ] **Shared parser, not a fork.** `node_edge` imports `parse_junit_xml` from `runners/junit.py`; it does NOT re-implement XML parsing. `pytest_edge` imports from the same module.
- [ ] **`materialize_tree` reused, not duplicated.** `node_edge` imports it (and `SANDBOX_PLACEHOLDER`) from `pytest_edge`. No second copy of the escape/collision logic.
- [ ] **Type consistency.** `NodeExecutionVerdict`, `node_execution_hash`, `overlay_node_oracle`, `collect_node_execution_specs`, `grade_node_execution`, `precompute_node_verdicts`, `run_node_tests`, `build_f3_verification` — names match between definitions, tests, and the wiring section. `held_out_files` (node) vs `held_out_tests` (pytest) are deliberately distinct field names.
- [ ] **Real repo untouched.** `git -C ~/Documents/Repository/web-dossier status --porcelain` is empty after the suite (the oracle reads files; it never writes into the checkout).

---

## Self-review notes

- **§18.6 coverage:** ≥3 fixtures (the golden test's 5 network subtests over distinct status mixes) — Task 9 headline test; contradiction checks (2XX excluded / 503 retained) — inside the golden test, fired by probe A; pure `AllOf` over execution variants — Tasks 6/8/9.
- **§4.1 / D31 coverage:** layer-pinned to `buildNetworkText` (the F3 spec runs only `report-to-allure.test.js`); causal/signal tests unchanged + asserted green (causal-guard spec) — Task 7/9.
- **§6 coverage:** deterministic, env-free — scrubbed env + content-addressed hash + canonicalized output — Tasks 3/4/6.
- **D19 coverage:** golden test/source live in the evaluator store; only the test (never the source) is overlaid oracle-wins; `build_f3_verification` reads from a passed-in store path — Task 9 + the no-leak test.
- **No placeholders:** every code step shows complete code; every run step shows the exact command + expected output.
