from agent_eval_lab.records.bash import (
    BashRequest,
    BashResult,
    bash_request_from_dict,
    bash_request_to_dict,
    bash_result_from_dict,
    bash_result_to_dict,
)


def test_bash_request_roundtrips():
    req = BashRequest(command="playwright-cli -s=S open http://x")
    assert bash_request_from_dict(bash_request_to_dict(req)) == req


def test_bash_result_roundtrips_and_is_frozen():
    res = BashResult(stdout="ok", stderr="", exit_code=0, timed_out=False)
    assert bash_result_from_dict(bash_result_to_dict(res)) == res
    d = bash_result_to_dict(res)
    assert d == {"stdout": "ok", "stderr": "", "exit_code": 0, "timed_out": False}


def test_bash_result_carries_no_wallclock():
    # Determinism: wall-clock is the one nondeterministic observable; it is absent.
    res = BashResult(stdout="", stderr="", exit_code=0, timed_out=False)
    assert "duration" not in bash_result_to_dict(res)
    assert "wall_time_s" not in bash_result_to_dict(res)
