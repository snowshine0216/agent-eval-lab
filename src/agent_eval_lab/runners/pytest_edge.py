"""EDGE: the sandboxed pytest execution boundary (ADR-0008, ADR-0009).

The single place subprocess/filesystem I/O happens for code-world:
materialize the file tree into a fresh temp dir, run pinned-interpreter
(`sys.executable`) pytest in a scrubbed from-scratch environment under a
hard timeout, parse the JUnit XML, canonicalize the output, clean up in a
`finally`.

Known limitation (documented, restated by item 004): no kernel-level
network isolation on macOS without containers — mitigated by the env scrub
(no proxy vars), the tight default timeout, and the item-003 rubric banning
network-touching tasks. On timeout, partial output is discarded (it is
timing-dependent, hence nondeterministic): the record carries empty streams
and exit code -9 (the SIGKILL convention).
"""

import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path

from agent_eval_lab.records.execution import (
    SuiteStatus,
    TestCaseResult,
    TestStatus,
)

SANDBOX_PLACEHOLDER = "<sandbox>"
_TIMING_TOKEN = re.compile(r"in \d+(?:\.\d+)?s\b")


def canonicalize_output(text: str, root: str) -> str:
    """Replace the sandbox root and pytest timing token (ADR-0009). Pure."""
    return _TIMING_TOKEN.sub(
        "in <duration>", text.replace(root, SANDBOX_PLACEHOLDER)
    )


def _case_status(case: ET.Element) -> TestStatus:
    if case.find("failure") is not None:
        return "failed"
    if case.find("error") is not None:
        return "error"
    if case.find("skipped") is not None:
        return "skipped"
    return "passed"


def parse_junit_xml(xml_text: str) -> tuple[TestCaseResult, ...]:
    """Extract per-test entries sorted by `classname::name`. Pure."""
    cases = (
        TestCaseResult(
            test_id=f"{case.get('classname', '')}::{case.get('name', '')}",
            status=_case_status(case),
        )
        for case in ET.fromstring(xml_text).iter("testcase")
    )
    return tuple(sorted(cases, key=lambda case: case.test_id))


def suite_status(exit_code: int) -> SuiteStatus:
    """Pytest exit-code classification: 0/1/5 named; 2-4 (and rest) error."""
    if exit_code == 0:
        return "passed"
    if exit_code == 1:
        return "failed"
    if exit_code == 5:
        return "no_tests"
    return "error"


def materialize_tree(files: Mapping[str, str], root: Path) -> None:
    """Write the tree under root: sorted order, parents created, UTF-8.

    Defense in depth: refuses any resolved target outside root, even though
    the pure tools already reject non-canonical paths.
    """
    resolved_root = root.resolve()
    for path in sorted(files):
        target = (resolved_root / path).resolve()
        if not target.is_relative_to(resolved_root):
            raise RuntimeError(
                f"refusing to materialize outside sandbox: {path!r}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[path], encoding="utf-8")
