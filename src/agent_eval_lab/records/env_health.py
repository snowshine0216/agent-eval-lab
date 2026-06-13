"""Environment health probe result (D21/D28 §18.5).

Model-action-INDEPENDENT: produced by a side-channel reachability/health check
the candidate cannot influence, so an agent cannot wedge the env to convert its
own failures into 'invalid'. Frozen and total; nullable status fields carry the
probe's HTTP status (2XX/3XX = healthy per §18.5) or None when no probe ran on
that side.
"""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class EnvHealth:
    pre_healthy: bool
    post_healthy: bool
    pre_status: int | None = None
    post_status: int | None = None
