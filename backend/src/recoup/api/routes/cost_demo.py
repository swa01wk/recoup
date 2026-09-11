"""
Cost Explorer Demo — Phase 6b Priority 6.

GET /api/cost-demo/summary   — real AWS account spend for current month.

Blocked until Sep 3, 2026 (Cost Explorer enabled Sep 2; 24h data lag).
Falls back to fixture values in simulation mode.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter

from ...config import settings

router = APIRouter()


def _first_of_month() -> str:
    today = date.today()
    return today.replace(day=1).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _fetch_live() -> dict[str, Any]:
    """Call real Cost Explorer APIs."""
    import boto3

    ce = boto3.client("ce", region_name="us-east-1")  # CE only available in us-east-1

    start = _first_of_month()
    end = _today()

    # Total account spend
    resp = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
    )
    results = resp.get("ResultsByTime", [])
    total_usd = 0.0
    if results:
        total_usd = float(
            results[0].get("Total", {}).get("UnblendedCost", {}).get("Amount", "0")
        )

    # Per-service breakdown
    resp_svc = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    breakdown: list[dict[str, Any]] = []
    for result in resp_svc.get("ResultsByTime", []):
        for group in result.get("Groups", []):
            service_name = group["Keys"][0]
            amount = float(
                group.get("Metrics", {})
                .get("UnblendedCost", {})
                .get("Amount", "0")
            )
            if amount > 0.001:
                breakdown.append({"service": service_name, "cost_usd": round(amount, 4)})

    breakdown.sort(key=lambda x: x["cost_usd"], reverse=True)

    return {
        "total_usd": round(total_usd, 4),
        "billing_period_start": start,
        "billing_period_end": end,
        "breakdown": breakdown[:10],
    }


@router.get("/summary")
def cost_summary() -> dict[str, Any]:
    """
    Return AWS account cost summary for the current month.

    Calls real Cost Explorer APIs when live AWS resources are configured.
    Cost Explorer was enabled Sep 2, 2026 — data available from Sep 3.

    Returns:
        total spend, billing period, per-service breakdown.
    """
    simulated = not settings.live_aws_enabled
    fetched_at = datetime.now(UTC).isoformat()

    if settings.live_aws_enabled:
        try:
            data = _fetch_live()
            data_source = "live"
        except Exception:  # noqa: BLE001
            data = {
                "total_usd": 8.39,
                "billing_period_start": _first_of_month(),
                "billing_period_end": _today(),
                "breakdown": [
                    {"service": "Amazon EC2", "cost_usd": 3.12},
                    {"service": "Amazon CloudWatch", "cost_usd": 1.85},
                    {"service": "AWS Key Management Service", "cost_usd": 1.00},
                    {"service": "Amazon DynamoDB", "cost_usd": 0.98},
                    {"service": "Amazon S3", "cost_usd": 0.88},
                    {"service": "Amazon SNS", "cost_usd": 0.56},
                ],
            }
            simulated = True
            data_source = "simulation_fallback"
    else:
        data = {
            "total_usd": 8.39,
            "billing_period_start": _first_of_month(),
            "billing_period_end": _today(),
            "breakdown": [
                {"service": "Amazon EC2", "cost_usd": 3.12},
                {"service": "Amazon CloudWatch", "cost_usd": 1.85},
                {"service": "AWS Key Management Service", "cost_usd": 1.00},
                {"service": "Amazon DynamoDB", "cost_usd": 0.98},
                {"service": "Amazon S3", "cost_usd": 0.88},
                {"service": "Amazon SNS", "cost_usd": 0.56},
            ],
        }
        data_source = "simulation"

    return {
        "fetched_at": fetched_at,
        "simulated": simulated,
        "data_source": data_source,
        **data,
        "_aws": {
            "service": "CostExplorer",
            "api": "GetCostAndUsage",
            "live": not simulated,
        },
    }
