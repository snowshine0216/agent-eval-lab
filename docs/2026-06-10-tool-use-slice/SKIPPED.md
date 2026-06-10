# SKIPPED — Weeks 1–2 Tool-Use Vertical Slice

No items skipped. This is a single-feature (spec mode, N=1) run.

For reference, the following are **out of scope for this slice** (later weeks in the
design doc — not skipped backlog items, just not part of Weeks 1–2):

- Final-state / composite (`AllOf` / `TrajectorySpec`) verification — Weeks 3–4.
- LLM-as-judge + calibration — Weeks 3–4.
- Execution graders / code-repair — Weeks 5–6.
- `ExperimentSpec`/`ExperimentResult`, bootstrap CIs, Holm correction, Inspect conformance — Weeks 7–8.
- Multi-turn / scripted-user, leakage-safe splits, never-train manifest — Weeks 9–10.
- Dataset generator, contamination checks, `TrajectoryExample` export — Weeks 13–14.
- MLX finetuning + closed-loop re-eval — Weeks 15–16.

The data model is designed (in `items/001-spec.md`) so these later additions do
**not** require reworking the locked types landed in this slice.
