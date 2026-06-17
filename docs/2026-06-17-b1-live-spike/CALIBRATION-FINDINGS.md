# B-1 live spike — calibration findings (2026-06-17)

First **live** execution of the B-1 spike (owner ran the calibrate-first protocol of the runbook
before any paid sweep). Outcome: the harness now drives the live MSTR Library end-to-end, but
**no candidate completed B-1** in a feasible budget. The full 24-run sweep was **not** launched —
calibration predicted it would be ~all-censored.

## Setup confirmed working

- MSTR Library reachable from the run host; `bxu` (candidate) and `mstr1` (evaluator) both
  authenticate via REST (`204` + auth token). `bxu` is **passwordless**.
- playwright-cli `0.1.14` under node `v22.22.2` (the harness's pinned PATH); Chrome channel + chromium present.
- Pre-auth via storageState + cert-ignore config (ADR-0022) — validated: a fresh context loading
  the saved `bxu` login opens `/app` authenticated; `0` login-page hits across a 150-round trial.

## Calibration trials (deepseek-v4-pro chat-loop unless noted)

| # | arm | cap | stop_reason | how far it got | saved? | ~cost |
|---|---|---|---|---|---|---|
| 1 | noskill | 50r | `max_rounds` | **pre-fix** — stuck at cert error + login form; hallucinated a password | ❌ | $0.11 |
| 2 | noskill | 150r | `max_rounds` | auth held all 150r; reached Create → Report → Design → SAPBW source tree; **stuck selecting the cube** | ❌ | $0.79 |
| 3 | **skill** | 150r | `max_rounds` | cleaner technique (element refs + search vs JS-eval scraping); still stuck at cube/report-object selection | ❌ | $0.90 |
| 4 | noskill | `claude -p` sonnet-4-6, $6 / 20 min | **timeout** | **no trajectory recorded (blind)** — ran the full 20 min, saved nothing | ❌ | ≤$6 |

**MSTR check:** searched the Tutorial project for every trial's save-name fragment
(`b-b1`, `claude-sonnet`, `deepseek-deepseek`, `__0000`, `noskill`) → **0 objects**. Nobody saved a report.

## Conclusion

This answers the parent spec's core question — *"can a model drive the MSTR Library SPA end-to-end at
all?"* For these candidates at these budgets: **they navigate but cannot complete the B-1 Design-mode
build** (cube → grid → answer prompt → Save). The bottleneck is **not** auth, the cert, or the round
cap (all solved/raised) — it is candidate capability on a long-horizon, deeply-nested antd GUI.
deepseek (both arms) consistently stalls at source-cube selection; the skill improves *technique* but
not *completion*. The `claude -p` probe is **inconclusive** — its driver records no trajectory, so its
20-min timeout cannot distinguish "working the build" from "stuck at login" (it may not have loaded
the storageState if it ran playwright-cli from a non-workdir CWD).

## Decisions

- **No paid sweep.** A k=3 sweep (3 chat models × 2 arms) at 150 rounds would be ~$50–100, several
  hours, and ~all-censored — calibration already predicts the null result. Not run (owner decision).
- **Ship the harness fixes** (ADR-0022 + the `--max-rounds` / `--max-budget-usd` / `--claude-timeout`
  flags + `[candidate] storage_state`) — they are real, tested improvements that unblock any future
  B run.
- **Deferred for a future run** (not done here): making the `claude -p` driver observable (trajectory
  capture) so its completion can be judged; raising its timeout; or reframing B-1 to a shorter /
  pre-staged objective so the noskill-vs-skill comparison can produce non-censored data.

## Cost

~$5–8 total across the 4 trials (chat models ~$1.8 recorded; `claude -p` bounded by the $6 budget,
actual unrecorded — the timeout path captures no cost).
