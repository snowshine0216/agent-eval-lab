# MASTER-SPEC — Weeks 5-6: Coding Agent Evaluation

Mode: **backlog** (4 distinct deliverables from `docs/ROADMAP.md` → "Weeks 5-6: Coding Agent Evaluation")
Source: `docs/ROADMAP.md` lines 136-149, plus user-stated exit gate: **final evaluation report presentation**.
Date: 2026-06-11

## Intent

Extend the existing agent-eval harness (deterministic workspace-world, tiered graders,
multi-run runner) with a **coding-agent evaluation slice**: agents repair small broken
programs inside an isolated code-world; grading is execution-based (the task's test
suite is the oracle, run in a reproducible sandbox); failures are explicitly classified
as task defects, agent limitations, or harness defects; the run exits with a final
evaluation report presented to the user.

This is tier-2 grading per `docs/ARCHITECTURE.md` ("Execution (objective): run tests in
an isolated environment; tests are the oracle") — between the existing deterministic
tier (AST/state/policy) and the LLM-judge tier.

## Item classification

| id | Item (from roadmap) | Scope | Rationale |
|----|--------------------|-------|-----------|
| 001 | **Isolated, reproducible task environments** — code-world: file-tree state, code-editing tools for the agent (read/write/list/run-tests), and a sandboxed execution edge (subprocess pytest in a temp dir with timeout, no network, deterministic env) | **IN** | Foundation for everything else; pure-core state + effectful execution edge matches the existing architecture |
| 002 | **Execution-based graders (tests as the oracle)** — new `VerificationSpec` variant + grader that materializes the final file-tree state and runs the task's held-out test suite; verdict from test results; golden conformance cases | **IN** | Depends on 001's execution edge; pure interpreter + edge-threaded results, same pattern as `LlmJudgeSpec` (ADR-0005) |
| 003 | **10-20 small code-repair tasks** — reviewed dataset (`code_repair_v1`) of small broken Python programs with held-out oracle tests, taxonomy/tier tags, anti-rote conformance suite in CI | **IN** | Depends on 001 (world/tools) + 002 (verification); follows the v2 dataset quality bar from Weeks 3-4 |
| 004 | **Failure classification + final evaluation report** — explicit task/agent/harness failure classification applied to live baseline runs over `code_repair_v1`; report command; final evaluation report presented to the user (**exit gate**) | **IN** | Depends on 003; the classification taxonomy + live runs + presentation close the slice |

No OUT items — all four roadmap deliverables are actionable without human input,
credentials beyond the already-configured provider keys, or SME involvement.

## Cross-cutting constraints (engineering focus, not items)

- **Test-driven development** — red-green-refactor per CLAUDE.md; every item lands with tests written first.
- **Boundary and integration testing** — the subprocess-execution edge gets integration tests; pure core gets unit + property tests.
- **Reproducibility** — same task + same final file tree ⇒ byte-identical grader verdict; sandbox is hermetic (temp dir, pinned interpreter, no network, fixed env vars, seeded everything).
- Functional core / imperative shell: all subprocess and filesystem I/O stays at the edges; graders remain pure interpreters over data (verdicts threaded in, per ADR-0005 precedent).
- Live runs use the existing provider registry; `openrouter:gpt-5.5` remains unreachable from this network (known ToS block) and is not a target condition.

## Exit gate (user-stated)

The run is complete only when a **final evaluation report** over the code-repair slice
(live baseline runs, execution-grader verdicts, failure classification, known
limitations) is produced and **presented** to the user in the close-out.
