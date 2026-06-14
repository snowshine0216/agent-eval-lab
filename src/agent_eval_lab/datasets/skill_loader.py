"""Load the stripped knowledge-only strategy-test fork (§18.9/D27).

The fork is ALREADY stripped + staged on disk by the owner (gitignored
evaluator-only/stripped-strategy-test/SKILL.md; the path is evaluator.toml
[skill] strategy_test_path). This loader only READS it — no stripping logic
lives in the eval lab. Injected as the B-skill arm's system prompt; the
B-noskill arm gets nothing (D25/D37). The estimand is the BUNDLED stripped-skill
effect, never 'domain knowledge alone'."""

from pathlib import Path


def load_stripped_skill(path: Path) -> str:
    """Return the stripped SKILL.md text. Raises FileNotFoundError if absent
    (the caller — build_b_tasks — surfaces a clear error before any run)."""
    return Path(path).read_text(encoding="utf-8")
