# MASTER-SPEC — claude-p F baseline

**Mode:** plan (autodetected — target has 7 numbered TDD tasks with file paths,
fenced shell commands, and `Run:`/`Expected:` markers).
**Run dir:** `docs/2026-06-16-claude-p-f-baseline/`
**Source plan:** `docs/superpowers/plans/2026-06-16-claude-p-f-baseline.md`
**Source spec:** `docs/superpowers/specs/2026-06-16-claude-p-f-baseline-design.md`

## Goal

Run vanilla Claude Code (`claude -p`, Sonnet 4.6, no skills) as the agent on
F1/F2/F3 repair tasks under two tool surfaces (`edit-only`, `natural`), graded by
the existing held-out Node oracle — a Claude Code baseline distinct from the v2
model-vs-model ablation.

## Scope classification

| # | Item | Scope | Note |
|---|------|-------|------|
| 001 | Implement the 7-task TDD plan: `runners/claude_cli_candidate.py` + `run-f-claude-baseline` CLI subcommand + unit tests + report dir (Tasks 1–6), validated by the no-quota **dry-run** smoke (Task 7 step 1) | **IN** | Pure code + unit tests; no quota, no network. |

## Explicitly OUT (deferred to owner) — see SKIPPED.md

- **Task 7 real smoke run** (1 × F1 × edit-only, plan steps 3–5) — spawns a real
  nested `claude -p`, consumes the owner's Pro/Max subscription quota, and needs
  `NODE_BIN` pointed at Node ≥20 for the held-out oracle. The plan labels Task 7
  "manual integration — then PAUSE / the agreed stop point." Resource-consuming +
  owner-gated → deferred.
- **Full 30-attempt run** (`--surface both`, k=5, bases f1/f2/f3 = 2×3×5) — the
  plan forbids running it "without owner go-ahead."

## Why this split

The implementation (Tasks 1–6) is fully autonomous: deterministic Python, unit
tests with no real `claude` and no network, and a `--dry-run` path that makes no
subprocess. That entire surface lands on the feature branch through the normal
autodev gates. The paid integration (real `claude -p` quota + Node-≥20 oracle) is
exactly the human-gated PAUSE the owner built into the plan, so it stays OUT and
is handed back at the pause with evidence.
