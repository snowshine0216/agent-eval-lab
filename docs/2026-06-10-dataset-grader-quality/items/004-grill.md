Verdict: PASS

Subagent: opus
Questions resolved: 11 (Q1–Q11; Q4/Q10-scope confirmed no-ADR; Q1–Q3/Q5–Q9
sharpened the spec; Q11 produced one ADR)

## Docs touched (blob SHAs)

| File | Blob SHA | Change |
|------|----------|--------|
| `CONTEXT.md` | `21470fc` | +2 runner/artifact terms (**condition_id**, **prompt-config tag**) |
| `docs/adr/0007-prompt-config-tag-extends-run-artifact-naming.md` | `5d30656` | new ADR (Q11) |
| `docs/2026-06-10-dataset-grader-quality/items/004-spec.md` | `5ecb7fa` | refined in place (below) |
| `docs/2026-06-10-dataset-grader-quality/items/004-grill.md` | self | this file |

## Spec refined

Inline strike-through corrections (nothing deleted) + `## Resolved decisions`
appended:
- **Primary metric** — struck "pass^3 on the paired 50 tasks" → **T3+T4 Δ pass^3**
  (Q3); added the enforced pairing precondition + no-degeneracy note (Q1/Q2).
- **Configuration B** — added the planning-prompt **sha256 hash-pin** reusing the
  `graders/judge.prompt_hash` precedent (Q5).
- **Held fixed** — struck bare "temperature=0.0" → "**0.0 *requested***"; added the
  temperature/seed-honesty note and the shared-`condition_id` / path-as-identity
  note (Q10, Q11).
- **Run order** — corrected the "up-to-6-step / 8–10" prose (ceiling is **6 loop
  iterations**) and added partial-condition (`incomplete`) recovery (Q8).
- **AC 2** — corrected the starvation signature: `stop_reason="max_steps"` is *not*
  a `FailureCategory`; a starved chain is a `FinalStateSpec` outcome miss
  (`failure_reason=None`), not `step_limit_exceeded` (Q6).
- **AC 4** — added the paired-universe raise + no-degeneracy assertions (Q1/Q2).
- **AC 5 / AC 10** — `incomplete ≠ blocked ≠ fabricated` three-way split (Q8).
- **AC 7** — verdict keyed to the **T3+T4** Δ CI (consistent with Q3).
- **AC 11** (new) — two-config artifacts never collide; v1 naming preserved (Q11).
- **Discriminativeness verdict** — two mechanical rungs (strong: paired-CI-excludes-0
  and/or per-tier monotone; weak: differs-and-sub-1.000) (Q9).
- **Non-goals** — sharpened: one CI read ⇒ no family-wise error; the prompt-hash is
  the poor-man's `spec_hash` (Q10-scope).

## Resolved decisions (Q / A / Rationale / Doc impact)

**Q1 — Is the pairing pinned (resample *tasks*; both configs move together)?**
- A: Pin it as an **enforced precondition** — `paired_pass_pow_k_diff_ci` requires
  an identical task-id universe across `results_a`/`results_b` and **raises on
  mismatch**; one task-id multiset per iteration is applied to both configs.
- Rationale: design §4.6 is binding ("same paired tasks"); narrated pairing is not
  enforced pairing. A blocked/short condition must never silently half-pair.
- Doc impact: spec Primary-metric block, estimator bullet, AC 4.

**Q2 — Degenerate-resample policy vs `agreement.py` D7.**
- A: **No degeneracy class for pass^k** — all-pass/all-fail resamples are
  legitimate 1.0/0.0. Reuse the `BootstrapCI` *shape* but `n_degenerate ≡ 0` (not
  copied from the κ path). Test asserts both extremes give finite CIs.
- Rationale: copying D7 verbatim would imply a degeneracy that does not exist for
  this estimand — a domain-fidelity bug. Reuse shape, not meaning.
- Doc impact: spec Primary-metric block, estimator bullet, AC 4.

**Q3 — Primary-metric scope contradiction.**
- A: Primary = **T3+T4 Δ pass^3** (where the directional hypothesis lives);
  overall-50 Δ is secondary/descriptive. Verdict reads the declared-primary CI.
- Rationale: hypothesis is "planning helps on hard tiers; T1+T2 indistinguishable".
  Reading the verdict off an unnamed-as-primary CI is estimand slippage.
- Doc impact: spec Primary-metric block; AC 7 already keyed to T3+T4.

**Q4 — Seeding.** Bootstrap seed `20260610` (matches `calibrate`/`agreement.py`),
explicit arg, same seed ⇒ byte-identical CI. No ADR (established precedent).

**Q5 — Planning prompt is a measured artifact; pin it.**
- A: Commit the fixture **and** record its sha256-over-canonical-bytes in the
  comparison header, reusing `graders/judge.prompt_hash` + `graders/canonical` (the
  CONTEXT.md *prompt hash* term). A has no single prompt → record "per-task author
  prompt (no override)"; pin **B's** hash.
- Rationale: a comparison whose only varying input is a prompt is unreproducible
  unless that prompt is content-pinned; the machinery already exists.
- Doc impact: spec Configuration-B block.

**Q6 — `max_steps` loop semantics at exhaustion; does wiring change v1?**
- A: `stop_reason="max_steps"` is **not** a `FailureCategory`; `step_limit_exceeded`
  comes only from a `MaxToolCalls` breach (`graders/policy.py`). A starved chain is
  a `FinalStateSpec` outcome miss (`failure_reason=None`). v1 unchanged — all 20 v1
  tasks carry no `max_steps`. Declared v2 ceiling is **6** (= today's default), so
  wiring's live effect is mainly to stop *over*-budgeting the 20 `max_steps:4`
  tasks (preserving `extra_call` signal).
- Rationale: the original AC 2 conflated the loop's stop_reason with the grader's
  policy category — different layers.
- Doc impact: spec AC 2, Run-order block.

**Q7 — Temperature/seed honesty.**
- A: `client.py` **does** send `temperature` (default 0.0) — honest — but sends
  **no seed**, and providers are not greedy-deterministic at temp 0. Report states
  temp=0.0 *requested*; residual variation is what k=3/pass^3 measures; no
  bit-exact-determinism claim.
- Rationale: record what is actually sent; the only seeded knob is the bootstrap.
- Doc impact: spec Held-fixed block.

**Q8 — Local Qwen wall-clock + partial conditions.**
- A: Streaming leaves a *partial* JSONL on interrupt; builders mark it `incomplete`
  with the actual tally and grade only over present records — never block, never
  invent. Zero-record = `blocked`. Corrected the overstated step prose (ceiling 6).
- Rationale: honor the streaming-survival property (commit 7a651bc);
  `incomplete ≠ blocked ≠ fabricated`.
- Doc impact: spec Run-order block, AC 5, AC 10.

**Q9 — Discriminativeness verdict: mechanical, not vibes.**
- A: Two computed rungs. **Strong** (claims "v2 discriminates"): ≥1 hosted pair
  separated by a pass^3 gap whose **paired CI excludes 0**, and/or per-tier
  **monotone non-increasing** for ≥1 hosted condition. **Weak** (necessary only):
  hosted pass^3 differ on ≥1 task *and* ≥1 hosted pass^3 < 1.000.
- Rationale: "did v2 separate the models" must be a computation; reuses the paired
  estimator and the same n=50 honesty.
- Doc impact: spec failure-mode-report discriminativeness bullet.

**Q10 / scope — single contrast ⇒ no multiple-testing.**
- A: Verdict reads exactly **one** pre-declared CI (T3+T4 Δ) ⇒ no family, no
  family-wise error; discriminativeness rungs are descriptive. The prompt-fixture
  sha256 is the poor-man's `spec_hash`. No ADR (restatement of scope).
- Doc impact: spec Non-goals (sharpened).

**Q11 — Condition-naming collision: two same-model configs overwrite each other.**
- A: `condition_id` is `provider:model` and is stamped *inside* every `RunResult`,
  so `default`/`planning` runs of `deepseek:deepseek-v4-pro` collide on filename
  **and** in-record id — the cross-model-overwrite bug class already fixed in
  c744b5f. **Extend the artifact slug with an optional prompt-config tag**
  (`…__default.jsonl` / `…__planning.jsonl`), empty by default (v1 filename + the
  existing distinctness guard byte-for-byte unchanged); `compare-configs`
  identifies configs by **source path, labeled by role**, not the shared
  `condition_id`. The frozen `RunResult` schema is **not** mutated.
- Rationale: ADR-worthy (three-of-three) — hard to reverse once artifacts/tooling
  parse the names; surprising (a reader expects `condition_id` to be run identity);
  real trade-off (filename-tag vs record-schema-change vs synthetic-id). Filename
  tag keeps the frozen record schema and the v1 artifact contract intact.
- Doc impact: **ADR-0007**; spec Run-order/Held-fixed/CLI-surface blocks, AC 11;
  CONTEXT.md adds **condition_id** + **prompt-config tag**.
