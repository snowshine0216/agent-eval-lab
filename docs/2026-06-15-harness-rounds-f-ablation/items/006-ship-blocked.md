# 006 — /ship steps 8+9 review: hardening before push

Source: /ship steps 8 (code-reviewer + silent-failure-hunter) + 9 (adversarial). **The hard boundary
holds**: no accidental paid execution (3 reviewers + CLEAN adversarial — `_default_run_fn_factory` is
the sole network path, unreachable on dry-run/injected-factory/import); `ablation_run_order`
deterministic (240 units, no dup, interleaved); freeze integrity OK (M1 `verify_spec_hash` green, 24
tests). Two real fixes + one honesty fix before push.

## Must-fix (latent defect — the driver's purpose is a 240-attempt PAID run)

### B1 — driver loses ALL results on a mid-run exception (silent-failure 3×P0; adversarial noted)
`cli.py` `_run_f_ablation_command` buffers every attempt in memory and writes the per-condition JSONL +
realized-order sidecar **only after** the full 240-unit loop. A mid-loop raise — `KeyError` on a
task_id skew (`arm_tasks[unit.task_id]`), any `run_fn` exception, or an uncaught `httpx.TransportError`
(which `_run_f_command` DOES catch, line ~945) — discards every banked (paid) result, writes nothing,
and returns a raw traceback with no exit code. **Fix (match `_run_f_command`'s streaming pattern):**
- Validate `set(arm_tasks) == {u.task_id for u in order}` BEFORE the loop (catch task_id skew before any
  paid call); exit 1 with a diagnostic if it fails.
- Open per-condition JSONL handles before the loop; `_append_runs` per attempt (stream, don't buffer).
- Wrap the loop body in try/except for `httpx.TransportError` (+ the subprocess/git errors
  `_run_f_command` catches); on error set aborted, break.
- In a `finally`, flush/close handles AND write the realized-order sidecar (so a partial run still
  leaves a sidecar + the completed JSONL rows).

### B2 — realized-order sidecar write is not atomic (silent-failure P1)
`_write_realized_order` uses `write_text`; a crash mid-write leaves a truncated "authoritative
drift-control record" that may parse with <240 entries. **Fix:** use the existing `_atomic_write`.

## Should-fix (audit honesty)

### B3 — `correction="holm"` on a descriptive/no-Holm spec (code-reviewer P0.2; silent-failure Note)
`f_ablation_spec.build_f_ablation_spec` sets `MultiplicityFamily.correction="holm"` while
`planned_comparisons=()` and the design declares descriptive / **no Holm** (§D.2). Holm on zero
comparisons is vacuous (not a runtime bug — adversarial agreed), but the spec hash would lock in a
misleading value. **Fix:** make it honest — widen the schema `Literal["holm"]` → `Literal["holm",
"none"]` and set `correction="none"` for the ablation family (M1 keeps `"holm"`; canonical_json
serializes the VALUE so M1's frozen hash is UNCHANGED — verify). If the ExperimentSpec does not require
a family, dropping the family is also acceptable. Either way the descriptive spec must not claim Holm.

## Documented / accepted (no code change)
- **Dispatch via `main()` doesn't pass `run_fn_factory`** (both reviewers P1): this is CORRECT — the
  production path uses the real factory; tests inject by calling `_run_f_ablation_command` directly or
  monkeypatching. No current path makes an unintended call (adversarial CLEAN). Test-authoring
  discipline, not a code bug. Accept.
- **`Path("/nonexistent")` sentinel store on the injected-factory branch** (both reviewers P1): the
  injected-factory branch is test-only; production uses the default factory + real config. A real
  injected-factory call is not a production path. Accept (the streaming fix's upfront coverage check
  also makes a skew loud).
- **Hardcoded `f_repo` path** (code-reviewer P1): pre-existing pattern shared with `_run_f_command`;
  not new tech debt for 006 to refactor. Accept.
