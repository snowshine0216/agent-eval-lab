Verdict: PASS-WITH-NITS

> Initial verdict was **FAIL** (latent bugs F1, F2). Fixed pre-push in fix round 1 (ship.md
> "review demands fixes before push" path) and confirmed by an independent focused re-review:
> **BOTH FIXED** — see "## Resolution" at the bottom. Remaining items are documented nits/notes.

Source: /ship steps 8+9 (pre-landing parallel review + adversarial review)
Subagents: pr-review-toolkit:code-reviewer, pr-review-toolkit:silent-failure-hunter, general-purpose (adversarial, sonnet)
Diff reviewed: autodev/harness-rounds-f-ablation-feature...HEAD (item 002)

## Blockers (P0)
- None. Off-by-one in the bound is correct (checked at end-of-iteration, turn's work kept; tested at
  `rounds==3` exactly at cap + natural-completion-breaks-first). spec_hash unmoved. CF1 round-trip and
  CF2 direct-access verified clean.

## Latent bugs (route to fix — FAIL)
- **F1 (P1, confirmed by all 3 reviewers):** `runners/dset_run.py` calls `run_task_k_valid(...)` with
  `max_rounds=resolve_max_rounds("D")` but **does not pass `safety_cap`**, so D-run artifacts inherit
  the `run_task_k_valid` default `safety_cap=200` and **record 200 regardless of `cfg.runner.safety_cap`**
  (spec says browser backstop is ~300; F-path threads `cfg.runner.safety_cap` at cli.py:906). The
  recorded `safety_cap` field — added by THIS item so "an artifact proves its policy" (§9.2) — can lie
  for D runs. **Fix:** thread the configured `safety_cap` into the dset_run `run_task_k_valid` call.
- **F2 (P1, adversarial):** the loop's `env_unhealthy` post-probe override fires for
  `completed_natural` / `safety_cap` stop reasons but **excludes `"max_rounds"`**. A run that hits the
  round cap on a crashed env records `stop_reason="max_rounds"` instead of `env_unhealthy`, so the
  environment-validity mask silently misses it. **Fix:** include `"max_rounds"` in the env_unhealthy
  override condition alongside `safety_cap`.

## Nits (fold into the fix round if cheap)
- **F3:** `reports/classify.py` module docstring (~line 48) still says `max_rounds_bound` is "read
  defensively" — CF2 made it direct access. Update the prose.
- **F4 (P2):** `resolve_max_rounds` / the loop accept `max_rounds <= 0` without a guard; `max_rounds=0`
  or negative fires one API call before stopping. 0/negative are never real config values, but a
  one-line guard (reject non-positive) hardens it.
- **F-resolver bypass (P1, intentional):** the F path wires `DOMAIN_MAX_ROUNDS["F"]` directly rather
  than `resolve_max_rounds(domain="F", task=...)`, so a per-task `metadata.max_rounds` override on an F
  task is ignored. This is intentional for item 002 (F is arm-wide; per-task F arms arrive in item 003)
  — add a one-line comment at the call site documenting why F is exempt. Not a behavior fix.

## Note (not fixing)
- Adversarial flagged a P0-if-triggered: `trajectory_from_dict` does not coerce `max_rounds` to int, so
  a hand-corrupted JSONL with `"max_rounds": "20"` would crash the loop at `>=`. Practically protected
  (records are system-produced; task YAML parsing coerces). Left as a documented note; not fixing.

## Resolution (fix round 1, pre-push — confirmed by focused re-review)
- **F1 FIXED** — `cli.py:832` threads `safety_cap=cfg.runner.safety_cap` → `run_dset` → `run_task_k_valid` (dset_run.py:123). Exactly one D-run call site; no bypass. Test `test_run_dset_threads_configured_safety_cap_not_default` (asserts 300, not default 200).
- **F2 FIXED** — `loop.py:201` includes `"max_rounds"` in the env_unhealthy override set; `max_rounds_bound=True` set before the override fires (preserved); classifier handles `env_unhealthy + max_rounds_bound=True` correctly. Test `test_post_probe_unhealthy_with_max_rounds_sets_env_unhealthy_stop_reason`.
- **F3 FIXED** — classify.py module docstring now says "direct attribute access".
- **F4 FIXED** — `resolve_max_rounds` raises ValueError on non-positive (tests for 0/-1/-99); `None` still = unbounded.
- **F-resolver bypass** — documented with a one-line comment at the F call site (intentional; F per-task arms arrive in item 003).
- Fix commits: 17d899e, 505752c, f90e370, 4143300, 88f9846. Full suite after fix: **1021 passed, 17 skipped, 0 failed**; `verify_spec_hash` green.
