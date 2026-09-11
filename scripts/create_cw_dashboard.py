#!/usr/bin/env python3
"""
Create the ``Recoup-Demo`` CloudWatch Dashboard.

Run ONCE after the backend has published at least one set of custom metrics
(i.e. after hitting /api/quality/scorecard with live AWS resources configured).

Dashboard shows:
  - 4 single-value (number) widgets: OpportunitiesDetected, CreditsRecoveredUSD,
    HumanApprovalsRequired, UnsafeActionsBlocked
  - 1 time-series widget: GoldenPathSuccessRate over last 24h
  - 1 time-series widget: CreditsRecoveredUSD over last 24h

Usage:
    python scripts/create_cw_dashboard.py [--region us-east-1] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys

DASHBOARD_NAME = "Recoup-Demo"
NAMESPACE = "Recoup"

METRICS = [
    "OpportunitiesDetected",
    "CreditsRecoveredUSD",
    "HumanApprovalsRequired",
    "UnsafeActionsBlocked",
    "GoldenPathSuccessRate",
]


def build_dashboard_body(region: str) -> dict:
    """Return the CloudWatch dashboard JSON body."""
    # Row 1: 4 single-value (number) widgets
    number_widgets = []
    titles = {
        "OpportunitiesDetected": "Opportunities Detected",
        "CreditsRecoveredUSD": "Credits Recovered (USD)",
        "HumanApprovalsRequired": "Human Approvals Required",
        "UnsafeActionsBlocked": "Unsafe Actions Blocked",
    }
    for idx, (metric, title) in enumerate(list(titles.items())):
        x = (idx % 4) * 6
        y = (idx // 4) * 3
        number_widgets.append(
            {
                "type": "metric",
                "x": x,
                "y": y,
                "width": 6,
                "height": 3,
                "properties": {
                    "title": title,
                    "metrics": [
                        [
                            NAMESPACE,
                            metric,
                        ]
                    ],
                    "view": "singleValue",
                    "period": 86400,  # 24h
                    "stat": "Sum",
                    "region": region,
                },
            }
        )

    # Row 2: GoldenPathSuccessRate time series
    success_rate_widget = {
        "type": "metric",
        "x": 0,
        "y": 3,
        "width": 12,
        "height": 6,
        "properties": {
            "title": "Golden Path Success Rate (%)",
            "metrics": [
                [NAMESPACE, "GoldenPathSuccessRate"]
            ],
            "view": "timeSeries",
            "stacked": False,
            "period": 300,
            "stat": "Average",
            "region": region,
            "yAxis": {"left": {"min": 0, "max": 100}},
        },
    }

    # Row 2: CreditsRecoveredUSD time series
    credits_widget = {
        "type": "metric",
        "x": 12,
        "y": 3,
        "width": 12,
        "height": 6,
        "properties": {
            "title": "Credits Recovered (USD) — Cumulative",
            "metrics": [
                [NAMESPACE, "CreditsRecoveredUSD"]
            ],
            "view": "timeSeries",
            "stacked": False,
            "period": 300,
            "stat": "Sum",
            "region": region,
            "yAxis": {"left": {"min": 0}},
        },
    }

    return {
        "widgets": number_widgets + [success_rate_widget, credits_widget]
    }


def create(region: str = "us-east-1", dry_run: bool = False) -> None:
    body = build_dashboard_body(region)
    body_json = json.dumps(body, indent=2)

    if dry_run:
        print(f"[DRY RUN] Would create CloudWatch dashboard '{DASHBOARD_NAME}'")
        print(f"Region: {region}")
        print("Dashboard body:")
        print(body_json)
        return

    import boto3  # type: ignore[import-untyped]

    cw = boto3.client("cloudwatch", region_name=region)
    cw.put_dashboard(DashboardName=DASHBOARD_NAME, DashboardBody=body_json)

    print(f"Dashboard '{DASHBOARD_NAME}' created/updated successfully.")
    print(f"View at: https://{region}.console.aws.amazon.com/cloudwatch/home"
          f"?region={region}#dashboards:name={DASHBOARD_NAME}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create Recoup-Demo CloudWatch dashboard")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    create(region=args.region, dry_run=args.dry_run)
