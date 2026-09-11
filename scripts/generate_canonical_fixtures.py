#!/usr/bin/env python3
"""
Generate canonical metric_series.json fixture for the Recoup replay engine.

Produces metric_series.json under eval_fixtures/sla/api_gateway/canonical/.
All other fixture files are committed manually (health_event.json,
billing_snapshot.json, cloudtrail_events.json, sla_contract_ref.yaml,
expected_output.json). billing_snapshot.json is overwritten by
inject_sla_traffic.py with real AWS billing data.

Run once to create / overwrite the metric series:
    python scripts/generate_canonical_fixtures.py

The generated file is treated as immutable after the first CI run.
A SHA-256 hash is printed so changes can be detected.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CANONICAL_DIR = REPO_ROOT / "eval_fixtures" / "sla" / "api_gateway" / "canonical"

# Canonical parameters — must match the golden test spec (Appendix C)
TOTAL_INTERVALS = 8_640          # 31-day billing month × 12 five-minute slots/hour
INCIDENT_START_IDX = 24          # 2026-09-01 02:00 UTC = minute 120 = slot 24
INCIDENT_END_IDX = 29            # 2026-09-01 02:25 UTC = slot 29 (inclusive)
BILLING_MONTH_START = datetime(2026, 9, 1, tzinfo=timezone.utc)
INTERVAL_MINUTES = 5

# Expected metric series invariants (credit depends on billing snapshot)
EXPECTED_UPTIME_PCT = "99.930556"
EXPECTED_UNAVAILABLE = 6


def generate_metric_series() -> list[dict]:
    """
    Generate 8,640 five-minute CloudWatch-style availability intervals for the
    canonical September 2026 API Gateway SLA scenario.

    6 intervals (indices 24–29, covering 02:00–02:30 UTC on Sep 1) are at 0%
    availability. All others are at 100%.
    """
    intervals = []
    for i in range(TOTAL_INTERVALS):
        ts = BILLING_MONTH_START + timedelta(minutes=INTERVAL_MINUTES * i)
        ts_end = ts + timedelta(minutes=INTERVAL_MINUTES)
        is_incident = INCIDENT_START_IDX <= i <= INCIDENT_END_IDX

        intervals.append({
            "start": ts.isoformat().replace("+00:00", "Z"),
            "end": ts_end.isoformat().replace("+00:00", "Z"),
            "availability_pct": "0.0" if is_incident else "100.0",
            "request_count": 0 if is_incident else 1000,
            "error_count": 1000 if is_incident else 0,
            "_slot_index": i,
        })

    return intervals


def validate_series(intervals: list[dict]) -> None:
    """Assert the golden invariants hold before writing."""
    assert len(intervals) == TOTAL_INTERVALS, (
        f"Expected {TOTAL_INTERVALS} intervals, got {len(intervals)}"
    )
    bad = [iv for iv in intervals if iv["availability_pct"] == "0.0"]
    assert len(bad) == EXPECTED_UNAVAILABLE, (
        f"Expected {EXPECTED_UNAVAILABLE} unavailable intervals, got {len(bad)}"
    )
    # Verify the incident window
    incident = [iv for iv in intervals if INCIDENT_START_IDX <= iv["_slot_index"] <= INCIDENT_END_IDX]
    assert all(iv["availability_pct"] == "0.0" for iv in incident), (
        "All incident-window intervals must be 0% available"
    )
    # Quick uptime check (floating point is fine here — only for validation)
    good = TOTAL_INTERVALS - EXPECTED_UNAVAILABLE
    uptime = round(good / TOTAL_INTERVALS * 100, 6)
    assert abs(uptime - 99.930556) < 0.000001, f"Unexpected uptime: {uptime}"


def strip_slot_index(intervals: list[dict]) -> list[dict]:
    """Remove internal _slot_index key before writing to disk."""
    return [{k: v for k, v in iv.items() if k != "_slot_index"} for iv in intervals]


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> None:
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CANONICAL_DIR / "metric_series.json"

    print("Generating canonical metric series …")
    intervals = generate_metric_series()
    validate_series(intervals)
    clean = strip_slot_index(intervals)

    payload = {
        "_recoup_fixture_version": "1.0.0",
        "_recoup_scenario_id": "replay-apigateway-2026-09-sla-001",
        "_note": (
            f"{TOTAL_INTERVALS} five-minute CloudWatch availability intervals for "
            f"API Gateway in us-east-1, September 2026. "
            f"Slots {INCIDENT_START_IDX}–{INCIDENT_END_IDX} "
            f"(02:00–02:30 UTC Sep 1) are at 0% availability."
        ),
        "total_intervals": TOTAL_INTERVALS,
        "unavailable_intervals": EXPECTED_UNAVAILABLE,
        "interval_minutes": INTERVAL_MINUTES,
        "billing_month_start": BILLING_MONTH_START.isoformat().replace("+00:00", "Z"),
        "intervals": clean,
    }

    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    digest = sha256_of_file(out_path)
    size_kb = out_path.stat().st_size / 1024

    print(f"  Written: {out_path}")
    print(f"  Size:    {size_kb:.1f} KB")
    print(f"  SHA-256: {digest}")
    print(f"  Intervals: {TOTAL_INTERVALS} total, {EXPECTED_UNAVAILABLE} unavailable")
    print(f"  Uptime:  99.930556%  →  10% tier  →  credit from billing_snapshot.json")
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
