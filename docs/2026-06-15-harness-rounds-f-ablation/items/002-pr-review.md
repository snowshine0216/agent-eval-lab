Verdict: PASS-WITH-NITS

Source: /code-review skill (independent second-pass, in-conversation output only; no PR comment posted)
PR comment URL: none (skill did not post a comment; findings captured below)
Diff reviewed: autodev/harness-rounds-f-ablation-feature...claude/harness-rounds-f-ablation-002
Review model: claude-sonnet-4-6

## Verification of prior latent bugs (F1, F2 — must NOT re-flag as unfixed)

- **F1 CONFIRMED FIXED** — `cli.py:832` passes `safety_cap=cfg.runner.safety_cap` into `run_dset`,
  which threads it to `run_task_k_valid`. Test `test_run_dset_threads_configured_safety_cap_not_default`
  asserts value 300 (not default 200). Verified present.
- **F2 CONFIRMED FIXED** — `loop.py:198-202` includes `"max_rounds"` in the env_unhealthy override
  set alongside `"completed_natural"` and `"safety_cap"`. `max_rounds_bound=True` is set before the
  override fires and is preserved. Test `test_post_probe_unhealthy_with_max_rounds_sets_env_unhealthy_stop_reason`
  asserts both `stop_reason == "env_unhealthy"` and `max_rounds_bound is True`. Verified present.
- **F3 CONFIRMED FIXED** — `classify.py` module docstring (line ~48) now reads "direct attribute
  access on the Trajectory dataclass (a real field as of item 002)". Verified.
- **F4 CONFIRMED FIXED** — `round_budget.py:30-31` raises `ValueError` on `resolved <= 0`. Tests cover
  0, -1, -99. Verified.
- **F-resolver bypass DOCUMENTED** — `cli.py:910-911` has inline comment "F is arm-wide in this
  phase; per-task F overrides arrive in item 003." Verified.

## Findings (2 nits, 0 latent bugs, 0 blockers)

| # | File | Note | Class | Description |
|---|------|------|-------|-------------|
| N1 | `src/agent_eval_lab/runners/multi_run.py` | L90-121 | nit | `run_task_k` (legacy B-domain path) does not accept or thread `max_rounds` — correctly intentional (B is config-only/deferred per ADR-0017 and the resolver comment), but no comment in the function docstring says so. The docstring says `max_steps` is accepted "for CLI compatibility" but is silent about `max_rounds`. Low risk: only one call site in `cli.py` and it's the baseline command. Consider a one-liner: "max_rounds not threaded: B is config-only/deferred (ADR-0017 §9.9)." |
| N2 | `src/agent_eval_lab/records/serialize.py` | `trajectory_from_dict` | nit | `max_rounds` and `safety_cap` are not int-coerced on deserialize (`data.get("max_rounds")` passes through as-is). As documented in the first-pass review (002-review.md "Note"), this is intentional — records are system-produced, hand-corrupted JSONL is out of scope. The note is in the review file but not at the call site. A one-line inline comment at the deserialize call site would prevent future surprise. |

## Intentional patterns verified (do NOT flag as bugs)

- F uses `DOMAIN_MAX_ROUNDS["F"]` directly in `cli.py` (arm-wide; per-task F arms arrive in item 003;
  documented at the call site). Correct.
- `trajectory_from_dict` does not int-coerce `max_rounds` (records are system-produced; documented
  note in 002-review.md). Correct.
- `run_task_k` does not thread `max_rounds` (legacy path; B is config-only/deferred). Correct.

## Summary

All four pre-push latent bugs (F1-F4) and the F-resolver bypass comment are confirmed fixed and
present in the branch. Both findings in this review are documentation nits — no correctness or
CLAUDE.md violations. The feature is correctly implemented across all modified modules with full
test coverage (1021 passed / 17 skipped per PR description).
