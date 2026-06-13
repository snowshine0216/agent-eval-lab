# 008 — runner-harden plan (Package 1)

Spec source: HANDOFF.md §"What is NOT done" + §"Scoped pilot run" robustness gap; spec §7/§18.1/§18.11.

## Goal
Make the D-set runner survive a bad provider request and a context-length blowup without
crashing or losing data; wire local Qwen + the SiliconFlow Qwen ladder; then run D at **k=5**
across the full roster and regenerate the M1 report.

## Code phase (strict TDD — each red→green→refactor)

1. **Bound tool-result context fed back to the provider** (the GLM-5.1 SiliconFlow 400).
   - NEW pure module `runners/history.py`: `trim_tool_result_history(turns, *, char_budget)`
     — newest-first greedy keep; older `ToolResultTurn` contents replaced with a short elision
     marker once the budget is exceeded; the newest tool result is always kept; non-tool turns
     untouched; deterministic. Safe for grading (grader reads only the final answer + frozen
     snapshot, never the browse dumps — verified in `graders/fact_key.py`).
   - Wire into `loop.run_single`: build each round's messages from the trimmed view.
   - Tests: `tests/runners/test_history.py` (budget, newest-kept, idempotent, non-tool untouched).

2. **Catch per-run provider errors as a recorded failure, not a crash.**
   - `records/trajectory.py`: add shared sentinel `PROVIDER_ERROR` (next to `NO_CHOICES_ERROR`).
   - `loop.run_single`: wrap `chat_completion` in `try/except httpx.HTTPError` → record
     `ParseFailure(raw="HTTP <status>: <body[:500]>", error=PROVIDER_ERROR)`, `stop_reason="parse_failure"`,
     break. No secrets in `raw` (response body only; keys live in request headers).
   - `reports/classify.py`: map `error == PROVIDER_ERROR` → `harness_failure / provider_response`
     (same honest bucket as `NO_CHOICES_ERROR`: the provider delivered no usable completion).
     Counts as a VALID failed trial (NOT env-invalid → not replaced); surfaced in the taxonomy.
   - Tests: `test_loop.py` (400 → parse_failure recorded, no raise); `test_classify.py` (mapping).

3. **Write run JSONL incrementally** so one bad task can't lose a whole model's run.
   - `runners/dset_run.run_dset`: tuple-return → **generator** (`Iterator[ReplacementOutcome]`),
     yielding one outcome per task (executor built+closed per task as today).
   - `cli._run_dset_command`: consume the generator inside the open file, `_append_runs` (flush)
     per task, collect void task ids, write the `<runs>.void.json` sidecar (so `report-m1`
     consumes `run-dset` output directly, voids included). Client closed after consumption.
   - `experiments/m1_run.run_m1`: `tuple(run_dset(...))` (collect — keeps its dict contract).
   - Tests: `test_dset_run.py` (generator yields per task; partial survives a later raise);
     `test_cli.py` (incremental file grows; void sidecar written).

4. **Provider config: local Qwen + SiliconFlow ladder.**
   - `runners/config.py`: `local.model_id` `qwen3-8b` → **`Qwen/Qwen3-8B`** (verified: ollama
     `/v1/models` serves exactly this id). Add `siliconflow` provider
     (`base_url=https://api.siliconflow.cn/v1`, `api_key_env=SILICONFLOW_API_KEY`,
     default `model_id=Qwen/Qwen3.5-397B-A17B`) — the ladder's 35B is reached via `--model`.
     (Both ladder ids verified present on SiliconFlow `/v1/models`.)
   - Tests: `test_config.py` (local id; siliconflow provider + key env + condition_id).

## Execute phase (after code gates pass + PR merged)

5. **Re-freeze the M1 spec** for the corrected `local` condition id: update
   `examples/experiments/m1-agentic-v1.draft.json` (`local:qwen3-8b` → `local:Qwen/Qwen3-8B`
   in the condition + 4 planned-comparisons; drop "(PROVISIONAL)" from the now-verified ladder
   labels/comparison names), preserve the unchanged D dataset/pricing provenance hashes from the
   current frozen spec, `freeze-spec` → new `reports/agentic-v1/M1-spec.frozen.json`.
6. **Run D at k=5** (`evaluator.toml` already `k_valid=5`) for: deepseek, glm, minimax,
   siliconflow×2 (397B + 35B via --model), local. `run-dset` per provider (incremental;
   resumable). Background; record cost/rounds/tokens.
7. **`report-m1`** over all landed D arms → regenerate `reports/agentic-v1/M1-final-report.md`.

## Gates
TDD green + whole-tree ruff + full suite → drift (diff vs this plan) → `/code-review` → `/verify`
(check-env + a stubbed run-dset smoke proving incremental write + no-crash on a 400) → PR → squash-merge to main.

## Integrity
No secrets in tracked files. `ParseFailure.raw` carries only the response body (no auth header).
Draft spec is candidate-visible provenance (no answers). Run artifacts are gitignored (`/reports/`).
