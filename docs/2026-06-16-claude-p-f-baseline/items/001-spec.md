# 001-spec (inferred from plan)

Goal: Run vanilla Claude Code (`claude -p`, Sonnet 4.6, no skills) as the F-task
agent over two tool surfaces (`edit-only`, `natural`), graded by the held-out
Node oracle, via a new `runners/claude_cli_candidate.py` + `run-f-claude-baseline`
CLI subcommand that reuses `run_f_candidate`'s strict-VOID k-loop — a Claude Code
baseline distinct from the v2 model ablation.

Acceptance criteria:
  - `parse_claude_result` maps `usage.input/output_tokens` → prompt/completion tokens, carries `num_turns`/`total_cost_usd`/`is_error`, and raises a typed `ClaudeResultParseError` on malformed or incomplete JSON (Task 1 tests green).
  - `claude_system_prompt` differs between surfaces ONLY by the "Do not attempt to run tests" line; no Factor-P scaffolding leaks into either; `build_claude_argv` disables skills (`--disable-slash-commands`), denies Bash on `edit-only`, allows it on `natural`, and rejects unknown surfaces (Task 2 tests green).
  - `materialize_tree` + `read_back_tree` round-trip a `{relpath: content}` tree, ignore `.git`/`node_modules`, and include files Claude created (Task 3 tests green).
  - `make_claude_run_fn` builds a `Trajectory` carrying the produced tree, runs in a temp workdir under a clean `HOME`, records `rounds`/usage, and returns an env-invalid `Trajectory` (`ParseFailure(error=PROVIDER_ERROR)`) on nonzero exit, timeout, parse error, or `is_error` (Task 4 tests green).
  - `summarize_baseline` rolls one `ReplacementOutcome` per base into `BaselineRow`s with strict VOID (`void` iff `< k` clean attempts), `pass_hat_k` (not void AND all clean attempts pass), and `pass_at_1` (Task 5 tests green).
  - `run-f-claude-baseline` parses with defaults `surface=both`, `k=5`, `bases=[f1,f2,f3]`, `model=claude-sonnet-4-6`, `smoke=False`; `--dry-run` writes `claude-baseline.plan.json` and makes no subprocess; a real run drives `run_f_candidate` per surface, writes per-attempt JSONL (valid + invalid) + `claude-baseline-summary.json`, and fail-fasts when the resolved Node cannot run the oracle (Task 6 tests green).
  - Full unit suite + lint pass: `pytest -q && ruff check . && ruff format --check .`.
  - The no-quota entry-point smoke `run-f-claude-baseline --out <dir> --smoke --dry-run` exits 0, prints the plan path, and the plan JSON shows `attempts: 1`, `surfaces: ["edit-only"]` (Task 7 step 1).

Constraints: Lands on feature branch `feat/claude-p-f-baseline` only — never `main`
(no opt-in given). The paid Task 7 smoke (real `claude -p`, ~1 quota unit, needs
`NODE_BIN` ≥20) and the full 30-run are the plan's deliberate PAUSE — OUT of the
autonomous run, deferred to the owner (see SKIPPED.md). Verify gate uses the
no-quota dry-run as the entry-point smoke.
