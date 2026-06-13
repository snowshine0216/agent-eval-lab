from agent_eval_lab.records.execution import TestCaseResult
from agent_eval_lab.runners.junit import parse_junit_xml

_NODE_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
\t<testcase name="alpha pass" time="0.000688" classname="test"/>
\t<testcase name="beta fail" time="0.000072" classname="test">
\t\t<failure type="testCodeFailure" message="should not include 200"/>
\t</testcase>
</testsuites>
"""

def test_parse_node_junit_sorts_and_maps_statuses() -> None:
    assert parse_junit_xml(_NODE_XML) == (
        TestCaseResult(test_id="test::alpha pass", status="passed"),
        TestCaseResult(test_id="test::beta fail", status="failed"),
    )


def test_parse_junit_xml_raises_parse_error_on_malformed() -> None:
    # L1 premise: malformed/partial XML raises ET.ParseError (a SyntaxError
    # subclass), which node_edge.run_node_tests now guards and turns into an
    # error-status ExecutionResult rather than crashing the grading run.
    import xml.etree.ElementTree as ET

    import pytest

    with pytest.raises(ET.ParseError):
        parse_junit_xml('<testsuites><testcase name="x"')  # truncated, no close
