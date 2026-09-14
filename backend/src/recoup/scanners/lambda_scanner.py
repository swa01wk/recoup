"""Lambda scanner — over-provisioned memory (high memory, sub-10ms avg duration)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .base import BaseScanner
from .finding import Finding

_GB_SECOND_PRICE = 0.0000166667


class LambdaScanner(BaseScanner):
    service_name = "Lambda"

    def _scan(self, session: Any, region: str) -> list[Finding]:
        findings: list[Finding] = []
        lam = session.client("lambda", region_name=region)
        cw = session.client("cloudwatch", region_name=region)

        paginator = lam.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page["Functions"]:
                name = fn["FunctionName"]
                memory_mb = fn.get("MemorySize", 128)

                if memory_mb < 512:
                    continue

                # Read tags for scenario detection
                fn_tags: dict[str, str] = fn.get("Tags", {})
                if not fn_tags:
                    try:
                        fn_tags = lam.list_tags(Resource=fn["FunctionArn"]).get("Tags", {})
                    except Exception:  # noqa: BLE001
                        fn_tags = {}
                scenario = fn_tags.get("RecoupScenario")
                is_demo = fn_tags.get("RecoupDemo", "").lower() == "true"

                end = datetime.now(UTC)
                start = end - timedelta(days=7)
                resp = cw.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Duration",
                    Dimensions=[{"Name": "FunctionName", "Value": name}],
                    StartTime=start,
                    EndTime=end,
                    Period=604800,
                    Statistics=["Average"],
                )
                datapoints = resp.get("Datapoints", [])

                target_memory = max(128, memory_mb // 4)
                savings_ratio = 1 - (target_memory / memory_mb)

                if not datapoints:
                    # Never invoked in the past 7 days — high memory with zero usage
                    findings.append(Finding(
                        service="Lambda",
                        resource_id=name,
                        resource_type="AWS::Lambda::Function",
                        finding_type="OVERSIZED_LAMBDA",
                        issue=(
                            f"Function {name} has {memory_mb}MB memory but 0 invocations "
                            f"over 7 days — appears unused"
                        ),
                        estimated_monthly_savings_usd=round(savings_ratio * 5.0, 2),
                        recommendation=(
                            f"Reduce memory from {memory_mb}MB to {target_memory}MB "
                            "or delete if unused"
                        ),
                        severity="medium",
                        region=region,
                        scenario_tag=scenario,
                        is_demo_resource=is_demo,
                        evidence={
                            "configured_memory_mb": memory_mb,
                            "invocation_count_30d": 0,
                            "p99_duration_ms": "no_data",
                            "error_rate": "no_data",
                            "compute_optimizer_recommendation": f"Reduce to {target_memory}MB",
                            "scenario_tag": scenario or "",
                        },
                    ))
                    continue

                avg_duration_ms = datapoints[0]["Average"]
                if avg_duration_ms < 10.0:
                    findings.append(Finding(
                        service="Lambda",
                        resource_id=name,
                        resource_type="AWS::Lambda::Function",
                        finding_type="OVERSIZED_LAMBDA",
                        issue=(
                            f"Function {name} has {memory_mb}MB memory but avg duration "
                            f"{avg_duration_ms:.1f}ms — likely over-provisioned"
                        ),
                        estimated_monthly_savings_usd=round(savings_ratio * 5.0, 2),
                        recommendation=f"Reduce memory from {memory_mb}MB to {target_memory}MB",
                        severity="low",
                        region=region,
                        scenario_tag=scenario,
                        is_demo_resource=is_demo,
                        evidence={
                            "configured_memory_mb": memory_mb,
                            "p99_duration_ms": f"{avg_duration_ms:.1f}",
                            "compute_optimizer_recommendation": f"Reduce to {target_memory}MB",
                            "scenario_tag": scenario or "",
                        },
                    ))

        return findings
