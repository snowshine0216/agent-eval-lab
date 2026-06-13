# Agent Eval Lab — Design: Use-Case-Geared Agentic Eval (`agentic_v1`)

- **Date:** 2026-06-12
- **Status:** Draft for review — **revised after two rounds of 2026-06-12 review** plus a
  **third review** (verdict on each: reject-as-implementation-ready; third review being
  resolved in this revision). Finding→resolution maps: §15 (first two reviews), §15b (third
  review, D33–D38).
- **Supersedes:** the *substrate and primary-experiment* design of
  [2026-06-12-differentiated-hard-substrate-design.md](2026-06-12-differentiated-hard-substrate-design.md)
  (its differentiation **thesis** is retained as the reasoning trail).
- **Scope:** Weeks 7–10. Measures **which model performs best on the owner's real cases,
  at what efficiency**, and **whether the `strategy-test` skill raises that** — over real
  systems, with an evaluator/candidate integrity boundary and a defensible validity model.

> **Implementation is BLOCKED on two preconditions** (§7, §9): a records+runner revision
> (the current schema cannot store the promised metrics, and the runner always truncates),
> and committed owner-reviewed oracle artifacts in evaluator-only storage. The F3 tracer
> bullet may proceed once its oracle artifact exists; nothing else may.

---

## 1. Purpose

Two questions over the owner's own systems: **(1)** which model is best on my cases, at
what **rounds / tokens / cost / wall-time**; **(2)** does the `strategy-test` domain skill
raise success/efficiency on the MSTR authoring task. A use-case-specific measuring
instrument over private/internal systems — reliability + efficiency, not single-run
accuracy.

## 2. What carries over, what changes

**Carries over:** the differentiation thesis; the data model spine (extended in §7);
execution-based grading, `FinalStateSpec`, calibrated `LlmJudgeSpec`, `AllOf`; `pass^k` =
task-level reliability via cluster bootstrap *by task*; the deterministic-headline /
realistic-mode-separate philosophy.

**Changes:** real systems (no synthetic); `playwright-cli` headless browser runtime;
budget **measured not imposed**; **characterization** primary; **owner-authored goldens**;
a **skill-effect experiment**; and — from the review — an **evaluator/candidate integrity
boundary** (§9), **per-run isolation** (§4.3), an **environment validity model** (§6), a
**records+runner revision** (§7), a **defensible aggregation policy** (§8), and
**strengthened, committed oracles** (§6/§9).

## 3. Decisions

D6–D18 as previously recorded (drop info axis; budget measured-not-imposed;
characterization primary; raise the bar; browser = owner's `playwright-cli` service;
verifiable backbone + judged residue; harness+tracer first; real repo; playwright-cli
runtime; deterministic sub-checks for flaky backends; reference-then-grade with
owner-authored goldens; skill-effect M2; level-tiered docs grading). **Added by this
revision:**

- **D19 — evaluator/candidate integrity boundary (P0).** Goldens, oracles, answer keys,
  golden object-ids, and reference solutions live in **evaluator-only storage**, absent
  from candidate workspaces, git refs, prompts, and browser/account permissions. The
  candidate is graded on what it *produced*, never on access to the answer.
- **D20 — per-run isolation (P0).** Every arm/repeat runs in an isolated workspace with a
  **unique condition+run id**; preflight absence check; the grader keys on the **object
  the run created** (captured id), not a name search; reset/cleanup between trials.
- **D21 — environment validity model (P1).** Live-system cases carry **pre/post health
  probes**; a per-run **validity mask** excludes env-unhealthy runs from `pass^k` (marked
  *invalid*, not *failed*); a **versioned environment-failure category (fc-v3)** is added —
  fc-v2 has no env arm. "REST readback objective" ≠ "execution deterministic."
- **D22 — records+runner revision is a precondition (P1).** The current `Trajectory`
  cannot store rounds/cost/wall-time/tool-counts/cap-binding/health, and the runner always
  imposes `max_steps`/`max_tokens`. A schema+runner revision (with a natural-completion /
  **censoring** contract) lands **before** any experiment plan.
- **D23 — domain-macro aggregation (P1).** No raw-pooled leaderboard. Report **per-domain
  scores** (F, D, B) and a **pre-registered macro-weighting** across domains; the composite
  is transparent and never a docs-QA ranking in disguise.
- **D24 — oracle-strength bar (P2).** Every oracle is a **committed, owner-reviewed
  artifact** with **negative/contradiction checks** and (where applicable) **multiple
  held-out/generated fixtures**; structural-only checks are insufficient.
- **D25 — M2 is a real controlled experiment (P1).** **Multiple** independent B tasks;
  **identical instrumentation on both arms** (harness-side, not skill-side); the skill
  pinned to a **read-only commit** with capture/consolidate/stage-edit behaviors disabled;
  **only domain knowledge** toggled. *(Read-only-pin framing **superseded by D27**: a pin does
  not silence prose instructions — the treatment is a stripped `SKILL.md` fork.)*

**Added by the second review (2026-06-12, "still not implementation-ready"):**

- **D26 — B-task count / estimand (P1).** Target **≥10** B tasks for a cluster bootstrap (a
  3-cluster interval is near-degenerate); below the floor, pre-register a fixed-effect /
  mixed-model estimand — never label a low-cluster percentile interval a cluster-bootstrap CI.
- **D27 — knowledge-only = stripped skill fork (P2).** A read-only pin does not silence prose
  instructions; the treatment is a forked `SKILL.md` with capture/consolidate/Non-negotiables
  + runner/cost wiring removed (or that machinery moved harness-side).
- **D28 — validity-mask abuse bound (P2).** A model-action-independent health probe + a
  pre-registered max invalid-rate above which the condition is **VOID** — so an agent cannot
  earn "invalid" in place of "failed."
- **D29 — experiment types are net-new (P1).** `MetricDef` / `ExperimentSpec` /
  `ExperimentResult` do not exist in `src/`; they are built under the §7 precondition.
- **D30 — answers relocated + gitignored (P1).** Answer keys leave `examples/datasets/` for
  `/evaluator-only/`; the candidate `.gitignore` blocks reintroduction.
- **D31 — F3 is attachment-layer-pinned (P1).** F3 changes only the diagnose-trace *rendering*
  (`buildNetworkText`, non-2XX surfaced) and leaves the `>=500` causal filter + its 503 smoke
  test green.
- **D32 — candidate base is a frozen pre-fix SHA (P0).** The F-set golden is an **OPEN** owner
  PR against `m2021`; the candidate checks out the PR's **base commit** (pinned SHA, evaluator
  config), never "latest `m2021`" — so a future merge cannot leak the answer into the candidate
  tree. The golden PR/head ref and a fetch token are withheld from the candidate.

**Added by the third review (2026-06-12):**

- **D33 — evaluator-only store requires filesystem/process isolation, not just gitignore (P0).**
  `.gitignore` prevents commits, not reads — a shell-driven candidate process can read any
  gitignored file in the working tree. The evaluator-only store must be **permission-isolated at
  the filesystem or process level** (separate directory with OS-level access restrictions,
  secrets manager, or a separate evaluator-only repo checked out under different OS credentials).
  Gitignore is retained as a second-layer commit guard, never the primary access boundary.
- **D34 — `pass^k` requires exactly k valid replacement trials (P1).** When a run is marked
  invalid, a replacement trial runs immediately. `pass^k` is computed over exactly **k** valid
  trials per task-condition. If the per-condition void threshold (D28) is reached before k valid
  trials are obtained, the condition is **INCOMPLETE** and excluded from `pass^k` entirely —
  never scored over fewer than k valid observations.
- **D35 — `safety_cap` is a failure for success metrics (P1).** A run that hits the safety cap
  did not complete the task. For **success metrics** (`pass^k`, task success rate) it is a
  **task failure**. For **completion-time / efficiency distributions** it is a **right-censored
  observation**. The prior framing "not a failure" is retracted; it biases success upward by
  treating non-completion as missing data.
- **D36 — D-set is env-dependent until docs are snapshotted (P1).** The D-set browses a live
  HTTP server (`<CMC_DOCS_HOST>`); the "static, version-pinned" label is only valid if the
  docs content is **snapshotted and content-hashed at each run start** and the hash matches a
  reference. Without a snapshot+hash step, D-set falls under the validity-mask model (D21/D28),
  not the unconditionally-deterministic category.
- **D37 — M2 estimand is the bundled skill effect, not a knowledge-only effect (P1).** Removing
  the behavioral sections changes prompt length, wording, and attention allocation alongside
  domain knowledge. Without a context-length-matched placebo and randomized arm order, domain
  knowledge cannot be isolated. The estimand is the **bundled stripped-skill effect**; "only
  domain knowledge toggled" is retracted.
- **D38 — M1 statistical parameters frozen in `ExperimentSpec` before any run (P1).** Required
  pre-registration fields (immutable once written): `k`; number of repeats; primary metric per
  domain; macro-score formula; composite CI method; multiplicity family and correction (Holm).
  Domain weights default to equal; alternatives may be declared at pre-registration only — **no
  post-hoc override**. F-domain has 3 tasks: cluster bootstrap is inapplicable; F-score reports
  a **point estimate with a binomial/exact CI**.

## 4. Substrate + concrete test-case catalog

A task = provided context + goal + verifiable end-state oracle (`AllOf`) + optional judged
residue + capability/diversity tags. Three sets.

### 4.1 Feature set (F) — repo `web-dossier` (golden = owner branch, evaluator-only)

Repo `~/Documents/Repository/web-dossier` (wdio at `tests/wdio`). The **golden solution is
PROVIDED** — an owner PR (title *"fix snapshot failure analysis: diag trace, non-2XX filter,
TC99396_10 assertion"*, **OPEN** against `m2021`, 5 files, +71/−9), held **evaluator-only**
(PR number + head SHA in evaluator config, not here — D19/D32). **The candidate base is PINNED
to the frozen pre-fix commit** (the PR's base SHA, recorded evaluator-side), **not** "latest
`m2021`" — the PR is OPEN against `m2021`, so once it merges, tracking `m2021` would carry the
answer into the candidate's tree (D32). The candidate gets that frozen pre-fix checkout with
**no access to the PR/head ref** and no token to fetch it. Oracles are committed, owner-reviewed
artifacts (D24); the candidate *task prompt* withholds localization (which files to touch is
part of the task).

- **F1 — replace flaky image comparison with assertions** in `TC99396_10`. The golden touches
  `Snapshots_SendBackground.spec.js` (image-compare call removed, −7) and adds
  notification-section assertions in `pageObjects/common/LibraryNotification.js` (+16).
  *Oracle (evaluator-side scope):* the case no longer calls image-compare **and** asserts on
  **specific, owner-specified notification-section content** (not "an assertion exists");
  validated against the golden. Structural-only checks are rejected (D24).
- **F2 — diagnose trace on assertion failure** — the golden enhances the wdio fixture in
  `wdio.conf.ts` (+22; the afterTest/afterHook failure-analysis path).
  *Oracle:* a forced-failure harness asserts a diagnose trace of the **owner-specified shape**
  is produced; reconciled with the existing `failure-analysis` engine (below).
- **F3 — surface failed requests in the diagnose *view* *(first tracer bullet)*.** The
  re-review found the engine **already** catches the 503 causally — `correlate.js:28` filters
  network entries at `>=500` (`failure-analysis.config.js` `serverErrorStatus: 500`),
  `signal.js` emits `backend-error-present`, and `failure-analysis.spec.js` has a committed
  503 smoke test. The real defect is the **attachment/trace rendering** (`report-to-allure.js`
  `buildNetworkText`) dumping the whole buffer — 2xx included — so a human can't see the
  failures. **F3 therefore targets the attachment layer ONLY:** surface **non-2XX** requests
  in the rendered diagnose trace and **leave the `>=500` causal/signal filter and its 503
  smoke test unchanged** (they must stay green). *Oracle:* a predicate over recorded request
  sets, (a) scoped to `buildNetworkText`'s output (not the causal layer), (b) graded over
  **≥3 held-out + generated fixtures** so a one-fixture hardcode fails, (c) with
  **contradiction checks** (surfacing a 2xx, or dropping the 503 / any non-2XX, fails),
  (d) asserting the existing causal-signal tests are **unchanged**. Owner decides whether
  benign 3xx are filtered from the view. Deterministic and env-free — but a layer-pinned
  oracle, not a naive `non-2XX` rewrite of the causal rule (D31). **Confirmed by the golden:**
  the PR changes exactly `report-to-allure.js` (+5/−1) and its test (+27) — the attachment
  layer — and leaves `correlate.js` / `signal.js` untouched, empirically validating D31.

### 4.2 Research / docs set (D) — CMC docs via `playwright-cli`

Browse `http://<CMC_DOCS_HOST>/docs/24.12/Introduction.html` (+ linked sections)
headless via `playwright-cli`; answer the **15 questions** (Levels 1–5). The **questions**
are a **to-be-committed** candidate dataset (`examples/datasets/cmc-docs-questions.txt` —
currently untracked; must be committed before D-set runs begin); the **answer key is
evaluator-only** — relocated to `evaluator-only/cmc-docs-answers.txt`, gitignored (D19/D30)
**and permission-isolated per D33** (gitignore is a commit guard, not an access boundary).

*Grading (D18 + D24):*
- **L1–L3:** required **fact-keys** present **and** **forbidden/contradiction keys absent** (no
  answer facts appear in this candidate-visible spec — fact-keys are evaluator-only artifacts)
  **and** a calibrated faithfulness gate (no hallucination). Fact-keys are an owner-reviewed
  committed artifact in the evaluator store.
- **L4–L5:** calibrated `LlmJudgeSpec` vs the baseline, behind the human–human-then-judge–
  human κ protocol; reported, never the sole headline where a fact-key floor exists.
- `pass^k` valid **only once a docs snapshot+hash step is in place** (D36); without it, D-set
  runs under the validity-mask model. Target: version-pinned 24.12 docs, content-hashed at each
  run start.

### 4.3 Browser set (B) — MicroStrategy Library MDX report (multiple tasks, two variants)

The **hardest browser test**: long-horizon MSTR Library GUI automation via `playwright-cli`
(object browser, hierarchy/attribute placement, Design Mode, mandatory prompt, Save-As).
**M2 requires MULTIPLE independent B tasks** (D25) — one report cannot yield a bootstrap CI,
and a 3-task cluster bootstrap is near-degenerate (the percentile CI takes only 4 values).
**≥10 independent B tasks — owner-committed (2026-06-12)**, so M2 keeps the cluster bootstrap;
the fixed-effect / mixed-model estimand remains a pre-registered **contingency only** if
authoring falls short, and a low-cluster percentile interval is never labelled a
"cluster-bootstrap CI" (D26). The exemplar below is **B-1**; B-2..B-10+ are owner-co-designed
variants (different cubes/objects/prompts/save targets).

**Exemplar B-1 — create an MDX report** at
`…/MicroStrategyLibrary/app` (Tutorial Project, candidate login = an **isolated,
least-privilege account** per D20, *not* an account that can read the golden):
- source **SAPBW > AV_TUTO > Query_CharacteristicValue_Mandatory**; **Rows** Years
  Hierarchy + Region; **Columns** Cost; **Design Mode**; prompt **South** → Apply;
  **Save** to the run's **isolated folder** as **`<model>-<condition>-<run_id>`** (unique).

**Isolation & capture (D20):** preflight-assert the target name/folder is empty; on save,
**capture the created object id**; grade *that* object; **delete/reset** after grading.

**Golden (evaluator-only, D19):** a reference report exists; its **object id is held in
gitignored evaluator config, NOT in this spec, and NOT readable by the candidate account**.
The oracle reads it with **evaluator** credentials.

**Two variants (M2, D25):**
- **B-noskill:** model drives `playwright-cli` with only its own knowledge.
- **B-skill:** model additionally has a **stripped, frozen `strategy-test` variant** — a
  forked `SKILL.md` with the agent-behavioral sections **removed** (the mandatory
  capture/consolidate entry-check + Non-negotiables, `SKILL.md:152-158/200/223-232`, and all
  `strategy-test-run` / `strategy-test-cost` wiring), leaving **domain knowledge only**.
  A read-only pin alone is insufficient — those behaviors are *prose instructions* the pinned
  text still issues (D27). **Both arms are instrumented identically by the harness** (§7); the
  skill's own cost/usage machinery is removed from the arm, not merely cross-checked.

*Oracle (independent of the skill; env-validity-masked, §6):* (1) the **captured object**
exists in the run folder; (2) definition = source cube `Query_CharacteristicValue_Mandatory`,
Rows ⊇ {Years Hierarchy, Region}, Columns ⊇ {Cost}, prompt = South; (3) executed grid equals
the evaluator-only golden under prompt = South.

**Diversity** across F/D/B + horizon + planning is a design gate; tags recorded.

## 5. Tooling & environment

- **Feature (F):** `web-dossier`'s Node/wdio toolchain at the edge; F3/F1/F2 oracles run
  independent of the live Intelligence Server.
- **Browser/research (D, B):** `playwright-cli` headless; the model issues commands via a
  shell tool (the owner's QA-agent shape). `qa-skills` supplies the `playwright-cli` and
  (B-skill) the **stripped knowledge-only `strategy-test` fork** (D27).
- **B-set grading:** evaluator-side MSTR **REST** readback by object id (preferred — robust,
  independent of the UI under test) or a `playwright-cli` readback under evaluator
  credentials; choice in the plan.
- **Reachability is the owner's environment** (internal IPs / labs server / VPN); the
  harness records targets; unreachable/unhealthy = env, not model failure (§6).

## 6. Determinism, environment validity, and grading

**Two distinct properties, not conflated (Finding 5):** *grading objectivity* (a REST/unit
oracle gives an objective verdict) is **separate** from *environment determinism* (the live
labs server / Intelligence Server is not reproducible run-to-run).

- **Fully deterministic, env-free → `pass^k` valid unconditionally:** F3 (recorded
  fixtures), F1/F2 (forced-failure/structural over the owner golden). D-set L1–L3 reaches
  this category **only if** the docs content is **snapshotted and content-hashed at each run
  start** and the hash matches a pre-registered reference (D36). Without a snapshot+hash step,
  D-set falls under the validity-mask category below.
- **Objective grade but env-dependent → `pass^k` valid only over the VALIDITY MASK:** the
  B-set, any live-Intelligence-Server case, and (until snapshotted) the D-set. Each run carries
  **pre/post health probes via a model-action-INDEPENDENT side channel** (a reachability/health
  check the candidate cannot influence — so an agent cannot wedge the server to convert its
  failures into "invalids"); a run whose env was unhealthy is marked **invalid** (excluded from
  `pass^k`), **never charged to the model**. A **pre-registered max invalid-rate per condition**
  is enforced: above it the condition's results are **VOID**, not merely reported (D28). The
  invalid-rate is always reported alongside pass^k.
  **Replacement-trial protocol (D34):** when a run is invalid, a replacement trial runs
  immediately; `pass^k` is computed over exactly **k** valid trials. If the void threshold is
  reached before k valid trials are obtained, the condition is **INCOMPLETE** and excluded from
  pass^k — never scored over fewer than k valid observations.
- **Environment-failure representation (fc-v3):** fc-v2 (`passed|task|agent|harness`) gains
  a versioned **`environment_failure`** category driven by the new health-probe record
  fields (§7). The classifier stays pure/total/versioned (ADR-0013 discipline).

**Subjective residue** (D L4–L5; summary quality) → calibrated `LlmJudgeSpec`, reported
alongside, never the sole pass/fail; `AllOf` keeps the deterministic backbone independent of
the judge.

## 7. Records + runner revision (precondition — Finding 6)

The current model cannot record the experiment and the runner always truncates. **Required
before any experiment plan:**

- **Records:** extend `Trajectory`/`Usage` (append-only, versioned) with **rounds**, **cost**
  (tokens×pricing), **wall_time_s**, **tool_call_counts**, **safety_cap_bound**, **env_health**
  (pre/post probe results), and a **per-run unique id** (`run_uid` / `condition_uid`) — today
  there is only `condition_id` + `run_index`, no isolation primitive for the §4.3 unique save
  name (D20). Extend `stop_reason` with **`completed_natural`**, **`safety_cap`** (censored),
  and **`env_unhealthy`** — distinct from today's `max_steps`.
- **Experiment types are NET-NEW, not carried over (D29):** `MetricDef`, `ExperimentSpec`,
  `ExperimentResult` are described in the 2026-06-09 design doc but **do not exist in `src/`**;
  the precondition designs + builds + tests them (pre-registration, `spec_hash` reconciliation,
  the §8 macro-aggregation rule), it does not assume them.
- **Runner — censoring contract (D35):** run to **natural completion**; impose only a
  **generous safety cap** that, if hit, sets `stop_reason="safety_cap"`. This role is
  **dual**: for **success metrics** (`pass^k`, task success rate) it is a **task failure** —
  the model did not complete the task within the operational budget; for **completion-time /
  efficiency distributions** it is a **right-censored observation** (actual duration ≥ cap,
  unknown). The prior framing "not a failure" is retracted — it biases success metrics upward.
  Today `loop.py` hard-loops `range(max_steps)`; this is the change. Censored runs are
  surfaced in both roles — never silently dropped, never silently counted as successes.
- **Metrics:** rounds/tokens/cost/wall-time become first-class `MetricDef`s; censoring and
  validity masks are explicit in every aggregate.

## 8. Experiments

Pre-registered `ExperimentSpec` → recorded `ExperimentResult` (both **net-new types**, §7);
cluster bootstrap *by task* where the cluster count supports it (≥10), paired, Holm-corrected;
≥1 Inspect AI conformance check.

- **M1 — model characterization (primary), with a defensible aggregation rule (D23/D38).** Do
  **not** pool 15 D + 3 F + n B by raw count (that is a docs-QA ranking). Report **per-domain
  scores** (F-score, D-score, B-score) each with CIs — **F-domain has 3 tasks: cluster
  bootstrap is inapplicable; F-score is a point estimate with a binomial/exact CI, not a
  cluster-bootstrap CI** — plus a **pre-registered macro-weighted composite** (default: equal
  weight per capability domain; alternatives declared at pre-registration only — **no
  post-hoc weight adjustment**). The following are frozen in `ExperimentSpec` before any run
  and are immutable: `k`, repeats, primary metric per domain, macro-score formula, composite CI
  method, Holm multiplicity family. Pareto charts (success vs cost/rounds/tokens) per domain.
  Roster:
  `deepseek-v4-pro`, `GLM-5.1` (SiliconFlow), `MiniMax-M3`, `gpt-5.5` (if reachable), and a
  within-family Qwen ladder — `Qwen/Qwen3.5-397B-A17B` (397B/~17B) → `Qwen/Qwen3.6-35B-A3B`
  (35B/~3B) → local `Qwen3-8B`.
- **M2 — skill effect (controlled, D25/D26/D27).** Over **≥10** independent B tasks (or the
  pre-registered fixed-effect / mixed-model fallback if fewer), paired **B-noskill vs B-skill**
  per model. **Identical harness-side instrumentation** on both arms; the treatment is the
  **stripped `strategy-test` bundle** (§4.3). **The estimand is the bundled skill effect
  (D37)** — the effect of providing the stripped knowledge+context bundle, which includes
  domain knowledge alongside prompt-length and wording changes; "only domain knowledge
  toggled" is retracted (a length-matched placebo would be required to isolate the knowledge
  component). Report per-task + macro pass-rate and rounds/tokens/cost deltas with CIs over
  the **valid** runs; below the bootstrap floor, report the pre-registered alternative —
  never a degenerate percentile interval.

**Deferred:** E3 axis ablation; live-web dynamic mode.

## 9. Evaluator/candidate integrity boundary (Findings 1, 2, 8)

The headline integrity requirement. Concretely:

- **Storage split:** an **evaluator-only store** (**permission-isolated at the filesystem or
  process level** — separate directory with OS-level access restriction, secrets manager, or
  a separate repo checked out under different OS credentials; `.gitignore` is a commit guard
  only, not an access boundary — D33) holds: golden branches, golden object-ids (incl. the B
  golden), answer keys, fact-key artifacts, oracle code, reference solutions. The **candidate
  store** (the repo checkout + prompt + tools the model under test sees) holds **none** of these.
- **No leakage channels:** goldens absent from git refs the candidate can reach, from the
  tracked spec (this revision **redacts the B golden URL/object-id**), from prompts, and from
  the candidate's MSTR account permissions and browser session.
- **Per-run isolation (D20):** unique condition+run id; isolated workspace/folder/account;
  preflight absence; grade the **captured created object**; reset/cleanup between trials.
- **Committed oracle artifacts (D24):** every oracle (F1/F2/F3, D fact-keys, B definition +
  golden compare) is a versioned, owner-reviewed artifact in the evaluator store, with
  negative/contradiction checks and multi-fixture coverage where applicable.
- **Datasets:** CMC **questions** → **to-be-committed** candidate dataset
  (`examples/datasets/cmc-docs-questions.txt` — currently untracked; must be committed before
  D-set runs begin); CMC **answers** → **relocated to `evaluator-only/cmc-docs-answers.txt`**
  and gitignored, but **gitignore is a commit guard only** — the file requires
  filesystem/process-level isolation per D33 before any candidate run. The candidate repo's
  `.gitignore` guards `/evaluator-only/`, `/examples/datasets/cmc-docs-answers.txt`,
  `*.answers.txt`, `*.golden.*` so reintroduction is **blocked, not just discouraged** (D30).

## 10. First deliverable (tracer) and what's deferred

**Order (dependency-correct):**

1. **Records+runner revision (§7)** — schema extension + censoring contract + fc-v3 env
   category. *Precondition for everything measured.*
2. **F3 tracer bullet** — owner golden branch (evaluator-only) + the F3 oracle over multiple
   recorded/generated fixtures with contradiction checks, reconciled with the
   `failure-analysis` engine. Env-free; proves reference-then-grade.
3. **Repo task adapter** — wdio edge runner; F1/F2 oracles vs the owner golden.
4. **`playwright-cli` harness + D-set** — browse the docs; fact-key (+ forbidden-key +
   faithfulness) grading; answers in the evaluator store.
5. **B-set (multiple tasks) + evaluator-side MSTR oracle + isolation** — REST readback +
   golden compare under evaluator creds; per-run isolation; **stripped knowledge-only
   `strategy-test` fork** (D27).
6. **M1 / M2 reports** — per-domain + macro aggregation; validity masks; Pareto; fc-v3
   taxonomy.

**Deferred (with the owner):** the full hard-case set; judge calibration; live-web mode;
E3 ablation; a pinned backend for full e2e determinism.

## 11. Success criteria (tracer milestone)

- Records+runner revision merged: a run records rounds/cost/wall-time/tool-counts/cap-binding/
  env-health and can complete naturally (censoring contract), with tests.
- F3 graded by an env-free oracle over **≥3 fixtures** with contradiction checks, reconciled
  with the existing engine; F1/F2 by owner-golden behavior checks.
- D-set: `playwright-cli` browses the docs; L1–L3 required+forbidden fact-keys grade
  deterministically; answers stay evaluator-only.
- B-set: ≥10 independent tasks (or the pre-registered fallback estimand); isolated per-run with
  a `run_uid`; evaluator-side oracle; validity-masked `pass^k` with an enforced max
  invalid-rate; M2 reports skill deltas (stripped knowledge-only treatment) over valid runs.
- M1 publishes **per-domain** scores + a pre-registered macro composite — never a raw pool.
- No golden/oracle/answer artifact is reachable from any candidate workspace, ref, prompt, or
  account.

## 12. Out of scope (YAGNI)

- Synthetic repo / synthetic browser sandbox.
- Headline unconditional `pass^k` on live-server cases (validity-masked instead).
- E3 / any ablation this milestone.
- Standing up an Intelligence Server for full e2e determinism (grade on sub-checks).

## 13. Risks & open questions

- **Live-server non-determinism** — handled by health probes + validity mask + fc-v3; residual
  risk = cases with no clean sub-check stay env-tagged.
- **Internal reachability** (`10.197.*`, `<MSTR_LABS_HOST>`) — eval runs where the owner has
  access; unreachable = env, not model failure.
- **MSTR REST oracle effort** — auth + read path under evaluator creds; plan picks REST vs
  `playwright-cli` readback.
- **Judge reliability** — gated behind calibration; deterministic floor retained.
- **F3 vs existing engine** — the predicate must be owner-defined against
  `failure-analysis`'s intentional filtering, not asserted in the abstract.
- **Owner-pending:** ~~the `web-dossier` golden branch~~ **provided (owner PR, evaluator-only,
  base SHA pinned)**; the remaining **≥10 B tasks**; the evaluator-store location/secret
  handling; confirmation of REST-vs-`playwright-cli` readback and the shell+`playwright-cli`
  agent shape.

## 14. Decisions & rationale log

D6–D18 as recorded. D19–D25 (§3) carry their rationale inline. Cross-cutting principle: the
eval's credibility rests on the **candidate never seeing the answer** and the **measurement
recording what it claims to** — both were violated by the pre-review draft and are now
structural requirements, not asides.

## 15. Review response (finding → resolution)

| # | Finding | Resolution |
|---|---|---|
| 1 (P0) | Goldens visible to the agent | D19 §9: evaluator-only store; **B golden URL redacted from spec**; golden branch off candidate refs; least-priv candidate MSTR account |
| 2 (P0) | B runs not isolated / name-collide | D20 §4.3/§9: unique condition+run id, isolated folder/account, preflight absence, **grade the captured object id**, reset between trials |
| 4 (P1) | M2 not controlled/estimable | D25 §8 (skill-handling **superseded by D27 / §15a-E**): **multiple** B tasks; identical harness-side instrumentation; **stripped knowledge-only `SKILL.md` fork**; knowledge-only toggle |
| 5 (P1) | Determinism/env claims contradictory; no fc-v2 env arm | D21 §6: objectivity ≠ determinism; pre/post health probes; **validity mask**; versioned **fc-v3 `environment_failure`** |
| 6 (P1) | Data model can't record the experiment | D22 §7: **records+runner revision precondition** — add rounds/cost/wall-time/tool-counts/cap-binding/env-health; **censoring contract** (no forced truncation) |
| 7 (P1) | Leaderboard has no aggregation rule | D23 §8: **per-domain scores + pre-registered macro-weighting**; no raw pool |
| 8 (P2) | Oracles too weak; F3 redundant/conflicting; CMC files untracked | D24 §4/§9: committed owner-reviewed oracles, negative/contradiction checks, **multi-fixture** F3 reconciled with the existing engine, predicate restated as non-2XX; questions tracked / answers evaluator-only |

### 15a. Second review (2026-06-12) — finding → resolution

| # | Finding (re-review, code-grounded) | Resolution |
|---|---|---|
| A (P1) | ≥3 B tasks → degenerate cluster bootstrap (`reliability.py`) | D26 §4.3/§8: target ≥10, else pre-registered fixed-effect / mixed-model estimand |
| B (P1) | F3 `non-2XX` conflicts with the live `>=500` causal filter (`correlate.js:28`); engine already catches the 503 | D31 §4.1: F3 pinned to the **attachment layer** (`buildNetworkText`); causal filter + 503 smoke test left green |
| C (P1) | `MetricDef`/`ExperimentSpec`/`ExperimentResult` referenced as existing; absent from `src/` | D29 §7: scoped as net-new types in the precondition |
| D (P1) | Answers untracked **but not gitignored** → one `git add -A` leaks the key | D30 §9: relocated to `/evaluator-only/` + `.gitignore` guard added |
| E (P2) | Read-only pin ≠ behavioral inertness (`SKILL.md` mandates capture/consolidate) | D27 §4.3: stripped knowledge-only `SKILL.md` fork; cost/runner machinery removed |
| F (P2) | Validity-mask invalid-rate has no abuse bound | D28 §6: model-independent probe + pre-registered max invalid-rate → VOID |
| 2-carry (P0) | Isolation lacked a run-id primitive | D20 + §7: `run_uid` / `condition_uid` added to the records precondition |

### 15b. Third review (2026-06-12) — finding → resolution

| # | Finding | Resolution |
|---|---|---|
| 1 (P0) | `.gitignore` prevents commits, not reads; candidate process can read any gitignored file in the working tree | D33 §9: evaluator-only store requires OS-level permission isolation; gitignore is a commit guard only |
| 2 (P0) | Candidate-visible spec leaked an answer fact (`Q2 requires 1.34`) | §4.2: example removed; no answer facts in the candidate-visible spec; fact-keys are evaluator-only |
| 3 (P1) | "Valid runs only" breaks fixed-`k`: `pass_pow_k` scores however many valid rows remain, not exactly k | D34 §6: replacement-trial protocol — run until exactly k valid trials; condition is INCOMPLETE if void threshold hit first |
| 4 (P1) | `safety_cap` declared "not a failure" without qualifying success vs time metrics; biases success upward | D35 §7: `safety_cap` = task failure for success metrics; right-censored observation for time/efficiency distributions |
| 5 (P1) | D-set classified as unconditionally deterministic despite browsing a live HTTP server | D36 §4.2/§6: D-set is deterministic only with snapshot+hash; otherwise under the validity-mask model |
| 6 (P1) | M2 cannot attribute effect to domain knowledge alone (confounds: prompt length, wording, attention) | D37 §8: estimand is the "bundled skill effect"; "only domain knowledge toggled" retracted |
| 7 (P1) | M1 under-specified — k, repeats, primary metric, CI method, multiplicity, weights unresolved; F's 3 tasks cannot support per-domain cluster-bootstrap CI; "owner may override" enables post-hoc weighting | D38 §8: all parameters frozen in `ExperimentSpec` before any run; F-score is point estimate + binomial/exact CI; no post-hoc weight override |
| 8 (P2) | Questions file untracked while spec says "committed"; stale "pinned read-only" in §5 and §16 | §9: questions status corrected (to-be-committed); §5/§16: "pinned-read-only" → "stripped knowledge-only fork (D27)" |

## 16. Work decomposition (for writing-plans)

1. **Records+runner revision** (§7) — schema + censoring + fc-v3. *(Precondition.)*
2. **F3 oracle + tracer** — multi-fixture, contradiction checks, engine-reconciled; owner
   golden branch evaluator-only.
3. **Repo task adapter** — wdio edge runner; F1/F2 owner-golden oracles.
4. **`playwright-cli` harness + D-set** — fact-key (+forbidden+faithfulness) grading;
   answers evaluator-only.
5. **B-set (multi-task) + evaluator MSTR oracle + isolation** — `playwright-cli` readback
   under evaluator creds (navigate folder → open object → run → verify grid); per-run
   isolation; **stripped knowledge-only `strategy-test` fork** (D27).
6. **M1/M2 reports** — per-domain + macro aggregation; validity masks; Pareto; fc-v3 taxonomy.

Deferred: full hard set, judge calibration, live-web mode, E3 ablation, pinned backend.

## 17. Next step

Address the two preconditions first: the **records+runner revision** (package 1) and the
**F3 oracle artifact** (package 2, env-free) — now buildable, since the F-set golden PR is
provided (its `report-to-allure.js` change is the F3 reference). The owner stands up the
**evaluator-only store** (golden PR base/head SHAs + B golden id + answer key) and pins the
candidate base SHA in parallel. Only then do D/B and the M1/M2 reports follow.

## 18. Implementation parameters (resolved 2026-06-13 grill session)

All parameters below are **frozen for the records+runner revision and writing-plans**. They
answer "what value?" for every decision the spec left open. New session: read §18 first, then
proceed to writing-plans with §16 work decomposition.

### 18.1 Runner & records

| Parameter | Value | Rationale |
|---|---|---|
| `safety_cap` | **200 tool calls** | Generous ceiling for long-horizon B-set; never truncates reasonable runs |
| `stop_reason` new values | `completed_natural` \| `safety_cap` \| `env_unhealthy` | Distinct from legacy `max_steps` |
| `run_uid` format | `f"{condition_id}__{run_index:04d}"` | Deterministic, human-readable slug; e.g. `deepseek:deepseek-v4-pro__0003` |
| `Trajectory` versioning | `schema_version: Literal["1","2"] = "2"` + `v1_compat()` classmethod | No separate V2 type; existing run files load via compat |
| Replacement-trial loop | Extend `multi_run.py` with `k_valid: int` + `validity_fn` callback | Loops until exactly k valid trials or VOID threshold hit |

### 18.2 Experiment parameters (freeze into `ExperimentSpec` before any run)

| Parameter | Value |
|---|---|
| `k` | **5** valid trials per task-condition |
| `repeats` | **1** |
| `safety_cap` | 200 tool calls (matches runner) |
| `max_invalid_rate` | **0.40** (40% → VOID) |
| Domain weights (macro) | Equal: F = D = B = 1.0 |
| Multiplicity correction | Holm |
| F-domain CI method | Point estimate + binomial/exact CI (3 tasks; cluster bootstrap inapplicable) |
| D/B-domain CI method | Cluster bootstrap by task |
| All comparisons | Two-sided; effect = `metric(condition_b) − metric(condition_a)` |
| M2 arm convention | `condition_a = noskill`, `condition_b = skill` (positive = improvement, negative = regression) |

### 18.3 New types (all net-new in `src/agent_eval_lab/experiments/`)

**`Domain`** — `Literal["F", "D", "B"]` alias in `experiments/schema.py`.

**`ExperimentRunRef`** — content-verified run reference persisted in the experiment manifest:
```python
@dataclass(frozen=True, kw_only=True)
class ExperimentRunRef:
    run_uid: str
    artifact_sha256: str
    domain: Domain
    repeat_index: int
    attempt_index: int   # 0 = first attempt; increments on invalid replacement trials
```

**`ExperimentRunRecord`** — in-memory hydrated wrapper (never persisted nested):
```python
@dataclass(frozen=True, kw_only=True)
class ExperimentRunRecord:
    ref: ExperimentRunRef
    run: RunResult   # canonical owner of task_id, condition_id, Trajectory, GradeResult
```
`RunResult` is the canonical owner of all run data; `ExperimentRunRecord` adds only
experiment-context fields (`experiment_id`, `spec_hash`, `domain`, `repeat_index`,
`attempt_index` — derivable from `ref`). Hydration: receive run-artifact files explicitly;
require exactly one matching `run_uid`; verify SHA-256; hard-fail on missing/duplicate/mismatch.

**`MetricDef`**:
```python
@dataclass(frozen=True, kw_only=True)
class MetricDef:
    name: str
    domain: Domain | Literal["composite"]
    primary: bool           # exactly one per domain (D38)
    aggregation: Literal["pass_pow_k", "mean", "median", "point_estimate"]
    ci_method: Literal["cluster_bootstrap", "binomial_exact", "none"]
    validity_mask: bool
    censoring_policy: Literal["failure", "right_censored"]
    # safety_cap: "failure" for pass_pow_k; "right_censored" for efficiency distributions
```

**`MultiplicityFamily`**:
```python
@dataclass(frozen=True, kw_only=True)
class MultiplicityFamily:
    id: str
    description: str
    correction: Literal["holm"]
    alpha: float
```

**`PlannedComparison`**:
```python
@dataclass(frozen=True, kw_only=True)
class PlannedComparison:
    name: str
    family_id: str       # joins to MultiplicityFamily.id
    domain: Domain
    condition_a: str     # condition_id
    condition_b: str     # condition_id; effect = metric(b) − metric(a)
    metric_name: str
```

**`ConditionDef`**:
```python
@dataclass(frozen=True, kw_only=True)
class ConditionDef:
    condition_id: str           # provider:model
    label: str                  # e.g. "deepseek-noskill", "deepseek-skill"
    skill_variant: Literal["none", "strategy_test_stripped"] = "none"
    system_prompt_hash: str | None = None   # SHA256 of injected system prompt at freeze time
```

**`ExperimentSpec`** (frozen by `eval-lab freeze-spec` before any run):
```python
@dataclass(frozen=True, kw_only=True)
class ExperimentSpec:
    experiment_id: str
    k: int
    repeats: int
    safety_cap: int
    max_invalid_rate: float
    conditions: tuple[ConditionDef, ...]
    metrics: tuple[MetricDef, ...]
    macro_weights: tuple[DomainWeight, ...]   # DomainWeight = (domain: Domain, weight: float)
    families: tuple[MultiplicityFamily, ...]
    planned_comparisons: tuple[PlannedComparison, ...]
    dataset_snapshot_hash: str    # SHA256 over sorted canonical JSON of all task defs
    pricing_snapshot_hash: str    # SHA256 over evaluator-only/pricing.json
    spec_hash: str                # SHA256 of spec excluding this field; written by freeze-spec
```

**`ExperimentResult`** — aggregate output of pure metrics layer:
```python
@dataclass(frozen=True, kw_only=True)
class ExperimentResult:
    experiment_id: str
    spec_hash: str
    condition_id: str
    domain: Domain | Literal["composite"]
    metric_name: str
    estimate: float
    ci_lower: float | None
    ci_upper: float | None
    ci_method: str
    valid_run_count: int
    invalid_run_count: int
    void: bool
```

### 18.4 `evaluator.toml` schema

Lives at the repo root; read by the harness at startup. Password stored directly (test
environment). Not committed to the candidate repo — lives in the permission-isolated
evaluator store pointed to by `[store] path`.

```toml
[store]
path = "/path/to/evaluator-only"   # OS-level permission-isolated directory (D33)

[health_probe]
url = "https://<MSTR_LABS_HOST>/MicroStrategyLibrary/api/auth/login"
username = "<MSTR_USER>"
password = "<MSTR_PASS>"                 # test environment — acceptable in evaluator store

[skill]
strategy_test_path = "/path/to/evaluator-only/stripped-strategy-test/SKILL.md"

[runner]
safety_cap = 200
k_valid = 5
max_invalid_rate = 0.40

[oracle.b_set]
readback = "playwright-cli"         # navigate folder → open object → run → verify grid
```

### 18.5 Environment health probe (D21/D28)

Single-level probe: POST to `[health_probe] url` with credentials; **2XX or 3XX = healthy**,
anything else = `env_unhealthy`. Run pre- and post-run. Auth token from the probe response is
reused for the evaluator's `playwright-cli` oracle session.

### 18.6 F3 oracle fixture generation

Fixtures are **generated programmatically** from the golden PR's test file
(`report-to-allure.js` test, +27 lines) in the evaluator store — not hand-written. Minimum
3 fixtures: (1) non-2XX only (happy path), (2) mixed 2XX + non-2XX (contradiction check: 2XX
must not appear in output), (3) 503 only (must appear; must not drop it). The grader is a pure
`AllOf` over `ExecutionSpec` variants.

### 18.7 B-set oracle

`playwright-cli` readback under **evaluator credentials**: navigate to the run's isolated
folder → open the created object by its captured id → run it → verify executed grid matches
the evaluator-only golden under prompt = South. REST API deferred (requires significant
auth/endpoint construction).

### 18.8 B-task independence rule (D26)

Each B task must vary on ≥1 of these three axes vs B-1:
1. **Source object axis** — different cube, dataset, or project.
2. **Template structure axis** — different row/column/filter layout.
3. **Prompt/interaction axis** — different prompt type, answer value, or no prompt.

A variant that changes only the save-target name is **not** an independent task.

### 18.9 Stripped `strategy-test` skill fork

Stored in the **evaluator store** at `[skill] strategy_test_path`. Injected as system prompt
for the B-skill arm only. Stripped by section header (not line number):

- **Remove:** *Default run path* (`strategy-test-run` commands), *Capture & consolidate*
  (entry check + capture + consolidate), *Contribute back*, and capture/consolidate-specific
  non-negotiables ("never commit drafts/inbox.md", "no mid-run writes to real files").
- **Keep:** session bootstrap snippet, credential slot convention, full topic map, escalation,
  domain non-negotiables ("no raw pixel coordinates", "REST API is forbidden in browser tests").

The model lazy-loads domain-skills/ and interaction-skills/ files via `bash` using
`$SKILL_PATH` (from `evaluator.toml`). No special `read_skill` tool — standard bash file reads.

### 18.10 `playwright-cli` agent shape and preflight

**Agent shape:** single `bash` tool for all operations (playwright-cli commands + skill file
reads + F-set repo operations). At eval startup, `playwright-cli install --skills` loads
browser interaction skills into agent context.

**Preflight (`eval-lab check-env`)** — implemented in `src/agent_eval_lab/cli.py`:
1. `playwright-cli --version` — exits non-zero with diagnostic if not found.
2. MSTR health probe (POST to auth/login) — enabled with `--evaluator-config evaluator.toml`.

Install playwright-cli once before any D/B-set eval:
```bash
npm install -g @playwright/cli@latest
playwright-cli install --skills
uv run python -m agent_eval_lab.cli check-env --evaluator-config evaluator.toml
```

### 18.11 Pricing snapshot

`evaluator-only/pricing.json` (gitignored, snapshot_date 2026-06-13). Standard post-promo
rates. Condition IDs for the Qwen ladder (`siliconflow:Qwen/Qwen3.5-397B-A17B`,
`siliconflow:Qwen/Qwen3.6-35B-A3B`) are **provisional** — update once the SiliconFlow
provider entry is added to `runners/config.py`.
