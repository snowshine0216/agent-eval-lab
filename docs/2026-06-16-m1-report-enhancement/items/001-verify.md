Verdict: PASS

Subagent: sonnet
Source: /verify (direct entry-point: report-m1 CLI on real F/D data)
Entry point exercised: uv run python -m agent_eval_lab.cli report-m1 --spec $SPEC --runs "F:deepseek:deepseek-v4-pro=..." (5 F conditions, 2 D conditions) --prices $PRICES --out reports/agentic-v1/M1-final-report.md

Observed behavior:
  - Exit code 0, no traceback — observed: EXIT_CODE=0, stdout emitted 3 file paths only, no exception
  - M1-F-report.md and M1-D-report.md written — observed: both present at 15598 and 16244 bytes; M1-B-report.md absent (correct, no B runs)
  - Overview contains `## Efficiency & cost` — observed: line 40
  - Overview contains `## Subreports` linking M1-F-report.md + M1-D-report.md + hand companions — observed: lines 173-178 with all 4 links
  - Overview contains `## Per-domain headlines` with `best pass^k` — observed: line 21; lines "best pass^k: `siliconflow:Qwen/Qwen3.6-35B-A3B` (0.333)" and "best pass^k: `deepseek:deepseek-v4-pro` (0.000)"
  - Overview contains `## Failure classification (fc-v4) per condition` — observed: line 125
  - Overview does NOT contain `Failure taxonomy` — observed: grep returned no match (PASS)
  - F subreport contains `# M1 subreport — F` — observed: line 1
  - F subreport contains `## Task quick-reference` — observed: line 6
  - F subreport contains `## Cross-model summary` — observed: line 14
  - F subreport contains `## Per-task detail` — observed: line 22
  - F subreport contains `## Task-defect candidates` — observed: line 230
  - F subreport contains `## Per-condition efficiency` — observed: line 239
  - F subreport contains `## Failure classification (fc-v4) per task × condition` — observed: line 249
  - D subreport contains all 7 §6 sections — observed: lines 1, 6, 26, 46, 468, 485, 492 respectively
  - Per-trial ✅❌ matrix renders in F cross-model summary — observed: "f-f3 | 2/5 ✅❌❌❌✅ | — admin (not executed) | ..."
  - Grader-aware gap renders in F per-task detail — observed: "grader gap: passed 1/5 oracle tests; failing: `test::TC99396_10 waits on the named terminal snapshot notification`, ..."
  - D subreport missing/forbidden facts — observed: D failures driven by llm_judge sub-grader; fact_key sub-evidence has empty missing_required/present_forbidden (verified in raw JSONL); renderer correctly shows "grader gap: failed" for llm_judge-failed records; D missing/forbidden fact rendering path is covered by design, no actual missing/forbidden facts present in this dataset's failed records
  - Task-defect candidates render in F — observed: f-f1, f-f2 with shared failing oracle units; f-f3 excluded (glm admin-blocked, not unanimous)
  - Administrative cell never renders as real 0/k failure — observed: glm:Pro/zai-org/GLM-5.1 on f-f3 renders as "administrative 0/5 — not executed (owner decision)" and cross-model summary shows "— admin (not executed)"; grep for "admin" in F report found only these 2 correct lines

Determinism: byte-identical — `diff -r reports/agentic-v1/ reports/agentic-v1-2/` produced no output (empty diff = PASS)

Failures: none
