# Oracle paths are disjoint from visible tests; oracle breadth is proven mechanically

Code-repair datasets (item 003, `code_repair_v1`, and every later generation
including Weeks 13-14 generated tasks) keep the oracle tests **path-disjoint**
from the visible tests: no `ExecutionSpec.held_out_tests` path may equal or
canonical-prefix-collide with any initial-tree path. The intuitive alternative —
the oracle as a literal superset of the visible suite — is rejected. Semantic
breadth is instead **proven mechanically** by the dataset's conformance suite:
the oracle run collects the *combined* tree (visible tests still count at
grading time), the stub check proves every oracle independently detects its
planted bug (visible tests overwritten with trivially-passing stubs, program
unrepaired, oracle still fails), and the hack-fixture check proves strict
breadth exactly where the taxonomy claims overfit resistance (a minimal
visible-suite-satisfying wrong patch passes the visible suite and fails the
oracle).

## Considered Options

- **Disjoint paths + mechanical breadth proof** (chosen). Disjointness makes
  the ADR-0010 overlay's displaced-path branch unreachable for authored
  content, makes the stub/hack checks well-defined (each suite is attributable
  to one side), and turns "the oracle is broader" from an unreviewable semantic
  claim into CI-proven facts.
- **Oracle ⊇ visible (literal superset).** Rejected: the superset property is
  only checkable as byte-duplication, duplicated content drifts, and an agent
  stubbing a visible test would be invisibly "compensated" by the oracle's copy
  rather than detected.
- **Disjointness as an authoring convention only (no conformance contract).**
  Rejected: unenforced, it erodes with the first generated dataset.

## Consequences

The conformance contract (disjoint paths, stub neutralization, hack-fixture
breadth) is the template every future code-repair dataset generation inherits;
item 004's failure classifier may assume an oracle non-pass is attributable to
the program, never to a visible-test/oracle path conflict. Because visible and
oracle files collect together in one pytest run, unique test-module basenames
across both sides become a dataset invariant (pytest's import-mismatch guard).
Rows are append-only, so revisiting this policy means a new dataset version and
a conformance rewrite — it is fixed for the code-repair lineage.
