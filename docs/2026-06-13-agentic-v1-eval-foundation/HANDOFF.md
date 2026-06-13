# Handoff — agentic_v1 use-case eval (autodev run, 2026-06-13)

What got built, what the report shows, and exactly what to do next.

## TL;DR
The **measuring instrument is complete and verified** (5 of 7 spec packages, all TDD-gated,
repo green + ruff-clean, on branch `autodev/agentic-v1-eval-foundation`). A **real scoped M1
run** was executed on the **D-domain** (CMC docs QA) across the reachable cloud models, and an
actual report was produced. The **F-domain** (004) and **B-domain/M2** (006) harnesses are
designed-but-not-built; the full-scale run is a parameter change you kick off.

## What's built and merged (feature branch `autodev/agentic-v1-eval-foundation`)
| Pkg | Item | What it is |
|---|---|---|
| 1 | records+runner | versioned `Trajectory` (+`v1_compat`), censoring loop (safety_cap=200 tool calls), `run_task_k_valid` (k-valid replacement-trial loop), fc-v3 `environment_failure` classifier |
| — | experiment types | `experiments/` pkg: all §18.3 types, `freeze-spec` (spec_hash), `evaluator.toml` loader, pricing/cost, content-verified hydration, `check-env` (passes live: playwright + MSTR 204) |
| 2 | F3 oracle | `node --test` execution oracle, golden-discriminating (golden PASS / pre-fix FAIL / 2xx-mutant FAIL / causal-tamper FAIL); D19/D31 honored |
| 4 | D-set harness | sandboxed playwright-cli **bash agent** + `FactKeySpec` grader (required+forbidden+faithfulness) + 15 fact-keys + `run-dset` / `run-m1` / `report-m1` |
| 6 | M1/M2 report engine | per-domain pass^k (D/B cluster-bootstrap, F Clopper–Pearson), Holm, macro composite, Pareto, validity-mask/void, fc-v3 taxonomy; partial-coverage graceful |

Every item passed: drift check → `/code-review` (HIGH) → `/verify`. The gates caught and fixed
**real** bugs at every step (VOID-formula over-voting, a return-type mismatch, `[oracle.b_set]`
parsing, `readback` type, self-signed-cert TLS, cost-by-condition inflation, an `ET.ParseError`
crash gap, a node-version guard, a validity-misclassification, a silent-void gap, a composite
zero-weight crash, a void-replay loss). See `items/*-review.md` for details.

## The report
- **File:** `reports/agentic-v1/M1-final-report.md`  (regenerate any time with the command below)
- **Coverage:** M1, **D-domain only**, scoped run — **3 models** (deepseek-v4-pro, GLM-5.1,
  MiniMax-M3) × **15 CMC docs questions** × **k=2 valid trials** (full spec is k=5).
- **Frozen spec:** `reports/agentic-v1/M1-spec.frozen.json` (`spec_hash=6ec69869…`).
- F-domain and B-domain render as **"not yet run"** (their harnesses aren't built); the macro
  composite is flagged **reduced-coverage**. This is the honest partial report, not a failure.

**Scoped pilot run (2026-06-13), D-domain, k=2, 2 models** (spec `M1-pilot-spec.frozen.json`, `spec_hash=732ede1b…`):

| model | D pass^k [95% CI] | cost (30 runs) | tokens | rounds | valid/invalid/void |
|---|---|---|---|---|---|
| deepseek-v4-pro | **0.600** [0.333, 0.867] | $10.16 | 5.74M | 4.5 | 30 / 0 / 0 |
| MiniMax-M3 | **0.600** [0.333, 0.867] | **$1.11** | **1.69M** | 5.0 | 30 / 0 / 0 |

- **Finding:** the two frontier models **tie on D-domain accuracy** (pass^k = 0.60; 9/15 questions reliable across both k=2 trials), Δ=0.000, Holm-adj p=1.0 (**not significant**). The differentiation is **efficiency**: MiniMax dominates the cost (~**9× cheaper**) and token Pareto frontiers; DeepSeek edges rounds (4.5 vs 5).
- **Failures:** 12/30 runs each, all classified `agent_failure / other_miss` (the model browsed a healthy env but missed required fact-keys) — not env/harness failures (validity mask: 0 invalid, 0 void).
- **GLM-5.1 (SiliconFlow) crashed** mid-run on an HTTP `400 Bad Request` — almost certainly context-length (the browse accumulates large page-text dumps into the conversation; GLM-5.1's window is tighter). **Robustness gap exposed:** `run_dset` lets one bad request abort the whole model's run, and writes JSONL only at the end, so GLM's partial data was lost. **Fix before the next run:** (a) catch per-run provider errors → record as `agent_failure`/`harness_failure` instead of crashing; (b) cap/trim the page text fed back into the conversation (or stream incrementally); (c) write runs incrementally, not at the end. Then GLM is includable.
- **Caveat:** this is a **scoped pilot** (k=2, D-only, 2 models) — NOT the pre-registered k=5 M1. The canonical k=5 spec is frozen separately at `M1-spec.frozen.json` (`spec_hash=6ec69869…`) for the full run.

## What is NOT done (and why)
| Gap | Status | Why |
|---|---|---|
| **004 — F-domain (F1/F2)** | designed, not built | env-free oracles for the wdio TC99396_10 image-compare→assertions (F1) + the diagnose-trace fixture (F2); the F3 oracle (node-test pattern) is the template. The golden is staged at `evaluator-only/web-dossier-golden/` (base `5b0c13a6` / head `ebdfcbea`). |
| **006 — B-domain + M2** | designed, not built | MSTR Library long-horizon browser automation + the stripped `strategy-test` fork + REST/playwright readback oracle. MSTR is **reachable** (auth 204). Needs: B-1..B-10 task defs (only B-1 exemplar exists), a B golden object id, and a least-priv **candidate** MSTR account (≠ evaluator) for the D19 boundary. |
| **local Qwen3-8B** | excluded from the run | ollama serves `Qwen/Qwen3-8B` but its `/v1/chat/completions` endpoint times out (model not serving inference). Config id is also `qwen3-8b` ≠ `Qwen/Qwen3-8B` — fix `runners/config.py` + start the model in ollama. |
| **SiliconFlow Qwen ladder** | provisional | `siliconflow:Qwen/Qwen3.5-397B-A17B` / `Qwen3.6-35B-A3B` condition ids are placeholders; the `siliconflow` provider entry isn't in `runners/config.py` yet (it currently rides the `glm` SiliconFlow key). Add the provider + verify the model ids before including. |
| **gpt-5.5** | blocked | China region-block + datacenter-IP ToS-block. Kept in the roster; runs automatically if the network changes. |
| **k=5, all 15 D-questions** | scoped to k=2 | wall-clock: k=5 × 15q × N models is hours. k=2 was run for a same-session report; bump to k=5 for the spec-faithful headline. |

## How to run more (exact commands)
Prereqs every time:
```bash
cd ~/Documents/Repository/agent-eval-lab
export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"   # playwright-cli needs node>=20
set -a; . ./.env; set +a                                    # cloud API keys + CMC_DOCS_URL
```
**Scale the D-domain to k=5 (all 15 q):** edit `evaluator.toml` `[runner] k_valid=5`, then per model:
```bash
uv run python -m agent_eval_lab.cli run-dset --provider deepseek \
  --evaluator-config evaluator.toml --out reports/agentic-v1
# repeat for --provider glm / minimax (and local/siliconflow once fixed)
```
(or the scratch `/tmp/run_dset_scoped.py PROVIDER N_Q K_VALID OUT_DIR` used for the scoped run.)

**Regenerate / extend the report** (add `D:cond=path` lines as runs land; F/B render "not yet run"):
```bash
uv run python -m agent_eval_lab.cli report-m1 \
  --spec reports/agentic-v1/M1-spec.frozen.json \
  --runs D:deepseek:deepseek-v4-pro=reports/agentic-v1/runs-m1-deepseek-deepseek-v4-pro-D.jsonl \
         D:glm:Pro/zai-org/GLM-5.1=reports/agentic-v1/runs-m1-glm-Pro-zai-org-GLM-5.1-D.jsonl \
         D:minimax:MiniMax-M3=reports/agentic-v1/runs-m1-minimax-MiniMax-M3-D.jsonl \
  --prices evaluator-only/pricing.json --out reports/agentic-v1/M1-final-report.md \
  --seed 20260613 --n-resamples 2000 --alpha 0.05
```

## Recommended next steps (in order)
1. **Scale D to k=5** across the 3 working models (+ fix local Qwen, + add SiliconFlow) — biggest report-quality win for the least new code.
2. **Build 004 (F-domain)** — env-free, golden already staged; reuses the F3 node-test oracle pattern. Adds a 2nd domain to the macro composite.
3. **Build 006 (B-domain + M2)** — the skill-effect experiment; needs the owner artifacts above (B tasks, candidate account, B golden).
4. **Land the work:** the feature branch is left open with all items merged; open its PR to `main` when ready (this run did NOT auto-merge to a protected branch).

## Where things live
- Run tracker: `docs/2026-06-13-agentic-v1-eval-foundation/PROGRESS.md` · preflight evidence: `PREFLIGHT.md` · per-item specs/plans/verdicts: `items/`.
- Evaluator-only (gitignored, never candidate-visible): `evaluator-only/` (F-golden, cmc answers + fact-keys, pricing). `evaluator.toml` (creds, gitignored).
