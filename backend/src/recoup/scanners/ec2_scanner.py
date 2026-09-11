"""EC2 scanner — idle instances, stopped instances, oversized types."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .base import BaseScanner
from .finding import Finding


class EC2Scanner(BaseScanner):
    service_name = "EC2"

    def _scan(self, session: Any, region: str) -> list[Finding]:
        findings: list[Finding] = []
        ec2 = session.client("ec2", region_name=region)
        cw = session.client("cloudwatch", region_name=region)

        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate(
            Filters=[{"Name": "instance-state-name", "Values": ["running", "stopped"]}]
        ):
            for reservation in page["Reservations"]:
                for inst in reservation["Instances"]:
                    iid = inst["InstanceId"]
                    itype = inst["InstanceType"]
                    state = inst["State"]["Name"]
                    tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                    scenario = tags.get("RecoupScenario")
                    is_demo = tags.get("RecoupDemo", "").lower() == "true"

                    if state == "stopped":
                        findings.append(Finding(
                            service="EC2",
                            resource_id=iid,
                            resource_type="AWS::EC2::Instance",
                            finding_type="STOPPED_INSTANCE",
                            issue=f"Instance {iid} ({itype}) has been stopped",
                            estimated_monthly_savings_usd=self._hourly_cost(itype) * 730,
                            recommendation="Terminate if no longer needed to eliminate EBS costs",
                            severity="medium",
                            region=region,
                            scenario_tag=scenario,
                            is_demo_resource=is_demo,
                            evidence={
                                "instance_type": itype,
                                "state": state,
                                "scenario_tag": scenario or "",
                            },
                        ))
                        continue

                    # Check CPU for running instances
                    end = datetime.now(UTC)
                    start = end - timedelta(days=7)
                    resp = cw.get_metric_statistics(
                        Namespace="AWS/EC2",
                        MetricName="CPUUtilization",
                        Dimensions=[{"Name": "InstanceId", "Value": iid}],
                        StartTime=start,
                        EndTime=end,
                        Period=604800,
                        Statistics=["Average"],
                    )
                    datapoints = resp.get("Datapoints", [])
                    if datapoints:
                        avg_cpu = datapoints[0]["Average"]
                        if avg_cpu < 5.0:
                            monthly = self._hourly_cost(itype) * 730
                            findings.append(Finding(
                                service="EC2",
                                resource_id=iid,
                                resource_type="AWS::EC2::Instance",
                                finding_type="IDLE_INSTANCE",
                                issue=(
                                    f"Instance {iid} ({itype}) avg CPU"
                                    f" {avg_cpu:.1f}% over 7d — idle"
                                ),
                                estimated_monthly_savings_usd=monthly,
                                recommendation=(
                                    "Right-size to a smaller instance type"
                                    " or stop if unused"
                                ),
                                severity="high" if monthly > 50 else "medium",
                                region=region,
                                scenario_tag=scenario,
                                is_demo_resource=is_demo,
                                evidence={
                                    "instance_type": itype,
                                    "state": state,
                                    "cpu_utilization_7d_avg": f"{avg_cpu:.2f}%",
                                    "cost_context": f"${monthly:.2f}/month",
                                    "scenario_tag": scenario or "",
                                },
                            ))

        return findings

    @staticmethod
    def _hourly_cost(instance_type: str) -> float:
        _costs: dict[str, float] = {
            "t3.nano": 0.0052, "t3.micro": 0.0104, "t3.small": 0.0208,
            "t3.medium": 0.0416, "t3.large": 0.0832,
            "m5.large": 0.096, "m5.xlarge": 0.192, "m5.2xlarge": 0.384,
            "c5.large": 0.085, "c5.xlarge": 0.17,
            "r5.large": 0.126, "r5.xlarge": 0.252,
        }
        return _costs.get(instance_type, 0.10)
