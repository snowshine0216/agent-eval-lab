from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.reports.edit_paths import EditPaths, edit_paths


def _traj(turns):
    return Trajectory(
        turns=tuple(turns),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0,
        stop_reason="completed_natural",
        rounds=len(turns),
    )


def test_collects_str_replace_and_write_file_targets():
    traj = _traj([
        MessageTurn(role="assistant", content="ok"),
        ToolCallTurn(tool_calls=(
            ToolCall(call_id="c1", name="str_replace", arguments={"path": "wdio.conf.ts"}),
            ToolCall(call_id="c2", name="write_file", arguments={"path": "index.ts", "content": "x"}),
        )),
    ])
    out = edit_paths(traj, target_paths=("wdio.conf.ts",))
    assert out == EditPaths(
        edited=("index.ts", "wdio.conf.ts"),
        out_of_scope=("index.ts",),
    )


def test_dedups_repeated_edits():
    traj = _traj([
        ToolCallTurn(tool_calls=(
            ToolCall(call_id="c1", name="str_replace", arguments={"path": "a.ts"}),
            ToolCall(call_id="c2", name="str_replace", arguments={"path": "a.ts"}),
        )),
    ])
    out = edit_paths(traj, target_paths=("a.ts",))
    assert out.edited == ("a.ts",)
    assert out.out_of_scope == ()


def test_unknown_edit_tool_contributes_no_path():
    traj = _traj([
        ToolCallTurn(tool_calls=(
            ToolCall(call_id="c1", name="read_file", arguments={"path": "a.ts"}),
            ToolCall(call_id="c2", name="list_files", arguments={}),
        )),
    ])
    out = edit_paths(traj, target_paths=("a.ts",))
    assert out.edited == ()
    assert out.out_of_scope == ()


def test_missing_path_argument_is_fail_quiet():
    traj = _traj([
        ToolCallTurn(tool_calls=(
            ToolCall(call_id="c1", name="write_file", arguments={"content": "x"}),
        )),
    ])
    out = edit_paths(traj, target_paths=())
    assert out.edited == ()
