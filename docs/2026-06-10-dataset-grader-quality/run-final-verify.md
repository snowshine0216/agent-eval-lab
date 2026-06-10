Verdict: PASS

Subagent: sonnet
Source: autodev/dataset-grader-quality-feature (14 commits ahead of main; 131 files, 22 879 insertions)
Entry point exercised: `uv run python -m agent_eval_lab.cli`

## Cross-item flow observed

### Step 1 — CLI surface (all 4 subcommands present)
`uv run python -m agent_eval_lab.cli --help` → positional commands listed:
`run-baseline`, `calibrate`, `report-validation`, `compare-configs`. All 4 present.

### Step 2 — Cross-item E2E flow (load-bearing)

**Task slice:** ws2-040 from `workspace_tool_use_v2.jsonl` — verification type `all_of` (AllOf[FinalStateSpec + TrajectorySpec], item 001 grader), tier T4/distractor_resistance.

**run-baseline (item 002 dataset + item 001 grader):**
```
uv run python -m agent_eval_lab.cli run-baseline \
  --dataset /tmp/ws2-040-slice.jsonl \
  --provider local --model Qwen/Qwen3-8B --k 1 --out /tmp/rv
```
Output: `/tmp/rv/runs-local-Qwen-Qwen3-8B.jsonl` + `/tmp/rv/baseline-local-Qwen-Qwen3-8B.md`

JSONL record confirmed: `grader_id: "all_of"` with two `sub_results` entries
(`grader_id: "final_state"` and `grader_id: "trajectory"`). AllOf grader fired,
both sub-graders evaluated, final_state failed (emails map empty), trajectory
failed (no tool calls — model emitted a parse_failure). Grade propagated correctly.

**report-validation (item 004):**
```
uv run python -m agent_eval_lab.cli report-validation \
  --runs "Qwen3-8B=local:Qwen/Qwen3-8B=/tmp/rv/runs-local-Qwen-Qwen3-8B.jsonl" \
  --dataset /tmp/ws2-040-slice.jsonl \
  --tiers .../workspace_tool_use_v2_tiers.json \
  --k 1 --expected-n-tasks 1 --out /tmp/rv-report
```
Rendered report includes: per-condition reliability table, per-tier accuracy curve,
failure taxonomy (unclassified × T4 × distractor_resistance), deterministic-vs-flaky
split, budget-floor assertion table, exemplar trace excerpt (tool-call sequence:
"(no tool calls)"), per-task pass matrix, discriminativeness verdict. Full section
structure intact.

### Step 3 — Calibration surface (item 003)
`calibrate export-packet --fixtures examples/calibration/fixtures.jsonl --rubric examples/calibration/rubric.md --out /tmp/calibration-packet.md`
→ 221-line blind packet with 20 items (cf-01 through cf-20), rubric header, score
blanks. 20-item count matches spec.

### Step 4 — Full gates
- pytest: `363 passed in 3.48s` — all green, matches expected count.
- ruff check: `All checks passed!`
- ruff format --check: `85 files already formatted`

### Step 5 — Byte-identical regeneration (validation report)
Ran canonical 4-condition report-validation command (seed=20260610, n-resamples=2000)
→ `/tmp/re-validation.md`. `diff` against committed `validation-report.md` → empty.
`BYTE_IDENTICAL` confirmed.

## Failures: none
