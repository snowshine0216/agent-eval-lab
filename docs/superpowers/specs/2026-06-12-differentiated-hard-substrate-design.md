# Agent Eval Lab — Design: Differentiated Hard-Substrate Phase (folds Weeks 7–10)

- **Date:** 2026-06-12
- **Status:** **Superseded** (same day) by
  [2026-06-12-use-case-agentic-eval-design.md](2026-06-12-use-case-agentic-eval-design.md).
  The differentiation **thesis** (§1–§2: the product is the measuring instrument, not
  the benchmark) carries forward and is the reason this record is kept. The
  *substrate* (three-axis code-repair ablation) and *primary experiment* (E3) were
  replaced after the owner specified the real use case (long-horizon agentic work +
  browser use) and chose model **characterization** over axis ablation. Read the
  superseding spec for the live design.
- **Scope:** Re-sequences and re-aims the original Weeks 7–8 (controlled experiments)
  and Weeks 9–10 (multi-turn + `code_repair_v2` + leakage splits) into a single
  phase built around a *differentiated hard substrate*. Supersedes the **sequencing**
  — not the locked data model — of those weeks in
  [2026-06-09-agent-eval-pipeline-design.md](2026-06-09-agent-eval-pipeline-design.md).
- **Relationship to roadmap:** implements the "next weeks" takeaways recorded in
  [docs/ROADMAP.md](../../ROADMAP.md) after Weeks 5–6.

This is a strategy/design record produced from a brainstorm on 2026-06-12. It
exists to answer one question raised by the project owner: *if our eval measures
the same capabilities as existing benchmarks, what is its differentiated value,
and what is worth building next now that the easy substrate is saturated?*

---

## 1. The question this phase answers

After Weeks 5–6, `code_repair_v1` is saturated across all four conditions (`pass@1`
and `pass^3` both 1.000). The Weeks 5–6 report scopes that precisely: it is *"a
statement about this dataset's shape, not about coding ability."* v1 was
deliberately the friendliest configuration possible — single-concern modules of a
few dozen lines, a **visible failing test that already localizes the bug**, the
whole tree readable in 1–2 `read_file` calls, no reproduction step, no ambiguity,
generous budgets. That configuration is in-distribution even for a local 8B in
2026. Meanwhile `workspace_tool_use_v2` is **not** saturated (Qwen3-8B at 0.620,
with a real tier gradient and deterministic failures).

So "the eval is saturated" is too strong. The accurate statement: **the easy code
set hit its ceiling by design, and the differentiated hard substrate has not been
built yet.** Two questions follow, and they are the reason this phase exists:

1. If our eval measures the same capabilities as SWE-bench / τ-bench / BFCL, why
   are we duplicating them?
2. Given the easy substrate has hit its ceiling, what is the *next* thing worth
   building?

## 2. Thesis — where the differentiation actually lives

An eval can differentiate in exactly three places. Be honest about which a solo,
synthetic, ~20h/week project can win:

| Axis | Meaning | Can we win it? |
|---|---|---|
| **Tasks (the data)** | Build tasks public benchmarks lack | **Mostly no.** We cannot out-realism SWE-bench or out-scale BFCL. "Given a real repo, do the fix" *is* SWE-bench; a smaller synthetic copy is strictly weaker. Weakest place to differentiate. |
| **Metrics (what we report)** | `pass^k` reliability + cost/latency | **Partial.** Real, but τ-bench already reports `pass^k` and cost leaderboards exist. |
| **Methodology / harness** | How we measure, and *proof the instrument is trustworthy* | **Yes — this is the moat.** |

Two things a static public benchmark structurally **cannot** offer, on which this
phase is built:

- **Parametrically-controlled difficulty.** Because difficulty is a *recorded
  knob*, we can ablate *which axis* breaks a model. SWE-bench cannot dial its own
  difficulty — its tasks have fixed, unknown hardness. This is the "iterate the
  standard" deliverable (JD#1), not a copy.
- **Failure attribution + provable instrument validity.** The task/agent/harness
  split caught a *real harness defect* in Weeks 5–6 (the 512-token MLX truncation
  that a naive benchmark would have logged as "Qwen scores 0.133"). Plus
  reproducibility-as-contract, reward-hack hardening, and leakage-safe generation.
  No static benchmark does this.

**Corollary:** synthetic + contamination-free is not a consolation prize. It is the
*enabling substrate* for the Phase 2/3 closed loop — you cannot generate
leakage-safe train/held-out partitions from real GitHub issues.

**The headline of this phase is the measuring instrument, not the benchmark.**

## 3. Decisions taken in this brainstorm

- **D1 — Direction: synthetic-hard + harness-led.** Not real-repo realism, not
  harness-only with trivial tasks, not skip-straight-to-closed-loop.
- **D2 — Success bar: locate the boundary.** Build a controllable difficulty
  gradient and ablate which axis breaks each model. **Not** separating the two
  ceiling hosted models.
- **D3 — Experiment order: E3 first, then E1/E2.** E3 is built and run first on
  `code_repair_v2`; E1/E2 are retained and run after, on tool-use v2.
- **D4 — Keep both `scope` and `budget` axes** despite their non-orthogonality;
  control for it by fixing baselines (see §4), do not drop an axis.
- **D5 — Real-repo external-validity slice is optional**, ≤5 tasks, gated on
  Option-1 results, reported separately. Repo named by the owner once v2 results
  exist.

Rationale for each is logged in §12.

## 4. `code_repair_v2` — the substrate

Three difficulty axes, each a **recorded `difficulty_knob` coordinate** on every
task so the report and grader can slice by axis:

- **Information**: visible failing test (v1) → **prose-only bug report**. The agent
  must write the reproduction first. The oracle is *unchanged* — held-out tests via
  `ExecutionSpec`. Removing the visible test removes the free localization, not the
  grader. (Most differentiated axis.)
- **Scope**: single-file (v1) → **multi-file / multi-hunk coherent edits** over a
  synthetic multi-module tree, where *localization is the actual work*.
- **Budget**: generous (v1) → **tight declared `max_steps` / `max_tokens`**, swept
  as a curve. Budget is already an explicit, recorded eval parameter after Weeks 5–6.

**Invariants carried over from v1 (non-negotiable):** hermetic pytest sandbox with
canonicalized byte-deterministic output (ADR-0009); oracle/visible disjointness +
oracle-breadth proven mechanically (ADR-0012); anti-rote conformance suite in CI;
oracle-wins overlay (ADR-0010); execution-hash-keyed verdict map (ADR-0011).

**Construction discipline:** tasks are authored as *base families*, with each axis
varied **one step at a time** around a family baseline. This is what makes E3
interpretable — every task carries an `(information, scope, budget)` coordinate and
differs from a sibling by a single-axis delta.

**Non-orthogonality (the honest part).** The axes are *not* independent. Large
`scope` is only hard *under finite `budget`* — v1's tree was "readable in 1–2
`read_file` calls," so localization only bites when reading-everything exceeds the
budget. The ablation therefore **fixes a declared baseline level for the non-varied
axes** when sweeping one axis, and each E3 cell records its held-fixed levels. We do
not pretend the axes are orthogonal; we control for it and report the controls.

**Prose-report ambiguity (the second honest part).** A prose-only report must be
(a) solvable *without leaking the held-out test*, and (b) unambiguous enough that
failure means "couldn't localize/repair," not "couldn't guess the intent." This is
bought by the same conformance + spot-audit machinery as v1, plus a **new anti-leak
check** that the report does not transitively reveal the oracle.

**New ADRs expected:** prose-report task shape + anti-leak check; multi-file
world-template representation; per-axis baseline-fixing convention for ablation
cells.

## 5. Experiments

All via pre-registered `ExperimentSpec` → recorded `ExperimentResult` (the
statistics work is *realized inside the eval*, not studied separately). Every
experiment: cluster bootstrap *by task*, paired comparisons, **Holm correction
across each family**, and ≥1 task wrapped as an Inspect AI `Task` for a conformance
differential.

### E3 — primary; built and run first

- **Hypothesis:** each difficulty axis has a locatable breaking point per model.
- **Substrate:** `code_repair_v2`.
- **Primary metric:** `pass^3` per `(axis × level × condition)`.
- **Deliverable:** a **per-model breaking-point map** — for each model, the
  `(information, scope, budget)` level at which `pass^3` degrades from ceiling, with
  cluster-bootstrap CIs. This is the mechanical read-off of the "locate the
  boundary" bar (D2).
- **Decision rule (pre-registered, per axis):** *"axis X is a boundary for model M
  iff `pass^3` at the hard level is below the easy level and the paired bootstrap CI
  of the difference excludes 0,"* with the held-fixed levels of the other two axes
  recorded for that cell.

### E1 — retained; run after E3

- **Hypothesis:** a more precise tool description improves tool-selection accuracy.
- **Substrate:** tool-use v2 (non-saturated for the local model).
- One pre-registered comparison (`vague` vs `precise`); decision rule as in the
  program design. Demonstrates the method even if the effect is local-only.

### E2 — retained; run after E3

- **Output:** which model is most reliable (`pass^3`) at argument extraction, and at
  what cost.
- **Substrate:** tool-use v2.
- Multiple pairwise comparisons, pre-registered **and** Holm-corrected; output is a
  **reliability-vs-cost Pareto chart** — a portfolio artifact regardless of frontier
  saturation.

## 6. Harness as the headline

What is genuinely *new* here — not a re-run of fc-v2:

- **fc-v2 attribution exercised on a substrate with real failures.** v1 had none
  (all conditions passed). Multi-file / longer-horizon repair opens new attribution
  paths the split must handle: *localized-but-mis-edited*, *partial-fix*,
  *repro-never-written*, *budget-exhausted-mid-edit*. Deliverable: a failure-mode
  report that classifies these correctly.
- **Budget-sweep as a defect-surfacing tool.** The truncation defect was found via
  budget; the sweep institutionalizes that discovery move and is expected to surface
  further harness/agent boundary cases.
- **Reproducibility contract under longer trajectories + tighter budgets** —
  byte-identical report regeneration still verified.
- **Methodology write-up:** *"agent limitation vs. evaluation-system defect,"* with
  the Weeks 5–6 truncation episode plus any new catches as worked examples. This is
  the portfolio's headline narrative and the executable form of the README promise
  to "distinguish agent failures from harness failures."

## 7. Real-repo external-validity slice (optional)

- **Scope:** ≤5 real bugs from a repo the owner names, wrapped in the *same* harness
  unchanged.
- **Purpose: external validity.** (a) Does the harness run on real code without
  modification? (b) Does our synthetic difficulty *rank-correlate* with real
  difficulty on the axis where we found a boundary?
- **Gating:** chosen *after* v2/E3 results exist, so the repo matches an axis with a
  located boundary and we can test whether the boundary *transfers*.
- **Reporting discipline:** separate section, **never mixed into headline numbers**
  (same rule as the LLM-user mode); contamination caveat stated explicitly — real
  repos may be in training data, so this is a *validity probe*, not a
  contamination-free measurement.

## 8. Roadmap re-sequencing

Original Weeks 7–8 (E1/E2) and Weeks 9–10 (`code_repair_v2` + multi-turn + leakage
splits) collapse into this one phase:

- **Spine (primary):** `code_repair_v2` substrate → E3 → harness/failure-mode report.
- **Retained, secondary:** E1/E2 on tool-use v2; multi-turn scripted-user protocol;
  leakage-safe splits + never-train manifest (the closed-loop prerequisite). These
  stay in the phase but are explicitly *subordinate* to the spine and may trail it.
- **Release #1 (Weeks 11–12) deliverables unchanged** — now backed by experiments
  with real signal rather than null results on saturated tasks.

## 9. Success criteria (definition of done)

- `code_repair_v2` exists with recorded per-axis difficulty knobs, passes the same
  conformance / oracle-breadth bar as v1, and shows a non-trivial difficulty
  gradient for *at least the local model and one hosted model*.
- E3 produces a per-model breaking-point map with pre-registered decision rules and
  cluster-bootstrap CIs.
- E1 and E2 produce their artifacts (comparison + Pareto chart) on the non-saturated
  tool-use substrate.
- A failure-mode report classifies the new multi-file / long-horizon failures via
  fc-v2 and documents ≥1 agent-vs-harness distinction as a worked example.
- Reproducibility contract holds (byte-identical reports) under the new trajectory
  lengths and budgets.
- *(Optional)* real-repo slice reported separately with the transfer read-off.

**Non-goal explicitly excluded from "done":** separating the two ceiling hosted
models.

## 10. Out of scope (YAGNI)

- Frontier-vs-frontier separation as a gate.
- A real-repo *benchmark* (the slice is a ≤5-task validity probe).
- Long-horizon-with-recovery as a distinct synthetic axis (hard to make
  deterministic; folded into the budget axis for now).
- LLM-simulated users for headline numbers.

## 11. Risks & open questions

- **Scope×budget non-orthogonality (§4)** — controlled by baseline-fixing, but the
  interpretation of any axis boundary must always state the held-fixed levels.
  Primary methodological risk.
- **The gradient may not reveal a hosted-model boundary on some axes** — hosted
  models may ceiling everywhere reachable synthetically. This is an *acceptable,
  reportable* outcome under the "locate the boundary" bar: a null on an axis is still
  a located edge ("not reachable within our synthetic budget"), provided we log the
  cap honestly rather than implying coverage.
- **Prose-report leakage** — the anti-leak check is new and must be
  conformance-tested before any prose-only task counts.
- **Synthetic multi-file realism** — localization in a synthetic tree may be easier
  than in real code; the §7 slice is the external-validity answer, but only after the
  fact.

## 12. Decisions & rationale log

1. **Synthetic-hard + harness-led over real-repo realism (D1).** Real repos forfeit
   the contamination-free + leakage-safe-generation moat and compete with SWE-bench
   on its own turf, which a solo project loses. The differentiator is parametric
   difficulty + harness validity, neither of which a static benchmark has.
2. **Locate-the-boundary over separate-the-frontier (D2).** The latter stakes the
   portfolio on an outcome outside our control (two models at 1.000). The former is
   achievable synthetically and is the stronger capability-boundary story for JD#1.
3. **E3 first, then E1/E2 (D3).** E3 is where the new substrate's signal lives and
   where the success bar is read off; E1/E2 are method demonstrations that ride the
   already-non-saturated tool-use set and can trail.
4. **Keep both `scope` and `budget` despite non-orthogonality (D4).** Dropping an
   axis to force orthogonality would hide a real property of code repair
   (localization difficulty is budget-relative). We control for it instead of
   pretending it away.
5. **Real-repo slice optional, gated, separate (D5).** External validity is worth a
   small, honest probe; it is not worth converting the project into a benchmark
   clone or contaminating the headline.

## 13. Work decomposition (for writing-plans)

Ordered packages; each is a candidate implementation plan:

1. **`code_repair_v2` substrate** — multi-file world templates, prose-only task
   shape + anti-leak conformance, budget knobs, per-axis baseline convention, new
   ADRs. *(Spine; unblocks everything.)*
2. **E3 axis-ablation experiment** — `ExperimentSpec` cells, breaking-point-map
   report, decision rules.
3. **Harness / failure-mode work** — fc-v2 on real failures, budget-sweep tooling,
   methodology write-up.
4. **E1/E2 on tool-use v2** — retained experiments + Pareto chart.
5. *(Optional, deferred)* **real-repo external-validity slice** — after package 2
   results.

Multi-turn scripted-user + leakage-safe splits remain scheduled but subordinate;
they may be their own later packages.

## 14. Next step

On approval of this design, proceed to **writing-plans** for **package 1
(`code_repair_v2` substrate)** — the spine that unblocks E3 and everything
downstream.
