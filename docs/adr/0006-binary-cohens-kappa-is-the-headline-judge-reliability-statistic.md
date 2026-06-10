# Binary Cohen's κ (score ≥ 4) is the headline judge-reliability statistic; weighted κ is secondary

The judge scores summary fidelity on an anchored 1-5 scale, but the **headline
reliability statistic is Cohen's κ on a binarization** (`score >= 4` ⇒ "faithful",
else "unfaithful"), with a seeded percentile bootstrap CI resampling items.
Quadratic-weighted κ over the raw 1-5 scale is computed and reported as a
*secondary, descriptive* number only. Both the 1-5 score and the binary label are
recorded, so re-thresholding needs no re-annotation.

## Considered Options

- **Binary κ headline, weighted κ secondary** (chosen). Three reasons: (1) the
  roadmap deliverable names *Cohen's* κ — a categorical statistic; (2) binary κ
  measures the *pass/fail decision the grader actually ships*
  (`GradeResult.passed`), so the reliability statistic matches the shipped
  behavior, not a finer ordinal scale we never act on; (3) the project's stats
  focus is estimators + CIs, not the ordinal-weighting theory weighted κ needs.
  The `>=4` cut is **not arbitrary**: it is defined by the rubric anchors — the
  4↔3 boundary is the only place in the scale where "a fabrication or a material
  omission" first appears, which is exactly the faithful/unfaithful line.
- **Raw 5-point (nominal) Cohen's κ as headline.** Rejected: treats near-miss
  (4 vs 5) and gross (1 vs 5) disagreement identically *and* reports reliability
  on a scale finer than the binary decision we ship.
- **Quadratic-weighted κ as headline.** Rejected as the headline (kept as
  secondary): it uses the ordinal information well, but it is not the decision the
  grader emits and pulls in ordinal-weighting theory the deliverable does not ask
  for. It earns its place only as a near-miss-vs-gross diagnostic.

## Consequences

The binarization threshold is **coupled to the rubric anchors** — re-anchoring the
rubric forces re-examining the `>=4` cut, and fixture authoring (the anchor each
fixture plants) is the costly-to-redo half of this decision. To guard the §6.5
step-4 imbalanced-category concern, the report surfaces observed agreement, the
confusion matrix, and per-class agreement *alongside* κ, so a high-agreement/low-κ
base-rate artifact is visible. Weighted κ needs its own hand-verified ordinal test
vector (distinct from the unweighted literature vectors), since a 2×2 textbook κ
does not exercise the weighting.
