"""Execution edge: pure helpers + sandboxed pytest integration (ADR-0009)."""

import tempfile
from pathlib import Path

import pytest

from agent_eval_lab.records.execution import TestCaseResult
from agent_eval_lab.runners.pytest_edge import (
    canonicalize_output,
    materialize_tree,
    parse_junit_xml,
    run_pytest,
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


def test_materialize_tree_writes_sorted_nested_utf8(tmp_path: Path) -> None:
    materialize_tree(
        {"pkg/mod.py": "x = 'é'\n", "test_mod.py": "import pkg.mod\n"},
        tmp_path,
    )
    written = tmp_path / "pkg" / "mod.py"
    assert written.read_text(encoding="utf-8") == "x = 'é'\n"
    assert (tmp_path / "test_mod.py").read_text(encoding="utf-8") == (
        "import pkg.mod\n"
    )


def test_materialize_tree_refuses_escape_outside_root(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="outside sandbox"):
        materialize_tree({"../escape.py": "x = 1\n"}, tmp_path)


_PASSING_TREE = {
    "calc.py": "def add(a, b):\n    return a + b\n",
    "test_calc.py": (
        "from calc import add\n"
        "\n"
        "\n"
        "def test_add():\n"
        "    assert add(1, 2) == 3\n"
    ),
}

_FAILING_TREE = {
    "calc.py": "def add(a, b):\n    return a - b\n",
    "test_calc.py": (
        "from calc import add\n"
        "\n"
        "\n"
        "def test_add():\n"
        "    assert add(1, 2) == 3\n"
        "\n"
        "\n"
        "def test_zero():\n"
        "    assert add(0, 0) == 0\n"
    ),
}


def _sandbox_dirs() -> set:
    return set(Path(tempfile.gettempdir()).glob("agent-eval-sandbox-*"))


def test_run_pytest_passing_tree() -> None:
    result = run_pytest(_PASSING_TREE, timeout_s=30.0)
    assert result.status == "passed"
    assert result.exit_code == 0
    assert (result.passed, result.failed, result.errors, result.skipped) == (
        1,
        0,
        0,
        0,
    )
    assert result.tests == (
        TestCaseResult(test_id="test_calc::test_add", status="passed"),
    )
    assert "1 passed in <duration>" in result.stdout


def test_run_pytest_failing_tree_reports_per_test_statuses() -> None:
    result = run_pytest(_FAILING_TREE, timeout_s=30.0)
    assert result.status == "failed"
    assert result.exit_code == 1
    assert (result.passed, result.failed) == (1, 1)
    assert result.tests == (
        TestCaseResult(test_id="test_calc::test_add", status="failed"),
        TestCaseResult(test_id="test_calc::test_zero", status="passed"),
    )
    assert "1 failed, 1 passed in <duration>" in result.stdout
    assert "agent-eval-sandbox-" not in result.stdout


def test_run_pytest_cleans_up_its_sandbox() -> None:
    before = _sandbox_dirs()
    run_pytest(_PASSING_TREE, timeout_s=30.0)
    assert _sandbox_dirs() == before


def test_sandbox_env_hides_parent_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_LAB_SENTINEL", "leak-me")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake-secret")
    tree = {
        "test_env.py": (
            "import os\n"
            "\n"
            "\n"
            "def test_clean_env():\n"
            "    assert 'EVAL_LAB_SENTINEL' not in os.environ\n"
            "    assert 'OPENROUTER_API_KEY' not in os.environ\n"
        )
    }
    result = run_pytest(tree, timeout_s=30.0)
    assert result.status == "passed"
