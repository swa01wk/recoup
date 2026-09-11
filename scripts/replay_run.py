#!/usr/bin/env python3
"""
Headless replay execution script — Verified Replay for the canonical SLA scenario.

Runs the full Recoup recovery graph against the canonical API Gateway SLA fixture
and prints a structured result to stdout.  Useful for:
  - CI smoke tests (exit code 0 only if credit > 0 and all runs identical)
  - Local demo without running the FastAPI server
  - Timing P95 measurement (--runs N for multiple runs)

Usage:
    # Single run (default)
    python scripts/replay_run.py

    # N consecutive runs (timing + consistency check)
    python scripts/replay_run.py --runs 20

    # JSON output only
    python scripts/replay_run.py --json

    # Custom opportunity ID
    python scripts/replay_run.py --opportunity-id my-opp-001
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from decimal import Decimal
from pathlib import Path

# Make sure the backend package is importable from repo root
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from recoup.adapters.replay import CANONICAL_SCENARIO, ReplayAdapter  # noqa: E402
from recoup.graph.recoup_graph import recoup_graph  # noqa: E402
from recoup.graph.types import PolicyDecision  # noqa: E402

EXPECTED_UPTIME = Decimal("99.930556")
EXPECTED_TIER = Decimal("10")


def run_once(opportunity_id: str | None = None) -> tuple[dict, float]:
    """Execute one replay and return (result_dict, elapsed_seconds)."""
    adapter = ReplayAdapter()
    state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id=opportunity_id)

    t0 = time.monotonic()
    final = recoup_graph.run(state)
    elapsed = time.monotonic() - t0

    result = final.availability_result
    return {
        "opportunity_id": final.opportunity_id,
        "scenario_id": CANONICAL_SCENARIO.scenario_id,
        "simulation_mode": final.simulation_mode,
        "monthly_uptime_pct": str(result.monthly_uptime_pct) if result else None,
        "threshold_breached": result.threshold_breached if result else None,
        "tier_pct": str(result.tier_pct) if result else None,
        "billed_charges": str(result.billed_charges) if result else None,
        "potential_credit": str(result.potential_credit) if result else None,
        "policy_decision": final.policy_decision.value if final.policy_decision else None,
        "case_id": final.case_id,
        "errors": final.errors,
        "elapsed_s": round(elapsed, 3),
    }, elapsed


def validate_result(result: dict, expected_credit: Decimal | None = None) -> list[str]:
    """Return a list of failure messages (empty = pass)."""
    failures = []

    credit = Decimal(result["potential_credit"] or "0")
    if credit <= Decimal("0"):
        failures.append(f"Credit must be positive, got {credit}")
    if expected_credit is not None and credit != expected_credit:
        failures.append(f"Credit inconsistency: expected {expected_credit}, got {credit}")

    uptime = Decimal(result["monthly_uptime_pct"] or "0")
    if uptime != EXPECTED_UPTIME:
        failures.append(f"Uptime mismatch: expected {EXPECTED_UPTIME}, got {uptime}")

    tier = Decimal(result["tier_pct"] or "0")
    if tier != EXPECTED_TIER:
        failures.append(f"Tier mismatch: expected {EXPECTED_TIER}%, got {tier}%")

    if result["policy_decision"] != PolicyDecision.REQUIRE_APPROVAL.value:
        failures.append(
            f"Policy decision: expected REQUIRE_APPROVAL, got {result['policy_decision']}"
        )

    if not result["simulation_mode"]:
        failures.append("simulation_mode must be True for replay runs")

    if result["errors"]:
        failures.append(f"Graph errors: {result['errors']}")

    return failures


def print_result(result: dict, run_idx: int | None = None) -> None:
    prefix = f"[Run {run_idx}] " if run_idx is not None else ""
    credit = result.get("potential_credit", "?")
    uptime = result.get("monthly_uptime_pct", "?")
    tier = result.get("tier_pct", "?")
    elapsed = result.get("elapsed_s", "?")
    decision = result.get("policy_decision", "?")

    print(f"{prefix}✓ Credit: ${credit}  Uptime: {uptime}%  Tier: {tier}%  "
          f"Decision: {decision}  Time: {elapsed}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recoup Verified Replay")
    parser.add_argument("--runs", type=int, default=1,
                        help="Number of consecutive replay runs (default: 1)")
    parser.add_argument("--json", action="store_true",
                        help="Print JSON output only (no human-readable lines)")
    parser.add_argument("--opportunity-id", default=None,
                        help="Override the opportunity ID")
    args = parser.parse_args()

    if not args.json:
        print(f"Recoup Verified Replay — {CANONICAL_SCENARIO.name}")
        print(f"Scenario: {CANONICAL_SCENARIO.scenario_id}")
        print(f"Expected: credit > 0, uptime {EXPECTED_UPTIME}%, tier {EXPECTED_TIER}%")
        print("-" * 70)

    results = []
    elapsed_times = []
    all_failures: list[str] = []

    for i in range(args.runs):
        opp_id = args.opportunity_id or f"replay-headless-{i + 1:04d}"
        result, elapsed = run_once(opportunity_id=opp_id)
        results.append(result)
        elapsed_times.append(elapsed)

        # For consistency check: first run sets the reference credit
        expected_credit = (
            Decimal(results[0]["potential_credit"] or "0") if i > 0 else None
        )
        failures = validate_result(result, expected_credit=expected_credit)
        if failures:
            all_failures.extend([f"Run {i + 1}: {f}" for f in failures])

        if not args.json:
            print_result(result, run_idx=(i + 1) if args.runs > 1 else None)

    if args.json:
        output = results[0] if args.runs == 1 else {"runs": results}
        print(json.dumps(output, indent=2))
    else:
        print("-" * 70)
        if args.runs > 1:
            p50 = statistics.median(elapsed_times)
            p95 = sorted(elapsed_times)[int(len(elapsed_times) * 0.95)]
            print(f"Timing over {args.runs} runs:  P50 = {p50:.3f}s  P95 = {p95:.3f}s")
            credits = set(r["potential_credit"] for r in results)
            consistent = len(credits) == 1
            credit_val = next(iter(credits)) if consistent else "INCONSISTENT"
            print(f"Consistency: {'✓ All ' + str(args.runs) + ' runs produced $' + str(credit_val) if consistent else '✗ INCONSISTENT: ' + str(credits)}")

        if all_failures:
            print(f"\n✗ FAILED ({len(all_failures)} assertion(s)):")
            for f in all_failures:
                print(f"  • {f}")
            sys.exit(1)
        else:
            n = args.runs
            credit = results[0]["potential_credit"] if results else "?"
            print(f"\n✓ All {n} run{'s' if n != 1 else ''} passed — ${credit} deterministic")


if __name__ == "__main__":
    main()
