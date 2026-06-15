Verdict: PASS-WITH-NITS
Source: /ship steps 8+9 (code-reviewer + silent-failure-hunter + adversarial); findings fixed pre-push (commit 2728c95)

## Verdict summary
**The hard boundary holds** — no accidental paid execution: all 3 reviewers + the CLEAN adversarial
verdict confirm `_default_run_fn_factory` is the sole network path, unreachable on `--dry-run`,
injected-factory, or import. `ablation_run_order` is deterministic (240 units, no dup, arms interleaved
within each block); freeze integrity OK (M1 `verify_spec_hash` green, AblationPolicy separate hash). One
real latent defect + atomicity + a spec-honesty issue fixed pre-push. Triage: items/006-ship-blocked.md.

### Fixed pre-push (commit 2728c95)
- **B1 (latent defect)** — the driver buffered all 240 attempts and wrote per-condition JSONL + the
  sidecar only AFTER the full loop, so a mid-run exception (task_id skew, `run_fn` raise, uncaught
  `TransportError`) lost **all** paid results with a raw traceback. Since the driver's purpose is a
  240-attempt PAID run, that's real money lost. Reworked to STREAM like `_run_f_command`: upfront
  task_id-coverage check (catches skew before any call), per-condition handles opened before the loop +
  `_append_runs` per attempt, `except TransportError`/git-error → aborts cleanly, `finally` closes
  handles + writes the sidecar. New tests: mid-run `TransportError` aborts with partial rows + sidecar
  preserved (rc≠0); task_id skew caught before any `run_fn` call (calls==[], rc=1).
- **B2** — `_write_realized_order` now uses `_atomic_write` (no truncated "authoritative drift-control
  record" on a crash).
- **B3 (honesty)** — the descriptive ablation spec set `correction="holm"` with empty comparisons (§D.2
  says no Holm). Widened the schema `Literal["holm"]` → `Literal["holm","none"]` and set
  `correction="none"` for the ablation family. **M1's frozen hash UNCHANGED** (canonical_json serializes
  the value "holm" for M1; 24 spec tests green).

### Documented / accepted (no code change)
- Dispatch via `main()` doesn't pass `run_fn_factory` (both reviewers P1): correct by design — production
  uses the real factory; tests inject via direct call/monkeypatch; no current path makes an unintended
  call (adversarial CLEAN). The upfront skew check + crash-safety further bound a real run.
- `Path("/nonexistent")` sentinel on the injected-factory branch (test-only path) and the hardcoded
  `f_repo` (pre-existing pattern shared with `_run_f_command`) — accepted.

## Verification after fixes
- `pytest -o addopts="" -q` → 1095 passed / 18 skipped / 0 failed.
- M1 + ablation + driver: 44 passed (M1 hash unchanged; B1 crash-safety tests green).
- `--dry-run` makes ZERO run_fn calls. `ruff check .` + `ruff format --check .` clean.
