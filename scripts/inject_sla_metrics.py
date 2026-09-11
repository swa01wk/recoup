#!/usr/bin/env python3
"""
Inject SLA metric data into CloudWatch for the demo.

Writes 8,640 five-minute intervals (30 days × 288 per day) into a real
CloudWatch namespace ``Recoup/SLA/Demo`` with metric ``Availability5min``.
Six windows at 2026-08-01T02:00–02:30Z are set to 0.0 (outage) — the rest
are 100.0 (healthy).

Run ONCE before the demo. The graph will then pick up this data from CW when
live AWS resources are configured.

Usage:
    cd backend
    python ../scripts/inject_sla_metrics.py

Cost: ~$0.01 (first 10 custom metrics/month free, then $0.30/metric/month)
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NAMESPACE = "Recoup/SLA/Demo"
METRIC_NAME = "Availability5min"
PERIOD_MINUTES = 5
DIMENSION_NAME = "Service"
DIMENSION_VALUE = "APIGateway-us-east-1"

# Period: August 2026 (UTC)
PERIOD_START = datetime(2026, 8, 1, 0, 0, 0, tzinfo=UTC)
PERIOD_END = datetime(2026, 8, 31, 23, 55, 0, tzinfo=UTC)

# Outage windows (inclusive start, exclusive end)
OUTAGE_WINDOWS = [
    (datetime(2026, 8, 1, 2, 0, 0, tzinfo=UTC), datetime(2026, 8, 1, 2, 30, 0, tzinfo=UTC)),
]

# CloudWatch put_metric_data max batch size
BATCH_SIZE = 1000


def is_outage(ts: datetime) -> bool:
    for start, end in OUTAGE_WINDOWS:
        if start <= ts < end:
            return True
    return False


def generate_data_points() -> list[dict]:
    """Generate all 8,640 data points for August 2026."""
    points = []
    t = PERIOD_START
    while t <= PERIOD_END:
        value = 0.0 if is_outage(t) else 100.0
        points.append({"ts": t, "value": value})
        t += timedelta(minutes=PERIOD_MINUTES)
    return points


def inject(dry_run: bool = False, region: str = "us-east-1") -> None:
    """Write all data points to CloudWatch in batches."""
    points = generate_data_points()
    total = len(points)
    outage_count = sum(1 for p in points if p["value"] == 0.0)
    print(f"Generated {total} data points ({outage_count} outage intervals)")

    if dry_run:
        print("[DRY RUN] Would write to CloudWatch namespace:", NAMESPACE)
        sample = [p for p in points if p["value"] == 0.0][:6]
        for p in sample:
            print(f"  {p['ts'].isoformat()}  availability={p['value']}")
        print("Dry run complete — no data written.")
        return

    import boto3  # type: ignore[import-untyped]

    cw = boto3.client("cloudwatch", region_name=region)

    batches = [points[i : i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    print(f"Writing {total} data points in {len(batches)} batches to {NAMESPACE}/{METRIC_NAME}…")

    for batch_idx, batch in enumerate(batches):
        metric_data = [
            {
                "MetricName": METRIC_NAME,
                "Dimensions": [
                    {"Name": DIMENSION_NAME, "Value": DIMENSION_VALUE},
                ],
                "Timestamp": p["ts"],
                "Value": p["value"],
                "Unit": "Percent",
            }
            for p in batch
        ]
        cw.put_metric_data(Namespace=NAMESPACE, MetricData=metric_data)
        pct = round((batch_idx + 1) / len(batches) * 100)
        print(f"  Batch {batch_idx + 1}/{len(batches)} ({pct}%) — {len(batch)} points")

    print(f"\nDone. {total} data points written to CloudWatch.")
    print(f"Namespace:   {NAMESPACE}")
    print(f"Metric:      {METRIC_NAME}")
    print(f"Dimension:   {DIMENSION_NAME}={DIMENSION_VALUE}")
    print(f"Period:      {PERIOD_START.date()} – {PERIOD_END.date()}")
    print(f"Outage pts:  {outage_count} ({OUTAGE_WINDOWS[0][0]} – {OUTAGE_WINDOWS[0][1]})")
    print("\nView in CloudWatch console:")
    print(f"  https://{region}.console.aws.amazon.com/cloudwatch/home"
          f"?region={region}#metricsV2:graph=~();namespace={NAMESPACE}")


def verify(region: str = "us-east-1") -> None:
    """Read back a sample of data points to verify the injection."""
    import boto3  # type: ignore[import-untyped]

    cw = boto3.client("cloudwatch", region_name=region)
    start = OUTAGE_WINDOWS[0][0] - timedelta(hours=1)
    end = OUTAGE_WINDOWS[0][1] + timedelta(hours=1)

    resp = cw.get_metric_statistics(
        Namespace=NAMESPACE,
        MetricName=METRIC_NAME,
        Dimensions=[{"Name": DIMENSION_NAME, "Value": DIMENSION_VALUE}],
        StartTime=start,
        EndTime=end,
        Period=300,
        Statistics=["Average"],
    )
    dps = sorted(resp.get("Datapoints", []), key=lambda x: x["Timestamp"])
    print(f"\nVerification — {len(dps)} datapoints around outage window:")
    for dp in dps:
        val = dp["Average"]
        flag = " ← OUTAGE" if val == 0.0 else ""
        print(f"  {dp['Timestamp'].isoformat()}  {val:.1f}%{flag}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inject SLA metrics into CloudWatch")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written without calling AWS")
    parser.add_argument("--verify", action="store_true", help="Read back data around the outage window")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    args = parser.parse_args()

    if args.verify:
        verify(region=args.region)
        sys.exit(0)

    inject(dry_run=args.dry_run, region=args.region)
