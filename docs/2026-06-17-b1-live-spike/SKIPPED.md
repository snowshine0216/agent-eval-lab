# SKIPPED — B-1 Live Spike

No OUT-scope **autodev items** (spec mode, N=1).

For traceability, the spec's own in-item deferrals (spec §9) — these are NOT separate autodev
items; they are explicitly out of scope *inside* item 001 and stay deferred:

- **Live `MstrReadbackClient`** (evaluator-credentialed readback) + automated definition
  extraction + exact-grid compare — replaced by human (owner) scoring this spike.
- **B-2 … B-10** task definitions + goldens, and therefore the cluster-bootstrap CI.
- **`run-m1` integration** — `run-b` is standalone; B stays out of the D/F re-run path.
- **REST readback** — noted in the parent spec; not built here.
- **OS-level `claude -p` confinement** — deferred to the production B runner; the spike ships a
  documented residual limitation + store relocation instead.
- **Live execution / paid 24-run sweep** — owner-run after the build (spec §12 preconditions).
