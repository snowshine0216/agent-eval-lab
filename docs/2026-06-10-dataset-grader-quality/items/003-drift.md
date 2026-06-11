Verdict: PASS

Subagent: sonnet / Plan checklist items: 23 / Verified present in diff: 23 / Drift findings (evidence, action each): see below / Load-bearing decisions verified: see below

---

## Plan checklist: 23/23 tasks verified present in diff

| Task | Status | Notes |
|------|--------|-------|
| T1 — LlmJudgeSpec in schema union | OK | tasks/schema.py, dataclass frozen+kw_only, added to VerificationSpec |
| T2 — parse llm_judge | OK | tasks/parse.py, _parse_scale with bool guard, 3 test cases |
| T3 — build_judge_prompt + prompt_hash | OK | graders/judge.py, sha256 over canonical JSON, scale rendered into prompt (D4) |
| T4 — parse_judge_response 3 failure cases | OK | no_score / out_of_range / conflicting_scores; _SCORE_LINE regex; repeated identical scores NOT conflicting |
| T5 — grade_llm_judge binarizes at >=4 | OK | PASS_THRESHOLD=4; _non_pass duck-typed; skip decorator removed in T9 |
| T6 — collect_judge_specs pure walk | OK | recurses AllOf exactly as grade_all_of; returns () for non-judge specs |
| T7 — thread verdicts through grade_all_of | OK | composite.py signature gains verdicts; threaded unchanged into recursive grade() call |
| T8 — dispatch LlmJudgeSpec; verdicts in grade_trajectory | OK | grade_trajectory gains optional verdicts=None->{}; routes LlmJudgeSpec to grade_llm_judge |
| T9 — run_judge + JudgeError (edge) | OK | judge_edge.py; 4 JudgeError kinds; replace() stamps judge_model+prompt_hash |
| T10 — serialize JudgeVerdict/JudgeError | OK | serialize.py verdict_to_dict/verdict_from_dict round-trips; lazy imports avoid cycle |
| T11 — agreement.py confusion matrix + kappa | OK | 4 literature vectors (V1 0.40, V2 1.0, V3 0.0, V4 0.7601); degenerate flag; empty/mismatch guards |
| T12 — weighted_kappa hand-verified ordinal | OK | 3x3 table [[10,5,0],[5,20,5],[0,5,10]] → 2/3 exact rational (D6b) |
| T13 — kappa_bootstrap_ci seeded percentile | OK | random.Random(seed); n_degenerate counted and reported (D7); determinism test |
| T14 — packet build/serialize | OK | build_packet blind (score=None); JSONL header+body; packet_from_jsonl round-trip |
| T15 — import_packet validation | OK | rejects format mismatch / order mismatch / unscored / out-of-range (D11) |
| T16 — compute_agreement + render_agreement_report | OK | binary kappa headline + CI + weighted secondary + confusion matrix |
| T17 — calibration corpus (16 fixtures, rubric, labels) | OK | fixtures.jsonl 16 fixtures; intended_labels.jsonl separate (D9); anchors 5×4,4×3,3×3,2×3,1×3 |
| T18 — CLI calibrate export-packet | OK | nested subparser (D11); _CALIBRATION_SPEC constant; writes .jsonl + .md sibling |
| T19 — CLI calibrate compute | OK | import_packet validates each; compute_agreement; --seed/--n-resamples/--alpha flags |
| T20 — provisional.py + CLI provisional-label | OK | run_provisional_labeling edge; key pre-flight skip (D12); score=None on JudgeError |
| T21 — calibration-runbook.md | OK | §6.5 state machine; fixture design table (16 rows); OPEN steps 2+3 documented |
| T22 — full-suite verification gate + ruff | OK | 296 passed; ruff check/format clean; v2 fixture unchanged; grep gate clean |
| T23 — provisional live run artifact | OK | calibration-provisional-summary.md with PROVISIONAL banner; both models ran (deepseek+glm); κ+CI+confusion matrix committed |

---

## Drift findings

**D-1 (incidental — AMEND plan): Tasks 18-20 implemented in two commits instead of three separate stub-then-fill cycles.**

Evidence: commit log shows `feat(cli): nested calibrate subparser; export-packet writes blind packet` (16bcf9d) covers T18, and `feat(calibrate): provisional LLM-annotator edge + CLI with key pre-flight skip` (4e09bcf) bundles T19+T20 provisional. Plan intended separate stub/fill steps per task. Coverage is identical — all three CLI subcommands have tests (`test_calibrate_export_packet_writes_blind_jsonl_and_md`, `test_calibrate_compute_reports_kappa_and_ci`, `test_provisional_label_skips_cleanly_when_key_unset` in `tests/test_cli.py`). Rationale: the plan's TDD steps specify red-green-refactor within a task; merging T19+T20 into one commit does not reduce coverage or break any AC. **Action: AMEND plan inline — accepted divergence, same outcome.**

**D-2 (incidental): Two lint-fix commits after implementation (92b950f, 4ae7c1e).**

Evidence: `chore: ruff format + full-suite green gate for item 003` (92b950f) reformatted 13 files (long-line wrapping, ruff style fixes, no logic changes). `style: wrap two long lines, drop unused imports (lint gate)` (4ae7c1e) fixed 2 long lines + removed unused imports in provisional.py and test files. Both are exactly the Task-22 gate commit (plan step 22.6: `git commit -m "chore: ruff format + full-suite green gate for item 003"`). 4ae7c1e also added the committed provisional summary artifact (Task 23 step 4). No logic added or removed. **Action: incidental — no amendment needed.**

**D-3 (minor divergence — AMEND plan): calibration-provisional-summary.md also bundles the "Reading this number" section with verbatim kappa+CI from the live run, beyond the plan's template placeholders.**

Evidence: committed file (`docs/2026-06-10-dataset-grader-quality/calibration-provisional-summary.md`) adds an extra "Reading this number" paragraph not in the plan's template. This is purely additive documentation. PROVISIONAL banner, kappa, CI, confusion matrix, and OPEN state are all present. **Action: AMEND plan — additive prose beyond template is acceptable.**

**D-4 (minor divergence — AMEND plan): `calibrate/provisional.py:render_provisional_summary` last line differs from plan template.**

Evidence: plan template says `"a plumbing/feasibility number, not a reliability verdict (see runbook)."` but committed code says `"a plumbing/feasibility number, not a reliability verdict"` and `"(see the calibration runbook)."` on a separate line. Text is semantically equivalent. **Action: AMEND plan — cosmetic text split acceptable.**

---

## Load-bearing decisions verified

- **D1 — collect_judge_specs pure walk + grade_all_of verdicts threading:** VERIFIED. `collect_judge_specs` in `graders/judge.py` recurses `AllOf` identically to `grade_all_of`; `grade_all_of` in `composite.py` passes `verdicts` unchanged into every recursive `grade()` call (`tests/graders/test_composite.py::test_all_of_threads_verdicts_into_every_sub_call` asserts sentinel identity).

- **D2 — JudgeError/JudgeParseFailure never coerced:** VERIFIED. `parse_judge_response` returns `JudgeVerdict | JudgeParseFailure` with no clamp/default. `run_judge` catches `HTTPStatusError`, `TransportError`, `JudgeParseFailure`, empty-choices — all return `JudgeError`, no exception escapes. Missing or error key in `verdicts` → `_non_pass()` → `passed=False`, `failure_reason=None` (tests: `test_grade_missing_verdict_is_judge_not_run`, `test_grade_judge_error_at_key_is_structured_nonpass`).

- **D3 — JudgeVerdict carries judge_model + prompt_hash:** VERIFIED. `run_judge` calls `replace(parsed, judge_model=model, prompt_hash=p_hash)` where `model = condition_id(config)`. Evidence dict in `grade_llm_judge` includes both fields. `test_run_judge_success_stamps_model_and_hash` asserts `verdict.judge_model == "deepseek:deepseek-v4-pro"`.

- **D4 — scale rendered into prompt, hash is faithful interpretation key:** VERIFIED. `build_judge_prompt` renders `f"score {lo}-{hi}"` and `f"RUBRIC (score {lo}-{hi})"` into both system messages. `test_different_scale_changes_prompt_and_hash` asserts different scales produce different prompts AND different hashes.

- **Purity guards (D1/AC 12):** VERIFIED. `grep -rE "httpx|chat_completion" graders/ metrics/agreement.py calibrate/packet.py` returns empty. `test_judge_module_imports_no_http_client` and `test_dispatch_module_imports_no_http_client` assert source text is httpx-free.

- **κ literature vectors (D6b):** VERIFIED. V1=0.40 (textbook 2×2, n=50), V2=1.0 (perfect), V3=0.0 (chance-balanced), V4=0.7601 (Cohen 1960, n=200) all pass `pytest.approx`. Weighted κ on 3×3 ordinal table = 2/3 exact (hand-verified rational, `abs=1e-9`).

- **Fixture intended labels outside blind packet (D9):** VERIFIED. `examples/calibration/fixtures.jsonl` contains `{"id", "verification", "trajectory"}` only — no `intended_anchor`, no `planted_failure`. `examples/calibration/intended_labels.jsonl` is the separate file. `test_intended_labels_are_not_in_the_fixtures_file` enforces this at CI.

- **Fixture design table (D9):** VERIFIED. `calibration-runbook.md` contains the 16-row table with `fixture_id | intended_anchor | planted_failure | description`. Anchor distribution 5×4, 4×3, 3×3, 2×3, 1×3 matches plan exactly. Binary split: 7 faithful (cf-01..07), 9 unfaithful (cf-08..16).

- **Provisional summary labeled PROVISIONAL with κ + CI + confusion matrix (AC 9):** VERIFIED. Summary opens with unmissable `> **PROVISIONAL — this is LLM-LLM agreement…**` banner; contains binary κ=0.8621, 95% CI=[0.5294,1.0000], weighted κ=0.9430, confusion matrix, and explicit "steps 2 (>=2 human annotators) and 3 (judge-human kappa) remain OPEN".

- **Runbook documents OPEN human-human/judge-human state (AC 10):** VERIFIED. Runbook step 2 is marked `**OPEN:** requires the project owner + a second human annotator (SKIPPED.md)`; step 3 is `**OPEN** until step 2 closes`.

- **D11 — calibrate is nested subparser (not flat):** VERIFIED. `_build_parser()` in `cli.py` adds `calibrate = subparsers.add_parser("calibrate")` then `cal_sub = calibrate.add_subparsers(dest="calibrate_command")` with three sub-sub-parsers. Packet JSONL carries `packet_format="calib-packet-v1"` + `rubric_version`; `import_packet` raises `ValueError` on mismatch.

- **D12 — provisional-label pre-flights provider key:** VERIFIED. `_run_provisional_label` checks `os.environ.get(config.api_key_env)` before any call and prints `"<ENV> key unset; provisional run skipped"` then returns 0. `test_provisional_label_skips_cleanly_when_key_unset` asserts exit code 0 and no file written.

---

## Plan amendments applied

1. **Task 18-20 stub-then-fill sequencing:** Plan steps that call for separate "stub" then "fill" commits for each of T18/T19/T20 are amended to accept the two-commit grouping (T18 alone; T19+T20 together), given identical test coverage.

2. **Task 23 provisional summary template:** "Reading this number" additive section is accepted as within scope.

3. **render_provisional_summary line-break cosmetic:** Two-line split of runbook reference text accepted.
