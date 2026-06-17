## B-1 Live Spike runbook (owner-performed)

> **First live run executed 2026-06-17 — see [CALIBRATION-FINDINGS.md](../2026-06-17-b1-live-spike/CALIBRATION-FINDINGS.md).**
> Outcome: harness works end-to-end, but no candidate completed B-1 in a feasible budget; the
> paid sweep was NOT run. The procedure below is the validated one (ADR-0022 pre-auth).

Preconditions (all owner, before the live run):
1. **Candidate login.** `bxu` is **passwordless** and least-privilege (cannot read the goldens —
   verified). `[candidate] password` is a vestigial non-empty placeholder (the `run-b` guard
   requires it, but `render_b_prompt` drops it — the credential never reaches the model, §7).
2. **Pre-auth (ADR-0022).** The candidate session is authenticated **out-of-band** via a pre-saved
   playwright `storageState`. One time, log into the Library as `bxu` in a playwright-cli session
   (with `ignoreHTTPSErrors`) and `state-save` it, then set `[candidate] storage_state` to that
   file. The chat **and** claude drivers auto-write a per-trial `.playwright/cli.config.json`
   (cert-ignore + this storageState), so the candidate's first `open` lands authenticated.
   **Regenerate the storageState before each sweep — MSTR sessions expire** (watch for
   `login-page` hits as the expiry signal during long runs).
3. `[candidate] url` set (`…/MicroStrategyLibrary/app`) and `[candidate] folder` chosen (`/Candidate/bxu`).
4. **Store relocation (§7):** for any `--driver claude` arm, point `[store] path` + `storage_state`
   at a location OUTSIDE the repo tree (the claude -p path is NOT OS-confined). The chat driver is
   allowlist-confined and does not require relocation.
5. MSTR Library reachable from the run host (internal labs host / VPN).
6. playwright-cli on PATH under node ≥20 (the harness pins `…/v22.22.2/bin`); Chrome/chromium installed.
   The self-signed labs cert is handled automatically by the cert-ignore config (no flag needed).

Calibrate FIRST (decision 6): run ONE trial (one model, noskill) and confirm it does NOT
hit `max_rounds` far from Save before the full 24-run sweep. Raise the round cap with
`--max-rounds` (chat) per calibration; `--max-budget-usd` / `--claude-timeout` bound the claude arm:

    uv run agent-eval-lab run-b --provider deepseek \
      --evaluator-config /relocated/evaluator.toml --arm noskill --out reports/b1-spike \
      --driver chat --max-rounds 150

Inspect `reports/b1-spike/b1-verdict-sheet-*.md`: if the single trial's stop_reason is
`max_rounds (censored)` with the object NOT near Save, raise `--max-rounds` (or fix the prompt)
before the sweep. **2026-06-17 finding:** deepseek (both arms, 150r) and `claude -p` (20-min
timeout) all censored without saving — calibrate honestly before committing to the paid sweep.

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
