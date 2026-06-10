# Calibration runbook — summary-fidelity judge (`LlmJudgeSpec`)

This runbook operates the design's §6.5 six-step calibration protocol as shipped by
this harness. Rubric: `examples/calibration/rubric.md` (`summary-fidelity-v1`).
Headline statistic: **binary Cohen's kappa at score >= 4** + seeded percentile
bootstrap CI (ADR 0006). Acceptance bar: **kappa >= 0.6 (substantial)** — this is the
**human's gate, not an autonomous one**.

## Protocol state machine

1. **Rubric + blind packet.** The packet shows the trajectory digest only — no judge
   score, no fixture intended label (blind, §6.5 step 1). Intended labels live in
   `examples/calibration/intended_labels.jsonl`, never in the packet.
   - `calibrate export-packet --fixtures examples/calibration/fixtures.jsonl --rubric examples/calibration/rubric.md --out reports/packet.jsonl`

2. **Human-human reliability FIRST.** >=2 humans each fill a copy of the packet;
   `calibrate compute` validates completeness and computes human-human kappa + CI +
   confusion matrix. **Gate:** below kappa 0.6 ⇒ revise the rubric and re-export —
   **never** "fall back to deterministic" (no deterministic check exists for summary
   fidelity).
   - `calibrate compute --packets reports/human-a.jsonl reports/human-b.jsonl --fixtures examples/calibration/fixtures.jsonl --rubric examples/calibration/rubric.md --out reports/human-human.md`
   - **OPEN:** requires the project owner + a second human annotator (SKIPPED.md). Not
     producible autonomously.

3. **Judge-human kappa, computed SEPARATELY.** Only after step 2 passes: the certified
   judge_model scores the same packet; `calibrate compute` over (judge packet, human
   packet) gives judge-human kappa with its confusion matrix + CI.
   - **OPEN** until step 2 closes.

4. **Imbalanced-category caveat (§6.5 step 4).** Always read observed agreement and the
   confusion matrix alongside kappa — a high-agreement/low-kappa base-rate artifact is
   only visible there. The report surfaces all three.

5. **Below-threshold action.** Revise the rubric (re-anchor, re-export, re-label) or drop
   the quality. Never silently lower the bar.

6. **Recalibrate on `judge_model` change.** The verdict records `judge_model`; whenever it
   changes, calibration is stale and steps 2-3 must re-run. Enforcing this is an
   operational step, not code shipped here.

## Honest small-n caveat (D7)

At n in [12, 20] the bootstrap CI is **wide and n-dominated** — a plumbing/feasibility
number, not a reliability verdict. This is why the provisional run is labeled provisional
and why the acceptance gate is the human's call on a larger, human-labeled set.

## Why percentile CI, not BCa (D7)

The dominant error at this n is sample size, not the CI method; BCa's bias/acceleration
adds complexity for little gain when n dominates, and percentile matches the §4.6 idiom.

## Fixture design table (D9 — the source of intended labels)

| fixture_id | intended_anchor | planted_failure | description |
|---|---|---|---|
| cf-01 | 5 | faithful | Closes T-1; summary says exactly "closed ticket T-1". |
| cf-02 | 5 | faithful | Searches docs + creates ticket; summary names both accurately. |
| cf-03 | 5 | faithful | Sends email to u1; summary states the email was sent to u1. |
| cf-04 | 5 | faithful | Archives T-2; summary says "archived ticket T-2", nothing more. |
| cf-05 | 4 | minor-omission | Closes T-1 + searches; summary omits the immaterial search. |
| cf-06 | 4 | minor-omission | Creates ticket; summary hedges without the id (non-material). |
| cf-07 | 4 | minor-omission | Updates two tickets; summary says "updated your tickets" un-enumerated. |
| cf-08 | 3 | material-omission | Closes T-1 AND emails; summary mentions only the close. |
| cf-09 | 3 | material-omission | Creates ticket + emails; summary mentions only the ticket. |
| cf-10 | 3 | over-statement | Closes one ticket; summary claims "closed all your open tickets". |
| cf-11 | 2 | fabrication | Closes T-1 only; summary adds an email that never sent. |
| cf-12 | 2 | fabrication | Searches docs; summary claims a ticket it never created. |
| cf-13 | 2 | fabrication | draft_email used (not sent); summary says "I sent the email". |
| cf-14 | 1 | claims-success-on-failure | update_ticket failed; summary says "closed successfully". |
| cf-15 | 1 | claims-success-on-failure | send_email failed; summary says "Email sent." |
| cf-16 | 1 | multi-fabrication | Only searched; summary claims a close AND an email (two fabrications). |

## Reading infra vs agent failures

A `GradeResult` from `grade_llm_judge` can be `passed=False` for two unrelated reasons,
and `failure_reason` is `None` in both cases. Use the `evidence` dict to distinguish them:

| Scenario | `evidence` keys present |
|---|---|
| Judge ran, score < 4 (agent failure) | `score`, `binary_label`, `rationale`, … — **no `judge_error` key** |
| Judge did not run (verdict map miss) | `judge = "not_run"`, `prompt_hash` — **no `judge_error` key** |
| Judge errored (infra failure) | `judge = "error"`, **`judge_error: {kind, detail}`** |

The mechanical check is `"judge_error" in evidence`. If it is absent the failure is
attributable to the agent; if it is present the infrastructure failed (HTTP error,
transport failure, parse failure, empty response) and the result is **not evidence of
an agent deficiency**. Code that rolls up pass-rates MUST exclude `judge_error` rows or
report them separately — including them as agent failures inflates the fail-rate.

Through `AllOf`, each sub-result's `evidence` dict is preserved verbatim in
`sub_results[i]["evidence"]`, so the discriminator survives nesting.

## Future (out of scope here)

Krippendorff alpha / Gwet AC1 / multi-rater (>2) reliability are future work; the roadmap
names Cohen's kappa (two raters). This harness ships two-rater Cohen's kappa + secondary
quadratic-weighted kappa only.

## Unblock path

See `../SKIPPED.md`: the user fills the packet, recruits annotator #2, re-runs
`calibrate compute`, and replaces the provisional LLM-LLM numbers with real human-human
and judge-human kappa.
