Verdict: PASS-WITH-NITS

Source: /ship steps 8+9
PR: https://github.com/snowshine0216/agent-eval-lab/pull/8

## Findings and resolutions

- Arithmetic audit (adversarial recount from raw runs JSONL): every
  committed number EXACT — C3 0.980/0.940, C4 0.620/0.620, C4-T3 7/22 =
  0.318, Config B 49/50 with ws2-014 (T2) the sole planning failure,
  primary T3+T4 Δ CI [0,0] valid (zero hard-tier failures both configs).

- BLOCKER (fixed pre-push): `_parse_runs_spec` split "=" left-to-right —
  condition ids containing "=" silently loaded a wrong path and rendered
  blocked. rsplit fix + pinned test.
- BLOCKER (fixed pre-push): malformed/truncated runs JSONL raised a bare
  traceback with no file/line context (still fails loud — now structured).
- P1 (fixed): tasks with <k runs vacuously passed `all()` — report layer
  now excludes them, names them, and forces condition status incomplete.
- P1 (fixed, verdict-honesty): the "strong" discriminativeness rung was
  satisfied by flat-at-ceiling monotone gradients. Gradient rung now
  requires a strict decrease; verdict names its evidence and near-misses.
  Regenerated verdict: weak met (C4 local decisively separated), strong NOT
  met (C1vsC3 Δ −0.060, CI [−0.140, 0.000] touches 0 at n=50). The
  degenerate identical pair renders "No observed difference", not
  "near-miss".
- P1 (fixed): capability lookup `"?"` fallback → raises like tier_of;
  `_task_reliability` de-duplicated; compare-configs CLI diagnostics
  (universe mismatch, missing files, empty hard subset) now clean one-line
  errors; skipped pairs noted in the report.

- NIT (documented): prompt-tag slug collision convention in ADR-0007.
- NIT (by design): missing --runs path renders the condition blocked (the
  plan's sanctioned mechanism for showing openrouter-style blocks).
