"""EIP scanner — unassociated Elastic IPs (~$3.65/month each)."""

from __future__ import annotations

from typing import Any

from .base import BaseScanner
from .finding import Finding

_EIP_MONTHLY_COST = 3.65


class EIPScanner(BaseScanner):
    service_name = "EIP"

    def _scan(self, session: Any, region: str) -> list[Finding]:
        findings: list[Finding] = []
        ec2 = session.client("ec2", region_name=region)

        resp = ec2.describe_addresses()
        for addr in resp.get("Addresses", []):
            if not addr.get("AssociationId"):
                tags = {t["Key"]: t["Value"] for t in addr.get("Tags", [])}
                scenario = tags.get("RecoupScenario")
                is_demo = tags.get("RecoupDemo", "").lower() == "true"
                findings.append(Finding(
                    service="EIP",
                    resource_id=addr.get("AllocationId", addr.get("PublicIp", "unknown")),
                    resource_type="AWS::EC2::EIP",
                    finding_type="IDLE_EIP",
                    issue=f"Unassociated Elastic IP {addr.get('PublicIp', '')}",
                    estimated_monthly_savings_usd=_EIP_MONTHLY_COST,
                    recommendation="Release the Elastic IP address if no longer needed",
                    severity="low",
                    region=region,
                    scenario_tag=scenario,
                    is_demo_resource=is_demo,
                    evidence={
                        "eip_association_state": "unassociated",
                        "public_ip": addr.get("PublicIp", ""),
                        "allocation_id": addr.get("AllocationId", ""),
                        "public_ipv4_owner": addr.get("Domain", "vpc"),
                        "scenario_tag": scenario or "",
                    },
                ))

        return findings
