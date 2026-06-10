# OnlyModifies uses leaf-path prefix coverage, not exact-path matching

`OnlyModifies(paths)` grades policy by diffing `initial_state` against
`trajectory.final_state`, computing the set of changed *leaf* dot-paths, and
permitting a change iff some declared path is **equal to or a prefix of** the
changed path. A change to any leaf not covered by a declared prefix fails with
`forbidden_action`.

## Considered Options

- **Prefix coverage** (chosen). `OnlyModifies(paths=("tickets.T-1",))` permits
  any change *under* `tickets.T-1` (e.g. `tickets.T-1.status`,
  `tickets.T-1.assignee`) while forbidding edits elsewhere. This is the behavior
  the design's own example (§4.3) intends — the declared path names a subtree,
  not a single leaf.
- **Exact-path matching.** Rejected: the design example would then forbid the
  status edit it is clearly meant to permit, because the changed leaf
  (`tickets.T-1.status`) is never literally equal to the declared subtree
  (`tickets.T-1`).

## Consequences

Path coverage is segment-aware (a declared `tickets.T-1` covers
`tickets.T-1.status` but NOT `tickets.T-10.status`), so prefix matching is on
dot-segment boundaries, not raw string prefixes. Dataset authors declare the
*subtree* an agent may touch; the grader treats every leaf outside those
subtrees as a forbidden modification. This makes `OnlyModifies` the side-effect
allowlist the composite-verification design depends on.

## Amendment (2026-06-10)

Empty mappings contribute no leaves at any depth: `_leaf_paths` treats an empty
Mapping as nothing (no entry emitted), whether at the root or nested. As a
consequence, creation or deletion of an *empty* container is invisible to
`OnlyModifies` (e.g. `{}` → `{"tickets": {}}` detects no change). This is a
known, accepted blind spot of leaf-diff semantics. The rationale: the previous
asymmetric behaviour (empty mapping at root → no leaves; nested → phantom leaf
`{prefix: {}}`) produced false FAILs (wrong grades) when an agent correctly
populated a subtree whose initial value was an empty container — suppressing
`pass^k` signal on valid runs. Eliminating phantom-path false FAILs is the
higher-priority correctness property; not policing unobservable empty-container
creation is the accepted trade-off.
