"""Execution edge: pure helpers + sandboxed pytest integration (ADR-0009)."""

import pytest

from agent_eval_lab.records.execution import TestCaseResult
from agent_eval_lab.runners.pytest_edge import (
    canonicalize_output,
    parse_junit_xml,
    suite_status,
)

_JUNIT_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
<testsuite name="pytest" errors="0" failures="1" skipped="1" tests="3">
<testcase classname="test_calc" name="test_zero" time="0.001" />
<testcase classname="test_calc" name="test_add" time="0.001">
<failure message="assert -1 == 3">trace</failure>
</testcase>
<testcase classname="test_calc" name="test_later" time="0.000">
<skipped type="pytest.skip" message="later">reason</skipped>
</testcase>
</testsuite>
</testsuites>
"""


def test_canonicalize_output_replaces_root_and_timing_token() -> None:
    raw = (
        "ImportError in '/tmp/agent-eval-sandbox-x1/test_a.py'\n"
        "1 failed, 1 passed in 0.01s\n"
    )
    expected = (
        "ImportError in '<sandbox>/test_a.py'\n"
        "1 failed, 1 passed in <duration>\n"
    )
    assert canonicalize_output(raw, "/tmp/agent-eval-sandbox-x1") == expected


def test_canonicalize_output_normalizes_no_tests_summary() -> None:
    assert (
        canonicalize_output("no tests ran in 0.00s", "/r")
        == "no tests ran in <duration>"
    )


def test_parse_junit_xml_sorts_by_test_id_and_maps_statuses() -> None:
    assert parse_junit_xml(_JUNIT_XML) == (
        TestCaseResult(test_id="test_calc::test_add", status="failed"),
        TestCaseResult(test_id="test_calc::test_later", status="skipped"),
        TestCaseResult(test_id="test_calc::test_zero", status="passed"),
    )


@pytest.mark.parametrize(
    ("exit_code", "status"),
    [
        (0, "passed"),
        (1, "failed"),
        (2, "error"),
        (3, "error"),
        (4, "error"),
        (5, "no_tests"),
    ],
)
def test_suite_status_classifies_pytest_exit_codes(
    exit_code: int, status: str
) -> None:
    assert suite_status(exit_code) == status
