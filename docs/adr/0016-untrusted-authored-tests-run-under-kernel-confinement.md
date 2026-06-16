# Untrusted authored-test execution is kernel-confined, distinct from the trusted sandbox

Factor V of the F-domain harness ablation lets the model-under-test write its own
JavaScript (**authored tests**) and run them via `run_tests` for
self-verification feedback. That is **untrusted code** executing as the evaluator
OS user. The existing **sandbox** (ADR-0009; CONTEXT.md) is deliberately
*convention-level, not kernel-level — "no containers"* because it only ever ran
**trusted** oracle/evaluator code. Run untrusted code under it and the model can
read the held-out **oracle tests** / `evaluator-only` golden store by absolute
path and print them to stdout (which is returned mid-trajectory to the model),
and can exfiltrate over the network — defeating the held-out design (D19/D33). We
therefore run authored tests under a separate, kernel-enforced tier —
**confined execution** — and leave the trusted sandbox untouched.

## Decision

On macOS, `runners/sandboxed_node_edge.py` wraps `node --test` in a
`sandbox-exec` (seatbelt) profile that is **deny-read-by-default with an explicit
read-allowlist** (the candidate temp tree + the node binary + the enumerated
system paths node needs to start: `/usr/lib`, `/System`, the dyld shared cache,
`/usr/bin:/bin:<node parent>`), plus `(deny network*)` and write-deny outside the
tree. The trusted **oracle edge** keeps its existing convention-level **sandbox**
unchanged (so its frozen `ExecutionResult` records and the ADR-0009 contract are
preserved).

## Considered Options

- **seatbelt read-allowlist** (chosen). No daemon dependency; pure-local on the
  macOS dev box. Brittle across node/macOS versions (the allowlist must enumerate
  node's actual read dependencies) and macOS-only — V execution **skips on Linux
  CI**, where the executor is injected as a fake (the ablation is declared
  macOS-local-only, so a CI skip cannot void or bias results).
- **Docker `--network none`, temp-tree-only mount** (pre-authorized fallback).
  Hermetic read-confinement by construction and portable; requires Docker running
  and has heavier per-run startup. Adopted automatically if the seatbelt
  allowlist cannot be made to *both* start node *and* block an `evaluator-only`
  read — no further decision needed.
- **Broad `(allow file-read*)` + `(deny network*)`** (rejected). Insufficient:
  model JS reads the golden and prints it to stdout, which is returned to the
  model in-trajectory; denying the network does not close that channel. The
  allowlist, not a blanket read-allow, is the boundary.
- **Reserved-path provenance / static-analyzing the model's JS** (rejected). The
  reserved `tests/authored/` path controls *which files run*, not *what they
  read*; static analysis of test code is an obfuscation arms race. Neither is a
  security boundary — both are defense-in-depth at most.

## Consequences

- This reverses the documented "no kernel isolation, no containers" limitation of
  **sandbox** — but **only** for the untrusted authored-test tier. The trusted
  oracle/execution edge is unchanged, so ADR-0009's frozen-record byte-identity
  still holds for grading.
- The macOS integration test for this tier must prove **both** that node starts
  under the profile **and** that an `evaluator-only` read and a network call are
  blocked — a half-built profile that silently allows reads is worse than none.
- `confined execution` and `sandbox` are now distinct glossary terms separated by
  *trust model*; conflating them re-opens the leak this ADR closes.
