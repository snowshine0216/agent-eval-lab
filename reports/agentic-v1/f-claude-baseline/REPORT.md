# Claude Code F-baseline — results (2026-06-16)

Vanilla Claude Code (`claude -p`, **claude-sonnet-4-6**, no skills/CLAUDE.md/plugins/hooks via `--safe-mode`) as the agent on the F1/F2/F3 web-dossier repair tasks, two tool surfaces, graded by the held-out Node oracle. A **Claude Code baseline, distinct** from the v2 model ablation (deepseek/minimax/qwen).

- Config: `--surface both --k 5 --bases f1 f2 f3` = **2 × 3 × 5 = 30 attempts**.
- Auth/billing: session OAuth/subscription (quota, not per-token \$).
- Oracle: held-out Node test (Node v22.22.2); grades purely off the produced tree.
- **Run health: 30/30 valid, 0 env-invalid, 0 VOID.** Every attempt was a fair, graded trial.

## Results

| surface | base | pass^k (5/5) | pass@1 | passed | mean rounds | mean completion tok |
|---------|------|:------------:|:------:|:------:|:-----------:|:-------------------:|
| edit-only | f1 | ✗ | 0.00 | 0/5 | 6.8 | 2265 |
| edit-only | f2 | ✗ | 0.00 | 0/5 | 6.4 | 5491 |
| edit-only | **f3** | **✓** | **1.00** | **5/5** | 4.2 | 1872 |
| natural | f1 | ✗ | 0.00 | 0/5 | 7.4 | 2649 |
| natural | f2 | ✗ | 0.00 | 0/5 | 7.0 | 5084 |
| natural | **f3** | ✗ | **0.80** | **4/5** | 3.0 | 1658 |

Totals: ~96.4k tokens across 30 attempts (≈95k completion). pass^k = all k clean attempts pass.

## Observations

- **F3 is the only solvable task for this baseline.** edit-only nails it 5/5 (pass^k); natural gets 4/5 (one miss → no pass^k). F3 also needs the fewest rounds (3–4), i.e. it's the easy one.
- **F1 and F2 are unsolved (0/5 on both surfaces).** The model *did* work — 6–7 rounds, multi-file edits — but never satisfied the held-out oracle. F2 is the most expensive (≈5k completion tok/attempt, ~2–3× F1/F3) and still 0/5: high effort, no pass.
- **`natural` (with Bash) did NOT beat `edit-only`.** On the only solvable task (F3) it was *worse* (4/5 vs 5/5). The extra Bash surface bought nothing here — consistent with the plan's caveat that the temp tree has no installed wdio/node_modules, so in-tree test running has limited practical value (D19: the held-out golden is never seeded).
- **No truncation / no env-invalid.** Unlike the early MLX defect history, every attempt ran to `completed_natural` and was graded.

## Comparison context (not apples-to-apples)

The v2 model ablation (PR #37, deepseek/minimax/qwen, 2×2 arms) saw `pass^k = 0` for all models and `pass@1` ≈ qwen .22 / deepseek .18 / minimax .10 across the F-set. This Claude baseline is a **different harness** (Claude Code drives its own loop + native tools; no Factor-P/Factor-V arms), so the numbers aren't directly comparable — but the qualitative picture matches: F3 tractable, F1/F2 hard. This baseline gets a clean pass^k on F3/edit-only that the ablation models did not.

## Known gaps / methodology notes

- **`total_cost_usd` is parsed but NOT persisted** in the trajectory records (the runner maps tokens + rounds into `Usage`/`rounds` but drops cost). So per-attempt API-equivalent \$ is unavailable for this run. Follow-up: persist `total_cost_usd` and re-run if a cost metric is wanted. (`prompt_tokens` is the claude-reported, cache-adjusted input count, not a cumulative prompt size — read completion tokens as the effort signal.)
- **`is_error` → env-invalid masking.** `--max-budget-usd 0.50` aborts also set `is_error` and would be masked out of pass^k. In THIS run nothing voided, so it didn't bite — but if a future run shows VOIDs, check the budget-stop rate before trusting pass^k (see plan "Known limitation").
- **Auth fix (PR #40):** the original clean-temp-HOME isolation broke OAuth (creds resolve via `$HOME` → macOS Keychain + `~/.claude.json`); the first smoke was all "Not logged in"/VOID. Fixed by running under the real HOME + `--safe-mode` (disables CLAUDE.md/skills/plugins/hooks/MCP while keeping auth/model/tools) — a stronger vanilla guarantee. All 30 attempts here used the fixed harness.

## Artifacts

- Summary: `reports/agentic-v1/f-claude-baseline/full/claude-baseline-summary.json`
- Per-attempt JSONL (drill-down): `full/runs-claude-claude-cli-claude-sonnet-4-6-{edit-only,natural}-F.jsonl` (15 each)
