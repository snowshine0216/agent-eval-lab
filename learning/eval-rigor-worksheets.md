# Eval Rigor — 1-Month Generation-First Path (Worksheets)

> **Your gap is *generating* options, not *evaluating* them.** So this is drills,
> not reading. The eval lab is your gym; the spec's §8–§10 tables are the answer
> key. Reading is just-in-time support, never the main event.

## The engine (run on every real decision, all month)
On any decision worth more than 5 minutes:
- [ ] Write the **decision**, your **option set**, the **tradeoffs**, your **pick**, and one **falsifiable prediction** — *before* consulting me, Codex, or any doc.
- [ ] *Then* run the adversarial check (Codex / a subagent / a colleague).
- [ ] **Diff** their findings against your list. The gap names the mental model you're missing — go read just that.

Why it works: deliberate practice (generate → immediate feedback → space it). Recognition you already have; only generation-with-feedback builds recall.

## How to use these worksheets
- Budget ~5–8 h/week (≈2–3 h read, ≈3–4 h drill).
- For each drill: **fill the blank list from a cold start.** Do **not** open the spec or `eval-rigor-answer-key.md` until you've written your list.
- Then open the answer key, score yourself, and write the one missing model you most want to keep.

---

## Week 1 — Confounding & experimental design  *(the #1 source of findings)*
**Model to build:** a comparison only measures the factor if every *other* difference is held constant or randomized away.

- [ ] **Read (~3 h):** Montgomery, *Design and Analysis of Experiments* — the `2^k` factorial + blocking + confounding chapters only. Skim a DAG/confounder explainer (Pearl, *The Book of Why*, ch. on confounding) for intuition.
- [ ] **Drill (cold start — no spec open):** For the F-set 2×2 ablation (bare/prompt/feedback/both × F1/F2/F3), list **every threat to validity and its control.** Prompt yourself: *What, besides P and V, could differ across arms and move the result?*

  My threats → controls (fill in ≥6):
  1.
  2.
  3.
  4.
  5.
  6.
  7.

- [ ] **Score:** open answer key §W1. `caught ÷ total = ____`. One model to keep: ____________________

---

## Week 2 — Measurement & honest inference  *(the #2 source)*
**Model to build:** name the estimand and its honest uncertainty *before* reporting a number; know when you may only describe, not infer.

- [ ] **Read (~2 h):** HumanEval (Chen et al. 2021) — the **pass@k** section + its unbiased estimator. A right-censoring / Kaplan–Meier intro (Klein & Moeschberger ch. 1).
- [ ] **Drill A (cold start):** Re-derive why **pass^k ≠ pass@k** in one paragraph (what does each *estimand* claim?).

  My derivation:

- [ ] **Drill B (cold start):** From a blank page, decide: (a) is the 2×2 confirmatory or descriptive, and why; (b) the censoring policy for a cap-bound run across **success** vs **resource** vs **time** metrics.

  My calls (fill in ≥6 points total):
  1.
  2.
  3.
  4.
  5.
  6.

- [ ] **Score:** open answer key §W2. `caught ÷ total = ____`. One model to keep: ____________________

---

## Week 3 — Eval failure modes & threat modeling  *(narrow, but P0 when it hits)*
**Model to build:** ask "what makes this number a lie?" — leakage, contamination, and untrusted-code channels.

- [ ] **Read (~2 h):** SWE-bench contamination discussion; Saltzer & Schroeder least-privilege (skim the 8 principles); one `sandbox-exec`/SBPL write-up.
- [ ] **Drill (cold start):** Red-team **Factor V** (model writes & runs its own tests for feedback). List every way it could **leak the grader** or **escape isolation**, and the control for each.

  My leak/escape vectors → controls (fill in ≥6):
  1.
  2.
  3.
  4.
  5.
  6.

- [ ] **Score:** open answer key §W3. `caught ÷ total = ____`. Did you independently reach the **stdout-return-channel** point? Y / N. One model to keep: ____________________

---

## Week 4 — Capstone (pure generation)
**Goal:** drive a full spec → self-review loop solo, then measure yourself against a real adversarial pass.

- [ ] Pick a *new, small* eval-lab change (e.g., a new metric, a new F task, a config knob).
- [ ] Write the **full mini-spec** AND **your own adversarial review** (P0/P1/P2, file:line) — solo, before any tool.
- [ ] *Then* run Codex / a subagent adversarial review on it.
- [ ] **Score:** `findings you caught ÷ total findings = ____`. Capture each decision as an ADR + any new term in `CONTEXT.md` (the capture habit is learned by doing).

---

## Scorecard (fill in — watch the trend, not the absolute)
| week | drill | caught ÷ total | the one model I keep |
|---|---|---|---|
| 1 | threats to validity |  |  |
| 2 | estimand + censoring |  |  |
| 3 | leak/escape red-team |  |  |
| 4 | capstone self-review |  |  |

**You're done when** the marginal adversarial review stops surprising you (target: W1 ~30% → W4 ~70%+ caught).
