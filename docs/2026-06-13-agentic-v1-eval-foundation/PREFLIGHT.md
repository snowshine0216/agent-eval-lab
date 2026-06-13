# Preflight — agentic_v1 eval foundation (2026-06-13)

User gate: *"make sure none blocked so you can run eval successfully … stop if any preflight fails."*
**All preflights PASS.** Evidence below.

## 1. Model providers (M1 roster)
Built `.env` (gitignored) from `~/.zshrc` exports. Load with `set -a; . ./.env; set +a` (zsh needs `./.env`).

| Provider | Auth check | Models |
|---|---|---|
| DeepSeek (`api.deepseek.com`) | HTTP 200 | `deepseek-v4-pro` |
| SiliconFlow (`api.siliconflow.cn`) | HTTP 200 | `Pro/zai-org/GLM-5.1`, Qwen ladder `Qwen/Qwen3.5-397B-A17B`, `Qwen/Qwen3.6-35B-A3B` |
| MiniMax (`api.minimaxi.com`) | HTTP 200 | `MiniMax-M3` |
| local ollama (`localhost:11434`) | HTTP 200 | `Qwen/Qwen3-8B` |
| OpenRouter `gpt-5.5` | **BLOCKED** (region + datacenter-IP ToS) — dropped, prior finding |

→ ≥5 reachable models for M1.

## 2. MSTR labs server (B-set / M2) — **REACHABLE**
Earlier HTTP 000 was the self-signed cert; `curl -k` fixes it.
`POST https://<MSTR_LABS_HOST>/MicroStrategyLibrary/api/auth/login`
(<MSTR_USER>/<MSTR_PASS>, loginMode 1) → **HTTP 204 + `x-mstr-authtoken`**. Health probe (§18.5) works.

## 3. playwright-cli (D-set / B-set) — **INSTALLED**
`@playwright/cli@0.1.14` requires node ≥18 → installed under **nvm node v22.22.2**
(`~/.nvm/versions/node/v22.22.2/bin/playwright-cli`). Default shell node is v16 → harness MUST
prepend the node-22 bin to PATH. `install --skills` done. Smoke test drove the live docs server
(`http://<CMC_DOCS_HOST>/docs/24.12/Introduction.html`) and read real DOM ("Introduction |
Strategy Customer Managed Cloud Documentation"). `.playwright-cli/` + `.claude/skills/playwright-cli/` gitignored.

## 4. F-set golden — **STAGED** (`evaluator-only/web-dossier-golden/`, gitignored)
Owner PR **#23483** isolated to its single fix commit.
- **Golden head:** `ebdfcbea74a4f871af623a4def93391593b14238`
- **Candidate base (pin):** `5b0c13a6bc9e7b9a3c60083da511f3efd0d39505` (= `ebdfcbea~1`)
- Verified `5b0c13a6..ebdfcbea` = **5 files, +71/−9** (matches spec §4.1 exactly).
- **D31 holds:** correlate.js / signal.js / failure-analysis.config.js untouched.
- `report-to-allure.js` change = the non-2XX `buildNetworkText` filter (F3 attachment layer).
- Golden test already encodes the §18.6 F3 fixtures (all-2XX→no attachment; mixed 200/503/200→include 503, exclude 200).
- Candidate base shows the UNFILTERED buggy `buildNetworkText`.
- ⚠️ memory's old base `f2990fde…` was a **bad object** (absent from repo) — corrected.

Staged files: `F-golden.patch`, `golden-files/{LibraryNotification,Snapshots_SendBackground.spec,report-to-allure,report-to-allure.test,wdio.conf.ts}.golden`, `golden-files/MANIFEST.txt`, `meta.json`.

## Residual B-set authoring gaps (NOT environmental blockers)
- B-1..B-10 task defs not authored (only B-1 exemplar in spec §4.3).
- B golden object id not staged in evaluator-only.
- Only one MSTR account (<MSTR_USER>) — a least-priv *candidate* account (≠ evaluator, D19) still needed for B integrity.
→ B-domain runnable for **B-1 only**; full M2 ≥10-task bootstrap is an owner co-design gap (tracked in SKIPPED.md).
