"""RDS scanner — low-connection instances, single-AZ production DBs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..config import settings
from .base import BaseScanner
from .finding import Finding

_RDS_HOURLY: dict[str, float] = {
    "db.t3.micro": 0.017, "db.t3.small": 0.034, "db.t3.medium": 0.068,
    "db.t3.large": 0.136, "db.m5.large": 0.192, "db.m5.xlarge": 0.384,
    "db.r5.large": 0.24, "db.r5.xlarge": 0.48,
}


class RDSScanner(BaseScanner):
    service_name = "RDS"

    def _scan(self, session: Any, region: str) -> list[Finding]:
        findings: list[Finding] = []
        rds = session.client("rds", region_name=region)
        cw = session.client("cloudwatch", region_name=region)

        paginator = rds.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for db in page["DBInstances"]:
                dbid = db["DBInstanceIdentifier"]
                dbclass = db["DBInstanceClass"]
                engine = db["Engine"]
                multi_az = db.get("MultiAZ", False)

                # Check connection count over lookback window
                end = datetime.now(UTC)
                start = end - timedelta(days=settings.recoup_rds_lookback_days)
                period_secs = settings.recoup_rds_lookback_days * 86400
                resp = cw.get_metric_statistics(
                    Namespace="AWS/RDS",
                    MetricName="DatabaseConnections",
                    Dimensions=[{"Name": "DBInstanceIdentifier", "Value": dbid}],
                    StartTime=start,
                    EndTime=end,
                    Period=period_secs,
                    Statistics=["Average"],
                )
                datapoints = resp.get("Datapoints", [])
                avg_connections = datapoints[0]["Average"] if datapoints else None

                # Get tags for demo resource detection.
                # Try rds:ListTagsForResource first; fall back to ResourceGroupsTaggingAPI
                # (tag:GetResources) which is always permitted in RecoupReadOnlyRole.
                tags: dict[str, str] = {}
                db_arn = db.get("DBInstanceArn", "")
                try:
                    tag_resp = rds.list_tags_for_resource(ResourceName=db_arn)
                    tags = {t["Key"]: t["Value"] for t in tag_resp.get("TagList", [])}
                except Exception:  # noqa: BLE001
                    # Fallback: ResourceGroupsTaggingAPI (tag:GetResources is permitted).
                    # Do NOT combine ResourceARNList with ResourceTypeFilters — AWS treats
                    # them as mutually exclusive filters and may return empty results.
                    try:
                        tagging = session.client("resourcegroupstaggingapi", region_name=region)
                        res = tagging.get_resources(ResourceARNList=[db_arn])
                        for r in res.get("ResourceTagMappingList", []):
                            # Normalise ARN casing before comparison
                            if r.get("ResourceARN", "").lower() == db_arn.lower():
                                tags = {t["Key"]: t["Value"] for t in r.get("Tags", [])}
                    except Exception:  # noqa: BLE001
                        tags = {}
                scenario = tags.get("RecoupScenario")
                is_demo = tags.get("RecoupDemo", "").lower() == "true"

                monthly = _RDS_HOURLY.get(dbclass, 0.10) * 730

                if avg_connections is not None and avg_connections < 1.0:
                    findings.append(Finding(
                        service="RDS",
                        resource_id=dbid,
                        resource_type="AWS::RDS::DBInstance",
                        finding_type="IDLE_RDS",
                        issue=(
                            f"DB instance {dbid} ({dbclass}/{engine}) avg connections "
                            f"{avg_connections:.1f}/day over "
                            f"{settings.recoup_rds_lookback_days}d — appears idle"
                        ),
                        estimated_monthly_savings_usd=monthly,
                        recommendation="Stop or delete idle RDS instance to eliminate charges",
                        severity="high",
                        region=region,
                        scenario_tag=scenario,
                        is_demo_resource=is_demo,
                        evidence={
                            "instance_class": dbclass,
                            "engine": engine,
                            "cpu_avg": "n/a",
                            "connection_count_avg": f"{avg_connections:.1f}",
                            "io_signals": "idle",
                            "cost_context": f"${monthly:.2f}/month",
                            "scenario_tag": scenario or "",
                        },
                    ))
                elif avg_connections is None:
                    # No CloudWatch history yet — new or never-connected instance.
                    # Flag as potentially idle so demo scanners surface it immediately.
                    findings.append(Finding(
                        service="RDS",
                        resource_id=dbid,
                        resource_type="AWS::RDS::DBInstance",
                        finding_type="IDLE_RDS",
                        issue=(
                            f"DB instance {dbid} ({dbclass}/{engine}) has no connection "
                            f"history in the past {settings.recoup_rds_lookback_days}d — "
                            "appears idle / newly launched"
                        ),
                        estimated_monthly_savings_usd=monthly,
                        recommendation="Stop or delete if unused; no connections recorded",
                        severity="medium",
                        region=region,
                        scenario_tag=scenario,
                        is_demo_resource=is_demo,
                        evidence={
                            "instance_class": dbclass,
                            "engine": engine,
                            "cpu_avg": "no_data",
                            "connection_count_avg": "no_data",
                            "io_signals": "no_history",
                            "cost_context": f"${monthly:.2f}/month",
                            "scenario_tag": scenario or "",
                        },
                    ))
                elif not multi_az and "prod" in dbid.lower():
                    findings.append(Finding(
                        service="RDS",
                        resource_id=dbid,
                        resource_type="AWS::RDS::DBInstance",
                        issue=(
                            f"Production DB {dbid} is Single-AZ"
                            " — risk of data loss on AZ failure"
                        ),
                        estimated_monthly_savings_usd=0.0,
                        recommendation="Enable Multi-AZ for production workloads",
                        severity="medium",
                        region=region,
                    ))

        return findings
