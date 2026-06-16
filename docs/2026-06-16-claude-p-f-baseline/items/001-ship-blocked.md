# 001 — /ship pre-push review findings (steps 8+9)

Source: pr-review-toolkit:code-reviewer + silent-failure-hunter + adversarial (general-purpose).
Status: routed to a fix subagent before push (per ship.md "review can demand fixes before push").

## Blockers / high-value — FIXED before push

1. **[P0 crash] `--evaluator-config default=None`** (`cli.py:1761`) → `load_evaluator_config(None)` does `None.open()` → `AttributeError` on the documented invocation (`run-f-claude-baseline --out X --smoke`). Every sibling subcommand uses a real config. Fix: default to `Path("evaluator.toml")` (the repo-root canonical config the agentic runs already use). NOT `required=True` — the `--dry-run` path (the verify entry-point smoke) must work without a config.
2. **[Validity] Env contamination defeats the "vanilla" claim** (`claude_cli_candidate.py:205`). `env = {**os.environ, "HOME": clean_home}` overrides only HOME; `CLAUDE_CONFIG_DIR`, `XDG_CONFIG_HOME`, `CLAUDE_CODE_EFFORT_LEVEL`/`CLAUDE_EFFORT`, `CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` leak from the parent session → the nested `claude -p` may run at xhigh effort with the owner's plugins/config, silently invalidating the baseline label. Fix: surgical denylist of those keys (never touch PATH/HOME/auth/ANTHROPIC_*/*TOKEN*/*KEY*).
3. **[Robustness] `read_back_tree` crash aborts the whole paid run** (`claude_cli_candidate.py:222`, read at `:143`). `path.read_text()` on a non-UTF-8 file Claude produced (likelier on `natural`/Bash) raises `UnicodeDecodeError` OUTSIDE any try/except, escaping `run_fn` — not caught by `run_f_candidate`, crashing mid-run and losing prior surfaces' results. Fix: wrap the read-back → env-invalid (an unreadable tree is no fair trial), don't silently `errors="replace"` (would corrupt grading input).
4. **[Debuggability/polish]** include `completed.stderr` in the nonzero-exit env-invalid `raw` (claude writes its real error there); `--bases choices=["f1","f2","f3"]` (reject bad input cleanly vs bare KeyError); `f_repo` existence fail-fast with a clean message (same pattern as the Node guard). Close test gaps: `is_error=True`→env-invalid, parse-error→env-invalid, env-sanitization, read-back-failure→env-invalid.

## Documented, NOT changed (methodology — owner's call at the smoke pause)

- **`is_error` → env-invalid may mask budget-exhausted model misses.** The runner sets `--max-budget-usd 0.5`; a budget-capped attempt that left a partial/wrong tree returns `is_error:true` and is masked out of pass^k instead of graded as a FAIL — inflating pass^k. This is **spec-compliant** ("subprocess failures become env-invalid") but is a methodology choice that changes what pass^k means. Surfaced to the owner at the smoke pause; not re-decided autonomously. Add to the plan's "Known limitation" list.
- **`--smoke` silently overrides `--surface`/`--bases`/`--k`** (by design: smoke = 1×F1×edit-only). Documented behavior; no change.

## Clean (verified by reviewers)

- argv has no shell-injection surface (`subprocess.run(list)`, no shell; prompt/system_prompt are discrete tokens).
- `summarize_baseline` VOID/pass^k/pass@1 math correct (`zip(strict=True)`, n_valid=0 division guarded, k=0 → void).
- tree round-trip: deletion reflected, empty content round-trips, `.git`/`node_modules` filtered by exact top-level part only (no substring false-positives).
- Node fail-fast reached before any subprocess; correctly bypassed only when `run_fn_factory` is injected (tests).
