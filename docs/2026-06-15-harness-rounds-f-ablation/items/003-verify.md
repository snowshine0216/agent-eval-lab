Verdict: PASS

Subagent: sonnet
Source: library escape hatch
Entry point exercised:
  - `python -m pytest tests/datasets/test_f_tasks.py tests/runners/test_f_candidate.py -o addopts="" -rs -q`
  - `python -c "from agent_eval_lab.datasets.f_tasks import build_f_task_arms; ..."` (direct import smoke)
  - `python -m pytest tests/experiments/test_m1_spec.py tests/experiments/test_spec_hash.py -o addopts="" -q`

Observed behavior:
  - 12 arms with suffixed ids — `build_f_task_arms` returns 12 tasks; ids: `f-f1-bare`, `f-f1-both`, `f-f1-feedback`, `f-f1-prompt`, `f-f2-*`, `f-f3-*`; confirmed by `test_build_f_task_arms_returns_twelve_arms_with_suffixed_ids` PASSED and direct import smoke (`arm count: 12`).
  - Arms share verification + tree — `test_four_arms_of_a_base_share_verification_and_tree_state` PASSED; direct smoke confirms all four f1 arms constructible with shared base.
  - 2×2 P/V mapping — direct import smoke: `bare factor_p=False factor_v=False tools=('bash',)`, `prompt factor_p=True factor_v=False tools=('bash',)`, `feedback factor_p=False factor_v=True tools=('bash','run_tests')`, `both factor_p=True factor_v=True tools=('bash','run_tests')`; confirmed by `test_arms_differ_only_in_factor_flags_and_tools` PASSED.
  - Factor P block present on prompt/both via make_edit_task — `test_factor_p_block_present_only_on_prompt_and_both_arms` PASSED; `test_make_edit_task_without_flag_keeps_unmodified_edit_system` PASSED (bare/feedback arms unchanged); `test_factor_p_block_uses_visible_tests_vocabulary` PASSED (glossary term verified).
  - Factor P is a named isolated constant — verified by `test_factor_p_block_present_only_on_prompt_and_both_arms` (tests the constant is present/absent); implementation uses a named constant.
  - V tool surface (feedback/both arms have `run_tests`) — direct smoke shows `tools=('bash','run_tests')` for feedback and both; `test_make_edit_task_offers_run_tests_only_on_v_arms` PASSED.
  - Task-scoped run_uid collision-free — `test_run_uid_is_task_scoped` PASSED; `test_run_uid_collision_free_across_arms_in_one_condition` PASSED.
  - No arm_id / spec change → verify_spec_hash passes — `tests/experiments/test_spec_hash.py` (24 tests) all PASSED; frozen M1 specs still verify.
  - Report groups by task_id — no report-side plumbing added; `pass^k` groups by `task_id` naturally (no change needed, confirmed by no new report code in the diff).
  - max_rounds=40 per arm — direct smoke: all four f1 arms show `max_rounds=40`; `test_each_arm_carries_the_40_round_ablation_override` PASSED.

Test summary:
  - Focused 003 tests: 21 passed, 5 skipped (all skips are environment-gated: `node>=20 + local web-dossier golden store + repo required`), 0 failed.
  - Frozen spec tests: 24 passed, 0 failed.

Failures: none
