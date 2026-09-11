"""
CloudTrail No-Actor Demo — Phase 6b Priority 3.

GET /api/cloudtrail-demo/check   — call real CloudTrail LookupEvents for the
                                   demo instance, return attribution analysis.

Real data available NOW:
  - All CloudTrail events for i-0d3389d7f950f7d3f in last 24 h are AssumeRole
    with User: None
  - Root account making DescribeMetricFilters every 5 min
  - Decrypt events with User: None
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter

from ...config import settings

router = APIRouter()

_DEMO_INSTANCE_ID = "i-0d3389d7f950f7d3f"

# Events that indicate a human user was the actor
_HUMAN_EVENT_NAMES = {
    "ConsoleLogin",
    "StartSession",
    "CreateKeyPair",
    "ImportKeyPair",
    "RunInstances",
    "StartInstances",
    "StopInstances",
    "TerminateInstances",
    "ModifyInstanceAttribute",
    "CreateImage",
}


def _check_live(instance_id: str, hours: int = 24) -> list[dict[str, Any]]:
    """Call real CloudTrail LookupEvents for the instance."""
    import boto3

    ct = boto3.client("cloudtrail", region_name=settings.bedrock_region)
    now = datetime.now(UTC)
    start = now - timedelta(hours=hours)

    paginator = ct.get_paginator("lookup_events")
    pages = paginator.paginate(
        LookupAttributes=[
            {"AttributeKey": "ResourceName", "AttributeValue": instance_id}
        ],
        StartTime=start,
        EndTime=now,
        PaginationConfig={"MaxItems": 200},
    )

    events: list[dict[str, Any]] = []
    for page in pages:
        for evt in page.get("Events", []):
            # Extract only safe, non-sensitive fields
            username = evt.get("Username")
            ct_event = evt.get("CloudTrailEvent")
            identity_type = "Unknown"
            if ct_event:
                import json

                try:
                    parsed = json.loads(ct_event)
                    ui = parsed.get("userIdentity", {})
                    identity_type = ui.get("type", "Unknown")
                    if not username:
                        username = ui.get("userName") or ui.get("principalId", "None")
                except Exception:  # noqa: BLE001, S110
                    pass
            events.append(
                {
                    "event_name": evt.get("EventName", "Unknown"),
                    "event_time": evt.get("EventTime", now).isoformat()
                    if hasattr(evt.get("EventTime", now), "isoformat")
                    else str(evt.get("EventTime", now)),
                    "user_identity_type": identity_type,
                    "username": username or "None",
                    "request_id": evt.get("EventId", ""),
                }
            )

    return events


def _analyse_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive attribution analysis from a list of CloudTrail events."""
    total = len(events)

    human_attributed = [
        e
        for e in events
        if e.get("username") not in (None, "None", "")
        and e.get("user_identity_type") not in ("AssumedRole", "AWSService", "Unknown")
        and e.get("event_name") in _HUMAN_EVENT_NAMES
    ]

    # Only IAMUser events (not Root — Root is used by automated services)
    # or explicitly attributed human events count as human actors.
    has_human_actor = (
        any(e.get("user_identity_type") == "IAMUser" for e in events)
        or len(human_attributed) > 0
    )

    actor_types: dict[str, int] = {}
    for e in events:
        t = e.get("user_identity_type", "Unknown")
        actor_types[t] = actor_types.get(t, 0) + 1

    return {
        "total_events": total,
        "actor_attributed": has_human_actor,
        "human_events": len(human_attributed),
        "actor_type_breakdown": actor_types,
        "requires_human_review": not has_human_actor and total > 0,
        "finding": (
            "Human actor found — cost changes are attributable."
            if has_human_actor
            else (
                "No human actor found in CloudTrail events — all activity is "
                "automated (AssumedRole / AWSService). Cost anomalies in this "
                "period cannot be attributed to a specific user. Human review required."
                if total > 0
                else "No CloudTrail events found for this resource in the time window."
            )
        ),
    }


# Deterministic simulation fixture — mirrors real account data
_SIM_EVENTS: list[dict[str, Any]] = [
    {
        "event_name": "AssumeRole",
        "event_time": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        "user_identity_type": "AssumedRole",
        "username": "None",
        "request_id": "sim-0001",
    },
    {
        "event_name": "DescribeMetricFilters",
        "event_time": (datetime.now(UTC) - timedelta(minutes=10)).isoformat(),
        "user_identity_type": "Root",
        "username": "None",
        "request_id": "sim-0002",
    },
    {
        "event_name": "Decrypt",
        "event_time": (datetime.now(UTC) - timedelta(minutes=15)).isoformat(),
        "user_identity_type": "AssumedRole",
        "username": "None",
        "request_id": "sim-0003",
    },
    {
        "event_name": "AssumeRole",
        "event_time": (datetime.now(UTC) - timedelta(minutes=20)).isoformat(),
        "user_identity_type": "AssumedRole",
        "username": "None",
        "request_id": "sim-0004",
    },
]


@router.get("/check")
def cloudtrail_check(
    instance_id: str = _DEMO_INSTANCE_ID,
    hours: int = 24,
) -> dict[str, Any]:
    """
    Run a CloudTrail attribution check for the demo instance.

    Calls real CloudTrail LookupEvents when live AWS resources are configured.
    Otherwise returns a deterministic simulation that mirrors the real account
    data (AssumeRole + Root with User: None).

    Returns:
        attribution analysis including actor_attributed flag, event breakdown,
        and whether human review is required.
    """
    simulated = not settings.live_aws_enabled
    events: list[dict[str, Any]]

    if settings.live_aws_enabled:
        try:
            events = _check_live(instance_id, hours=hours)
            data_source = "live"
        except Exception:  # noqa: BLE001
            events = list(_SIM_EVENTS)
            simulated = True
            data_source = "simulation_fallback"
    else:
        events = list(_SIM_EVENTS)
        data_source = "simulation"

    analysis = _analyse_events(events)

    return {
        "instance_id": instance_id,
        "window_hours": hours,
        "simulated": simulated,
        "data_source": data_source,
        "checked_at": datetime.now(UTC).isoformat(),
        "events": events[:20],  # cap response size; full data in CloudTrail console
        **analysis,
        "_aws": {
            "service": "CloudTrail",
            "api": "LookupEvents",
            "live": not simulated,
        },
    }
