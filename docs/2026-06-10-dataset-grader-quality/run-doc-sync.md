Verdict: FAIL

Subagent: sonnet
Items reviewed: 4

Doc changes verified:
  - CONTEXT.md (new file, 342 lines): all item-grill terms present
      - Item 001 (ADRs 0001-0003): VerificationSpec union, Constraint, Outcome/Policy verification,
        Path-independence, final_state, FailureCategory, forbidden_action, step_limit_exceeded, AllOf
      - Item 002 (ADR 0004): Distractor tool, Difficulty knob, Tier, State-dependent chain,
        provenance, version (dataset), world_template_id, max_steps (task hint), review (task)
      - Item 003 (ADRs 0005-0006): Judge rubric, Summary fidelity, JudgeVerdict, prompt hash,
        Annotation packet, Cohen's κ (headline binary), Provisional calibration
      - Item 004 (ADR 0007): condition_id, prompt-config tag
  - docs/adr/0001-final-state-recorded-on-trajectory.md (new, item 001)
  - docs/adr/0002-only-modifies-prefix-coverage.md (new, item 001)
  - docs/adr/0003-allof-evaluates-all-subspecs.md (new, item 001)
  - docs/adr/0004-per-task-max-steps-is-data-runner-wiring-deferred.md (new, item 002)
  - docs/adr/0005-judge-verdicts-precomputed-at-edge-threaded-into-pure-grader.md (new, item 003)
  - docs/adr/0006-binary-cohens-kappa-is-the-headline-judge-reliability-statistic.md (new, item 003)
  - docs/adr/0007-prompt-config-tag-extends-run-artifact-naming.md (new, item 004)
  - CHANGELOG.md (Weeks 3-4 section added): covers all four items including new CLI subcommands
    calibrate, report-validation, compare-configs, --system-prompt-file, Trajectory.final_state,
    TaskMetadata.max_steps/review, composite graders, LlmJudgeSpec, calibration harness,
    workspace-world v2, workspace_tool_use_v2, dataset conformance suite
  - docs/2026-06-10-dataset-grader-quality/taxonomy.md (committed run artifact)
  - docs/2026-06-10-dataset-grader-quality/rubric.md (committed run artifact)
  - docs/2026-06-10-dataset-grader-quality/review-ledger.md (committed run artifact)
  - docs/2026-06-10-dataset-grader-quality/calibration-runbook.md (committed run artifact)
  - docs/2026-06-10-dataset-grader-quality/calibration-provisional-summary.md (committed run artifact)
  - docs/2026-06-10-dataset-grader-quality/validation-report.md (committed run artifact)
  - docs/2026-06-10-dataset-grader-quality/comparison-report.md (committed run artifact)

Missing coverage:
  - README.md does not document the three new CLI subcommands (calibrate,
    report-validation, compare-configs) or the new --system-prompt-file flag
    added to run-baseline. The README CLI section shows only `run-baseline`
    and does not mention the nested calibrate subgroup (export-packet /
    provisional-label / compute). The Status section still reads "Weeks 1–2
    tool-use slice implemented" — it has not been updated to reflect Weeks 3-4.

Manual fix path:
  README.md — CLI surface section (after the Local model section, before
  ## Repository Layout): add a "### Additional subcommands" subsection
  documenting:
    - calibrate export-packet / provisional-label / compute (judge calibration harness)
    - report-validation (regenerate failure-mode report from JSONL)
    - compare-configs (regenerate two-config comparison from JSONL)
    - --system-prompt-file flag on run-baseline (prompt-config tag, artifact naming)
  README.md — Status section: update from "Weeks 1–2" to reflect Weeks 3-4
  completion (composite graders, workspace-world v2, LLM-judge + calibration,
  failure-mode report, two-config comparison).
