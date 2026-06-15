Verdict: PASS

Subagent: sonnet
Plan checklist items: 8 tasks / ~30 steps
Verified present in diff: all 8 tasks, all material steps
Step 7.4 (0 pass^k moves) verdict: verified data-growth (invariant proof)

---

## Step-by-step review

**Task 1 (censor `pass_pow_k` + `task_reliability`):** OK
- `_run_passes` helper added in `reliability.py` lines 21-33 (diff lines 205-217).
  Predicate: `run.grade.passed and not (traj.safety_cap_bound or getattr(traj, "max_rounds_bound", False))`.
  Matches plan §D.4 exactly — `getattr` defensive read confirmed present.
- `pass_pow_k` routes through `_run_passes` (diff line 228).
- `task_reliability` routes through `_run_passes` (diff line 242).
- `pass_at_1` and `failure_counts` left unchanged (diff shows `pass_at_1` still uses `run.grade.passed`).
- All five censoring tests present and match plan spec (diff lines 427-473).
- Step 1.6 Fisher-inheritance test present (diff lines 467-473).

**Task 2 (historical invariant test):** OK
- `tests/metrics/test_reliability_historical.py` created (diff lines 474-519).
- `test_no_historical_record_is_a_passed_and_capped_run` and `test_historical_corpus_is_non_empty` present, match plan spec exactly.
- Both tests PASS when run (`uv run pytest tests/metrics/test_reliability_historical.py -v`: 2 passed).

**Task 3 (fc-v4 Row E.1 — `node_execution` leaf fix):** OK
- `first_execution_evidence` guard changed: `if grader_id in ("execution", "node_execution"):` (diff line 344).
- Docstring updated (diff line 336).
- Three E1 tests present (diff lines 604-628): `test_e1_failing_node_execution_leg_is_oracle_red`, `test_e1_top_level_node_execution_grader_is_found`, `test_e1_first_execution_evidence_matches_node_execution`.

**Task 4 (fc-v4 Rows E.2 + E.3 — `budget_exhausted`):** OK
- `budget_exhausted` added to closed `Subcategory` Literal (diff line 304). Count comment updated to 20 (diff lines 294-296).
- `_CAP_STOP_REASONS = frozenset({"safety_cap", "max_rounds"})` added (diff line 312).
- `_cap_bound(run)` predicate added (diff lines 315-329). Uses `safety_cap_bound`, `getattr(traj, "max_rounds_bound", False)`, and `stop_reason in _CAP_STOP_REASONS`.
- `classify_run` row-1 guard updated: `if run.grade.passed and not cap_bound:` (diff line 356).
- `_classify_grade_and_budget` signature extended with `cap_bound: bool` (diff line 374). Budget-cap block inserted before `max_steps` block (diff lines 382-388).
- `_run` test helper extended with `safety_cap_bound` parameter in `test_classify.py` (diff lines 528, 536).
- All seven E2/E3 tests present (diff lines 632-668). Legacy max_steps backward-compat test present.

**Task 5 (bump CLASSIFIER_VERSION to fc-v4):** OK
- `CLASSIFIER_VERSION = "fc-v4"` (diff line 283).
- Module docstring updated with fc-v4 section (diff lines 261-275).
- `test_classifier_version_is_fc_v4`, `test_fc_v4_version_label`, `test_subcategory_vocabulary_is_closed_at_20_after_fc_v4` all present (diff lines 547-577).
- `test_classify_properties.py` updated: `"max_rounds"` added to stop_reason sampled_from (diff line 677), `safety_cap_bound=st.booleans()` added (diff line 685), classifier_version assertion changed to `"fc-v4"` (diff line 694).
- Step 5.5 propagation updates: `test_committed_runs.py` (diff line 746), `test_m1_build.py` (diff line 720), `test_final.py` (diff line 707), `test_m1_render.py` (diff line 733) — all four updated.

**Task 6 (ADR-0013 fc-v4 amendment):** OK
- `docs/adr/0013-failure-classification-is-derived-total-and-versioned.md` amended with fc-v4 section (diff lines 22-59). All three row changes documented. Defensive `max_rounds_bound` read noted. Historical proof reference included.

**Task 7 (re-emit M1-F report):** OK with one Step 7.4 deviation — see below.
- `reports/agentic-v1/M1-F-report.md` added as a new file (diff lines 60-196).
- Header reads `classifier fc-v4` (report line 4). Verified: `grep "classifier fc-v4"` matches line 4.
- Taxonomy moves confirmed: `oracle_red` appears in 5 per-condition taxonomy rows; `budget_exhausted` appears for GLM F2 (5 safety_cap runs). Residual `other_miss` (GLM F3, 5 rows) is correct: those administrative `marked_failed_not_executed` records have no `execution` key in evidence, so `first_execution_evidence` correctly returns None and they fall through to `other_miss`.
- Step 7.3 verified. Step 7.5 verified.

**Task 8 (full-suite verification):** OK
- 163 tests pass (`uv run pytest tests/metrics tests/reports tests/test_committed_runs.py`).
- `ruff check` and `ruff format --check` both clean.

---

## Step 7.4 deviation analysis

**Plan spec (Step 7.4):** "Capture pre-change pass^k table for the diff guard" (Step 7.1), then after re-emit: `diff /tmp/m1f-passk-before.txt /tmp/m1f-passk-after.txt && echo "PASS^K UNCHANGED"`. Expected: empty diff (byte-identical).

**Actual:** `reports/agentic-v1/M1-F-report.md` did not exist on the feature base branch (`autodev/harness-rounds-f-ablation-feature`) or on any prior commit in any branch. The file was never tracked in git before this branch. Therefore Step 7.1 ("capture pre-change") had no source file, and the byte-identical diff in Step 7.4 was unrunnable.

**Impl agent's claimed explanation:** "pass^k numbers DID change, attributes to GLM going 5→15 valid runs." Verified: GLM F JSONL has 15 records (F1×5 + F2×5 + F3×5), all `passed=False`. The 5 F2 records have `safety_cap_bound=True` and `passed=False`. The 5 F3 records are administrative `marked_failed_not_executed` entries. Zero GLM records have `passed=True`. Therefore GLM pass^k=0.000 is unchanged whether or not the censor fires.

**Spec acceptance criterion "Zero pass^k numbers move":** Satisfied by the invariant proof:
- `test_no_historical_record_is_a_passed_and_capped_run` iterates all committed JSONL records (≥1000 corpus confirmed by `test_historical_corpus_is_non_empty`) and asserts `offenders == []`. Both tests PASS.
- Direct inspection of GLM F JSONL confirms: the 5 `safety_cap_bound=True` records all have `passed=False`, so the censor never fires on a would-be pass.
- The byte-identical diff check was an implementation-level verification step, NOT the spec acceptance criterion. The spec acceptance criterion is the empirical invariant test (Task 2), which passes.

**Ruling:** verified data-growth (invariant proof). The step 7.4 byte-identical diff check was unrunnable because the file was a first-time emit. The 0-moves guarantee is established by `test_no_historical_record_is_a_passed_and_capped_run`. NOT a finding — accepted.

---

## Incidental scope

- `docs/2026-06-15-harness-rounds-f-ablation/PROGRESS.md`: tracker row update (branch + impl SHA). Incidental process tracking — ignored.
- `fix(lint): E501 + import sort` commit (2fd47fb): line-wrapping and import-sort fixes in `classify.py`, `test_reliability.py`, `test_reliability_historical.py`. Purely formatting — ignored.

---

## Drift findings

None. All plan steps verified present in the diff and matching intent. The only deviation (Step 7.4 byte-identical diff) is accepted on invariant-proof grounds.
