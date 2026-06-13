# MASTER-PLAN — agentic_v1 domains + runs (continuation)

- **Mode:** backlog (3 dependency-ordered packages from §16: Pkg 1 harden+run, Pkg 004 F-domain,
  Pkg 006 B-domain/M2). Per-item brainstorming + grill are **PRE-COMPLETED ⏭️** — the source spec
  is the output of 3 review rounds + the 2026-06-13 grill (§15/§15a/§15b/§18). Orchestrator does
  NOT re-invoke brainstorming/grill; each item-spec derives from its source-spec section.
- **PR shape: Mode A — per-package PR to `main`, squash-merged.** Explicit user opt-in this turn:
  *"each as its own PR to main (squash; keep history clean of secrets)."* Each package is one PR;
  squash-merge to main after its gates pass. Matches the established cadence (foundation PRs #15/#16/#17).
- **Protected-branch opt-in:** GRANTED this turn ("each as its own PR to main"). Squash-merge to `main` per package.
- **Project type:** non-web (Python eval library) → **Verify** (not QA) on every item. The live
  run IS part of verification for 008/009 (real models, real money — authorized "full roster").
- **Implementation (corrected 2026-06-13 after user pushback):** follow the autodev
  **`superpowers:subagent-driven-development`** contract — Sonnet impl subagents — for the net-new
  **009 (F-domain)** and **010 (B-domain)** work. **008** was implemented inline on Opus before the
  correction; per user decision it is **kept** (TDD-green) and routed through its independent gates
  (drift subagent + `/code-review` + `/verify`) rather than wastefully re-implemented. Earlier
  "inline is the right call" framing was a rationalization and is retracted. Gates unchanged for all
  items: drift → `/code-review` → `/verify` → PR → squash-merge to main.
- **Test discipline:** tests mirror src (`tests/<pkg>/test_<mod>.py`), `uv run pytest`. Whole tree ruff-clean.
- **Env for live arms (every run):**
  `export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"` + `set -a; . ./.env; set +a`.
- **Integrity (never relaxed):** repo is PUBLIC — creds/labs-host/docs-IP live ONLY in gitignored
  `evaluator.toml` + `.env`. Goldens/answers/object-ids never reachable by the candidate (D19/D33).

## Items (dependency order)

| # | id | Package | Status | Depends |
|---|----|---------|--------|---------|
| 008 | runner-harden | Pkg 1: harden D-runner + Qwen/SiliconFlow + **RUN D k=5** + regen report | IN | — (foundation merged) |
| 009 | f-domain-adapter | Pkg 004: isolated wdio workspace + F1/F2 oracles + **RUN F candidate** | IN (golden staged) | 008 |
| 010 | b-domain-m2 | Pkg 006: B isolation + readback oracle + stripped-skill fork + **RUN M2** | IN (owner artifacts pending) | 009 |

## Models per dispatch
Plan→Fable (specs pre-completed, plans inline-light). **Impl (009/010)→Sonnet subagents via
`superpowers:subagent-driven-development`.** Drift→Sonnet subagent. 008 impl was inline-Opus (kept).
`/code-review` + `/verify` invoked as skills on each package's diff.

## Run convention
After each phase passes its gate, mark the PROGRESS cell ✅ and the task `completed`. Resume from
PROGRESS.md on a fresh session. `.autodev-current` points here.
