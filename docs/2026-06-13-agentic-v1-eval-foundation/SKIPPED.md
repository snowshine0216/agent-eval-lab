# SKIPPED / PARTIAL — agentic_v1 eval foundation

Nothing is fully skipped at the code level; these are **run-coverage** limits with written reasons,
per the autodev contract (blocked sub-scope documented, never silently abandoned).

## gpt-5.5 (OpenRouter) — dropped from M1 roster
**Reason:** China region-block on direct access + datacenter-IP (AS13410/199.255.83.x) ToS-block via
proxy. Confirmed unrunnable in a prior phase. The harness keeps the `openrouter` provider entry so it
runs automatically if the network situation changes; the report notes it as "not evaluated — blocked."

## Full M2 skill experiment (≥10 B tasks) — PARTIAL (B-1 only)
**Reason:** owner-authoring gaps, not environmental:
- B-2..B-10 independent task defs not authored (spec §4.3 ships only the B-1 exemplar). The
  independence rule (§18.8) requires each to vary ≥1 axis — owner co-design.
- B golden object id not staged in the evaluator store.
- Only one MSTR account (<MSTR_USER>) exists; the D19 integrity boundary needs a separate least-privilege
  *candidate* account that cannot read the golden.

**What runs now:** B-1 (authored from the spec exemplar), noskill vs skill arms, isolated per-run,
MSTR playwright-cli readback oracle. M2 is reported as a **single-task contingency** (paired noskill
vs skill on B-1), explicitly NOT a cluster-bootstrap CI (a 1-task bootstrap is degenerate — §8/D26).
Item 006 builds the full multi-task machinery so adding B-2..B-10 later needs only data, not code.

**To unblock the full M2:** owner provides B-2..B-10 task defs + a candidate MSTR account + B goldens;
then re-run item 007's M1/M2 with the expanded B-domain.
