Verdict: PASS-WITH-NITS
Source: /ship steps 8+9 (pr-review-toolkit:code-reviewer + silent-failure-hunter + adversarial 15-vector security test); findings fixed pre-push (commit 69300da)

## Security verdict
**No P0 sandbox escape.** The adversarial reviewer ran 15 attack vectors against the live seatbelt on
this host — direct golden read, file/dir/hard symlinks into evaluator-only/, subprocess `cat`/`sh`/
`osascript`/`curl`, alt-node binaries, `process.binding`, `npm install`, write-outside-tree — and
**every golden-content-read and network-exfil attempt was BLOCKED (EPERM)**. The silent-failure hunter
found **no silently-unsandboxed code path**. The boundary contains malicious model JS for the real
threat (reading/exfiltrating the held-out golden). Full triage: items/005-ship-blocked.md.

### Fixed pre-push (commit 69300da)
- **B1 (LIVE leak, adversarial V8 / code-reviewer P1-2)** — `(allow file-read-metadata)` was unscoped,
  letting model JS `stat()` a golden for its size+mtime (a size-based correctness oracle). Scoped to the
  read-allowlist subpaths (+ metadata-only `/private`,`/var` for node's ancestor `realpathSync`; goldens
  live under `/Users`, disjoint). **Re-verified independently:** `stat(golden)` → EPERM, `read(golden)`
  → EPERM, network → EPERM, node still starts, 3 integration tests pass.
- **B2 (NODE_BIN injection, code-reviewer P0-2)** — `node_dir` derived from `$NODE_BIN` fed the
  read-allowlist; now asserts the node install dir is not an ancestor of `evaluator-only/` (raises a
  trust-boundary RuntimeError) + unit test.
- **B3 (robustness, silent-failure P1-B)** — a sandbox-infra `OSError` at `Popen` now returns an
  `error`-status NodeFeedbackResult instead of crashing the trajectory + unit test.
- **B4 (least-privilege, code-reviewer P1-1)** — switched to inline `sandbox-exec -p <profile>` so no
  `.profile.sb` is written into the model-readable tree.

### Documented / accepted (no code change)
- **`(import "system.sb")`** (code-reviewer P0-1; adversarial V9 P3): required (node won't start without
  it — a hand-rolled mach/sysctl set aborts node, verified). Empirically NOT a golden leak — the golden
  is EPERM-blocked under it; system.sb only reaches world-readable `/private/etc/passwd` (no creds). The
  file-read policy stays fully enumerated/deny-default; system.sb covers only non-file process
  primitives. The `test_sandbox_blocks_evaluator_only_read` integration test guards against a future
  macOS broadening it. Documented in the module docstring.
- Sandbox-denied op classified `failed` (silent-failure P1-A): not silent — the EPERM text is merged
  into `output`. TAP/newer-node format + cleanup `ignore_errors` (Notes): pinned-node / resource-only.

## Verification after fixes
- 3 macOS integration security tests RAN + PASSED on this host (not skipped).
- `pytest -o addopts="" -q` → 1074 passed / 18 skipped / 0 failed.
- `ruff check .` + `ruff format --check .` clean. Oracle (node_edge.py, execution.py) byte-identical.
