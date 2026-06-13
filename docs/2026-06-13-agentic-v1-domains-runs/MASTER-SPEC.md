# MASTER-SPEC — agentic_v1 domains + runs (continuation)

Continues the `agentic_v1` use-case eval. The 5/7 instrument foundation is merged to `main`
(PR #15 + CI guards #16/#17). This run delivers the **remaining domains + the live M1/M2 runs**
so the deliverable — an updated M1/M2 report over the owner's real systems — lands.

Source spec: [docs/superpowers/specs/2026-06-12-use-case-agentic-eval-design.md](../superpowers/specs/2026-06-12-use-case-agentic-eval-design.md)
Foundation handoff: [../2026-06-13-agentic-v1-eval-foundation/HANDOFF.md](../2026-06-13-agentic-v1-eval-foundation/HANDOFF.md)

## IN scope (this run)

| # | id | Package | What it delivers |
|---|----|---------|------------------|
| 008 | runner-harden | Pkg 1 | Harden the D-set runner (provider-error → recorded failure not crash; trim page-text fed back into the conversation; incremental JSONL write); fix local Qwen config (`qwen3-8b` → ollama `Qwen/Qwen3-8B`) + add the SiliconFlow Qwen-ladder provider. Then **run D-domain at k=5** across deepseek/glm/minimax/local + SiliconFlow Qwen ladder and **regenerate report-m1**. |
| 009 | f-domain-adapter | Pkg 004 | F-domain repo adapter: isolated candidate `web-dossier` workspace pinned to the frozen pre-fix SHA (`5b0c13a6`), wdio/node edge, **F1 + F2 env-free oracles** reusing the F3 node-test pattern, golden-discriminating + contradiction checks. Wire F into `run-m1`. **Run candidate F-runs** across the roster → F-domain enters the macro composite. |
| 010 | b-domain-m2 | Pkg 006 | B-domain: per-run MSTR Library isolation (`run_uid` save name, preflight-absence, capture created object id, reset), the stripped knowledge-only `strategy-test` fork loader (D27), and the `playwright-cli` readback oracle under **evaluator** creds (D19). Wire B into `run-m1`/report. **Run B-noskill vs B-skill (M2)** once owner artifacts land. |

## Deliverable
`reports/agentic-v1/M1-final-report.md` regenerated with **D (k=5) + F** per-domain scores,
macro composite, Pareto (success vs cost/rounds/tokens), fc-v3 taxonomy, validity/void —
and **B-domain + M2** added once 010's owner artifacts are provided.

## OUT of scope (YAGNI / deferred — §12)
- gpt-5.5 (region/ToS blocked — auto-includes if the network changes).
- E3 axis ablation; live-web dynamic mode; judge calibration κ; pinned backend for full e2e determinism.
- Synthetic substrates.

## Integrity invariants (carried, never relaxed — §9)
- No golden/oracle/answer/object-id reachable from any candidate workspace, ref, prompt, or account.
- Repo is PUBLIC: MSTR creds / labs host / internal docs IP live ONLY in gitignored `evaluator.toml` + `.env`.
- Candidate `web-dossier` checkout pins the frozen pre-fix SHA (`5b0c13a6`), never `m2021` HEAD (D32).
