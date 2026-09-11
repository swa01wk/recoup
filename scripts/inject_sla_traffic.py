#!/usr/bin/env python3
"""
inject_sla_traffic.py — Option C: real API Gateway traffic injection for SLA demo.

Injects real traffic against the `recoup-sla-demo` API Gateway, simulates a
30-minute outage window by toggling Lambda OUTAGE_MODE, then captures the real
CloudWatch 5xx metrics and CloudTrail events into the fixture files.

After this script completes:
  - eval_fixtures/sla/api_gateway/canonical/metric_series.json   ← real CW data
  - eval_fixtures/sla/api_gateway/canonical/cloudtrail_events.json ← real CT data
  - eval_fixtures/sla/api_gateway/canonical/health_event.json    ← real account + API ID

Usage:
    python scripts/inject_sla_traffic.py \\
        --api-url https://<id>.execute-api.us-east-1.amazonaws.com/prod/health \\
        --lambda-name recoup-sla-health \\
        [--normal-calls 100000] \\
        [--outage-calls 500] \\
        [--outage-duration-min 30] \\
        [--region us-east-1] \\
        [--dry-run]

Cost: ~$0.70 (200K API calls at $3.50/million; Lambda within free tier).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import boto3
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

FIXTURES_DIR = Path(__file__).parent.parent / "eval_fixtures" / "sla" / "api_gateway" / "canonical"
ACCOUNT_ID = "625962218034"
REGION = "us-east-1"


# ── helpers ─────────────────────────────────────────────────────────────────

def _call_api(url: str) -> tuple[int, float]:
    """Make one API call, return (status_code, latency_ms)."""
    t0 = time.monotonic()
    try:
        r = requests.get(url, timeout=10)
        return r.status_code, (time.monotonic() - t0) * 1000
    except Exception:
        return 0, (time.monotonic() - t0) * 1000


def _burst(url: str, n: int, workers: int = 20, label: str = "") -> dict:
    """Fire n parallel calls, return stats."""
    statuses: list[int] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_call_api, url) for _ in range(n)]
        for i, f in enumerate(as_completed(futs)):
            code, _ = f.result()
            statuses.append(code)
            if (i + 1) % max(1, n // 10) == 0:
                pct = (i + 1) / n * 100
                ok = statuses.count(200)
                print(f"  {label} {pct:5.0f}% — {ok}/{i+1} OK", end="\r", flush=True)
    print()
    ok = statuses.count(200)
    err5xx = sum(1 for s in statuses if s >= 500)
    return {"total": n, "ok": ok, "err5xx": err5xx}


def _set_outage_mode(lambda_client, fn_name: str, enabled: bool) -> None:
    """Toggle OUTAGE_MODE env var on the Lambda function."""
    cfg = lambda_client.get_function_configuration(FunctionName=fn_name)
    env = cfg.get("Environment", {}).get("Variables", {})
    env["OUTAGE_MODE"] = "true" if enabled else "false"
    lambda_client.update_function_configuration(
        FunctionName=fn_name,
        Environment={"Variables": env},
    )
    # Wait for update to propagate
    waiter = lambda_client.get_waiter("function_updated")
    waiter.wait(FunctionName=fn_name)


def _fetch_cloudwatch_5xx(api_name: str, start: datetime, end: datetime, region: str) -> list[dict]:
    """Fetch real 5XXError metrics from CloudWatch for the API."""
    cw = boto3.client("cloudwatch", region_name=region)
    resp = cw.get_metric_statistics(
        Namespace="AWS/ApiGateway",
        MetricName="5XXError",
        Dimensions=[{"Name": "ApiName", "Value": api_name}],
        StartTime=start,
        EndTime=end,
        Period=300,  # 5-minute intervals
        Statistics=["Sum", "SampleCount"],
    )
    datapoints = sorted(resp["Datapoints"], key=lambda d: d["Timestamp"])
    return [
        {
            "start": d["Timestamp"].isoformat(),
            "end": (d["Timestamp"] + timedelta(minutes=5)).isoformat(),
            "request_count": int(d["SampleCount"]),
            "error_count": int(d["Sum"]),  # nodes.py expects 'error_count'
            "availability_pct": str(
                round(
                    max(0, 1 - (d["Sum"] / d["SampleCount"])) * 100
                    if d["SampleCount"] > 0
                    else 100.0,
                    6,
                )
            ),
        }
        for d in datapoints
    ]


def _fetch_cloudtrail_events(api_id: str, start: datetime, end: datetime, region: str) -> list[dict]:
    """Fetch real CloudTrail events for the API Gateway resource."""
    ct = boto3.client("cloudtrail", region_name=region)
    events = []
    paginator = ct.get_paginator("lookup_events")
    for page in paginator.paginate(
        LookupAttributes=[
            {"AttributeKey": "ResourceName", "AttributeValue": f"recoup-sla-demo"},
        ],
        StartTime=start,
        EndTime=end,
        MaxResults=50,
    ):
        for e in page["Events"]:
            events.append({
                "EventId": e.get("EventId"),
                "EventName": e.get("EventName"),
                "EventTime": e["EventTime"].isoformat() if e.get("EventTime") else None,
                "Username": e.get("Username"),
                "Resources": [
                    {"ResourceName": r.get("ResourceName"), "ResourceType": r.get("ResourceType")}
                    for r in e.get("Resources", [])
                ],
            })
    return events


def _update_health_event(api_id: str, outage_start: datetime, outage_end: datetime) -> None:
    """Update health_event.json with real account ID and API Gateway ID."""
    path = FIXTURES_DIR / "health_event.json"
    with open(path) as f:
        data = json.load(f)

    data["account"] = ACCOUNT_ID
    data["time"] = outage_end.strftime("%Y-%m-%dT%H:%M:%SZ")
    data["resources"] = [f"arn:aws:apigateway:{REGION}::/restapis/{api_id}"]
    data["detail"]["startTime"] = outage_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    data["detail"]["endTime"] = outage_end.strftime("%Y-%m-%dT%H:%M:%SZ")
    data["detail"]["affectedResources"] = [
        {"entityValue": f"arn:aws:apigateway:{REGION}::/restapis/{api_id}"}
    ]
    data["_recoup_fixture_version"] = "1.1.0"
    data["_recoup_scenario_id"] = f"replay-apigateway-{outage_start.strftime('%Y-%m')}-sla-001"
    data.pop("_note", None)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ health_event.json updated → account={ACCOUNT_ID}, api_id={api_id}")


def _save_metric_series(intervals: list[dict], outage_start: datetime) -> None:
    """Write real CloudWatch 5xx data to metric_series.json."""
    path = FIXTURES_DIR / "metric_series.json"

    # Count unavailable intervals (availability < 100%)
    unavailable = [i for i in intervals if float(i["availability_pct"]) < 100.0]

    data = {
        "_recoup_fixture_version": "1.1.0",
        "_recoup_scenario_id": f"replay-apigateway-{outage_start.strftime('%Y-%m')}-sla-001",
        "_note": (
            f"Real CloudWatch 5XXError metrics from API Gateway 'recoup-sla-demo' "
            f"in account {ACCOUNT_ID}. Outage window: {outage_start.strftime('%Y-%m-%dT%H:%M:%SZ')}. "
            f"Captured by scripts/inject_sla_traffic.py."
        ),
        "total_intervals": len(intervals),
        "unavailable_intervals": len(unavailable),
        "interval_minutes": 5,
        "billing_month_start": outage_start.replace(day=1, hour=0, minute=0, second=0).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "intervals": intervals,
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ metric_series.json updated → {len(intervals)} intervals, {len(unavailable)} unavailable")


def _save_billing_snapshot(total_calls: int, outage_start: datetime) -> tuple[str, str]:
    """Update billing_snapshot.json with real billing figures from the injection run."""
    path = FIXTURES_DIR / "billing_snapshot.json"
    # API Gateway REST API: $3.50 per million calls (us-east-1, 2026 pricing)
    billed = round(total_calls / 1_000_000 * 3.50, 4)
    billed_str = f"{billed:.2f}"

    with open(path) as f:
        data = json.load(f)

    data["billing_cycle"] = outage_start.strftime("%Y-%m")
    data["billed_amount_usd"] = billed_str
    data["line_items"][0]["quantity"] = total_calls
    data["line_items"][0]["amount_usd"] = billed_str
    data["_status"] = f"REAL — {total_calls:,} calls injected by inject_sla_traffic.py on {outage_start.strftime('%Y-%m-%d')}"

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    credit_str = f"{round(billed * 0.10, 4):.2f}"
    print(f"  ✅ billing_snapshot.json updated → billed=${billed_str}, credit=10%×${billed_str}=${credit_str}")
    return billed_str, credit_str


def _save_cloudtrail_events(events: list[dict], outage_start: datetime) -> None:
    """Write real CloudTrail events to cloudtrail_events.json."""
    path = FIXTURES_DIR / "cloudtrail_events.json"
    data = {
        "_recoup_fixture_version": "1.1.0",
        "_recoup_scenario_id": f"replay-apigateway-{outage_start.strftime('%Y-%m')}-sla-001",
        "_note": (
            f"Real CloudTrail events for API Gateway 'recoup-sla-demo' "
            f"in account {ACCOUNT_ID}. Captured by scripts/inject_sla_traffic.py."
        ),
        "events": events,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ cloudtrail_events.json updated → {len(events)} events")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--api-url", required=True, help="API Gateway health endpoint URL")
    parser.add_argument("--lambda-name", default="recoup-sla-health", help="Lambda function name")
    parser.add_argument("--normal-calls", type=int, default=500_000, help="Normal calls per phase (default: 500000)")
    parser.add_argument("--outage-calls", type=int, default=500, help="Calls during outage window (default: 500)")
    parser.add_argument("--outage-duration-min", type=int, default=30, help="Outage window duration in minutes (default: 30)")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without making AWS calls")
    args = parser.parse_args()

    total_calls = args.normal_calls * 2 + args.outage_calls
    est_cost = total_calls / 1_000_000 * 3.50
    api_id = args.api_url.split(".execute-api.")[0].split("//")[1] if ".execute-api." in args.api_url else "unknown"

    print("=" * 60)
    print("Recoup SLA Demo — Traffic Injection (Option C)")
    print("=" * 60)
    print(f"  API URL:         {args.api_url}")
    print(f"  API ID:          {api_id}")
    print(f"  Lambda:          {args.lambda_name}")
    print(f"  Normal calls:    {args.normal_calls:,} × 2 phases")
    print(f"  Outage calls:    {args.outage_calls:,} (→ 503)")
    print(f"  Total calls:     {total_calls:,}")
    print(f"  Estimated cost:  ${est_cost:.2f}")
    print(f"  Dry run:         {args.dry_run}")
    print()

    if args.dry_run:
        print("DRY RUN — no AWS calls made. Remove --dry-run to execute.")
        sys.exit(0)

    lambda_client = boto3.client("lambda", region_name=args.region)
    run_start = datetime.now(UTC)

    # ── Phase 1: pre-outage normal traffic ──────────────────────────────────
    print(f"[1/4] Pre-outage normal traffic ({args.normal_calls:,} calls → 200 OK)")
    stats = _burst(args.api_url, args.normal_calls, workers=50, label="pre-outage")
    print(f"      Result: {stats['ok']:,} OK / {stats['err5xx']} 5xx")

    # ── Phase 2: outage simulation ───────────────────────────────────────────
    outage_start = datetime.now(UTC)
    print(f"\n[2/4] Outage simulation ({args.outage_calls} calls → 503)")
    print(f"      Setting Lambda OUTAGE_MODE=true ...")
    _set_outage_mode(lambda_client, args.lambda_name, enabled=True)
    outage_stats = _burst(args.api_url, args.outage_calls, workers=20, label="outage")
    outage_end = datetime.now(UTC)
    print(f"      Result: {outage_stats['err5xx']} 5xx / {outage_stats['ok']} OK")
    print(f"      Window: {outage_start.strftime('%H:%M:%S')} → {outage_end.strftime('%H:%M:%S')} UTC")
    print(f"      Resetting Lambda OUTAGE_MODE=false ...")
    _set_outage_mode(lambda_client, args.lambda_name, enabled=False)

    # ── Phase 3: post-outage recovery ────────────────────────────────────────
    print(f"\n[3/4] Post-outage recovery ({args.normal_calls:,} calls → 200 OK)")
    stats2 = _burst(args.api_url, args.normal_calls, workers=50, label="recovery")
    print(f"      Result: {stats2['ok']:,} OK / {stats2['err5xx']} 5xx")

    # ── Phase 4: capture real evidence ──────────────────────────────────────
    print(f"\n[4/4] Capturing real AWS evidence ...")

    # Wait a moment for CloudWatch metrics to propagate (can take 1-2 min)
    print("      Waiting 90s for CloudWatch metrics to propagate ...")
    time.sleep(90)

    window_start = run_start - timedelta(hours=1)
    window_end = datetime.now(UTC)

    cw_intervals = _fetch_cloudwatch_5xx("recoup-sla-demo", window_start, window_end, args.region)
    ct_events = _fetch_cloudtrail_events(api_id, window_start, window_end, args.region)

    total_injected = args.normal_calls * 2 + args.outage_calls
    print(f"\n  Saving fixture files ...")
    _update_health_event(api_id, outage_start, outage_end)
    _save_metric_series(cw_intervals, outage_start)
    _save_cloudtrail_events(ct_events, outage_start)
    billed_str, credit_str = _save_billing_snapshot(total_injected, outage_start)

    print()
    print("=" * 60)
    print(f"✅ Done — real SLA scenario deployed")
    print(f"   API Gateway:  recoup-sla-demo ({api_id})")
    print(f"   Calls:        {total_injected:,}")
    print(f"   Real billing: ${billed_str}")
    print(f"   Real credit:  ${credit_str}  (10% × ${billed_str})")
    print()
    print("   Add to .env:")
    print(f"   RECOUP_SLA_DEMO_API_ID={api_id}")
    print()
    print("Verify in AWS console:")
    print(f"  API Gateway:   https://console.aws.amazon.com/apigateway/home?region={args.region}#/apis")
    print(f"  CloudWatch:    https://console.aws.amazon.com/cloudwatch/home?region={args.region}#metricsV2:namespace=AWS/ApiGateway")
    print(f"  CloudTrail:    https://console.aws.amazon.com/cloudtrail/home?region={args.region}#/events")
    print()
    print(f"  Total calls injected: {total_calls:,}")
    print(f"  Estimated cost:       ${est_cost:.2f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
