# code_repair_v1 — task validity rubric

**Version: `cr-rubric-v1`** — every shipped row carries
`metadata.review = "passed:cr-rubric-v1"`.

This is the **authoring rubric** (the author's task-validity checklist) — distinct
from a *judge* rubric (`LlmJudgeSpec.rubric`, unused here) and from the
`VerificationSpec` itself (CONTEXT.md, the three rubric senses). Every task in
`code_repair_v1.jsonl` must pass all eight checks; the per-task verdict is
recorded in `metadata.review` (source of truth, frozen with the append-only row)
and mirrored in `review-ledger.md` (regenerable audit view).

## Checklist (every task must pass a–h)

- **(a) Unambiguous, single defensible fix** — exactly one defect family with one
  defensible repair semantics; alternative spellings of the same fix pass the
  oracle (the **reference solution** witnesses solvability, never uniqueness).
- **(b) Single capability** — the task isolates exactly one of the six taxonomy
  capabilities; a secondary skill, if unavoidable, is noted in the ledger.
- **(c) Verification matches intent** — the oracle (`ExecutionSpec`) is the outcome
  authority; policy clauses ride `TrajectorySpec` legs inside `AllOf`, never prose;
  no `FinalStateSpec` byte-equality over repaired files (valid alternative fixes
  must pass).
- **(d) Deterministic, hermetic** — no clock/RNG/network/env/filesystem/subprocess
  surface in any fixture tree; the 15-module import banlist is the mechanical
  backstop; dates are literal ISO strings.
- **(e) Self-contained oracle, disjoint paths** — no `conftest.py` anywhere (the
  sandbox runs `--noconftest`; a file inert in the sandbox but live under plain
  pytest is an authoring trap); oracle paths are disjoint from every initial-tree
  path (ADR-0012); test-module basenames unique across visible + oracle;
  `*_test.py` basenames banned so the `test_*.py` convention equals collection;
  harness-reserved basenames banned at any depth.
- **(f) Solvable inside the budget** — the reference solution passes visible suite
  and oracle through the production oracle edge within the 10 s sandbox default
  (`timeout_s = None` on all 15) and within `metadata.max_steps`
  (≥ 6 all, ≥ 8 T3/T4, ≤ 16).
- **(g) No import-time-exploit surface** — graded modules run code at import inside
  the oracle process (ADR-0010 residual trust boundary); each task's import-time
  surface is plain defs/constants, screened per row.
- **(h) The knob is the hardness** — for T3/T4, the declared `difficulty_knob` is
  the thing that actually makes the task hard (the human gate the mechanical
  checks cannot prove).

## Mechanical backstop

`tests/datasets/test_code_repair_v1.py` enforces (c)-shape, (d), (e), (f), and the
breadth/anti-rote witnesses of (a) mechanically over all 15 tasks — including the
no-op zero, stub neutralization, hack-fixture breadth, anti-rote transcription and
oracle-leakage proxies, policy coherence, and the determinism spot-check — on real
sandboxed pytest through the production oracle edge. Checks (a)-full, (b), (g),
and (h) are human gates recorded in the ledger.

## Re-review

Re-reviewing under a new rubric is a **new dataset version** (new `version` +
`world_template_id` family), never an in-place row edit — `metadata.review` is
frozen with the append-only row, and the sidecars freeze with it. A ledger edit
can never un-gate a row. The review-fixtures sidecar carries solutions and joins
the Weeks 9-10 never-train manifest.
