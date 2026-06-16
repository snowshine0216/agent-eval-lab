# MASTER-SPEC — M1 report enhancement (overview + per-domain subreports)

- **Mode:** `spec` (single feature; design doc with Goals / Decisions / Architecture / Testing, no numbered execution steps). N = 1.
- **Source spec:** [docs/superpowers/specs/2026-06-15-m1-report-enhancement-design.md](../superpowers/specs/2026-06-15-m1-report-enhancement-design.md) (copied verbatim to `items/001-spec.md`).
- **Run invoked:** 2026-06-16 via `/autodev <spec> + "regenerate F-set and D-set report for review"`.

## Scope classification

| # | Item | Class | Rationale |
|---|------|-------|-----------|
| 001 | Enrich the auto-generated M1 report: thin cross-domain overview + efficiency/cost rollup in `M1-final-report.md`, plus a new deterministic per-domain subreport `M1-<domain>-report.md` reaching the depth of the hand-written F analysis. Report-layer only — new pure modules (`evidence_summary.py`, `edit_paths.py`, `defects.py` extract, `m1_detail.py`), CLI wiring (`--subreports`), and the `Failure taxonomy → Failure classification (fc-v4)` heading rename. TDD throughout. | **IN** | Self-contained, report-layer-only change against an existing deterministic harness; fully specified with feasibility verified in the source spec (§3). No runner / scoring / model re-run. |

No OUT-scope items (single-feature spec). `SKIPPED.md` is empty.

## Explicitly out of scope (per source spec §11 — not autodev work-items, just non-goals carried forward)

- Re-running any model; changing `grade.passed`, pass^k, CI, or comparison math.
- Authoring root-cause prose (stays in hand companions `M1-F-failure-analysis.md` / `M1-F-report-NOTES.md`).
- The B-domain grader adapter (added as one `evidence_gap` branch when B runs exist).
- HTML / charts (markdown only).
- `validation.py`'s parallel "Failure taxonomy" mislabel — spun out to a separate follow-up per source spec §7.

## Post-implementation deliverable (user request this turn)

After 001 merges, **regenerate the M1 report for the F-set and D-set** (run `report-m1` against the local run JSONL in `reports/agentic-v1/`) and surface the regenerated overview + `M1-F-report.md` + `M1-D-report.md` for the user to review. This is a presentation step, not a code work-item — handled in Phase 3 close-out using the merged code.
