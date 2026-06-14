import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

import agent_eval_lab.runners.bash_edge as be
from agent_eval_lab.records.bash import BashRequest, BashResult
from agent_eval_lab.runners.bash_edge import (
    DEFAULT_TIMEOUT_S,
    make_bash_executor,
    parse_argv,
)

_NODE22_BIN = Path.home() / ".nvm/versions/node/v22.22.2/bin"


def _pw_cli_path() -> str | None:
    cli_dir = os.environ.get("PLAYWRIGHT_CLI_DIR", str(_NODE22_BIN))
    return shutil.which("playwright-cli", path=f"{cli_dir}:/usr/bin:/bin")


# The daemon/browser tests need a real node-22 playwright-cli; they are local-only
# (CI has no node/store), matching the rest of the browse suite.
requires_playwright_cli = pytest.mark.skipif(
    _pw_cli_path() is None,
    reason="playwright-cli (node-22) not on PATH — browse/daemon tests are local-only",
)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_pid_dead(pid: int, timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    return not _pid_alive(pid)


def test_parse_argv_rejects_shell_metacharacters():
    # `;`, `|`, `&` must not be honoured — one program per call.
    assert parse_argv("playwright-cli -s=S open http://x") == [
        "playwright-cli",
        "-s=S",
        "open",
        "http://x",
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
        session_id="t",
        workdir=tmp_path,
        allowed_bins=frozenset({"sleep"}),
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


# --- playwright daemon leak: close() must reap the executor's own daemons ---
# The model picks arbitrary session names, so close() cannot target a daemon by
# name. Instead each executor's daemons are scoped to a per-workdir registry
# (PWTEST_DAEMON_SESSION_DIR) and reaped via the tool's own scoped `close-all`.


def test_bash_env_scopes_playwright_daemon_dir_under_workdir(tmp_path):
    # Every playwright daemon this executor spawns must register under a
    # per-workdir session dir, so close() can reap exactly its own daemons
    # without touching the machine's other playwright-cli sessions.
    env = be._bash_env(str(tmp_path))
    assert env["PWTEST_DAEMON_SESSION_DIR"] == str(tmp_path / ".pw-daemon")


def test_reap_session_daemons_is_a_noop_when_no_daemon_dir(tmp_path):
    # No daemon was ever spawned (no .pw-daemon dir) -> reaping must not spawn
    # a playwright-cli subprocess. Keeps non-browse executors hermetic.
    calls = []
    be._reap_session_daemons(tmp_path, run=lambda *a, **k: calls.append((a, k)))
    assert calls == []


def test_reap_session_daemons_runs_scoped_close_all(tmp_path, monkeypatch):
    # When a daemon dir exists, reaping invokes `playwright-cli close-all` with
    # the per-workdir session dir, the workdir as cwd, and a bounding timeout.
    (tmp_path / ".pw-daemon").mkdir()
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    pw = fakebin / "playwright-cli"
    pw.write_text("#!/bin/sh\nexit 0\n")
    pw.chmod(0o755)
    monkeypatch.setenv("PLAYWRIGHT_CLI_DIR", str(fakebin))

    calls = []
    be._reap_session_daemons(tmp_path, run=lambda argv, **k: calls.append((argv, k)))

    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv == [str(pw), "close-all"]
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["env"]["PWTEST_DAEMON_SESSION_DIR"] == str(tmp_path / ".pw-daemon")
    assert kwargs["timeout"] == be._REAP_TIMEOUT_S


def test_reap_session_daemons_swallows_subprocess_errors(tmp_path, monkeypatch):
    # A wedged/failing daemon must never make teardown raise — reaping is
    # strictly best-effort (close() still has to rmtree the workdir).
    (tmp_path / ".pw-daemon").mkdir()
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    pw = fakebin / "playwright-cli"
    pw.write_text("#!/bin/sh\nexit 0\n")
    pw.chmod(0o755)
    monkeypatch.setenv("PLAYWRIGHT_CLI_DIR", str(fakebin))

    def boom(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout"))

    be._reap_session_daemons(tmp_path, run=boom)  # must not raise


def test_close_reaps_daemons_before_removing_workdir(tmp_path):
    # close() must reap daemons BEFORE rmtree — the reaper reads the per-workdir
    # session dir, which rmtree would otherwise destroy first.
    seen = {}

    def fake_reap(workdir):
        seen["workdir_present"] = Path(workdir).exists()

    _executor, close = be.make_bash_executor(
        session_id="t", workdir=tmp_path, reap_fn=fake_reap
    )
    close()

    assert seen["workdir_present"] is True
    assert not tmp_path.exists()


# --- per-command heartbeat: the I/O edge emits a sub-task liveness signal ---
# The per-task jsonl is the run's only progress signal and is too coarse — a
# single hard live task outlives any sane stall threshold, so a watchdog watching
# only the jsonl false-kills healthy work. The executor (the I/O edge) emits a
# heartbeat per command so a monitor sees continuous in-task progress.


def test_executor_fires_heartbeat_on_each_command(tmp_path):
    beats = []
    executor, close = be.make_bash_executor(
        session_id="cmc-q07",
        workdir=tmp_path,
        allowed_bins=frozenset({"true"}),
        heartbeat_fn=beats.append,
    )
    try:
        executor(BashRequest(command="true"))
        executor(BashRequest(command="true"))
    finally:
        close()
    assert beats == ["cmc-q07", "cmc-q07"]


def test_executor_fires_heartbeat_even_for_a_rejected_command(tmp_path):
    # A rejected/disallowed command is still liveness — the model is actively
    # driving the run — so the heartbeat fires before the allowlist check.
    beats = []
    executor, close = be.make_bash_executor(
        session_id="cmc-q07", workdir=tmp_path, heartbeat_fn=beats.append
    )
    try:
        res = executor(BashRequest(command="curl http://evil"))  # disallowed -> 127
        assert res.exit_code == 127
    finally:
        close()
    assert beats == ["cmc-q07"]


def test_executor_heartbeat_failure_never_breaks_a_command(tmp_path):
    # Heartbeat is best-effort telemetry: a write failure (disk full, etc.) must
    # never fail the command it accompanies.
    def boom(_session_id):
        raise OSError("disk full")

    executor, close = be.make_bash_executor(
        session_id="t",
        workdir=tmp_path,
        allowed_bins=frozenset({"true"}),
        heartbeat_fn=boom,
    )
    try:
        res = executor(BashRequest(command="true"))
        assert res.exit_code == 0  # command succeeded despite the heartbeat failure
    finally:
        close()


@requires_playwright_cli
def test_close_reaps_a_real_playwright_daemon(tmp_path):
    # The real regression guard (local-only): an `open` spawns a persistent
    # detached daemon; close() must leave no daemon process behind.
    import re

    executor, close = be.make_bash_executor(session_id="itest", workdir=tmp_path)
    res = executor(BashRequest(command="playwright-cli -s=itest open about:blank"))
    match = re.search(r"opened with pid (\d+)", res.stdout)
    try:
        assert res.exit_code == 0, res.stderr
        assert match is not None, f"no daemon pid in stdout: {res.stdout!r}"
        assert _pid_alive(int(match.group(1)))
        # the daemon registered under the per-workdir scoped session dir
        assert list((tmp_path / ".pw-daemon").rglob("*.session"))
    finally:
        close()

    assert match is not None
    assert _wait_pid_dead(int(match.group(1))), "daemon survived close()"
    assert not tmp_path.exists()
