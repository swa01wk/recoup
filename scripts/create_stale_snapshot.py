#!/usr/bin/env python3
"""
Phase 6f - Scenario 8: Create and tag the Stale EBS Snapshot demo resource.

CDK cannot create standalone EBS snapshots natively, so this script:
1. Finds the unattached-ebs volume deployed by RecoupDemoWorkloadsStack
2. Creates a snapshot of that volume
3. Tags the snapshot with RecoupScenario=stale-snapshot and all standard demo tags

The EBSScanner detects snapshots > 90 days old whose source volume is deleted.
For demo purposes, if you need immediate detection, set DEMO_THRESHOLD_DAYS=1
in the environment when running the scanner (or reduce the age check to 1 day
for the demo session).

Usage:
    python scripts/create_stale_snapshot.py

    # Dry-run (show what would happen, no AWS calls)
    DRY_RUN=1 python scripts/create_stale_snapshot.py
"""

from __future__ import annotations

import os
import sys

import boto3

REGION = "us-east-1"
DRY_RUN = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

DEMO_TAGS = [
    {"Key": "Project",          "Value": "Recoup"},
    {"Key": "Environment",      "Value": "hackathon-demo"},
    {"Key": "RecoupDemo",       "Value": "true"},
    {"Key": "ManagedBy",        "Value": "CDK"},
    {"Key": "RecoupScenario",   "Value": "stale-snapshot"},
    {"Key": "Name",             "Value": "recoup-demo-stale-snapshot"},
]


def find_unattached_ebs_volume() -> str | None:
    ec2 = boto3.client("ec2", region_name=REGION)
    resp = ec2.describe_volumes(
        Filters=[
            {"Name": "tag:RecoupScenario", "Values": ["unattached-ebs"]},
            {"Name": "tag:RecoupDemo",      "Values": ["true"]},
        ]
    )
    volumes = resp.get("Volumes", [])
    if not volumes:
        return None
    return volumes[0]["VolumeId"]


def create_snapshot(volume_id: str) -> str:
    ec2 = boto3.client("ec2", region_name=REGION)
    print(f"  Creating snapshot from volume {volume_id}…")
    resp = ec2.create_snapshot(
        VolumeId=volume_id,
        Description="Recoup Phase 6f demo - stale snapshot (scenario 8)",
    )
    snap_id = resp["SnapshotId"]
    print(f"  Snapshot created: {snap_id}")

    print(f"  Tagging snapshot {snap_id}…")
    ec2.create_tags(Resources=[snap_id], Tags=DEMO_TAGS)
    print("  Tags applied ✓")

    return snap_id


def main() -> None:
    print("Phase 6f - Creating Stale EBS Snapshot (Scenario 8)")
    if DRY_RUN:
        print("  [DRY_RUN=1 - no AWS calls will be made]")
    print(f"  Region: {REGION}")
    print()

    # Step 1: Find the unattached-ebs volume
    print("Step 1: Locating unattached-ebs demo volume…")
    if DRY_RUN:
        print("  (dry-run) Would call ec2.describe_volumes(tag:RecoupScenario=unattached-ebs)")
        volume_id = "vol-DRYRUN00000000000"
    else:
        volume_id = find_unattached_ebs_volume()
        if not volume_id:
            print("  ✗ No volume with RecoupScenario=unattached-ebs found.")
            print()
            print("  Ensure RecoupDemoWorkloadsStack is deployed:")
            print("    cdk deploy RecoupDemoWorkloadsStack")
            sys.exit(1)
    print(f"  Found volume: {volume_id} ✓")

    # Step 2: Create snapshot
    print()
    print("Step 2: Creating and tagging snapshot…")
    if DRY_RUN:
        snap_id = "snap-DRYRUN00000000000"
        print(f"  (dry-run) Would create snapshot from {volume_id}")
        print("  (dry-run) Would tag snapshot as RecoupScenario=stale-snapshot")
    else:
        snap_id = create_snapshot(volume_id)

    print()
    print("═" * 60)
    print(f"Scenario 8 ready: {snap_id}")
    print()
    print("Note: The EBSScanner flags snapshots > 90 days old.")
    print("For immediate demo detection, the scanner threshold can be lowered")
    print("by setting RECOUP_STALE_SNAPSHOT_DAYS=1 before running a scan.")
    print()
    print("To verify the snapshot exists:")
    print(f"  aws ec2 describe-snapshots --snapshot-ids {snap_id}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
