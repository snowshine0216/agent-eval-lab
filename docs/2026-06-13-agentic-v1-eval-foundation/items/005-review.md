# Item 005 — D-set Harness Code Review

**Branch:** `feat/agentic-v1-005-dset-harness`
**Diff base:** `autodev/agentic-v1-eval-foundation`
**Reviewer:** Claude Sonnet 4.6 (code-review skill, HIGH effort)
**Date:** 2026-06-13
**Suite result:** 827 passed, 1 failed, 8 skipped (the 1 failure is a pre-existing
sandbox-cleanup flake in `test_run_pytest_timeout_is_structured_and_reaped` that
passes in isolation and is unrelated to this PR)

---

## VERDICT: PASS-WITH-NITS

**ZERO Blockers. TWO Latents. FOUR Nits.**

The bash sandbox is structurally sound: `shell=False` is confirmed throughout,
the `playwright-cli`-only allowlist is enforced before exec, timeout + process-group
kill are present, and stdout is truncated. The D19 no-leak boundary holds — the
evaluator-only store is gitignored, absent from the system prompt and tool
description, and the no-leak test is non-trivial. The `FactKeySpec` grader is pure
and enforces all three gates (required-present, forbidden-absent, faithfulness). The
executor seam widening to `BashRequest` is type-correct and does not disturb the
item-001 `ExecutionRequest` path. Two latent defects were found: a `validity_fn`
false-invalid misclassification when no assistant message is present, and silent
voiding of tasks with no diagnostic output.

---

## Findings

### Latents (2)

**L1 — `_non_pass` (no-answer) omits `page_snapshot_sha256`, causing `validity_fn`
to classify a model failure as env-invalid**

- Files: `src/agent_eval_lab/graders/fact_key.py` lines 39–43;
  `src/agent_eval_lab/runners/dset_run.py` lines 24–33
- When `grade_fact_key` is called and there is no assistant message in the trajectory,
  it returns `_non_pass({"error": "no assistant message in trajectory"})`. The
  evidence dict does NOT contain `page_snapshot_sha256`. The
  `make_snapshot_validity_fn` then reads `run.grade.evidence.get("page_snapshot_sha256")`
  which returns `None`, so `None != reference_sha256` → `validity_fn` returns
  `False`. In `run_task_k_valid._is_invalid`, a `False` from `validity_fn` marks
  the run as env-invalid (replacement candidate), not model-failed. A run where
  the model gave no answer should count as a valid (passed=False) trial, not as an
  invalid env trial consuming the max-invalid-rate budget.
- In the worst case (model consistently fails to produce a text turn), all runs
  become "invalid", max-invalid-rate trips, and the task is voided — even though
  the environment is healthy. This inflates the invalid-rate budget for actual
  env-drift events.
- No test covers the no-answer → validity_fn=False path.
- **Fix (option A):** In `grade_fact_key`, always include `page_snapshot_sha256` in
  evidence even on the no-answer path:
  ```python
  def _non_pass(evidence: Mapping[str, Any], spec: FactKeySpec | None = None) -> GradeResult:
      merged = dict(evidence)
      if spec is not None:
          merged["page_snapshot_sha256"] = spec.page_snapshot_sha256
      return GradeResult(grader_id=GRADER_ID, passed=False, score=0.0,
                         evidence=merged, failure_reason=None)
  ```
  Then change `grade_fact_key`'s no-answer branch to pass `spec` through.
- **Fix (option B):** In `make_snapshot_validity_fn`, treat `None` (key absent) as
  valid rather than invalid, and document that "missing sha = non-env-drift failure":
  ```python
  def validity_fn(run: RunResult) -> bool:
      recorded = run.grade.evidence.get("page_snapshot_sha256")
      if recorded is None:
          return True  # no sha in evidence = model failure, not env drift
      return recorded == reference_sha256
  ```
  Option B is the smaller change but slightly conflates two cases. Option A is more
  explicit and is preferred.

---

**L2 — VOID outcomes are silently dropped from the `run-dset` JSONL output with no
diagnostic**

- File: `src/agent_eval_lab/cli.py` line 764
- `_run_dset_command` iterates over `outcomes` and writes only `outcome.valid_runs`
  to the output JSONL. If `outcome.void is True` (max-invalid-rate tripped), the
  task disappears from the output with no warning. An operator running the command
  would see fewer than 15 lines in the JSONL without any explanation.
- This interacts with L1: if L1 fires repeatedly it can trigger void, making the
  silent drop a reachable condition rather than a theoretical one.
- **Fix:** After writing valid_runs, emit a warning to stderr for voided tasks:
  ```python
  for outcome in outcomes:
      _append_runs(fh, outcome.valid_runs)
      if outcome.void:
          print(
              f"WARNING: task {outcome.valid_runs[0].task_id if outcome.valid_runs "
              f"else '(unknown)'} was VOIDED (max-invalid-rate exceeded); "
              f"excluded from output",
              file=sys.stderr,
          )
  ```
  Or (preferred, since void tasks have no valid_runs): track task ids and emit
  a single summary line after the loop.

---

### Nits (4)

**N1 — `parse_argv`: no guard against slash in `argv[0]` (path injection, defense-in-depth)**

- File: `src/agent_eval_lab/runners/bash_edge.py` lines 107–112
- `binname = Path(argv[0]).name` strips the directory component, so a command like
  `/home/attacker/playwright-cli arg` passes the allowlist check (basename ==
  `"playwright-cli"`). `shutil.which("/home/attacker/playwright-cli", path=…)` then
  resolves it directly (slash-containing arguments bypass PATH lookup per Python
  docs) and the attacker binary is executed.
- In practice this is not exploitable in the eval context: a candidate can only
  issue commands through the `bash` tool, which only allows `playwright-cli`, which
  is a headless browser that cannot write arbitrary executables to the filesystem.
  But the defense relies on the external constraint; the sandbox code itself has
  no guard.
- **Fix:** Add a check in `parse_argv` (or in the executor before the `which` call):
  ```python
  if "/" in argv[0]:
      return None  # reject paths with directory components
  ```
  This is a one-liner and makes the sandbox self-contained.

**N2 — Q01 required key `"container"` is too generic**

- File: `evaluator-only/cmc-docs-factkeys.json`, question `cmc-q01`
- The required key `"container"` is a single common English word. A candidate could
  pass this key by saying "Container Registry is needed" or "containers are used in
  Docker" without identifying CMC as a container-based solution. The matching is
  case-insensitive substring, so even mentioning the unrelated "Container Registry"
  prerequisite from the same page would satisfy this key.
- The snapshot line is: *"CMC is a flexible, container-based solution"*, so the
  intended target is the phrase `"container-based"`.
- **Suggestion:** Replace `"container"` with `"container-based"` in `cmc-q01`
  required keys. This is a minor specificity tightening that prevents incidental
  matching.

**N3 — `validity_fn` is `None` when `reference_sha256` is omitted from `run_dset`
  (snapshot-hash gate silently disabled when called without the arg)**

- File: `src/agent_eval_lab/runners/dset_run.py` lines 61–64
- `reference_sha256` is `Optional[str]`; if omitted, `validity_fn` is `None` and
  page-drift detection is disabled. The CLI (`_run_dset_command`) always passes the
  sha from the factkeys JSON, so this is safe in production. However, the test
  `test_run_dset_threads_k_valid_and_records` calls `run_dset` without
  `reference_sha256`, which means the "snapshot-hash validity_fn was threaded"
  assertion at line 99 checks that `"validity_fn" in captured` (key present) but
  does not check it is non-None. A future caller omitting `reference_sha256` would
  silently run without drift detection.
- **Suggestion:** Either make `reference_sha256` required (no default), or assert
  `captured["validity_fn"] is not None` in the test to make the intent explicit.

**N4 — `_SESSION` placeholder in candidate system prompt is undocumented**

- File: `src/agent_eval_lab/datasets/cmc_dset.py` line 37
- The system prompt shows `$SESSION` as a placeholder: *"playwright-cli -s=$SESSION
  open …"*. The candidate model must invent a session ID and substitute it. The
  prompt relies on the model understanding that `$SESSION` is a variable it chooses,
  not a literal string or an env var that is magically injected. This is probably
  fine for capable models, but there is no test or documentation of this convention.
  The task prompt could be clearer: *"choose any session ID (e.g. `-s=sess1`)"*.
- Impact: minor usability/documentation only. The bash edge does not inject
  `$SESSION`; the model must supply its own value.

---

## Scrutiny responses (per-checklist)

### 1. Bash sandbox — `shell=False`, allowlist, injection surface

**`shell=False` throughout:** Confirmed. `subprocess.Popen` is called with
`[resolved, *argv[1:]]` and no `shell=True`. The env is built from scratch
(`_bash_env`) with no `os.environ` inheritance. `check-env` uses `subprocess.run`
with a list argument (also no shell); it runs at operator-init time, not in the
eval loop.

**`>` and `<` safe with `shell=False`:** Confirmed. With `Popen(shell=False)`, the OS
passes `>` and `<` as literal argument strings to the process. No file is opened for
redirection. A playwright-cli `eval "() => document.body.innerText"` command contains
`>` inside a quoted JS arrow function; shlex parses this as a single token within the
quoted string, never as a redirect operator. The commit message and inline comment
correctly explain the rationale.

**Binary allowlist enforced before exec:** Confirmed. Lines 107–109 check
`Path(argv[0]).name not in allowed_bins` and return `_reject(…)` without calling
`subprocess.Popen`. The resolution via `shutil.which` follows only if the name passes.
See N1 for the one defense-in-depth gap (slash in argv[0]).

**Env isolation:** From-scratch env with `PATH` pinned to node-22 bin + `/usr/bin:/bin`
only; `HOME=workdir`; `NO_COLOR=1`; `TZ=UTC`. No `os.environ` inheritance. Good.

**Timeout + process-group kill:** `process.communicate(timeout=timeout_s)` →
`TimeoutExpired` → `_kill_process_group` sends `SIGKILL` to the process group
(`start_new_session=True`). `BashResult(timed_out=True, exit_code=-9)` is returned
without spawning a new process. Correct.

**Stdout truncation:** `truncate_output(out.decode("utf-8", "replace"))` is applied
to both stdout and stderr before storing in `BashResult`. The `replace` error handler
prevents decode failures on binary output.

### 2. D19 no-leak

**Evaluator store path not visible to candidate:** The `FactKeySpec` (including
`page_snapshot`, `required`, `forbidden`) lives in `Task.verification`, which is
never serialized to the OpenAI wire format. `wire.py:turn_to_message` only converts
`MessageTurn`, `ToolCallTurn`, and `ToolResultTurn`. `Task.verification` is never
included in the messages list sent to the model.

**System prompt and tool description:** The system prompt (`_SYSTEM` in `cmc_dset.py`)
contains only the CMC source URL and playwright-cli invocation examples. It does not
mention fact-keys, snapshot paths, required values, or forbidden values. The bash
tool description (`BROWSE_TOOLS["bash"].description`) likewise contains none of these.
Both are explicitly asserted by `test_bash_tool_surface_exposes_no_answer` and
`test_answer_values_absent_from_system_prompt`.

**D19 tests are non-trivial:** The tests assert actual absence of answer-specific
tokens ("1.34", "Managed Redis 7", "calico 3.29") from the system prompt content.
The key-in-question-text exclusion logic is correct: keys like "Management Console"
appear in the question text legitimately and are excluded from the check; version
numbers like "1.34" do not appear in the question text and must be absent from the
system prompt.

**Can playwright-cli read `evaluator-only/`?** The browser environment runs with
`HOME=workdir` and `cwd=workdir` (under `evaluator_store/dset-work/…`). A candidate
could attempt `playwright-cli open file:///path/to/evaluator-only/cmc-docs-factkeys.json`
by guessing the path. However: (a) the store path is not given to the candidate, and
(b) playwright-cli's headless Chromium restricts `file://` access by default (no
`--allow-file-access-from-files`). Even so, there is no explicit test verifying that
`file://` navigation to the store is blocked. This is accepted as a defense-in-depth
gap, not a blocker, given the two-layer protection.

**`evaluator-only/` is gitignored:** Confirmed. `/.gitignore` line 16:
`/evaluator-only/`. The `test_evaluator_store_is_gitignored` test passes (exit 0
from `git check-ignore`).

### 3. `FactKeySpec` grader — required, forbidden, faithfulness

**All three gates enforced:** Confirmed in `grade_fact_key` (lines 55–63):
`required_not_on_page` (faithfulness), `missing_required` (candidate answer),
`present_forbidden` (hallucination). `passed` requires all three lists to be empty.

**Case/whitespace normalization:** `_normalize` casefolds and collapses `\s+` to a
single space. This is correct for the expected text content. Note that `+` in
"Prometheus + KEDA" is not treated as whitespace; the candidate must include spaces
around `+` to match the key as stored. The snapshot text contains the key with spaces
("Prometheus + KEDA"), so a candidate who directly quotes the page will pass.

**Substring false-positive for "1.34" → "1.345":** The required key `"1.34"` is a
substring, so a candidate answer saying "kubernetes 1.345" would pass. The snapshot
contains only `1.34` (not `1.345` or any `1.34x` variant), so the faithfulness gate
does not block this. In practice, `1.345` is not a real Kubernetes version and is
extremely unlikely. Flagged as a nit (N2-adjacent) but not a blocker because the
faithfulness gate ensures `"1.34"` is on the page, and the snapshot numbers are clean.

**Grading is pure:** No I/O, no side effects, no mutable state. All inputs are
immutable (`frozen=True` dataclasses and strings). ✓

### 4. Fact-key spot-check

Four questions checked against snapshot and answer key:

**Q02** (L1 — Kubernetes version): required `["1.34"]`, forbidden `["1.32", "1.33",
"1.30", "1.28"]`. Snapshot line 202: `Kubernetes Cluster | 1.34 | Reference`.
Answer key: *"The recommended Kubernetes version is 1.34."* Required is present on
the page. Forbidden keys are genuine wrong versions. **Good discriminator.**

**Q04** (L2 — namespace names): required `["Strategy Management Layer Namespace",
"Strategy Managed Prerequisites Namespace", "Environment Namespace"]`. All three
appear verbatim in the snapshot (lines 33–35 and 100–118). No forbidden keys.
Multi-word exact phrases make false-pass very unlikely. **Good.**

**Q09** (L3 — observability): required `["Prometheus + KEDA", "Service Mesh",
"Calico", "L7 LB for Library"]`. All four are present in the snapshot (lines 114,
147, 211, 212). No forbidden keys (the question asks to enumerate, so absence of
contradiction is correct). **Good.**

**Q11** (L4 — upgrade scenario): required `["1.34", "Managed Redis 7", "Service Mesh"]`,
forbidden `["1.32 is supported", "redis 6 is supported"]`. The required keys are on
the page (lines 202, 206, 147). The forbidden keys are specific enough — a candidate
correctly stating "upgrade from 1.32" would NOT trigger `"1.32 is supported"` (the
full phrase is the key, not "1.32" alone). **Well-crafted. No false-fail risk.**

**Q01** (L1 — CMC definition): required `["container", "cloud infrastructure"]`,
forbidden `["fully managed saas", "strategy hosts", "strategy manages your cloud"]`.
The forbidden keys are appropriate contradictions. The required key `"container"` is
too generic (see N2) — "Container Registry" on the same page would satisfy it. The
key `"cloud infrastructure"` is more discriminating and is on the page.
**Partial concern; see N2.**

### 5. Validity mask wiring (`run_dset`, D36)

**Snapshot-hash validity_fn:** `make_snapshot_validity_fn` returns a function that
reads `run.grade.evidence["page_snapshot_sha256"]` and compares it against the
reference. A match → valid (page is as expected). A mismatch → invalid (page drifted).
The `run_dset` integration test confirms `validity_fn` is threaded to `run_task_k_valid`.
The CLI always passes `reference_sha256` from the factkeys JSON.

**L1 interaction:** As documented under L1, a run with no assistant message returns
evidence without `page_snapshot_sha256`, making `validity_fn` return False. This
misclassifies a model failure as env-drift.

**k_valid / max_invalid_rate integration:** `run_dset` threads `k_valid` and
`max_invalid_rate` from the evaluator config to `run_task_k_valid`. The test at
`test_run_dset_threads_k_valid_and_records` confirms `k_valid=5` is captured.
The void path (VOID outcome → silent drop) is covered by L2.

### 6. Executor seam (ADR-0008 / item-001 behavior preserved)

**`BashRequest` dispatch:** `loop.py` line 141: `isinstance(applied, (ExecutionRequest, BashRequest))`
— both types route through `_fulfill`. The `Executor` type alias accepts both.
`_serialize_effect_result` dispatches on `isinstance(result, BashResult)` vs
`ExecutionResult`. No string-based dispatch.

**Item-001 behavior unchanged:** `run_baseline` uses `resolve_world()` which returns
the code_world `apply`/`executor`. That world's `apply` only returns `ExecutionRequest`
or `ToolOutcome`, never `BashRequest`. The type union is additive; existing paths
are not affected.

**`apply_browse` pure:** Returns `BashRequest` (effect-request) or `ToolFailure`
(pure validation). No I/O. State is threaded through unchanged. ✓

### 7. CLAUDE.md FP; silent failures; mutable state

- All new dataclasses (`BashRequest`, `BashResult`, `FactKeySpec`) use
  `frozen=True, kw_only=True`. ✓
- `grade_fact_key`, `_normalize`, `_final_answer` are pure: no I/O, no side effects. ✓
- `parse_argv` is pure. `make_bash_executor` is an effect at construction (creates
  workdir) but is clearly at the edge. ✓
- No module-level mutable state introduced. ✓
- No broad `except Exception` catches in new code. ✓
- Silent failure identified: VOID tasks silently omitted from output (L2). ✓
- `_non_pass` evidence gap identified (L1). ✓

---

## What looks good

- **Sandbox architecture is clean:** the three-tier separation (pure `apply_browse`
  → effect-request `BashRequest` → sandboxed `make_bash_executor`) mirrors the
  existing `ExecutionRequest` pattern exactly. No new conceptual territory.
- **`shell=False` is not an afterthought:** the commit that relaxed `>` rejection
  includes a clear inline comment, a docstring explaining the reasoning, and a
  dedicated test (`test_parse_argv_allows_arrow_function_in_eval`). The
  reasoning is correct.
- **Evaluator store isolation is layered:** gitignore (D33) + no store path in
  system prompt (D19 test) + `FactKeySpec` never on the wire + playwright-cli
  file:// restriction. No single point of failure.
- **FactKeySpec grader is genuinely pure:** total function, no I/O, all paths
  return `GradeResult`. The faithfulness gate is an elegant authoring guard —
  a spec author who writes a required key not on the page gets a non-pass with
  `required_not_on_page` evidence, not a silent wrong result.
- **`load_questions` is defensive:** raises `ValueError` if not exactly 15 questions
  parsed; the factkeys JSON similarly asserts `len(entries) == 15`. Mismatch is
  caught at task-build time, not silently at grading.
- **ADR-0008 seam is minimal and correct:** the only change to `loop.py` is extending
  the `isinstance` tuple; the existing `ExecutionRequest` path is identical. The
  new `Effect` and `Executor` type aliases document the seam clearly.
- **Suite is green:** 827 passed, 1 pre-existing flake (sandbox cleanup race in an
  unrelated test), 8 skipped (requires live env). All 25 item-005 tests pass.
