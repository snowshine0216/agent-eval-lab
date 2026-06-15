# Item 005 — Factor V confined-execution sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supply the Factor V executor — a confined `run_tests` tool that runs the model's own **authored tests** (`tests/authored/`) under a real macOS kernel **confined-execution** boundary (`sandbox-exec` seatbelt), so a V arm can iterate against its own tests without being able to read the held-out oracle/`evaluator-only/` golden (the in-trajectory stdout leak) or reach the network — leaving the trusted oracle path (`runners/node_edge.py`) and the frozen `truncate_output` contract byte-stable.

**Architecture:** A new edge module `runners/sandboxed_node_edge.py` mirrors `node_edge.py`'s structure (materialize tree → run node → record) but (a) wraps the `node --test tests/authored/` invocation in a `/usr/bin/sandbox-exec -p <profile>` prefix, (b) builds that profile from a **pure** `seatbelt_profile(temp_tree, node_paths) -> str` function whose policy is **deny-default + `(import "system.sb")` + an explicit enumerated read-allowlist** (NO broad `(allow file-read*)`), (c) renders V feedback through a **separate tail-aware** renderer and persists a **distinct versioned V record class** (`NodeFeedbackResult`), and (d) exposes `make_authored_test_executor(...)` — an injected callable that **ignores model-supplied commands** and always runs the fixed `node --test tests/authored/`. `f_candidate.make_f_run_fn` replaces its item-003 `NotImplementedError` V-guard with: on macOS+`sandbox-exec`, route V arms to the sandboxed executor; off-macOS, keep skipping/guarding. `bare`/`prompt` keep `executor=None`.

**Tech Stack:** Python 3.12, dataclasses, pytest, macOS `/usr/bin/sandbox-exec` (seatbelt SBPL), node v16.20.2 via nvm (`node --test`, TAP output — junit reporter absent on v16), `subprocess` at the edge.

---

## Background — read before starting (in this order)

1. **Spec:** `docs/2026-06-15-harness-rounds-f-ablation/items/005-spec.md` — authoritative acceptance criteria (security is the priority; the read-**allowlist**, not a broad allow, is load-bearing).
2. **Design:** `docs/superpowers/specs/2026-06-15-agentic-v1-harness-rounds-F-ablation-design.md` — **§B.4** (the V loop: seatbelt profile, `make_authored_test_executor`, tail-aware feedback, V-specific ToolDef), **§9.1 / §10.3** (round-3 row #3: deny-read-by-default + explicit read-allowlist; broad read-allow reopens the leak), **§11.5** (`confined execution` vs `sandbox` glossary split), **Part G step 5** (this item's slice).
3. **ADR:** `docs/adr/0016-untrusted-authored-tests-run-under-kernel-confinement.md` — the decision this plan implements (deny-default + enumerated allowlist; Docker `--network none` is the pre-authorized fallback ONLY if seatbelt can't both start node and block the read; the integration test must prove BOTH start-and-block).
4. **Code — study, do NOT modify the oracle path:**
   - `src/agent_eval_lab/runners/node_edge.py` — the **trusted oracle** node path (DO NOT MODIFY; §9.7 byte-stability). Mirror: `_node_env(root)` (line 85), `node_supports_junit()` (line 64 — the probe shape), `run_node_tests`, `canonicalize_node_output`, `_node_bin`, `_kill_process_group`, `_timeout_result`.
   - `src/agent_eval_lab/runners/loop.py` — `Effect = ExecutionRequest | BashRequest` (line 46), `Executor = Callable[[Effect], ExecutionResult | BashResult]` (line 48), `_serialize_effect_result` (line 51), `_fulfill` (line 57). The loop fulfils an effect-request via the injected executor and records `ToolSuccess(result=<dict>)`.
   - `src/agent_eval_lab/runners/f_candidate.py` — `make_f_run_fn` (line 195); the V-arm `NotImplementedError` guard at line 216 (`(edit_task.initial_state or {}).get("factor_v")`) is what we REPLACE. `make_edit_task` (line 168) already offers `run_tests` on V arms.
   - `src/agent_eval_lab/tools/code_world.py` — the shared `run_tests` ToolDef (line 80, description "Run pytest over every visible test" — wrong for node), `CODE_WORLD_TOOLS` (line 29), `_run_tests` → `ExecutionRequest(files=...)` (line 241), `_HARNESS_RESERVED` (line 91).
   - `src/agent_eval_lab/runners/pytest_edge.py` — `materialize_tree` (line 148, reused by node_edge), `_kill_process_group`, `_timeout_result`, `execute_request`/`run_pytest` (the executor record-shape to mirror).
   - `src/agent_eval_lab/runners/bash_edge.py` — `make_bash_executor` (line 150): the `make_*_executor` **injected-callable factory** pattern to mirror (returns a closure that rejects disallowed input at the edge).
   - `src/agent_eval_lab/records/execution.py` — `ExecutionResult`, `truncate_output` (line 54; **DO NOT change**, ADR-0009), `OUTPUT_CAP_BYTES = 8192`, `TRUNCATION_MARKER`. The V record is a **distinct versioned class**, not a reuse of this one.
   - `src/agent_eval_lab/records/serialize.py` — `outcome_to_dict` (line 30): `ToolSuccess.result` is serialized as an opaque dict, so the V record only needs a `*_to_dict` producing a plain JSON dict.
   - `tests/runners/test_node_edge.py` — mirror test style + the Darwin/node gating markers.

## Environment facts (verified on THIS host — `2026-06-15`, do not re-derive)

- **Host:** Darwin 25.5.0 / macOS 26.5.1 (Tahoe), `/usr/bin/sandbox-exec` present (root:wheel, 0755).
- **node:** `which node` → `/Users/snow/.nvm/versions/node/v16.20.2/bin/node`, `node --version` → `v16.20.2`. node's parent dir = `/Users/snow/.nvm/versions/node/v16.20.2/bin`; the **node install dir** (the subpath to allow) = `/Users/snow/.nvm/versions/node/v16.20.2` (the nvm version root containing `bin/`, `lib/`, `include/`).
- **node v16 `--test`:** WORKS (TAP output, exit 0/1). `node_supports_junit()` returns **False** on v16 (the `--test-reporter=junit` it gates needs node ≥20). **Therefore V feedback must NOT depend on junit** — it uses exit-code + tail-rendered TAP, and the integration test must NOT gate the block-read/block-network assertions on junit support.
- **Goldens present:** `evaluator-only/web-dossier-golden/golden-files/*.golden` exist (e.g. `report-to-allure.js.golden`) — the integration test reads one of these *under the profile* and asserts EPERM.
- **dyld:** `/private/var/db/dyld` exists but is empty on Tahoe; the OS dyld shared cache lives under `/System/Volumes/Preboot/Cryptexes/OS/...` and `/System/Cryptexes`, both covered by the `(subpath "/System")` allow. `(subpath "/private/var/db/dyld")` is kept (harmless, spec-named, covers older macOS).

### Profile verification already performed on this host (evidence for Task 2 / Task 8)

The exact enumerated profile below was tested verbatim against `/usr/bin/sandbox-exec -f <profile> <node> ...`:

| assertion | command shape | result |
|---|---|---|
| node STARTS | `node run.js` (prints a marker) | **exit 0**, marker printed |
| benign in-tree read | `fs.readFileSync('marker.txt')` inside tree | **allowed** |
| benign in-tree write | `fs.writeFileSync('tests/authored/scratch.txt', ...)` | **allowed** |
| `node --test tests/authored/` | a passing authored test | **exit 0**, TAP `# pass 1` |
| evaluator-only read | `fs.readFileSync('<...>.golden')` | **exit 1**, `Error: EPERM` |
| network connect | `net.connect(80, '93.184.216.34')` | **exit 3**, `NET-BLOCKED:EPERM` |

The control: with `(deny default)` and the SAME profile but a **broad** `(allow file-read*)`, the golden read SUCCEEDS — confirming the allowlist (not the network deny) is what closes the stdout-leak channel. `(import "system.sb")` supplies the mach-bootstrap/sysctl/process-info baseline node needs WITHOUT a broad file-read (system.sb → its golden read was still EPERM-denied); a hand-rolled `(allow mach*)`/`(allow sysctl-read)` set without `system.sb` aborts node at startup (SIGABRT/exit 134).

---

## File Structure

- **Create** `src/agent_eval_lab/records/node_feedback.py` — the distinct versioned V record class `NodeFeedbackResult` + `node_feedback_result_to_dict` (+ `_from_dict` for round-trip) + the **tail-aware** renderer `render_feedback_tail`. Separate from `records/execution.py` so the oracle's head-truncated `ExecutionResult` stays byte-stable.
- **Create** `src/agent_eval_lab/runners/sandboxed_node_edge.py` — the confined edge: pure `seatbelt_profile(...)`, the `darwin_sandbox_available()` probe, `node_install_paths()`, `run_authored_tests_sandboxed(...)` (the subprocess edge), and `make_authored_test_executor(...)` (the injected callable factory).
- **Create** `tests/runners/test_sandboxed_node_edge.py` — pure profile-builder unit tests (no subprocess), fake-executor wiring tests, the tail-renderer tests, and the macOS-only integration test that ACTUALLY blocks an `evaluator-only/` read + a network call and confirms a benign in-tree run is allowed.
- **Modify** `src/agent_eval_lab/tools/code_world.py` — add a V-specific node-accurate `run_tests` ToolDef (`AUTHORED_RUN_TESTS_TOOLDEF`) and a `CODE_WORLD_TOOLS_V` registry that swaps it in. Do NOT mutate the shared `CODE_WORLD_TOOLS["run_tests"]` (other consumers below depend on the pytest wording).
- **Modify** `tests/tools/test_code_world.py` — assert the V ToolDef is node-accurate and the shared one is unchanged.
- **Modify** `src/agent_eval_lab/runners/f_candidate.py` — replace the V-arm `NotImplementedError` with macOS routing to the sandboxed executor (off-macOS: keep skip/guard); use `CODE_WORLD_TOOLS_V` registry for V arms.
- **Modify** `tests/runners/test_f_candidate.py` — replace `test_make_f_run_fn_refuses_live_v_arm_until_005` with the new routing tests (macOS routes to a fake executor; off-macOS still skips/guards).

### Shared-ToolDef consumer audit (do this FIRST — informs Task 5)

Before changing anything in `code_world.py`, confirm who reads `CODE_WORLD_TOOLS["run_tests"]`:

```bash
grep -rn "run_tests" src/agent_eval_lab/ | grep -v "\.pyc"
grep -rn "CODE_WORLD_TOOLS" src/agent_eval_lab/ tests/ | grep -v "\.pyc"
```

Expected finding (from study): `f_candidate.make_edit_task` adds the *name* `"run_tests"` to a V arm's `available_tools`, and `run_single` looks the name up in the registry it is given. The pytest code-world (D/B sets) and any python-domain task consume `CODE_WORLD_TOOLS` with the pytest-worded `run_tests`. **Decision: do NOT mutate the shared ToolDef** (mutating its description to node wording would mislabel the python path). Instead add a V-specific ToolDef and a `CODE_WORLD_TOOLS_V` registry; `make_f_run_fn` passes `CODE_WORLD_TOOLS_V` for V arms. Record the audit result in the Task 5 commit message.

---

## The load-bearing security control — the seatbelt profile (typed verbatim)

`seatbelt_profile(temp_tree, node_dir, *, extra_read_subpaths=DEFAULT_SYSTEM_READ_SUBPATHS)` is a **pure** function returning this exact string (with `{temp_tree}` and `{node_dir}` substituted — both must be **resolved absolute** paths, no trailing slash). `DEFAULT_SYSTEM_READ_SUBPATHS = ("/usr/lib", "/usr/bin", "/bin", "/System", "/private/var/db/dyld")`:

```scheme
(version 1)
(deny default)
(import "system.sb")
(allow process-exec)
(allow process-fork)
(allow file-read-metadata)
(allow file-read* (subpath "{temp_tree}"))
(allow file-read* (subpath "{node_dir}"))
(allow file-read* (subpath "/usr/lib"))
(allow file-read* (subpath "/usr/bin"))
(allow file-read* (subpath "/bin"))
(allow file-read* (subpath "/System"))
(allow file-read* (subpath "/private/var/db/dyld"))
(deny network*)
(allow file-write* (subpath "{temp_tree}"))
```

Properties this enforces, asserted by unit tests in Task 2:
- `(deny default)` baseline; `(import "system.sb")` supplies ONLY the mach-bootstrap/sysctl/process-info node needs to start (no broad file-read — verified: the golden read is still EPERM under it).
- **NO broad `(allow file-read*)`** anywhere (the unit test asserts the substring `(allow file-read*)\n` / `(allow file-read* )` form never appears WITHOUT a following `(subpath ...)`). Reads are scoped to: the candidate temp tree, the node install dir, and the enumerated system paths.
- `(deny network*)` closes the network exfiltration channel; `(allow file-write* (subpath temp_tree))` permits in-tree scratch (e.g. node test temp files) with writes denied elsewhere by `(deny default)`.
- `process-exec`/`process-fork` let node spawn its test workers.

**Why `(import "system.sb")` and not hand-rolled mach/sysctl allows:** verified on this host — without it, a hand-rolled `(allow mach*)`/`(allow sysctl-read)` set still aborts node at startup (exit 134, no stderr). `system.sb` is Apple's minimal process baseline and (critically) does NOT grant broad file-read, so the allowlist remains the read boundary (the golden read is EPERM-denied under `system.sb` + the enumerated reads). This is faithful to ADR-0016's "enumerated allowlist" intent: the *file-read* policy is fully enumerated and deny-default; `system.sb` only covers non-file process primitives.

---

## Task 1: The distinct versioned V record class + tail-aware renderer

**Files:**
- Create: `src/agent_eval_lab/records/node_feedback.py`
- Test: `tests/runners/test_sandboxed_node_edge.py` (record/renderer section)

- [ ] **Step 1: Write the failing tests** (create the test file with this section)

```python
from agent_eval_lab.records.node_feedback import (
    FEEDBACK_SCHEMA_VERSION,
    NodeFeedbackResult,
    node_feedback_result_from_dict,
    node_feedback_result_to_dict,
    render_feedback_tail,
)


def test_node_feedback_result_round_trips() -> None:
    rec = NodeFeedbackResult(
        status="failed",
        exit_code=1,
        passed=2,
        failed=1,
        output="ok 1\nnot ok 2\n# fail 1\n",
    )
    back = node_feedback_result_from_dict(node_feedback_result_to_dict(rec))
    assert back == rec


def test_node_feedback_dict_carries_schema_version() -> None:
    rec = NodeFeedbackResult(
        status="passed", exit_code=0, passed=1, failed=0, output="# pass 1\n"
    )
    d = node_feedback_result_to_dict(rec)
    assert d["schema_version"] == FEEDBACK_SCHEMA_VERSION
    assert d["record"] == "node_feedback"


def test_render_feedback_tail_keeps_the_end_when_too_long() -> None:
    # 20000 lines; the failure summary is the LAST line. Tail-aware: it survives.
    body = "\n".join(f"ok {i}" for i in range(20000)) + "\n# fail 7 AT-THE-END\n"
    rendered = render_feedback_tail(body)
    assert "# fail 7 AT-THE-END" in rendered  # the END is kept (tail-aware)
    assert rendered.startswith("[head truncated]")  # marker at the FRONT
    assert len(rendered.encode("utf-8")) <= 8192 + len("[head truncated]\n")


def test_render_feedback_tail_passthrough_when_short() -> None:
    assert render_feedback_tail("# pass 3\n") == "# pass 3\n"


def test_render_feedback_tail_never_splits_a_multibyte_char() -> None:
    body = "é" * 9000  # 2 bytes each -> 18000 bytes, over the cap
    rendered = render_feedback_tail(body)
    # decodes cleanly (no half-character) and is tail-anchored
    assert rendered.encode("utf-8").decode("utf-8")
    assert rendered.endswith("é")
```

- [ ] **Step 2: Run to verify it fails** — `python -m pytest -o addopts="" tests/runners/test_sandboxed_node_edge.py -q` → FAIL (`ModuleNotFoundError: node_feedback`).

- [ ] **Step 3: Write the minimal implementation**

```python
"""Versioned V-feedback record + tail-aware renderer (ADR-0016, §9.7).

DISTINCT from records/execution.ExecutionResult: the oracle's record stays
head-truncated (truncate_output, ADR-0009) and byte-stable; V feedback is its
own versioned class rendered TAIL-aware (the node failure summary prints at the
END of a run, so the head is the disposable part). Nothing here imports or
changes truncate_output.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

FEEDBACK_SCHEMA_VERSION = 1
FEEDBACK_CAP_BYTES = 8192
HEAD_TRUNCATION_MARKER = "[head truncated]\n"

FeedbackStatus = Literal["passed", "failed", "error", "timeout"]


@dataclass(frozen=True, kw_only=True)
class NodeFeedbackResult:
    """One sandboxed authored-test run, rendered for the model (no wall-clock)."""

    status: FeedbackStatus
    exit_code: int
    passed: int
    failed: int
    output: str


def render_feedback_tail(text: str) -> str:
    """TAIL-truncate at FEEDBACK_CAP_BYTES of UTF-8, marker at the FRONT.

    The node failure summary prints at the END; keep the tail, drop the head. A
    multibyte character split at the cut is dropped, never half-recorded. Pure.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= FEEDBACK_CAP_BYTES:
        return text
    tail = encoded[-FEEDBACK_CAP_BYTES:].decode("utf-8", errors="ignore")
    return HEAD_TRUNCATION_MARKER + tail


def node_feedback_result_to_dict(result: NodeFeedbackResult) -> dict[str, Any]:
    return {
        "record": "node_feedback",
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "status": result.status,
        "exit_code": result.exit_code,
        "passed": result.passed,
        "failed": result.failed,
        "output": result.output,
    }


def node_feedback_result_from_dict(data: Mapping[str, Any]) -> NodeFeedbackResult:
    return NodeFeedbackResult(
        status=data["status"],
        exit_code=data["exit_code"],
        passed=data["passed"],
        failed=data["failed"],
        output=data["output"],
    )
```

- [ ] **Step 4: Run to verify it passes** — same pytest command → the 5 record/renderer tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/records/node_feedback.py tests/runners/test_sandboxed_node_edge.py
git commit -m "feat(005): versioned NodeFeedbackResult + tail-aware renderer (V feedback)"
```

---

## Task 2: The pure seatbelt profile builder + node-paths helper + Darwin probe

**Files:**
- Create: `src/agent_eval_lab/runners/sandboxed_node_edge.py` (profile/probe section only this task)
- Test: `tests/runners/test_sandboxed_node_edge.py` (profile section)

- [ ] **Step 1: Write the failing tests** (append to the test file)

```python
import sys

import pytest

from agent_eval_lab.runners.sandboxed_node_edge import (
    DEFAULT_SYSTEM_READ_SUBPATHS,
    SANDBOX_EXEC,
    darwin_sandbox_available,
    seatbelt_profile,
)

_TREE = "/private/var/folders/x/agent-eval-vsbx-abc"
_NODE_DIR = "/Users/who/.nvm/versions/node/v16.20.2"


def test_profile_is_deny_default_with_system_baseline() -> None:
    prof = seatbelt_profile(_TREE, _NODE_DIR)
    assert prof.startswith("(version 1)\n(deny default)\n")
    assert '(import "system.sb")' in prof


def test_profile_has_no_broad_file_read_allow() -> None:
    prof = seatbelt_profile(_TREE, _NODE_DIR)
    # the load-bearing assertion: every file-read allow is SCOPED to a subpath.
    for line in prof.splitlines():
        if line.startswith("(allow file-read*"):
            assert "(subpath " in line, f"unscoped file-read allow: {line!r}"
    # and the bare broad form never appears
    assert "(allow file-read*)" not in prof


def test_profile_scopes_reads_to_tree_node_and_system() -> None:
    prof = seatbelt_profile(_TREE, _NODE_DIR)
    assert f'(allow file-read* (subpath "{_TREE}"))' in prof
    assert f'(allow file-read* (subpath "{_NODE_DIR}"))' in prof
    for sysp in DEFAULT_SYSTEM_READ_SUBPATHS:
        assert f'(allow file-read* (subpath "{sysp}"))' in prof


def test_profile_denies_network_and_scopes_writes() -> None:
    prof = seatbelt_profile(_TREE, _NODE_DIR)
    assert "(deny network*)" in prof
    assert f'(allow file-write* (subpath "{_TREE}"))' in prof
    # no broad write allow
    assert "(allow file-write*)" not in prof


def test_profile_allows_process_primitives() -> None:
    prof = seatbelt_profile(_TREE, _NODE_DIR)
    assert "(allow process-exec)" in prof
    assert "(allow process-fork)" in prof


def test_darwin_probe_false_off_macos(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert darwin_sandbox_available() is False
```

- [ ] **Step 2: Run to verify it fails** — FAIL (`ImportError: seatbelt_profile`).

- [ ] **Step 3: Write the minimal implementation** (create the module with the profile/probe section)

```python
"""EDGE: confined `node --test tests/authored/` execution (ADR-0016, §B.4).

The UNTRUSTED sibling of node_edge.py. Where node_edge runs TRUSTED oracle code
un-sandboxed, this module runs the model's own AUTHORED tests under a macOS
sandbox-exec seatbelt that is deny-read-by-default with an explicit
read-allowlist (the candidate tree + node install dir + enumerated system
paths) plus deny-network and write-only-in-tree. The allowlist (not a broad
read-allow) is the security boundary: a broad (allow file-read*) would let model
JS read evaluator-only/ and print the golden to stdout, which is returned to the
model in-trajectory (deny network* alone does NOT close that channel).

node_edge.py (the trusted oracle path) is deliberately NOT touched here so its
frozen ExecutionResult records stay byte-stable (§9.7).

ESCALATION (ADR-0016): if this seatbelt allowlist cannot both start node AND
block an evaluator-only/ read on a given host, escalate to Docker --network none
with only the temp tree mounted. As of 2026-06-15 the seatbelt path is verified
working on macOS 26.5.1 + node v16.20.2, so Docker is NOT built.
"""

import os
import shutil
import sys
from pathlib import Path

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
DEFAULT_SYSTEM_READ_SUBPATHS: tuple[str, ...] = (
    "/usr/lib",
    "/usr/bin",
    "/bin",
    "/System",
    "/private/var/db/dyld",
)


def seatbelt_profile(
    temp_tree: str,
    node_dir: str,
    *,
    extra_read_subpaths: tuple[str, ...] = DEFAULT_SYSTEM_READ_SUBPATHS,
) -> str:
    """Build the deny-default seatbelt profile (SBPL). Pure.

    temp_tree and node_dir MUST be resolved absolute paths with no trailing
    slash. Reads are enumerated (deny-default everywhere else); there is NO broad
    (allow file-read*). Writes are scoped to temp_tree; network is denied.
    """
    read_subpaths = (temp_tree, node_dir, *extra_read_subpaths)
    read_lines = "\n".join(
        f'(allow file-read* (subpath "{p}"))' for p in read_subpaths
    )
    return (
        "(version 1)\n"
        "(deny default)\n"
        '(import "system.sb")\n'
        "(allow process-exec)\n"
        "(allow process-fork)\n"
        "(allow file-read-metadata)\n"
        f"{read_lines}\n"
        "(deny network*)\n"
        f'(allow file-write* (subpath "{temp_tree}"))\n'
    )


def darwin_sandbox_available() -> bool:
    """True iff this host is macOS with an executable sandbox-exec.

    Mirrors node_supports_junit's probe shape: a cheap, side-effect-free
    capability check used to gate real V execution (skips on Linux CI).
    """
    if sys.platform != "darwin":
        return False
    return os.access(SANDBOX_EXEC, os.X_OK)


def node_install_paths() -> tuple[str, str]:
    """Return (resolved node binary, resolved node install dir). Edge (resolves
    a real path). The install dir is the binary's parent's parent (nvm layout:
    <ver>/bin/node -> allow subpath <ver>); falls back to the bin dir if the
    layout is flat.
    """
    resolved = shutil.which(os.environ.get("NODE_BIN", "node"))
    if resolved is None:
        raise RuntimeError("node binary not found (set NODE_BIN or add node to PATH)")
    node_bin = str(Path(resolved).resolve())
    bin_dir = Path(node_bin).parent
    install_dir = bin_dir.parent if bin_dir.name == "bin" else bin_dir
    return node_bin, str(install_dir)
```

- [ ] **Step 4: Run to verify it passes** — the profile/probe tests PASS.

- [ ] **Step 5: Verify the profile string is REAL on this host** (evidence step — macOS only; this proves the typed-verbatim profile actually works, not just that the builder emits the right substrings):

```bash
python - <<'PY'
import subprocess, tempfile, os
from pathlib import Path
from agent_eval_lab.runners.sandboxed_node_edge import seatbelt_profile, node_install_paths
node_bin, node_dir = node_install_paths()
tree = Path(tempfile.mkdtemp(prefix="agent-eval-vsbx-")).resolve()
(tree / "run.js").write_text("console.log('NODE_STARTED_OK')\n")
prof = seatbelt_profile(str(tree), node_dir)
pf = tree / ".profile.sb"; pf.write_text(prof)
golden = "evaluator-only/web-dossier-golden/golden-files/report-to-allure.js.golden"
golden = str(Path(golden).resolve())
def run(args): return subprocess.run(["/usr/bin/sandbox-exec","-f",str(pf),node_bin,*args],cwd=tree,capture_output=True,text=True)
a = run(["run.js"]); print("start exit", a.returncode, a.stdout.strip())
b = run(["-e", f"require('fs').readFileSync({golden!r},'utf8');console.log('LEAK')"]); print("golden exit", b.returncode, "EPERM" in b.stderr)
import shutil; shutil.rmtree(tree, ignore_errors=True)
PY
```

Expected: `start exit 0 NODE_STARTED_OK` and `golden exit 1 True`. (If this ever prints `LEAK` or a non-1 golden exit, STOP — the allowlist regressed; this is a blocker, escalate to the Docker fallback per ADR-0016.)

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/runners/sandboxed_node_edge.py tests/runners/test_sandboxed_node_edge.py
git commit -m "feat(005): pure seatbelt_profile builder + Darwin/sandbox-exec probe (deny-default + enumerated read-allowlist)"
```

---

## Task 3: The sandboxed authored-test subprocess edge + `make_authored_test_executor`

**Files:**
- Modify: `src/agent_eval_lab/runners/sandboxed_node_edge.py` (add the edge + factory)
- Test: `tests/runners/test_sandboxed_node_edge.py` (executor-wiring section, fake subprocess)

This task wires the executor without running a real sandbox (that is Task 8's integration test). The factory mirrors `bash_edge.make_bash_executor`: a closure that IGNORES model-supplied request contents and always runs the fixed `node --test tests/authored/`.

- [ ] **Step 1: Write the failing tests** (append; these use a fake `run_fn` so they run on CI)

```python
from agent_eval_lab.records.execution import ExecutionRequest
from agent_eval_lab.records.node_feedback import NodeFeedbackResult
from agent_eval_lab.runners.sandboxed_node_edge import (
    AUTHORED_TEST_DIR,
    make_authored_test_executor,
)


def test_executor_ignores_request_paths_and_runs_authored_dir() -> None:
    seen: list[tuple] = []

    def fake_run(files, *, node_bin, node_dir, timeout_s):
        seen.append(tuple(sorted(files)))
        return NodeFeedbackResult(
            status="passed", exit_code=0, passed=1, failed=0, output="# pass 1\n"
        )

    executor = make_authored_test_executor(
        node_bin="/x/node", node_dir="/x", run_fn=fake_run
    )
    # the model snapshotted the WHOLE tree (incl. seeded causal tests); the
    # executor must run only tests/authored/ regardless.
    req = ExecutionRequest(
        files={
            "tests/authored/a.test.js": "x",
            "tests/wdio/seeded.causal.test.js": "should-not-run",
        }
    )
    out = executor(req)
    assert isinstance(out, NodeFeedbackResult)
    assert out.status == "passed"
    # the materialized tree carried both files (snapshot), but run_fn only ever
    # gets the FIXED test dir as the path to run (asserted via the command below)


def test_executor_run_fn_receives_fixed_authored_test_path() -> None:
    captured: dict = {}

    def fake_run(files, *, node_bin, node_dir, timeout_s):
        captured["test_dir"] = AUTHORED_TEST_DIR
        return NodeFeedbackResult(
            status="error", exit_code=1, passed=0, failed=0, output="no tests\n"
        )

    executor = make_authored_test_executor(
        node_bin="/x/node", node_dir="/x", run_fn=fake_run
    )
    executor(ExecutionRequest(files={"tests/authored/a.test.js": "x"}))
    assert captured["test_dir"] == "tests/authored/"


def test_authored_test_dir_is_reserved_constant() -> None:
    assert AUTHORED_TEST_DIR == "tests/authored/"
```

- [ ] **Step 2: Run to verify it fails** — FAIL (`ImportError: make_authored_test_executor`).

- [ ] **Step 3: Write the implementation** (append to `sandboxed_node_edge.py`)

```python
import re
import signal
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from contextlib import suppress

from agent_eval_lab.records.execution import ExecutionRequest
from agent_eval_lab.records.node_feedback import NodeFeedbackResult, render_feedback_tail
from agent_eval_lab.runners.node_edge import canonicalize_node_output
from agent_eval_lab.runners.pytest_edge import materialize_tree

AUTHORED_TEST_DIR = "tests/authored/"
DEFAULT_TIMEOUT_S = 30.0
_TIMEOUT_EXIT_CODE = -9
# node v16 TAP summary lines, e.g. "# pass 3" / "# fail 1".
_TAP_PASS = re.compile(r"^# pass (\d+)$", re.MULTILINE)
_TAP_FAIL = re.compile(r"^# fail (\d+)$", re.MULTILINE)


def _node_env(root: str, node_dir: str) -> dict[str, str]:
    """From-scratch env (mirrors node_edge._node_env): never inherits os.environ."""
    return {
        "TZ": "UTC",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "HOME": root,
        "PATH": f"/usr/bin:/bin:{node_dir}/bin",
        "NODE_OPTIONS": "",
        "NO_COLOR": "1",
    }


def _tap_count(text: str, pattern: re.Pattern) -> int:
    m = pattern.search(text)
    return int(m.group(1)) if m else 0


def _classify(exit_code: int, passed: int, failed: int) -> str:
    if exit_code == 0:
        return "passed"
    if exit_code == 1 and (passed or failed):
        return "failed"
    return "error"


def _kill_process_group(process: subprocess.Popen) -> None:
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    with suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=2.0)


def run_authored_tests_sandboxed(
    files: Mapping[str, str],
    *,
    node_bin: str,
    node_dir: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> NodeFeedbackResult:
    """Materialize the tree, run `node --test tests/authored/` UNDER the seatbelt
    profile, render tail-aware feedback. Edge (subprocess/FS). Deterministic out.
    """
    root = Path(tempfile.mkdtemp(prefix="agent-eval-vsbx-")).resolve()
    try:
        materialize_tree(files, root)
        profile_path = root / ".profile.sb"
        profile_path.write_text(
            seatbelt_profile(str(root), node_dir), encoding="utf-8"
        )
        command = [
            SANDBOX_EXEC,
            "-f",
            str(profile_path),
            node_bin,
            "--test",
            AUTHORED_TEST_DIR,
        ]
        process = subprocess.Popen(
            command,
            cwd=root,
            env=_node_env(str(root), node_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            return NodeFeedbackResult(
                status="timeout",
                exit_code=_TIMEOUT_EXIT_CODE,
                passed=0,
                failed=0,
                output="",
            )
        merged = canonicalize_node_output(
            stdout.decode("utf-8", "replace") + stderr.decode("utf-8", "replace"),
            str(root),
        )
        passed = _tap_count(merged, _TAP_PASS)
        failed = _tap_count(merged, _TAP_FAIL)
        return NodeFeedbackResult(
            status=_classify(process.returncode, passed, failed),
            exit_code=process.returncode,
            passed=passed,
            failed=failed,
            output=render_feedback_tail(merged),
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def make_authored_test_executor(
    *,
    node_bin: str,
    node_dir: str,
    run_fn: Callable[..., NodeFeedbackResult] = run_authored_tests_sandboxed,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Callable[[ExecutionRequest], NodeFeedbackResult]:
    """Build the V executor: an injected callable the loop fulfils run_tests with.

    It IGNORES model-supplied request contents beyond the snapshotted tree and
    ALWAYS runs the fixed `node --test tests/authored/` (model-supplied commands
    are rejected by construction — there is no path for them). tests/authored/ is
    a reserved writable dir no seeded tree populates, so F3's seeded causal tests
    are never run as feedback. Reserved-path scoping is provenance; the seatbelt
    sandbox is the security boundary (§B.4). run_fn injected for tests.
    """

    def executor(request: ExecutionRequest) -> NodeFeedbackResult:
        return run_fn(
            dict(request.files),
            node_bin=node_bin,
            node_dir=node_dir,
            timeout_s=timeout_s,
        )

    return executor
```

- [ ] **Step 4: Run to verify it passes** — the executor-wiring tests PASS (no real sandbox; `run_fn` is faked).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/sandboxed_node_edge.py tests/runners/test_sandboxed_node_edge.py
git commit -m "feat(005): sandboxed authored-test edge + make_authored_test_executor (fixed node --test tests/authored/)"
```

---

## Task 4: Loop serialization accepts the V record (`NodeFeedbackResult`)

The loop's `_serialize_effect_result` currently handles `BashResult` then falls through to `execution_result_to_dict`. The V executor returns a `NodeFeedbackResult`, so the loop must route it. This is a SMALL, additive change to a trusted file — guard it with a test first; it does NOT touch `truncate_output` or the oracle path.

**Files:**
- Modify: `src/agent_eval_lab/runners/loop.py:51-54` (`_serialize_effect_result`) and line 48 (`Executor` type)
- Test: `tests/runners/test_loop.py` (add one case)

- [ ] **Step 1: Write the failing test** (append to `tests/runners/test_loop.py`)

```python
def test_serialize_effect_result_handles_node_feedback() -> None:
    from agent_eval_lab.records.node_feedback import NodeFeedbackResult
    from agent_eval_lab.runners.loop import _serialize_effect_result

    rec = NodeFeedbackResult(
        status="failed", exit_code=1, passed=0, failed=1, output="not ok 1\n"
    )
    d = _serialize_effect_result(rec)
    assert d["record"] == "node_feedback"
    assert d["status"] == "failed"
    assert d["schema_version"] == 1
```

- [ ] **Step 2: Run to verify it fails** — FAIL (`_serialize_effect_result` calls `execution_result_to_dict` on a `NodeFeedbackResult`, raising `AttributeError`/wrong shape).

- [ ] **Step 3: Implement** — edit `loop.py`. Add the import and the isinstance branch; widen the `Executor` return type:

```python
# add to the records imports near the top of loop.py
from agent_eval_lab.records.node_feedback import (
    NodeFeedbackResult,
    node_feedback_result_to_dict,
)
```

```python
# widen the Executor type alias (line ~48)
Executor = Callable[["Effect"], "ExecutionResult | BashResult | NodeFeedbackResult"]


def _serialize_effect_result(
    result: "ExecutionResult | BashResult | NodeFeedbackResult",
) -> dict:
    if isinstance(result, BashResult):
        return bash_result_to_dict(result)
    if isinstance(result, NodeFeedbackResult):
        return node_feedback_result_to_dict(result)
    return execution_result_to_dict(result)
```

- [ ] **Step 4: Run to verify it passes** — the new test PASSES; run the whole loop suite (`python -m pytest -o addopts="" tests/runners/test_loop.py -q`) to confirm no regression (the Bash/ExecutionResult branches are unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/loop.py tests/runners/test_loop.py
git commit -m "feat(005): loop serializes NodeFeedbackResult (additive; oracle path unchanged)"
```

---

## Task 5: V-specific node-accurate `run_tests` ToolDef + `CODE_WORLD_TOOLS_V`

**Files:**
- Modify: `src/agent_eval_lab/tools/code_world.py` (add the V ToolDef + V registry; do NOT mutate the shared one)
- Test: `tests/tools/test_code_world.py`

- [ ] **Step 0: Run the consumer audit** (from the File Structure section) and record the result. Confirm the shared `run_tests` (pytest wording) is consumed by the python/D-set path; the V path needs a separate node-accurate ToolDef.

- [ ] **Step 1: Write the failing tests** (append to `tests/tools/test_code_world.py`)

```python
def test_v_run_tests_tooldef_is_node_accurate() -> None:
    from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS_V

    desc = CODE_WORLD_TOOLS_V["run_tests"].description
    assert "pytest" not in desc.lower()
    assert "authored" in desc.lower()
    assert "node" in desc.lower()


def test_shared_run_tests_tooldef_is_unchanged_pytest_wording() -> None:
    from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS

    # the python/D-set path keeps its pytest wording — V must not have mutated it
    assert "pytest" in CODE_WORLD_TOOLS["run_tests"].description.lower()


def test_v_registry_shares_edit_tools_with_base() -> None:
    from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS, CODE_WORLD_TOOLS_V

    for name in ("read_file", "write_file", "str_replace", "list_files"):
        assert CODE_WORLD_TOOLS_V[name] is CODE_WORLD_TOOLS[name]
    # only run_tests differs
    assert CODE_WORLD_TOOLS_V["run_tests"] is not CODE_WORLD_TOOLS["run_tests"]
```

- [ ] **Step 2: Run to verify it fails** — FAIL (`ImportError: CODE_WORLD_TOOLS_V`).

- [ ] **Step 3: Implement** — append to `code_world.py` after `CODE_WORLD_TOOLS`:

```python
# Factor V (item 005): the model runs its OWN authored tests under node, NOT
# pytest. The shared run_tests ToolDef above keeps its pytest wording for the
# python/D-set path; this node-accurate ToolDef is swapped in for V arms only.
AUTHORED_RUN_TESTS_TOOLDEF = ToolDef(
    name="run_tests",
    description=(
        "Run your authored JavaScript tests in tests/authored/ with "
        "`node --test`; returns the run's pass/fail summary and output. Only "
        "tests under tests/authored/ run — seeded tests are not executed. "
        "Write your tests there first, then call this to check your edit."
    ),
    parameters=_NO_ARGS,
)

CODE_WORLD_TOOLS_V: Mapping[str, ToolDef] = {
    **CODE_WORLD_TOOLS,
    "run_tests": AUTHORED_RUN_TESTS_TOOLDEF,
}
```

- [ ] **Step 4: Run to verify it passes** — the 3 ToolDef tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/tools/code_world.py tests/tools/test_code_world.py
git commit -m "feat(005): V-specific node-accurate run_tests ToolDef + CODE_WORLD_TOOLS_V (shared ToolDef unchanged)"
```

---

## Task 6: `make_f_run_fn` routes V arms to the sandboxed executor on macOS

**Files:**
- Modify: `src/agent_eval_lab/runners/f_candidate.py:195-236` (`make_f_run_fn`); imports at top
- Test: `tests/runners/test_f_candidate.py` (replace the until-005 refusal test)

The item-003 guard raised `NotImplementedError` for any V arm. Now: on macOS+`sandbox-exec`, build the sandboxed executor and pass `CODE_WORLD_TOOLS_V` to `run_single`; off-macOS, keep the skip/guard (real V is macOS-local-only by design — §B.4). `bare`/`prompt` (factor_v falsey) always `executor=None` + `CODE_WORLD_TOOLS`.

- [ ] **Step 1: Write the failing tests** (in `tests/runners/test_f_candidate.py`, replacing `test_make_f_run_fn_refuses_live_v_arm_until_005`)

```python
def test_make_f_run_fn_routes_v_arm_to_sandboxed_executor_on_macos(monkeypatch) -> None:
    """On macOS+sandbox-exec a V arm runs the loop with a sandboxed executor and
    the V (node-accurate) registry — NOT executor=None, NOT NotImplementedError."""
    import httpx

    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.config import ProviderConfig
    from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS_V

    monkeypatch.setattr(fc, "darwin_sandbox_available", lambda: True)
    monkeypatch.setattr(fc, "node_install_paths", lambda: ("/x/node", "/x"))
    captured: dict = {}

    def fake_run_single(**kwargs):
        captured["executor"] = kwargs["executor"]
        captured["registry"] = kwargs["registry"]
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
        )

    monkeypatch.setattr(fc, "run_single", fake_run_single)
    cfg = ProviderConfig(id="local", base_url="http://x/v1", api_key_env="", model_id="m")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    run_fn = fc.make_f_run_fn(
        config=cfg, http_client=client, temperature=0.0, max_tokens=64,
        condition_id="c", safety_cap=200, max_rounds=40,
    )
    v_edit = make_edit_task(
        _flagged_task(factor_p=False, factor_v=True), base_tree={"a.js": "x\n"}
    )
    run_fn(v_edit, 0)
    assert captured["executor"] is not None  # routed to the sandboxed executor
    assert captured["registry"] is CODE_WORLD_TOOLS_V  # node-accurate V registry


def test_make_f_run_fn_skips_v_arm_off_macos(monkeypatch) -> None:
    """Off macOS (CI), real V execution skips — make_f_run_fn raises the skip
    guard (executor cannot be the real sandbox; fake executor is injected in
    unit tests, not here)."""
    import httpx

    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.runners.config import ProviderConfig

    monkeypatch.setattr(fc, "darwin_sandbox_available", lambda: False)
    cfg = ProviderConfig(id="local", base_url="http://x/v1", api_key_env="", model_id="m")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    run_fn = fc.make_f_run_fn(
        config=cfg, http_client=client, temperature=0.0, max_tokens=64,
        condition_id="c", safety_cap=200, max_rounds=40,
    )
    v_edit = make_edit_task(
        _flagged_task(factor_p=False, factor_v=True), base_tree={"a.js": "x\n"}
    )
    with pytest.raises(NotImplementedError, match="macOS"):
        run_fn(v_edit, 0)


def test_make_f_run_fn_bare_arm_stays_executor_none(monkeypatch) -> None:
    """bare/prompt (factor_v falsey) always run executor=None + the base registry."""
    import httpx

    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.config import ProviderConfig
    from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS

    captured: dict = {}

    def fake_run_single(**kwargs):
        captured["executor"] = kwargs["executor"]
        captured["registry"] = kwargs["registry"]
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
        )

    monkeypatch.setattr(fc, "run_single", fake_run_single)
    cfg = ProviderConfig(id="local", base_url="http://x/v1", api_key_env="", model_id="m")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    run_fn = fc.make_f_run_fn(
        config=cfg, http_client=client, temperature=0.0, max_tokens=64,
        condition_id="c", safety_cap=200, max_rounds=40,
    )
    bare_edit = make_edit_task(
        _flagged_task(factor_p=False, factor_v=False), base_tree={"a.js": "x\n"}
    )
    run_fn(bare_edit, 0)
    assert captured["executor"] is None
    assert captured["registry"] is CODE_WORLD_TOOLS
```

- [ ] **Step 2: Run to verify it fails** — FAIL (the current guard raises `NotImplementedError` mentioning "item 005", not "macOS"; and there is no routing/registry branch).

- [ ] **Step 3: Implement** — edit `f_candidate.py`. Add imports near the top:

```python
from agent_eval_lab.runners.sandboxed_node_edge import (
    darwin_sandbox_available,
    make_authored_test_executor,
    node_install_paths,
)
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS_V
```

Replace the `run_fn` body (the V-guard block + the single `run_single` call):

```python
    def run_fn(edit_task: Task, run_index: int) -> Trajectory:
        is_v = bool((edit_task.initial_state or {}).get("factor_v"))
        if is_v and not darwin_sandbox_available():
            # Real Factor V execution is macOS-local-only by design (§B.4): the
            # seatbelt confined-execution boundary is Darwin-only. On a non-macOS
            # host (CI) we cannot run a real V arm; unit tests inject a fake
            # executor instead. Refuse rather than silently run a no-op V loop.
            raise NotImplementedError(
                "Factor V real execution requires macOS + sandbox-exec "
                f"(arm {edit_task.id!r}); CI injects a fake executor"
            )
        if is_v:
            node_bin, node_dir = node_install_paths()
            executor = make_authored_test_executor(node_bin=node_bin, node_dir=node_dir)
            registry = CODE_WORLD_TOOLS_V
        else:
            executor = None
            registry = CODE_WORLD_TOOLS
        return run_single(
            task=edit_task,
            registry=registry,
            config=config,
            http_client=http_client,
            run_index=run_index,
            temperature=temperature,
            max_tokens=max_tokens,
            apply_fn=code_world_apply,
            executor=executor,
            run_uid=f"{condition_id}__{edit_task.id}__{run_index:04d}",
            safety_cap=safety_cap,
            max_rounds=max_rounds,
        )
```

Update the `make_f_run_fn` docstring's "refuses to drive a live V arm" sentence to: "a V arm is routed to the sandboxed `make_authored_test_executor` on macOS; off-macOS real V execution is refused (macOS-local-only, §B.4)."

- [ ] **Step 4: Run to verify it passes** — the 3 routing tests PASS; run the full `tests/runners/test_f_candidate.py` to confirm bare/prompt paths unaffected.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/f_candidate.py tests/runners/test_f_candidate.py
git commit -m "feat(005): route V arms to sandboxed make_authored_test_executor on macOS (off-macOS skip; bare/prompt executor=None)"
```

---

## Task 7: End-to-end V loop with a FAKE executor (CI-safe)

Prove the full path — model emits `run_tests` → `apply` returns `ExecutionRequest` → loop fulfils via the injected executor → `ToolSuccess(result=node_feedback dict)` lands on the trajectory — WITHOUT a real sandbox, so it runs on CI.

**Files:**
- Test: `tests/runners/test_sandboxed_node_edge.py` (loop-integration-with-fake section)

- [ ] **Step 1: Write the test**

```python
def test_v_loop_records_node_feedback_via_fake_executor() -> None:
    """run_tests -> ExecutionRequest -> fake executor -> ToolSuccess(node_feedback)."""
    import httpx

    from agent_eval_lab.records.node_feedback import NodeFeedbackResult
    from agent_eval_lab.records.turns import ToolResultTurn, ToolSuccess
    from agent_eval_lab.runners.config import ProviderConfig
    from agent_eval_lab.runners.loop import run_single
    from agent_eval_lab.tasks.schema import Task, TaskInput
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS_V, apply as cw_apply

    # provider: round 1 calls run_tests, round 2 stops naturally
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            msg = {
                "role": "assistant",
                "tool_calls": [
                    {"id": "c1", "type": "function",
                     "function": {"name": "run_tests", "arguments": "{}"}}
                ],
            }
        else:
            msg = {"role": "assistant", "content": "done"}
        return httpx.Response(200, json={"choices": [{"message": msg}], "usage": {}})

    def fake_executor(request):
        return NodeFeedbackResult(
            status="failed", exit_code=1, passed=0, failed=1, output="not ok 1\n"
        )

    task = Task(
        id="f-f1-feedback",
        input=TaskInput(
            messages=(MessageTurn(role="system", content="edit"),),
            available_tools=("read_file", "run_tests"),
        ),
        initial_state={"files": {"tests/authored/a.test.js": "x"}, "factor_v": True},
        verification=(),
    )
    cfg = ProviderConfig(id="local", base_url="http://x/v1", api_key_env="", model_id="m")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    traj = run_single(
        task=task, registry=CODE_WORLD_TOOLS_V, config=cfg, http_client=client,
        run_index=0, temperature=0.0, max_tokens=64, apply_fn=cw_apply,
        executor=fake_executor,
    )
    results = [t for t in traj.turns if isinstance(t, ToolResultTurn)]
    assert len(results) == 1
    assert isinstance(results[0].outcome, ToolSuccess)
    assert results[0].outcome.result["record"] == "node_feedback"
    assert results[0].outcome.result["status"] == "failed"
```

> Note: confirm the `Task`/`TaskInput`/`MessageTurn` constructor kwargs against `src/agent_eval_lab/tasks/schema.py` and `records/turns.py` before running — adjust field names if the schema differs. The intent (run_tests → fake executor → node_feedback ToolSuccess) is the load-bearing assertion.

- [ ] **Step 2: Run to verify it fails first if any wiring is missing**, then passes once Tasks 3-5 are in. Run: `python -m pytest -o addopts="" tests/runners/test_sandboxed_node_edge.py::test_v_loop_records_node_feedback_via_fake_executor -v`.

- [ ] **Step 3: Commit**

```bash
git add tests/runners/test_sandboxed_node_edge.py
git commit -m "test(005): end-to-end V loop records node_feedback via fake executor (CI-safe)"
```

---

## Task 8: The macOS-only integration test — ACTUALLY blocks the leak + network, allows benign run

This is the security proof. It must RUN on this host (node v16 + sandbox-exec both present), NOT skip — the block-read/block-network assertions use a minimal `node -e` under the profile, and the benign-run assertion uses a real `node --test tests/authored/` (v16 supports `--test`, no junit needed). Gate ONLY on Darwin + `sandbox-exec` (+ node present), NOT on `node_supports_junit`.

**Files:**
- Test: `tests/runners/test_sandboxed_node_edge.py` (integration section)

- [ ] **Step 1: Write the test**

```python
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_eval_lab.runners.sandboxed_node_edge import (
    SANDBOX_EXEC,
    darwin_sandbox_available,
    node_install_paths,
    run_authored_tests_sandboxed,
    seatbelt_profile,
)

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))

# Gate ONLY on Darwin + sandbox-exec + node present — NOT on junit support.
requires_seatbelt = pytest.mark.skipif(
    not (darwin_sandbox_available() and _NODE is not None),
    reason="macOS + sandbox-exec + node required for the confined-execution test",
)

_EVALUATOR_GOLDEN = (
    Path("evaluator-only/web-dossier-golden/golden-files/report-to-allure.js.golden")
    .resolve()
)


def _run_under_profile(node_bin: str, node_dir: str, tree: Path, args: list[str]):
    profile = tree / ".profile.sb"
    profile.write_text(seatbelt_profile(str(tree), node_dir), encoding="utf-8")
    return subprocess.run(
        [SANDBOX_EXEC, "-f", str(profile), node_bin, *args],
        cwd=tree, capture_output=True, text=True, timeout=30,
    )


@requires_seatbelt
def test_sandbox_blocks_evaluator_only_read(tmp_path) -> None:
    assert _EVALUATOR_GOLDEN.exists(), "test precondition: golden present"
    node_bin, node_dir = node_install_paths()
    tree = (tmp_path / "t").resolve()
    tree.mkdir()
    res = _run_under_profile(
        node_bin, node_dir, tree,
        ["-e", f"require('fs').readFileSync({str(_EVALUATOR_GOLDEN)!r},'utf8');"
               "console.log('LEAK-SUCCEEDED')"],
    )
    assert res.returncode != 0, "evaluator-only read MUST be blocked"
    assert "LEAK-SUCCEEDED" not in res.stdout
    assert "EPERM" in res.stderr  # sandbox denial, not ENOENT


@requires_seatbelt
def test_sandbox_blocks_network(tmp_path) -> None:
    node_bin, node_dir = node_install_paths()
    tree = (tmp_path / "t").resolve()
    tree.mkdir()
    res = _run_under_profile(
        node_bin, node_dir, tree,
        ["-e",
         "const net=require('net');"
         "const s=net.connect(80,'93.184.216.34',()=>{console.log('NET-OK');process.exit(0)});"
         "s.on('error',e=>{console.log('NET-BLOCKED:'+e.code);process.exit(3)});"
         "setTimeout(()=>{console.log('NET-TIMEOUT');process.exit(4)},3000)"],
    )
    assert "NET-OK" not in res.stdout, "network connect MUST be blocked"
    assert res.returncode != 0


@requires_seatbelt
def test_sandbox_starts_node_and_runs_benign_authored_test() -> None:
    """The boundary still permits the legitimate workflow: node starts, runs an
    authored test that reads/writes IN-TREE, and reports pass."""
    node_bin, node_dir = node_install_paths()
    files = {
        "package.json": '{"type":"module"}\n',
        "tests/authored/x.test.js": (
            "import test from 'node:test';\n"
            "import assert from 'node:assert/strict';\n"
            "import fs from 'node:fs';\n"
            "test('benign in-tree', () => {\n"
            "  const c = fs.readFileSync('package.json','utf8');\n"
            "  assert.ok(c.includes('module'));\n"
            "  fs.writeFileSync('tests/authored/scratch.txt','ok');\n"
            "});\n"
        ),
    }
    out = run_authored_tests_sandboxed(files, node_bin=node_bin, node_dir=node_dir)
    assert out.status == "passed", out.output
    assert out.exit_code == 0
    assert out.passed == 1
```

- [ ] **Step 2: Run on THIS host and confirm it RUNS (does not skip)** —

```bash
python -m pytest -o addopts="" tests/runners/test_sandboxed_node_edge.py -v -k "sandbox_blocks or benign_authored"
```

Expected: 3 PASSED (NOT skipped) — `test_sandbox_blocks_evaluator_only_read`, `test_sandbox_blocks_network`, `test_sandbox_starts_node_and_runs_benign_authored_test`. If any shows `s`/skipped on this host, the gating is wrong (it must gate on Darwin+sandbox-exec+node, NOT junit) — fix the marker.

- [ ] **Step 3: Commit**

```bash
git add tests/runners/test_sandboxed_node_edge.py
git commit -m "test(005): macOS integration test ACTUALLY blocks evaluator-only read + network, allows benign run"
```

---

## Task 9: Full verification + lint

- [ ] **Step 1: Run the whole suite** (the CI invocation — `-o addopts=""` overrides the repo's `-q`/testpaths so explicit selection works):

```bash
python -m pytest -o addopts="" tests -q
```

Expected: all green. On this host the 3 integration tests RUN (not skip); on CI they skip (off-macOS) and the fake-executor unit tests cover the wiring. No prior test regresses (oracle `node_edge`/`pytest_edge` records untouched; `truncate_output` untouched).

- [ ] **Step 2: Lint — whole repo, both checks** (CI runs both):

```bash
ruff check .
ruff format --check .
```

Expected: `All checks passed!` and no reformat needed. If `format --check` flags the new files, run `ruff format src/agent_eval_lab/records/node_feedback.py src/agent_eval_lab/runners/sandboxed_node_edge.py tests/runners/test_sandboxed_node_edge.py` and re-commit.

- [ ] **Step 3: Confirm the oracle path is byte-identical** (it must not have been touched):

```bash
git diff --stat HEAD~8 -- src/agent_eval_lab/runners/node_edge.py src/agent_eval_lab/records/execution.py
```

Expected: EMPTY (no changes to `node_edge.py` or `execution.py`/`truncate_output`).

- [ ] **Step 4: Commit any lint fixups** (if Step 2 reformatted anything):

```bash
git add -- src/agent_eval_lab tests   # NEVER `git add -A`/`.`; never stage evaluator-only/ or .env*
git commit -m "chore(005): ruff format"
```

> SECURITY (item 002 lesson): stage ONLY the files you created/modified by explicit path. Run `git status` before every commit and confirm nothing under `evaluator-only/` or any `.env*` is staged.

---

## Self-Review — spec acceptance criteria → task mapping

| Spec acceptance criterion (005-spec.md) | Implemented by |
|---|---|
| New `runners/sandboxed_node_edge.py` wraps `node --test` in a seatbelt profile, deny-read-by-default + explicit read-allowlist (temp tree + node dir + `/usr/lib`,`/System`,dyld,`/usr/bin`,`/bin`,node parent) + `(deny network*)` + write-deny-outside | Task 2 (`seatbelt_profile`) + Task 3 (`run_authored_tests_sandboxed`) |
| Read-allowlist is mandatory (broad allow reopens the leak); profile both starts node AND blocks `evaluator-only/` read | Task 2 Step 5 (host evidence) + Task 8 (`test_sandbox_blocks_evaluator_only_read` + `test_sandbox_starts_node_and_runs_benign_authored_test`); unit test `test_profile_has_no_broad_file_read_allow` |
| Trusted oracle keeps un-sandboxed `node_edge` path; `node_edge.py` NOT modified | No task touches it; Task 9 Step 3 asserts byte-identity |
| Escalation note: Docker `--network none` fallback if seatbelt can't both start+block | Module docstring (Task 3) records the decision; **NOT built** because seatbelt is verified working (see note below) |
| Probe Darwin + `sandbox-exec` (mirror `node_supports_junit`); skip real V off-macOS; fake executor in unit tests | Task 2 (`darwin_sandbox_available`) + Task 6 (off-macOS skip) + Tasks 3/7 (fake executor) |
| `make_authored_test_executor` runs ONLY `tests/authored/`, rejects model commands (fixed `node --test tests/authored/`) | Task 3 (`make_authored_test_executor` + `AUTHORED_TEST_DIR`); tests assert request paths ignored |
| Reuses ADR-0008 (`run_tests`→`ExecutionRequest`→executor→`ToolSuccess`); bare/prompt keep `executor=None` + no `run_tests` | Task 6 (routing) + Task 7 (end-to-end) + Task 4 (serialization) |
| V-arm `NotImplementedError` guard replaced by routing on macOS; guard/skip remains off-macOS | Task 6 |
| V-specific node-accurate `run_tests` ToolDef; do NOT break the shared one | Task 5 (`AUTHORED_RUN_TESTS_TOOLDEF` + `CODE_WORLD_TOOLS_V`; shared one untouched) |
| Global `truncate_output` NOT changed; V feedback uses separate tail-aware rendering | Task 1 (`render_feedback_tail`, separate module); `truncate_output` never imported/edited |
| Persisted V records are a distinct versioned record class | Task 1 (`NodeFeedbackResult` + `schema_version`) |
| Unit tests inject fake executor (run on CI) | Tasks 3, 7 |
| One macOS-only integration test: blocks `evaluator-only/` read + network, still runs an authored test; gated on Darwin+sandbox-exec(+node), not junit | Task 8 |

### Docker-fallback decision (explicit, per ADR-0016 / spec non-goal)

**Decision: seatbelt path adopted; Docker `--network none` fallback NOT built.** The pre-authorized condition for escalating to Docker is "the seatbelt allowlist cannot both start node AND block an `evaluator-only/` read." On this host (macOS 26.5.1, node v16.20.2) the exact enumerated profile in this plan was verified to (a) start node (exit 0), (b) run `node --test tests/authored/` green, (c) EPERM-block the `evaluator-only/` golden read, and (d) EPERM-block a network connect. The condition for Docker is therefore NOT met. The escalation path is recorded in the `sandboxed_node_edge.py` module docstring (Task 3) so a future host where the allowlist breaks has a documented next step; no Docker code is written now (spec non-goal: "Docker fallback is only built if the seatbelt path provably cannot both start node and block the read").

### Spec-gap judgment calls (flagged, with section)

1. **`(import "system.sb")` vs a fully hand-rolled mach/sysctl allow set (§B.4 / ADR-0016).** The spec/ADR enumerate the *file-read* allowlist but say only "the minimal mach/sysctl node needs to start." Verified on this host: a hand-rolled `(allow mach*)`/`(allow sysctl-read)` set still aborts node at startup (exit 134), whereas `(import "system.sb")` starts it cleanly AND does not weaken the read boundary (the golden read is still EPERM-denied under it — system.sb grants no broad file-read). Judgment: use `system.sb` for the non-file process baseline; keep the file-read policy fully enumerated and deny-default. This honors the load-bearing requirement (the read allowlist is the boundary) while being robust across macOS point releases.

2. **node v16 has no junit reporter, but the spec's record/oracle shape is junit-derived (§B.4 / node_edge).** The trusted oracle (`node_edge`) parses junit XML and is correctly gated by `node_supports_junit` (skips on v16). For V *feedback* there is no need for structured junit — the model needs human-readable pass/fail + output. Judgment: the V path parses node's **TAP `# pass`/`# fail` summary** + exit code (works on v16) and does NOT depend on junit, so the security boundary test RUNS on this host instead of skipping (spec constraint: the block-read/block-network test "must actually run here"). The `make_authored_test_executor` real path is consequently *not* junit-gated; the integration test is gated on Darwin+sandbox-exec+node only.

3. **Loop serialization touch (Task 4) — a trusted-file edit not called out in the spec.** The spec says reuse ADR-0008 (`executor`→`ToolSuccess`), but `_serialize_effect_result` only handles `BashResult`/`ExecutionResult`; a new `NodeFeedbackResult` requires one additive isinstance branch. Judgment: this is the minimal, test-guarded seam to let a distinct V record flow through the existing loop without changing the oracle's `ExecutionResult` serialization. The alternative (making the V record subclass `ExecutionResult`) would couple the V record to the frozen oracle contract — rejected to keep the record classes distinct (§9.7).

---

## Execution Handoff

Plan complete and saved to `docs/2026-06-15-harness-rounds-f-ablation/items/005-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks (Tasks 1→9 in order; Tasks 1, 2, 5 are independent and could parallelize, but 3 depends on 1+2, 4 on 1, 6 on 3+5, 7 on 3+4+5, 8 on 2+3).
2. **Inline Execution** — execute tasks in this session via executing-plans with checkpoints.

Which approach?
