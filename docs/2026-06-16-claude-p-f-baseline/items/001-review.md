Verdict: PASS-WITH-NITS

Source: /ship steps 8+9 (pre-landing parallel review + adversarial review)
Reviewers: pr-review-toolkit:code-reviewer, pr-review-toolkit:silent-failure-hunter, adversarial (general-purpose, sonnet)

## Blockers / latent bugs — all FIXED before push (commits 80bf605, 9b7d571)

- **[P0 crash] `--evaluator-config default=None`** → `load_evaluator_config(None)` `AttributeError` on the documented smoke invocation. Fixed: defaults to `Path("evaluator.toml")`; `--dry-run` still works without it. (cli.py:1761; test `test_claude_baseline_parser_defaults`.)
- **[Validity — invalidates the baseline] env contamination** — only `HOME` was overridden; `CLAUDE_CONFIG_DIR`/`XDG_CONFIG_HOME`/effort/entrypoint/plugin vars leaked from the parent session into the nested `claude -p`, so the "vanilla Sonnet-4.6/no-skills" label could be silently false (xhigh effort, owner plugins). Fixed: `_sanitized_env` surgical denylist strips them; auth (`ANTHROPIC_*`/`*TOKEN*`/`*KEY*`), PATH, HOME preserved. (claude_cli_candidate.py:151-168; test `test_sanitized_env_strips_contaminating_keys_and_sets_clean_home`.)
- **[Robustness — crashes the whole paid run] `read_back_tree` unguarded** — a non-UTF-8 artifact (likelier on `natural`/Bash) raised `UnicodeDecodeError` outside `run_f_candidate`'s env-invalid net, aborting mid-run and losing prior results. Fixed: read-back wrapped → env-invalid (no fair trial), never `errors="replace"` (would corrupt grading input). (test `test_run_fn_unreadable_produced_tree_is_env_invalid`.)

## Polish — FIXED (same fix pass)

- nonzero-exit env-invalid `raw` now carries `stderr` (claude writes its real error there) — debuggable voids. (test `test_run_fn_nonzero_exit_carries_stderr_in_raw`.)
- `--bases choices=["f1","f2","f3"]` — clean argparse error vs a bare KeyError. (test `test_claude_baseline_bases_rejects_unknown_value`.)
- missing `web-dossier` repo fails fast with a clear message on real runs. (test `test_claude_baseline_missing_f_repo_fails_fast`.)
- closed run_fn coverage gaps: `is_error` and unparseable-stdout → env-invalid now tested.

## NITS — documented, deferred to owner (not blockers)

- **`is_error` → env-invalid may mask budget-exhausted model misses** — spec-compliant ("subprocess failures become env-invalid"), but `--max-budget-usd 0.50` aborts also set `is_error`, so a budget-capped attempt is masked out of pass^k instead of graded as a FAIL → can inflate pass^k. Methodology decision, NOT changed autonomously; recorded in the plan's "Known limitation" section and to be surfaced (budget-stop rate) at the smoke pause for the owner to decide.
- `--smoke` silently overrides `--surface`/`--bases`/`--k` — by design (smoke = 1×F1×edit-only). Documented behavior.

## Verified clean by reviewers

- No shell-injection surface (`subprocess.run(list)`, no shell; prompt/system_prompt discrete tokens).
- `summarize_baseline` VOID/pass^k/pass@1 math correct (`zip(strict=True)`, n_valid=0 division guarded, k=0 → void).
- tree round-trip: deletion reflected; empty content round-trips; `.git`/`node_modules` filtered by exact top-level part (no substring false-positives).
- Node fail-fast reached before any subprocess; bypassed only when `run_fn_factory` is injected (tests).

Post-fix: full suite green (`uv run pytest -q` exit 0), `ruff check` + `ruff format --check` clean.
