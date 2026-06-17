"""EDGE: the sandboxed, stateful playwright-cli bash boundary (§18.10, ADR-0008).

The single place subprocess I/O happens for the D/B-set agent. Unlike pytest_edge
(one-shot tree per call), the bash edge threads a PERSISTENT playwright-cli
session across calls within one run, so the executor is a stateful closure built
per-run via make_bash_executor(session_id, workdir).

Sandboxing: no shell (shlex.split + Popen(argv, shell=False)); an allowlist of
binaries (default {"playwright-cli"}); a from-scratch env with PATH pinned to the
node-22 bin dir; a per-command timeout with SIGKILL-the-group on expiry; stdout
truncated, wall-clock absent. A command that is unparseable, empty, or whose
argv[0] is not allowlisted returns exit_code 127 WITHOUT spawning a process.
"""

import os
import shlex
import shutil
import signal
import subprocess
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

from agent_eval_lab.records.bash import BashRequest, BashResult
from agent_eval_lab.records.execution import truncate_output

DEFAULT_TIMEOUT_S = 60.0
_TIMEOUT_EXIT_CODE = -9
ALLOWED_BINS = frozenset({"playwright-cli"})
_NODE22_BIN = str(Path.home() / ".nvm/versions/node/v22.22.2/bin")

# Per-workdir playwright daemon registry (PWTEST_DAEMON_SESSION_DIR). Scoping the
# registry under the workdir lets close() reap EXACTLY this executor's daemons
# (ADR-0008) — the model picks arbitrary session names, so name-targeting is out.
_DAEMON_SUBDIR = ".pw-daemon"
# Upper bound on the graceful `close-all` reap so a wedged daemon cannot hang
# task teardown; survivors (if any) are leaked, not blocked on.
_REAP_TIMEOUT_S = 30.0


def _playwright_cli_dir() -> str:
    return os.environ.get("PLAYWRIGHT_CLI_DIR", _NODE22_BIN)


def parse_argv(command: str) -> list[str] | None:
    """shlex.split the command; reject shell control sequences. Pure.

    Since the executor uses Popen(argv, shell=False), shell redirections (>,<)
    and pipelines (|) are inert — the OS never interprets them. The operators
    we must reject are ones that SHLEX would tokenize as control operators
    (`;`, `|`, `&&`, `||`, `$(`, backtick) and would allow multiple program
    invocations or command substitution. Arrow functions (`=>`) in JavaScript
    quoted arguments are safe because they stay inside a single shlex token.

    Returns the argv list, or None if the command is empty, unparseable, or
    contains a shell control sequence (`;`, `|`, `&`, backtick, `$(`).
    """
    # Reject unambiguous shell control operators that shlex would treat as
    # delimiters/substitutions regardless of quoting position in the string.
    # NOTE: `>` and `<` are intentionally NOT rejected here — they are safe
    # with shell=False and legitimately appear in arrow-function literals
    # (e.g. `playwright-cli eval "() => document.body.innerText"`).
    if any(tok in command for tok in (";", "|", "&", "`", "$(")):
        return None
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if not argv:
        return None
    # Browser file:// navigation is a read-the-store vector (§7): a
    # `playwright-cli open file:///…/evaluator.toml` + eval would exfiltrate the
    # integrity store. Refuse any file:-scheme argument (case-insensitive). HTTP(S)
    # navigation is unaffected.
    if any(tok.lower().startswith("file:") for tok in argv):
        return None
    # The allowlist is name-based (`Path(argv[0]).name`); a slash-containing
    # argv[0] would let `shutil.which` resolve an absolute/relative path and
    # bypass the allowlist's intent. Require a BARE binary name (review N1).
    if "/" in argv[0]:
        return None
    return argv


def _bash_env(workdir: str) -> dict[str, str]:
    """From-scratch env: never inherits os.environ; PATH pinned to node-22.

    PWTEST_DAEMON_SESSION_DIR pins playwright-cli's session registry under the
    workdir, so every daemon this executor spawns is bookkept per-task and can
    be reaped at close() without touching the machine's other playwright-cli
    sessions (the leak fix — see _reap_session_daemons).
    """
    return {
        "PATH": _playwright_cli_dir() + ":/usr/bin:/bin",
        "HOME": workdir,
        "TZ": "UTC",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "NO_COLOR": "1",
        "PWTEST_DAEMON_SESSION_DIR": str(Path(workdir) / _DAEMON_SUBDIR),
    }


def _kill_process_group(process: subprocess.Popen) -> None:
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    with suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=2.0)


def _reject(message: str) -> BashResult:
    return BashResult(stdout="", stderr=message, exit_code=127, timed_out=False)


def _reap_session_daemons(
    workdir: Path,
    *,
    run: Callable[..., object] = subprocess.run,
) -> None:
    """Stop the playwright daemons (and their Chrome) this executor spawned.

    A `playwright-cli -s=<name> open` starts a PERSISTENT, detached `cliDaemon.js`
    node process (a grandchild we never see) plus its Chrome helpers; rmtree-ing
    the workdir does not touch them, so they leak across tasks. The model picks
    arbitrary session names, so we cannot stop them by name. Instead the executor
    scopes the daemon registry to <workdir>/.pw-daemon (see _bash_env) and we run
    the tool's own `close-all`, which gracefully stops every daemon in THAT
    registry — exactly this executor's, never the machine's other sessions.

    Best-effort by construction:
      * no registry dir -> no daemon was ever spawned -> do nothing (and never
        spawn a subprocess, so non-browse executors stay hermetic);
      * playwright-cli not on the pinned PATH (e.g. CI without node) -> nothing
        we can do;
      * the call is time-bounded and all subprocess errors are swallowed, so a
        wedged daemon can neither hang nor abort task teardown.
    """
    if not (workdir / _DAEMON_SUBDIR).exists():
        return
    env = _bash_env(str(workdir))
    resolved = shutil.which("playwright-cli", path=env["PATH"])
    if resolved is None:
        return
    with suppress(subprocess.SubprocessError, OSError):
        run(
            [resolved, "close-all"],
            cwd=str(workdir),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_REAP_TIMEOUT_S,
            check=False,
        )


def make_bash_executor(
    *,
    session_id: str,
    workdir: Path,
    allowed_bins: frozenset[str] = ALLOWED_BINS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    reap_fn: Callable[[Path], None] = _reap_session_daemons,
    heartbeat_fn: Callable[[str], None] | None = None,
) -> tuple[Callable[[BashRequest], BashResult], Callable[[], None]]:
    """Build a stateful bash executor bound to one workdir + session id.

    Returns (executor, close). `close` reaps the playwright daemons this executor
    spawned (reap_fn, injected for tests) and then removes the workdir. The
    session id is the caller's to thread into playwright-cli `-s=` commands (the
    harness injects it into the task prompt); the workdir isolates the
    playwright daemon registry and other artifacts per run.

    heartbeat_fn (when given) is called with the session id on EVERY command —
    a sub-task liveness signal for a stall watchdog. The per-task run output is
    too coarse: one hard live task can outlive any sane stall threshold, so a
    monitor watching only that output false-kills healthy in-task work. The
    heartbeat fires at the I/O edge (where progress actually happens) and is
    strictly best-effort — a heartbeat failure never fails the command.
    """
    workdir.mkdir(parents=True, exist_ok=True)

    def executor(request: BashRequest) -> BashResult:
        if heartbeat_fn is not None:
            with suppress(OSError):
                heartbeat_fn(session_id)
        argv = parse_argv(request.command)
        if argv is None:
            return _reject("unparseable or shell-metacharacter command rejected")
        binname = Path(argv[0]).name
        if binname not in allowed_bins:
            return _reject(f"command not allowed: {binname}")
        resolved = shutil.which(argv[0], path=_bash_env(str(workdir))["PATH"])
        if resolved is None:
            return _reject(f"binary not found on pinned PATH: {argv[0]}")
        process = subprocess.Popen(
            [resolved, *argv[1:]],
            cwd=str(workdir),
            env=_bash_env(str(workdir)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            out, err = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            return BashResult(
                stdout="", stderr="", exit_code=_TIMEOUT_EXIT_CODE, timed_out=True
            )
        return BashResult(
            stdout=truncate_output(out.decode("utf-8", "replace")),
            stderr=truncate_output(err.decode("utf-8", "replace")),
            exit_code=process.returncode,
            timed_out=False,
        )

    def close() -> None:
        # Reap BEFORE rmtree: the reaper reads <workdir>/.pw-daemon, which
        # rmtree would otherwise destroy first (leaving the daemons orphaned).
        reap_fn(workdir)
        shutil.rmtree(workdir, ignore_errors=True)

    return executor, close
