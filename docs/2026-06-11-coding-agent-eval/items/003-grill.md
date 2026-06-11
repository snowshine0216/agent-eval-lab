Verdict: PASS

Subagent: fable
Questions resolved: 16
Docs touched (commit 62edaac):
  - CONTEXT.md (terms updated: Difficulty knob, world_template_id, version
    (dataset), oracle tests; terms added: sidecar (dataset), visible tests,
    distractor file, bug class, hack fixture, reference solution)
  - docs/adr/0012-oracle-paths-disjoint-from-visible-tests-breadth-proven-mechanically.md (new)
Spec refined: items/003-spec.md (commit 62edaac)

## Resolved decisions

- Q: Criterion 10 admits only `failed` | `no_tests` — a green visible suite plus
  a prose bug report is unrepresentable. Gap or deliberate?
  A: Deliberate for v1: prose-only = zero visible test files; the third symptom
  shape is deferred to a future version.
  Rationale: a tri-state breaks the binary mechanical check; 15 tasks cannot also
  carry a new capability variant.
  Doc impact: criterion 10 sharpened; CONTEXT.md term visible tests.

- Q: What is a "visible test file", given pytest defaults collect both
  `test_*.py` and `*_test.py`?
  A: Basename `test_*.py` only; `*_test.py` basenames banned in every fixture
  tree so the convention equals collection.
  Rationale: a `foo_test.py` would be collected by the sandbox but escape the
  stub/symptom conformance checks.
  Doc impact: spec criteria 7/10; CONTEXT.md term visible tests.

- Q: Criterion 11 required every reference tree to "pass the visible suite" —
  what does a prose-only task pass?
  A: `passed` where visible tests exist; `no_tests` for prose-only tasks.
  Rationale: the original wording was unsatisfiable for prose-only tasks.
  Doc impact: criterion 11 struck + corrected.

- Q: Is the visible/oracle disjointness policy ADR-worthy?
  A: Yes — ADR-0012: disjoint oracle paths; breadth proven mechanically (stub
  neutralization + hack fixtures); literal superset rejected.
  Rationale: three-of-three — frozen append-only rows, surprising vs the common
  oracle ⊇ visible expectation, real trade-off; constrains item 004's classifier
  and the Weeks 13-14 generator.
  Doc impact: ADR-0012; criterion 8 cross-ref; CONTEXT.md oracle tests.

- Q: CONTEXT.md defined the difficulty knob as "a closed vocabulary" listing only
  the five workspace knobs — the code dialect contradicts the glossary.
  A: Knob vocabularies are per-world dialects; names never reused across dialects
  with mutated meanings.
  Rationale: the spec already chose a code dialect; the glossary had to say so.
  Doc impact: CONTEXT.md term Difficulty knob.

- Q: CONTEXT.md's world_template_id reads as one template per dataset; 15
  per-task templates breaks that reading.
  A: Granularity is a per-dataset declaration; code_repair_v1 declares one
  program family per task.
  Rationale: the template is the Weeks 9-10 split isolation boundary; one shared
  id would force the dataset into a single partition.
  Doc impact: CONTEXT.md term world_template_id.

- Q: Is `version="1"` a regression while workspace sits at `"2"`?
  A: No — the version counter is scoped to its dataset lineage; lineages count
  independently.
  Rationale: prevents a future reader "fixing" code_repair_v1 to version "3".
  Doc impact: CONTEXT.md term version (dataset).

- Q: The dotted-path ambiguity guard claimed coverage of "every tree the task can
  reach" — can it?
  A: No. The guard covers fixture-shipped trees (now including hack trees); an
  agent minting a fresh extension path (e.g. writing `app.py.bak` itself) is
  silently covered by an `app.py` allowlist entry — a graders/policy.py residual
  named in criterion 16 so item 004 classifies it as harness, not task.
  Rationale: static dataset checks cannot enumerate agent-created paths;
  overclaiming soundness corrupts the downstream failure taxonomy.
  Doc impact: criterion 16 + Open-questions 12 struck/corrected.

- Q: The hermeticity banlist omits `os` and `tempfile` — floor too low?
  A: Add both; the list stays closed at 15 modules.
  Rationale: os.urandom/os.environ/os.system and RNG-named tempfile I/O are the
  remaining one-import nondeterminism surfaces; stdlib micro-programs need
  neither.
  Doc impact: criterion 19 extended.

- Q: Does append-only freezing cover the sidecars, and do solutions in the
  review-fixtures sidecar threaten the finetune data boundary?
  A: Sidecars freeze with the dataset version; the review-fixtures sidecar joins
  the Weeks 9-10 never-train manifest.
  Rationale: sidecars key frozen row ids; the fixtures file carries solutions
  that must never leak into training data in the eval→data→finetune program.
  Doc impact: Constraints extended; CONTEXT.md term sidecar (dataset).

- Q: Do the code-repair fixture concepts get canonical names?
  A: Yes: visible tests, distractor file, bug class, hack fixture, reference
  solution, sidecar (dataset).
  Rationale: item 004's report and the Weeks 13-14 generator need these words;
  naming once prevents another "rubric"-style overload.
  Doc impact: CONTEXT.md, six terms added.

- Q: Criterion 20's "non-trivial line" had no definition — same as criterion 15's?
  A: Same: stripped lines > 3 chars.
  Rationale: two leakage proxies, one threshold.
  Doc impact: criterion 20 sharpened.

- Q: "Shared system turn" — how shared, and how many turns?
  A: Exactly two message turns per task; the system turn byte-identical across
  all 15 rows.
  Rationale: mechanically checkable; mirrors v2; keeps item 004's prompt-config
  comparison clean.
  Doc impact: criterion 1 sharpened.

- Q: code_world's reserved-name check is root-level only — is a nested
  `pkg/sitecustomize.py` acceptable in fixtures?
  A: No — reserved basenames banned at any depth in all four fixture-tree kinds.
  Rationale: inert-in-sandbox-but-live-under-plain-pytest files are the authoring
  trap the spec already bans for conftest.py.
  Doc impact: criterion 7 sharpened.

- Q: Does the tier-sidecar shape claim hold against the report tooling?
  A: Yes — verified in code: cli.py json.loads a flat {task_id: tier} map;
  reports/validation.py and comparison.py consume it via tier_of.
  Rationale: criterion 3's "reads it unchanged" stands.
  Doc impact: none.

- Q: A no-op trajectory trivially passes every policy leg — does criterion 12's
  "fails every task" hold on AllOf tasks?
  A: Yes — AllOf ANDs all legs (ADR-0003); the ExecutionSpec leg fails on the
  planted bug, so the composite fails. Conformance asserts the composite verdict.
  Rationale: verified against grade_trajectory/grade_all_of semantics.
  Doc impact: none.
