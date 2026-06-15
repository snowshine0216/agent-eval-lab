# Item 005 — Factor V confined-execution sandbox

> Spec authored by **extraction** from the design doc (brainstorming/grill skipped per user
> override). Authoritative source: **§B.4** (seatbelt `sandbox-exec`, `runners/sandboxed_node_edge.py`,
> `make_authored_test_executor`, tail-aware feedback, V-specific `run_tests` ToolDef), **§9.1 / §10.3**
> (P0 leakage channel + read-allowlist), **ADR-0016** (confined execution), **§11.5**, and **Part G
> step 5**. Builds on item 003 (V arms declare the `run_tests` surface; `make_f_run_fn` currently
> raises `NotImplementedError` for live V arms — this item supplies the executor) and item 004
> (enriched trees give V real authored-test material).

## Goal

Supply the **Factor V executor**: a confined `run_tests` tool that runs the model's own **authored
tests** under a real kernel **confined-execution** boundary, so a V arm can iterate against its own
tests without being able to read the held-out oracle or reach the network. The current trusted-oracle
node path (`runners/node_edge.py`) runs model JS as the evaluator user with full FS + network — a
**real evaluator-oracle leakage channel** (§9.1, D33): a broad `(allow file-read*)` would let model
JS read `evaluator-only/` and **print the golden to stdout, which is returned to the model
in-trajectory** — `deny network*` alone does NOT close that channel. This item adds a **new** module
with a **deny-read-by-default + explicit read-allowlist** seatbelt profile, leaving the trusted oracle
path **untouched** (its frozen records must stay byte-stable, §9.7).

## Acceptance criteria

**Confined-execution boundary — `runners/sandboxed_node_edge.py` (§B.4 / §9.1 / §10.3 / ADR-0016, P0):**
- [ ] New module `runners/sandboxed_node_edge.py` wraps `node --test` in a macOS **`sandbox-exec`
  seatbelt** profile that is **deny-read-by-default with an explicit read-allowlist** — only:
  - the candidate temp tree (the materialized arm workspace),
  - the node install dir,
  - the enumerated system paths node needs to start: `/usr/lib`, `/System`, the dyld shared cache,
    and the `/usr/bin:/bin:<node parent>` of the node env ([node_edge.py `_node_env`](../../../src/agent_eval_lab/runners/node_edge.py)),
  - **plus `(deny network*)` and `(deny file-write*)` outside the tree.**
- [ ] The **read-allowlist is mandatory, not a convenience**: a broad `(allow file-read*)` reopens the
  stdout leak of `evaluator-only/`. The profile must both (a) start node and (b) block an
  `evaluator-only/` read.
- [ ] The **trusted oracle keeps its un-sandboxed `node_edge` path** — `runners/node_edge.py` is
  **not modified** (evaluator code; leaving it untouched preserves its frozen records, §9.7).
- [ ] **Escalation note (risk):** the allowlist is brittle across node/macOS versions; if it cannot
  both start node and block an `evaluator-only/` read, escalate to Docker `--network none` (only the
  temp tree mounted). Record this fallback in the module/spec (no need to build Docker here unless the
  seatbelt path can't be made to work).

**Platform gate (§B.4):**
- [ ] The sandboxed executor **probes Darwin + `sandbox-exec` availability** (mirror
  `node_supports_junit`'s probe shape, [node_edge.py:64](../../../src/agent_eval_lab/runners/node_edge.py:64)).
  On a non-macOS host (CI), real V execution **skips**; unit tests inject a **fake executor** (the
  executor is already an injected callable). V runs are **macOS-local-only by design** — recorded in
  the ablation spec (item 006). A CI skip cannot silently void or bias results (the fake executor is
  deterministic; real V is macOS-local).

**Authored-test executor — `make_authored_test_executor` (§B.4 / §10.8):**
- [ ] `make_authored_test_executor` runs **only** `tests/authored/` (a reserved writable path no
  seeded tree populates) regardless of `ExecutionRequest` contents — F3's seeded causal tests are
  **not** run as feedback, and **model-supplied commands are rejected** (fixed `node --test
  tests/authored/`). Reserved-path scoping is for **provenance**; the seatbelt sandbox is the
  **security boundary** (§B.4).
- [ ] Reuses ADR-0008: `run_tests` → `ExecutionRequest`
  ([code_world.py:241](../../../src/agent_eval_lab/tools/code_world.py)) →
  `make_authored_test_executor` (sandboxed) → `ToolSuccess`. `bare`/`prompt` keep `executor=None` +
  no `run_tests` (unchanged from item 003).
- [ ] Wire the executor so item 003's `make_f_run_fn` V-arm `NotImplementedError` guard is **replaced**
  by routing V arms to the sandboxed `make_authored_test_executor` (only on macOS; the guard/skip
  remains the behavior off-macOS). `bare`/`prompt` stay `executor=None`.

**V-specific `run_tests` ToolDef (§10.8):**
- [ ] V arms get a **V-specific `run_tests` ToolDef with a node-accurate description** — today's reads
  "Run pytest over every visible test" ([code_world.py:83](../../../src/agent_eval_lab/tools/code_world.py:83)),
  which is **wrong and misleading** for the node path. Provide a node-accurate ToolDef for the V path
  (run the model's authored tests under `node --test tests/authored/`). Do **not** mutate the shared
  ToolDef in a way that breaks any other consumer — add/scope the V-specific one.

**Output / record contract (§9.7):**
- [ ] The global `truncate_output` (frozen oracle contract, ADR-0009) is **NOT changed**. V feedback
  uses a **separate tail-aware rendering** (failure summaries print at the **end** of a node run).
- [ ] Persisted V records are a **distinct versioned record class**, leaving the oracle's
  head-truncated `ExecutionResult` byte-stable.

**Tests (Part G step 5):**
- [ ] Unit tests inject a **fake executor** (no real sandbox/node) — run everywhere incl. CI.
- [ ] **One macOS-only integration test asserts the sandbox BLOCKS** (a) an `evaluator-only/` read and
  (b) a network call — and confirms it still **starts node / runs an authored test**. Gate it on
  Darwin + `sandbox-exec` (and a minimal node invocation, so the boundary is actually exercised on
  this host rather than skipped — node `--test` version-gating must not prevent the *block-read /
  block-network* assertions from running where `sandbox-exec` + node exist).

## Non-goals (deferred / out of scope)
- **The `run-f-ablation` driver + `f_ablation_spec` + seeded order (item 006).** No driver, no spec
  freeze, no execution.
- **No paid provider execution / no pilot / no full run.**
- **No change to `runners/node_edge.py`** (the trusted oracle path) — frozen records stay byte-stable.
- **No change to the global `truncate_output`** (ADR-0009).
- **No change to the held-out oracles/golden** (D19), no `arm_id`/`ConditionDef`/`ExperimentSpec`
  change; frozen M1 specs keep verifying.
- **Docker fallback** is only built if the seatbelt path provably cannot both start node and block the
  read (record the decision; default is seatbelt).

## Constraints
- **Security is the priority.** The read-allowlist (not a broad allow) is the load-bearing control —
  the leak it closes is model JS printing the golden to stdout (returned in-trajectory). Any review
  finding of a sandbox-escape / read-leak is a **blocker**, not a nit.
- **TDD / FP house style**: the profile builder is a **pure function** of (temp tree, node paths) →
  profile string; the executor is an injected callable; effects (subprocess) at the edge.
- **macOS-local by design**: the seatbelt path is Darwin-only; CI uses the fake executor. This is
  recorded so a CI skip cannot be read as a passing real-V run.
- This host **is** macOS with `sandbox-exec`, node, and `evaluator-only/` goldens present — the
  block-read + block-network integration test **must actually run here** (not just skip) to prove the
  boundary; verification will exercise it.
- **Stage only own files — NO broad `git add`** (security lesson, item 002). Especially important here:
  do not stage anything under `evaluator-only/` or any `.env*`.
- CI runs `ruff check .` AND `ruff format --check .` whole-repo; pytest with `-o addopts=""`.
- No network. Offline TDD only (the sandbox test asserts network is *blocked*, which needs no live net).
