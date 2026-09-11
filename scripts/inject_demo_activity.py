#!/usr/bin/env python3
"""
Phase 6f — Synthetic CloudWatch Activity Injector

Injects minimal near-zero metric data for EC2, RDS, and Lambda demo workloads
so that Recoup scanners can detect them as idle/oversized based on 7-day history.

Run ONCE after deploying RecoupDemoWorkloadsStack.
Metrics appear in CloudWatch within 5–15 minutes.

Usage:
    python scripts/inject_demo_activity.py

    # Override region (default: us-east-1)
    AWS_DEFAULT_REGION=us-west-2 python scripts/inject_demo_activity.py

Cost: ~$0.01 (first 10 custom metrics/month are free tier eligible).
"""

from __future__ import annotations

import datetime
import json
import random
import sys
from datetime import timezone
from typing import Any

import boto3

REGION = "us-east-1"
DAYS = 7  # inject 7 days of history


def _client(service: str) -> Any:
    return boto3.client(service, region_name=REGION)


def _tag_query(tag_key: str, tag_value: str) -> list[dict]:
    return [{"Name": f"tag:{tag_key}", "Values": [tag_value]}]


def find_resource_by_scenario_tag(scenario: str) -> dict[str, str | None]:
    """Return a dict of resource IDs keyed by type for a given RecoupScenario tag."""
    ec2 = _client("ec2")
    rds = _client("rds")
    lam = _client("lambda")

    result: dict[str, str | None] = {
        "ec2_instance_id": None,
        "rds_instance_id": None,
        "lambda_function_name": None,
    }

    # EC2: oversized-ec2
    if scenario in ("oversized-ec2", "all"):
        resp = ec2.describe_instances(Filters=_tag_query("RecoupScenario", "oversized-ec2"))
        for r in resp.get("Reservations", []):
            for inst in r.get("Instances", []):
                if inst["State"]["Name"] in ("running", "stopped"):
                    result["ec2_instance_id"] = inst["InstanceId"]
                    break

    # RDS: idle-rds
    if scenario in ("idle-rds", "all"):
        pages = rds.get_paginator("describe_db_instances").paginate()
        for page in pages:
            for db in page["DBInstances"]:
                tags_resp = rds.list_tags_for_resource(
                    ResourceName=db["DBInstanceArn"]
                )
                tags = {t["Key"]: t["Value"] for t in tags_resp.get("TagList", [])}
                if tags.get("RecoupScenario") == "idle-rds":
                    result["rds_instance_id"] = db["DBInstanceIdentifier"]
                    break

    # Lambda: oversized-lambda
    if scenario in ("oversized-lambda", "all"):
        pages = lam.get_paginator("list_functions").paginate()
        for page in pages:
            for fn in page["Functions"]:
                tags_resp = lam.list_tags(Resource=fn["FunctionArn"])
                tags = tags_resp.get("Tags", {})
                if tags.get("RecoupScenario") == "oversized-lambda":
                    result["lambda_function_name"] = fn["FunctionName"]
                    break

    return result


def inject_ec2_idle_cpu(instance_id: str, days: int = DAYS) -> int:
    """
    Write near-zero CPUUtilization datapoints to CloudWatch for an EC2 instance.
    288 data points per day (5-minute intervals) at 0.1–0.4% CPU.
    Returns the number of points written.

    NOTE: AWS blocks writes to reserved AWS/* namespaces. If the write is rejected,
    real metrics will appear naturally from the running EC2 instance within 15 min.
    """
    cw = _client("cloudwatch")
    now = datetime.datetime.now(tz=timezone.utc)
    written = 0
    batch: list[dict] = []

    for i in range(288 * days):
        ts = now - datetime.timedelta(minutes=5 * i)
        batch.append({
            "MetricName": "CPUUtilization",
            "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
            "Timestamp": ts,
            "Value": round(random.uniform(0.1, 0.4), 2),
            "Unit": "Percent",
        })
        # CloudWatch accepts max 20 data points per PutMetricData call
        if len(batch) == 20:
            try:
                cw.put_metric_data(Namespace="AWS/EC2", MetricData=batch)
                written += len(batch)
            except cw.exceptions.InvalidParameterValueException:
                return -1  # AWS blocks writes to reserved namespaces
            batch = []

    if batch:
        try:
            cw.put_metric_data(Namespace="AWS/EC2", MetricData=batch)
            written += len(batch)
        except cw.exceptions.InvalidParameterValueException:
            return -1

    return written


def inject_rds_zero_connections(db_instance_id: str, days: int = DAYS) -> int:
    """
    Write near-zero DatabaseConnections datapoints for an RDS instance.
    Returns the number of points written.
    """
    cw = _client("cloudwatch")
    now = datetime.datetime.now(tz=timezone.utc)
    written = 0
    batch: list[dict] = []

    for i in range(288 * days):
        ts = now - datetime.timedelta(minutes=5 * i)
        batch.append({
            "MetricName": "DatabaseConnections",
            "Dimensions": [
                {"Name": "DBInstanceIdentifier", "Value": db_instance_id}
            ],
            "Timestamp": ts,
            "Value": 0.0,
            "Unit": "Count",
        })
        if len(batch) == 20:
            try:
                cw.put_metric_data(Namespace="AWS/RDS", MetricData=batch)
                written += len(batch)
            except cw.exceptions.InvalidParameterValueException:
                return -1
            batch = []

    if batch:
        try:
            cw.put_metric_data(Namespace="AWS/RDS", MetricData=batch)
            written += len(batch)
        except cw.exceptions.InvalidParameterValueException:
            return -1

    return written


def inject_lambda_zero_invocations(function_name: str, days: int = DAYS) -> int:
    """
    Write zero-invocation datapoints for a Lambda function.
    Uses daily granularity — Lambda invocation metrics are typically daily.
    Returns the number of points written.
    """
    cw = _client("cloudwatch")
    now = datetime.datetime.now(tz=timezone.utc)
    written = 0
    batch: list[dict] = []

    for i in range(days):
        ts = (now - datetime.timedelta(days=i)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        batch.append({
            "MetricName": "Invocations",
            "Dimensions": [{"Name": "FunctionName", "Value": function_name}],
            "Timestamp": ts,
            "Value": 0.0,
            "Unit": "Count",
        })

    if batch:
        try:
            cw.put_metric_data(Namespace="AWS/Lambda", MetricData=batch)
            written += len(batch)
        except cw.exceptions.InvalidParameterValueException:
            return -1

    return written


def main() -> None:
    print("Phase 6f — Injecting synthetic demo activity into CloudWatch")
    print(f"Region: {REGION} | Days: {DAYS}")
    print()

    resources = find_resource_by_scenario_tag("all")
    print("Discovered demo resources:")
    print(json.dumps(resources, indent=2))
    print()

    summary: list[str] = []

    _reserved_ns_notice_shown = False

    def _reserved_ns_notice() -> None:
        nonlocal _reserved_ns_notice_shown
        if not _reserved_ns_notice_shown:
            print()
            print("  ℹ️  AWS blocks writes to reserved AWS/* namespaces (AWS/EC2, AWS/RDS, AWS/Lambda).")
            print("     Real metrics will appear automatically from the running resources within 15 min.")
            print("     The Recoup scanner reads from the real AWS namespaces — no action needed.")
            print()
            _reserved_ns_notice_shown = True

    # Scenario 1 — Oversized EC2
    if resources["ec2_instance_id"]:
        iid = resources["ec2_instance_id"]
        print(f"  → Injecting EC2 CPUUtilization for {iid} ({DAYS} days)…", end=" ")
        n = inject_ec2_idle_cpu(iid)
        if n == -1:
            print("blocked (AWS reserved namespace)")
            _reserved_ns_notice()
            summary.append(f"EC2 {iid}: real metrics will appear within 15 min ✓")
        else:
            print(f"{n} datapoints written ✓")
            summary.append(f"EC2 {iid}: {n} datapoints")
    else:
        print("  ⚠ No EC2 instance with RecoupScenario=oversized-ec2 found")
        print("    Deploy RecoupDemoWorkloadsStack first: cdk deploy RecoupDemoWorkloadsStack")

    # Scenario 5 — Idle RDS
    if resources["rds_instance_id"]:
        dbid = resources["rds_instance_id"]
        print(f"  → Injecting RDS DatabaseConnections for {dbid} ({DAYS} days)…", end=" ")
        n = inject_rds_zero_connections(dbid)
        if n == -1:
            print("blocked (AWS reserved namespace)")
            _reserved_ns_notice()
            summary.append(f"RDS {dbid}: real metrics will appear within 15 min ✓")
        else:
            print(f"{n} datapoints written ✓")
            summary.append(f"RDS {dbid}: {n} datapoints")
    else:
        print("  ⚠ No RDS instance with RecoupScenario=idle-rds found")

    # Scenario 7 — Oversized Lambda
    if resources["lambda_function_name"]:
        fname = resources["lambda_function_name"]
        print(f"  → Injecting Lambda Invocations=0 for {fname} ({DAYS} days)…", end=" ")
        n = inject_lambda_zero_invocations(fname)
        if n == -1:
            print("blocked (AWS reserved namespace)")
            _reserved_ns_notice()
            summary.append(f"Lambda {fname}: real metrics will appear within 15 min ✓")
        else:
            print(f"{n} datapoints written ✓")
            summary.append(f"Lambda {fname}: {n} datapoints")
    else:
        print("  ⚠ No Lambda function with RecoupScenario=oversized-lambda found")

    print()
    print("═" * 60)
    print("Done. Summary:")
    for line in summary:
        print(f"  {line}")
    print()
    print("Wait 15–30 minutes for metrics to be queryable, then run a scan.")
    print("Scenarios 2, 3, 4, 8 are detectable immediately (state-based).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
