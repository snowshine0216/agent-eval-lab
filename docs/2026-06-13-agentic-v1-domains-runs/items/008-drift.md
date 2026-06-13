Verdict: PASS

Subagent: sonnet
Plan checklist items: 4
Verified present in diff: 4
Drift findings:
  (none)
Integrity spot-check: ParseFailure.raw header-leak — clear

---

## Verification detail

### Step 1 — history-trim module (runners/history.py)

OK. `src/agent_eval_lab/runners/history.py` is a new pure module (diff lines 452–521).
`trim_tool_result_history(turns, *, char_budget)` implements newest-first greedy keep;
older `ToolResultTurn` contents are replaced with `_ELIDED_RESULT`; non-tool turns pass
through untouched; deterministic. Wired into `loop.run_single` via
`messages=tuple(turn_to_message(turn) for turn in trim_tool_result_history(turns))`
(diff loop.py +14 lines in the try block). Tests: `tests/runners/test_history.py` (new
file, 90 lines) covers budget, newest-kept, idempotent, non-tool untouched, and elided
serialization.

### Step 2 — provider-error → recorded failure (trajectory/loop/classify)

OK. `PROVIDER_ERROR = "provider request failed"` added to `records/trajectory.py`
(diff line +342). `loop.run_single` wraps `chat_completion` in
`try/except httpx.HTTPStatusError`, records `ParseFailure(raw=_provider_error_raw(exc),
error=PROVIDER_ERROR)`, sets `stop_reason="parse_failure"`, breaks (diff loop.py
+586–599). `reports/classify.py` maps `error == PROVIDER_ERROR` →
`harness_failure/provider_response` (diff lines +364–373). Tests: `test_loop.py`
(`test_loop_records_provider_http_error_as_parse_failure` — 400 → parse_failure,
no raise; `test_provider_error_raw_carries_no_auth_header` — header-leak guard);
`test_classify.py` (`test_provider_error_maps_to_harness_provider_response`).

### Step 3 — incremental JSONL + void sidecar (dset_run/cli/m1_run)

OK. `dset_run.run_dset` return type changed from `tuple[ReplacementOutcome, ...]` to
`Iterator[ReplacementOutcome]`; body uses `yield outcome` (diff dset_run.py lines
+428, +450). `cli._run_dset_command` consumes the generator inside `path.open("w")`,
calls `_append_runs(fh, outcome.valid_runs)` per task, collects void ids, writes
`path.with_suffix(".void.json")` sidecar after the loop (diff cli.py lines +236–285).
`experiments/m1_run.run_m1` wraps `run_dset(...)` in `tuple(...)` to keep its dict
return shape (diff m1_run.py lines +310–322). Tests: `test_dset_run.py`
(`test_run_dset_yields_incrementally_so_earlier_tasks_survive_a_later_raise` — generator
yields per task, partial survives ConnectError on second task); `test_cli.py`
(`test_run_dset_writes_incrementally_and_records_void_sidecar` — incremental file
grows, void sidecar written with correct task ids).

Note on test_cli.py adaptation: `_fail_second_task_handler` was changed from returning
`httpx.Response(400, ...)` to raising `httpx.ConnectError`. This is a required
consequence of step 2 — a 400 is now recorded inside `run_single` (not a propagating
exception), so the test that validates incremental write survival correctly uses a
transport error (ConnectError) to exercise the abort path. Not scope creep.

### Step 4 — provider config (config.py)

OK. `local.model_id` changed from `"qwen3-8b"` → `"Qwen/Qwen3-8B"` (diff config.py
line +406). `siliconflow` provider added: `base_url="https://api.siliconflow.cn/v1"`,
`api_key_env="SILICONFLOW_API_KEY"`, `model_id="Qwen/Qwen3.5-397B-A17B"` (diff
config.py lines +385–394). Tests: `test_config.py` adds
`test_local_model_id_matches_ollama_served_name` (asserts `"Qwen/Qwen3-8B"`),
`test_siliconflow_qwen_ladder_provider_is_wired` (url/key/model_id/no proxy), and
updates `test_condition_id_pairs_provider_and_model` to expect the corrected id.

### Integrity spot-check

`_provider_error_raw(exc: httpx.HTTPStatusError)` in `loop.py`:
```
body = exc.response.text[:_PROVIDER_ERROR_BODY_CAP]
return f"HTTP {exc.response.status_code}: {body}"
```
Reads `exc.response.text` and `exc.response.status_code` — both from the HTTP response
object. The API key lives in request headers, not in the response body. No auth header
leak. Confirmed by `test_provider_error_raw_carries_no_auth_header` which builds a
request with `Authorization: Bearer SECRET` and asserts `"SECRET" not in raw`.
Status: **clear**.
