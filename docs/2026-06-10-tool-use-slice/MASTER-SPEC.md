# MASTER-SPEC — Weeks 1–2 Tool-Use Vertical Slice

- **Mode:** spec (single feature, N=1)
- **Source:** [docs/superpowers/specs/2026-06-09-agent-eval-pipeline-design.md](../superpowers/specs/2026-06-09-agent-eval-pipeline-design.md) §16, §11 (Wk 1–2 row), §3–§6, §12
- **Date:** 2026-06-10
- **Run dir:** `docs/2026-06-10-tool-use-slice/`

## Scope classification

| # | Item | Scope | Rationale |
|---|------|-------|-----------|
| 001 | Weeks 1–2 tool-use vertical slice (locked `VerificationSpec` subset + task schema, synthetic `workspace-world` with schema-validated tools, ~20 tool-use tasks, AST tool-call grader + failure taxonomy, OpenAI-compatible provider client, multi-run runner with limits + cost capture, initial golden conformance suite, baseline report) | **IN** | The one part of the design that needs an implementation plan now (§16). Delivered as a single vertical-slice PR per the project owner's decision. |

No OUT items — this is a single-feature spec run. Everything beyond the Weeks 1–2 slice (final-state/composite verification, LLM-judge, execution graders, experiments, multi-turn, dataset engineering, finetuning) is explicitly **later weeks** in the design doc and is not in this run's scope. See [SKIPPED.md](SKIPPED.md).

## The deliverable, restated

A minimum, reproducible evaluation system for **tool use & function-calling** that:
1. defines the **locked, immutable data spine** (frozen dataclasses → JSONL) for the subset of `VerificationSpec` needed for tool-use grading;
2. runs models against a **deterministic synthetic tool-world** through a pure model↔tool loop with explicit state;
3. grades tool calls with a **schema-first AST grader** that emits a **structured failure taxonomy** (never silently repairs bad args);
4. captures **multiple runs per task from day one** with cost/latency, so reliability (`pass^k`) is computable later without retrofitting;
5. proves the grader against a **hand-verified golden conformance suite**;
6. produces a **baseline report** from recorded/deterministic trajectories.

Full acceptance criteria and the locked type subset live in [items/001-spec.md](items/001-spec.md).
