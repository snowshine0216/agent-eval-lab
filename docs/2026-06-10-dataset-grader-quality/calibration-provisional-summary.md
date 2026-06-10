# Calibration — PROVISIONAL summary (item 003)

> **PROVISIONAL — this is LLM-LLM agreement, NOT the human-human reliability that
> calibration protocol §6.5 step 2 requires.** It proves the export -> label ->
> compute pipeline works end-to-end. Protocol step 2 (>=2 human annotators) and step 3
> (judge-human kappa) remain **OPEN**. Unblock path: the user fills the packet, recruits
> annotator #2 (see SKIPPED.md), and re-runs `calibrate compute` to replace these numbers.

- Annotator models that ran: `deepseek:deepseek-v4-pro, glm:Pro/zai-org/GLM-5.1`
- Models skipped (missing key): none
- Fixtures: 16 (examples/calibration/fixtures.jsonl)
- Binary Cohen's kappa (LLM-LLM) = `0.8621`
- 95% percentile bootstrap CI = `[0.5294, 1.0000]` (n_resamples=2000, seed=20260610, degenerate_resamples=`0`)
- Weighted (quadratic) kappa = `0.9430`
- Observed agreement = `0.9375`; degenerate = `False`

## Confusion matrix (binary)

| A \\ B | faithful | unfaithful |
|---|---|---|
| faithful | 5 | 1 |
| unfaithful | 0 | 10 |

(A = deepseek:deepseek-v4-pro, B = glm:Pro/zai-org/GLM-5.1)

## Reading this number

At n in [12, 20] the bootstrap CI is wide and n-dominated — a plumbing/feasibility
number, not a reliability verdict. The kappa >= 0.6 acceptance bar applies to the
human-labeled set the user produces, not to this LLM-LLM run. The LLM-LLM kappa of
0.86 looks strong, but the CI is wide ([0.53, 1.00]) because n=16. See
`calibration-runbook.md`.
