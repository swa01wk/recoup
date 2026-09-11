"""S3 scanner — buckets with no lifecycle policy."""

from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from .base import BaseScanner
from .finding import Finding


class S3Scanner(BaseScanner):
    service_name = "S3"

    def _scan(self, session: Any, region: str) -> list[Finding]:
        findings: list[Finding] = []
        s3 = session.client("s3", region_name=region)

        resp = s3.list_buckets()
        for bucket in resp.get("Buckets", []):
            name = bucket["Name"]
            try:
                self._scan_bucket(s3, name, region, findings)
            except Exception:  # noqa: BLE001
                # One bad bucket (redirect error, timeout, etc.) must not
                # stop the rest of the scan.
                pass

        return findings

    def _scan_bucket(
        self,
        s3: Any,
        name: str,
        region: str,
        findings: list[Finding],
    ) -> None:
        """Inspect a single S3 bucket and append a finding if applicable."""
        # Fetch tags for scenario/demo detection.
        # Catch any exception (not just ClientError) so cross-region redirect
        # errors or transient network issues don't propagate to the caller.
        try:
            tag_resp = s3.get_bucket_tagging(Bucket=name)
            tags = {t["Key"]: t["Value"] for t in tag_resp.get("TagSet", [])}
        except Exception:  # noqa: BLE001
            tags = {}

        scenario = tags.get("RecoupScenario")
        is_demo = tags.get("RecoupDemo", "").lower() == "true"

        try:
            s3.get_bucket_lifecycle_configuration(Bucket=name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchLifecycleConfiguration":
                findings.append(Finding(
                    service="S3",
                    resource_id=name,
                    resource_type="AWS::S3::Bucket",
                    finding_type="NO_LIFECYCLE_POLICY",
                    issue=(
                        f"Bucket '{name}' has no lifecycle policy"
                        " — objects accumulate indefinitely"
                    ),
                    estimated_monthly_savings_usd=5.0,
                    recommendation=(
                        "Add lifecycle rules to transition old objects to S3-IA or Glacier "
                        "and expire non-current versions"
                    ),
                    severity="low",
                    region=region,
                    scenario_tag=scenario,
                    is_demo_resource=is_demo,
                    evidence={
                        "lifecycle_policy_state": "none",
                        "storage_class_distribution": "STANDARD",
                        "scenario_tag": scenario or "",
                    },
                ))
            # Any other ClientError (AccessDenied, etc.) — skip bucket silently
        except Exception:  # noqa: BLE001, S110
            pass
