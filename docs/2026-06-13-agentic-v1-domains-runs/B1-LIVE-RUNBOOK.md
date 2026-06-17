## B-1 Live Spike runbook (owner-performed; deferred per spec §9)

Preconditions (spec §12 — all owner, before the live run):
1. `[candidate] password` set in `evaluator.toml` (currently empty); `bxu` confirmed
   least-privilege (CANNOT read the goldens).
2. `[candidate] url` set (e.g. `…/MicroStrategyLibrary/app`) and `[candidate] folder` chosen.
3. **Store relocation (§7):** move the evaluator store + `evaluator.toml` OUT of the repo
   tree and update `[store] path` BEFORE any `--driver claude` arm runs (the claude -p path
   is NOT OS-confined — a naive `./evaluator.toml` read must fail).
4. MSTR Library reachable from the run host (internal labs host / VPN).
5. `playwright-cli install --skills` run once on the host.

Calibrate FIRST (decision 6): run ONE trial (one model, noskill) and confirm it does NOT
hit `max_rounds` far from Save before the full 24-run sweep:

    uv run agent-eval-lab run-b --provider dashscope --model qwen3.7-max \
      --evaluator-config /relocated/evaluator.toml --arm noskill --out reports/b1-spike \
      --driver chat

Inspect `reports/b1-spike/b1-verdict-sheet-*.md`: if the single trial's stop_reason is
`max_rounds (censored)` with the object NOT near Save, raise max_rounds (or fix the prompt)
before the sweep.

Full sweep (per model × both arms; chat models run SEQUENTIALLY — never two models on the one
bxu login, §7):

    uv run agent-eval-lab run-b --provider dashscope --model qwen3.7-max --arm both ...
    uv run agent-eval-lab run-b --provider deepseek  --arm both ...
    uv run agent-eval-lab run-b --provider minimax   --arm both ...
    uv run agent-eval-lab run-b --driver claude --provider <claude> --arm both ...   # store relocated first

Score (Phase 2, manual): open each saved object in MSTR, score it against the
definition-match checklist (R1..R5) in the verdict sheet, and write
`verdicts.json` = `{run_uid: "PASS" | "FAIL" | "INVALID"}`.

Report (Phase 3, pure):

    uv run agent-eval-lab report-b --trials reports/b1-spike/trials-b-*.jsonl \
      --verdicts verdicts.json --prices evaluator-only/pricing.json \
      --out reports/b1-spike/B1-report.md

OUT of scope (owner-deferred, spec §9): the live MstrReadbackClient / automated readback /
exact-grid compare; OS-level claude -p confinement; the paid sweep itself. B-1 is a one-task
contingency (point summary, never a bootstrap CI).

**Known limitation:** a `claude -p` `--max-budget-usd` exhaustion exits cleanly with `is_error=False` and is recorded as `completed_natural` (not censored), because `ClaudeRunMeta` exposes no budget signal and the F-baseline driver behaves identically; calibrate-first mitigates premature caps.
