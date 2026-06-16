Verdict: PASS-WITH-NITS
Source: /ship steps 8+9 (pr-review-toolkit:code-reviewer + silent-failure-hunter + adversarial)

## Findings and resolution
0 P0/blockers. 2 P1 cleanups fixed pre-push; 2 accepted as intended design.

### Fixed pre-push (commit on this branch)
- **Dead defensive None-guard** `f_candidate.py:140` — `(task.initial_state or {}).get(...)` → direct
  `task.initial_state.get(...)`. `prefix_candidate_tree` (line 139) already asserts `initial_state is
  not None` before the loop, so the `or {}` was dead for the None case; direct access makes a future
  None a **loud** AttributeError instead of a silent un-enriched arm (house style — 002 CF2). Both
  reviewers (silent-failure + code-reviewer) flagged the silent-skip class.
- **Dead no-op test line** `test_f_candidate.py:236` — `monkeypatch.setattr(fr, "subprocess",
  fr.subprocess)` (assigned to itself). Removed.

### Accepted — intended design (no code change)
- **F2 `index.js` exposes `{signal, confidence}` field names** (adversarial: RISKS). This is the
  **intended enrichment** (§C: "analyzeFailure's source so its return shape is readable from
  source"; §11.6 includes the source, excludes the tests that *assert* the split). All four arms get
  byte-identical context, so it shifts the floor equally and does **not** confound the P-vs-no-P
  comparison. The *discriminating* behavior (surfacing both fields in the printed `wdio.conf.ts`
  summary) stays held-out; reading the return shape ≠ knowing to surface both. The design already
  flags F-hypotheses as retrospective with confirmation deferred to held-out F4–F6 (§F). Adversarial
  verdict was RISKS (signal-ceiling sensitivity), not BREAKS — an experimental-design observation,
  not a code/correctness bug.
- **§10.4 invariant test is `@requires_repo`-gated → skipped in CI** (silent-failure note). Inherent:
  the invariant materializes the REAL F trees, which needs the local web-dossier repo — consistent
  with the F-domain's macOS-local design (spec §B.4 platform gate). The disjointness *logic* IS
  enforced in CI by the non-gated unit test `test_seeded_held_out_disjoint_false_on_canonical_prefix_collision`
  (genuine canonical-case collision). The invariant-over-real-tasks test runs locally (passed:
  all 15 tasks disjoint).

## Verification after fixes
- `pytest tests/runners/test_f_candidate.py tests/runners/test_f_overlay_disjoint.py -k "context or disjoint or missing" -o addopts="" -q` → 10 passed
- `ruff check .` → All checks passed! · `ruff format --check .` → 202 files already formatted
