# 010 — B-domain owner artifacts (status)

Tracks the three (really four) owner-provided inputs 010 needs. **Creds + goldens live ONLY in
gitignored locations — never repeated here (public repo).**

| Artifact | Status | Where / note |
|---|---|---|
| **Candidate MSTR account** (least-priv, ≠ evaluator `mstr1`, can't read goldens — D19/D20) | ✅ STAGED | `evaluator.toml` `[candidate]` (gitignored). Provided by owner 2026-06-13. Wire a typed `CandidateConfig` in 010. |
| **Stripped knowledge-only `strategy-test` fork** (D27/§18.9) | ✅ STAGED | `evaluator-only/stripped-strategy-test/` (gitignored). SKILL.md stripped (run-path/capture/consolidate/contribute/cost wiring removed; bootstrap + credential slots + full Topic Map + escalation + domain non-negotiables kept). 79 domain files copied so all 57 Topic-Map `$SKILL_PATH` refs resolve (verified). `evaluator.toml [skill] strategy_test_path` already points at its `SKILL.md`. Source: `~/Documents/Repository/qa-skills/skills/strategy-test`. |
| **B-1 task instruction** | ✅ READY | Fully specified in spec §4.3 exemplar (SAPBW > AV_TUTO > Query_CharacteristicValue_Mandatory; Rows Years Hierarchy + Region; Cols Cost; Design Mode; prompt South → Apply; Save-As unique `<model>-<condition>-<run_id>`). Author as the candidate-visible B task. |
| **B-1 golden object id** | ✅ STAGED | `evaluator.toml [oracle.b_set.goldens]` key `"B-1"` + `[oracle.b_set] project_id` (gitignored, D19). Owner-provided 2026-06-13; **cross-checked against memory `agentic-eval-phase.md` — object + project ids match**. Enables the full B-1 oracle check (3) executed-grid-equals-golden. (Was in memory but never persisted to the evaluator store → couldn't be read by the harness; now durable on disk.) |
| **B-2..B-10 task defs + per-task golden object ids** | ❌ STILL NEEDED | Each varies ≥1 axis vs B-1 (§18.8: source / template / prompt). Needed for the full M2 ≥10-task cluster bootstrap; until then M2 is a 1-task contingency (NOT a cluster-bootstrap CI — §8/D26). |

## What 010 can do now vs. when the rest lands
- **Buildable + runnable now (FULL B-1):** the full B-set machinery (per-run isolation + `run_uid`
  save name + preflight-absence + capture-created-object-id + reset), the stripped-skill loader
  (`$SKILL_PATH`), the `playwright-cli` readback oracle, B-noskill vs B-skill arms, and the
  **full B-1 oracle (checks 1+2+3)** — the B-1 golden id is now staged. M2 over B-1 is a 1-task
  contingency (NOT a cluster-bootstrap CI — §8/D26), reported honestly.
- **Needs B-2..B-10 + their goldens:** the full M2 ≥10-task cluster bootstrap.

If the remaining goldens/tasks don't arrive: ship 010's code, run B-1 (definition-only or full if its
golden id lands), and mark the rest BLOCKED in PROGRESS/SKIPPED with these rows.
