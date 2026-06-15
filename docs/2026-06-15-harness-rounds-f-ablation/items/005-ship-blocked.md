# 005 — /ship steps 8+9 security review: hardening before push

Source: /ship steps 8 (code-reviewer + silent-failure-hunter) + 9 (adversarial, 15 attack vectors).
**No P0 sandbox-escape / golden-content-read / network-exfil found** (all 15 adversarial vectors
BLOCKED; no silently-unsandboxed path). Two confirmed leaks/holes + robustness fixed pre-push.

## Must-fix (security)

### B1 — `(allow file-read-metadata)` is unscoped → golden size/mtime oracle (adversarial V8, LIVE; code-reviewer P1-2)
`sandboxed_node_edge.py` `seatbelt_profile` emits a global `(allow file-read-metadata)`. Verified live:
model JS `fs.statSync('<golden>')` returns size+mtime. A model could compare its output byte-count to
the golden's size = a one-bit correctness signal (and the size flows back via NodeFeedbackResult.output).
**Fix:** scope `(allow file-read-metadata (subpath "{temp_tree}") (subpath "{node_dir}") <system subpaths>)`
to MATCH the read allowlist. **Empirically verify** node still starts AND `stat(golden)` is now blocked.

### B2 — NODE_BIN can inject the read-allowlist (code-reviewer P0-2)
`node_install_paths()` derives `node_dir` from `$NODE_BIN`; it is inserted verbatim into the profile's
read-allowlist. If `NODE_BIN` resolves so `node_dir` is an ancestor of `evaluator-only/`, the golden
becomes readable. **Fix:** after computing `install_dir`, assert it does NOT share a path prefix with /
contain the `evaluator-only/` canonical path (raise if it does). Defense-in-depth on the trust boundary.

## Should-fix (robustness on a security boundary)

### B3 — sandbox-infra error crashes the trajectory (silent-failure P1-B)
If `/usr/bin/sandbox-exec` passes the capability probe but fails at `Popen` (TOCTOU / removed / full
disk on profile write), the `OSError` propagates through `_fulfill` and crashes the run (the loop only
catches httpx errors). **Fix:** wrap the launch so an infra failure returns an `error`-status
NodeFeedbackResult, not an exception.

### B4 — profile written inside the readable tree (code-reviewer P1-1)
`.profile.sb` is written into `root` (read+write allowed), so node can read the allowlist. Low-risk (no
secret path is named in the profile — it's deny-default), but least-privilege says don't. **Fix:** use
`sandbox-exec -p <inline profile string>` (no file) — also removes the temp artifact. Update the
integration-test helper to match.

## Documented / accepted (no code change)
- **`(import "system.sb")`** (code-reviewer P0-1; adversarial V9 P3): empirically NOT a golden leak —
  the golden under `~/Documents/...` is EPERM-blocked; system.sb only reaches world-readable
  `/private/etc/passwd` (no creds, irrelevant). It is REQUIRED (a hand-rolled mach/sysctl set aborts
  node at startup, verified). The file-read policy stays fully enumerated/deny-default; system.sb covers
  only non-file process primitives. The integration test (`test_sandbox_blocks_evaluator_only_read`)
  guards the actual threat. Residual: a future macOS could broaden system.sb — the integration test
  would catch a golden-read regression. Document in the module docstring.
- **Sandbox-denied op classified `failed`** (silent-failure P1-A): not silent to the model — the EPERM
  text is merged into `output` (render_feedback_tail), so the trajectory record shows it. Accept.
- **TAP regex / newer-node format** (Note-C/P1-4): the eval is macOS-local on a pinned node (v16); exit
  code drives pass/fail (node exits non-zero on failure). Accept; note as a forward-compat limitation.
- **rmtree ignore_errors / cleanup race** (P1-3/Note-D): resource-leak only, post-sandbox. Accept.
