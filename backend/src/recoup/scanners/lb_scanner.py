"""Load Balancer scanner — idle ALBs/NLBs (no requests for 7 days)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .base import BaseScanner
from .finding import Finding

_LB_MONTHLY_COST = 16.20  # ~$0.008/hour fixed + LCU charges; fixed alone is ~$5.76/month


class LBScanner(BaseScanner):
    service_name = "ELB"

    def _scan(self, session: Any, region: str) -> list[Finding]:
        findings: list[Finding] = []
        elbv2 = session.client("elbv2", region_name=region)
        cw = session.client("cloudwatch", region_name=region)

        paginator = elbv2.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for lb in page["LoadBalancers"]:
                arn = lb["LoadBalancerArn"]
                name = lb["LoadBalancerName"]
                lb_type = lb.get("Type", "application").upper()
                metric = "RequestCount" if lb_type == "APPLICATION" else "ProcessedBytes"
                namespace = "AWS/ApplicationELB" if lb_type == "APPLICATION" else "AWS/NetworkELB"

                end = datetime.now(UTC)
                start = end - timedelta(days=7)
                resp = cw.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric,
                    Dimensions=[{"Name": "LoadBalancer", "Value": arn.split("loadbalancer/")[-1]}],
                    StartTime=start,
                    EndTime=end,
                    Period=604800,
                    Statistics=["Sum"],
                )
                datapoints = resp.get("Datapoints", [])
                total = datapoints[0]["Sum"] if datapoints else 0

                if total == 0:
                    findings.append(Finding(
                        service="ELB",
                        resource_id=arn,
                        resource_type=f"AWS::ElasticLoadBalancingV2::{lb_type.capitalize()}LoadBalancer",
                        issue=f"{lb_type} Load Balancer '{name}' had 0 requests/bytes over 7 days",
                        estimated_monthly_savings_usd=_LB_MONTHLY_COST,
                        recommendation=(
                            "Delete idle load balancer to eliminate"
                            " fixed hourly charges"
                        ),
                        severity="medium",
                        region=region,
                    ))

        return findings
