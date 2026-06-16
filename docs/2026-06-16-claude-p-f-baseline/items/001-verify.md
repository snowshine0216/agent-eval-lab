Verdict: PASS

Subagent: sonnet
Source: Fallback used: direct CLI entry-point
Entry point exercised:
  - `uv run python -c "from agent_eval_lab.cli import main; import sys; sys.exit(main(['run-f-claude-baseline', '--help']))"` — exit 0
  - `uv run python -c "from agent_eval_lab.cli import main; import sys; sys.exit(main(['run-f-claude-baseline', '--out', '/tmp/claudebl-verify', '--smoke', '--dry-run']))"` — exit 0
  - `uv run python -c "from agent_eval_lab.cli import main; import sys; sys.exit(main(['run-f-claude-baseline', '--out', '/tmp/x', '--bases', 'f9']))"` — exit 2 (argparse error)
  - `uv run pytest tests/runners/test_claude_cli_candidate.py tests/test_cli.py -q -p no:cacheprovider` — exit 0, 75 tests collected and passed

Observed behavior:
  - `parse_claude_result` maps `usage.input/output_tokens` → prompt/completion tokens, carries `num_turns`/`total_cost_usd`/`is_error`, raises `ClaudeResultParseError` on malformed JSON — observed: tests `test_parse_happy_path_maps_usage_and_turns`, `test_parse_is_error_true_is_carried`, `test_parse_malformed_json_raises_typed_error`, `test_parse_missing_usage_raises_typed_error` all green (Task 1 tests green)
  - `claude_system_prompt` differs between surfaces ONLY by "Do not attempt to run tests" line; no Factor-P scaffolding leaks; `build_claude_argv` disables skills (`--disable-slash-commands`), denies Bash on `edit-only`, allows it on `natural`, rejects unknown surfaces — observed: `test_system_prompt_differs_only_by_run_tests_line`, `test_argv_edit_only_denies_bash_and_disables_skills`, `test_argv_natural_allows_bash`, `test_argv_rejects_unknown_surface` all green (Task 2 tests green)
  - `materialize_tree` + `read_back_tree` round-trip a `{relpath: content}` tree, ignore `.git`/`node_modules`, include files Claude created — observed: `test_materialize_then_read_back_round_trips`, `test_read_back_ignores_git_and_node_modules`, `test_read_back_includes_files_claude_created` all green (Task 3 tests green)
  - `make_claude_run_fn` builds a `Trajectory` carrying the produced tree, runs in a temp workdir under a clean `HOME`, records `rounds`/usage, returns env-invalid `Trajectory` (`ParseFailure(error=PROVIDER_ERROR)`) on nonzero exit, timeout, parse error, or `is_error` — observed: `test_run_fn_success_builds_trajectory_with_produced_tree`, `test_run_fn_nonzero_exit_is_env_invalid`, `test_run_fn_timeout_is_env_invalid`, `test_run_fn_is_error_true_is_env_invalid`, `test_run_fn_unparseable_stdout_is_env_invalid` all green (Task 4 tests green)
  - `summarize_baseline` rolls one `ReplacementOutcome` per base into `BaselineRow`s with strict VOID, `pass_hat_k`, and `pass_at_1` — observed: `test_summary_clean_all_pass_is_pass_hat_k`, `test_summary_one_valid_fail_breaks_pass_hat_k`, `test_summary_void_when_an_attempt_is_env_invalid`, `test_summary_pairs_base_ids_to_outcomes_in_order` all green (Task 5 tests green)
  - `run-f-claude-baseline` parses with defaults `surface=both`, `k=5`, `bases=[f1,f2,f3]`, `model=claude-sonnet-4-6`, `smoke=False`; `--dry-run` writes `claude-baseline.plan.json` and makes no subprocess; bad base (`f9`) exits non-zero with argparse error — observed: `test_claude_baseline_parser_defaults`, `test_claude_baseline_dry_run_makes_no_subprocess`, `test_claude_baseline_writes_records_and_void_summary` all green (Task 6 tests green); bad-base rejection verified live: exit 2, message "invalid choice: 'f9' (choose from f1, f2, f3)"
  - Full unit suite + lint pass — observed: 75 tests passed (exit 0); `ruff check` and `ruff format --check` both exit 0 on `claude_cli_candidate.py` and `cli.py`
  - No-quota entry-point smoke exits 0, prints plan path, plan JSON shows `attempts: 1`, `surfaces: ["edit-only"]`, `bases: ["f1"]`, `k: 1` — observed: plan JSON written to `/tmp/claudebl-verify/claude-baseline.plan.json` with exactly those values (also `k: 1`)

Deferred to owner paid smoke (out of scope):
  - Real `claude -p` subprocess invocation (consumes subscription quota, needs NODE_BIN >= 20)
  - Full 30-run baseline across all bases and surfaces
  - Verification that the Node oracle grades real Claude edits correctly
  - Verification that `--smoke` without `--dry-run` fails fast when Node < 20 is the default

Failures: none
