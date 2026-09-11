"""Cost Explorer scanner — RI/Savings Plans coverage gap, top-5 services by spend."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .base import BaseScanner
from .finding import Finding


class CostExplorerScanner(BaseScanner):
    service_name = "Cost Explorer"

    def _scan(self, session: Any, region: str) -> list[Finding]:
        findings: list[Finding] = []
        ce = session.client("ce", region_name="us-east-1")

        end = date.today()
        start = end - timedelta(days=30)
        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")

        # Top-5 services by spend
        resp = ce.get_cost_and_usage(
            TimePeriod={"Start": start_str, "End": end_str},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        results = resp.get("ResultsByTime", [])
        if results:
            groups = sorted(
                results[0].get("Groups", []),
                key=lambda g: float(g["Metrics"]["UnblendedCost"]["Amount"]),
                reverse=True,
            )
            for grp in groups[:5]:
                service = grp["Keys"][0]
                amount = float(grp["Metrics"]["UnblendedCost"]["Amount"])
                if amount > 10.0:
                    findings.append(Finding(
                        service="Cost Explorer",
                        resource_id=service,
                        resource_type="AWS::CostExplorer::ServiceSpend",
                        issue=f"{service} spent ${amount:.2f} in the last 30 days",
                        estimated_monthly_savings_usd=round(amount * 0.20, 2),
                        recommendation=(
                            "Review for Reserved Instance or Savings Plans coverage to "
                            "reduce on-demand spend by 20-40%"
                        ),
                        severity="high" if amount > 100 else "medium",
                        region="global",
                    ))

        # RI/SP coverage check
        try:
            cov_resp = ce.get_reservation_coverage(
                TimePeriod={"Start": start_str, "End": end_str},
                Granularity="MONTHLY",
            )
            cov_results = cov_resp.get("Total", {})
            coverage_pct = float(
                cov_results.get("CoverageHours", {}).get("CoverageHoursPercentage", "100")
            )
            if coverage_pct < 50.0:
                findings.append(Finding(
                    service="Cost Explorer",
                    resource_id="ri-coverage",
                    resource_type="AWS::CostExplorer::ReservationCoverage",
                    issue=(
                        f"Reserved Instance coverage is {coverage_pct:.1f}%"
                        " — most spend is on-demand"
                    ),
                    estimated_monthly_savings_usd=0.0,
                    recommendation=(
                        "Purchase Reserved Instances or Savings Plans for steady-state workloads "
                        "to save 30-60% vs on-demand pricing"
                    ),
                    severity="high" if coverage_pct < 20 else "medium",
                    region="global",
                ))
        except Exception:  # noqa: BLE001, S110
            pass

        return findings
