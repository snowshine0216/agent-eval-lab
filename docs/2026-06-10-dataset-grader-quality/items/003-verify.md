Verdict: PASS

Subagent: sonnet
Source: claude/dataset-grader-quality-003
Entry points exercised: CLI help, export-packet, compute (perfect agreement + corrupt-packet + null-score), judge grading path (AllOf round-trip + parse failures + JudgeError), provisional summary inspection, pytest + ruff check + ruff format --check.

## Observed behavior per criterion

**AC1 — LlmJudgeSpec parses:**
`verification_from_dict({'type':'llm_judge', ...})` returns an `LlmJudgeSpec` with default `scale=(1,5)`. Custom scale `[1,7]` parses to `(1,7)`. An invalid scale `[5,1]` raises `ValueError: scale must have lo < hi`. `LlmJudgeSpec` is in the `VerificationSpec` union in `tasks/schema.py`. PASS.

**AC2 — Pure judge core:**
`build_judge_prompt` produces 2 messages, renders scale (`1-5`) and `SCORE:` contract. `parse_judge_response("...\nSCORE: 5", scale=(1,5))` returns `JudgeVerdict(score=5)`. Three parse failures confirmed: `"no_score"` (no integer), `"out_of_range"` (SCORE:9), `"conflicting_scores"` (SCORE:4/SCORE:2). `grade_llm_judge` binarizes at ≥4. Evidence carries `judge_model`, `prompt_hash`, `score`, `scale`, `threshold`, `binary_label`, `rationale`, `raw`. Missing key → `evidence["judge"]=="not_run"`, `failure_reason=None`. `JudgeError` at key → `evidence["judge"]=="error"`, `judge_error={"kind":..., "detail":...}`. Module imports no http client (confirmed by test `test_judge_module_imports_no_http_client`). PASS.

**AC3 — Dispatch threads verdicts + AllOf judge leg:**
`grade_trajectory(verification=AllOf(specs=(FinalStateSpec, LlmJudgeSpec)), ..., verdicts={h:v5})` → `passed=True`, `sub_results` has both grader_ids `["final_state","llm_judge"]`. SCORE:2 with passing deterministic leg → `passed=False` (AND). `JudgeParseFailure` at key → `passed=False`, `judge_error` in sub-result evidence. All existing tests (315 total) pass unchanged. PASS.

**AC4 — Edge records auditable evidence:**
`runners/judge_edge.py` exists; integration tests (test_provisional.py) stub the http client. `run_judge` stamps `judge_model` + `prompt_hash` on verdict. Transport error / parse failure → `JudgeError` (not a crash). No live call required by tests. PASS.

**AC5 — Cohen's κ + bootstrap CI:**
Perfect agreement → κ=1.0. Chance-level → κ≈0.0. Degenerate (all-same-category) → κ=0.0 with `degenerate=True`, no `ZeroDivisionError`. Seeded bootstrap CI deterministic; `n_degenerate` counted. Quadratic-weighted κ over 3×3 ordinal table → 0.7843 (hand-computable). PASS.

**AC6 — Blind packet export/import/validate:**
`calibrate export-packet` writes 20 items, all `score=None`, no `intended_label` field, `packet_format=calib-packet-v1`. `import_packet` (called via `calibrate compute`) rejects: dropped item → `ValueError: item order/set mismatch`; null score → `ValueError: unscored item: 'cf-05'`. With ≥2 valid packets → κ + CI + confusion matrix computed. PASS.

**AC7 — Calibration corpus:**
`examples/calibration/fixtures.jsonl` has 20 fixtures (in [12,20]). All parse; every `LlmJudgeSpec` is inside `AllOf` with a deterministic leg. Intended anchors span {1,2,3,4,5} (≥3). Fixture design table committed in `calibration-runbook.md` with all 20 rows. PASS.

**AC8 — CLI surface:**
`--help` shows nested `calibrate {export-packet,compute,provisional-label}` sub-subparser group coexisting with `run-baseline`. Both `export-packet` and `compute` delegate to pure core. Full round-trip (20-item perfect-agreement) verified end-to-end. PASS.

**AC9 — Provisional run:**
`docs/.../calibration-provisional-summary.md` committed. PROVISIONAL banner present in first lines. Records: annotator models deepseek + glm, scored/errored counts (deepseek=20/0, glm=19/1), κ=0.8725, CI=[0.5775,1.0000], confusion matrix, and explicit statement that LLM–LLM ≠ human–human; steps 2–3 OPEN. PASS.

**AC10 — Runbook:**
`calibration-runbook.md` documents all 6 protocol steps. Names κ≥0.6 bar (human's gate). States n≈12–20 CI is wide and n-dominated (feasibility, not verdict). Justifies percentile over BCa. Cross-references SKIPPED.md. Fixture design table with 20 rows present. PASS.

**AC11 — v2 unchanged:**
`workspace_tool_use_v2.jsonl` has 0 occurrences of `llm_judge`. Conformance test still in suite and green. PASS.

**AC12 — Gates:**
`uv run pytest` → 315 passed (0 failed). `uv run ruff check .` → All checks passed. `uv run ruff format --check .` → 77 files already formatted. PASS.

## Failures: none
