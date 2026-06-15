Verdict: PASS-WITH-NITS
Source: /code-review skill (independent second-pass); no GitHub comment posted (source control connector not active in this session — review conducted directly from full PR diff via `gh pr diff 31`)

## Findings

| File:Location | Classification | Description |
|---------------|----------------|-------------|
| `cli.py:1530` | nit | `--evaluator-config` is `required=True` even when `--dry-run` is passed; the flag is never read on the dry path. User must supply a dummy path (e.g., `evaluator.toml`). The dry-run test workarounds this. Acceptable given dry-run is a preview/audit invocation. |
| `cli.py:1265` | nit | `run_fn_factory=None` has no type annotation (`Callable | None`). No runtime impact; mild readability gap at the injection seam. |
| `tests/cli/test_run_f_ablation.py:50–52` | nit | `test_dry_run_writes_order_and_makes_zero_run_fn_calls` monkeypatches `_ablation_arm_tasks` even though the dry-run path returns before that function is ever called (line 1287–1291). Harmless but redundant. |

## Critical path confirmations

**No accidental paid execution (CLEAN):**
- `_default_run_fn_factory` is the sole network path; reached only when `run_fn_factory is None` AND `args.dry_run` is False (a real user invocation).
- All 8 driver tests inject a fake factory via `run_fn_factory=_make_recording_factory(calls)` or spy via monkeypatch — no test ever calls `_default_run_fn_factory` or constructs any `httpx.Client`.
- `test_dry_run_writes_order_and_makes_zero_run_fn_calls` asserts `calls == []` — zero provider calls on dry path.
- Importing `cli.py`, `ablation_order.py`, or `f_ablation_spec.py` does NOT trigger any network call.

**No non-determinism found:**
- `ablation_run_order` uses `random.Random(seed)` — a local, seeded RNG; no `random` module-level state, no wall-clock.
- `test_same_seed_is_identical` and `test_no_wall_clock_dependence_two_calls_equal` assert reproducibility.

**Frozen M1 spec integrity confirmed:**
- No field added to `ConditionDef`, `ExperimentSpec`, or any shared schema dataclass.
- `MultiplicityFamily.correction` widened from `Literal["holm"]` to `Literal["holm", "none"]` — additive only; M1 keeps `"holm"`, canonical_json serializes the VALUE so M1's frozen hash is unchanged.
- `test_building_the_ablation_spec_does_not_touch_m1` explicitly verifies `verify_spec_hash(m1)` still passes after building/freezing the ablation spec.
- `AblationPolicy` is a new standalone dataclass; not an `ExperimentSpec` field.

**Pre-push fixes (2728c95) verified present:**
- B1 (crash-safety): streaming driver with upfront task_id-coverage check, per-condition handles opened before loop, `except httpx.TransportError` + subprocess errors → `aborted=True`, `finally` closes handles + writes sidecar. Tests `test_transport_error_mid_run_aborts_cleanly_and_preserves_partial_results` and `test_task_id_skew_is_caught_before_any_run_fn_call` both present and correct.
- B2 (atomic sidecar): `_write_realized_order` uses `_atomic_write` — confirmed in diff.
- B3 (honest correction): `correction="none"` confirmed in `f_ablation_spec.py:131` (not "holm").

## Verdict summary

All 3 findings are nits. Zero blockers. Zero latent bugs. No accidental paid execution, no non-determinism, no frozen-spec break. The critical boundary properties hold and are mechanically verified by tests.
