# Recorded execution output is canonicalized, never verbatim

The reproducibility constraint (same file tree ⇒ byte-identical serialized
`ExecutionResult`) is unsatisfiable over verbatim subprocess output: tracebacks
embed the per-run random temp-dir root, and pytest's summary line prints
wall-clock seconds (`1 failed in 0.03s`). We therefore record **canonicalized
output**: a pure, unit-testable helper replaces every occurrence of the temp
root with the fixed placeholder `<sandbox>` and normalizes the pytest timing
token, then head-truncates at a fixed byte cap (8 KiB per stream at time of
writing) with an explicit truncation marker.

## Considered Options

- **Canonicalize, then record** (chosen). Keeps assertion details and
  tracebacks — the signal the agent and item 004's failure analysis need —
  while making byte-identity actually hold.
- **Drop stdout/stderr entirely**, rely on JUnit per-test data. Rejected: loses
  pre-collection crash output, exactly the case where the XML is absent.
- **Relax byte-identity to a field-subset comparison.** Rejected: weakens the
  MASTER-SPEC hard constraint and invites silent nondeterminism into the
  record.

## Consequences

Recorded output is *not* what the subprocess printed: `<sandbox>` paths and the
normalized timing token are deliberate, not bugs, and must not be "fixed". The
canonicalizer is part of the record's contract — changing it invalidates
byte-comparison against previously recorded artifacts. Wall-clock duration
remains excluded from `ExecutionResult` entirely; determinism of the record is
a property of the *canonicalized* form, never of raw streams.
