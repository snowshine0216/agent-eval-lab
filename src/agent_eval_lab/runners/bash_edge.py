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
    # The allowlist is name-based (`Path(argv[0]).name`); a slash-containing
    # argv[0] would let `shutil.which` resolve an absolute/relative path and
    # bypass the allowlist's intent. Require a BARE binary name (review N1).
    if "/" in argv[0]:
        return None
    return argv


def _bash_env(workdir: str) -> dict[str, str]:
    """From-scratch env: never inherits os.environ; PATH pinned to node-22."""
    return {
        "PATH": _playwright_cli_dir() + ":/usr/bin:/bin",
        "HOME": workdir,
        "TZ": "UTC",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "NO_COLOR": "1",
    }


def _kill_process_group(process: subprocess.Popen) -> None:
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    with suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=2.0)


def _reject(message: str) -> BashResult:
    return BashResult(stdout="", stderr=message, exit_code=127, timed_out=False)


def make_bash_executor(
    *,
    session_id: str,
    workdir: Path,
    allowed_bins: frozenset[str] = ALLOWED_BINS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> tuple[Callable[[BashRequest], BashResult], Callable[[], None]]:
    """Build a stateful bash executor bound to one workdir + session id.

    Returns (executor, close). `close` removes the workdir (and any
    playwright-cli session artifacts under it). The session id is the caller's
    to thread into playwright-cli `-s=` commands (the harness injects it into the
    task prompt); the workdir isolates `.playwright-cli/` artifacts per run.
    """
    workdir.mkdir(parents=True, exist_ok=True)

    def executor(request: BashRequest) -> BashResult:
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
        shutil.rmtree(workdir, ignore_errors=True)

    return executor, close
