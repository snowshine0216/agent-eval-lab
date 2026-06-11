Verdict: PASS-WITH-NITS

Source: /ship steps 8+9
PR: https://github.com/snowshine0216/agent-eval-lab/pull/7

## Findings and resolutions

- BLOCKER (fixed pre-push): `compute_agreement` accepted unscored
  (score=None) items — crash on the binary path, or None==None counted as
  rater agreement (poisoned κ). Guard with structured ValueError naming
  fixture ids; ≠2 packets now an explicit error (was: silent first-two).
- BLOCKER (fixed pre-push): JudgeError graded passed=False with
  failure_reason=None and no evidence discriminator — infra failures
  indistinguishable from agent failures downstream. Evidence now carries an
  explicit nested judge_error marker; pinned: errored judge can never grade
  pass; AllOf sub_results preserve the marker; runbook documents the
  infra-vs-agent reading.
- P1 (fixed): weighted_kappa bare KeyError on out-of-category labels →
  structured ValueError. Non-atomic packet writes → tmp+os.replace. Silent
  partial provisional runs → scored/errored counts in CLI output and
  summary. Parse edge cases pinned (lowercase "score:" accepted —
  documented; bold/float fail safe).
- P1-reputational (fixed): all 9 unfaithful fixtures were gross violations —
  κ partly reflected case easiness. Four near-miss boundary fixtures
  (cf-17..cf-20) added; provisional re-run (n=19 scored, 1 GLM judge error
  surfaced): binary κ 0.8725, weighted 0.9396; summary gained an honest
  "Difficulty profile" section.

- Verified clean by reviewers: κ math (po/pe recomputed by hand twice,
  matches to 4 decimals), prompt-injection containment (digest prefixing),
  fixture hash uniqueness, pure/edge boundary (no httpx in graders/metrics),
  packet blindness (no intended labels in exported packet), v1/v2 parse
  backward compat.

- NIT (noted): compute_agreement third-annotator support deferred (explicit
  error now; Krippendorff α flagged as future work in runbook).
- NIT (noted): parse_judge_response called outside the edge yields verdicts
  with empty judge_model/prompt_hash (stamped only by run_judge) — pure-path
  callers documented in docstring.
