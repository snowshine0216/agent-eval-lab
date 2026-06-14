# 009 — F-domain repo adapter (F1/F2 oracles + run-m1 wiring) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the second M1 domain (F) to the macro composite: env-free repo-task oracles for F1 (TC99396_10 image-compare → named-notification assertion) and F2 (diagnose-trace on failure), reusing the F3 `NodeExecutionSpec`/`node_edge` pattern, plus a `build_f_tasks(...)` task builder and `run-m1` F wiring.

**Architecture:** Each F oracle is a `NodeExecutionSpec` (item-004's F3 shape) whose `held_out_files` carry a `tests/wdio/package.json` + a held-out node `--test` file sourced ONLY from the gitignored `evaluator-only/web-dossier-golden/` store at grade time. The candidate's produced source (the spec/page-object/conf file) lives in `trajectory.final_state["files"]`; the held-out test reads it via `node:fs` from the materialized tree root and asserts on it **behaviorally** (extracts the changed method/block and executes it with injected fakes), so structural-only solutions are rejected (D24). `build_f_tasks` attaches the oracle to a `Task`; `run_m1` gains an F branch that produces the candidate file tree and grades it via the existing node oracle edge.

**Tech Stack:** Python 3.12 + `uv` (pytest, ruff); Node ≥20 (`node --test --test-reporter=junit`) via `export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"`.

---

## Background the implementer MUST internalize before starting

**The golden (post-fix `ebdfcbea`, parent `5b0c13a6`) changes exactly 5 files** (confirmed by `git diff --stat 5b0c13a6 ebdfcbea`):

| file | Δ | belongs to |
| --- | --- | --- |
| `tests/wdio/pageObjects/common/LibraryNotification.js` | +16 | **F1** |
| `tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js` | −8 | **F1** |
| `tests/wdio/utils/failure-analysis/report-to-allure.js` | +6/−2 | **F3** (already built, do NOT touch) |
| `tests/wdio/utils/failure-analysis/__tests__/report-to-allure.test.js` | +27 | **F3** (already built) |
| `tests/wdio/wdio.conf.ts` | +23 | **F2** |

So **F1 = the spec + page-object pair**, **F2 = `wdio.conf.ts`**, and the `report-to-allure.*` pair is F3 (item 004, green — leave it alone).

**F1 — what the fix does (derived from `F-golden.patch` + the `.golden` files):**
- `Snapshots_SendBackground.spec.js` TC99396_10: the pre-fix body called
  `await libraryNotification.waitForAllNotificationShown();` then
  `await takeScreenshotByElement(libraryNotification.getNotificationSection(), 'TC99396_8', 'Prompted Report Notification Section', tolerance);`
  (a flaky image-compare on a non-deterministic error toast). The golden **removes both** and replaces them with
  `await libraryNotification.waitForSnapshotFinalNotificationByName(snapshotInfo.largePromptedDocument.name);`
- `LibraryNotification.js` **adds** the method (this exact text is the +16 block):
  ```js
  async waitForSnapshotFinalNotificationByName(notificationName, timeout = 90000) {
      const interval = 2000;
      const maxRetry = Math.ceil(timeout / interval);
      for (let retry = 0; retry < maxRetry; retry++) {
          const ready = await this.getSnapshotReadyNotificationByName(notificationName);
          const error = await this.getSnapshotErrorNotificationByName(notificationName);
          if (ready.length > 0 || error.length > 0) return;
          await browser.pause(interval);
      }
      throw new Error(`No ready/error notification appeared for ${notificationName} within ${timeout}ms`);
  }
  ```
  The owner-specified semantics: resolve on a **named** snapshot reaching a **terminal** state — **ready OR error** — and throw if neither appears.

**F2 — what the fix does (the `wdio.conf.ts` +23 block in `runFailureAnalysisEngine`):**
- Pre-fix discarded the engine result: `await analyzeFailure({ … });`. The golden **captures it**: `const diagResult = await analyzeFailure({ … });`.
- The golden then adds a guarded terminal diagnose-trace:
  ```js
  // Print a diagnose trace to the terminal …
  try {
      const snap = snapshotFn();
      const failedReqs = (snap?.network ?? []).filter(
          (e) => typeof e.status !== 'number' || e.status < 200 || e.status >= 300
      );
      if (failedReqs.length > 0) {
          const lines = failedReqs
              .map((e) => `  ${e.method ?? '?'} ${e.url ?? ''} → ${e.status ?? '?'}`)
              .join('\n');
          logger.log(`[DiagTrace] Failed requests:\n${lines}`);
      }
      logger.log(`[DiagTrace] signal=${diagResult?.signal ?? 'n/a'} confidence=${diagResult?.confidence ?? 'n/a'}`);
  } catch (_diagLog) { /* terminal logging errors must never surface */ }
  ```
  Owner-specified trace shape: (a) capture the engine result into `diagResult`; (b) log only **non-2XX** requests under `[DiagTrace] Failed requests:`; (c) log `[DiagTrace] signal=… confidence=…` from the engine result.

**Why the F3 import-and-exercise approach does NOT work for F1/F2:** `report-to-allure.js` is a pure, self-contained module the F3 test `import`s. The F1 spec needs Jasmine + live browser + page objects; `LibraryNotification.js` extends `BasePage` and needs `$`/`browser`; `wdio.conf.ts` imports the whole engine + `@wdio/types` and runs at wdio boot. None is loadable under bare `node --test`. **Therefore F1/F2 held-out tests read the candidate's produced file as text via `node:fs` and behaviorally execute the changed unit** (extract the method/block, rebuild it as a standalone function over injected fakes, run it). This is NOT token-grepping: the page-object negative ("must resolve on error-only") and the F2 non-2XX filter are exercised, not matched. Token checks alone were proven evadable by a clever mutant during plan authoring — that is exactly the D24 trap to avoid.

**All four discrimination claims below were validated during plan authoring** against the real golden / `5b0c13a6` trees with node v22.22.2.

## Integrity guards (NEVER relax — the repo is PUBLIC)
- Held-out F1/F2 test files are sourced ONLY from `evaluator-only/web-dossier-golden/golden-files/` at grade time (D19/D33). They are NEW golden artifacts you will create from the patch (see Task 1); they are gitignored.
- The candidate base is pinned to `5b0c13a6` — **never** `m2021` HEAD (D32). Tests read it via `git -C ~/Documents/Repository/web-dossier show 5b0c13a6:<path>` (non-destructive; never checkout).
- The golden SOURCE files (the fixed spec/page-object/conf) are never placed in `held_out_files` — only the held-out TEST is (mirrors `test_build_f3_does_not_leak_golden_source_into_held_out`). The candidate supplies the source under test.
- Reuse `NodeExecutionSpec` / `AllOf` / `runners/node_edge` / `runners/node_oracle_edge` / `graders/node_execution`. Do NOT write a parallel runner.

## File Structure

| path | create/modify | responsibility |
| --- | --- | --- |
| `evaluator-only/web-dossier-golden/golden-files/f1.held_out.test.js` | create | F1 held-out node test (gitignored golden artifact) |
| `evaluator-only/web-dossier-golden/golden-files/f2.held_out.test.js` | create | F2 held-out node test (gitignored golden artifact) |
| `src/agent_eval_lab/datasets/f1_oracle.py` | create | `build_f1_verification(evaluator_store) -> AllOf` (mirrors `f3_oracle.py`) |
| `src/agent_eval_lab/datasets/f2_oracle.py` | create | `build_f2_verification(evaluator_store) -> AllOf` |
| `src/agent_eval_lab/datasets/f_tasks.py` | create | `build_f_tasks(evaluator_store) -> tuple[Task, ...]` — attaches F1/F2/F3 oracles to Tasks |
| `src/agent_eval_lab/experiments/m1_run.py` | modify | add F branch that produces the candidate tree and collects ReplacementOutcomes |
| `src/agent_eval_lab/cli.py:808-820` | modify | `_load_m1_domain_tasks` returns `{"D": …, "F": build_f_tasks(store)}` |
| `tests/datasets/test_f1_oracle.py` | create | golden⇒PASS / prefix⇒FAIL / mutant⇒FAIL + no-leak |
| `tests/datasets/test_f2_oracle.py` | create | golden⇒PASS / prefix⇒FAIL / 2 mutants⇒FAIL + no-leak |
| `tests/datasets/test_f_tasks.py` | create | task builder shape + oracle attachment |
| `tests/experiments/test_m1_run.py` | modify | F branch produces outcomes (run_dset + f-runner stubbed) |
| `tests/test_cli.py` | modify | `_load_m1_domain_tasks` returns an `"F"` key |

---

## Task 1: Stage the F1 + F2 held-out golden test files

These are NEW evaluator-only artifacts (gitignored). Derive them verbatim from the `.golden`/patch you read. They are the held-out oracle TESTs the `NodeExecutionSpec`s overlay onto the candidate tree.

**Files:**
- Create: `evaluator-only/web-dossier-golden/golden-files/f1.held_out.test.js`
- Create: `evaluator-only/web-dossier-golden/golden-files/f2.held_out.test.js`
- Modify: `evaluator-only/web-dossier-golden/golden-files/MANIFEST.txt` (append the two new filenames)

- [ ] **Step 1: Create the F1 held-out test**

Write `evaluator-only/web-dossier-golden/golden-files/f1.held_out.test.js` with EXACTLY this content:

```js
// HELD-OUT F1 oracle (evaluator-only, never candidate-visible). node --test.
// Grades the candidate's produced Snapshots_SendBackground.spec.js + LibraryNotification.js:
//   (1) TC99396_10 no longer performs the flaky image-compare screenshot,
//   (2) it waits on the NAMED terminal snapshot notification instead,
//   (3) the page object's waitForSnapshotFinalNotificationByName resolves on a
//       READY-only OR an ERROR-only terminal state, and throws when neither appears.
// (3) is BEHAVIORAL (extracts the method and runs it with injected fakes) so a
// structural-only / token-only solution cannot pass (D24).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const SPEC = 'tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js';
const PAGE = 'tests/wdio/pageObjects/common/LibraryNotification.js';
const spec = fs.readFileSync(SPEC, 'utf8');
const page = fs.readFileSync(PAGE, 'utf8');

// The TC99396_10 it-block body: from its [TC99396_10] marker to the next it('[TC99396_1…').
function tc10Body(src) {
    const start = src.indexOf('[TC99396_10]');
    assert.ok(start >= 0, 'TC99396_10 must exist');
    const next = src.indexOf("it('[TC99396_1", start + 1);
    return src.slice(start, next === -1 ? undefined : next);
}
const body = tc10Body(spec);

// Extract an async method's source by balancing braces from its opening '{'.
function methodSource(src, name) {
    const sig = new RegExp(`async\\s+${name}\\s*\\(([^)]*)\\)\\s*\\{`);
    const m = sig.exec(src);
    assert.ok(m, `${name} must be defined`);
    let i = src.indexOf('{', m.index), depth = 0;
    const open = i;
    for (; i < src.length; i++) {
        if (src[i] === '{') depth++;
        else if (src[i] === '}') { depth--; if (depth === 0) break; }
    }
    return { args: m[1], body: src.slice(open + 1, i) };
}

function buildMethod(src, name) {
    const { args, body: b } = methodSource(src, name);
    // standalone async fn over an injected `browser`; `this` supplied at call time.
    // eslint-disable-next-line no-new-func
    return new Function('browser', `return async function(${args}){ ${b} };`);
}

function makeThis(readySeq, errorSeq) {
    let r = 0, e = 0;
    return {
        getSnapshotReadyNotificationByName: async () => readySeq[Math.min(r++, readySeq.length - 1)],
        getSnapshotErrorNotificationByName: async () => errorSeq[Math.min(e++, errorSeq.length - 1)],
    };
}
const fakeBrowser = { pause: async () => {} };

test('TC99396_10 no longer performs an image-compare screenshot', () => {
    assert.ok(!/takeScreenshotByElement\s*\(/.test(body),
        'TC99396_10 must not call takeScreenshotByElement (flaky image-compare removed)');
});

test('TC99396_10 waits on the named terminal snapshot notification', () => {
    assert.ok(/waitForSnapshotFinalNotificationByName\s*\(/.test(body),
        'TC99396_10 must wait on the named final (ready/error) notification');
    assert.ok(/largePromptedDocument/.test(body),
        'the wait must be keyed on the largePromptedDocument under test');
});

test('page-object wait resolves on an ERROR-only terminal state', async () => {
    const fn = buildMethod(page, 'waitForSnapshotFinalNotificationByName');
    const self = makeThis([[]], [[{}]]); // ready empty, error present
    await assert.doesNotReject(fn(fakeBrowser).call(self, 'LargePromptedDocument', 200),
        'must return when only an ERROR notification appears');
});

test('page-object wait resolves on a READY-only terminal state', async () => {
    const fn = buildMethod(page, 'waitForSnapshotFinalNotificationByName');
    const self = makeThis([[{}]], [[]]);
    await assert.doesNotReject(fn(fakeBrowser).call(self, 'LargePromptedDocument', 200));
});

test('page-object wait throws when NEITHER terminal notification ever appears', async () => {
    const fn = buildMethod(page, 'waitForSnapshotFinalNotificationByName');
    const self = makeThis([[]], [[]]);
    await assert.rejects(fn(fakeBrowser).call(self, 'LargePromptedDocument', 200),
        /No ready\/error notification|Error/);
});
```

- [ ] **Step 2: Create the F2 held-out test**

Write `evaluator-only/web-dossier-golden/golden-files/f2.held_out.test.js` with EXACTLY this content:

```js
// HELD-OUT F2 oracle (evaluator-only, never candidate-visible). node --test.
// Grades the candidate's produced wdio.conf.ts diagnose-trace:
//   (1) analyzeFailure's result is captured into diagResult (not discarded),
//   (2) the trace logs only non-2XX requests under "[DiagTrace] Failed requests:",
//   (3) the trace logs "[DiagTrace] signal=<s> confidence=<c>" from the engine result,
//   (4) no failed-requests block when every request is 2XX.
// (2)-(4) are BEHAVIORAL: the diag block is extracted and executed with injected
// logger/snapshotFn/diagResult fakes (D24 — no token-only acceptance).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const CONF = 'tests/wdio/wdio.conf.ts';
const conf = fs.readFileSync(CONF, 'utf8');

test('analyzeFailure result is captured into diagResult', () => {
    assert.ok(/const\s+diagResult\s*=\s*await\s+analyzeFailure\s*\(/.test(conf),
        'runFailureAnalysisEngine must capture analyzeFailure() into diagResult');
});

// Extract the guarded [DiagTrace] block: the try{…}catch(_diagLog){…} that follows
// the "Print a diagnose trace" comment. Balance braces for each clause.
function extractDiagBlock(src) {
    const i = src.indexOf('try {', src.indexOf('Print a diagnose trace'));
    assert.ok(i >= 0, 'a guarded diagnose-trace block must follow analyzeFailure');
    let depth = 0, j = i;
    for (; j < src.length; j++) {
        if (src[j] === '{') depth++;
        else if (src[j] === '}') { depth--; if (depth === 0) break; }
    }
    const catchStart = src.indexOf('catch', j);
    assert.ok(catchStart >= 0, 'diag block must be guarded by catch(_diagLog)');
    let d2 = 0, k = src.indexOf('{', catchStart);
    for (; k < src.length; k++) {
        if (src[k] === '{') d2++;
        else if (src[k] === '}') { d2--; if (d2 === 0) break; }
    }
    return src.slice(i, k + 1);
}

function runDiag({ network, diagResult }) {
    const block = extractDiagBlock(conf);
    const logs = [];
    const logger = { log: (m) => logs.push(String(m)) };
    const snapshotFn = () => ({ network });
    // eslint-disable-next-line no-new-func
    const fn = new Function('logger', 'snapshotFn', 'diagResult', block);
    fn(logger, snapshotFn, diagResult);
    return logs.join('\n');
}

test('logs failed (non-2XX) requests and omits 2XX', () => {
    const out = runDiag({
        network: [
            { method: 'GET', url: 'https://app/ok', status: 200 },
            { method: 'POST', url: 'https://app/auth', status: 503 },
        ],
        diagResult: { signal: 'backend-error-present', confidence: 'high' },
    });
    assert.match(out, /\[DiagTrace\] Failed requests:/);
    assert.match(out, /POST https:\/\/app\/auth → 503/);
    assert.ok(!/app\/ok/.test(out), '2XX requests must not appear in the diag trace');
});

test('logs the engine signal and confidence', () => {
    const out = runDiag({
        network: [],
        diagResult: { signal: 'selector-drift', confidence: 'medium-high' },
    });
    assert.match(out, /\[DiagTrace\] signal=selector-drift confidence=medium-high/);
});

test('emits no failed-requests block when every request is 2XX', () => {
    const out = runDiag({
        network: [{ method: 'GET', url: 'https://app/ok', status: 200 }],
        diagResult: { signal: 'n/a', confidence: 'n/a' },
    });
    assert.ok(!/Failed requests:/.test(out), 'no failed-requests block when all 2XX');
});
```

- [ ] **Step 3: Append the two filenames to MANIFEST.txt**

Append two lines to `evaluator-only/web-dossier-golden/golden-files/MANIFEST.txt`:

```
f1.held_out.test.js
f2.held_out.test.js
```

- [ ] **Step 4: Smoke-test both held-out tests against the GOLDEN tree (expect PASS)**

Run (sets node 22, builds a throwaway candidate tree from the goldens, runs each held-out test):

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
GOLD=~/Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden/golden-files
T=$(mktemp -d); cd "$T"
mkdir -p tests/wdio/specs/regression/snapshot/snapshots tests/wdio/pageObjects/common
printf '{"type":"module"}\n' > tests/wdio/package.json
cp "$GOLD/Snapshots_SendBackground.spec.js.golden" tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js
cp "$GOLD/LibraryNotification.js.golden" tests/wdio/pageObjects/common/LibraryNotification.js
cp "$GOLD/wdio.conf.ts.golden" tests/wdio/wdio.conf.ts
cp "$GOLD/f1.held_out.test.js" tests/wdio/f1.held_out.test.js
cp "$GOLD/f2.held_out.test.js" tests/wdio/f2.held_out.test.js
node --test tests/wdio/f1.held_out.test.js 2>&1 | grep -E "# (tests|pass|fail)"
node --test tests/wdio/f2.held_out.test.js 2>&1 | grep -E "# (tests|pass|fail)"
cd - >/dev/null; rm -rf "$T"
```

Expected:
```
# tests 5
# pass 5
# fail 0
# tests 4
# pass 4
# fail 0
```

- [ ] **Step 5: Commit**

```bash
git add evaluator-only/web-dossier-golden/golden-files/MANIFEST.txt
# NOTE: f1.held_out.test.js / f2.held_out.test.js are gitignored (evaluator-only) and
# will NOT be staged — that is correct. Verify they are ignored:
git check-ignore evaluator-only/web-dossier-golden/golden-files/f1.held_out.test.js
git commit -m "chore(009): stage F1/F2 held-out oracle tests (evaluator-only)"
```

Expected: `git check-ignore` prints the path (confirming it is gitignored). If it prints nothing, STOP — the evaluator-only store is not ignored; do not proceed (a public-repo leak risk).

---

## Task 2: `f1_oracle.py` — `build_f1_verification`

**Files:**
- Create: `src/agent_eval_lab/datasets/f1_oracle.py`
- Test: `tests/datasets/test_f1_oracle.py`

- [ ] **Step 1: Write the failing no-leak + discrimination test**

Create `tests/datasets/test_f1_oracle.py`:

```python
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_eval_lab.datasets.f1_oracle import (
    F1_PAGE_REL,
    F1_SPEC_REL,
    build_f1_verification,
)
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
from agent_eval_lab.runners.node_edge import node_supports_junit  # noqa: E402

_REPO = Path.home() / "Documents/Repository/web-dossier"
_AGENT = Path.home() / "Documents/Repository/agent-eval-lab"
_STORE = _AGENT / "evaluator-only/web-dossier-golden"
_GF = _STORE / "golden-files"

requires_node = pytest.mark.skipif(
    not node_supports_junit()
    or not (_GF / "f1.held_out.test.js").exists()
    or not _REPO.exists(),
    reason="node>=20 + local web-dossier golden store + repo required",
)
requires_store = pytest.mark.skipif(
    not (_GF / "f1.held_out.test.js").exists(),
    reason="local web-dossier golden store required",
)


def _show(sha: str, rel: str) -> str:
    return subprocess.run(
        ["git", "-C", str(_REPO), "show", f"{sha}:{rel}"],
        check=True, capture_output=True, text=True,
    ).stdout


def _base(spec: str, page: str) -> dict[str, str]:
    return {
        "tests/wdio/package.json": '{"type":"module"}\n',
        F1_SPEC_REL: spec,
        F1_PAGE_REL: page,
    }


def _grade(verification, base) -> bool:
    traj = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state={"files": base},
    )
    verdicts = precompute_node_verdicts(verification=verification, trajectory=traj)
    return grade_trajectory(
        verification=verification, trajectory=traj, registry={}, verdicts=verdicts
    ).passed


@requires_store
def test_build_f1_does_not_leak_golden_source_into_held_out() -> None:
    v = build_f1_verification(_STORE)
    all_held = {p for spec in v.specs for p in spec.held_out_files}
    # the held-out files carry the F1 TEST, never the golden SOURCE under test
    assert any(p.endswith("f1.held_out.test.js") for p in all_held)
    assert F1_SPEC_REL not in all_held
    assert F1_PAGE_REL not in all_held


@requires_node
def test_f1_passes_golden_fails_prefix_and_mutants() -> None:
    v = build_f1_verification(_STORE)
    gspec = (_GF / "Snapshots_SendBackground.spec.js.golden").read_text("utf-8")
    gpage = (_GF / "LibraryNotification.js.golden").read_text("utf-8")
    pspec = _show("5b0c13a6", F1_SPEC_REL)
    ppage = _show("5b0c13a6", F1_PAGE_REL)

    assert _grade(v, _base(gspec, gpage)) is True  # golden fix PASSES
    assert _grade(v, _base(pspec, ppage)) is False  # pre-fix base FAILS

    # MUTANT keeps-image-compare: golden page object, but the spec re-adds the
    # flaky takeScreenshotByElement into TC99396_10 (contradiction).
    mut_spec = gspec.replace(
        "await libraryNotification.waitForSnapshotFinalNotificationByName"
        "(snapshotInfo.largePromptedDocument.name);",
        "await libraryNotification.waitForSnapshotFinalNotificationByName"
        "(snapshotInfo.largePromptedDocument.name);\n"
        "        await takeScreenshotByElement("
        "libraryNotification.getNotificationSection(), 'TC99396_8', 'x', tolerance);",
        1,
    )
    assert mut_spec != gspec
    assert _grade(v, _base(mut_spec, gpage)) is False  # keeps-image-compare FAILS

    # MUTANT error-path-gutted: page-object resolves on READY only, not ERROR
    # (weakens the owner semantics; the behavioral negative catches it).
    mut_page = gpage.replace(
        "if (ready.length > 0 || error.length > 0) return;",
        "if (ready.length > 0) return;",
    )
    assert mut_page != gpage
    assert _grade(v, _base(gspec, mut_page)) is False  # error-path-gutted FAILS
```

- [ ] **Step 2: Run it to verify it fails**

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
uv run pytest tests/datasets/test_f1_oracle.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.datasets.f1_oracle'`.

- [ ] **Step 3: Write `f1_oracle.py`**

Create `src/agent_eval_lab/datasets/f1_oracle.py`:

```python
"""Assemble the F1 oracle verification (§4.1 / D24 / D31).

build_f1_verification(evaluator_store) returns the AllOf that build_f_tasks
attaches to the F1 task. The held-out F1 TEST is read from the evaluator store
and shipped as the only oracle file (plus the minimal tests/wdio/package.json);
the golden SOURCE (the fixed spec/page-object) is never shipped — the candidate's
own produced files are the source under test. D19: nothing here writes into a
candidate-visible location.
"""

from pathlib import Path

from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec

F1_SPEC_REL = (
    "tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js"
)
F1_PAGE_REL = "tests/wdio/pageObjects/common/LibraryNotification.js"
F1_TEST_REL = "tests/wdio/f1.held_out.test.js"
WDIO_PKG_REL = "tests/wdio/package.json"
WDIO_PKG_CONTENT = '{"type":"module"}\n'

_GOLDEN_TEST_REL = "golden-files/f1.held_out.test.js"


def build_f1_verification(evaluator_store: Path) -> AllOf:
    """Return the F1 AllOf: one NodeExecutionSpec running the held-out F1 test."""
    held_out_test = (evaluator_store / _GOLDEN_TEST_REL).read_text(encoding="utf-8")
    spec = NodeExecutionSpec(
        held_out_files={
            WDIO_PKG_REL: WDIO_PKG_CONTENT,
            F1_TEST_REL: held_out_test,
        },
        test_paths=(F1_TEST_REL,),
    )
    return AllOf(specs=(spec,))
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
uv run pytest tests/datasets/test_f1_oracle.py -v
```

Expected: PASS (3 passed). If node is absent, `test_f1_passes_golden_fails_prefix_and_mutants` SKIPS and only the no-leak test runs — that is acceptable in CI.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/datasets/f1_oracle.py tests/datasets/test_f1_oracle.py
git commit -m "feat(009): F1 oracle (image-compare removed + named-notification wait)"
```

---

## Task 3: `f2_oracle.py` — `build_f2_verification`

**Files:**
- Create: `src/agent_eval_lab/datasets/f2_oracle.py`
- Test: `tests/datasets/test_f2_oracle.py`

- [ ] **Step 1: Write the failing test**

Create `tests/datasets/test_f2_oracle.py`:

```python
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_eval_lab.datasets.f2_oracle import F2_CONF_REL, build_f2_verification
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
from agent_eval_lab.runners.node_edge import node_supports_junit  # noqa: E402

_REPO = Path.home() / "Documents/Repository/web-dossier"
_AGENT = Path.home() / "Documents/Repository/agent-eval-lab"
_STORE = _AGENT / "evaluator-only/web-dossier-golden"
_GF = _STORE / "golden-files"

requires_node = pytest.mark.skipif(
    not node_supports_junit()
    or not (_GF / "f2.held_out.test.js").exists()
    or not _REPO.exists(),
    reason="node>=20 + local web-dossier golden store + repo required",
)
requires_store = pytest.mark.skipif(
    not (_GF / "f2.held_out.test.js").exists(),
    reason="local web-dossier golden store required",
)


def _show(sha: str, rel: str) -> str:
    return subprocess.run(
        ["git", "-C", str(_REPO), "show", f"{sha}:{rel}"],
        check=True, capture_output=True, text=True,
    ).stdout


def _base(conf: str) -> dict[str, str]:
    return {"tests/wdio/package.json": '{"type":"module"}\n', F2_CONF_REL: conf}


def _grade(verification, base) -> bool:
    traj = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state={"files": base},
    )
    verdicts = precompute_node_verdicts(verification=verification, trajectory=traj)
    return grade_trajectory(
        verification=verification, trajectory=traj, registry={}, verdicts=verdicts
    ).passed


@requires_store
def test_build_f2_does_not_leak_golden_source_into_held_out() -> None:
    v = build_f2_verification(_STORE)
    all_held = {p for spec in v.specs for p in spec.held_out_files}
    assert any(p.endswith("f2.held_out.test.js") for p in all_held)
    assert F2_CONF_REL not in all_held


@requires_node
def test_f2_passes_golden_fails_prefix_and_mutants() -> None:
    v = build_f2_verification(_STORE)
    gconf = (_GF / "wdio.conf.ts.golden").read_text("utf-8")
    pconf = _show("5b0c13a6", F2_CONF_REL)

    assert _grade(v, _base(gconf)) is True  # golden fix PASSES
    assert _grade(v, _base(pconf)) is False  # pre-fix base FAILS

    # MUTANT surfaces-2xx: keeps the diag block but drops the non-2XX filter so
    # ALL requests (incl 200s) are logged (contradicts the owner trace shape).
    mut_c = gconf.replace(
        "const failedReqs = (snap?.network ?? []).filter(\n"
        "                (e) => typeof e.status !== 'number' "
        "|| e.status < 200 || e.status >= 300\n"
        "            );",
        "const failedReqs = (snap?.network ?? []);",
    )
    assert mut_c != gconf
    assert _grade(v, _base(mut_c)) is False  # surfaces-2xx FAILS

    # MUTANT omits-signal-line: removes the [DiagTrace] signal=… log entirely
    # (wrong trace shape — the engine result is not surfaced).
    import re

    mut_d = re.sub(
        r"logger\.log\(\s*`\[DiagTrace\] signal=.*?`\s*\);",
        "/* omitted */;",
        gconf,
        flags=re.S,
    )
    assert mut_d != gconf
    assert _grade(v, _base(mut_d)) is False  # omits-signal-line FAILS
```

- [ ] **Step 2: Run it to verify it fails**

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
uv run pytest tests/datasets/test_f2_oracle.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.datasets.f2_oracle'`.

- [ ] **Step 3: Write `f2_oracle.py`**

Create `src/agent_eval_lab/datasets/f2_oracle.py`:

```python
"""Assemble the F2 oracle verification (§4.1 / D24 / D31).

build_f2_verification(evaluator_store) returns the AllOf that build_f_tasks
attaches to the F2 task. The held-out F2 TEST is the only oracle file shipped
(plus the minimal tests/wdio/package.json); the golden wdio.conf.ts SOURCE is
never shipped — the candidate's produced conf is the source under test (D19).
"""

from pathlib import Path

from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec

F2_CONF_REL = "tests/wdio/wdio.conf.ts"
F2_TEST_REL = "tests/wdio/f2.held_out.test.js"
WDIO_PKG_REL = "tests/wdio/package.json"
WDIO_PKG_CONTENT = '{"type":"module"}\n'

_GOLDEN_TEST_REL = "golden-files/f2.held_out.test.js"


def build_f2_verification(evaluator_store: Path) -> AllOf:
    """Return the F2 AllOf: one NodeExecutionSpec running the held-out F2 test."""
    held_out_test = (evaluator_store / _GOLDEN_TEST_REL).read_text(encoding="utf-8")
    spec = NodeExecutionSpec(
        held_out_files={
            WDIO_PKG_REL: WDIO_PKG_CONTENT,
            F2_TEST_REL: held_out_test,
        },
        test_paths=(F2_TEST_REL,),
    )
    return AllOf(specs=(spec,))
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
uv run pytest tests/datasets/test_f2_oracle.py -v
```

Expected: PASS (3 passed; or 1 passed + 1 skipped if node absent).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/datasets/f2_oracle.py tests/datasets/test_f2_oracle.py
git commit -m "feat(009): F2 oracle (engine diagnose-trace shape on failure)"
```

---

## Task 4: `f_tasks.py` — `build_f_tasks` attaching F1/F2/F3 oracles to Tasks

The F-domain task builder mirrors `build_cmc_tasks` (the D builder): one `Task` per repo
fix, each carrying its node oracle as `verification`. F3's oracle already exists
(`build_f3_verification`); F1/F2 use the new builders.

The candidate-visible `TaskInput` describes the repo fix in prose (the candidate, at
the post-merge execute phase, will produce a file tree). The `initial_state` carries the
pinned candidate base SHA so the runner (Task 5) can reconstruct the `5b0c13a6` tree.

**Files:**
- Create: `src/agent_eval_lab/datasets/f_tasks.py`
- Test: `tests/datasets/test_f_tasks.py`

- [ ] **Step 1: Write the failing test**

Create `tests/datasets/test_f_tasks.py`:

```python
from pathlib import Path

import pytest

from agent_eval_lab.datasets.f_tasks import build_f_tasks
from agent_eval_lab.tasks.schema import AllOf

_STORE = Path.home() / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden"

requires_store = pytest.mark.skipif(
    not (_STORE / "golden-files" / "f1.held_out.test.js").exists(),
    reason="local web-dossier golden store required",
)


@requires_store
def test_build_f_tasks_returns_three_node_oracle_tasks() -> None:
    tasks = build_f_tasks(evaluator_store=_STORE)
    assert [t.id for t in tasks] == ["f-f1", "f-f2", "f-f3"]
    for t in tasks:
        assert t.capability == "repo_fix"
        assert isinstance(t.verification, AllOf)  # node-execution AllOf
        assert t.metadata.split == "held_out"
        # the pinned candidate base SHA travels on initial_state (D32)
        assert t.initial_state is not None
        assert t.initial_state["candidate_base_sha"].startswith("5b0c13a6")
        assert t.initial_state["repo"] == "web-dossier"


@requires_store
def test_f_tasks_carry_the_repo_relative_target_paths() -> None:
    tasks = {t.id: t for t in build_f_tasks(evaluator_store=_STORE)}
    assert "Snapshots_SendBackground.spec.js" in tasks["f-f1"].initial_state["target_paths"][0]
    assert tasks["f-f2"].initial_state["target_paths"] == ("tests/wdio/wdio.conf.ts",)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/datasets/test_f_tasks.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.datasets.f_tasks'`.

- [ ] **Step 3: Write `f_tasks.py`**

Create `src/agent_eval_lab/datasets/f_tasks.py`:

```python
"""Assemble the 3 F-domain Tasks (§4.1): each web-dossier repo fix paired with its
held-out node oracle. Mirrors datasets/cmc_dset.build_cmc_tasks (the D builder).

The candidate-visible TaskInput describes the fix in prose; the held-out ORACLE
(the node test) is read by the per-fix build_fN_verification from the
permission-isolated evaluator store (D19/D33). initial_state pins the candidate
base SHA (5b0c13a6, D32) and the repo-relative target paths so the F runner can
reconstruct the candidate workspace without ever touching m2021 HEAD.
"""

from pathlib import Path

from agent_eval_lab.datasets.f1_oracle import (
    F1_PAGE_REL,
    F1_SPEC_REL,
    build_f1_verification,
)
from agent_eval_lab.datasets.f2_oracle import F2_CONF_REL, build_f2_verification
from agent_eval_lab.datasets.f3_oracle import F3_SOURCE_REL, build_f3_verification
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import Task, TaskInput, TaskMetadata

_CANDIDATE_BASE_SHA = "5b0c13a6bc9e7b9a3c60083da511f3efd0d39505"

_SYSTEM = (
    "You are fixing a flaky end-to-end test in the web-dossier wdio suite. You have "
    "a single tool: `bash`. The repo is checked out at a frozen base commit. Make the "
    "owner-specified change, leaving all other layers untouched."
)

_F1_USER = (
    "In tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js, "
    "test case [TC99396_10] asserts on a non-deterministic error notification via a flaky "
    "image comparison (takeScreenshotByElement). Replace the image comparison with a "
    "deterministic wait on the NAMED snapshot reaching a terminal state (ready or error), "
    "adding a waitForSnapshotFinalNotificationByName(name) helper to "
    "tests/wdio/pageObjects/common/LibraryNotification.js."
)
_F2_USER = (
    "In tests/wdio/wdio.conf.ts, runFailureAnalysisEngine discards the failure-analysis "
    "engine result. Capture it and print a terminal diagnose trace: log only failed "
    "(non-2XX) requests under '[DiagTrace] Failed requests:', then log "
    "'[DiagTrace] signal=<signal> confidence=<confidence>' from the engine result. Guard "
    "the whole trace so a logging error never breaks afterTest/afterHook."
)
_F3_USER = (
    "In tests/wdio/utils/failure-analysis/report-to-allure.js, the network attachment "
    "lists every request. Surface only failed (non-2XX) requests so a 503 is not buried "
    "under hundreds of 200s, and emit no network attachment when all requests succeed."
)


def _task(*, task_id: str, user: str, verification, target_paths: tuple[str, ...]) -> Task:
    return Task(
        id=task_id,
        capability="repo_fix",
        input=TaskInput(
            messages=(
                MessageTurn(role="system", content=_SYSTEM),
                MessageTurn(role="user", content=user),
            ),
            available_tools=("bash",),
        ),
        verification=verification,
        metadata=TaskMetadata(
            split="held_out",
            version="f-domain-v1",
            provenance="web-dossier PR #23483 (pre-fix 5b0c13a6)",
        ),
        initial_state={
            "repo": "web-dossier",
            "candidate_base_sha": _CANDIDATE_BASE_SHA,
            "target_paths": target_paths,
        },
    )


def build_f_tasks(*, evaluator_store: Path) -> tuple[Task, ...]:
    return (
        _task(
            task_id="f-f1",
            user=_F1_USER,
            verification=build_f1_verification(evaluator_store),
            target_paths=(F1_SPEC_REL, F1_PAGE_REL),
        ),
        _task(
            task_id="f-f2",
            user=_F2_USER,
            verification=build_f2_verification(evaluator_store),
            target_paths=(F2_CONF_REL,),
        ),
        _task(
            task_id="f-f3",
            user=_F3_USER,
            verification=build_f3_verification(evaluator_store),
            target_paths=(F3_SOURCE_REL,),
        ),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/datasets/test_f_tasks.py -v
```

Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/datasets/f_tasks.py tests/datasets/test_f_tasks.py
git commit -m "feat(009): build_f_tasks — attach F1/F2/F3 node oracles to F-domain tasks"
```

---

## Task 5: `run_m1` F branch — produce the candidate tree and grade via the node oracle

`run_m1` currently runs only D and skips F/B. Add an F branch. The live candidate
F-runs across the roster are the POST-MERGE execute phase (non-goal here); this branch
is the wiring + a deterministic local-grade path. The branch is `run_dset`-shaped: per
F task, reconstruct the pinned `5b0c13a6` candidate tree, apply the candidate's edit (at
execute time this is the model's produced tree; here we materialize the base and grade),
and wrap each grade in a `ReplacementOutcome`. It is fully stubbed in unit tests.

We extract the F runner into `runners/f_run.py` so `run_m1` stays small and the runner is
unit-testable in isolation (mirrors `runners/dset_run.py`). The runner takes an injectable
`build_tree_fn` so tests stub tree production without a network/model call.

**Files:**
- Create: `src/agent_eval_lab/runners/f_run.py`
- Modify: `src/agent_eval_lab/experiments/m1_run.py` (add the F branch)
- Test: `tests/runners/test_f_run.py`
- Test: `tests/experiments/test_m1_run.py` (add an F-branch case)

- [ ] **Step 1: Write the failing f_run test**

Create `tests/runners/test_f_run.py`:

```python
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_eval_lab.datasets.f_tasks import build_f_tasks
from agent_eval_lab.runners.f_run import prefix_candidate_tree, run_f
from agent_eval_lab.runners.multi_run import ReplacementOutcome

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
from agent_eval_lab.runners.node_edge import node_supports_junit  # noqa: E402

_REPO = Path.home() / "Documents/Repository/web-dossier"
_STORE = Path.home() / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden"
_GF = _STORE / "golden-files"

requires_node = pytest.mark.skipif(
    not node_supports_junit()
    or not (_GF / "f1.held_out.test.js").exists()
    or not _REPO.exists(),
    reason="node>=20 + local web-dossier golden store + repo required",
)
requires_store = pytest.mark.skipif(
    not (_GF / "f1.held_out.test.js").exists(),
    reason="local web-dossier golden store required",
)


@requires_store
def test_run_f_yields_one_outcome_per_task_with_stubbed_tree() -> None:
    tasks = build_f_tasks(evaluator_store=_STORE)

    # stub tree producer: return an empty tree (no candidate edit) -> grade FAILS,
    # but the loop still yields a well-formed ReplacementOutcome per task.
    def build_tree_fn(task):
        return {"tests/wdio/package.json": '{"type":"module"}\n'}

    outcomes = list(run_f(tasks=tasks, build_tree_fn=build_tree_fn, k=1))
    assert len(outcomes) == len(tasks)
    assert all(isinstance(o, ReplacementOutcome) for o in outcomes)
    # empty candidate tree -> the node oracle cannot pass
    assert all(not o.valid_runs[0].grade.passed for o in outcomes)


@requires_node
def test_run_f_golden_tree_passes_f1() -> None:
    tasks = [t for t in build_f_tasks(evaluator_store=_STORE) if t.id == "f-f1"]
    gspec = (_GF / "Snapshots_SendBackground.spec.js.golden").read_text("utf-8")
    gpage = (_GF / "LibraryNotification.js.golden").read_text("utf-8")

    def build_tree_fn(task):
        tree = prefix_candidate_tree(task, repo=_REPO)  # pinned 5b0c13a6 base
        # apply the golden fix (stands in for the candidate's edit)
        tree["tests/wdio/specs/regression/snapshot/snapshots/"
             "Snapshots_SendBackground.spec.js"] = gspec
        tree["tests/wdio/pageObjects/common/LibraryNotification.js"] = gpage
        return tree

    outcomes = list(run_f(tasks=tasks, build_tree_fn=build_tree_fn, k=1))
    assert outcomes[0].valid_runs[0].grade.passed is True


@requires_node
def test_prefix_candidate_tree_pins_5b0c13a6_not_head() -> None:
    [t] = [t for t in build_f_tasks(evaluator_store=_STORE) if t.id == "f-f2"]
    tree = prefix_candidate_tree(t, repo=_REPO)
    conf = tree["tests/wdio/wdio.conf.ts"]
    # the pre-fix conf discards the engine result (no `const diagResult =`)
    assert "const diagResult = await analyzeFailure" not in conf
    # sanity: it is the same bytes git emits for the pinned sha
    expected = subprocess.run(
        ["git", "-C", str(_REPO), "show", "5b0c13a6:tests/wdio/wdio.conf.ts"],
        check=True, capture_output=True, text=True,
    ).stdout
    assert conf == expected
```

- [ ] **Step 2: Run it to verify it fails**

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
uv run pytest tests/runners/test_f_run.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.runners.f_run'`.

- [ ] **Step 3: Write `f_run.py`**

Create `src/agent_eval_lab/runners/f_run.py`:

```python
"""EDGE: run the F-domain repo-fix tasks and grade them via the node oracle.

Per F task: a candidate file tree is produced (build_tree_fn — the model's edit at
execute time; injectable so tests stub it), graded by the held-out NodeExecutionSpec
via precompute_node_verdicts + grade_trajectory, and wrapped one ReplacementOutcome
per task (k valid runs of the SAME deterministic tree — the node oracle is env-free
so every trial is valid and identical; pass^k is well-defined). The candidate base is
pinned to 5b0c13a6 (D32) via prefix_candidate_tree; m2021 HEAD is never read.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts
from agent_eval_lab.tasks.schema import Task

_CANDIDATE_BASE_SHA = "5b0c13a6bc9e7b9a3c60083da511f3efd0d39505"


def prefix_candidate_tree(task: Task, *, repo: Path) -> dict[str, str]:
    """Reconstruct the candidate workspace at the pinned base SHA (D32).

    Reads ONLY the task's target_paths from `git show 5b0c13a6:<path>` plus the
    minimal tests/wdio/package.json. Never checks out; never reads m2021 HEAD.
    """
    assert task.initial_state is not None
    assert task.initial_state["candidate_base_sha"] == _CANDIDATE_BASE_SHA
    tree: dict[str, str] = {"tests/wdio/package.json": '{"type":"module"}\n'}
    for rel in task.initial_state["target_paths"]:
        tree[rel] = subprocess.run(
            ["git", "-C", str(repo), "show", f"{_CANDIDATE_BASE_SHA}:{rel}"],
            check=True, capture_output=True, text=True,
        ).stdout
    return tree


def _grade_tree(task: Task, files: Mapping[str, str]) -> RunResult:
    traj = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state={"files": dict(files)},
    )
    verdicts = precompute_node_verdicts(
        verification=task.verification, trajectory=traj
    )
    grade = grade_trajectory(
        verification=task.verification, trajectory=traj, registry={}, verdicts=verdicts
    )
    return RunResult(
        task_id=task.id,
        condition_id="(f-local)",
        run_index=0,
        trajectory=traj,
        grade=grade,
    )


def run_f(
    *,
    tasks: Sequence[Task],
    build_tree_fn: Callable[[Task], Mapping[str, str]],
    k: int,
) -> Iterator[ReplacementOutcome]:
    """Yield one ReplacementOutcome per F task (env-free → k identical valid runs)."""
    for task in tasks:
        files = build_tree_fn(task)
        run = _grade_tree(task, files)
        runs = tuple(
            RunResult(
                task_id=run.task_id,
                condition_id=run.condition_id,
                run_index=i,
                trajectory=run.trajectory,
                grade=run.grade,
            )
            for i in range(k)
        )
        attempts = tuple(
            TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
        )
        yield ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)
```

- [ ] **Step 4: Verify `RunResult` / `ReplacementOutcome` / `TrialAttempt` field names**

Before running, confirm the dataclass signatures used above match the codebase (they were copied from `cli.py:_outcomes_from_runs` and `dset_run.py`). Run:

```bash
uv run python -c "
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
import inspect
print('RunResult:', [f for f in RunResult.__dataclass_fields__])
print('ReplacementOutcome:', [f for f in ReplacementOutcome.__dataclass_fields__])
print('TrialAttempt:', [f for f in TrialAttempt.__dataclass_fields__])
"
```

Expected: `RunResult: ['task_id', 'condition_id', 'run_index', 'trajectory', 'grade']`, `ReplacementOutcome: ['valid_runs', 'attempts', 'void']`, `TrialAttempt: ['attempt_index', 'valid', 'run']`. If any differ, adjust `f_run.py` to match before continuing.

- [ ] **Step 5: Run the f_run test to verify it passes**

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
uv run pytest tests/runners/test_f_run.py -v
```

Expected: PASS (3 passed; node-gated cases skip if node absent).

- [ ] **Step 6: Wire the F branch into `run_m1`**

Edit `src/agent_eval_lab/experiments/m1_run.py`. Add the import near the existing imports:

```python
from agent_eval_lab.runners.f_run import prefix_candidate_tree, run_f
```

Add an `f_repo` parameter to `run_m1`'s signature (after `evaluator_store: Path | None`):

```python
    evaluator_store: Path | None,
    f_repo: Path | None = None,
```

Replace the comment line `# F / B: no domain runner yet (items 004/006). Absent -> skipped, never a crash.` with the F branch:

```python
        f_tasks = domain_tasks.get("F")
        if f_tasks and f_repo is not None:

            def _build_tree(task):
                # POST-MERGE execute phase produces the model's edited tree here;
                # absent a candidate edit, grade the pinned base tree (deterministic).
                return prefix_candidate_tree(task, repo=f_repo)

            out[cond]["F"] = tuple(
                run_f(tasks=tuple(f_tasks), build_tree_fn=_build_tree, k=k_valid)
            )
        # B: no domain runner yet (item 010). Absent -> skipped, never a crash.
```

- [ ] **Step 7: Add the F-branch case to `tests/experiments/test_m1_run.py`**

Read `tests/experiments/test_m1_run.py` first to match its existing stub style (it stubs `run_dset`). Add this test (adjust the monkeypatch target/imports to match the file's existing pattern — the existing D test shows how `run_dset` is stubbed):

```python
def test_run_m1_f_branch_yields_outcomes(monkeypatch) -> None:
    from agent_eval_lab.experiments import m1_run
    from agent_eval_lab.runners.config import ProviderConfig
    from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.tasks.schema import (
        NodeExecutionSpec, Task, TaskInput, TaskMetadata,
    )

    def _outcome(task):
        traj = Trajectory(
            turns=(), usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=0, stop_reason="completed", final_state={"files": {}},
        )
        run = RunResult(
            task_id=task.id, condition_id="c", run_index=0, trajectory=traj,
            grade=GradeResult(grader_id="node_execution", passed=True, score=1.0,
                              evidence={}, failure_reason=None),
        )
        return ReplacementOutcome(
            valid_runs=(run,),
            attempts=(TrialAttempt(attempt_index=0, valid=True, run=run),),
            void=False,
        )

    # stub run_f so no node/subprocess is needed in this unit test
    monkeypatch.setattr(
        m1_run, "run_f",
        lambda *, tasks, build_tree_fn, k: iter(_outcome(t) for t in tasks),
    )

    f_task = Task(
        id="f-f1", capability="repo_fix",
        input=TaskInput(messages=(), available_tools=("bash",)),
        verification=NodeExecutionSpec(held_out_files={}, test_paths=()),
        metadata=TaskMetadata(split="held_out", version="f-domain-v1", provenance="x"),
        initial_state={"candidate_base_sha": "5b0c13a6", "target_paths": (),
                       "repo": "web-dossier"},
    )
    cfg = ProviderConfig(
        id="local", label="local", base_url="http://x", model_id="m",
        api_key_env=None,
    )
    out = m1_run.run_m1(
        configs=(cfg,), domain_tasks={"F": (f_task,)}, http_client=None,
        k_valid=2, max_invalid_rate=0.5, temperature=0.0, max_tokens=64,
        health_probe_fn=None, reference_sha256=None, evaluator_store=None,
        f_repo=__import__("pathlib").Path("/fake/repo"),
    )
    [(cond, by_domain)] = out.items()
    assert "F" in by_domain
    assert by_domain["F"][0].valid_runs[0].grade.passed is True
```

NOTE: the `ProviderConfig(...)` constructor args above are illustrative — read `src/agent_eval_lab/runners/config.py` `ProviderConfig` and use its ACTUAL fields, or reuse a `PROVIDERS[...]` entry as the existing D test does.

- [ ] **Step 8: Run the m1_run tests to verify they pass**

```bash
uv run pytest tests/experiments/test_m1_run.py -v
```

Expected: PASS (existing D tests + the new F test).

- [ ] **Step 9: Commit**

```bash
git add src/agent_eval_lab/runners/f_run.py src/agent_eval_lab/experiments/m1_run.py \
        tests/runners/test_f_run.py tests/experiments/test_m1_run.py
git commit -m "feat(009): run_m1 F branch — env-free node-oracle grade over pinned base"
```

---

## Task 6: `cli._load_m1_domain_tasks` returns the F key

**Files:**
- Modify: `src/agent_eval_lab/cli.py:808-820` (`_load_m1_domain_tasks`)
- Modify: `src/agent_eval_lab/cli.py:850` area + `_run_m1_command` (pass `f_repo` to `run_m1`)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Read `tests/test_cli.py` for the existing `_load_m1_domain_tasks` test (it stubs `cfg`/`store`). Add:

```python
def test_load_m1_domain_tasks_includes_f(tmp_path, monkeypatch) -> None:
    from agent_eval_lab import cli

    store = Path.home() / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden"
    if not (store / "golden-files" / "f1.held_out.test.js").exists():
        import pytest
        pytest.skip("local web-dossier golden store required")

    class _Store:
        path = str(store)

    class _Cfg:
        store = _Store()

    domain_tasks = cli._load_m1_domain_tasks(args=None, cfg=_Cfg())
    assert "D" in domain_tasks
    assert "F" in domain_tasks
    assert [t.id for t in domain_tasks["F"]] == ["f-f1", "f-f2", "f-f3"]
```

NOTE: confirm `_load_m1_domain_tasks`'s `cfg.store.path` access and the questions-file
path it uses for D — reuse the exact `store` shape the existing D test relies on.

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/test_cli.py::test_load_m1_domain_tasks_includes_f -v
```

Expected: FAIL with `KeyError: 'F'` / `assert 'F' in {'D': …}`.

- [ ] **Step 3: Modify `_load_m1_domain_tasks`**

Edit `src/agent_eval_lab/cli.py`. In `_load_m1_domain_tasks`, change the import line and the return:

```python
    from agent_eval_lab.datasets.cmc_dset import build_cmc_tasks
    from agent_eval_lab.datasets.f_tasks import build_f_tasks

    store = Path(cfg.store.path)
    tasks = build_cmc_tasks(
        evaluator_store=store,
        questions_path=Path("examples/datasets/cmc-docs-questions.txt"),
    )
    f_tasks = build_f_tasks(evaluator_store=store)
    return {"D": tasks, "F": f_tasks}
```

Update the docstring's `F/B return no tasks until items 004/006 land` line to:
`D = CMC docs tasks; F = web-dossier repo-fix tasks (009). B returns no tasks until 010.`

- [ ] **Step 4: Pass `f_repo` to `run_m1` in `_run_m1_command`**

Edit `src/agent_eval_lab/cli.py` `_run_m1_command`. The F repo path is fixed to the
local clone (the post-merge execute phase reads the pinned base from it). Add the
argument to the `run_m1(...)` call:

```python
            evaluator_store=store,
            f_repo=Path.home() / "Documents/Repository/web-dossier",
```

(Place `f_repo=...` immediately after the existing `evaluator_store=store,` line inside
the `run_m1(...)` call.)

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest tests/test_cli.py::test_load_m1_domain_tasks_includes_f -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/test_cli.py
git commit -m "feat(009): wire F into _load_m1_domain_tasks + run-m1 (f_repo pinned clone)"
```

---

## Task 7: Full-suite green + ruff clean (refactor checkpoint)

**Files:** none new — verification only.

- [ ] **Step 1: Run ruff over the whole tree**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

Expected: `All checks passed!` and no files would be reformatted. If format fails, run
`uv run ruff format src/ tests/` and re-stage.

- [ ] **Step 2: Run the full test suite**

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
uv run pytest -q
```

Expected: all pass. The known oracle-subprocess timeout flakes (node `--test` under load)
are the ONLY acceptable failures and are already guarded in CI exactly as for F3; if you
see a timeout-classified failure in a node oracle test, re-run that file once:
`uv run pytest tests/datasets/test_f1_oracle.py tests/datasets/test_f2_oracle.py tests/runners/test_f_run.py -q`.

- [ ] **Step 3: Verify no F3 / D / report-engine regression specifically**

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"
uv run pytest tests/datasets/test_f3_oracle.py tests/runners/test_node_oracle_edge.py \
              tests/reports/ tests/runners/test_dset_run.py -q
```

Expected: all pass (009 must not regress 004/005/008).

- [ ] **Step 4: Confirm the golden is never reachable from a candidate-visible location**

```bash
grep -rn "f1.held_out\|f2.held_out\|web-dossier-golden\|5b0c13a6" src/ | grep -v "_oracle.py\|f_tasks.py\|f_run.py\|cli.py"
git check-ignore evaluator-only/web-dossier-golden/golden-files/f1.held_out.test.js
```

Expected: the grep returns nothing outside the four wiring modules (no leak into a tracked,
candidate-visible path); `git check-ignore` prints the path (the held-out test is ignored).

- [ ] **Step 5: Final commit (if ruff reformatted anything)**

```bash
git add -A
git commit -m "chore(009): ruff format + full-suite green for F-domain" || echo "nothing to commit"
```

---

## Self-Review (completed during authoring)

- **Spec coverage:** AC1 (F1 golden-discriminating) → Task 2; AC2 (F2 golden-discriminating + engine reconciled) → Task 3 + Task 7 Step 3; AC3 (F wired into run-m1: `_load_m1_domain_tasks` + `run_m1` F runner + `build_f_tasks`) → Tasks 4/5/6; the report engine already renders F (`_DOMAINS=("F","D","B")`, `domains_not_run` → "not yet run") with no change needed (verified). AC4 (TDD + ruff + suite) → every task is red→green→commit; Task 7. AC5 (no regression) → Task 7 Step 3.
- **Constraints:** env-free node oracle (Tasks 2/3); candidate pin `5b0c13a6` never m2021 (Task 4 `initial_state`, Task 5 `prefix_candidate_tree` asserts the SHA); golden isolation (held-out test only in `held_out_files`, no-leak tests in Tasks 2/3; gitignore check in Tasks 1/7); D24 non-structural (behavioral page-object + diag-block execution, validated against named mutants); reuse F3 runner (`NodeExecutionSpec`/`node_oracle_edge`, no parallel runner).
- **Type consistency:** `RunResult`/`ReplacementOutcome`/`TrialAttempt` fields are verified in Task 5 Step 4 before use; `NodeExecutionSpec`/`AllOf` match `tasks/schema.py`; `build_fN_verification(evaluator_store)` signatures match `build_f3_verification`.

## Judgment calls made (cite the spec section)

1. **F1/F2 use a text-read + behavioral-execution oracle, not import-and-exercise** (spec §"F1/F2 oracle targets" + "Constraints/integrity: Env-free"). The spec says "reuse the F3 pattern" and "grade via `node --test` over held-out tests overlaid on the candidate's produced tree." F3's import-and-exercise works only because `report-to-allure.js` is a pure module; the F1 spec/page-object and F2 wdio.conf.ts are not standalone-loadable. The judgment: keep the F3 *mechanism* (`NodeExecutionSpec` overlay + `node --test`) but have the held-out test `fs.readFileSync` the candidate source and **execute the changed unit with injected fakes** (page-object method for F1, diag block for F2). This satisfies "deterministic, env-free, `pass^k`-valid" and D24's "no structural-only acceptance" — both proven against the golden, `5b0c13a6`, and named mutants during authoring.

2. **F2's scope is `wdio.conf.ts` only; the `report-to-allure.js` non-2XX filter is F3, not F2** (spec §"F1/F2 oracle targets" says F2 "enhances the wdio fixture in `wdio.conf.ts`"). The `F-golden.patch` touches both `wdio.conf.ts` AND `report-to-allure.js`, but the latter (+ its `__tests__` test) is the already-built F3 layer (item 004). Reading the patch resolves the ambiguity: F2 = the `[DiagTrace]` block + `const diagResult =` capture in `wdio.conf.ts`. The F2 oracle therefore "reconciles with the existing failure-analysis engine" by asserting only `wdio.conf.ts` behavior and leaving the F3 `report-to-allure` tests untouched (Task 7 Step 3 confirms they stay green).

3. **The F runner grades a deterministic base/edited tree; the live model F-runs are deferred** (spec §Non-goals: "the live candidate F-runs across the roster … are the post-merge execute phase"). `run_f` takes an injectable `build_tree_fn` so this PR wires + tests the grade path without a model call; the post-merge phase swaps in the model's produced tree. `k` identical valid runs are used because the node oracle is env-free (every trial is valid and identical → `pass^k` well-defined), consistent with §Constraints "`pass^k`-valid unconditionally."

4. **`build_f_tasks` includes F3 (ids `f-f1`/`f-f2`/`f-f3`)** — the spec centers F1/F2, but F3's oracle exists and the M1 F domain is the 3-task set (report engine + master-plan "F1/F2/F3"). Including F3 in the builder makes the F domain complete with no extra oracle work (reuses `build_f3_verification`). If the owner wants F3 excluded from the 009 task set, drop the `f-f3` tuple entry — a one-line change isolated to `build_f_tasks`.

---

## Execute-phase follow-ups

- `f_run._grade_tree` condition_id is a stub (`"(f-local)"`); thread the real arm condition_id when wiring the live F roster run. Decision: deferred — would require adding a `condition_id` param to `run_f`/`_grade_tree` and updating the `run_m1` F branch call site; the live execute phase is a non-goal for this item (§Non-goals) and the per-arm IDs are only needed when producing the multi-condition report.

**Plan complete and saved to `docs/2026-06-13-agentic-v1-domains-runs/items/009-plan.md`.** A Sonnet impl agent will execute it verbatim via subagent-driven-development.
