#!/usr/bin/env python3
"""
Fire a synthetic AWS Health event onto EventBridge.

The ``RecoupHealthEventRule`` routes it to the ``recoup-recovery-events`` SQS
queue.  The Recoup backend SQS poller picks it up and auto-starts the graph
workflow — no manual API call needed.

Usage:
    cd backend
    python ../scripts/fire_demo_event.py

    # Dry-run (print payload, no AWS call):
    python ../scripts/fire_demo_event.py --dry-run

    # Custom event-bus name:
    python ../scripts/fire_demo_event.py --event-bus RecoupEventBus

Video moment: "In production, this triggers automatically when AWS Health fires.
Here I'll put a synthetic event onto EventBridge and you'll see Recoup pick it
up within seconds."
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime


SYNTHETIC_HEALTH_EVENT = {
    "version": "0",
    "id": str(uuid.uuid4()),
    "source": "aws.health",
    "account": "625962218034",
    "time": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "region": "us-east-1",
    "resources": ["arn:aws:apigateway:us-east-1::/restapis"],
    "detail-type": "AWS Health Event",
    "detail": {
        "eventArn": (
            "arn:aws:health:us-east-1::event/APIGATEWAY/"
            "AWS_APIGATEWAY_OPERATIONAL_ISSUE/AWS_APIGATEWAY_OPERATIONAL_ISSUE_DEMO"
        ),
        "service": "APIGATEWAY",
        "eventTypeCode": "AWS_APIGATEWAY_OPERATIONAL_ISSUE",
        "eventTypeCategory": "issue",
        "region": "us-east-1",
        "startTime": "2026-08-01T02:00:00Z",
        "endTime": "2026-08-01T02:30:00Z",
        "statusCode": "closed",
        "eventScopeCode": "ACCOUNT_SPECIFIC",
        "affectedEntities": [
            {"entityValue": "arn:aws:apigateway:us-east-1::/restapis"},
        ],
        "_recoup_demo": True,
        "_recoup_replay": True,
    },
}


def fire(event_bus: str = "default", region: str = "us-east-1", dry_run: bool = False) -> None:
    payload = dict(SYNTHETIC_HEALTH_EVENT)
    payload["time"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload["id"] = str(uuid.uuid4())

    entry = {
        "Time": datetime.now(UTC),
        "Source": "aws.health",
        "DetailType": "AWS Health Event",
        "Detail": json.dumps(payload),
        "EventBusName": event_bus,
    }

    print("Synthetic EventBridge Health event:")
    print(json.dumps(payload, indent=2, default=str))
    print()

    if dry_run:
        print(f"[DRY RUN] Would put event onto bus '{event_bus}' in {region}")
        return

    import boto3  # type: ignore[import-untyped]

    eb = boto3.client("events", region_name=region)
    resp = eb.put_events(Entries=[entry])
    failed = resp.get("FailedEntryCount", 0)
    if failed:
        print(f"ERROR: {failed} event(s) failed to publish", file=sys.stderr)
        sys.exit(1)

    event_id = resp["Entries"][0].get("EventId", "unknown")
    print(f"Event published successfully.")
    print(f"  Event ID:   {event_id}")
    print(f"  Event bus:  {event_bus}")
    print(f"  Region:     {region}")
    print()
    print("The RecoupHealthEventRule should route this to recoup-recovery-events SQS.")
    print("The Recoup backend SQS poller will pick it up and start the workflow.")
    print("Watch the Command Center — an opportunity should appear within ~10 seconds.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fire a synthetic Health event onto EventBridge")
    parser.add_argument("--event-bus", default="default", help="EventBridge bus name (default: default)")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without calling AWS")
    args = parser.parse_args()

    fire(event_bus=args.event_bus, region=args.region, dry_run=args.dry_run)
