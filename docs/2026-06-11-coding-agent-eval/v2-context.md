The same four conditions were baselined on the workspace worlds in Weeks 1-4
(committed reports: docs/2026-06-10-dataset-grader-quality/).

- `workspace_tool_use_v1` (20 tasks, 3 tools) saturated: hosted conditions at
  pass^3 = 1.000 - it separated models on cost and latency only.
- `workspace_tool_use_v2` (50 tasks, k=3, the same bootstrap conventions):

| condition | pass@1 | pass^3 [95% CI] |
| --- | --- | --- |
| C1 deepseek:deepseek-v4-pro | 1.000 | 1.000 [1.000, 1.000] |
| C2 glm:Pro/zai-org/GLM-5.1 | 1.000 | 1.000 [1.000, 1.000] |
| C3 minimax:MiniMax-M3 | 0.980 | 0.940 [0.860, 1.000] |
| C4 local:Qwen/Qwen3-8B | 0.620 | 0.620 [0.480, 0.740] |

v2 discriminativeness verdict: weak rung (hosted separation within noise at
n=50); the local condition separated decisively, with T3 its hardest tier
(pass^3 0.318).
