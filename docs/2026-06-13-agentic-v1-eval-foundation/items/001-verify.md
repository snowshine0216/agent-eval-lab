# Item 001 — Records + Runner Revision: Verification

**Branch:** `feat/agentic-v1-001-records-runner`
**Date:** 2026-06-13
**Verifier:** Claude Code (autodev VERIFY gate)

---

## VERDICT: PASS

---

## Method

Scratch script `/tmp/verify_001_records_runner.py` run via `uv run python /tmp/verify_001_records_runner.py`.
No live model — uses `httpx.MockTransport` scripted clients identical to the helpers in `tests/runners/test_loop.py`.
The script imports the public module surface and exercises the integrated chain end-to-end.

---

## Check 1 — Censoring loop

### 1a: natural completion

`run_single` with a scripted client that emits two tool-call rounds then a final message (`create_ticket` → `update_ticket` → "Done."):

```
stop_reason        = 'completed_natural'
rounds             = 3
tool_call_counts   = {'create_ticket': 1, 'update_ticket': 1}
run_uid            = 'local:m__0000'
wall_time_s        = 0.00039045908488333225
usage.latency_s    = 0.00039045908488333225
wall_time_s==latency_s = True
```

Assertions: `stop_reason=="completed_natural"`, `rounds==3`, `tool_call_counts=={"create_ticket":1,"update_ticket":1}`, `run_uid=="local:m__0000"`, `wall_time_s==usage.latency_s`. All PASS.

### 1b: safety cap

`run_single` with a client that always returns a tool call (never finishes) and `safety_cap=3`:

```
stop_reason        = 'safety_cap'
safety_cap_bound   = True
total_tool_calls   = 3
```

Assertions: `stop_reason=="safety_cap"`, `safety_cap_bound is True`, exactly 3 tool calls. PASS.

### 1c: post-probe unhealthy

`health_probe_fn` returns pre-healthy, then a post-probe with `post_healthy=False, post_status=503`:

```
stop_reason        = 'env_unhealthy'
env_health.pre_healthy  = True
env_health.post_healthy = False
env_health.post_status  = 503
```

Assertions: `stop_reason=="env_unhealthy"`, `env_health is not None`, `post_healthy is False`, `pre_healthy is True`. PASS.

---

## Check 2 — Serialize round-trip + v1 back-compat

### 2a: v2 trajectory full round-trip

`trajectory_to_dict` on the check-1a trajectory (all new fields populated):

```
dict[schema_version]      = '2'
dict[rounds]              = 3
dict[wall_time_s]         = 0.00039045908488333225
dict[tool_call_counts]    = {'create_ticket': 1, 'update_ticket': 1}
dict[safety_cap_bound]    = False
dict[env_health]          = None
dict[run_uid]             = 'local:m__0000'
```

`trajectory_from_dict` on that dict:

```
restored.schema_version   = '2'
restored.rounds           = 3
restored.run_uid          = 'local:m__0000'
restored == original      = True
```

Assertions: `schema_version=="2"`, round-trip equality. PASS.

### 2b: real pre-revision artifact back-compat

One line from `reports/runs-deepseek-deepseek-v4-pro.jsonl` (no `schema_version` key):

```
v1 dict keys              = ['turns', 'usage', 'run_index', 'stop_reason', 'parse_failure', 'final_state']
'schema_version' present  = False
v1 stop_reason            = 'completed'
```

After `trajectory_from_dict`:

```
hydrated schema_version   = '1'
stop_reason               = 'completed'
rounds (safe default)     = 0
wall_time_s (safe default)= 0.0
safety_cap_bound (default)= False
env_health (default)      = None
run_uid (default)         = None
```

Assertions: `schema_version=="1"`, all new fields at safe defaults, no crash. PASS.

---

## Check 3 — Replacement-trial loop

### 3a: first invalid then valid → exactly k_valid valid runs

`validity_fn` marks first call invalid, rest valid; `k_valid=2`, `max_invalid_rate=0.9`:

```
void             = False
len(valid_runs)  = 2
len(attempts)    = 3
attempt_indices  = [0, 1, 2]
attempt_valid    = [False, True, True]
```

Assertions: `void is False`, exactly 2 valid runs, `attempt_index` increments 0→1→2. PASS.

### 3b: always invalid, max_invalid_rate=0.4 → VOID

`validity_fn` always returns False; `k_valid=2`, `max_invalid_rate=0.4`:

```
void             = True
len(valid_runs)  = 0
```

Assertions: `void is True`, `len(valid_runs) < 2`. PASS.

---

## Check 4 — fc-v3 classify

```
CLASSIFIER_VERSION = 'fc-v3'
```

### 4a: env_unhealthy trajectory → environment_failure

Check-1c trajectory (`stop_reason="env_unhealthy"`, `post_healthy=False`), grade failed:

```
category           = 'environment_failure'
subcategory        = 'post_probe_failed'
detail             = 'post-probe unhealthy (post_status=503)'
classifier_version = 'fc-v3'
```

Assertions: `category=="environment_failure"`, `subcategory=="post_probe_failed"`, `classifier_version=="fc-v3"`. PASS.

### 4b: normal completed_natural passed run → passed

Check-1a trajectory, grade passed:

```
category           = 'passed'
subcategory        = None
```

Assertions: `category=="passed"`, `subcategory is None`. PASS.

---

## Full test suite

```
697 passed in 22.67s
```

---

## Ruff

```
uv run ruff check src/agent_eval_lab/records src/agent_eval_lab/runners src/agent_eval_lab/reports
All checks passed!
```

---

## Findings

- No issues. All 4 checks passed cleanly on first run.
- The `wall_time_s` value is a real measured latency accumulated across mock HTTP calls (not zero), confirming the monotonic timer in `runners/client.py` is live even in mock transport.
- The v1 real artifact (`runs-deepseek-deepseek-v4-pro.jsonl`) carries `stop_reason="completed"` (legacy value), which hydrates without error — confirming the `Literal` union retains the legacy strings.
