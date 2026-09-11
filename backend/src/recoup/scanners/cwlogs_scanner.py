"""CloudWatch Logs scanner — log groups with no retention policy."""

from __future__ import annotations

from typing import Any

from .base import BaseScanner
from .finding import Finding

_CW_LOGS_GB_MONTH = 0.50  # $0.50/GB stored


class CWLogsScanner(BaseScanner):
    service_name = "CloudWatch Logs"

    def _scan(self, session: Any, region: str) -> list[Finding]:
        findings: list[Finding] = []
        logs = session.client("logs", region_name=region)

        paginator = logs.get_paginator("describe_log_groups")
        for page in paginator.paginate():
            for lg in page["logGroups"]:
                name = lg["logGroupName"]
                retention = lg.get("retentionInDays")
                stored_bytes = lg.get("storedBytes", 0)

                if retention is None:
                    stored_gb = stored_bytes / (1024 ** 3)
                    monthly = round(stored_gb * _CW_LOGS_GB_MONTH + 0.50, 2)
                    findings.append(Finding(
                        service="CloudWatch Logs",
                        resource_id=name,
                        resource_type="AWS::Logs::LogGroup",
                        issue=(
                            f"Log group '{name}' has no retention policy — "
                            f"{stored_bytes / (1024**3):.2f} GB stored indefinitely"
                        ),
                        estimated_monthly_savings_usd=monthly,
                        recommendation=(
                            "Set a retention policy (e.g. 30 or 90 days)"
                            " to control storage costs"
                        ),
                        severity="low",
                        region=region,
                    ))

        return findings
