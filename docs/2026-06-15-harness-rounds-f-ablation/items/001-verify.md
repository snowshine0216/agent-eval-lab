Verdict: PASS

Subagent: sonnet
Source: Fallback used: uv run pytest + uv run python -m agent_eval_lab.cli report-m1
Entry point exercised:
  1. `uv run pytest -q -o addopts="" tests/reports/test_classify.py tests/reports/test_classify_properties.py tests/metrics/test_reliability.py tests/metrics/test_reliability_historical.py`
  2. `uv run python -m agent_eval_lab.cli report-m1 --spec reports/agentic-v1/M1-spec.frozen.json --runs F:deepseek:... --out reports/agentic-v1/M1-F-report.md --seed 20260613 --n-resamples 2000 --alpha 0.05`

Observed behavior:
  - `CLASSIFIER_VERSION = "fc-v4"` — confirmed: `grep -n CLASSIFIER_VERSION src/agent_eval_lab/reports/classify.py` → line 59: `CLASSIFIER_VERSION = "fc-v4"`
  - Row E.1 (`node_execution` leaf fix) — `first_execution_evidence` accepts `"node_execution"` at classify.py:150 (`if grader_id in ("execution", "node_execution"):`); tests `test_e1_failing_node_execution_leg_is_oracle_red`, `test_e1_top_level_node_execution_grader_is_found`, `test_e1_first_execution_evidence_matches_node_execution` all PASS; failing node-F runs now land in `agent_failure / oracle_red` (confirmed in re-emitted report: deepseek=13, glm=5, minimax=15, qwen35=12, qwen36=10 oracle_red rows)
  - Row E.2 (cap-bound budget override) — `_CAP_STOP_REASONS = frozenset({"safety_cap", "max_rounds"})` at classify.py:120; `_cap_bound()` at classify.py:123 fires on `safety_cap_bound` flag or cap stop reasons; tests `test_e2_failing_safety_cap_run_is_budget_exhausted`, `test_e2_failing_safety_cap_bound_flag_is_budget_exhausted`, `test_e2_failing_max_rounds_run_is_budget_exhausted` PASS; glm condition shows 5 `budget_exhausted` rows in re-emitted report
  - Row E.3 (row-1 cap-bound guard) — `classify_run` at classify.py:171: `cap_bound = _cap_bound(run)` computed first; row-1 guard is `if run.grade.passed and not cap_bound:`; tests `test_e3_passed_but_safety_cap_bound_is_budget_exhausted`, `test_e3_passed_but_max_rounds_stop_is_budget_exhausted` PASS; `test_e3_passed_uncapped_still_passes` still PASS (backward compat)
  - Legacy `max_steps` stays `step_exhaustion` — `test_e2_legacy_max_steps_still_step_exhaustion` PASS; D2 decision honored
  - Classifier pure/total/never-raises — Hypothesis `test_classify_run_is_total_and_closed` exercises fc-v4 paths (sampled_from includes `"max_rounds"`, `safety_cap_bound` in strategy); PASS
  - ADR-0013 amended — `grep -n "fc-v4" docs/adr/0013-failure-classification-is-derived-total-and-versioned.md` → lines 85–121 contain the full fc-v4 amendment block (2026-06-15 entry)
  - `pass_pow_k` censor on `safety_cap_bound OR max_rounds_bound` — `_run_passes()` at reliability.py:21 reads `traj.safety_cap_bound or getattr(traj, "max_rounds_bound", False)`; routed by both `pass_pow_k` (line 45) and `task_reliability` (line 76); `test_pass_pow_k_censors_a_capped_pass` and `test_task_reliability_censors_a_capped_pass` PASS
  - Defensive `max_rounds_bound` read — `getattr(traj, "max_rounds_bound", False)` at reliability.py:32; `test_defensive_max_rounds_bound_read_when_field_absent` confirms field absent on existing records and `pass_pow_k` returns 1.0; PASS
  - Bootstrap CI and Fisher path inherit censor — `test_bootstrap_ci_inherits_the_censor` (ci.point==0.0 for capped pass) and `test_comparisons_fisher_path_inherits_censor` (sum==0) both PASS; no re-implementation needed
  - Re-emit M1-F report — command exited 0, output: `reports/agentic-v1/M1-F-report.md`; header line 4: `classifier fc-v4` confirmed by `grep -n "classifier fc-v4"` → line 4 match
  - Zero `pass^k` numbers move — `diff /tmp/m1f-passk-before.txt /tmp/m1f-passk-after.txt` produced no output → `PASS^K UNCHANGED`; `test_no_historical_record_is_a_passed_and_capped_run` PASS (0 offenders, corpus ≥1000 confirmed by `test_historical_corpus_is_non_empty`)
  - Taxonomy outputs moved — `other_miss` count in re-emitted report: 1 (glm only, non-execution failures); `oracle_red` count: 5 occurrences; `budget_exhausted` newly present for glm (5 runs); failure taxonomy section shows `oracle_red` rows for deepseek/glm/minimax/siliconflow conditions where `other_miss` previously appeared
  - Full test suite: 70 passed, 0 failed, 0 errors in 0.69s

Failures: none
