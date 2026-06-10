"""Deterministic content hash over a Trajectory (determinism guard)."""

import hashlib
import json

from agent_eval_lab.tasks.codec import to_dict
from agent_eval_lab.tasks.grading import Trajectory


def trajectory_hash(trajectory: Trajectory) -> str:
    """SHA-256 over the canonical JSON serialization of the trajectory."""
    payload = json.dumps(to_dict(trajectory), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
