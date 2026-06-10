# Item 003 — Model-based grader (`LlmJudgeSpec`) + calibration harness

- **Run:** `docs/2026-06-10-dataset-grader-quality`
- **Date:** 2026-06-10
- **Realizes:** design doc §4.3 (`LlmJudgeSpec` shape: `rubric`, `judge_model`,
  `scale=(1,5)` — the missing member of the `VerificationSpec` union), §6 Tier 3
  (LLM-as-judge: last resort, irreducibly subjective residue only), **§6.5 the
  six-step calibration protocol (BINDING)**, §3 (the one OpenAI-compatible client
  reused for judge calls), §4.6 (bootstrap CIs as the stats idiom).
- **Depends on (already merged):** item 001 — the pure dispatch
  (`graders/dispatch.py:grade_trajectory`), `AllOf` composite recursion
  (`graders/composite.py`), the `GradeResult{evidence, failure_reason}` record,
  `final_state` threading (the precedent for "edge pre-computes, pure grader reads"),
  and JSONL verification parsing (`tasks/parse.py:verification_from_dict`). Item 002 —
  the v2 world/tools and the `workspace_tool_use_v2.jsonl` set (consumed as a *source*
  of realistic trajectories to sample for the calibration fixtures; **not modified**).
- **Extends (current checkout):**
  - `tasks/schema.py` — add `LlmJudgeSpec` to the `VerificationSpec` union (additive).
  - `tasks/parse.py` — parse `type:"llm_judge"`.
  - `graders/judge.py` (**new, pure**) — `build_judge_prompt`, `parse_judge_response`,
    `JudgeVerdict`, `grade_llm_judge` (reads a *pre-computed* verdict; never calls out).
  - `graders/dispatch.py` — dispatch `LlmJudgeSpec` and thread a verdict map through
    `grade_trajectory` and `grade_all_of` (so a judge leg can sit inside `AllOf`).
  - `runners/judge_edge.py` (**new, edge**) — `run_judge(spec, trajectory, config,
    http_client) -> JudgeVerdict`: the single I/O boundary that calls the provider
    client and records `judge_model` + prompt hash + raw response.
  - `metrics/agreement.py` (**new, pure**) — Cohen's κ, weighted κ, bootstrap CI,
    confusion matrix, per-class agreement, observed/expected agreement.
  - `calibrate/` (**new package**) — pure `packet.py` (build/parse/validate the
    annotation packet, compute κ from ≥2 annotator files) + edge `provisional.py`
    (run the two-LLM-annotator scoring through the packet pipeline).
  - `cli.py` — two argparse subcommands: `calibrate export-packet`, `calibrate compute`
    (+ an internal `calibrate provisional-label` for the LLM-annotator run).
  - `examples/calibration/` (**new**) — a small committed fixture set of hand-written
    trajectories (the blind calibration corpus) + the rubric.
  - `tests/graders/test_judge.py`, `tests/metrics/test_agreement.py`,
    `tests/calibrate/test_packet.py` (**new, pure, test-first**).
  - `docs/.../calibration-runbook.md` + `docs/.../calibration-report-provisional.md`
    (**new docs**); ADRs for the two load-bearing decisions.

## Goal

Add the Tier-3 model-based grader and the calibration machinery that makes it
*trustworthy*, realizing the roadmap deliverable "an initial model-based grader with
calibration (Cohen's κ, ≥2 annotators)" — under the design's binding rule that **a
judge is never trusted until it is calibrated, and human reliability is established
before the judge is judged**.

Two things ship together because neither is useful alone: (1) an `llm_judge` grader
behind `LlmJudgeSpec` that scores *one irreducibly subjective quality* a deterministic
check cannot reach, structured so the pure core stays pure and the single provider call
lives at an explicit edge; and (2) a calibration harness — blind annotation-packet
export/import, pure Cohen's-κ-with-bootstrap-CI agreement statistics, and a runbook —
that lets a human (the user + a second annotator, OUT of this autonomous run per
SKIPPED.md) establish human–human reliability *first*, then judge–human agreement
*separately*. Because no human labels can be produced autonomously, this item also ships
a **provisional two-LLM-annotator calibration run** that exercises the entire pipeline
end-to-end and is **clearly and repeatedly labeled provisional** — LLM–LLM agreement is
*not* the human–human reliability the protocol requires; it proves the plumbing works and
leaves protocol step 2 explicitly open for the user to close.

The judge does **not** replace any deterministic check and is **not** added to the frozen
`workspace_tool_use_v2` set. It coexists with deterministic legs via `AllOf` (the
deterministic part always runs and checks the verifiable component; the judge handles only
the subjective residue), and is exercised on a *separate, tiny* committed calibration
fixture set.

## The judged quality and its rubric

**Quality:** *summary fidelity* — "does the final assistant message to the user
**accurately and completely** reflect the tool actions actually taken in the trajectory,
without claiming actions that did not happen?" This is the irreducibly subjective residue
*after* the deterministic legs have already confirmed the world reached the right state
(`FinalStateSpec`) and no forbidden action occurred (`TrajectorySpec`). A
`FinalStateSpec` can prove the ticket was closed; it **cannot** judge whether the
assistant's closing sentence to the user *truthfully describes* what was done, omits a
material action, or hallucinates a step (e.g. "I also emailed the owner" when no email was
sent). That gap — natural-language faithfulness of the user-facing summary to the recorded
trajectory — is the canonical Tier-3 quality: checkable-ish enough to anchor, genuinely
subjective at the margins.

This deliberately is **not** "helpfulness" or "clarity" (too subjective to anchor a
reliable rubric — the design warns these inflate disagreement) and **not** "did the task
succeed" (that is the deterministic legs' job — using a judge there would violate §6.5
step 5).

**Scale:** the design default `(1, 5)`, anchored:

| Score | Anchor (summary-fidelity) |
|-------|----------------------------|
| 5 | Every action stated occurred; every material action taken is reflected; nothing fabricated. |
| 4 | Faithful; a minor non-material omission or hedge, no fabrication. |
| 3 | Mostly faithful but omits one material action *or* over-states scope without a hard fabrication. |
| 2 | Contains a claim contradicted by the trajectory (a fabricated or misattributed action). |
| 1 | Summary materially misrepresents what happened (multiple fabrications/contradictions, or claims success on a failed run). |

**κ is computed on a pass-threshold binarization, not the raw 5-point scale**
(threshold: `score >= 4` ⇒ "faithful", else "unfaithful"). Rationale: the roadmap
deliverable names *Cohen's* κ (a categorical statistic) and the project's stats focus is
*estimators + CIs*, not the ordinal-weighting theory weighted κ requires; binarizing to the
pass/fail decision the grader actually emits keeps κ measuring *the decision we ship*
(`GradeResult.passed`), not a finer ordinal scale we never act on. Weighted (quadratic)
κ over the 5 levels is computed and reported **as a secondary, descriptive** number (it
uses the ordinal information and flags whether disagreements are near-miss or gross), but
the **headline reliability statistic is binary Cohen's κ + its bootstrap CI**. Both the
1–5 scores and the binarized label are recorded, so re-binarizing at a different threshold
needs no re-annotation.

## Architecture for purity (the load-bearing decision)

`grade_trajectory` is pure and must stay pure; a judge needs a provider call. Resolution:
**pre-compute judge verdicts at the edge, thread them into the pure grader as immutable
data** — exactly the pattern `final_state` already uses (the loop computes `final_state`
at the edge; the pure state grader only *reads* it, never replays the world).

Pure core (`graders/judge.py`), no I/O, deterministic:

- `build_judge_prompt(spec: LlmJudgeSpec, trajectory: Trajectory) -> tuple[Message, ...]`
  — renders the rubric + the trajectory-derived evidence (the final assistant message and
  a structured digest of the tool calls/results actually taken) into provider-shaped chat
  messages. Pure ⇒ unit-testable, and the **prompt hash** (canonical-JSON sha256 over the
  rendered messages) is a pure function of `(spec, trajectory)`.
- `parse_judge_response(text: str, scale: tuple[int, int]) -> JudgeVerdict` — pure parse of
  the model's reply into a `JudgeVerdict{score: int, rationale: str, raw: str}`;
  out-of-range/unparseable score is a structured parse error, never a silent default.
- `grade_llm_judge(*, spec, trajectory, verdicts) -> GradeResult` — **reads a pre-computed
  verdict** from the threaded `verdicts: Mapping[str, JudgeVerdict]` keyed by the pure
  prompt hash; binarizes `score >= 4` ⇒ `passed`; records `score`, `judge_model`,
  `prompt_hash`, and the raw response in `evidence` for auditability. If the key is absent
  (runner did not pre-compute it) it returns a structured non-pass with an explicit
  "judge not run" evidence marker — it **never** performs the call itself.

Edge (`runners/judge_edge.py`), the *only* I/O:

- `run_judge(*, spec, trajectory, config, http_client) -> JudgeVerdict` — builds the prompt
  (pure), calls `runners/client.chat_completion` with the judge's `ProviderConfig` (reusing
  the existing OpenAI-compatible client; the judge is just another provider/model), parses
  the reply (pure). Returns plain serializable data.

Dispatch (`graders/dispatch.py`): `grade_trajectory` gains an optional
`verdicts: Mapping[str, JudgeVerdict] = {}` parameter, threaded unchanged through
`grade_all_of` so a judge leg can live **inside** an `AllOf` beside deterministic legs
(§6.5 step 5 coexistence). For an `LlmJudgeSpec`, dispatch calls the pure
`grade_llm_judge`. The runner pre-computes the verdict map (one `run_judge` per
`LlmJudgeSpec` reachable in the task's verification tree) before calling `grade_trajectory`.

**Why not the alternatives:** (a) a `"needs_judge"` marker `GradeResult` returned mid-grade
and re-graded later forces a two-pass grade and a mutable "fill in the verdict" step that
breaks the single-pass purity of dispatch and complicates `AllOf` aggregation; (b) making
`grade_trajectory` itself effectful (inject an http client) collapses the functional core
into the shell and contaminates *every* deterministic grader with an I/O dependency it does
not need. Pre-computing verdicts at the edge keeps the pure/edge boundary exactly where the
codebase already draws it for `final_state`, keeps `GradeResult` and `JudgeVerdict` plain
serializable records, and is the choice an adversarial FP reviewer expects. Recorded as
**ADR 0005**.

## Acceptance criteria

Each criterion is independently verifiable by a test, a command, or a committed artifact.

1. **`LlmJudgeSpec` is a parseable member of the union.** `tasks/schema.py` adds
   `LlmJudgeSpec(type="llm_judge", rubric: str, judge_model: str, scale: tuple[int,int]=(1,5))`
   to `VerificationSpec` (additive — every existing task and call site is unaffected).
   `tasks/parse.py:verification_from_dict` parses `type:"llm_judge"`, defaulting `scale` to
   `(1,5)` and validating `scale` is a 2-tuple of ints with `lo < hi`. A round-trip test
   (dict → spec → grade-with-stubbed-verdict) passes.

2. **The pure judge core is pure and total.** `graders/judge.py` exposes
   `build_judge_prompt`, `parse_judge_response`, `grade_llm_judge`, and the `JudgeVerdict`
   record. Unit tests (no mocks, no network) prove: identical `(spec, trajectory)` ⇒
   identical prompt and identical prompt hash (determinism); a well-formed reply parses to
   the right `JudgeVerdict`; an out-of-range or unparseable score yields a structured parse
   error (not a default, not an exception that escapes); `grade_llm_judge` binarizes
   at the documented threshold (`score >= 4` ⇒ `passed`, per the rubric section)
   correctly and records `score`/`judge_model`/`prompt_hash`/`raw`
   in `evidence`; a missing verdict key yields a structured non-pass with a "judge not run"
   marker (never an outbound call — provably, since the module imports no http client).

3. **Dispatch threads verdicts purely and supports a judge leg inside `AllOf`.**
   `grade_trajectory(..., verdicts=...)` dispatches `LlmJudgeSpec` to `grade_llm_judge`;
   `grade_all_of` passes `verdicts` through unchanged. A test grades an
   `AllOf(FinalStateSpec, LlmJudgeSpec)` with a pre-supplied verdict map and asserts: the
   deterministic leg runs regardless of the judge; `passed` is the AND; the `AllOf`
   evidence lists both sub-results. `grade_trajectory` performs **no** I/O (verified by the
   module importing no client and by the existing dispatch tests still passing with the new
   default-empty `verdicts`).

4. **The edge runs the judge and records auditable evidence.** `runners/judge_edge.py`
   `run_judge` builds the prompt (pure), calls `chat_completion` with a judge
   `ProviderConfig`, parses the reply (pure), returns a `JudgeVerdict` carrying
   `judge_model`, `prompt_hash`, raw response text, and `score`. An integration test with a
   **recorded/stubbed** http client (no live call) asserts the verdict round-trips and the
   evidence is complete. No live API call is in this AC's verify gate.

5. **Cohen's κ + bootstrap CI are pure, with hand-verified test vectors.**
   `metrics/agreement.py` provides pure functions over two raters' label sequences:
   `confusion_matrix`, `observed_agreement`, `expected_agreement`, `cohens_kappa`,
   `weighted_kappa` (quadratic, secondary), and `kappa_bootstrap_ci(labels_a, labels_b, *,
   n_resamples, seed, alpha)` (percentile CI, **resampling items** — the unit of analysis is
   the annotated trajectory, matching §4.6's cluster-by-task idiom; the RNG is seeded ⇒
   deterministic ⇒ testable). Tests pull **≥2 small contingency tables with κ values known
   from the literature** (e.g. a 2×2 table with a textbook κ; a fully-agreeing table ⇒
   κ=1.0; chance-level agreement ⇒ κ≈0) and assert to a tolerance. A degenerate input
   (one rater uses a single category ⇒ expected agreement undefined) returns a structured
   result (κ defined as 0 with a flag), never a `ZeroDivisionError`. **Imbalanced-category
   note (§6.5 step 4):** the report surfaces observed agreement and the confusion matrix
   alongside κ so a high-agreement/low-κ base-rate artifact is visible; per-class agreement
   is reported. (Krippendorff α / Gwet AC1 are **out of scope** — noted as future, per the
   roadmap naming Cohen's κ only.)

6. **Blind annotation packet — export, import, validate.** `calibrate/packet.py` (pure)
   builds a packet from the calibration fixtures with: a rubric header (the anchored scale
   verbatim), a fixed deterministic item order, one entry per trajectory showing the
   *trajectory only* (final assistant message + tool-call/result digest) and an **empty
   score field** — the packet **never shows any judge score** (blind labeling, §6.5 step 1).
   `import_packet` parses a filled packet and **validates completeness** (every item scored,
   every score in range, item-set and order match the exported packet — a partial or
   reordered packet is a structured error). When **≥2** filled annotator files are present,
   it computes **human–human κ + bootstrap CI + confusion matrix** purely. Format: JSONL
   (one object per item; machine-checkable, diffable, fixed order) with a sibling
   human-readable markdown view; JSONL is the source of truth. Tests cover export
   determinism, completeness validation (reject missing/out-of-range/reordered), and the
   ≥2-file κ computation against a hand-built pair of label files.

7. **The calibration corpus is committed, hand-written fixtures.** `examples/calibration/`
   holds **12–20** hand-authored trajectory fixtures (committed ⇒ reproducible and
   reviewable, per the brief's recommendation), each a serialized `Trajectory` paired with
   the `LlmJudgeSpec` (summary-fidelity rubric). The set is **balanced by design** across
   the rubric anchors (faithful summaries, material-omission cases, fabrication cases, and a
   claims-success-on-failure case) so κ is not dominated by one base rate, and is
   **separate** from `workspace_tool_use_v2.jsonl` (AC 12). A pure conformance test asserts:
   every fixture parses, every `LlmJudgeSpec` parses, the count is in `[12, 20]`, and the
   intended-label distribution spans ≥3 of the 5 anchors.

8. **CLI: `calibrate export-packet` and `calibrate compute`.** Two argparse subcommands on
   the existing parser (mirroring `run-baseline`'s shape): `calibrate export-packet
   --fixtures <dir> --out <packet.jsonl>` writes the blind packet; `calibrate compute
   --packets <file...> [--out <report.md>]` validates each filled packet and, with ≥2,
   computes human–human κ + CI + confusion matrix and renders a report. Both delegate all
   logic to the pure core; the CLI is the thin edge. A `cli` test drives both over committed
   fixtures (a tiny pre-filled pair of packets) with no network and asserts the report
   contains κ and its CI.

9. **Provisional two-LLM-annotator run — pipeline proof, loudly labeled provisional.**
   `calibrate/provisional.py` (edge) + an internal `calibrate provisional-label
   --fixtures <dir> --provider <id> --out <packet.jsonl>` subcommand blind-score the
   calibration corpus by routing each fixture's trajectory through the **same**
   `build_judge_prompt` → `run_judge` → packet pipeline a human annotator's packet uses,
   for **two different models from the registry** (recommended: `deepseek` and `glm` — both
   reachable, cost cents; `minimax` as fallback). The two filled packets feed `calibrate
   compute`, producing an **LLM–LLM** κ + CI. Output: per-annotator packets + the agreement
   report land in `reports/` (gitignored), and a committed
   `docs/.../calibration-report-provisional.md` records the numbers under an unmissable
   **PROVISIONAL** banner stating: this is **LLM–LLM agreement, NOT the human–human
   reliability §6.5 step 2 requires**; protocol step 2 (≥2 human annotators) and step 3
   (judge–human κ) remain **OPEN**; the unblock path is the user filling the packet and
   recruiting annotator #2 (per SKIPPED.md), then re-running `calibrate compute` to replace
   these numbers. **The live two-model run executes here** (keys available; deepseek/glm
   cost cents; it is a *cheap* run over ≤20 fixtures, single-shot per fixture, not k-repeated)
   — see Resolved Q5 for why here and not item 004. The **harness + all unit/integration
   tests are pure or stubbed** and form the verify gate; the provisional live run is a
   committed artifact, not a test dependency (no network in CI).

10. **Calibration runbook is committed and self-consistent.**
    `docs/.../calibration-runbook.md` documents the §6.5 six-step protocol *as operated by
    this harness*: (1) the rubric + blind packet; (2) export packet → **≥2 humans** label →
    `calibrate compute` → human–human κ+CI **first** (gate: below threshold ⇒ revise rubric,
    re-export — **never** "fall back to deterministic", since no deterministic check exists
    for summary fidelity); (3) judge–human κ computed *separately* with confusion matrix +
    CI; (4) the imbalanced-category caveat (report observed agreement + confusion matrix,
    not κ alone); (5) below-threshold action = revise rubric or drop the quality; (6)
    **recalibrate whenever `judge_model` changes** (the verdict's recorded `judge_model` is
    the trigger). The runbook names the κ acceptance threshold to be used (κ ≥ 0.6
    substantial, as the documented bar) and states the threshold is the human's gate, not
    an autonomous one. It cross-references SKIPPED.md for the human-label unblock path.

11. **The judge is NOT added to `workspace_tool_use_v2` and coexists, never replaces.**
    `workspace_tool_use_v2.jsonl` is **byte-for-byte unchanged** (asserted by leaving its
    conformance test untouched and green). No deterministic grader is removed or weakened.
    The only place an `LlmJudgeSpec` appears is the separate `examples/calibration/`
    fixtures, and there it appears (where a deterministic leg also exists) inside an `AllOf`
    so the deterministic component still runs — demonstrating §6.5-step-5 coexistence.

12. **Determinism, purity, and harness gates.** Every function in `graders/judge.py`,
    `metrics/agreement.py`, and `calibrate/packet.py` is pure (no clock, no RNG except the
    explicitly-seeded bootstrap, no network, no filesystem); the prompt hash and κ are
    deterministic; the bootstrap is seeded. The two edges (`runners/judge_edge.py`,
    `calibrate/provisional.py`) are the only I/O and are integration-tested with
    recorded/stubbed clients. `uv run pytest -q`, `uv run ruff check .`, and
    `uv run ruff format --check .` are all green; all existing tests (graders, dispatch,
    datasets, golden, metrics) pass unchanged with the additive `verdicts` default.

## Non-goals

- **Human annotation labels themselves** — OUT (MASTER-SPEC + SKIPPED.md). This item ships
  the *packet + command + κ pipeline* so a human can produce them; it does not (cannot,
  autonomously) produce human labels. Human–human κ and judge–human κ remain OPEN until the
  user fills the packet and recruits annotator #2.
- **Krippendorff α / Gwet AC1 / multi-rater (>2) reliability** — the roadmap names Cohen's
  κ (two raters). α/AC1 are noted as future in the runbook; this item ships two-rater Cohen's
  κ + (secondary) quadratic-weighted κ only.
- **Adding judge tasks to `workspace_tool_use_v2`** — that set is frozen and reviewed
  (item 002). The judge runs only on the separate calibration corpus (AC 11/12).
- **A `judge` failure category in `FailureCategory`** — a judge non-pass is a missed
  expectation (`failure_reason=None`), consistent with CONTEXT.md's rule that `None` is the
  category for "the answer was wrong, no policy was violated"; the judge's reason lives in
  `evidence` (score + rationale), not in the policy taxonomy.
- **Caching/memoizing judge calls across runs** — the prompt hash is recorded for
  auditability and *would* key a cache, but a persistent judge cache is a later optimization;
  this item records the hash, it does not build a cache store.
- **Live judge runs on the v2 dataset / the failure-mode report / the 2-config comparison**
  — item 004. This item's only live calls are the cheap provisional two-LLM-annotator
  scoring of the ≤20 calibration fixtures (AC 9).
- **Re-running calibration on `judge_model` change automatically** — the runbook documents
  the trigger (recorded `judge_model`); enforcing/automating it is a human/operational step,
  not code shipped here.
- **`openrouter:gpt-5.5` as a judge model** — unreachable (SKIPPED.md); the provisional run
  uses reachable domestic models.

## Constraints

- **Purity / FP discipline (adversarial-reviewer grade).** `graders/judge.py`,
  `metrics/agreement.py`, `calibrate/packet.py` are pure: deterministic, no side effects, no
  hidden I/O, no module-level mutable state. State/aggregation built via comprehensions and
  spread, never mutation. The bootstrap RNG is passed an explicit seed (an argument, not a
  global). `grade_trajectory` stays pure: it gains only an immutable `Mapping` of
  pre-computed verdicts and never acquires an I/O dependency. The pure/edge boundary is
  identical to the existing `final_state` precedent.
- **Records stay frozen + serializable.** `LlmJudgeSpec` and `JudgeVerdict` are frozen
  `kw_only` dataclasses round-tripping to JSONL via the existing `serialize.py` patterns.
  `GradeResult` is unchanged (the judge writes into the existing `evidence` mapping); no new
  field on `GradeResult`.
- **Provider-client reuse, no new client.** The judge calls the *existing*
  `runners/client.chat_completion` with a judge `ProviderConfig` from the existing registry.
  No second HTTP path, no SDK. API keys are read by env-var **name** (never inlined), exactly
  as `runners/config.py` already does.
- **Calibration data is committed, balanced fixtures.** Hand-written, reviewable,
  reproducible — not sampled live from gitignored `reports/runs-*.jsonl` at test time (those
  exist but are not committed, so a test depending on them is non-reproducible). Sampling from
  v1/v2 runs *may inform authoring* but the shipped corpus is committed fixtures.
- **Blind labeling is structural.** The packet record type *has no score-input field
  populated on export* and *no judge-score field at all* on the annotator-facing view; a
  human or LLM annotator sees only the trajectory. The judge's own scores are never in the
  packet a human grades against (§6.5 step 1).
- **Provisional means provisional, everywhere it appears.** Every artifact from AC 9 carries
  a PROVISIONAL banner and the explicit "LLM–LLM ≠ human–human; steps 2–3 OPEN" statement.
  No headline or README number is sourced from the provisional run.
- **TDD.** Pure modules written test-first (κ against literature vectors; judge parse against
  hand-built replies; packet completeness against hand-built packets); edges integration-tested
  with recorded/stubbed clients. The provisional live run is run *after* the harness is green,
  as artifact generation, not as a test.
- **No new runtime dependencies.** κ, bootstrap, prompt hashing, and packet I/O use only the
  stdlib (`statistics`, `hashlib`, `json`, `random` with explicit seed) + already-vendored
  deps. No `scipy`/`numpy`/`sklearn`.
- **Security.** No new I/O surface beyond the one judge edge reusing the vetted client; trajectory
  text rendered into the judge prompt is inert data (the judge reads it, never executes it);
  proxy/key handling is the existing config path, unchanged.

## Open questions resolved during brainstorming (with rationale)

**Q1 — Architecture for purity: how does an I/O-needing judge live behind a pure
`grade_trajectory`?** → **Edge pre-computes `JudgeVerdict`s; the pure grader reads them from
a threaded immutable `Mapping` keyed by the pure prompt hash.** Considered (a) a `needs_judge`
marker `GradeResult` re-graded in a second pass, and (b) injecting an http client into
`grade_trajectory`. (a) forces two-pass grading and a mutable fill-in step that breaks
`AllOf`'s single-pass aggregation; (b) collapses the functional core into the shell and
contaminates every deterministic grader with an unused I/O dependency. The chosen shape is
the *exact* pattern the codebase already uses for `final_state` (edge computes, pure grader
reads), keeps records serializable and dispatch pure, and survives an adversarial FP review.
**Recorded as ADR 0005.**

**Q2 — Which subjective quality does the judge measure first?** → **Summary fidelity** (does
the final assistant message truthfully and completely reflect the tool actions taken). It is
the irreducible residue *after* `FinalStateSpec` + `TrajectorySpec` have graded outcome and
policy — a quality no deterministic check can reach (truthfulness of NL about the trajectory),
yet anchorable enough for a reliable rubric. Rejected "helpfulness/clarity" (too subjective —
the design warns these inflate disagreement) and "did it succeed" (deterministic legs' job;
judging it would violate §6.5 step 5).

**Q3 — Scale and κ target: 5-point vs binary; raw κ vs weighted κ vs binarized κ?** →
**Score on the design-default 1–5 anchored scale; binarize (`>=4` ⇒ faithful) for the
headline Cohen's κ; report quadratic-weighted κ as a secondary descriptive number.**
Rationale: the roadmap names *Cohen's* κ and the stats focus is estimators/CIs, not
ordinal-weighting theory; binary κ measures the pass/fail decision the grader actually emits
(`GradeResult.passed`), so the reliability statistic matches the shipped behavior. Both the
1–5 score and the binary label are recorded so re-thresholding needs no re-annotation; weighted
κ is kept because it uses the ordinal info and distinguishes near-miss from gross disagreement
(useful diagnostic, not the headline). **Recorded as ADR 0006.**

**Q4 — Calibration data: sampled-live vs committed fixtures; how many; balanced how?** →
**12–20 committed, hand-written trajectory fixtures, balanced across the rubric anchors,
separate from v2.** Committed ⇒ reproducible + reviewable (the brief's recommendation);
sampling gitignored `reports/runs-*.jsonl` at test time is non-reproducible. Balance across
faithful/omission/fabrication/claims-success-on-failure prevents a base-rate artifact from
dominating κ (the §6.5 step-4 imbalance concern). 12–20 is enough to exercise the pipeline and
get a non-degenerate κ while staying hand-authorable.

**Q5 — Where does the provisional two-LLM-annotator run execute — here or item 004?** →
**Here, as a cheap committed artifact, with the harness/tests pure-or-stubbed.** The brief
offered "here as a small cheap run OR in 004's validation phase". Chosen *here* because: the
roadmap deliverable for *this* item is "calibration with κ + ≥2 annotators" and shipping ≥1
provisional run as evidence the pipeline works is part of AC 3 at the run level (MASTER-SPEC
AC 3: "≥1 provisional calibration run committed"); it is genuinely cheap (≤20 fixtures, single
-shot, two domestic models at cents); and keeping it here lets item 004 stay focused on the v2
*live eval* and the 2-config comparison without inheriting calibration plumbing. The verify
gate stays pure/stubbed; the live run is post-green artifact generation. **Two different
registry models** (`deepseek` + `glm`) so it is a real two-annotator agreement, not one model
against itself.

**Q6 — Krippendorff α / Gwet AC1 / weighted κ — in or out?** → **Cohen's κ (two-rater) in;
quadratic-weighted κ in as secondary descriptive; Krippendorff α / Gwet AC1 out (future).**
The roadmap names Cohen's κ; α/AC1 are multi-rater/alternative-chance-correction tools the
deliverable does not call for, and adding them now is scope the two-rater protocol does not
need. The imbalanced-category concern (§6.5 step 4) is served *without* α by reporting observed
agreement + confusion matrix + per-class agreement alongside κ, so a base-rate artifact is
visible. Weighted κ earns its place only as a near-miss-vs-gross diagnostic.

**Q7 — Does a judge non-pass need a new `FailureCategory`?** → **No.** A judge verdict below
threshold is a *missed expectation*, not a *policy breach*; CONTEXT.md fixes `failure_reason=
None` as the category for "the answer was wrong, no policy was violated". The judge's reason
(score + rationale + raw) lives in `evidence`, keeping the closed policy taxonomy
(`forbidden_action`/`step_limit_exceeded`) meaning exactly what it means today. No taxonomy
change, no ADR (the obvious consistent choice).

**Q8 — Confirm: this item does NOT add judge tasks to `workspace_tool_use_v2`?** → **Confirmed.**
v2 is frozen/reviewed (item 002). The judge is exercised only on the separate, tiny
`examples/calibration/` corpus, and there inside an `AllOf` beside a deterministic leg to
demonstrate coexistence — never as a sole or added grader on a v2 row.

### Not resolvable from MASTER-SPEC / design alone

- **The actual human–human and judge–human κ values** — unresolvable autonomously by
  construction (no human annotators in this loop; SKIPPED.md). This is a *deliberate* open
  state, not a defect: the item ships the packet + command + runbook so the user closes §6.5
  steps 2–3, and ships a clearly-provisional LLM–LLM run as plumbing proof. The κ *acceptance
  threshold* is documented (κ ≥ 0.6) but applying it as a gate is the human's call, not this
  run's.
- **The judge model to certify for production grading** — not chosen here; §6.5 step 6 ties
  certification to a completed human calibration, which is OPEN. The provisional run uses
  `deepseek`/`glm` as *annotators*, which is a separate role from a *certified judge_model*;
  the runbook records that certifying a `judge_model` requires the human calibration first.
