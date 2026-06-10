Verdict: PASS

Subagent: opus
Questions resolved: 12 (8 adversarial angles D1–D12; D1/D2/D3 strengthened the purity
boundary; D4/D6/D8 hardened determinism + parse contract; D5 coupled threshold to anchors;
D6b/D7 closed TDD/CI gaps; D9 demanded the fixture design table; D11/D12 sharpened CLI + key
handling) — no unresolvable contradiction found; the spec's central claims hold against code.

## Docs touched

| File | Change |
|------|--------|
| `CONTEXT.md` | +7 model-based-grading terms (Judge rubric, Summary fidelity, JudgeVerdict, prompt hash, Annotation packet, Cohen's κ headline-binary, Provisional calibration); +2 dialogue turns exercising them |
| `docs/adr/0005-judge-verdicts-precomputed-at-edge-threaded-into-pure-grader.md` | new ADR (D1/D2/D3 — purity boundary) |
| `docs/adr/0006-binary-cohens-kappa-is-the-headline-judge-reliability-statistic.md` | new ADR (D5 — binary-κ headline) |
| `docs/2026-06-10-dataset-grader-quality/items/003-spec.md` | refined in place (strike-throughs + `## Resolved decisions`) |
| `docs/2026-06-10-dataset-grader-quality/items/003-grill.md` | self |

## Spec refined (in place)

Inline strike-throughs (nothing deleted) keyed `Resolved Dn`, + appended `## Resolved decisions`:
- **Architecture** — `JudgeVerdict` gains `judge_model`+`prompt_hash` (self-describing, D3);
  `parse_judge_response`/`run_judge` return failure sum types `JudgeParseFailure`/`JudgeError`
  (D2); named pure `collect_judge_specs` tree-walk + `grade_all_of` signature gains `verdicts`
  (D1); `scale` rendered into the prompt for key soundness (D4); canonical digest reuses
  `graders/canonical.py` (D8).
- **Rubric section** — `>=4` threshold defined by the 4↔3 anchor boundary, not free (D5).
- **AC 2** — three enumerated parse-failure cases + `SCORE: <int>` extraction contract (D6);
  full evidence field list (D3).
- **AC 4** — edge returns `JudgeVerdict | JudgeError`; integration test covers failure (D2).
- **AC 5** — separate hand-verified weighted-κ ordinal vector (D6b); degenerate-resample
  count/flag policy (D7).
- **AC 6** — `packet_format`+`rubric_version`; intended-label never in packet (D9/D11).
- **AC 7** — fixture design table is a required deliverable (D9).
- **AC 8** — nested `calibrate` subparser group (D11).
- **AC 9** — pre-flight key check + documented skip; keys confirmed in `../.env` (D12).
- **AC 10** — percentile-over-BCa justification + honest n≈12–20 wide-CI caveat (D7).
- **Constraints** — `JudgeError`/`JudgeParseFailure` added to frozen-records list.

## Resolved decisions

(Full D1–D12 with A / Rationale / Doc impact live in `003-spec.md` § "Resolved decisions
(grill, 2026-06-10)". Summary of the load-bearing ones:)

- **D1** — pure `collect_judge_specs` walks the spec tree; `grade_all_of` signature gains
  `verdicts` (precedent: item 001's `initial_state` threading). Verified no collector exists.
- **D2** — judge failure is an explicit sum type (`JudgeError` edge / `JudgeParseFailure` pure),
  mirroring `ToolOutcome`/`ParseFailure`; a failure ⇒ structured non-pass (`failure_reason=None`),
  never coerced. Verdict-map value type widened to `JudgeVerdict | JudgeError`.
- **D3** — `JudgeVerdict` carries `judge_model`+`prompt_hash` because it is the only edge→core
  channel; this is the load-bearing consequence of the purity boundary (feeds ADR 0005).
- **D4** — prompt hash keys verdicts; `scale` rendered into the prompt makes the hash a faithful
  interpretation key; identical-prompt dedup is correct.
- **D5** — `>=4` defined by anchors (fabrication/material-omission begins at 3); couples
  threshold to rubric (feeds ADR 0006).
- **D6 / D6b** — `SCORE: <int>` extraction; three enumerated parse failures; weighted κ needs its
  own ordinal test vector.
- **D7** — percentile CI (justified over BCa); honest n-dependence in runbook; degenerate
  resamples counted/flagged, never dropped/crashed.
- **D8** — canonical trajectory-order digest reusing `graders/canonical.py`; `ToolSuccess`/
  `ToolFailure` discriminator preserved; result truncation out of scope.
- **D9** — fixture design table required; intended label outside the blind packet.
- **D11** — nested `calibrate` subparser; versioned `packet_format`.
- **D12** — provisional run feasible (keys present); pre-flight + documented skip on absent keys;
  CI never depends on the network.

### ADRs cleared the bar (3-of-3)

- **ADR 0005** — purity boundary (edge pre-computes verdicts, pure grader reads). CLEARS:
  hard to reverse (architectural; precedent for `ExecutionSpec`), surprising ("why not inline?"),
  real trade-off (needs_judge-marker / inject-client both rejected with reasons). Written.
- **ADR 0006** — binary Cohen's κ headline, weighted κ secondary. CLEARS: surprising (ordinal
  textbook choice is weighted κ), real trade-off (raw/binarized/weighted-headline), rubric-anchor
  coupling makes fixture authoring costly to redo. Written.

No third ADR offered: D2 (sum-type failure), D7 (percentile CI), D9 (fixture table) and the
no-new-`FailureCategory` decision (spec Q7) are all the obvious consistent extension of an
existing documented pattern — not surprising deviations with live alternatives.
