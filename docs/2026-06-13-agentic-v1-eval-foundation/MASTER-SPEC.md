# MASTER-SPEC — agentic_v1 use-case eval foundation

**Source spec:** [docs/superpowers/specs/2026-06-12-use-case-agentic-eval-design.md](../superpowers/specs/2026-06-12-use-case-agentic-eval-design.md)
**Goal (user):** *"get the final report for all the model eval results specified."*
**Approach:** Option 1 — build the full code foundation with TDD in shippable PRs, wire each
live arm as its dependency clears, run the reachable arms, produce a real report that grows
partial → complete. Preflights all PASS (see PREFLIGHT.md).

## IN scope
The §16 work decomposition, dependency-ordered, each a shippable package:

1. **Records + runner revision** (§7/§18.1) — `Trajectory`/`Usage` schema_version 1|2 + `v1_compat`,
   new fields (rounds, cost, wall_time_s, tool_call_counts, safety_cap_bound, env_health, run_uid/
   condition_uid), `stop_reason` += completed_natural|safety_cap|env_unhealthy, censoring runner
   (safety_cap=200), `multi_run` k_valid + validity_fn replacement-trial loop, fc-v3
   `environment_failure` in classify.py, pricing→cost. *Precondition for everything measured.*
2. **Experiment types + pre-registration plumbing** (§18.3/§8) — net-new `experiments/` types
   (Domain, MetricDef, ExperimentSpec, ExperimentResult, ExperimentRunRef/Record,
   MultiplicityFamily, PlannedComparison, ConditionDef, DomainWeight); `evaluator.toml` loader;
   `eval-lab freeze-spec` (spec_hash); `eval-lab check-env`.
3. **F3 oracle** (§18.6, §4.1) — AllOf over ExecutionSpec; ≥3 fixtures generated from the staged
   golden test; contradiction checks (2XX excluded, 503 retained); causal-signal tests unchanged.
4. **Repo task adapter + F1/F2** (§4.1) — isolated candidate workspace at base SHA `5b0c13a6`;
   wdio edge runner; F1/F2 owner-golden behavior oracles.
5. **D-set harness** (§4.2/§18.10) — playwright-cli single-bash-tool agent; browse live CMC docs;
   L1–L3 required + forbidden fact-key grading + faithfulness gate; answers stay evaluator-only.
6. **B-set harness** (§4.3/§18.7/§18.9) — per-run isolation (run_uid folder/name), MSTR
   playwright-cli readback oracle under evaluator creds, stripped knowledge-only strategy-test fork.
7. **M1/M2 reports + RUN** (§8) — per-domain (F binomial/exact, D/B cluster bootstrap) + macro
   composite, Pareto, validity mask, fc-v3 taxonomy; freeze spec; **run M1 across reachable
   models/domains; emit the final report.**

## OUT of scope (spec §12 + environment)
- Synthetic substrates; headline unconditional pass^k on live cases; E3/any ablation;
  standing up an Intelligence Server; judge calibration (deterministic floor only); live-web mode.

## BLOCKED / PARTIAL (see SKIPPED.md)
- **gpt-5.5** — ToS/region blocked; dropped from the M1 roster.
- **Full M2 (≥10 B tasks)** — needs owner-authored B-2..B-10 + a least-priv candidate MSTR
  account. B-domain runs B-1 only; M2 reported as a contingency/partial, never a degenerate CI.
