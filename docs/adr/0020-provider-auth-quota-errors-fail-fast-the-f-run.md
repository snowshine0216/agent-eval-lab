# Provider auth/quota errors (HTTP 401/403) fail-fast the F run

The runner already refuses to *crash* on a rejected `/chat/completions` call: a
non-retryable `httpx.HTTPStatusError` is caught in `runners/loop.py` and recorded
as a `ParseFailure(error=PROVIDER_ERROR)` with `stop_reason="parse_failure"`, and
the run keeps going (ADR-0018 then routes such a run to env-invalid so it is masked
out of pass^k, never counted as a model FAIL). That is the right behaviour for a
*per-request* rejection — a single SiliconFlow 400 from context length should not
abort a whole multi-task run.

But the same "record-and-continue" path is wrong for an **account-global** block.
The first DashScope `qwen3.7-max` F-ablation run went 62% VOID: every call returned
HTTP 403 `AllocationQuota.FreeTierOnly` (free-tier exhaustion), and the driver
ground through 37 of 60 dead attempts before anyone noticed. pass@1 read 0.000 — an
artifact of an exhausted quota, not a measurement
(`reports/agentic-v1/f-ablation-v3-qwen37-VOID-freetier/`). A revoked or wrong key
(HTTP 401) has the identical shape. This is the same failure class as the node-v16
incident — a silent all-FAIL produced by an environment fault, not the model — and
the same precedent applies: refuse loudly rather than emit a false zero.

The status the driver needs to branch on is already recorded: `_provider_error_raw`
formats the rejection as `"HTTP {status}: {body}"` in `ParseFailure.raw` (the API
key lives in request headers, never the response, so nothing sensitive is captured).
The decision is purely *which* statuses are global blocks.

## Considered Options

- **Fail-fast on the first auth/quota status (401/403); leave 400/429 as
  record-and-continue** (chosen). A pure predicate
  `runners/loop.py::provider_auth_quota_status(trajectory)` returns 401/403 iff the
  recorded `PROVIDER_ERROR` carries that status, else `None`. The F-ablation driver
  (`_run_f_ablation_command`) and the single-arm `run-f` driver (`_run_f_command`)
  abort the moment it returns non-`None`, after writing whatever completed — the
  realized-order sidecar + streamed JSONL rows survive, exactly as on the existing
  `TransportError` abort path. Exit is non-zero with a message naming the
  quota/auth cause. The dead attempt itself is not graded or written.
- **Abort only after N consecutive auth/quota errors.** Rejected: 401/403 are not
  transient — a revoked key or an exhausted quota does not recover within a run —
  so the first occurrence is already conclusive, and any N>1 just lets N−1 more paid
  attempts burn for no information. The cost asymmetry favours first-error abort: a
  false abort costs one cheap re-run with a clear message; a missed block costs a
  silent 0.000 across the whole order.
- **Also fail-fast on 400 / 429.** Rejected. 400 is per-request (context length) —
  it can hit one oversized prompt while the rest of the order is fine, so aborting
  would throw away a recoverable run. 429 is transient and is *already* retried by
  the client (`runners/client.py::_RETRYABLE_STATUS`); a surfaced 429 means retries
  were exhausted, which is closer to a transport failure than a permanent block, and
  is not the silent-0.000 pathology this guard targets.
- **Push the guard into `run_single` / `run_f_candidate` so it raises.** Rejected:
  the loop's contract is "never raise on a provider HTTP error" (so one bad request
  cannot abort a multi-task run), and `is_env_invalid_run` / classify depend on the
  recorded `PROVIDER_ERROR`. The fail-fast decision is an *orchestration* policy and
  belongs at the driver edge, reading the trajectory the loop already records.

## Decision

`provider_auth_quota_status` is the single pure source of "is this an
account-global block?", co-located with its producer `_provider_error_raw` so the
`"HTTP {status}: …"` format and its inverse parser cannot drift (mirroring the
`PROVIDER_ERROR` / `NO_CHOICES_ERROR` constants shared with `reports/classify.py`).
Only **401 and 403** are global blocks. Both F drivers fail-fast on it, preserving
partial artifacts and exiting non-zero. Classification of the underlying
`PROVIDER_ERROR` is unchanged — this guard only decides whether to keep going.

## Consequences

- A quota-exhausted or bad/revoked key now aborts after the **first** dead F-ablation
  attempt (≤ k dead attempts for `run-f`, which discovers the block per whole task),
  instead of recording dozens and emitting a false 0.000. The operator sees the
  provider's own error text (e.g. `AllocationQuota.FreeTierOnly`) on stderr and a
  clear "fix the key/quota and retry".
- Partial results are not lost: completed rows stream to JSONL and the
  realized-order sidecar records exactly what executed — the run is resumable and
  auditable. The dead attempt is excluded from both.
- Defense-in-depth, not a replacement: `is_env_invalid_run` (ADR-0018) still masks
  any auth/quota row that slips through (e.g. a future caller that does not consult
  the guard), so such a run can never be silently scored as a model FAIL.
- 400/429 keep the prior record-and-continue + env-invalid masking — per-request and
  transient failures do not abort a run.
- Scope: the guard is wired into the F drivers (the evidenced incident path). The
  token-metered B/D/M `run_task_k` path and the Claude-CLI baseline (OAuth/subprocess,
  a different failure shape) are out of scope here; the pure predicate is reusable if
  that changes.
