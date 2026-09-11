"""
Missing Cost Allocation Tags Demo — Phase 6b Priority 4.

GET /api/tagging-demo/scan   — call ResourceGroupsTaggingAPI.get_resources(),
                               find resources missing required cost tags, return findings.

Real data available NOW:
  - EC2 i-0d3389d7f950f7d3f missing cost:team, environment
  - SQS queues, SNS topic, CloudWatch alarms — all missing cost:team
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from ...config import settings

router = APIRouter()

# Tags that are required for cost attribution
_REQUIRED_TAGS = {"cost:team", "environment"}

# Per-resource monthly cost estimates (USD) when tag data is unavailable
_RESOURCE_COST_ESTIMATES: dict[str, float] = {
    "ec2:instance": 7.59,
    "sqs:queue": 0.40,
    "sns:topic": 0.50,
    "cloudwatch:alarm": 0.10,
    "s3:bucket": 2.30,
    "dynamodb:table": 1.50,
    "kms:key": 1.00,
    "logs:log-group": 0.05,
}


def _service_type_key(resource_type: str) -> str:
    """Extract a cost-estimate bucket from a full resource type string."""
    rt = resource_type.lower()
    for key in _RESOURCE_COST_ESTIMATES:
        service, rtype = key.split(":")
        if service in rt and rtype in rt:
            return key
    # Fallback: match on service prefix
    for key in _RESOURCE_COST_ESTIMATES:
        service = key.split(":")[0]
        if service in rt:
            return key
    return ""


def _scan_live(account_id: str) -> list[dict[str, Any]]:
    """Call ResourceGroupsTaggingAPI and find untagged resources."""
    import boto3

    tagging = boto3.client(
        "resourcegroupstaggingapi", region_name=settings.bedrock_region
    )
    paginator = tagging.get_paginator("get_resources")

    findings: list[dict[str, Any]] = []
    for page in paginator.paginate(
        ResourcesPerPage=100,
        IncludeComplianceDetails=True,
        ExcludeCompliantResources=False,
    ):
        for resource in page.get("ResourceTagMappingList", []):
            arn: str = resource.get("ResourceARN", "")
            tags: dict[str, str] = {
                t["Key"]: t["Value"]
                for t in resource.get("Tags", [])
            }
            missing = sorted(_REQUIRED_TAGS - set(tags.keys()))
            if missing:
                rt = arn.split(":")[2] if arn.count(":") >= 2 else "unknown"
                cost_key = _service_type_key(arn)
                findings.append(
                    {
                        "arn": arn,
                        "resource_type": rt,
                        "present_tags": tags,
                        "missing_tags": missing,
                        "estimated_monthly_cost_usd": _RESOURCE_COST_ESTIMATES.get(
                            cost_key, 1.0
                        ),
                    }
                )
    return findings


# Deterministic simulation fixture — mirrors real account resource state
_SIM_FINDINGS: list[dict[str, Any]] = [
    {
        "arn": "arn:aws:ec2:us-east-1:625962218034:instance/i-0d3389d7f950f7d3f",
        "resource_type": "ec2",
        "present_tags": {"RecoupDemo": "true", "Name": "recoup-demo"},
        "missing_tags": ["cost:team", "environment"],
        "estimated_monthly_cost_usd": 7.59,
    },
    {
        "arn": "arn:aws:sqs:us-east-1:625962218034:recoup-recovery-events",
        "resource_type": "sqs",
        "present_tags": {},
        "missing_tags": ["cost:team", "environment"],
        "estimated_monthly_cost_usd": 0.40,
    },
    {
        "arn": "arn:aws:sqs:us-east-1:625962218034:recoup-recovery-events-dlq",
        "resource_type": "sqs",
        "present_tags": {},
        "missing_tags": ["cost:team", "environment"],
        "estimated_monthly_cost_usd": 0.40,
    },
    {
        "arn": "arn:aws:sns:us-east-1:625962218034:recoup-alerts",
        "resource_type": "sns",
        "present_tags": {},
        "missing_tags": ["cost:team", "environment"],
        "estimated_monthly_cost_usd": 0.50,
    },
    {
        "arn": "arn:aws:cloudwatch:us-east-1:625962218034:alarm:recoup-spend-alarm",
        "resource_type": "cloudwatch",
        "present_tags": {},
        "missing_tags": ["cost:team", "environment"],
        "estimated_monthly_cost_usd": 0.10,
    },
    {
        "arn": "arn:aws:logs:us-east-1:625962218034:log-group:/recoup/runtime",
        "resource_type": "logs",
        "present_tags": {},
        "missing_tags": ["cost:team", "environment"],
        "estimated_monthly_cost_usd": 0.05,
    },
]


@router.get("/scan")
def scan_tags() -> dict[str, Any]:
    """
    Scan all AWS resources for missing required cost allocation tags.

    Required tags: ``cost:team``, ``environment``

    Calls real ResourceGroupsTaggingAPI when live AWS resources are configured.
    Otherwise returns a deterministic simulation based on the real account
    resource state (EC2, SQS, SNS, CloudWatch, Logs all lack cost:team).

    Returns:
        findings list with ARNs, missing tags, and estimated attribution gap.
    """
    simulated = not settings.live_aws_enabled
    scanned_at = datetime.now(UTC).isoformat()

    if settings.live_aws_enabled:
        try:
            import boto3

            sts = boto3.client("sts")
            account_id = sts.get_caller_identity()["Account"]
            findings = _scan_live(account_id)
            data_source = "live"
        except Exception:  # noqa: BLE001
            findings = list(_SIM_FINDINGS)
            simulated = True
            data_source = "simulation_fallback"
    else:
        findings = list(_SIM_FINDINGS)
        data_source = "simulation"

    total_gap = sum(f["estimated_monthly_cost_usd"] for f in findings)

    return {
        "scanned_at": scanned_at,
        "simulated": simulated,
        "data_source": data_source,
        "required_tags": sorted(_REQUIRED_TAGS),
        "resources_scanned": len(findings),
        "resources_missing_tags": len(findings),
        "estimated_attribution_gap_usd_monthly": round(total_gap, 2),
        "findings": findings,
        "summary": (
            f"{len(findings)} resource{'s' if len(findings) != 1 else ''} found without "
            f"required cost allocation tags — estimated attribution gap: "
            f"${total_gap:.2f}/month"
        ),
        "_aws": {
            "service": "ResourceGroupsTaggingAPI",
            "api": "GetResources",
            "live": not simulated,
        },
    }
