# MASTER-SPEC — B-1 Live Spike (human-scored)

- **Mode:** spec (single feature; user-authored + grilled spec → writing-plans → impl)
- **Run dir:** `docs/2026-06-17-b1-live-spike/`
- **Source spec:** [items/001-spec.md](items/001-spec.md) (verbatim copy of
  `docs/superpowers/specs/2026-06-17-b-set-live-spike-design.md`)
- **Date:** 2026-06-17

## Scope classification

| # | Item | Scope | Rationale |
|---|------|-------|-----------|
| 001 | B-1 live spike — `run-b` standalone driver + injected candidate drivers (chat + `claude -p`) + grade-less `BTrial` + owner-verdict `report-b` pipeline, with full unit-test coverage and no live MSTR/provider | **IN** | This is the single feature the spec describes; it decomposes into 11 plan steps (spec §11) executed as one autodev item via `writing-plans` → `subagent-driven-development`. |

No OUT-scope items at the autodev level — the spec's own deferrals (live `MstrReadbackClient`, B-2…B-10, `run-m1` integration, REST readback, OS-level `claude -p` confinement) are **already** out of scope inside the single IN item and are recorded in [SKIPPED.md](SKIPPED.md) for traceability. They are not separate autodev items.

## Build-vs-run boundary (from the spec)

The spec is **build + test now; live execution deferred to the owner.** This run delivers the code + tests + runbook only. It does **not** run any live MSTR session, live provider call, or paid sweep. Success = the unit suite passes with fakes and the `run-b` / `report-b` CLI surfaces exist and are wired. The owner runs the 24-run live sweep later (spec §12 preconditions).
