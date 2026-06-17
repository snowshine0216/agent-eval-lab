"""Assemble the B-1 Task pair (§4.3): the candidate-visible MSTR Library
automation task paired with its held-out ReadbackSpec oracle. Mirrors
datasets/f_tasks.build_f_tasks (the F builder).

Two arms for M2 (D25/D37): b-b1-noskill (the model's own knowledge only) and
b-b1-skill (additionally injected the stripped strategy-test SKILL.md as the
system prompt). The arms differ ONLY by that injection — both are instrumented
identically by the harness (§7). The candidate prompt describes the task at a
fair problem level (§4.3) and NEVER names the golden object id or the exact
solution (TRAP 2 / D19/D33). B-2..B-10 are NOT provided — B-1 is a 1-task
contingency (D26); the >=10-task cluster bootstrap is NOT claimed here."""

from pathlib import Path

from agent_eval_lab.datasets.b1_oracle import build_b1_verification
from agent_eval_lab.datasets.skill_loader import load_stripped_skill
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.prompt import apply_system_prompt
from agent_eval_lab.tasks.schema import Task, TaskInput, TaskMetadata

_SYSTEM = (
    "You are automating the MicroStrategy Library web UI with a single tool: "
    "`bash` (you issue playwright-cli commands through it). Complete the "
    "owner-specified report build exactly; do not take shortcuts via APIs."
)

# Fair problem-level instruction (§4.3). Names the source cube, the row/column
# layout, the mandatory prompt, and the Save-As name pattern — NOT a golden
# object id, NOT a literal grid value (TRAP 2 / §4.1 withhold-localization).
_B1_USER = (
    "In the MicroStrategy Library app (Tutorial Project), create a new report in "
    "Design Mode from the source cube SAPBW > AV_TUTO > "
    "Query_CharacteristicValue_Mandatory. Place 'Years Hierarchy' and 'Region' on "
    "Rows and 'Cost' on Columns. Answer the mandatory prompt with 'South', then "
    "Apply. Save the report to your run's isolated folder under the unique name "
    "'<model>-<condition>-<run_id>' provided to you. Report when the saved report "
    "renders the prompted result."
)


def _task(*, task_id: str, messages: tuple[MessageTurn, ...], verification) -> Task:
    return Task(
        id=task_id,
        capability="browser_mstr",
        input=TaskInput(messages=messages, available_tools=("bash",)),
        verification=verification,
        metadata=TaskMetadata(
            split="held_out",
            version="b-domain-v1",
            provenance="source spec §4.3 exemplar B-1 (Tutorial Project)",
        ),
        initial_state={"task_key": "B-1"},
    )


def render_b_prompt(
    base_user: str,
    *,
    save_name: str,
    login: tuple[str, str],
    folder: str,
) -> str:
    """Inject the per-trial save-name + candidate login (app URL / username) +
    target folder into the static B-1 user prompt (spec §6.2). PURE.

    `login` is (app_url, username); there is DELIBERATELY no password parameter —
    the credential is handed to the live browser session out-of-band and NEVER
    enters the model context (§7 integrity boundary / TRAP 2)."""
    app_url, username = login
    return (
        f"{base_user}\n\n"
        f"Log in to the MicroStrategy Library app at {app_url} as user "
        f"{username!r} (the session is already authenticated for you; do not ask "
        f"for or print credentials). Save the report to the folder {folder!r} "
        f"under EXACTLY the unique name {save_name!r}."
    )


def build_b_tasks(*, golden_dir: Path, strategy_test_path: Path) -> tuple[Task, ...]:
    """Return the B-1 arm pair (noskill, skill). The same held-out ReadbackSpec
    grades both arms; the only difference is the injected stripped skill."""
    verification = build_b1_verification(golden_dir)
    base_messages = (
        MessageTurn(role="system", content=_SYSTEM),
        MessageTurn(role="user", content=_B1_USER),
    )
    skill_text = load_stripped_skill(strategy_test_path)
    skill_system = f"{_SYSTEM}\n\n{skill_text}"
    skill_messages = apply_system_prompt(base_messages, skill_system)
    return (
        _task(
            task_id="b-b1-noskill",
            messages=base_messages,
            verification=verification,
        ),
        _task(
            task_id="b-b1-skill",
            messages=skill_messages,
            verification=verification,
        ),
    )
