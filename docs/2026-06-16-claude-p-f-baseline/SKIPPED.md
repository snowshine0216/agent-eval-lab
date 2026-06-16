# SKIPPED — claude-p F baseline

These are OUT of the autonomous run and handed back to the owner. They are not
"abandoned" — they are the human-gated PAUSE the plan deliberately builds in.

## Task 7 — real smoke run (plan steps 3–5)

**Blocker:** consumes the owner's Claude Pro/Max subscription quota (spawns a real
nested `claude -p`) and requires `NODE_BIN` pointed at Node ≥20 for the held-out
oracle. The plan titles Task 7 "Smoke run (manual integration — then PAUSE)" and
states "This is the agreed stop point."

**Unblock path (owner):**
```bash
export NODE_BIN=/Users/snow/.nvm/versions/node/v22.22.2/bin/node
python -m agent_eval_lab run-f-claude-baseline \
  --out reports/agentic-v1/f-claude-baseline/_smoke --smoke
```
Then inspect the single JSONL row (non-empty produced tree, a graded pass/FAIL —
not env-invalid — recorded rounds + tokens + `total_cost_usd`).

## Full 30-attempt run

**Blocker:** the plan forbids running `--surface both` (k=5, bases f1/f2/f3 =
2×3×5 = 30 attempts) "without owner go-ahead." Gated behind the smoke report.

**Unblock path (owner):** after the smoke looks healthy, drop `--smoke` and run
the full matrix (keep or override `--max-budget-usd` / timeout defaults).
