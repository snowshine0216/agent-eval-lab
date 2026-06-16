# tests/runners/test_claude_cli_candidate.py
import json
import pytest
from agent_eval_lab.runners.claude_cli_candidate import (
    ClaudeRunMeta,
    ClaudeResultParseError,
    parse_claude_result,
)


def _result_json(**over):
    base = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 7,
        "total_cost_usd": 0.0123,
        "usage": {"input_tokens": 1500, "output_tokens": 320},
        "result": "done",
    }
    base.update(over)
    return json.dumps(base)


def test_parse_happy_path_maps_usage_and_turns():
    meta = parse_claude_result(_result_json())
    assert meta == ClaudeRunMeta(
        prompt_tokens=1500,
        completion_tokens=320,
        num_turns=7,
        total_cost_usd=0.0123,
        is_error=False,
    )


def test_parse_is_error_true_is_carried():
    meta = parse_claude_result(_result_json(is_error=True, subtype="error_max_turns"))
    assert meta.is_error is True


def test_parse_malformed_json_raises_typed_error():
    with pytest.raises(ClaudeResultParseError):
        parse_claude_result("not json {")


def test_parse_missing_usage_raises_typed_error():
    with pytest.raises(ClaudeResultParseError):
        parse_claude_result(json.dumps({"type": "result", "is_error": False}))


# ---- Task 2: SURFACES, claude_system_prompt, build_claude_argv ----------------
from agent_eval_lab.runners.claude_cli_candidate import (
    SURFACES,
    build_claude_argv,
    claude_system_prompt,
)


def test_surfaces_are_the_two_expected():
    assert SURFACES == ("edit-only", "natural")


def test_system_prompt_differs_only_by_run_tests_line():
    edit = claude_system_prompt("edit-only")
    nat = claude_system_prompt("natural")
    assert "Do not attempt to run tests" in edit
    assert "Do not attempt to run tests" not in nat
    # No Factor-P scaffolding leaks into either baseline.
    assert "gather context" not in edit.lower()
    assert "gather context" not in nat.lower()
    # Identical apart from that one sentence.
    assert edit.replace("\n\nDo not attempt to run tests.", "").strip() == nat.strip()


def test_argv_edit_only_denies_bash_and_disables_skills():
    argv = build_claude_argv(
        model="claude-sonnet-4-6",
        surface="edit-only",
        prompt="fix it",
        system_prompt="SYS",
        max_budget_usd=0.5,
    )
    assert argv[0] == "claude"
    assert "-p" in argv
    assert "--output-format" in argv and "json" in argv
    assert "--disable-slash-commands" in argv
    assert "--model" in argv and "claude-sonnet-4-6" in argv
    # Bash denied on edit-only; Read/Edit/Write allowed.
    deny = argv[argv.index("--disallowedTools") + 1]
    assert "Bash" in deny
    allow = argv[argv.index("--allowedTools") + 1]
    assert "Read" in allow and "Edit" in allow and "Write" in allow
    assert "Bash" not in allow
    # Prompt is the trailing positional.
    assert argv[-1] == "fix it"


def test_argv_natural_allows_bash():
    argv = build_claude_argv(
        model="claude-sonnet-4-6",
        surface="natural",
        prompt="fix it",
        system_prompt="SYS",
        max_budget_usd=0.5,
    )
    allow = argv[argv.index("--allowedTools") + 1]
    assert "Bash" in allow
    deny = argv[argv.index("--disallowedTools") + 1]
    assert "Bash" not in deny


def test_argv_rejects_unknown_surface():
    with pytest.raises(ValueError):
        build_claude_argv(
            model="m", surface="bogus", prompt="p", system_prompt="s", max_budget_usd=0.5
        )


# ---- Task 3: materialize_tree + read_back_tree --------------------------------
from pathlib import Path
from agent_eval_lab.runners.claude_cli_candidate import (
    materialize_tree,
    read_back_tree,
)


def test_materialize_then_read_back_round_trips(tmp_path):
    tree = {
        "src/a.js": "console.log(1)\n",
        "nested/dir/b.txt": "hello\n",
    }
    materialize_tree(tree, tmp_path)
    assert (tmp_path / "src/a.js").read_text() == "console.log(1)\n"
    assert read_back_tree(tmp_path) == tree


def test_read_back_ignores_git_and_node_modules(tmp_path):
    materialize_tree({"keep.js": "x\n"}, tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("y\n")
    assert read_back_tree(tmp_path) == {"keep.js": "x\n"}


def test_read_back_includes_files_claude_created(tmp_path):
    materialize_tree({"a.js": "1\n"}, tmp_path)
    (tmp_path / "new.js").write_text("2\n")
    assert read_back_tree(tmp_path) == {"a.js": "1\n", "new.js": "2\n"}
