"""Execution edge: pure helpers + sandboxed pytest integration (ADR-0009)."""

import json
import tempfile
from pathlib import Path

import pytest

from agent_eval_lab.records.execution import (
    TestCaseResult,
    execution_result_to_dict,
)
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
        "ImportError in '<sandbox>/test_a.py'\n1 failed, 1 passed in <duration>\n"
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
def test_suite_status_classifies_pytest_exit_codes(exit_code: int, status: str) -> None:
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


def test_materialize_tree_raises_on_casefold_collision(tmp_path: Path) -> None:
    """Defense in depth: two distinct keys that casefold to the same string."""
    with pytest.raises(RuntimeError, match="case"):
        materialize_tree({"a/Foo.py": "x = 1\n", "a/foo.py": "x = 2\n"}, tmp_path)


def test_materialize_tree_raises_on_nfc_nfd_collision(tmp_path: Path) -> None:
    """Defense in depth: NFC and NFD spellings of the same path are unsafe on APFS."""
    # NFC: U+00E9 precomposed LATIN SMALL LETTER E WITH ACUTE
    nfc_path = "café.py"
    # NFD: U+0065 + U+0301 combining LATIN SMALL LETTER E + COMBINING ACUTE ACCENT
    nfd_path = "café.py"
    with pytest.raises(RuntimeError, match="collision"):
        materialize_tree({nfc_path: "x = 1\n", nfd_path: "x = 2\n"}, tmp_path)


def test_materialize_tree_raises_on_dir_segment_case_collision(tmp_path: Path) -> None:
    """Defense in depth: 'A/x.py' and 'a/y.py' collapse on APFS."""
    with pytest.raises(RuntimeError, match="collision"):
        materialize_tree({"A/x.py": "x = 1\n", "a/y.py": "y = 2\n"}, tmp_path)


def test_materialize_tree_allows_same_dir_distinct_files(tmp_path: Path) -> None:
    """a/x.py and a/y.py in the same identically-spelled dir is safe."""
    materialize_tree({"a/x.py": "x = 1\n", "a/y.py": "y = 2\n"}, tmp_path)
    assert (tmp_path / "a" / "x.py").read_text(encoding="utf-8") == "x = 1\n"
    assert (tmp_path / "a" / "y.py").read_text(encoding="utf-8") == "y = 2\n"


def test_materialize_tree_raises_on_junit_xml_key(tmp_path: Path) -> None:
    """Defense in depth: .junit.xml key must be refused at materialization."""
    with pytest.raises(RuntimeError, match=r"\.junit\.xml"):
        materialize_tree({".junit.xml": "<xml/>\n"}, tmp_path)


# --- Finding 002 (item 002): sitecustomize.py / usercustomize.py reservation ---


def test_materialize_tree_raises_on_root_sitecustomize_py(tmp_path: Path) -> None:
    """Defense in depth: root sitecustomize.py is reserved by the harness."""
    with pytest.raises(RuntimeError, match="reserved"):
        materialize_tree({"sitecustomize.py": "import sys\n"}, tmp_path)


def test_materialize_tree_raises_on_root_usercustomize_py(tmp_path: Path) -> None:
    """Defense in depth: root usercustomize.py is reserved by the harness."""
    with pytest.raises(RuntimeError, match="reserved"):
        materialize_tree({"usercustomize.py": "import sys\n"}, tmp_path)


def test_materialize_tree_allows_nested_sitecustomize_py(tmp_path: Path) -> None:
    """pkg/sitecustomize.py is not on PYTHONPATH root — must be allowed."""
    materialize_tree({"pkg/sitecustomize.py": "x = 1\n"}, tmp_path)
    written = (tmp_path / "pkg" / "sitecustomize.py").read_text(encoding="utf-8")
    assert written == "x = 1\n"


def test_sitecustomize_attack_is_rejected_by_check_tree_invariants() -> None:
    """RED test: build the attack tree (broken module + oracle-style test +
    root sitecustomize.py that patches the broken module via sys.modules).

    BEFORE the fix: run_pytest returns status='passed' (fraudulent PASS).
    AFTER the fix: _check_tree_invariants raises RuntimeError, so the attack
    tree never reaches subprocess execution.

    This test verifies the post-fix behavior: RuntimeError is raised.
    """
    from agent_eval_lab.runners.pytest_edge import _check_tree_invariants

    sitecustomize_payload = (
        "import sys\n"
        "import types\n"
        "\n"
        "# Patch the broken module before any test imports it\n"
        "_m = types.ModuleType('calc')\n"
        "_m.add = lambda a, b: a + b\n"
        "sys.modules['calc'] = _m\n"
    )
    attack_tree = {
        "calc.py": "def add(a, b):\n    return a - b\n",  # broken
        "test_oracle_calc.py": (
            "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
        ),
        "sitecustomize.py": sitecustomize_payload,
    }
    with pytest.raises(RuntimeError, match="reserved"):
        _check_tree_invariants(attack_tree)


def test_sitecustomize_attack_passes_fraudulently_without_fix() -> None:
    """RED test: demonstrate that the attack tree WOULD pass (fraudulent PASS)
    if run_pytest were called with the attack tree directly, bypassing
    _check_tree_invariants.

    We run the tree bypassing the invariant guard to prove the attack works.
    After the fix the guard blocks the tree, but this test still documents
    the pre-fix attack vector by directly invoking _execute (bypassing the guard).
    This test uses monkeypatching to skip _check_tree_invariants.
    """
    import shutil
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from agent_eval_lab.runners.pytest_edge import _execute, materialize_tree

    sitecustomize_payload = (
        "import sys\n"
        "import types\n"
        "\n"
        "_m = types.ModuleType('calc')\n"
        "_m.add = lambda a, b: a + b\n"
        "sys.modules['calc'] = _m\n"
    )
    attack_tree = {
        "calc.py": "def add(a, b):\n    return a - b\n",
        "test_oracle_calc.py": (
            "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
        ),
        "sitecustomize.py": sitecustomize_payload,
    }
    root = Path(tempfile.mkdtemp(prefix="agent-eval-sandbox-test-")).resolve()
    try:
        # Materialize bypassing the invariant check (simulating the pre-fix state)
        with patch(
            "agent_eval_lab.runners.pytest_edge._check_tree_invariants",
            return_value=None,
        ):
            materialize_tree(attack_tree, root)
        result = _execute(root, timeout_s=30.0)
        # The attack succeeds: the broken calc.add is patched via sitecustomize.py
        # so the oracle test passes — this is the fraudulent PASS.
        assert result.status == "passed", (
            f"Expected fraudulent PASS to demonstrate the attack, got {result.status!r}"
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


# --- end Finding 002 ---


_PASSING_TREE = {
    "calc.py": "def add(a, b):\n    return a + b\n",
    "test_calc.py": (
        "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
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


def test_run_pytest_collection_error_tree() -> None:
    result = run_pytest({"test_broken.py": "import missing_module\n"}, timeout_s=30.0)
    assert result.status == "error"
    assert result.exit_code == 2
    assert result.errors == 1
    assert result.tests == (TestCaseResult(test_id="::test_broken", status="error"),)
    assert "<sandbox>" in result.stdout
    assert "agent-eval-sandbox-" not in result.stdout


def test_run_pytest_no_tests_tree() -> None:
    result = run_pytest({"calc.py": "x = 1\n"}, timeout_s=30.0)
    assert result.status == "no_tests"
    assert result.exit_code == 5
    assert result.tests == ()
    assert "no tests ran in <duration>" in result.stdout


def test_run_pytest_counts_skipped_tests() -> None:
    tree = {
        "test_skip.py": (
            "import pytest\n"
            "\n"
            "\n"
            "def test_ok():\n"
            "    assert True\n"
            "\n"
            "\n"
            "@pytest.mark.skip(reason='later')\n"
            "def test_later():\n"
            "    assert False\n"
        )
    }
    result = run_pytest(tree, timeout_s=30.0)
    assert result.status == "passed"
    assert result.exit_code == 0
    assert (result.passed, result.skipped) == (1, 1)
    assert result.tests == (
        TestCaseResult(test_id="test_skip::test_later", status="skipped"),
        TestCaseResult(test_id="test_skip::test_ok", status="passed"),
    )


def test_run_pytest_timeout_is_structured_and_reaped() -> None:
    tree = {"test_hang.py": ("import time\n\n\ndef test_hang():\n    time.sleep(30)\n")}
    before = _sandbox_dirs()
    result = run_pytest(tree, timeout_s=1.0)
    assert result.status == "timeout"
    assert result.exit_code == -9
    assert result.tests == ()
    assert (result.passed, result.failed, result.errors, result.skipped) == (
        0,
        0,
        0,
        0,
    )
    assert result.stdout == ""
    assert result.stderr == ""
    assert _sandbox_dirs() == before


def test_run_pytest_corrupt_junit_xml_returns_error_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corrupt JUnit XML must produce an error record, not crash the eval run."""
    original_read_text = Path.read_text

    def _corrupt_read_text(self: Path, *args, **kwargs) -> str:  # type: ignore[override]
        text = original_read_text(self, *args, **kwargs)
        if self.name == ".junit.xml":
            return "not valid xml <<<"
        return text

    monkeypatch.setattr(Path, "read_text", _corrupt_read_text)

    result = run_pytest(_PASSING_TREE, timeout_s=30.0)

    assert result.status == "error"
    assert result.tests == ()
    assert result.passed == 0
    assert result.failed == 0
    assert result.errors == 0
    assert result.skipped == 0
    assert "junit-xml-parse-error:" in result.stderr


def test_run_pytest_is_byte_identical_across_runs() -> None:
    first = run_pytest(_FAILING_TREE, timeout_s=30.0)
    second = run_pytest(_FAILING_TREE, timeout_s=30.0)
    first_bytes = json.dumps(execution_result_to_dict(first), sort_keys=True).encode(
        "utf-8"
    )
    second_bytes = json.dumps(execution_result_to_dict(second), sort_keys=True).encode(
        "utf-8"
    )
    assert first_bytes == second_bytes
