from agent_eval_lab.records.bash import BashRequest, BashResult
from agent_eval_lab.runners.bash_edge import (
    DEFAULT_TIMEOUT_S,
    make_bash_executor,
    parse_argv,
)


def test_parse_argv_rejects_shell_metacharacters():
    # `;`, `|`, `&` must not be honoured — one program per call.
    assert parse_argv("playwright-cli -s=S open http://x") == [
        "playwright-cli", "-s=S", "open", "http://x"
    ]
    assert parse_argv("playwright-cli x ; rm -rf /") is None  # contains `;`
    assert parse_argv("cmd | bash") is None  # contains `|`


def test_parse_argv_rejects_path_in_argv0():
    # review N1: a slash-containing argv[0] would bypass the name-based allowlist
    # (shutil.which resolves the path directly) — require a bare binary name.
    assert parse_argv("/usr/local/bin/playwright-cli open http://x") is None
    assert parse_argv("./playwright-cli open http://x") is None
    assert parse_argv("../evil/playwright-cli open http://x") is None


def test_parse_argv_allows_arrow_function_in_eval():
    # `>` inside a quoted JS arrow function is safe with shell=False and must
    # be allowed (the playwright-cli eval command uses this pattern).
    result = parse_argv('playwright-cli -s=S eval "() => document.body.innerText"')
    assert result is not None
    assert result[0] == "playwright-cli"
    assert "() => document.body.innerText" in result[-1]


def test_make_bash_executor_runs_an_allowed_command(tmp_path):
    # `true` is temporarily allowlisted via the env hook so this test needs no
    # network; production ALLOWED_BINS is {"playwright-cli"}.
    executor, close = make_bash_executor(
        session_id="t", workdir=tmp_path, allowed_bins=frozenset({"true"})
    )
    try:
        res = executor(BashRequest(command="true"))
        assert isinstance(res, BashResult)
        assert res.exit_code == 0
        assert res.timed_out is False
    finally:
        close()


def test_disallowed_binary_is_127_never_executed(tmp_path):
    executor, close = make_bash_executor(session_id="t", workdir=tmp_path)
    try:
        res = executor(BashRequest(command="curl http://evil"))
        assert res.exit_code == 127
        assert "not allowed" in res.stderr
    finally:
        close()


def test_unparseable_command_is_127(tmp_path):
    executor, close = make_bash_executor(session_id="t", workdir=tmp_path)
    try:
        res = executor(BashRequest(command="playwright-cli x ; rm -rf /"))
        assert res.exit_code == 127
    finally:
        close()


def test_timeout_kills_and_flags(tmp_path):
    executor, close = make_bash_executor(
        session_id="t", workdir=tmp_path, allowed_bins=frozenset({"sleep"}),
        timeout_s=0.5,
    )
    try:
        res = executor(BashRequest(command="sleep 5"))
        assert res.timed_out is True
        assert res.exit_code == -9
    finally:
        close()


def test_default_timeout_is_generous():
    assert DEFAULT_TIMEOUT_S >= 30.0
