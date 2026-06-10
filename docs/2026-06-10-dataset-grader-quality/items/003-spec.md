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
(threshold: `score >= 4` ⇒ "faithful", else "unfaithful"). **The `>=4` cut is defined by the
anchors, not free** (**Resolved D5**): the 4↔3 boundary is the only place in the scale where
"a fabrication or a material omission" first appears — exactly the faithful/unfaithful line — so
re-anchoring the rubric forces re-examining the threshold. Rationale: the roadmap
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
  — renders the rubric + the trajectory-derived evidence into provider-shaped chat messages.
  The digest is a **deterministic, canonical** rendering (**Resolved D8**) of, in trajectory
  order: every `ToolCallTurn` as `name(canonical-JSON args)` reusing `graders/canonical.py:
  canonicalize` + `json.dumps(sort_keys=True)`; each paired `ToolResultTurn` outcome rendered
  with its `ToolSuccess`/`ToolFailure` discriminator (`ok:<result>` / `error:<error>`); and the
  final assistant `MessageTurn.content`. **`scale` is rendered into the prompt** ("score 1-5…")
  so the prompt hash is a faithful key for *interpretation*, not just the reply (**Resolved D4**).
  The judge is instructed to emit a final `SCORE: <int>` line (**Resolved D6**). Pure ⇒
  unit-testable, and the **prompt hash** (sha256 over the canonical-JSON of the rendered
  messages, `sort_keys=True`) is a pure function of `(spec, trajectory)`. Result-blob truncation
  for large live trajectories is **out of scope** (fixtures are authored small; item 004 owns
  the live v2 run) — **Resolved D8**.
- `parse_judge_response(text: str, scale: tuple[int, int]) -> JudgeVerdict | JudgeParseFailure`
  — pure parse of the model's reply into a `JudgeVerdict{score: int, rationale: str, raw: str,
  ~~}~~ judge_model: str, prompt_hash: str}` (**Resolved D3** — the verdict is the *only*
  channel to the pure grader, so it carries `judge_model`+`prompt_hash`; the edge stamps them).
  The score is extracted from a required `SCORE: <int>` final line (**Resolved D6**); the three
  pure failure cases — (a) no extractable integer (refusal/prose-only), (b) integer out of
  `[lo, hi]`, (c) conflicting integers with no designated answer — each yield a structured
  `JudgeParseFailure{raw, error}`, **never** clamped, defaulted, or first-wins-silently.
- `grade_llm_judge(*, spec, trajectory, verdicts) -> GradeResult` — **reads a pre-computed
  verdict** from the threaded `verdicts: Mapping[str, JudgeVerdict ~~}~~ | JudgeError]` keyed by
  the pure prompt hash; binarizes `score >= 4` ⇒ `passed`; records `judge_model`, `prompt_hash`,
  `score`, `scale`, `threshold`, `binary_label`, `rationale`, and `raw` in `evidence` for
  auditability (**Resolved D3**). If the key is absent **or holds a `JudgeError`/`JudgeParseFailure`**
  (runner did not pre-compute it, or the call/parse failed) it returns a structured non-pass
  (`passed=False`, `failure_reason=None`) with an explicit "judge not run" / error evidence
  marker (**Resolved D2**) — it **never** performs the call itself and **never** coerces a failure
  into a pass or a policy-breach.

Edge (`runners/judge_edge.py`), the *only* I/O:

- `run_judge(*, spec, trajectory, config, http_client) -> JudgeVerdict ~~`~~ | JudgeError` —
  builds the prompt (pure), calls `runners/client.chat_completion` with the judge's
  `ProviderConfig` (reusing the existing OpenAI-compatible client; the judge is just another
  provider/model), parses the reply (pure), and **stamps `judge_model` (from the config) +
  `prompt_hash` onto the returned `JudgeVerdict`**. It **never lets an exception escape into the
  verdict map** (**Resolved D2**): a transport/HTTP failure or a `JudgeParseFailure` from the
  pure parser is captured as a serializable `JudgeError{kind, error, prompt_hash, judge_model}`
  — the same explicit-sum-type discipline the runtime uses for `ToolFailure`/`ParseFailure`.
  Returns plain serializable data.

Dispatch (`graders/dispatch.py`): `grade_trajectory` gains an optional
`verdicts: Mapping[str, JudgeVerdict ~~] = {}~~ | JudgeError] = {}` parameter; `grade_all_of`'s
signature **also** gains `verdicts` and threads it unchanged into every recursive sub-call
(**Resolved D1** — exactly as item 001 added `initial_state` and threaded it through
`grade_all_of`; the spec's "threaded unchanged" understated that `grade_all_of`'s own signature
changes). So a judge leg can live **inside** an `AllOf` beside deterministic legs (§6.5 step 5
coexistence). For an `LlmJudgeSpec`, dispatch calls the pure `grade_llm_judge`. The runner
pre-computes the verdict map by **first walking the spec tree with a pure
`collect_judge_specs(verification) -> tuple[LlmJudgeSpec, ...]`** (recursing `AllOf` exactly as
`grade_all_of` does, in the pure core — **Resolved D1**), running one `run_judge` per *distinct
rendered prompt* (identical prompts dedup to one call — **Resolved D4**), then calling
`grade_trajectory(..., verdicts=...)`.

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
   `build_judge_prompt`, `parse_judge_response`, `grade_llm_judge`, the `JudgeVerdict` record,
   ~~and~~ the `JudgeParseFailure` record, and the pure `collect_judge_specs` collector
   (**Resolved D1/D2**). Unit tests (no mocks, no network) prove: identical `(spec, trajectory)`
   ⇒ identical prompt and identical prompt hash (determinism, with `scale` rendered into the
   prompt — **Resolved D4**); a well-formed reply (with its `SCORE: <int>` line) parses to the
   right `JudgeVerdict`; each of the **three** parse-failure cases — no extractable integer,
   out-of-range integer, conflicting integers (**Resolved D6**) — yields a structured
   `JudgeParseFailure` (not a default, not a clamp, not an escaped exception); `grade_llm_judge`
   binarizes at the documented threshold (`score >= 4` ⇒ `passed`, per the rubric section)
   correctly and records ~~`score`/`judge_model`/`prompt_hash`/`raw`~~
   `judge_model`/`prompt_hash`/`score`/`scale`/`threshold`/`binary_label`/`rationale`/`raw`
   in `evidence` (**Resolved D3**); a missing verdict key **or a `JudgeError`/`JudgeParseFailure`
   at the key** yields a structured non-pass (`failure_reason=None`) with a "judge not run" /
   error marker (**Resolved D2**) — never an outbound call (provably, since the module imports no
   http client) and never a coerced pass/policy-breach.

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
   `judge_model`, `prompt_hash`, raw response text, and `score` — **or a `JudgeError` on
   transport/HTTP/parse failure, never an escaped exception** (**Resolved D2**). Integration
   tests with a **recorded/stubbed** http client (no live call) assert both the success
   round-trip *and* that a stubbed transport error / a refusal reply produce a serializable
   `JudgeError` (not a crash, not a coerced score). No live API call is in this AC's verify gate.

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
   roadmap naming Cohen's κ only.) **A separate hand-verified test vector for quadratic-weighted
   κ** over a small ordinal table (3×3 or 5×5), computed by hand or against a published worked
   example, is **required** — the 2×2 unweighted literature vectors do not exercise the weighting
   (**Resolved D6b**). **Degenerate bootstrap resamples** (a resample drawing a single category
   for one rater) take the same structured path as degenerate top-level input (κ=0 with a flag);
   `kappa_bootstrap_ci` **counts and reports** how many resamples were degenerate, never silently
   dropping them or crashing (**Resolved D7**).

6. **Blind annotation packet — export, import, validate.** `calibrate/packet.py` (pure)
   builds a packet from the calibration fixtures with: a `packet_format` version field + a
   `rubric_version` (**Resolved D11** — `import_packet` rejects a mismatched `packet_format`
   rather than mis-parsing), a rubric header (the anchored scale verbatim), a fixed deterministic
   item order, one entry per trajectory showing the *trajectory only* (final assistant message +
   tool-call/result digest) and an **empty score field** — the packet **never shows any judge
   score nor any fixture's intended label** (blind labeling, §6.5 step 1; intended labels live in
   the AC-7 fixture design table, **outside** the packet — **Resolved D9**).
   `import_packet` parses a filled packet and **validates completeness** (every item scored,
   every score in range, `packet_format` matches, item-set and order match the exported packet —
   a partial, reordered, or version-mismatched packet is a structured error). When **≥2** filled
   annotator files are present,
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
   intended-label distribution spans ≥3 of the 5 anchors. **A fixture design table is a required
   deliverable** (**Resolved D9**) — one row per fixture: `fixture_id | intended_anchor (1–5) |
   planted failure type (faithful / minor-omission / material-omission / fabrication /
   claims-success-on-failure) | one-line description`, committed in the runbook or a fixtures
   README. Discrimination lives in this design; the table makes "balanced by design" auditable.
   The intended label is **never** shipped inside the blind packet.

8. **CLI: `calibrate export-packet` and `calibrate compute`.** A ~~Two argparse subcommands on
   the existing parser (mirroring `run-baseline`'s shape)~~ **nested** `calibrate` subparser
   (a sub-subparser group hanging off the top-level `dest="command"`, coexisting with the flat
   `run-baseline` — **Resolved D11**): `calibrate export-packet
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
   — see Resolved Q5 for why here and not item 004. **`provisional-label` pre-flights the
   provider key** (checks `os.environ` for the config's `api_key_env` before any call) and exits
   with a documented "key unset; provisional run skipped" message rather than crashing mid-corpus
   or emitting a partial packet (**Resolved D12**); the committed report records which models
   actually ran and whether any was skipped for a missing key. Keys live in `../.env`
   (`DEEPSEEK_API_KEY` + `SILICONFLOW_API_KEY` confirmed present) and are read by env-var *name*
   via `ProviderConfig.api_key_env`, never inlined. The **harness + all unit/integration tests
   are pure or stubbed** and form the verify gate; the provisional live run is a committed
   artifact, not a test dependency (no network in CI) — absent keys never break CI, only skip the
   artifact.

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
    an autonomous one. **It states honestly that at n≈12–20 the bootstrap CI is wide and
    n-dominated — a plumbing/feasibility number, not a reliability verdict** (**Resolved D7**),
    reinforcing the PROVISIONAL framing; it justifies **percentile** CI over BCa (BCa's
    bias/acceleration adds complexity for little gain when sample size dominates the error, and
    percentile matches the §4.6 idiom). It cross-references SKIPPED.md for the human-label
    unblock path.

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
- **Records stay frozen + serializable.** `LlmJudgeSpec`, `JudgeVerdict`, `JudgeError`, and
  `JudgeParseFailure` are frozen `kw_only` dataclasses round-tripping to JSONL via the existing
  `serialize.py` patterns; `JudgeVerdict` carries `judge_model`+`prompt_hash` (self-describing —
  **Resolved D3**). `GradeResult` is unchanged (the judge writes into the existing `evidence`
  mapping); no new field on `GradeResult`.
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

## Resolved decisions (grill, 2026-06-10)

Eight adversarial angles grilled against the live codebase; all resolved, auto-accepted (no user
in the autonomous loop). `D` ids cross-reference the inline strike-throughs above.

**D1 — When does the runner know a task needs a judge, and is the spec-tree walk pure?**
- A: A **pure `collect_judge_specs(verification) -> tuple[LlmJudgeSpec, ...]`** in the core
  recurses `AllOf` exactly as `grade_all_of` does; the edge runs one `run_judge` per distinct
  rendered prompt, then calls `grade_trajectory(..., verdicts=...)`. `grade_all_of`'s own
  signature gains `verdicts` (the spec said "threaded unchanged" but understated this) — the
  exact precedent is item 001 adding `initial_state` and threading it through `grade_all_of`.
- Rationale: the "what needs a judge" decision must be a pure function of the spec tree; burying
  the walk in the edge would put grading logic in the shell. Verified: no collector exists yet;
  `grade_all_of` (composite.py) injects `grade` and recurses with a fixed keyword set.
- Doc impact: spec architecture + AC 2/3; ADR 0005; CONTEXT.md (JudgeVerdict, prompt hash).

**D2 — Judge call/parse failure: explicit state, never silent pass/fail.**
- A: Mirror `ToolOutcome`. `parse_judge_response -> JudgeVerdict | JudgeParseFailure` (pure);
  `run_judge -> JudgeVerdict | JudgeError` (edge, never lets an exception escape). Verdict map
  value type is `JudgeVerdict | JudgeError`. A `JudgeError`/`JudgeParseFailure` at a key (or a
  missing key) ⇒ structured non-pass (`failure_reason=None`) with the error in `evidence` —
  never a coerced pass, never a faked policy breach.
- Rationale: the codebase already enforces explicit-sum-type failures (`ToolSuccess|ToolFailure`,
  `ParseFailure`, `parse.py` never raising on bad args). The judge is the same discipline.
- Doc impact: spec architecture + AC 2/4; constraints; ADR 0005; CONTEXT.md (JudgeVerdict).

**D3 — What is in evidence for a judge leg, and where does it come from?**
- A: `JudgeVerdict` must carry `judge_model` + `prompt_hash` (the edge stamps them) because the
  pure grader has **no other source** — the verdict is the only edge→core channel. Evidence =
  `{judge_model, prompt_hash, score, scale, threshold, binary_label, rationale, raw}`.
- Rationale: the spec's original `JudgeVerdict{score, rationale, raw}` could not populate the
  evidence its own AC 4 demands. Self-describing verdict is the load-bearing consequence of the
  purity boundary.
- Doc impact: spec architecture + AC 2; constraints; ADR 0005; CONTEXT.md (JudgeVerdict).

**D4 — Is the verdict map keyed robustly (collisions)?**
- A: Key = prompt hash over canonical-JSON rendered messages. Two legs with byte-identical
  prompts legitimately share one verdict (correct dedup). The reverse hazard (same hash, should
  differ) is prevented by **rendering every interpretation-affecting field — notably `scale` —
  into the prompt**, so legs that should differ render different prompts and hash apart.
- Rationale: a hash that omitted `scale` would be an unsound key for binarization. Rendering it
  makes the hash faithful to interpretation, not just to the reply.
- Doc impact: spec architecture + AC 2; CONTEXT.md (prompt hash).

**D5 — Justify the `score >= 4` binarization threshold.**
- A: Not a free parameter — **defined by the anchors**: the 4↔3 boundary is the only place in
  the scale where "a fabrication or material omission" first appears, which is exactly the
  faithful/unfaithful line. Re-anchoring the rubric forces re-examining the cut.
- Rationale: couples the threshold to the rubric, so the binarization can't drift from the
  scale's semantics. Strengthens ADR 0006.
- Doc impact: spec rubric section; ADR 0006.

**D6 — Parse contract + weighted-κ test vector.**
- A: (D6) The judge emits a final `SCORE: <int>` line; the parser extracts exactly that and
  structurally fails on (a) no integer, (b) out-of-range, (c) conflicting integers — never
  clamps/defaults. (D6b) Quadratic-weighted κ needs its **own** hand-verified ordinal test
  vector (3×3 or 5×5); the 2×2 unweighted literature vectors do not exercise the weighting.
- Rationale: a named extraction contract makes the parse deterministic and the failure modes
  enumerable/testable; weighted κ would otherwise ship untested against a known value (TDD gap).
- Doc impact: spec architecture + AC 2/5.

**D7 — Bootstrap CI: percentile vs BCa; n-dependence; degenerate resamples.**
- A: Keep **percentile** (BCa's bias/acceleration adds complexity for little gain when sample
  size dominates the error; percentile matches the §4.6 idiom). Runbook states honestly that
  n≈12–20 ⇒ wide, n-dominated CI = a feasibility number, not a verdict. Degenerate *resamples*
  (single-category draw) take the same structured κ=0-with-flag path as degenerate top-level
  input; `kappa_bootstrap_ci` **counts and reports** them, never silently drops or crashes.
- Rationale: the dominant error at this n is sample size, not the CI method; consistency with
  the documented idiom beats marginal small-sample accuracy. No ADR — swapping CI method is
  local to one function and follows the documented idiom (not a surprising deviation).
- Doc impact: spec AC 5/10.

**D8 — Judge prompt: which turns; pure deterministic rendering.**
- A: Canonical rendering in trajectory order: each `ToolCallTurn` as `name(canonical-JSON args)`
  (reuse `graders/canonical.py:canonicalize` + `sort_keys=True`), each paired `ToolResultTurn`
  with its `ToolSuccess`/`ToolFailure` discriminator, then the final assistant message. Result
  truncation for large live trajectories is out of scope (fixtures are small; item 004 owns the
  live v2 run).
- Rationale: reuse the existing canonicalization idiom rather than invent one; `sort_keys`
  guarantees dict ordering can't perturb the prompt hash. Verified `canonicalize` exists.
- Doc impact: spec architecture + AC 2.

**D9 — Fixture design table; discrimination lives in fixture design.**
- A: A **fixture design table** is a required deliverable (one row per fixture: id, intended
  anchor, planted failure type, description). The intended label lives in the table/runbook,
  **never** in the blind packet (§6.5 step 1).
- Rationale: "balanced by design" is only auditable if each fixture's planted intent is
  recorded; that design is where κ's discrimination power comes from.
- Doc impact: spec AC 6/7; CONTEXT.md (Annotation packet).

**D11 — CLI nesting + versioned packet format.**
- A: `calibrate` is a **nested** subparser group (export-packet / compute / provisional-label),
  coexisting with the flat `run-baseline`. The packet JSONL carries `packet_format` +
  `rubric_version`; `import_packet` rejects a version mismatch rather than mis-parsing.
- Rationale: argparse supports nested subparsers; a versioned packet format prevents silent
  mis-parse of an old packet after a schema change.
- Doc impact: spec AC 6/8; CONTEXT.md (Annotation packet).

**D12 — Provisional run feasibility + key-absent failure mode.**
- A: deepseek+glm over ≤20 fixtures single-shot ≈ trivial cost; both keys (`DEEPSEEK_API_KEY`,
  `SILICONFLOW_API_KEY`) confirmed present in `../.env`. `provisional-label` **pre-flights the
  key** and exits with a documented skip message (never crashes mid-corpus / writes a partial
  packet). Absent keys never break CI (verify gate is pure/stubbed) — they only skip the
  artifact; the committed report records which models ran.
- Rationale: `chat_completion._headers` raises on a missing key; pre-flighting turns a mid-run
  crash into a clean, documented skip.
- Doc impact: spec AC 9; constraints.

### ADRs adjudicated (three-of-three bar)

- **ADR 0005 (purity boundary — edge pre-computes verdicts, pure grader reads)** — **CLEARS.**
  Hard to reverse (architectural shape; sets the precedent for `ExecutionSpec` too), surprising
  (a reader asks "why not call the judge inline?"), real trade-off (two named rejected
  alternatives). **Written.**
- **ADR 0006 (binary Cohen's κ headline, weighted κ secondary)** — **CLEARS.** Surprising (the
  textbook ordinal choice is weighted κ; binarizing + demoting it needs the "measures the shipped
  decision" rationale), real trade-off (raw / binarized / weighted-headline are three genuine
  options), and the rubric-anchor coupling (D5) makes the fixture-authoring half hard to reverse.
  **Written.**
