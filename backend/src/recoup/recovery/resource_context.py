"""Build resource-centric operational context from findings and signals."""

from __future__ import annotations

from ..models.recovery import (
    OperationalSignal,
    ResourceContext,
    ResourceEnvironment,
    ResourceIdentity,
)
from ..scanners.finding import Finding


def _env_from_tags(tags: dict[str, str]) -> str:
    for key in ("Environment", "env", "Stage", "stage"):
        if key in tags:
            return tags[key].lower()
    return "unknown"


def build_resource_context(
    finding: Finding, signals: list[OperationalSignal]
) -> ResourceContext:
    ev = finding.evidence or {}
    tags: dict[str, str] = {}
    if isinstance(ev.get("tags"), dict):
        tags = {str(k): str(v) for k, v in ev["tags"].items()}

    env = ResourceEnvironment(
        environment=_env_from_tags(tags),
        tags=tags,
        owner=str(ev.get("owner", "") or tags.get("Owner", "")),
        is_demo=finding.is_demo_resource,
        scenario_tag=finding.scenario_tag or "",
    )

    identity = ResourceIdentity(
        resource_id=finding.resource_id,
        resource_type=finding.resource_type,
        service=finding.service,
        region=finding.region,
        instance_type=str(ev.get("instance_type", "")),
    )

    cost_notes: list[str] = []
    if ev.get("cost_context"):
        cost_notes.append(str(ev["cost_context"]))
    cost_notes.append(f"Estimated recovery: ${finding.estimated_monthly_savings_usd:.2f}/mo")

    usage_notes = [
        s.description for s in signals if s.signal_type == "utilization"
    ]
    activity_notes = [
        s.description for s in signals if s.signal_type in ("activity", "finding")
    ]

    deps: list[str] = []
    for key in ("attached_volumes", "load_balancer", "security_groups"):
        if ev.get(key):
            deps.append(f"{key}: {ev[key]}")

    recovery_notes: list[str] = []
    if env.is_demo:
        recovery_notes.append("Demo resource (RecoupDemo=true)")
    if finding.recommendation:
        recovery_notes.append(f"Scanner recommendation: {finding.recommendation}")

    return ResourceContext(
        identity=identity,
        environment=env,
        cost_notes=cost_notes,
        usage_notes=usage_notes,
        activity_notes=activity_notes,
        dependencies=deps,
        recovery_notes=recovery_notes,
    )
