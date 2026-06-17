# 001 — /ship pre-landing review findings (pre-PR triage)

Source: `/ship` steps 8+9 — pr-review-toolkit:code-reviewer + silent-failure-hunter + adversarial.
Status: routed through triage-fix BEFORE opening the PR (ship.md → "review can demand fixes before push").

## P0 — must fix before landing (confirmed against source)

- **P0-1 — live `claude` arm silently VOIDs.** `cli.py:_real_b_candidate_factory` (~1674) passes bare
  `subprocess.run` as `run_subprocess`, unlike the F-baseline `_real_claude_factory` (cli.py:1517-1525)
  which wraps it with `capture_output=True, text=True`. Without capture, `completed.stdout` is `None` →
  `parse_claude_result(None)` raises → every live `claude` trial degrades to env-invalid → the whole arm
  VOIDs on a paid run with opaque diagnostics. **Fix:** wrap `subprocess.run` in a closure passing
  `capture_output=True, text=True` (mirror `_real_claude_factory`).

- **P0-2 — missing candidate config burns a paid run.** `cli.py:1718-1719` does `cfg.candidate.url or ""`
  and `cfg.candidate.folder or ""`, silently substituting `""` for missing required config. The empty
  URL/folder flow into `render_b_prompt`, producing a garbage prompt ("Log in … at  as user 'bxu'") that
  runs, looks valid, and wastes money. **Fix:** in `_run_b_command`, fail-fast with a clear config error
  if `candidate.url` or `candidate.folder` is missing/empty (and assert password non-empty), before any
  trial runs. Keep the config loader permissive (folder stays Optional for non-run-b consumers).

## P1 — fix now (cheap + correct)

- **P1-1 — empty-user-message silent render.** `b_candidate_chat._render_task` and
  `b_candidate_claude.run_fn` use `base_user = user.content if user is not None else ""`, silently
  rendering an empty task instruction. **Fix:** raise `ValueError` if the task has no user message.
- **P1-2 — CSV quoting.** `b_scoring.emit_verdict_sheet` joins with `","` and no escaping; a field with a
  comma corrupts the CSV. **Fix:** use the stdlib `csv` module for the CSV output (markdown unchanged).
- **P1-3 — coverage gap.** No `run-b` test for the 401/403 provider-auth fail-fast abort. **Fix:** add a
  test injecting a provider-auth trajectory; assert `rc == 1`, abort on first arm, verdict sheet still emitted.
- **P1-4 — duplicate run_uid double-counts.** `report-b` over concatenated JSONL with repeated run_uids
  inflates `valid`/`pass_at_1`. `report_b` is pure (cannot warn). **Fix:** dedupe by run_uid in the
  `_run_report_b` CLI edge (keep last) with a stderr warning; add a test. Keep `report_b` pure.

## Documented (not a code fix this spike)

- **P1-5 — claude budget-cap not censored.** A `--max-budget-usd` exhaustion exits 0 with
  `is_error=False`, recorded as `completed_natural`. `ClaudeRunMeta` exposes no budget/stop signal, and the
  F-baseline driver (claude_cli_candidate.py:282) behaves identically — this is a pre-existing limitation of
  the shared claude building blocks, not introduced here. **Action:** add a one-line known-limitation note
  to the B-1 runbook (calibrate-first already mitigates premature caps).
- **P1-6 — stale docstring.** `b_isolation.save_name_from_run_uid` docstring shows the old 2-part run_uid;
  the feature now uses a 3-part `condition_id__task_id__run_index`. Pre-existing file; **Fix:** 1-line
  docstring correction for accuracy.
