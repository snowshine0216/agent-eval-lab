Verdict: PASS-WITH-NITS
Source: /ship steps 8+9 (pre-landing parallel review: code-reviewer + silent-failure-hunter; adversarial review with two empirical re-verification rounds)

## Findings and resolutions

Round 1 (pre-landing parallel review):
- P0: agent-written conftest.py subverts oracle verdicts (pytest loads conftest regardless of PYTEST_DISABLE_PLUGIN_AUTOLOAD; hookwrapper forces outcome="passed"). FIXED in 93e4514: --noconftest uniformly (agent-visible and oracle runs share one semantics); red regression test demonstrated the subversion pre-fix.
- P0 (silent-failure): verdict_missing collapsed into the "not_run" bucket, conflating hash-lookup misses with missing final_state for item 004's classifier; no forensics in stored grades. FIXED in 735a525: "not_run" reserved for missing final_state; lookup miss → evidence execution="error" with kind="verdict_missing"; execution_hash now in evidence on all paths (pure-data observability — no logging in pure graders per CLAUDE.md).
- P1: oracle_edge broad `except Exception` hid programming errors. FIXED in 18b86a3: narrowed to (RuntimeError, OSError); TypeError now propagates (pinned by test).
- P1: serialize.verdict_from_dict raised KeyError instead of ValueError on missing "type". FIXED in 695f1f7.
- P1: oracle-secrecy golden test didn't scan initial_state. FIXED in de071fd.
- Declined (design): promoting suite status to a first-class GradeResult field / extending FailureCategory — the grilled spec deliberately keeps the closed taxonomy; item 004 reads the mechanical evidence discriminator. Recorded as accepted-by-design.

Round 2 (adversarial — BREAKS): sitecustomize.py on PYTHONPATH=root executes at interpreter startup, before --noconftest/plugin-disable; empirically flipped a failing oracle to PASS. FIXED in 4f24a60: root-level sitecustomize.py/usercustomize.py harness-reserved at both layers; residual in-process import boundary documented in pytest_edge docstring + ADR-0010.

Round 3 (adversarial — BREAKS): agent pytest config files (pytest.ini/setup.cfg/tox.ini/pyproject.toml) with addopts="-p evilplug" load arbitrary plugins; os._exit(0) in pytest_configure faked rc=0 PASS without importing agent code. FIXED in 54d9e9a: harness-owned .harness.ini written post-materialize + `-c .harness.ini` bypasses all agent config discovery; .harness.ini reserved root-level; 4 config variants pinned as regression tests.

Round 4 (adversarial — CLEAN): empirical battery over the config/startup class: python_files rename, testpaths redirect, addopts in all 4 config files, env vectors (from-scratch env — no PYTEST_ADDOPTS/PYTEST_PLUGINS), cache. All suppressed; oracle genuinely fails where it should. Remaining residual: the accepted, documented v1 in-process import boundary.

## Accepted nits / notes
- Verdict map not persisted on RunResult: accepted — grade evidence now carries execution_hash + error kinds, sufficient for post-hoc forensics without duplicating the map.
- timeout/error/no_tests all grade passed=False with discrimination via evidence["status"]: accepted-by-design (item 004's classifier input).
- ExecutionResult round-trip silently drops unknown fields (fixed dataclass): pre-existing serialization convention, unchanged.

Tests after all fix rounds: 550 passed; ruff check + format clean.
