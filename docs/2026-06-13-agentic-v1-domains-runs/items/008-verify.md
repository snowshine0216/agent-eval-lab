Verdict: PASS
Subagent: sonnet
Source: /verify fallback — CLI entry-point smoke (round 2, post-fix e297082)
Entry point exercised:
  - uv run pytest "tests/test_cli.py::test_run_dset_transport_error_gives_exit1_and_writes_void_sidecar" -v -p no:cacheprovider
  - uv run pytest "tests/test_cli.py::test_run_dset_writes_incrementally_and_records_void_sidecar" -v -p no:cacheprovider
  - uv run pytest tests/runners/test_loop.py -k "provider or http" -v -p no:cacheprovider
  - uv run pytest tests/runners/test_history.py -v -p no:cacheprovider
  - uv run python -c "from agent_eval_lab.runners.config import PROVIDERS; ..."
  - uv run python -m agent_eval_lab.cli check-env

Observed behavior:
  - run-dset mid-corpus TransportError -> exit-1 + .void.json sidecar — PASS: test_run_dset_transport_error_gives_exit1_and_writes_void_sidecar 1 passed in 4.29s
  - provider config live (local Qwen3-8B + siliconflow) — local model: Qwen/Qwen3-8B; siliconflow: present (Qwen/Qwen3.5-397B-A17B)
  - provider-400 recorded as parse_failure (no regression) — 2 passed (test_loop_records_provider_http_error_as_parse_failure + test_provider_error_raw_carries_no_auth_header) in 6.28s
  - history trim correct (no regression) — 6 passed (tests/runners/test_history.py) in 4.25s
  - check-env boots — exit 0: "[ok] playwright-cli: 0.1.14 / [skip] MSTR health probe — pass --evaluator-config to enable"

Failures: none
