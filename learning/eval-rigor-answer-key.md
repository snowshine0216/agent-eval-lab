# Eval Rigor — Answer Key

> ⛔ **Do not open until you've filled the worksheet drill from a cold start.**
> Peeking converts a generation drill (builds recall) into a reading exercise
> (builds only recognition — which you already have). Score honestly; the *trend*
> across weeks is the signal.

Each item: **the finding you should have generated** → *one-line model* → where it
lives in the spec (`2026-06-15-…-design.md`).

---

## §W1 — Threats to validity in the F-ablation (target: 7)

1. **Differing round caps across arms** confound the factor with budget → **uniform 40-cap**. *A factor effect is only clean if every arm gets the same budget.* (§8.3 / D.2)
2. **No randomized/counterbalanced run order** → provider drift / time effects masquerade as P/V → **seeded block-randomized order**. *Run order is a nuisance variable; randomize within blocks.* (§9.8 / B.7)
3. **Factor P references context the trees lack** (F1/F2 only had `target_paths`) → a vacuous treatment → **enrich trees identically across arms**. *A treatment that can't act isn't a treatment.* (§9.4 / B.5)
4. **Tree must be byte-identical across a base task's arms** (differ only in prompt/tools) → else the tree confounds P/V. *Hold everything but the factor constant.* (B.5 / B.2)
5. **All arms must share the same oracle/`verification`** → else they aren't comparable. *Same ruler for every arm.* (B.2, the arm-as-task pattern)
6. **Bare arm (enriched tree + 40-cap) ≠ production M1 F (minimal tree + 20-cap)** → bare is the *within-ablation control*, not the production baseline. *Name your control; don't smuggle a second change into it.* (D.2 / grilling Q7)
7. **Edit metrics mechanically penalize V** (authored tests counted as out-of-scope edits) → **separate `authored_test_edit_count` from product/out-of-scope**. *A metric must not punish compliance with the treatment.* (§9.5 / D.4)

---

## §W2 — Estimand + censoring (target: 8)

1. **pass^k ≠ pass@k.** pass^k = *all k trials pass* (reliability); pass@k = *≥1 of k passes*. Different estimands, opposite optimism. (glossary `pass_pow_k`)
2. **3 tasks → 3 task-level obs/arm → descriptive only**, no Holm / no confirmatory p-values. *Tiny N can describe, not confirm.* (§8.3 / D.2)
3. **Δ = P−bare is NOT a 2×2 main effect.** A main effect averages the factor over *both* levels of the other factor. (§8.3 / D.2)
4. **Factors derived from the same 3 tasks → retrospective, not a-priori** → exploratory; confirmation needs a held-out set (F4–F6). *Hypothesizing after results (HARKing) ≠ testing.* (§8.4 / F)
5. **Cap-bound run = task failure for success metrics**, but **right-censored** for time-to-completion. *Two roles for one event; state both.* (glossary `censoring` / D.1)
6. **Tokens/cost are OBSERVED even when capped** — only *time* is censored. *Don't drop a capped run's resource cost; it really was spent.* (§9.6 / D.3)
7. **`censoring_policy="failure"` was declared but unenforced** in `pass_pow_k` (keyed only on `grade.passed`) → enforce it. *A declared policy the code ignores is a bug.* (§8.2 / D.1)
8. **The censor lands in shared `reliability.py` → applies to D/B too**, going forward. *Know the blast radius of a "local" scoring change.* (§10.6 / D.1)

---

## §W3 — Factor-V leak / escape red-team (target: 8)

1. **Model-authored JS runs as the evaluator OS user** → can read the `evaluator-only/` golden by absolute path. *Untrusted code inherits the runner's privileges unless confined.* (§9.1)
2. **Reserved-path provenance ≠ isolation.** It controls *which files run*, not *what they read*. (§9.1 / B.4)
3. **`deny network*` alone is insufficient** — the test's stdout is **returned to the model in-trajectory**, so it can read the golden and *print* it. *Enumerate every exfil channel, not just the network.* (§10.3 / B.4)
4. **Seatbelt must be deny-read-by-default + explicit allowlist** (temp + node + system libs); a broad `allow file-read*` reopens the leak, and node won't start without its system paths. *Default-deny, then allow the minimum.* (§10.3 / B.4)
5. **Held-out golden is never seeded (D19); visible ∩ oracle = ∅ (ADR-0012).** *The grader must be invisible to the gradee.* (B.5)
6. **Tree enrichment can collide with the held-out overlay → `tree_collision`** → per-task disjointness invariant (reuse `prefix_collision`). *Growing the visible tree can silently corrupt grading.* (§10.4 / B.5)
7. **Running the *exact* oracle tests as feedback would leak the grader** → feedback is **model-authored tests only**. *Self-test ≠ see-the-answer.* (Factor-V feedback decision)
8. **Frozen canonical-output contract (ADR-0009)** — don't globally change `truncate_output`; scope a separate V rendering. *Don't mutate a frozen reproducibility contract for a local need.* (§9.7 / B.4)

---

## §W4 — Capstone
No fixed key — your scorecard is `findings you caught ÷ findings the adversarial
pass produced` on your own new change. The capstone passes when that ratio is
clearly above your Week-1 number and the surprises are few and minor.

---

### Cross-cutting models (the ones worth tattooing)
- **Hold everything constant but the factor** — or randomize it away.
- **Name the estimand and its uncertainty before reporting a number.**
- **Derived-from-the-data ≠ tested** — separate exploration from confirmation.
- **Default-deny, allowlist the minimum; enumerate *every* channel.**
- **Honor declared contracts (censoring policy, frozen records, disjointness) — a declaration the code ignores is the bug.**
