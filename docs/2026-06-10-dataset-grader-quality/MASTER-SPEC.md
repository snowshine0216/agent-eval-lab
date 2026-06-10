# MASTER-SPEC — Weeks 3-4: Dataset and Grader Quality

- **Mode:** backlog (≥2 distinct deliverables in the roadmap item)
- **Date:** 2026-06-10
- **Sources:** [docs/ROADMAP.md](../ROADMAP.md) § "Weeks 3-4",
  [design doc](../superpowers/specs/2026-06-09-agent-eval-pipeline-design.md)
  §4.3 (verification union), §5 (workspace-world + difficulty knobs),
  §6 (graders, judge calibration protocol)
- **User directive (this turn, overrides roadmap where stricter):** the new
  tasks MUST be capability-discriminating — hard, long-horizon (many steps),
  reasoning-required — because the v1 run saturated (three hosted frontier
  models at pass^3 = 1.000). After all validation passes, run the live
  evaluation and produce the report for user review.

## Context from Weeks 1-2 (why "harder" matters)

`workspace_tool_use_v1` (20 tasks, 3 tools) separates models only on cost and
latency. The only accuracy signal was local Qwen3-8B over-calling on the two
multi-step tasks. The v2 dataset must draw a capability boundary *between
strong models*, which means deeper multi-step chains, distractor tools,
state-dependent reasoning, constraint compliance, and path-independent
final-state grading.

## IN-scope items

| id | Title | Roadmap deliverable(s) covered |
|----|-------|--------------------------------|
| 001 | Composite verification layer: `FinalStateSpec`, `TrajectorySpec`, `AllOf` — constraint data variants, pure interpreters, grader dispatch, JSONL parsing, final-state threading through runner+trajectory, `forbidden_action`/`step_limit_exceeded` failure categories, golden-conformance extension | "final-state and composite (`AllOf` / `TrajectorySpec`) verification" |
| 002 | Workspace-world v2 + task taxonomy + scoring rubric + 50 reviewed hard tasks (`workspace_tool_use_v2`) — expanded tool surface (≥6 tools incl. distractors), difficulty-knob metadata, taxonomy doc, rubric doc, review checklist per task | "a task taxonomy and scoring rubric; 50 reviewed tasks" + user hardness directive |
| 003 | Model-based grader + calibration harness: `LlmJudgeSpec` scorer (pure prompt build / parse, provider call at edge), annotation packet export + import, Cohen's κ (+ bootstrap CI) and agreement stats, calibration runbook; provisional two-LLM-annotator calibration run clearly labeled provisional | "an initial model-based grader with calibration (Cohen's κ, ≥2 annotators)" — human labels themselves are OUT (see SKIPPED) |
| 004 | Validation + failure-mode report + two-configuration comparison: full harness gates, live runs of v2 across available conditions (k=3), failure-mode report, pre-declared 2-config comparison with estimator + CI treatment (stats focus realized here), report artifacts for user review | "a failure-mode report; a comparison of two agent configurations" + user directive to run the report |

## OUT-of-scope items (see SKIPPED.md)

- Human annotation labels for judge calibration (needs ≥2 human annotators).
- `openrouter:openai/gpt-5.5` as a live validation condition (network ToS
  block — environmental).
- Multi-turn `ScriptedUser` / `ask_user` clarification tasks (Weeks 9-10
  scope per roadmap; ambiguity difficulty-knob deferred with it).

## Acceptance criteria (run level)

1. `VerificationSpec` union extended with `FinalStateSpec | TrajectorySpec |
   AllOf`, parsed from JSONL, graded by pure interpreters, covered by golden
   conformance cases.
2. `examples/datasets/workspace_tool_use_v2.jsonl` has ≥50 tasks, each
   reviewed against the rubric, with taxonomy + difficulty metadata; the set
   is *designed not to saturate* (hard multi-step / reasoning tiers form the
   majority, with documented expected-failure rationale).
3. An `llm-judge` grader exists behind `LlmJudgeSpec`, with a calibration
   command computing Cohen's κ (and CI) from an annotation file; ≥1
   provisional calibration run committed as evidence the pipeline works.
4. A failure-mode report and a 2-config comparison over live runs of v2
   exist under `reports/` for user review, and all harness gates
   (pytest, ruff check, ruff format) are green.
