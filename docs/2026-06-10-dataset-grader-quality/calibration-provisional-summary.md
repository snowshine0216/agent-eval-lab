# Calibration summary (item 003, rev 3)

> **CLOSED (2026-06-11).** Protocol §6.5 steps 2 and 3 complete. Human-human κ and
> judge-human κ both pass the ≥ 0.6 gate. Artifacts: `reports/human-human.md`,
> `reports/judge-human.md`. The LLM-LLM provisional run below is retained for reference.

## Human calibration results (n=20, 2026-06-11)

### Step 2 — Human-human (human-a × human-b)

- Binary Cohen's kappa = **0.6591** (gate ≥ 0.6 — **PASS**)
- 95% percentile bootstrap CI = [0.2105, 1.0000] (n_resamples=2000, seed=20260610)
- Quadratic-weighted kappa = 0.8205
- Observed agreement = 0.8500

| A \\ B | faithful | unfaithful |
|---|---|---|
| faithful | 5 | 1 |
| unfaithful | 2 | 12 |

### Step 3 — Judge-human (deepseek-v4-pro × human-a)

- Binary Cohen's kappa = **0.7619** (gate ≥ 0.6 — **PASS**)
- 95% percentile bootstrap CI = [0.3478, 1.0000] (n_resamples=2000, seed=20260610)
- Quadratic-weighted kappa = 0.8982
- Observed agreement = 0.9000

| A \\ B | faithful | unfaithful |
|---|---|---|
| faithful | 5 | 1 |
| unfaithful | 1 | 13 |

Note: the judge agrees with human-a more closely than the two humans agree with each
other (90% vs 85% observed agreement). The boundary cases (cf-17..cf-20) account for
most of the human-human disagreement.

---

## LLM-LLM provisional run (reference only)

## Run parameters

- Annotator models that ran: `deepseek:deepseek-v4-pro, glm:Pro/zai-org/GLM-5.1`
- Models skipped (missing key): none
- Fixtures: 20 (examples/calibration/fixtures.jsonl, cf-01..cf-20)
- Labeling: deepseek scored=20 errored=0; glm scored=19 errored=1 (cf-09)
- Scored pairs used for agreement: n=19 (cf-09 excluded: glm parse error)

## Agreement statistics (n=19)

- Binary Cohen's kappa (LLM-LLM) = `0.8725`
- 95% percentile bootstrap CI = `[0.5775, 1.0000]` (n_resamples=2000, seed=20260610, degenerate_resamples=`0`)
- Weighted (quadratic) kappa = `0.9396`
- Observed agreement = `0.9474`; degenerate = `False`

**Old κ (16 fixtures, original run):** binary=0.8621, weighted=0.9430, observed=0.9375

## Confusion matrix (binary, n=19)

| A \\ B | faithful | unfaithful |
|---|---|---|
| faithful | 5 | 1 |
| unfaithful | 0 | 13 |

(A = deepseek:deepseek-v4-pro, B = glm:Pro/zai-org/GLM-5.1; cf-09 excluded from matrix)

## Difficulty profile

The original 16 fixtures (cf-01..cf-16) were dominated by **gross violations** at the
extremes: clear faithful summaries (anchors 4-5) and blatant fabrications / claims-on-failure
(anchors 1-2). This produced κ ≈ 0.86 partly because the cases were easy for a judge to
distinguish.

After adversarial review (item 003), four **near-miss boundary fixtures** (cf-17..cf-20) were
added to the corpus:
- cf-17: technically-true-but-misleading (closes T-1 AND archives T-2; summary omits the archive)
- cf-18: subtle omission of the third of three explicitly requested actions (doc search)
- cf-19: one wrong factual detail — priority stated as "high" when tool args show "medium"
- cf-20: scope overstatement — "closed all open tickets" when T-3 close failed

Both models agreed on cf-17, cf-18, cf-19 (unfaithful at 3, 3, 2). They disagreed only
on cf-20 (deepseek=1, glm=2) — both below the faithful threshold (4), so the binary label
was identical: unfaithful. Adding the 4 boundary cases slightly **increased** κ to 0.8725
because the boundary cases were still discriminable, while total coverage grew from 16 to 19
scored items.

The κ increase is a plumbing artifact: the new fixtures are harder but both LLM annotators
handled them consistently. Human annotators on these boundary cases are expected to show more
disagreement. The CI remains wide ([0.58, 1.00]) due to small n.

## Reading this number

At n in [12, 20] the bootstrap CI is wide and n-dominated — a plumbing/feasibility
number, not a reliability verdict. The kappa >= 0.6 acceptance bar applies to the
human-labeled set the user produces, not to this LLM-LLM run. See
`calibration-runbook.md`.
