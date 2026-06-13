# Item 002 — Verify (entry-point smoke, live evidence)

**VERDICT: PASS**  ·  Date 2026-06-13  ·  Branch `feat/agentic-v1-002-experiment-types`

## 1. `eval-lab check-env` — LIVE against the real environment ✅
```
$ PATH=node-22  uv run python -m agent_eval_lab.cli check-env --evaluator-config evaluator.toml
[ok] playwright-cli: 0.1.14
[ok] MSTR health probe: HTTP 204
REAL exit: 0
```
Both §18.10 preflights pass against the live MSTR labs server (real auth → 204) with the real
gitignored `evaluator.toml`. (Surfaced + fixed 3 spec-fidelity bugs: nested `[oracle.b_set]`,
`readback:str`, and self-signed-cert `verify=False`.)

## 2. `freeze-spec` idempotence + verification ✅
```
spec_hash set: True | idempotent: True (freeze(freeze(s)) == freeze(s)) | verify_spec_hash: True
```

## 3. evaluator.toml + pricing load ✅
- `load_evaluator_config(evaluator.toml)` returns a typed `EvaluatorConfig` with nested
  `[oracle.b_set] readback="playwright-cli"`, runner k_valid=5 / safety_cap=200 / max_invalid_rate=0.40.
- `load_pricing(evaluator-only/pricing.json)` loads; `pricing_snapshot_hash` stable; per-condition cost = tokens×price.

## 4. Suite + lint + isolation ✅
- `uv run pytest`: **772 passed**.
- `uv run ruff check src/agent_eval_lab/experiments src/agent_eval_lab/cli.py tests/experiments`: clean.
- No coupling: `grep -r experiments src/agent_eval_lab/records/ src/agent_eval_lab/runners/` → 0 matches.

All §18.3 types present and frozen; hydration hard-fails covered by unit tests (missing / duplicate / SHA-mismatch).
