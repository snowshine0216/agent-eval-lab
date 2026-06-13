# D-set Harness Implementation Plan (item 005)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the D-set harness — a model browses the live CMC docs via a single `bash` tool driving `playwright-cli` (headless), answers the 15 candidate-visible questions, and L1–L3 answers are graded **deterministically** by an evaluator-only fact-key oracle (required keys present AND forbidden/contradiction keys absent AND a faithfulness gate), with L4–L5 reported alongside via a clearly-marked judge stub.

**Architecture:** Reuse the item-001 censoring loop (`run_single`), the k_valid replacement loop (`run_task_k_valid`), the health-probe validity mask (§18.5), and the effect-request executor seam (`loop._fulfill`). The D-set BASH tool is an **effect-request fulfilled by a stateful subprocess executor** (it runs real `playwright-cli` subprocesses → effect/executor, bounded + sandboxed like `pytest_edge`: per-command timeout, no shell-injection, captured stdout) — but unlike the pytest/node executors it threads a **persistent playwright-cli session** across calls (the browser session is stateful). The fact-key grader is a **new pure `FactKeySpec`** grader added to the verification tagged-union: it reads the candidate's final answer text and a snapshotted page (D36), checks required/forbidden keys + a faithfulness gate. The 15 Task defs are built by a new `datasets/cmc_dset.py` that pairs each candidate-visible question with its evaluator-only fact-key oracle. A `run-dset` CLI path runs a model over the D-set via `run_task_k_valid` with the §18.5 health-probe validity mask, recording rounds/tokens/cost.

**Tech Stack:** Python 3.11 (frozen dataclasses, pure core / I/O edge split), `playwright-cli@0.1.14` (node 22), pytest + hypothesis, httpx. New code under `src/agent_eval_lab/{tools,graders,runners,datasets}/`; tests under `tests/`. Live-network parts gated behind a reachability/playwright skip-guard mirroring `node_supports_junit`.

---

## Feasibility-probe evidence (RAN 2026-06-13, live)

The agent shape was driven end-to-end against the live docs before this plan was written. **It works.**

**Environment:** `export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"` → `playwright-cli --version` = `0.1.14`, `node` = `v22.22.2`. `curl http://<CMC_DOCS_HOST>/docs/24.12/Introduction.html` = **HTTP 200 (0.027s)** — REACHABLE.

**Exact commands driven (Q2 — recommended Kubernetes version, expected `1.34`):**
```bash
SID="dset-probe-$$"
URL="http://<CMC_DOCS_HOST>/docs/24.12/Introduction.html"
playwright-cli -s=$SID open "$URL"
playwright-cli -s=$SID eval "() => document.body.innerText"   # -> 8949 bytes of page text
playwright-cli -s=$SID close
```

**Result:** the `eval "() => document.body.innerText"` call returned the **entire** Introduction page text (8949 bytes). The Support Matrix is inline on this single page; the row `Kubernetes Cluster\t1.34\tReference` is present. **`1.34` was found live.** Total round-trip wall time: **9.66s** (open ~7s incl. browser launch, eval ~2s, close ~0.5s).

**Key structural finding:** ALL 15 questions' source content lives on this **single** Introduction page (Overview, Architecture A/B, the three namespaces, Hybrid Responsibility Model, Deployment Flow Steps 1–6, Support Matrix). **No cross-page navigation is required** for any of the 15 — a single `open` + `eval innerText` (or `snapshot`) is sufficient to ground every fact-key. (Linked sections may be browsed by the model but are not needed for grading.)

**Fact-key contrast validated against the live page** (`grep -F` over the extracted innerText):
- Required keys PRESENT (good): `1.34`, `Managed Redis 7`, `Intelligence Server`, `Strategy Service Portal`, `Istio`, `Calico 3.29`.
- Forbidden/contradiction keys ABSENT (good): `1.32`, `1.33`, `Redis 6`, `Postgres 15`.

**Snapshot+hash (D36) feasible:** `sha256(innerText)` = `380f0306c0bd5e5b0ece6e003544ae3dee8cc294239d0b1e6fd6cfecad6d86f1` — stable, content-hashable at run start. (Hash value is illustrative; the impl computes it fresh at freeze time.)

**Safety-cap implication:** a competent run needs ~3–8 bash calls (open, 1–3 eval/snapshot, optional nav, final answer). The §18.1 `safety_cap=200` is far above this — never binds a reasonable D-set run. Per-command timeout of **60s** comfortably covers the observed ~7s cold browser launch.

---

## Design decisions (recorded before tasks)

### DEC-1 — bash is an ExecutionRequest effect, NOT a pure validation tool

It runs real `playwright-cli` subprocesses, so per ADR-0008 it is an **effect-request fulfilled at the edge** (`loop._fulfill` → executor), recorded as `ToolSuccess`. It is the **ONLY** tool the model gets (§18.10). Rationale: pure tools (workspace) never touch I/O; bash inherently does. This mirrors `pytest_edge`/`node_edge` precedent: from-scratch env, per-command timeout, captured+truncated stdout, no `shell=True`.

### DEC-2 — bash needs a NEW effect-request type `BashRequest` (not `ExecutionRequest`)

`ExecutionRequest` carries `{files}` for a one-shot tree materialization. The bash tool carries a **command string** and is **stateful** (playwright-cli session persists across calls within one run). So:
- New record `BashRequest(command: str)` in `records/bash.py` (frozen, kw_only) with to/from-dict.
- New record `BashResult(stdout, stderr, exit_code, timed_out)` — the deterministic-ish record (wall-clock absent, like `ExecutionResult`); stdout/stderr truncated via the existing `truncate_output`.
- The pure `bash` tool's `apply` returns `(state, BashRequest(command=args["command"]))`. The loop already routes "applied is an ExecutionRequest" → `_fulfill`. **The loop's `_fulfill`/`Executor` type currently narrows to `ExecutionRequest`; widen it to `ExecutionRequest | BashRequest`** (Task 4). The executor for bash is a **stateful closure** built per-run that owns the playwright-cli session id + a temp workdir.

### DEC-3 — fact-key grader is a NEW `FactKeySpec` (existing matchers do not suffice)

No existing matcher checks "required substrings present AND forbidden substrings absent AND a faithfulness gate." `OutputMatchSpec` is exact-equality; `LlmJudgeSpec` is non-deterministic. So a new pure `FactKeySpec` + `grade_fact_key` is required. It is added to the `VerificationSpec` union and the dispatcher.

### DEC-4 — fact-keys are matched against the CANDIDATE'S ANSWER, with a faithfulness gate against the snapshotted PAGE

- **Required keys** must appear in the candidate's final answer (MessageTurn content) → the model actually stated the fact.
- **Forbidden/contradiction keys** must be ABSENT from the candidate's answer → no hallucination of a wrong value (e.g. answering "1.32").
- **Faithfulness gate (L1–L3):** every required key that the candidate asserts must also be present in the **snapshotted page text** (carried in the spec, evaluator-authored from the live page at freeze time, content-hashed per D36). This is the "no hallucination" gate: an answer that names a plausible-but-absent value fails. Implemented as: the spec carries `page_snapshot` (the canonical page text) and `page_snapshot_sha256`; the grader confirms each required key is a substring of `page_snapshot` (authoring-time invariant, re-checked) AND of the answer. Matching is case-insensitive, whitespace-normalized substring (see DEC-5).

### DEC-5 — matching normalization

Keys and answer/page text are normalized before substring matching: lowercase, collapse runs of whitespace to a single space, strip. This makes `Managed Redis 7` match `managed redis 7` and survives the model reformatting tables into prose. Pure helper `_normalize(text) -> str`. No regex in keys (literal substrings only) — keeps the oracle owner-auditable.

### DEC-6 — L4–L5 grading: fact-key floor where feasible + judge stub, clearly marked

Per the spec (§4.2: "for M1 the deterministic fact-key floor is primary; L4–L5 judge is reported alongside") and the prompt's latitude ("scope L4–L5 grading to a judge spec stub that's clearly marked, OR fact-key-grade where feasible — decide and justify"):

**Decision:** L4–L5 are graded with the **same `FactKeySpec` fact-key floor** (required design-component keys present, forbidden contradictions absent) as the deterministic primary, wrapped in an `AllOf` with a **clearly-marked `LlmJudgeSpec` stub** that is reported but NOT the headline. **Justification:** the L4–L5 questions (scenarios/design/critique) still have *checkable anchored facts* — Q11 must mention upgrading K8s to `1.34` and adding a `Service Mesh`; Q15 must name ≥3 of the page's components (`Intelligence Server`, `Database`, `Redis`, `Search Service`, `Platform Analytics`). These are exactly fact-keys. The open-ended *quality* (argument coherence for Q13 SaaS/PaaS/self-hosted) is what the judge stub scores. So every D question gets a deterministic floor; the judge is additive and behind the §6 calibration gate (it is a STUB here — `judge_model="(stub-uncalibrated)"`, never the sole pass/fail). This keeps the M1 headline fully deterministic while honoring the level-tiered design.

### DEC-7 — Task encoding: a Python dataset module, NOT a JSONL file

The candidate-visible dataset already exists as prose at `examples/datasets/cmc-docs-questions.txt` (committed). The machine-readable Task defs are assembled by `datasets/cmc_dset.py::build_cmc_tasks(evaluator_store, page_snapshot)`, mirroring `datasets/f3_oracle.py::build_f3_verification(evaluator_store)`. Rationale: like F3, the verification pulls **evaluator-only** fact-keys from the permission-isolated store (D33) at build time — a JSONL in `examples/datasets/` would have to either embed fact-keys (leak, D19) or reference them, and the F3 precedent is already a build-function, not a JSONL. The 15 questions' *text* is read from the committed `cmc-docs-questions.txt`; the *oracles* are read from `evaluator-only/cmc-docs-factkeys.json`.

### DEC-8 — snapshot+hash (D36) and the page-snapshot lifecycle

Per D36, D-set is `pass^k`-valid only with a snapshot+hash. The evaluator authors `evaluator-only/cmc-docs-snapshot.txt` (the canonical Introduction page innerText) + records its sha256 in the factkeys JSON. At run start the harness (the executor, evaluator-side) re-snapshots the live page and compares the hash; **mismatch → the run is env-invalid** (drops under the validity mask via `validity_fn`, never charged to the model). The candidate never sees the snapshot — it browses live. The `FactKeySpec.page_snapshot` field carries the evaluator's frozen snapshot for the faithfulness gate. For M1 (validity-masked, no committed hash reference yet), the snapshot-hash check is wired but its mismatch routes to the validity mask, exactly as the spec prescribes ("for M1 it runs validity-masked").

---

## File structure (created / modified)

**Create:**
- `src/agent_eval_lab/records/bash.py` — `BashRequest`, `BashResult` + to/from-dict (DEC-2).
- `src/agent_eval_lab/runners/bash_edge.py` — the stateful sandboxed playwright-cli executor (DEC-1/DEC-2): session-threaded subprocess, per-command timeout, env scrub, stdout capture+truncate, session cleanup.
- `src/agent_eval_lab/tools/browse.py` — the pure `bash` `ToolDef` + `apply` returning `BashRequest` (DEC-1).
- `src/agent_eval_lab/graders/fact_key.py` — pure `FactKeySpec` grader (DEC-3/DEC-4/DEC-5).
- `src/agent_eval_lab/datasets/cmc_dset.py` — `build_cmc_tasks(...)` + question/factkey loaders (DEC-7).
- `src/agent_eval_lab/runners/dset_run.py` — `run_dset(...)` wiring `run_task_k_valid` + health probe + per-run bash executor (DEC-8).
- `evaluator-only/cmc-docs-factkeys.json` — the 15-question fact-key oracle (evaluator-only artifact; impl authors all 15 from the answer key).
- `evaluator-only/cmc-docs-snapshot.txt` — the canonical page snapshot for the faithfulness gate + D36 hash.
- Tests: `tests/records/test_bash.py`, `tests/runners/test_bash_edge.py`, `tests/tools/test_browse.py`, `tests/graders/test_fact_key.py`, `tests/datasets/test_cmc_dset.py`, `tests/runners/test_dset_run.py`, `tests/test_dset_no_leak.py`.

**Modify:**
- `src/agent_eval_lab/tasks/schema.py` — add `FactKeySpec`; extend the `VerificationSpec` union.
- `src/agent_eval_lab/graders/dispatch.py` — route `FactKeySpec` → `grade_fact_key`.
- `src/agent_eval_lab/runners/loop.py` — widen `Executor`/`_fulfill` to `ExecutionRequest | BashRequest`.
- `src/agent_eval_lab/records/serialize.py` — `BashResult` round-trip in `outcome_*` is unnecessary (it serializes as a plain dict inside `ToolSuccess.result`); confirm via test only.
- `src/agent_eval_lab/cli.py` — add the `run-dset` subcommand.

---

## Task 1: `BashRequest` / `BashResult` records (DEC-2)

**Files:**
- Create: `src/agent_eval_lab/records/bash.py`
- Test: `tests/records/test_bash.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/records/test_bash.py
from agent_eval_lab.records.bash import (
    BashRequest,
    BashResult,
    bash_request_to_dict,
    bash_request_from_dict,
    bash_result_to_dict,
    bash_result_from_dict,
)


def test_bash_request_roundtrips():
    req = BashRequest(command="playwright-cli -s=S open http://x")
    assert bash_request_from_dict(bash_request_to_dict(req)) == req


def test_bash_result_roundtrips_and_is_frozen():
    res = BashResult(stdout="ok", stderr="", exit_code=0, timed_out=False)
    assert bash_result_from_dict(bash_result_to_dict(res)) == res
    d = bash_result_to_dict(res)
    assert d == {"stdout": "ok", "stderr": "", "exit_code": 0, "timed_out": False}


def test_bash_result_carries_no_wallclock():
    # Determinism: wall-clock is the one nondeterministic observable; it is absent.
    res = BashResult(stdout="", stderr="", exit_code=0, timed_out=False)
    assert "duration" not in bash_result_to_dict(res)
    assert "wall_time_s" not in bash_result_to_dict(res)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/records/test_bash.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.records.bash'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/records/bash.py
"""Effect-request bridge records for the D/B-set bash tool (ADR-0008).

BashRequest is what pure `apply` returns for the single `bash` tool: a command
string, nothing else (timeout, session, and env are edge policy). BashResult is
the deterministic record the bash edge produces; the loop records it as
ToolSuccess.result. Wall-clock duration is deliberately absent (the one
nondeterministic observable); stdout/stderr are truncated, never verbatim.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, kw_only=True)
class BashRequest:
    """Frozen snapshot of one shell command to run; nothing else."""

    command: str


@dataclass(frozen=True, kw_only=True)
class BashResult:
    """Deterministic record of one sandboxed bash command (no wall-clock)."""

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


def bash_request_to_dict(request: BashRequest) -> dict[str, Any]:
    return {"command": request.command}


def bash_request_from_dict(data: Mapping[str, Any]) -> BashRequest:
    return BashRequest(command=data["command"])


def bash_result_to_dict(result: BashResult) -> dict[str, Any]:
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
    }


def bash_result_from_dict(data: Mapping[str, Any]) -> BashResult:
    return BashResult(
        stdout=data["stdout"],
        stderr=data["stderr"],
        exit_code=data["exit_code"],
        timed_out=data["timed_out"],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/records/test_bash.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/records/bash.py tests/records/test_bash.py
git commit -m "feat(records): add BashRequest/BashResult effect-request records (item 005 DEC-2)"
```

---

## Task 2: pure `bash` tool (DEC-1)

**Files:**
- Create: `src/agent_eval_lab/tools/browse.py`
- Test: `tests/tools/test_browse.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_browse.py
from agent_eval_lab.records.bash import BashRequest
from agent_eval_lab.tools.browse import BROWSE_TOOLS, apply_browse
from agent_eval_lab.records.turns import ToolFailure


def test_bash_apply_returns_execution_request():
    state, applied = apply_browse(
        registry=BROWSE_TOOLS,
        name="bash",
        arguments={"command": "playwright-cli -s=S open http://x"},
        state={},
    )
    assert state == {}  # pure: state unchanged (the effect is at the edge)
    assert isinstance(applied, BashRequest)
    assert applied.command == "playwright-cli -s=S open http://x"


def test_bash_schema_rejects_missing_command():
    state, applied = apply_browse(
        registry=BROWSE_TOOLS, name="bash", arguments={}, state={}
    )
    assert isinstance(applied, ToolFailure)
    assert "schema violation" in applied.error


def test_bash_is_the_only_tool():
    # §18.10: a SINGLE bash tool is all the candidate gets.
    assert tuple(BROWSE_TOOLS) == ("bash",)


def test_unknown_tool_is_failure():
    _, applied = apply_browse(
        registry=BROWSE_TOOLS, name="nope", arguments={}, state={}
    )
    assert isinstance(applied, ToolFailure)
    assert "unknown tool" in applied.error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_browse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.tools.browse'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/tools/browse.py
"""browse-world: the single `bash` tool (§18.10) for the D/B-set agent.

The candidate gets exactly one tool — `bash` — and drives playwright-cli (and,
for the B/F sets, repo operations) through it. `apply_browse` is pure: it
validates the command argument against the schema and returns a BashRequest
effect-request (ADR-0008) that the loop fulfils at the bash edge. The pure layer
never runs a subprocess; all I/O lives in runners/bash_edge.py.
"""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.bash import BashRequest
from agent_eval_lab.records.turns import ToolFailure, ToolOutcome
from agent_eval_lab.tools.validation import validate_args
from agent_eval_lab.tools.workspace import ToolDef

BROWSE_TOOLS: Mapping[str, ToolDef] = {
    "bash": ToolDef(
        name="bash",
        description=(
            "Run a single shell command and return its stdout, stderr, and exit "
            "code. Use this to drive playwright-cli (a headless browser) — e.g. "
            "`playwright-cli -s=<session> open <url>`, then "
            "`playwright-cli -s=<session> eval \"() => document.body.innerText\"`. "
            "Reuse the same -s=<session> id across commands to keep one browser "
            "session. Each command has a time limit; output is truncated if large."
        ),
        parameters={
            "type": "object",
            "properties": {"command": {"type": "string", "minLength": 1}},
            "required": ["command"],
            "additionalProperties": False,
        },
    ),
}


def apply_browse(
    *,
    registry: Mapping[str, ToolDef],
    name: str,
    arguments: Mapping[str, Any],
    state: Mapping[str, Any],
) -> tuple[Mapping[str, Any], "BashRequest | ToolOutcome"]:
    """Pure tool application: validate args, return a BashRequest effect-request.

    State is threaded through unchanged (the effect happens at the edge).
    """
    tool = registry.get(name)
    if tool is None:
        return state, ToolFailure(error=f"unknown tool: {name}")
    error = validate_args(tool.parameters, arguments)
    if error is not None:
        return state, ToolFailure(error=f"schema violation: {error}")
    if name == "bash":
        return state, BashRequest(command=arguments["command"])
    raise RuntimeError(
        f"harness misconfiguration: tool {name!r} is registered but has no impl"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_browse.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/tools/browse.py tests/tools/test_browse.py
git commit -m "feat(tools): add the single bash effect-tool for the D/B-set agent (item 005 DEC-1)"
```

---

## Task 3: the sandboxed stateful bash edge (DEC-1/DEC-2)

**Files:**
- Create: `src/agent_eval_lab/runners/bash_edge.py`
- Test: `tests/runners/test_bash_edge.py`

**Sandboxing design (mirrors `pytest_edge`/`node_edge`, adapted for a stateful session):**
- **No shell injection:** the command is parsed with `shlex.split` and run with `subprocess.Popen(argv, shell=False)`. `shell=True` is NEVER used. (The model's "command" is an argv string for one program invocation; pipes/redirects/`;`/`&&` are NOT honored — if the model needs grep, it does it client-side or via `eval`. This is a deliberate constraint: one program per bash call. A command containing shell metacharacters that `shlex` cannot resolve to a runnable argv returns a `BashResult` with `exit_code=127` and an explanatory stderr, never a shell.)
- **Allowlist:** the resolved argv[0] basename must be in `ALLOWED_BINS = {"playwright-cli"}` (extended for B/F sets later). Anything else → `BashResult(exit_code=127, stderr="command not allowed: <bin>")`. This bounds the blast radius — the candidate cannot `cat /etc/passwd` or `curl` an exfil endpoint.
- **PATH pinned to node 22:** the executor injects `PATH` containing the node-22 bin dir (`$HOME/.nvm/versions/node/v22.22.2/bin`) prepended, resolvable via a `_playwright_cli_dir()` helper (env override `PLAYWRIGHT_CLI_DIR`, else the node-22 default). From-scratch env otherwise (no inherited secrets/proxies), like `_node_env`.
- **Per-command timeout:** default **60s** (covers the observed ~7s cold launch with headroom); on timeout, SIGKILL the process group (the `_kill_process_group` pattern) and return `BashResult(timed_out=True, exit_code=-9)`.
- **Session threading:** the executor is a **stateful closure** (`make_bash_executor(session_id, workdir)`) that owns one playwright-cli session id and a temp workdir (`cwd`). Every command runs in that workdir, so playwright-cli's `.playwright-cli/` session artifacts (snapshots/console logs) land in an isolated dir, cleaned up by the caller after the run (`close_bash_executor`).
- **Output capture+truncate:** stdout/stderr decoded utf-8/replace, truncated via `truncate_output` (8 KiB cap), no wall-clock recorded.

- [ ] **Step 1: Write the failing test**

```python
# tests/runners/test_bash_edge.py
import shutil

import pytest

from agent_eval_lab.records.bash import BashRequest, BashResult
from agent_eval_lab.runners.bash_edge import (
    make_bash_executor,
    parse_argv,
    DEFAULT_TIMEOUT_S,
)


def test_parse_argv_rejects_shell_metacharacters():
    # `;`, `|`, `&&` must not be honoured — one program per call.
    assert parse_argv("playwright-cli -s=S open http://x") == [
        "playwright-cli", "-s=S", "open", "http://x"
    ]
    assert parse_argv("playwright-cli x ; rm -rf /") is None  # contains `;`


def test_make_bash_executor_runs_an_allowed_command(tmp_path):
    # `true` is temporarily allowlisted via the env hook so this test needs no
    # network; production ALLOWED_BINS is {"playwright-cli"}.
    executor, close = make_bash_executor(
        session_id="t", workdir=tmp_path, allowed_bins=frozenset({"true"})
    )
    try:
        res = executor(BashRequest(command="true"))
        assert isinstance(res, BashResult)
        assert res.exit_code == 0
        assert res.timed_out is False
    finally:
        close()


def test_disallowed_binary_is_127_never_executed(tmp_path):
    executor, close = make_bash_executor(session_id="t", workdir=tmp_path)
    try:
        res = executor(BashRequest(command="curl http://evil"))
        assert res.exit_code == 127
        assert "not allowed" in res.stderr
    finally:
        close()


def test_unparseable_command_is_127(tmp_path):
    executor, close = make_bash_executor(session_id="t", workdir=tmp_path)
    try:
        res = executor(BashRequest(command="playwright-cli x ; rm -rf /"))
        assert res.exit_code == 127
    finally:
        close()


def test_timeout_kills_and_flags(tmp_path):
    executor, close = make_bash_executor(
        session_id="t", workdir=tmp_path, allowed_bins=frozenset({"sleep"}),
        timeout_s=0.5,
    )
    try:
        res = executor(BashRequest(command="sleep 5"))
        assert res.timed_out is True
        assert res.exit_code == -9
    finally:
        close()


def test_default_timeout_is_generous():
    assert DEFAULT_TIMEOUT_S >= 30.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_bash_edge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.runners.bash_edge'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/runners/bash_edge.py
"""EDGE: the sandboxed, stateful playwright-cli bash boundary (§18.10, ADR-0008).

The single place subprocess I/O happens for the D/B-set agent. Unlike pytest_edge
(one-shot tree per call), the bash edge threads a PERSISTENT playwright-cli
session across calls within one run, so the executor is a stateful closure built
per-run via make_bash_executor(session_id, workdir).

Sandboxing: no shell (shlex.split + Popen(argv, shell=False)); an allowlist of
binaries (default {"playwright-cli"}); a from-scratch env with PATH pinned to the
node-22 bin dir; a per-command timeout with SIGKILL-the-group on expiry; stdout
truncated, wall-clock absent. A command that is unparseable, empty, or whose
argv[0] is not allowlisted returns exit_code 127 WITHOUT spawning a process.
"""

import os
import shlex
import shutil
import signal
import subprocess
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

from agent_eval_lab.records.bash import BashRequest, BashResult
from agent_eval_lab.records.execution import truncate_output

DEFAULT_TIMEOUT_S = 60.0
_TIMEOUT_EXIT_CODE = -9
ALLOWED_BINS = frozenset({"playwright-cli"})
_NODE22_BIN = str(Path.home() / ".nvm/versions/node/v22.22.2/bin")


def _playwright_cli_dir() -> str:
    return os.environ.get("PLAYWRIGHT_CLI_DIR", _NODE22_BIN)


def parse_argv(command: str) -> list[str] | None:
    """shlex.split the command; reject shell metacharacters. Pure.

    Returns the argv list, or None if the command is empty, unparseable, or
    contains a shell control operator (`;`, `|`, `&`, `>`, `<`, backtick, `$(`).
    """
    if any(tok in command for tok in (";", "|", "&", ">", "<", "`", "$(")):
        return None
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    return argv or None


def _bash_env(workdir: str) -> dict[str, str]:
    """From-scratch env: never inherits os.environ; PATH pinned to node-22."""
    return {
        "PATH": _playwright_cli_dir() + ":/usr/bin:/bin",
        "HOME": workdir,
        "TZ": "UTC",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "NO_COLOR": "1",
    }


def _kill_process_group(process: subprocess.Popen) -> None:
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    with suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=2.0)


def _reject(message: str) -> BashResult:
    return BashResult(stdout="", stderr=message, exit_code=127, timed_out=False)


def make_bash_executor(
    *,
    session_id: str,
    workdir: Path,
    allowed_bins: frozenset[str] = ALLOWED_BINS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> tuple[Callable[[BashRequest], BashResult], Callable[[], None]]:
    """Build a stateful bash executor bound to one workdir + session id.

    Returns (executor, close). `close` removes the workdir (and any
    playwright-cli session artifacts under it). The session id is the caller's
    to thread into playwright-cli `-s=` commands (the harness injects it into the
    task prompt); the workdir isolates `.playwright-cli/` artifacts per run.
    """
    workdir.mkdir(parents=True, exist_ok=True)

    def executor(request: BashRequest) -> BashResult:
        argv = parse_argv(request.command)
        if argv is None:
            return _reject("unparseable or shell-metacharacter command rejected")
        binname = Path(argv[0]).name
        if binname not in allowed_bins:
            return _reject(f"command not allowed: {binname}")
        resolved = shutil.which(argv[0], path=_bash_env(str(workdir))["PATH"])
        if resolved is None:
            return _reject(f"binary not found on pinned PATH: {argv[0]}")
        process = subprocess.Popen(
            [resolved, *argv[1:]],
            cwd=str(workdir),
            env=_bash_env(str(workdir)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            out, err = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            return BashResult(
                stdout="", stderr="", exit_code=_TIMEOUT_EXIT_CODE, timed_out=True
            )
        return BashResult(
            stdout=truncate_output(out.decode("utf-8", "replace")),
            stderr=truncate_output(err.decode("utf-8", "replace")),
            exit_code=process.returncode,
            timed_out=False,
        )

    def close() -> None:
        shutil.rmtree(workdir, ignore_errors=True)

    return executor, close
```

> Note: the test's `make_bash_executor(session_id=...)` is keyword-only. Update the two non-`tmp_path` test calls to use `session_id=` / `workdir=` keywords (already shown). The `allowed_bins`/`timeout_s` overrides exist solely so the edge is testable without the network.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_bash_edge.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/bash_edge.py tests/runners/test_bash_edge.py
git commit -m "feat(runners): add sandboxed stateful playwright-cli bash edge (item 005 DEC-1)"
```

---

## Task 4: widen the loop executor to accept `BashRequest` (DEC-2)

**Files:**
- Modify: `src/agent_eval_lab/runners/loop.py:43-54` (the `Executor` type + `_fulfill`)
- Test: `tests/runners/test_loop_effects.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/runners/test_loop_effects.py
from agent_eval_lab.records.bash import BashRequest, BashResult, bash_result_to_dict
from agent_eval_lab.runners.loop import _fulfill


def test_fulfill_routes_a_bash_request():
    def executor(req):
        assert isinstance(req, BashRequest)
        return BashResult(stdout="hi", stderr="", exit_code=0, timed_out=False)

    out = _fulfill(BashRequest(command="playwright-cli -s=S open http://x"), executor)
    # A fulfilled effect-request is always ToolSuccess (ADR-0008); the result is
    # the serialized BashResult dict.
    assert out.result == bash_result_to_dict(
        BashResult(stdout="hi", stderr="", exit_code=0, timed_out=False)
    )
```

> The executor here returns a `BashResult`, whose `to_dict` differs from `execution_result_to_dict`. `_fulfill` currently hardcodes `execution_result_to_dict(executor(request))`. The fix: `_fulfill` must serialize whichever result type the executor returns. Make the executor return an already-serializable mapping is over-engineering; instead, `_fulfill` dispatches on the result type.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_loop_effects.py::test_fulfill_routes_a_bash_request -v`
Expected: FAIL — `_fulfill` passes a `BashResult` to `execution_result_to_dict`, raising `AttributeError`/wrong dict.

- [ ] **Step 3: Write minimal implementation**

Edit `src/agent_eval_lab/runners/loop.py`. Update the imports and the `Executor` type + `_fulfill`:

```python
# imports (add):
from agent_eval_lab.records.bash import BashRequest, BashResult, bash_result_to_dict
from agent_eval_lab.records.execution import (
    ExecutionRequest,
    ExecutionResult,
    execution_result_to_dict,
)

# type aliases (replace):
Effect = ExecutionRequest | BashRequest
ApplyFn = Callable[..., tuple[Mapping[str, Any], "ToolOutcome | Effect"]]
Executor = Callable[[Effect], "ExecutionResult | BashResult"]


def _serialize_effect_result(result: "ExecutionResult | BashResult") -> dict:
    if isinstance(result, BashResult):
        return bash_result_to_dict(result)
    return execution_result_to_dict(result)


def _fulfill(request: Effect, executor: Executor | None) -> ToolSuccess:
    """Fulfill an effect-request at the edge; always ToolSuccess (ADR-0008)."""
    if executor is None:
        raise RuntimeError(
            "harness misconfiguration: apply returned an effect-request but "
            "no executor is configured"
        )
    return ToolSuccess(result=_serialize_effect_result(executor(request)))
```

Then in `run_single`, the branch `isinstance(applied, ExecutionRequest)` must become `isinstance(applied, (ExecutionRequest, BashRequest))`:

```python
            outcome = (
                _fulfill(applied, executor)
                if isinstance(applied, (ExecutionRequest, BashRequest))
                else applied
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_loop_effects.py tests/runners/test_loop.py -v`
Expected: PASS (existing pytest-effect tests still green; the new bash test green).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/loop.py tests/runners/test_loop_effects.py
git commit -m "feat(runners): widen the loop executor seam to BashRequest effects (item 005 DEC-2)"
```

---

## Task 5: `FactKeySpec` schema type (DEC-3)

**Files:**
- Modify: `src/agent_eval_lab/tasks/schema.py` (add `FactKeySpec`; extend the union)
- Test: `tests/tasks/test_schema.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/tasks/test_schema.py
from agent_eval_lab.tasks.schema import FactKeySpec, VerificationSpec


def test_fact_key_spec_is_frozen_and_in_union():
    spec = FactKeySpec(
        required=("1.34",),
        forbidden=("1.32", "1.33"),
        page_snapshot="... Kubernetes Cluster 1.34 ...",
        page_snapshot_sha256="abc123",
        level=2,
    )
    assert spec.required == ("1.34",)
    assert spec.forbidden == ("1.32", "1.33")
    assert spec.level == 2
    # the union accepts it (a FactKeySpec is a VerificationSpec)
    v: VerificationSpec = spec
    assert v.type == "fact_key"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tasks/test_schema.py::test_fact_key_spec_is_frozen_and_in_union -v`
Expected: FAIL — `ImportError: cannot import name 'FactKeySpec'`.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_eval_lab/tasks/schema.py`, add after `LlmJudgeSpec`:

```python
@dataclass(frozen=True, kw_only=True)
class FactKeySpec:
    """Deterministic D-set L1-L3 oracle (§4.2 / D18 / D24).

    required: literal substrings that MUST appear in the candidate's answer AND
      in page_snapshot (the faithfulness gate: a stated fact must be on the page).
    forbidden: contradiction substrings that must be ABSENT from the answer
      (e.g. a wrong version number = a hallucination).
    page_snapshot: the evaluator-frozen page text the answer is graded against
      (D36 snapshot); page_snapshot_sha256 records its content hash.
    level: the question's level (1-5); informs reporting, not the pass rule.

    Matching is case-insensitive, whitespace-normalized literal substring
    (graders/fact_key.py). No regex — keys stay owner-auditable.
    """

    type: Literal["fact_key"] = "fact_key"
    required: tuple[str, ...]
    forbidden: tuple[str, ...]
    page_snapshot: str
    page_snapshot_sha256: str
    level: int
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
    | FactKeySpec
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tasks/test_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/tasks/schema.py tests/tasks/test_schema.py
git commit -m "feat(schema): add FactKeySpec to the verification union (item 005 DEC-3)"
```

---

## Task 6: the pure fact-key grader (DEC-3/DEC-4/DEC-5)

**Files:**
- Create: `src/agent_eval_lab/graders/fact_key.py`
- Test: `tests/graders/test_fact_key.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/graders/test_fact_key.py
from agent_eval_lab.graders.fact_key import grade_fact_key, _normalize
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import FactKeySpec

_PAGE = "Kubernetes Cluster   1.34   Reference. Managed Redis 7."


def _answer(text: str) -> Trajectory:
    return Trajectory(
        turns=(
            MessageTurn(role="user", content="q"),
            MessageTurn(role="assistant", content=text),
        ),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed_natural",
    )


def _spec(required, forbidden):
    return FactKeySpec(
        required=required, forbidden=forbidden,
        page_snapshot=_PAGE, page_snapshot_sha256="x", level=1,
    )


def test_normalize_collapses_whitespace_and_casefolds():
    assert _normalize("Managed   Redis\n7") == "managed redis 7"


def test_pass_when_required_present_and_forbidden_absent():
    g = grade_fact_key(
        spec=_spec(required=("1.34",), forbidden=("1.32", "1.33")),
        trajectory=_answer("The recommended Kubernetes version is 1.34."),
    )
    assert g.passed is True
    assert g.score == 1.0


def test_fail_when_required_missing():
    g = grade_fact_key(
        spec=_spec(required=("1.34",), forbidden=()),
        trajectory=_answer("The recommended version is whatever."),
    )
    assert g.passed is False
    assert "1.34" in g.evidence["missing_required"]


def test_fail_when_forbidden_present_hallucination():
    g = grade_fact_key(
        spec=_spec(required=("1.34",), forbidden=("1.32",)),
        trajectory=_answer("The recommended version is 1.32, not 1.34."),
    )
    assert g.passed is False
    assert "1.32" in g.evidence["present_forbidden"]


def test_faithfulness_gate_required_key_absent_from_page_is_authoring_error():
    # A required key the evaluator put in the spec but that is NOT on the page is
    # an authoring fault, surfaced as a non-pass with a clear evidence flag (the
    # grader never silently passes an off-page assertion).
    g = grade_fact_key(
        spec=_spec(required=("9.99",), forbidden=()),
        trajectory=_answer("The version is 9.99."),
    )
    assert g.passed is False
    assert "9.99" in g.evidence["required_not_on_page"]


def test_case_insensitive_and_whitespace_tolerant_match():
    g = grade_fact_key(
        spec=_spec(required=("Managed Redis 7",), forbidden=()),
        trajectory=_answer("strategy manages a   managed redis 7   cluster"),
    )
    assert g.passed is True


def test_no_assistant_message_is_non_pass():
    traj = Trajectory(
        turns=(MessageTurn(role="user", content="q"),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0, stop_reason="completed_natural",
    )
    g = grade_fact_key(spec=_spec(required=("1.34",), forbidden=()), trajectory=traj)
    assert g.passed is False
    assert g.evidence["error"] == "no assistant message in trajectory"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_fact_key.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.graders.fact_key'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/graders/fact_key.py
"""Pure D-set fact-key grading (§4.2 / D18 / D24).

A deterministic L1-L3 oracle: the candidate's final answer must contain every
required key, must contain no forbidden/contradiction key, and every required
key must also be on the evaluator-frozen page snapshot (the faithfulness gate —
no hallucinating off-page facts). Matching is case-insensitive, whitespace-
normalized, literal substring. No I/O, total.
"""

import re
from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import FactKeySpec

GRADER_ID = "fact_key"
_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace + strip. Pure."""
    return _WS.sub(" ", text).strip().casefold()


def _final_answer(trajectory: Trajectory) -> str | None:
    return next(
        (
            t.content
            for t in reversed(trajectory.turns)
            if isinstance(t, MessageTurn) and t.role == "assistant"
        ),
        None,
    )


def _non_pass(evidence: Mapping[str, Any]) -> GradeResult:
    return GradeResult(
        grader_id=GRADER_ID, passed=False, score=0.0,
        evidence=evidence, failure_reason=None,
    )


def grade_fact_key(*, spec: FactKeySpec, trajectory: Trajectory) -> GradeResult:
    answer = _final_answer(trajectory)
    if answer is None:
        return _non_pass({"error": "no assistant message in trajectory"})

    page = _normalize(spec.page_snapshot)
    ans = _normalize(answer)

    # Faithfulness/authoring gate: every required key must be ON the page.
    required_not_on_page = [k for k in spec.required if _normalize(k) not in page]
    # Required keys the candidate failed to state.
    missing_required = [k for k in spec.required if _normalize(k) not in ans]
    # Forbidden/contradiction keys the candidate stated (hallucination).
    present_forbidden = [k for k in spec.forbidden if _normalize(k) in ans]

    passed = (
        not required_not_on_page and not missing_required and not present_forbidden
    )
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={
            "level": spec.level,
            "required_not_on_page": required_not_on_page,
            "missing_required": missing_required,
            "present_forbidden": present_forbidden,
            "page_snapshot_sha256": spec.page_snapshot_sha256,
        },
        failure_reason=None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_fact_key.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/fact_key.py tests/graders/test_fact_key.py
git commit -m "feat(graders): add pure fact-key grader with faithfulness gate (item 005 DEC-4)"
```

---

## Task 7: dispatch `FactKeySpec` → `grade_fact_key`

**Files:**
- Modify: `src/agent_eval_lab/graders/dispatch.py`
- Test: `tests/graders/test_dispatch.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/graders/test_dispatch.py
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import FactKeySpec


def test_dispatch_routes_fact_key_spec():
    spec = FactKeySpec(
        required=("1.34",), forbidden=(), page_snapshot="v 1.34",
        page_snapshot_sha256="x", level=1,
    )
    traj = Trajectory(
        turns=(
            MessageTurn(role="user", content="q"),
            MessageTurn(role="assistant", content="the version is 1.34"),
        ),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0, stop_reason="completed_natural",
    )
    g = grade_trajectory(verification=spec, trajectory=traj, registry={})
    assert g.grader_id == "fact_key"
    assert g.passed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_dispatch.py::test_dispatch_routes_fact_key_spec -v`
Expected: FAIL — `ValueError: unsupported verification spec: FactKeySpec(...)`.

- [ ] **Step 3: Write minimal implementation**

In `src/agent_eval_lab/graders/dispatch.py`: import and route.

```python
from agent_eval_lab.graders.fact_key import grade_fact_key
from agent_eval_lab.tasks.schema import (  # add FactKeySpec to the existing import
    ...,
    FactKeySpec,
)
```

Add a branch in `grade_trajectory` (before the `AllOf` branch is fine):

```python
    if isinstance(verification, FactKeySpec):
        return grade_fact_key(spec=verification, trajectory=trajectory)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_dispatch.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/dispatch.py tests/graders/test_dispatch.py
git commit -m "feat(graders): dispatch FactKeySpec to the fact-key grader (item 005)"
```

---

## Task 8: author the evaluator-only fact-key oracle (all 15 questions)

**Files:**
- Create: `evaluator-only/cmc-docs-factkeys.json`
- Create: `evaluator-only/cmc-docs-snapshot.txt`
- Test: `tests/datasets/test_cmc_dset.py` (the schema/coverage test added in Task 9 validates this file)

> This task produces the evaluator-only artifact. The impl agent authors all 15 entries by reading `evaluator-only/cmc-docs-answers.txt` (the answer key) and confirming each required key is a substring of the snapshot. The schema + 3 worked exemplars are below; the impl completes the remaining 12 by the same recipe. The file lives under `/evaluator-only/` (gitignored, permission-isolated, D33) — NEVER under `examples/`.

**Schema** (`evaluator-only/cmc-docs-factkeys.json`):

```json
{
  "snapshot_file": "cmc-docs-snapshot.txt",
  "snapshot_sha256": "<sha256 of cmc-docs-snapshot.txt computed at authoring time>",
  "source_url": "http://<CMC_DOCS_HOST>/docs/24.12/Introduction.html",
  "questions": [
    {
      "id": "cmc-q01", "level": 1,
      "required": ["container-based", "your own cloud"],
      "forbidden": ["fully managed SaaS", "Strategy hosts"]
    },
    {
      "id": "cmc-q02", "level": 1,
      "required": ["1.34"],
      "forbidden": ["1.32", "1.33", "1.30", "1.28"]
    },
    {
      "id": "cmc-q03", "level": 1,
      "required": ["Strategy Managed Infrastructure", "Customer Managed Infrastructure"],
      "forbidden": []
    }
  ]
}
```

> **Authoring recipe for the impl (apply to all 15):**
> 1. Generate `evaluator-only/cmc-docs-snapshot.txt` from the live page (the probe command in the feasibility section: `playwright-cli ... eval "() => document.body.innerText"`), strip the playwright-cli result wrapper, keep the raw innerText. Record its sha256 in `snapshot_sha256`.
> 2. For each question, read the matching numbered answer in `evaluator-only/cmc-docs-answers.txt`.
> 3. **required**: pick the 1–4 literal substrings that pin the answer (a version number, a component name, a responsibility-owner phrase). EVERY required key MUST be a substring of the snapshot (run the faithfulness-gate check — the Task-6 grader's `required_not_on_page` must be empty for the golden answer).
> 4. **forbidden**: pick contradiction substrings — the *wrong* values a confused model would emit (e.g. Q2: other K8s versions; Q11: `Redis 6` when the page says `Managed Redis 7`). All forbidden keys MUST be ABSENT from the snapshot (a forbidden key that is on the page is a mis-authored contradiction — Task 9 asserts this).
> 5. **Level tagging**: Q1–3 = L1, Q4–6 = L2, Q7–9 = L3, Q10–12 = L4, Q13–15 = L5. L1–L3 are the deterministic headline; L4–L5 keys form the deterministic floor under the judge stub (DEC-6).

**Worked exemplars (grounded in the live page + answer key):**
- **cmc-q02 (L1, K8s version):** required `["1.34"]`; forbidden `["1.32","1.33","1.30","1.28"]`. (Probe-validated: `1.34` present, `1.32`/`1.33` absent.)
- **cmc-q06 (L2, mandatory vs optional prereqs):** required `["Load Balancer","Cert Manager","Service Mesh","Database","Redis","Search Service"]`; forbidden `[]` (the question asks to *separate* mandatory from optional — both groups' names are required).
- **cmc-q11 (L4, upgrade path from 1.32/Redis 6/no mesh):** required `["1.34","Managed Redis 7","Service Mesh"]`; forbidden `["1.32 is supported","Redis 6 is supported"]` (the model must say to upgrade, not that the old versions are fine).

- [ ] **Step 1: Generate the snapshot artifact**

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
SID="factkey-author"
URL="http://<CMC_DOCS_HOST>/docs/24.12/Introduction.html"
playwright-cli -s=$SID open "$URL" >/dev/null
playwright-cli -s=$SID eval "() => document.body.innerText" > /tmp/raw.txt
playwright-cli -s=$SID close >/dev/null
# strip the playwright-cli "### Result" wrapper, keep raw innerText:
python3 - <<'PY'
import re, pathlib
raw = pathlib.Path("/tmp/raw.txt").read_text()
# the innerText is the JSON-ish quoted block after "### Result"
m = re.search(r'### Result\s*\n"(.*)"\s*\n### Ran', raw, re.S)
text = (m.group(1) if m else raw).encode().decode("unicode_escape")
pathlib.Path("evaluator-only/cmc-docs-snapshot.txt").write_text(text)
import hashlib
print(hashlib.sha256(text.encode()).hexdigest())
PY
```

- [ ] **Step 2: Author all 15 fact-key entries** into `evaluator-only/cmc-docs-factkeys.json` per the recipe, pasting the sha256 from Step 1 into `snapshot_sha256`.

- [ ] **Step 3: Verify the artifact is gitignored and not staged**

Run: `git check-ignore evaluator-only/cmc-docs-factkeys.json evaluator-only/cmc-docs-snapshot.txt`
Expected: both paths echoed (they ARE ignored — `/evaluator-only/` rule). Then `git status --porcelain | grep evaluator-only` → no output.

- [ ] **Step 4: Commit** (only the plan/test scaffolding — the evaluator-only files are intentionally NOT committed, D33)

```bash
# NOTHING under evaluator-only/ is committed. This step is a no-op commit guard:
git status --porcelain  # confirm no evaluator-only/* staged
```

---

## Task 9: the D-set dataset module (DEC-7)

**Files:**
- Create: `src/agent_eval_lab/datasets/cmc_dset.py`
- Test: `tests/datasets/test_cmc_dset.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/datasets/test_cmc_dset.py
import hashlib
import json
from pathlib import Path

import pytest

from agent_eval_lab.datasets.cmc_dset import (
    CMC_SOURCE_URL,
    build_cmc_tasks,
    load_questions,
)
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import AllOf, FactKeySpec

_QUESTIONS = Path("examples/datasets/cmc-docs-questions.txt")
_STORE = Path("evaluator-only")

requires_store = pytest.mark.skipif(
    not (_STORE / "cmc-docs-factkeys.json").exists(),
    reason="evaluator-only fact-key store not present (offline / candidate checkout)",
)


def test_load_questions_returns_15_nonempty():
    qs = load_questions(_QUESTIONS)
    assert len(qs) == 15
    assert all(q.strip() for q in qs)


@requires_store
def test_build_cmc_tasks_makes_15_domain_D_tasks():
    tasks = build_cmc_tasks(evaluator_store=_STORE, questions_path=_QUESTIONS)
    assert len(tasks) == 15
    for t in tasks:
        assert t.capability == "docs_qa"
        assert t.input.available_tools == ("bash",)
        # the question text is in the user turn; the URL is in the system turn
        assert any(
            CMC_SOURCE_URL in m.content
            for m in t.input.messages if isinstance(m, MessageTurn)
        )


@requires_store
def test_l1_l3_tasks_are_factkey_l4_l5_are_allof_with_judge_stub():
    tasks = build_cmc_tasks(evaluator_store=_STORE, questions_path=_QUESTIONS)
    for t in tasks:
        level = int(t.id.split("-q")[1])  # cmc-q07 -> 7
        if level <= 9:  # L1-L3 (questions 1-9)
            assert isinstance(t.verification, FactKeySpec)
        else:           # L4-L5 (questions 10-15)
            assert isinstance(t.verification, AllOf)


@requires_store
def test_every_factkey_required_is_on_the_snapshot():
    # The authoring faithfulness invariant: no required key is off-page, and no
    # forbidden key is on-page (a mis-authored contradiction).
    data = json.loads((_STORE / "cmc-docs-factkeys.json").read_text())
    snap = (_STORE / data["snapshot_file"]).read_text()
    assert hashlib.sha256(snap.encode()).hexdigest() == data["snapshot_sha256"]
    low = " ".join(snap.lower().split())
    for q in data["questions"]:
        for k in q["required"]:
            assert " ".join(k.lower().split()) in low, f"{q['id']} required off-page: {k}"
        for k in q["forbidden"]:
            assert " ".join(k.lower().split()) not in low, f"{q['id']} forbidden on-page: {k}"


@requires_store
def test_golden_answers_pass_their_own_factkey_oracle():
    # Round-trip: the owner answer-key text grades PASS against its fact-keys
    # (so the oracle is not impossibly strict). Answers come from the eval store.
    answers = _load_answer_key(_STORE / "cmc-docs-answers.txt")  # helper in test
    tasks = build_cmc_tasks(evaluator_store=_STORE, questions_path=_QUESTIONS)
    for t in tasks:
        if not isinstance(t.verification, FactKeySpec):
            continue
        ans = answers[t.id]
        traj = Trajectory(
            turns=(MessageTurn(role="assistant", content=ans),),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=0, stop_reason="completed_natural",
        )
        g = grade_trajectory(verification=t.verification, trajectory=traj, registry={})
        assert g.passed, f"{t.id} golden answer failed its own oracle: {g.evidence}"
```

> The `_load_answer_key` helper (test-local) parses `evaluator-only/cmc-docs-answers.txt` into `{cmc-qNN: answer_text}` by the numbered-list structure. Keep it in the test file.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/datasets/test_cmc_dset.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.datasets.cmc_dset'` (the `load_questions` test fails first).

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/datasets/cmc_dset.py
"""Assemble the 15 D-set Tasks (§4.2): each candidate-visible CMC question paired
with its evaluator-only fact-key oracle.

Mirrors datasets/f3_oracle.py: the candidate-visible QUESTION text is read from
the committed examples/datasets/cmc-docs-questions.txt; the ORACLE (fact-keys +
page snapshot) is read from the permission-isolated evaluator store (D19/D33).
Nothing here writes a fact-key into a candidate-visible location.

L1-L3 (questions 1-9) -> a FactKeySpec (deterministic headline).
L4-L5 (questions 10-15) -> an AllOf(FactKeySpec floor, LlmJudgeSpec STUB) — the
fact-key floor is deterministic; the judge stub is reported, never the headline
(DEC-6 / §4.2 / §6). The stub is clearly marked judge_model="(stub-uncalibrated)".
"""

import json
import re
from pathlib import Path

from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import (
    AllOf,
    FactKeySpec,
    LlmJudgeSpec,
    Task,
    TaskInput,
    TaskMetadata,
)

CMC_SOURCE_URL = "http://<CMC_DOCS_HOST>/docs/24.12/Introduction.html"
_FACTKEYS_REL = "cmc-docs-factkeys.json"

_SYSTEM = (
    "You are answering documentation questions about Strategy Customer Managed "
    "Cloud (CMC). You have a single tool: `bash`. Use it to drive a headless "
    "browser via playwright-cli. Start a session and open the docs, e.g.:\n"
    f"  playwright-cli -s=$SESSION open {CMC_SOURCE_URL}\n"
    "  playwright-cli -s=$SESSION eval \"() => document.body.innerText\"\n"
    "Reuse the same -s=$SESSION id across commands. Read the page, then answer "
    "the question using ONLY information found in the documentation. Give your "
    "final answer as a plain-text message (no tool call)."
)


def load_questions(path: Path) -> tuple[str, ...]:
    """Parse the 15 numbered questions from the candidate-visible questions file.

    Questions are top-level numbered items `N. ...`; sub-bullets and level
    headers are folded into the preceding question's text.
    """
    text = path.read_text(encoding="utf-8")
    # Split on lines that start a top-level numbered question: "1. ", "2. ", ...
    parts = re.split(r"(?m)^\s*(\d+)\.\s", text)
    # parts = [preamble, "1", q1, "2", q2, ...]
    questions: list[str] = []
    for i in range(1, len(parts), 2):
        body = parts[i + 1].strip()
        # stop the body at the next Level header if one bled in
        body = re.split(r"(?m)^\s*Level \d", body)[0].strip()
        questions.append(body)
    if len(questions) != 15:
        raise ValueError(f"expected 15 questions, parsed {len(questions)}")
    return tuple(questions)


def _factkey_spec(entry: dict, snapshot: str, sha: str) -> FactKeySpec:
    return FactKeySpec(
        required=tuple(entry["required"]),
        forbidden=tuple(entry["forbidden"]),
        page_snapshot=snapshot,
        page_snapshot_sha256=sha,
        level=entry["level"],
    )


def _judge_stub(level: int) -> LlmJudgeSpec:
    return LlmJudgeSpec(
        rubric=(
            "Score 1-5 the quality of this CMC documentation answer: coverage of "
            "the relevant page sections, internal consistency, and whether claims "
            "are grounded in the docs. (UNCALIBRATED STUB — reported only.)"
        ),
        judge_model="(stub-uncalibrated)",
        scale=(1, 5),
    )


def build_cmc_tasks(*, evaluator_store: Path, questions_path: Path) -> tuple[Task, ...]:
    questions = load_questions(questions_path)
    data = json.loads((evaluator_store / _FACTKEYS_REL).read_text(encoding="utf-8"))
    snapshot = (evaluator_store / data["snapshot_file"]).read_text(encoding="utf-8")
    sha = data["snapshot_sha256"]
    entries = data["questions"]
    if len(entries) != 15:
        raise ValueError(f"expected 15 fact-key entries, got {len(entries)}")

    tasks: list[Task] = []
    for n, (question, entry) in enumerate(zip(questions, entries), start=1):
        floor = _factkey_spec(entry, snapshot, sha)
        verification = (
            floor if n <= 9 else AllOf(specs=(floor, _judge_stub(entry["level"])))
        )
        tasks.append(
            Task(
                id=f"cmc-q{n:02d}",
                capability="docs_qa",
                input=TaskInput(
                    messages=(
                        MessageTurn(role="system", content=_SYSTEM),
                        MessageTurn(role="user", content=question),
                    ),
                    available_tools=("bash",),
                ),
                verification=verification,
                metadata=TaskMetadata(
                    split="held_out",
                    version="cmc-dset-v1",
                    provenance="examples/datasets/cmc-docs-questions.txt",
                    difficulty_knob=f"L{entry['level']}",
                ),
            )
        )
    return tuple(tasks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/datasets/test_cmc_dset.py -v`
Expected: PASS where the store exists; `requires_store` tests SKIP on a candidate checkout (no leak). `test_load_questions_returns_15_nonempty` always runs (questions are committed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/datasets/cmc_dset.py tests/datasets/test_cmc_dset.py
git commit -m "feat(datasets): build the 15 D-set tasks from questions + eval-only fact-keys (item 005 DEC-7)"
```

---

## Task 10: the `run_dset` wiring (DEC-8)

**Files:**
- Create: `src/agent_eval_lab/runners/dset_run.py`
- Test: `tests/runners/test_dset_run.py`

This wires the D-set into `run_task_k_valid` with a per-task bash executor + the §18.5 health probe (validity mask), recording rounds/tokens/cost. The snapshot-hash check (D36) is the `validity_fn`: if the live page hash at run start differs from `page_snapshot_sha256`, the run is invalid (env, not model).

- [ ] **Step 1: Write the failing test**

```python
# tests/runners/test_dset_run.py
from pathlib import Path

import httpx
import pytest

from agent_eval_lab.runners.dset_run import (
    run_dset,
    make_snapshot_validity_fn,
)
from agent_eval_lab.records.bash import BashResult
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn


def _run(stop_reason="completed_natural", sha="match"):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="1.34"),),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0, stop_reason=stop_reason,
    )
    return RunResult(
        task_id="cmc-q02", condition_id="c", run_index=0, trajectory=traj,
        grade=GradeResult(grader_id="fact_key", passed=True, score=1.0,
                          evidence={"page_snapshot_sha256": sha}, failure_reason=None),
    )


def test_snapshot_validity_fn_marks_hash_mismatch_invalid():
    # The validity_fn is satisfied iff the run's recorded page hash matches the
    # reference (D36): a mismatch -> invalid (env), excluded from pass^k.
    validity_fn = make_snapshot_validity_fn(reference_sha256="match")
    assert validity_fn(_run(sha="match")) is True
    assert validity_fn(_run(sha="DIFFERENT")) is False


def test_run_dset_threads_k_valid_and_records(monkeypatch, tmp_path):
    # Stub run_task_k_valid so this is a pure-wiring test (no provider/network).
    from agent_eval_lab.runners import dset_run

    captured = {}

    def fake_k_valid(**kwargs):
        captured.update(kwargs)
        from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
        r = _run()
        return ReplacementOutcome(
            valid_runs=(r,) * kwargs["k_valid"],
            attempts=(TrialAttempt(attempt_index=0, valid=True, run=r),),
            void=False,
        )

    monkeypatch.setattr(dset_run, "run_task_k_valid", fake_k_valid)

    outcomes = run_dset(
        evaluator_store=tmp_path,  # an empty store is fine: tasks are injected
        tasks=(_make_q02_task(tmp_path),),
        config=_fake_config(),
        http_client=httpx.Client(),
        k_valid=5,
        max_invalid_rate=0.40,
        temperature=0.0,
        max_tokens=4096,
        health_probe_fn=lambda: None,  # tolerated by the stub
    )
    assert captured["k_valid"] == 5
    assert "executor" in captured  # a bash executor was threaded
    assert "validity_fn" in captured  # the snapshot-hash validity_fn was threaded
    assert len(outcomes) == 1
```

> `_make_q02_task` and `_fake_config` are test-local builders (a `FactKeySpec` task with `available_tools=("bash",)` and a dummy `ProviderConfig`). The key assertions: `run_dset` passes `k_valid`, an `executor`, and a `validity_fn` into `run_task_k_valid`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_dset_run.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.runners.dset_run'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_eval_lab/runners/dset_run.py
"""EDGE: run a model over the D-set via the k_valid replacement loop (§4.2 / D34).

Each task runs under run_task_k_valid with: a per-task stateful bash executor
(one playwright-cli session + isolated workdir per task), the §18.5 health-probe
validity mask, and a snapshot-hash validity_fn (D36 — a live-page hash mismatch
at run start marks the run env-invalid, excluded from pass^k). Records carry
rounds/tokens/cost via the unchanged Trajectory fields (item 001).
"""

from collections.abc import Callable, Mapping
from pathlib import Path

import httpx

from agent_eval_lab.records.env_health import EnvHealth
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.runners.bash_edge import make_bash_executor
from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.runners.multi_run import ReplacementOutcome, run_task_k_valid
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.browse import BROWSE_TOOLS, apply_browse


def make_snapshot_validity_fn(*, reference_sha256: str) -> Callable[[RunResult], bool]:
    """A run is valid iff its recorded page-snapshot hash matches the reference
    (D36). The hash is recorded in the fact-key grade evidence; a mismatch means
    the live docs drifted from the frozen snapshot -> env-invalid, not model."""

    def validity_fn(run: RunResult) -> bool:
        recorded = run.grade.evidence.get("page_snapshot_sha256")
        return recorded == reference_sha256

    return validity_fn


def run_dset(
    *,
    evaluator_store: Path,
    tasks: tuple[Task, ...],
    config: ProviderConfig,
    http_client: httpx.Client,
    k_valid: int,
    max_invalid_rate: float,
    temperature: float,
    max_tokens: int,
    health_probe_fn: "Callable[[], EnvHealth] | None" = None,
    reference_sha256: str | None = None,
) -> tuple[ReplacementOutcome, ...]:
    """Run every D-set task k_valid times; return one ReplacementOutcome per task.

    A fresh bash executor (isolated session + workdir) is built per task and
    closed after; the snapshot-hash validity_fn (when reference_sha256 is given)
    routes live-docs drift to the validity mask.
    """
    condition = condition_id(config)
    validity_fn = (
        make_snapshot_validity_fn(reference_sha256=reference_sha256)
        if reference_sha256 is not None
        else None
    )
    outcomes: list[ReplacementOutcome] = []
    for task in tasks:
        workdir = evaluator_store / "dset-work" / f"{condition_id_slug(condition)}__{task.id}"
        executor, close = make_bash_executor(session_id=task.id, workdir=workdir)
        try:
            outcome = run_task_k_valid(
                task=task,
                registry=BROWSE_TOOLS,
                config=config,
                http_client=http_client,
                k_valid=k_valid,
                max_invalid_rate=max_invalid_rate,
                max_steps=0,  # unused: the censoring safety cap governs
                temperature=temperature,
                max_tokens=max_tokens,
                validity_fn=validity_fn,
                health_probe_fn=health_probe_fn,
                apply_fn=apply_browse,
                executor=executor,
            )
        finally:
            close()
        outcomes.append(outcome)
    return tuple(outcomes)


def condition_id_slug(condition: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9._-]+", "-", condition)
```

> Note one subtlety: `run_task_k_valid` builds a NEW `run_uid` per attempt and reuses the SAME `executor` across the k attempts of one task. Because playwright-cli's session is keyed by `-s=<session_id>` and the prompt tells the model to use `$SESSION`, sequential attempts share the browser session unless the model picks distinct ids. For the D-set this is benign (read-only browsing). If per-attempt isolation is later required, build the executor inside a per-attempt callback — out of scope for M1 (documented limitation).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_dset_run.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/dset_run.py tests/runners/test_dset_run.py
git commit -m "feat(runners): wire run_dset over k_valid with snapshot-hash validity mask (item 005 DEC-8)"
```

---

## Task 11: the `run-dset` CLI subcommand

**Files:**
- Modify: `src/agent_eval_lab/cli.py`
- Test: `tests/test_cli.py` (extend) / `tests/experiments/test_cli_experiments.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_cli.py
from agent_eval_lab.cli import _build_parser


def test_run_dset_subcommand_parses():
    parser = _build_parser()
    args = parser.parse_args([
        "run-dset",
        "--provider", "deepseek",
        "--evaluator-config", "evaluator.toml",
        "--out", "reports",
    ])
    assert args.command == "run-dset"
    assert args.provider == "deepseek"
    assert args.evaluator_config == Path("evaluator.toml")
```

> A network-touching end-to-end CLI run is NOT unit-tested (it needs a provider + live docs). The handler reuses `load_evaluator_config` (for store path + k_valid + max_invalid_rate + the health probe) and `run_dset`. The handler is covered by the parser test + the `run_dset` wiring test (Task 10); a manual smoke command is in the drift checklist.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_run_dset_subcommand_parses -v`
Expected: FAIL — `argument command: invalid choice: 'run-dset'`.

- [ ] **Step 3: Write minimal implementation**

In `_build_parser`, add the subparser:

```python
    rd = subparsers.add_parser(
        "run-dset", help="run a model over the D-set (CMC docs) via playwright-cli"
    )
    rd.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    rd.add_argument("--model", help="override the provider's default model id")
    rd.add_argument("--evaluator-config", required=True, type=Path, metavar="TOML")
    rd.add_argument("--out", type=Path, default=Path("reports"))
    rd.add_argument("--temperature", type=float, default=0.0)
    rd.add_argument("--max-tokens", type=int, default=4096)
```

Add the dispatch in `main` (before the baseline fallthrough):

```python
    if args.command == "run-dset":
        return _run_dset_command(args, http_client)
```

And the handler (reuses `load_evaluator_config`, `health_probe`, `run_dset`, streams `runs-<slug>.jsonl` exactly like `run_baseline`):

```python
def _run_dset_command(args, http_client):
    from agent_eval_lab.datasets.cmc_dset import build_cmc_tasks
    from agent_eval_lab.runners.dset_run import run_dset
    from agent_eval_lab.runners.config import condition_id

    cfg = load_evaluator_config(args.evaluator_config)
    store = Path(cfg.store.path)
    config = PROVIDERS[args.provider]
    if args.model:
        config = replace(config, model_id=args.model)
    factkeys = json.loads((store / "cmc-docs-factkeys.json").read_text())
    tasks = build_cmc_tasks(
        evaluator_store=store,
        questions_path=Path("examples/datasets/cmc-docs-questions.txt"),
    )
    client = http_client or httpx.Client(
        timeout=120.0, trust_env=False, proxy=resolve_proxy(config, os.environ)
    )

    def health_probe_fn():
        from agent_eval_lab.records.env_health import EnvHealth
        hp = cfg.health_probe
        probe_client = httpx.Client(timeout=10.0, verify=False)
        try:
            r = health_probe(hp.url, hp.username, hp.password, client=probe_client)
        finally:
            probe_client.close()
        return EnvHealth(
            pre_healthy=r.healthy, post_healthy=r.healthy,
            pre_status=r.status_code, post_status=r.status_code,
        )

    try:
        outcomes = run_dset(
            evaluator_store=store, tasks=tasks, config=config, http_client=client,
            k_valid=cfg.runner.k_valid, max_invalid_rate=cfg.runner.max_invalid_rate,
            temperature=args.temperature, max_tokens=args.max_tokens,
            health_probe_fn=health_probe_fn,
            reference_sha256=factkeys["snapshot_sha256"],
        )
    finally:
        if http_client is None:
            client.close()
    args.out.mkdir(parents=True, exist_ok=True)
    slug = _slug(condition_id(config))
    path = args.out / f"runs-dset-{slug}.jsonl"
    with path.open("w") as fh:
        for outcome in outcomes:
            _append_runs(fh, outcome.valid_runs)
    print(path)
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/test_cli.py
git commit -m "feat(cli): add run-dset subcommand (item 005)"
```

---

## Task 12: the no-leak integrity check (D19)

**Files:**
- Create: `tests/test_dset_no_leak.py`

This is the D19 integrity gate: the candidate sees ONLY the question + the bash tool. Fact-keys, the answer key, and the snapshot must be ABSENT from the candidate prompt and the tool surface.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dset_no_leak.py
import json
from pathlib import Path

import pytest

from agent_eval_lab.datasets.cmc_dset import build_cmc_tasks
from agent_eval_lab.tools.browse import BROWSE_TOOLS

_STORE = Path("evaluator-only")
_QUESTIONS = Path("examples/datasets/cmc-docs-questions.txt")

requires_store = pytest.mark.skipif(
    not (_STORE / "cmc-docs-factkeys.json").exists(),
    reason="evaluator-only store absent (candidate checkout / offline)",
)


@requires_store
def test_no_factkey_appears_in_any_candidate_prompt():
    data = json.loads((_STORE / "cmc-docs-factkeys.json").read_text())
    tasks = build_cmc_tasks(evaluator_store=_STORE, questions_path=_QUESTIONS)
    # the candidate-visible surface = every message turn's content
    surface = "\n".join(
        m.content for t in tasks for m in t.input.messages
    ).lower()
    for q in data["questions"]:
        # forbidden keys (wrong answers) and required keys (right answers) are
        # BOTH evaluator-only; neither may appear in the candidate prompt.
        for key in (*q["required"], *q["forbidden"]):
            # allow generic terms that legitimately appear in the question text
            # by asserting the SPECIFIC answer tokens are absent. The fact-keys
            # are authored to be answer-specific (e.g. "1.34"), so this holds.
            assert key.lower() not in surface, f"LEAK: {q['id']} key {key!r} in prompt"


@requires_store
def test_answer_key_text_not_in_candidate_prompt():
    answers = (_STORE / "cmc-docs-answers.txt").read_text().lower()
    tasks = build_cmc_tasks(evaluator_store=_STORE, questions_path=_QUESTIONS)
    surface = "\n".join(m.content for t in tasks for m in t.input.messages).lower()
    # a distinctive answer-only phrase must not be in the prompt
    assert "managed redis 7" not in surface
    assert "calico 3.29" not in surface


def test_bash_tool_surface_exposes_no_answer():
    # the only tool is bash; its description must not name a snapshot/answer path
    desc = BROWSE_TOOLS["bash"].description.lower()
    assert "evaluator-only" not in desc
    assert "factkey" not in desc
    assert "answer" not in desc


def test_evaluator_store_is_gitignored():
    # D33: the store is gitignored (commit guard); permission-isolation is an
    # ops concern, but the commit guard is testable here.
    import subprocess
    out = subprocess.run(
        ["git", "check-ignore", "evaluator-only/cmc-docs-factkeys.json"],
        capture_output=True, text=True,
    )
    assert out.returncode == 0  # the path IS ignored
```

> The first test's premise: fact-keys are answer-specific tokens (version numbers, component names) that, by construction, do NOT appear in the candidate-visible question text. If the impl finds a fact-key that legitimately overlaps a question word (e.g. a key `"Redis"` when Q15 mentions "Redis"), tighten the key to the answer-specific form (`"Managed Redis 7"`) — the test failure is the signal to author better keys. This is a feature, not a flake.

- [ ] **Step 2: Run test to verify it fails (or passes immediately if keys are clean)**

Run: `uv run pytest tests/test_dset_no_leak.py -v`
Expected: `test_bash_tool_surface_exposes_no_answer` + `test_evaluator_store_is_gitignored` PASS immediately; the `requires_store` tests PASS once Task 8 authored answer-specific keys (or FAIL loudly if a key leaks — the signal to retighten).

- [ ] **Step 3: (only if a leak fails)** retighten the offending fact-key in `evaluator-only/cmc-docs-factkeys.json` to its answer-specific form, re-run.

- [ ] **Step 4: Commit**

```bash
git add tests/test_dset_no_leak.py
git commit -m "test(dset): D19 no-leak gate — fact-keys/answers absent from candidate surface (item 005)"
```

---

## Task 13: full-suite green + drift sweep

- [ ] **Step 1: Run the whole suite**

Run: `uv run pytest -q`
Expected: all green; the live/store-dependent tests SKIP cleanly offline (the `requires_store` / node guards).

- [ ] **Step 2: Lint**

Run: `uv run ruff check src/ tests/`
Expected: clean.

- [ ] **Step 3: Manual live smoke (network-gated, run by the owner where reachable)**

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
uv run python -m agent_eval_lab.cli check-env --evaluator-config evaluator.toml
uv run python -m agent_eval_lab.cli run-dset --provider deepseek \
  --evaluator-config evaluator.toml --out reports
# inspect reports/runs-dset-deepseek-*.jsonl: each cmc-qNN run records rounds,
# usage.prompt_tokens/completion_tokens, stop_reason, and a fact_key grade.
```

- [ ] **Step 4: Commit any drift fixes**

```bash
git add -A && git commit -m "chore(dset): suite green + ruff clean (item 005)"
```

---

## Drift checklist (run before declaring done)

- [ ] **§4.2 grading model honored:** L1–L3 graded by required-present AND forbidden-absent AND faithfulness gate (Task 6); L4–L5 = `AllOf(FactKeySpec floor, judge stub)` with the stub clearly marked and never the headline (Task 9, DEC-6).
- [ ] **§18.10 agent shape:** a SINGLE `bash` tool (`BROWSE_TOOLS == ("bash",)`, Task 2); it is the only `available_tools` entry on every D task (Task 9).
- [ ] **§18.5 health probe + validity mask:** `run_dset` threads `health_probe_fn`; an env-unhealthy run is invalid via the existing `_is_invalid` (item 001); a snapshot-hash mismatch is invalid via `validity_fn` (D36, Task 10).
- [ ] **Effect/executor decision recorded:** bash is an `ExecutionRequest`-style effect (DEC-1) via a NEW `BashRequest` type (DEC-2), fulfilled by a sandboxed subprocess executor (Task 3) through the widened loop seam (Task 4). Bounded: shlex (no shell), allowlist, pinned PATH, 60s timeout, captured/truncated stdout.
- [ ] **D19 no-leak:** fact-keys/answers/snapshot absent from the candidate prompt + tool surface (Task 12); the store is gitignored (D33 commit guard) and read only by `build_cmc_tasks` at oracle-assembly time.
- [ ] **D36 snapshot+hash:** the snapshot is content-hashed; for M1 a hash mismatch routes to the validity mask (validity-masked, as the spec prescribes for M1).
- [ ] **Reuse, not reinvent:** `run_single` (censoring loop), `run_task_k_valid` (k_valid replacement), `truncate_output`, `_kill_process_group` pattern, `load_evaluator_config`/`health_probe`, the `f3_oracle` build-function pattern — all reused, none duplicated.
- [ ] **Records carry the metrics:** each run records `rounds`, `usage` (tokens → cost downstream), `stop_reason`, `tool_call_counts`, `env_health` via the unchanged `Trajectory` (item 001) — no schema change needed here.
- [ ] **Offline-green:** every live/store-dependent test is behind `requires_store` or a node/reachability guard; `uv run pytest -q` is green with no network and no evaluator store.
- [ ] **FP discipline (user CLAUDE.md):** all new core (`fact_key.py`, `browse.py`, `cmc_dset.py`, record modules) is pure (no I/O); I/O is isolated to the edges (`bash_edge.py`, `dset_run.py`, `cli.py`); frozen dataclasses; spread/return-new, no argument mutation; functions < ~20 lines.

---

## Risks (flagged for the impl agent + owner, before impl)

1. **Session sharing across k_valid attempts (DEC-8 note).** `run_task_k_valid` reuses one `executor` (one playwright-cli session) across the k attempts of a task. For read-only D-set browsing this is benign, but if the model leaves the browser on a stale page between attempts, attempt 2+ may answer from the wrong page. **Mitigation:** the system prompt tells the model to `open` the docs URL at the start of every run; the model controls the session id. If flakiness appears, move executor construction into a per-attempt callback (a small `run_task_k_valid` extension) — deferred from M1, documented.
2. **playwright-cli result wrapper parsing (Task 8 Step 1).** `eval` output is wrapped in `### Result\n"<escaped innerText>"\n### Ran...`. The snapshot extractor must strip this wrapper and unescape. The probe confirmed the wrapper shape; the regex in Task 8 handles it, but the impl must verify the unescape round-trips (a `\n` in the page becomes a real newline) — assert `len(snapshot) > 8000` after extraction.
3. **Forbidden-key authoring is the integrity load-bearer.** The L1–L3 determinism rests on forbidden keys catching hallucinations. If forbidden lists are thin, a confidently-wrong answer could pass. **Mitigation:** Task 9's `test_every_factkey_required_is_on_the_snapshot` + the golden-answer round-trip test bound *strictness*; the owner reviews the forbidden lists (D24 owner-review bar) before any M1 run. This is owner-pending, same as F3's oracle review.
4. **Faithfulness gate is substring-only, not entailment.** A model that quotes the right number in a wrong sentence ("1.34 is unsupported") could pass the fact-key floor. For L1–L3 this is acceptable (the spec's deterministic floor is intentionally a *floor*); the L4–L5 judge stub + the forbidden contradiction keys (e.g. "1.34 is unsupported" as a forbidden phrase where it matters) are the backstop. Flagged so the owner calibrates forbidden phrases per question.
5. **Allowlist scope.** `ALLOWED_BINS = {"playwright-cli"}` blocks the model from `grep`/`cat`-ing the filesystem — good for D19, but it means the model must parse page text in its own context (it cannot pipe to grep). The probe showed 8949 bytes fits comfortably; if a linked section pushes output past the 8 KiB `truncate_output` cap, the model must use `eval` with a targeted selector rather than full `innerText`. Documented; not a blocker for the single-page D-set.
6. **`run_task_k_valid(max_steps=...)` is a required-but-unused arg.** Passed as `0`; the censoring safety cap governs (item 001). If a future signature change drops `max_steps`, update `run_dset` — flagged.
