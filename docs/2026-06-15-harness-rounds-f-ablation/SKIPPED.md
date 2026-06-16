# SKIPPED — out-of-scope for this run

These are **deferred**, not abandoned. The user scoped this run to *infra only — Part G steps 1–6
code* (2026-06-15). The infra built here (item 006: `run-f-ablation` driver + frozen
`f_ablation_spec`) is exactly what unblocks the first two.

## Step 6 (execution) — pilot + full 240-attempt paid run
**Blocker:** real, irreversible API spend across 4 frontier models (deepseek-v4-pro, GLM-5.1,
MiniMax-M3, Qwen3.6-35B) — 4 arms × 4 models × 3 tasks × k=5 = **240 attempts**, plus a ~24-attempt
pilot. Also requires the macOS-local Factor-V seatbelt sandbox (not available on CI).
**Unblock path:** after item 006 merges, the user runs `run-f-ablation` against the frozen
`f_ablation_spec` — pilot (1 model × 4 arms × 3 tasks × k=2) first, then the full 240. The driver
writes one `runs-ablation-{slug}-F.jsonl` per condition + the realized-order sidecar.

## Step 7 — descriptive report + queue F4–F6
**Blocker:** depends on the run records from step 6. The report is the Part C narrative +
§D.2 per-arm `pass^k` (4×3, never a 12-task pool) + §D.3 resource/time split + §D.4 harness signals
(`product_edit_count`, `authored_test_edit_count`, `out_of_scope_edit_rate`, `run_tests` adoption).
**Unblock path:** run after step 6 produces records; then queue the F4–F6 held-out follow-up (Part F).

## Part F — held-out F4–F6 confirmation
**Blocker:** by design a **separate follow-up phase** (§F) — author untouched F4–F6 web-dossier
tasks, pre-register the factors, run the ablation there. Explicitly out of scope for this design
beyond recording the queue item.
**Unblock path:** its own future spec/run once the retrospective ablation (steps 6–7) has results.
