Verdict: PASS

Subagent: sonnet
Items reviewed: 4
Re-run date: 2026-06-11

---

## Prior verdict (FAIL) summary

The initial run (2026-06-10) found all documentation targets verified except
README.md, which was missing:

1. The three new CLI subcommands — `calibrate export-packet`, `calibrate
   provisional-label`, `calibrate compute`, `report-validation`,
   `compare-configs`.
2. The `--system-prompt-file` flag on `run-baseline`.
3. A Status section still reading "Weeks 1–2 tool-use slice implemented"
   without reflecting Weeks 3–4 completion.

All other verified-coverage items (CONTEXT.md, ADRs 0001–0007, CHANGELOG.md,
run artifacts) passed the initial gate and were not re-examined in depth.

---

## Remediation commit

Commit `7be4934` (2026-06-11):

    docs: README — document Weeks 3-4 CLI surface (report-validation,
    compare-configs, calibrate, --system-prompt-file) and update status

`git show HEAD --stat` confirms the commit touched **README.md only**
(1 file changed, 43 insertions, 4 deletions). CONTEXT.md and docs/adr/ were
not modified, preserving the doc-sync lock's intent.

---

## Verification evidence — four previously-missing items

All four items are now covered in README.md `### Additional subcommands`
(line 122) and `## Status` (line 221).

### 1. `--system-prompt-file` flag on `run-baseline`

README (lines 124–128) documents the flag, its `<path>` argument, the
alternate-agent-configuration purpose, and the tagged-artifact naming
(`runs-<condition>__<tag>.jsonl`).

Argparse verification (`cli.py` line 436–441):
```
baseline.add_argument(
    "--system-prompt-file",
    type=Path,
    help="override each task's system turn ...",
)
```
Name, type, and purpose match exactly.

### 2. `report-validation` subcommand

README (lines 133–138) shows the full invocation with flags `--runs`,
`--dataset`, `--tiers`, `--k`, `--expected-n-tasks`, `--seed`,
`--n-resamples`, `--out`.

Argparse verification (`cli.py` lines 474–486): all eight flags are defined
on the `report-validation` parser with matching names and types.

`--runs` uses `nargs="+"` and the README example passes a single positional
value — correct.

### 3. `compare-configs` subcommand

README (lines 142–147) shows flags `--config-a`, `--config-b`, `--tiers`,
`--planning-prompt-file`, `--k`, `--seed`, `--n-resamples`, `--out`.

Argparse verification (`cli.py` lines 492–500): all eight flags are defined
with matching names. One note: README omits `--alpha` (optional, has default
0.05) — not a documentation gap; optional-with-default flags are legitimately
omitted from usage examples.

### 4. `calibrate` subcommand group

README (lines 151–153) shows all three subcommands:
- `calibrate export-packet --out packet.jsonl`
- `calibrate provisional-label ...`
- `calibrate compute ...`

Argparse verification (`cli.py` lines 443–444, 370–376): `calibrate` is a
top-level subparser with a required nested `calibrate_command` subparser
dispatching `export-packet`, `provisional-label`, `compute`. Names match.

### 5. Status section

README lines 223–233 now read "Weeks 1–4 are implemented," covering: Weeks
1–2 tool-use slice, and Weeks 3–4 composite verification, 50-task dataset,
calibrated LLM judge, per-task step budgets, and live multi-condition
validation and comparison reports. Resolves the stale-status gap.

---

## Spot-checks on prior verified-coverage list

- **CONTEXT.md** — grep for `condition_id`, `prompt-config tag`, `VerificationSpec`,
  `AllOf` returns 21 matches. Coverage intact.
- **CHANGELOG.md** — grep for `calibrate`, `report-validation`, `compare-configs`,
  `system-prompt-file` returns 3 matches. Coverage intact.

---

## Full verified-coverage list

- README.md `### Additional subcommands` + `## Status`: all four missing items
  now covered (this re-run).
- CONTEXT.md (342 lines): all item-grill terms present for items 001–004.
    - Item 001 (ADRs 0001–0003): VerificationSpec union, Constraint,
      Outcome/Policy verification, Path-independence, final_state,
      FailureCategory, forbidden_action, step_limit_exceeded, AllOf.
    - Item 002 (ADR 0004): Distractor tool, Difficulty knob, Tier,
      State-dependent chain, provenance, version (dataset),
      world_template_id, max_steps (task hint), review (task).
    - Item 003 (ADRs 0005–0006): Judge rubric, Summary fidelity,
      JudgeVerdict, prompt hash, Annotation packet, Cohen's κ (headline
      binary), Provisional calibration.
    - Item 004 (ADR 0007): condition_id, prompt-config tag.
- docs/adr/0001-final-state-recorded-on-trajectory.md (item 001)
- docs/adr/0002-only-modifies-prefix-coverage.md (item 001)
- docs/adr/0003-allof-evaluates-all-subspecs.md (item 001)
- docs/adr/0004-per-task-max-steps-is-data-runner-wiring-deferred.md (item 002)
- docs/adr/0005-judge-verdicts-precomputed-at-edge-threaded-into-pure-grader.md (item 003)
- docs/adr/0006-binary-cohens-kappa-is-the-headline-judge-reliability-statistic.md (item 003)
- docs/adr/0007-prompt-config-tag-extends-run-artifact-naming.md (item 004)
- CHANGELOG.md Weeks 3–4 section: covers all four items including new CLI
  subcommands, Trajectory.final_state, TaskMetadata.max_steps/review,
  composite graders, LlmJudgeSpec, calibration harness, workspace-world v2,
  workspace_tool_use_v2, dataset conformance suite.
- docs/2026-06-10-dataset-grader-quality/taxonomy.md (committed run artifact)
- docs/2026-06-10-dataset-grader-quality/rubric.md (committed run artifact)
- docs/2026-06-10-dataset-grader-quality/review-ledger.md (committed run artifact)
- docs/2026-06-10-dataset-grader-quality/calibration-runbook.md (committed run artifact)
- docs/2026-06-10-dataset-grader-quality/calibration-provisional-summary.md (committed run artifact)
- docs/2026-06-10-dataset-grader-quality/validation-report.md (committed run artifact)
- docs/2026-06-10-dataset-grader-quality/comparison-report.md (committed run artifact)
