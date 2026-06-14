# Deferred live-execute runbook (D / F / B-M2 + final report)

Per the 2026-06-14 decision ("build 010 code; defer ALL live runs"), the code for 008/009/010
is built + gated + merged, and the **live execute phases are left for the owner to run** on their
own schedule. The runs hit live infra (CMC docs Intelligence Server, MSTR Library) — budget ~8–15h
for the full D roster alone (≈6–10 min/task × 15 tasks × 6 arms; the local CPU arm is slowest).

All run artifacts live under gitignored `/reports/agentic-v1/`. The M1 spec is frozen at
`spec_hash ca4467f2…` for `local:Qwen/Qwen3-8B` (`reports/agentic-v1/M1-spec.frozen.json`).

## 0. Environment (every run)
```bash
cd ~/Documents/Repository/agent-eval-lab
export PATH="/opt/homebrew/bin:$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"   # timeout + node
set -a; . ./.env; set +a                                                       # cloud keys + CMC_DOCS_URL
uv run python -m agent_eval_lab.cli check-env --evaluator-config evaluator.toml  # expect MSTR 204 + playwright ok
```
Provider keys required (all confirmed present 2026-06-14): `DEEPSEEK_API_KEY`, `SILICONFLOW_API_KEY`
(serves both `glm` and `siliconflow`), `MINIMAX_KEY`. `local` = ollama `Qwen/Qwen3-8B` (no key).

## 1. D-domain k=5 roster (6 arms) — stall-watchdog script
A progress-based watchdog kills an arm only if its output JSONL stops growing for 20 min (healthy
arms run to completion; a wedged live browse is reaped). The script body is saved below — recreate
`/tmp/run-d-k5-v2.sh` from it (or this repo's git history of this run) and:
```bash
bash /tmp/run-d-k5-v2.sh        # foreground; or wrap in nohup/& for background
tail -f reports/agentic-v1/run-d-k5.log
```
Arms + output slugs (the `_slug` maps `:` and `/` → `-`):
| arm | command flags | output |
|---|---|---|
| deepseek-v4-pro | `--provider deepseek` | `runs-dset-deepseek-deepseek-v4-pro.jsonl` |
| GLM-5.1 (SiliconFlow) | `--provider glm` | `runs-dset-glm-Pro-zai-org-GLM-5.1.jsonl` |
| MiniMax-M3 | `--provider minimax` | `runs-dset-minimax-MiniMax-M3.jsonl` |
| Qwen3.5-397B | `--provider siliconflow --model Qwen/Qwen3.5-397B-A17B` | `runs-dset-siliconflow-Qwen-Qwen3.5-397B-A17B.jsonl` |
| Qwen3.6-35B | `--provider siliconflow --model Qwen/Qwen3.6-35B-A3B` | `runs-dset-siliconflow-Qwen-Qwen3.6-35B-A3B.jsonl` |
| local Qwen3-8B | `--provider local` | `runs-dset-local-Qwen-Qwen3-8B.jsonl` |
Each arm: `uv run python -m agent_eval_lab.cli run-dset <flags> --evaluator-config evaluator.toml --out reports/agentic-v1`.
Each run is incremental (per-task flush) + writes a `<runs>.void.json` sidecar (008 hardening) — a
crashed/killed arm keeps its completed tasks; just re-run that arm (it truncates + restarts cleanly).
`gpt-5.5` stays SKIPPED (region/ToS — see SKIPPED.md).

## 2. F-domain candidate runs (after the condition_id wiring)
⚠️ **Pre-req:** wire the real per-arm condition_id through `run_m1`'s F branch — see
`items/009-plan.md` → "## Execute-phase follow-ups" (`f_run._grade_tree` currently stubs
`condition_id="(f-local)"`). Until then F outcomes can't be attributed per arm.
F is env-free (no live infra) — the candidate produces a file tree, the node oracle grades it. Run F
across the same roster via `run-m1` (it builds D + F domain tasks). Candidate `web-dossier` checkout
stays pinned at `5b0c13a6` (never `m2021` HEAD — D32).

## 3. B-domain + M2 (after 010 merges) — live MSTR
Per 010 (B isolation + readback oracle + stripped-skill fork). **M2 is a 1-task contingency** until
B-2..B-10 + their goldens are provided (only B-1 is staged — see `items/010-b-domain-artifacts.md`).
Exact commands land in 010's plan/ship docs.

## 4. Regenerate the M1 report (D + F [+ B]) once runs land
```bash
uv run python -m agent_eval_lab.cli report-m1 \
  --spec reports/agentic-v1/M1-spec.frozen.json \
  --runs D:deepseek:deepseek-v4-pro=reports/agentic-v1/runs-dset-deepseek-deepseek-v4-pro.jsonl \
         D:glm:Pro/zai-org/GLM-5.1=reports/agentic-v1/runs-dset-glm-Pro-zai-org-GLM-5.1.jsonl \
         D:minimax:MiniMax-M3=reports/agentic-v1/runs-dset-minimax-MiniMax-M3.jsonl \
         D:siliconflow:Qwen/Qwen3.5-397B-A17B=reports/agentic-v1/runs-dset-siliconflow-Qwen-Qwen3.5-397B-A17B.jsonl \
         D:siliconflow:Qwen/Qwen3.6-35B-A3B=reports/agentic-v1/runs-dset-siliconflow-Qwen-Qwen3.6-35B-A3B.jsonl \
         D:local:Qwen/Qwen3-8B=reports/agentic-v1/runs-dset-local-Qwen-Qwen3-8B.jsonl \
  --prices evaluator-only/pricing.json --out reports/agentic-v1/M1-final-report.md \
  --seed 20260613 --n-resamples 2000 --alpha 0.05
```
(Add `F:<condition_id>=<path>` mappings once F runs land. Confirm exact slugs by `ls reports/agentic-v1/`.)
Partial rosters are fine — map only the arms that completed; the report renders the rest as not-yet-run.

## Watchdog script body (recreate /tmp/run-d-k5-v2.sh)
The script is in this run's git history; it sequences the 6 arms above, each with a 20-min
no-output-growth watchdog and a playwright-orphan reap between arms. Stall ticks = 10 × 120s.
