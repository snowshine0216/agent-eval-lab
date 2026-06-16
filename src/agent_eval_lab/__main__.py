"""Entry point for `python -m agent_eval_lab`.

Lets the documented invocations (plan Task 7, the agentic recipes) work:
`python -m agent_eval_lab <command> ...`.
"""

import sys

from agent_eval_lab.cli import main

if __name__ == "__main__":
    sys.exit(main())
