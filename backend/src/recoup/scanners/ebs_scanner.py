"""EBS scanner — unattached volumes, gp2 migration candidates, stale snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..config import settings
from .base import BaseScanner
from .finding import Finding

_GB_COST_PER_MONTH_GP2 = 0.10   # gp2 ~$0.10/GB/month
_GB_COST_PER_MONTH_GP3 = 0.08   # gp3 ~$0.08/GB/month  (same perf, lower cost)
_GB_COST_PER_MONTH_SNAP = 0.05  # EBS snapshot ~$0.05/GB/month


def _get_tags(tag_list: list[dict[str, str]]) -> dict[str, str]:
    return {t["Key"]: t["Value"] for t in tag_list}


def _is_demo(tags: dict[str, str]) -> bool:
    return tags.get("RecoupDemo", "").lower() == "true"


class EBSScanner(BaseScanner):
    service_name = "EBS"

    def _scan(self, session: Any, region: str) -> list[Finding]:
        findings: list[Finding] = []
        ec2 = session.client("ec2", region_name=region)

        # ── Scenario 2: Unattached volumes ───────────────────────────────────
        paginator = ec2.get_paginator("describe_volumes")
        for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
            for vol in page["Volumes"]:
                size_gb = vol.get("Size", 0)
                vtype = vol.get("VolumeType", "gp2")
                monthly = size_gb * _GB_COST_PER_MONTH_GP2
                tags = _get_tags(vol.get("Tags", []))
                scenario = tags.get("RecoupScenario")
                is_demo = _is_demo(tags)

                findings.append(Finding(
                    service="EBS",
                    resource_id=vol["VolumeId"],
                    resource_type="AWS::EC2::Volume",
                    finding_type="UNATTACHED_VOLUME",
                    issue=f"Unattached {size_gb} GiB {vtype} volume",
                    estimated_monthly_savings_usd=monthly,
                    recommendation="Delete volume or create a snapshot then delete",
                    severity="medium" if monthly > 10 else "low",
                    region=region,
                    scenario_tag=scenario,
                    is_demo_resource=is_demo,
                    evidence={
                        "volume_type": vtype,
                        "size_gib": size_gb,
                        "attachment_state": "available",
                        "availability_zone": vol.get("AvailabilityZone", ""),
                        "iops_config": vol.get("Iops"),
                        "throughput_config": vol.get("Throughput"),
                        "created": str(vol.get("CreateTime", "")),
                        "snapshot_relationships": vol.get("SnapshotId") or "none",
                        "scenario_tag": scenario or "",
                    },
                ))

        # ── Scenario 3: gp2 migration candidates ─────────────────────────────
        for page in paginator.paginate(Filters=[{"Name": "volume-type", "Values": ["gp2"]}]):
            for vol in page["Volumes"]:
                # Skip already reported (unattached gp2 volumes)
                if vol.get("State") == "available":
                    continue
                size_gb = vol.get("Size", 0)
                # gp2→gp3 saves ~20% at same or better performance
                savings = round(size_gb * (_GB_COST_PER_MONTH_GP2 - _GB_COST_PER_MONTH_GP3), 2)
                tags = _get_tags(vol.get("Tags", []))
                scenario = tags.get("RecoupScenario")
                is_demo = _is_demo(tags)

                findings.append(Finding(
                    service="EBS",
                    resource_id=vol["VolumeId"],
                    resource_type="AWS::EC2::Volume",
                    finding_type="GP2_MIGRATION_CANDIDATE",
                    issue=(
                        f"Volume {vol['VolumeId']} is {size_gb} GiB gp2 — "
                        "migrating to gp3 saves ~20% at equal performance"
                    ),
                    estimated_monthly_savings_usd=savings,
                    recommendation=(
                        "Modify volume type from gp2 to gp3 via AWS console or CLI: "
                        f"aws ec2 modify-volume --volume-id {vol['VolumeId']} --volume-type gp3"
                    ),
                    severity="medium",
                    region=region,
                    scenario_tag=scenario,
                    is_demo_resource=is_demo,
                    evidence={
                        "volume_type": "gp2",
                        "size_gib": size_gb,
                        "attachment_state": vol.get("State", ""),
                        "iops_config": vol.get("Iops"),
                        "throughput_config": vol.get("Throughput"),
                        "current_monthly_cost_usd": round(size_gb * _GB_COST_PER_MONTH_GP2, 2),
                        "gp3_monthly_cost_usd": round(size_gb * _GB_COST_PER_MONTH_GP3, 2),
                        "scenario_tag": scenario or "",
                    },
                ))

        # ── Scenario 8: Stale snapshots (>90 days, source volume deleted) ────
        snap_paginator = ec2.get_paginator("describe_snapshots")
        try:
            caller_id = session.client("sts").get_caller_identity()
            owner_id = caller_id.get("Account", "self")
        except Exception:  # noqa: BLE001
            owner_id = "self"

        for page in snap_paginator.paginate(OwnerIds=[owner_id]):
            for snap in page["Snapshots"]:
                start_time = snap.get("StartTime")
                if not start_time:
                    continue
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                age_days = (datetime.now(UTC) - start_time).days
                if age_days < settings.recoup_stale_snapshot_days:
                    continue

                # Check if source volume still exists
                source_vol_id = snap.get("VolumeId", "")
                source_exists = False
                if source_vol_id and source_vol_id != "vol-ffffffff":
                    try:
                        resp = ec2.describe_volumes(VolumeIds=[source_vol_id])
                        source_exists = len(resp.get("Volumes", [])) > 0
                    except Exception:  # noqa: BLE001
                        source_exists = False  # volume not found = deleted

                if source_exists:
                    continue

                size_gb = snap.get("VolumeSize", 0)
                monthly = round(size_gb * _GB_COST_PER_MONTH_SNAP, 2)
                tags = _get_tags(snap.get("Tags", []))
                scenario = tags.get("RecoupScenario")
                is_demo = _is_demo(tags)

                findings.append(Finding(
                    service="EBS",
                    resource_id=snap["SnapshotId"],
                    resource_type="AWS::EC2::Snapshot",
                    finding_type="STALE_SNAPSHOT",
                    issue=(
                        f"Snapshot {snap['SnapshotId']} is {age_days} days old; "
                        "source volume has been deleted — no restore target"
                    ),
                    estimated_monthly_savings_usd=monthly,
                    recommendation="Delete snapshot — source volume no longer exists",
                    severity="low",
                    region=region,
                    scenario_tag=scenario,
                    is_demo_resource=is_demo,
                    evidence={
                        "age_days": age_days,
                        "source_volume": source_vol_id or "unknown",
                        "source_volume_state": "deleted",
                        "size_gib": size_gb,
                        "description": snap.get("Description", ""),
                        "created": str(start_time),
                        "scenario_tag": scenario or "",
                    },
                ))

        return findings
