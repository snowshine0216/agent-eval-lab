# Item 007 — Verify (M1/M2 aggregation + report layer)

**VERDICT: PASS** · 2026-06-13 · branch `feat/agentic-v1-007-m1-m2-reports`

## 1. Suite + reference values ✅
- `uv run pytest`: **874 passed, 8 skipped** (node-gated D-set tests skip; this item is node-independent).
- Binomial/Clopper–Pearson + Fisher + Holm + Pareto reference-value tests green (match the plan's
  scipy-verified values: 2/3→[0.0943,0.9916], 3/3 lower 0.2924, 0/3 upper 0.7076; Fisher 2/3-vs-2/3→1.0; Holm→[0.04,0.04]).

## 2. M1 spec builds + freezes ✅
`build_m1_spec(dataset_snapshot_hash=…, pricing_snapshot_hash=…)` → 6 conditions
(deepseek-v4-pro, glm GLM-5.1, minimax MiniMax-M3, local qwen3-8b, + 2 SiliconFlow Qwen ladder [provisional]),
15 metrics, 15 planned comparisons, 1 Holm family, k=5, repeats=1, max_invalid_rate=0.40, equal weights F=D=B=1.0.
Draft has empty spec_hash (correct); `freeze_spec` → spec_hash set + `verify_spec_hash` True.

## 3. Partial D-only report renders correctly ✅ (the report-engine smoke)
Fed synthetic D-domain ReplacementOutcomes for 2 conditions (deepseek all-pass, minimax fails q01) →
`build_m1_report` → `render_markdown` produced:
- **Per-domain table:** deepseek D pass^k 1.000 [1.000,1.000]; minimax 0.667 [0.000,1.000] (cluster_bootstrap); valid/invalid counts. F & B → "not yet run" (NOT failures).
- **Macro composite:** weighted by DOMAIN (D23), `weighted_halfwidth_propagation` CI, "reduced coverage" flag (F/B absent).
- **Pareto:** pass^k vs cost_usd / rounds / tokens; deepseek on the cost frontier (1.000 @ $0.0209), minimax cheaper ($0.012); on-frontier marking correct.
- **Holm comparisons:** skipped arms rendered "(skipped — arm not run)", not fabricated.
- Header carries spec_hash + dataset/pricing snapshot hashes + seed + n_resamples + alpha + fc-v3 provenance.

## 4. Determinism ✅
Task-14 byte-identity gate in the suite pins identical report output for the same runs+spec+seed (seeded bootstrap, RNG passed as argument).

## Correctness invariants confirmed in render
F=binomial (never cluster bootstrap, D38); validity mask + void/INCOMPLETE explicit (valid/invalid columns);
weights from the frozen spec only (no post-hoc); composite never a raw task pool. The actual multi-model RUN
is a separate downstream step (`eval-lab run-m1`); `run_m1` is stub-tested here.
