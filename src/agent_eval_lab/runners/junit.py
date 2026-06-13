"""Pure JUnit-XML parsing shared by the pytest and node test edges."""

import xml.etree.ElementTree as ET

from agent_eval_lab.records.execution import TestCaseResult, TestStatus


def case_status_of(case: ET.Element) -> TestStatus:
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
            status=case_status_of(case),
        )
        for case in ET.fromstring(xml_text).iter("testcase")
    )
    return tuple(sorted(cases, key=lambda case: case.test_id))
