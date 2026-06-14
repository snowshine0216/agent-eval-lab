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

## 3. B-domain + M2 (010 MERGED — PR #21, `4e57bc4`) — live MSTR
010 landed the deterministic machinery (injectable `MstrReadbackClient` Protocol, per-run isolation
D20, readback oracle + `ReadbackSpec`, stripped-skill loader, B-noskill/B-skill arms, `run_b`,
`run_m1` B branch, cli B wiring). Tests stub all MSTR I/O. The LIVE execute needs these 5 steps
(canonical list in `items/010-plan.md` → "## Execute-phase follow-ups"):

1. **Implement the live `MstrReadbackClient`** (the Protocol in `src/agent_eval_lab/runners/mstr_client.py`)
   — an EVALUATOR-credentialed `playwright-cli` readback implementing `name_exists` /
   `created_object_id` / `readback` / `delete_object` against the live Intelligence Server using the
   evaluator account (`evaluator.toml [health_probe]` creds), `[oracle.b_set] project_id`, and the
   run's isolated folder. This is the ONLY piece with live MSTR I/O — no test in 010 needs it.
2. **Wire the live client into `cli._run_m1_command`** — swap `b_client=None` → the live client and
   pass the live `b_folder` (the run's isolated folder under the Tutorial Project). With `b_client`
   set, `run_m1`'s B branch runs the real readback grade. (010 added a stderr diagnostic that fires
   when B tasks are loaded but the live client is absent — that's your "not yet wired" cue.)
3. **Drive the candidate arms live** — `b-b1-noskill` and `b-b1-skill` with the CANDIDATE account
   (`evaluator.toml [candidate]` — least-priv, CANNOT read the golden, D19/D20) clicking through the
   Library UI; the harness records rounds/tokens/cost/wall-time on the `Trajectory`. The live save
   name comes from the real `Trajectory.run_uid` (010's `run_b` synthesizes a distinct per-arm
   save-name from `condition_id`+task index for the deterministic path; the live runner uses the
   real per-run uid).
4. **Env-validity mask** — wire the §18.5 health probe + the D34 replacement-trial loop (VOID on
   env-unhealthy) into the live B runner, mirroring `run_dset`. The live Intelligence Server is not
   run-to-run reproducible (§6), so B is graded only over the validity mask.
5. **Report M2 over B-1 HONESTLY** — a **1-task contingency**. NEVER label a 1-task percentile
   interval a "cluster-bootstrap CI" (D26/§8). B-2..B-10 task defs + their goldens are still NEEDED
   for the ≥10-task cluster bootstrap — mark them BLOCKED (`items/010-b-domain-artifacts.md`). Both
   arms are instrumented identically by the harness; the estimand is the bundled stripped-skill
   effect (D25/D37), not knowledge-only.

Integrity (PUBLIC repo): the candidate account never reaches any golden/oracle/object-id; the golden
object id / golden grid / project id stay in gitignored `evaluator.toml` + `evaluator-only/` ONLY.

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
(Add `F:<condition_id>=<path>` mappings once F runs land, and `B:<condition_id>=<path>` once the B/M2
arms land. Confirm exact slugs by `ls reports/agentic-v1/`. The report engine renders B generically
(`reports/m1._DOMAINS=("F","D","B")`) and treats a 1-task B as a contingency, never a cluster-bootstrap CI.)
Partial rosters are fine — map only the arms that completed; the report renders the rest as not-yet-run.

## Watchdog script body (recreate /tmp/run-d-k5-v2.sh)
The script is in this run's git history; it sequences the 6 arms above, each with a 20-min
no-output-growth watchdog and a playwright-orphan reap between arms. Stall ticks = 10 × 120s.
