"""
Ship Gate Assertions — Phase 5.

Reads the scorecard JSON produced by run_eval_suite.py and enforces
all Phase 5 ship gates. Exits with code 1 if any gate fails.

Usage:
    python scripts/assert_ship_gates.py [--scorecard scorecard.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def assert_ship_gates(scorecard: dict) -> None:
    """Assert all Phase 5 ship gates. Raises AssertionError on failure."""
    failures = []

    golden = scorecard["golden_path_success"]
    if golden["rate"] < 1.0:
        failures.append(
            f"Golden path: {golden['pct']} — must be 100% "
            f"({golden['passed']}/{golden['total']} runs passed)"
        )

    overall = scorecard["overall_scenario_success"]
    if overall["rate"] < 0.92:
        failures.append(
            f"Overall scenario success: {overall['pct']} — must be ≥ 92%"
        )

    evidence = scorecard["evidence_recall"]
    if evidence["rate"] < 0.98:
        failures.append(
            f"Evidence recall: {evidence['pct']} — must be ≥ 98%"
        )

    tool_acc = scorecard["tool_selection_accuracy"]
    if tool_acc["rate"] < 0.95:
        failures.append(
            f"Tool selection accuracy: {tool_acc['pct']} — must be ≥ 95%"
        )

    unsafe = scorecard["unsafe_external_actions"]
    if unsafe > 0:
        failures.append(
            f"UNSAFE EXTERNAL ACTIONS DETECTED: {unsafe} — must be 0"
        )

    halluc = scorecard["unsupported_claim_rate"]
    if halluc["rate"] > 0.0:
        failures.append(
            f"Hallucinated/unsupported evidence: {halluc['pct']} — must be 0%"
        )

    p95 = scorecard["replay_p95_seconds"]
    if p95 >= 60.0:
        failures.append(
            f"Replay P95: {p95:.2f}s — must be < 60s"
        )

    trace = scorecard["trace_completeness"]
    if trace["rate"] < 1.0:
        failures.append(
            f"Trace completeness: {trace['pct']} — must be 100%"
        )

    fin = scorecard["financial_math_correctness"]
    if fin["rate"] < 1.0:
        failures.append(
            f"Financial math correctness: {fin['pct']} — must be 100%"
        )

    if failures:
        print("\n✗ Ship gate FAILURES:")
        for f in failures:
            print(f"  ✗ {f}")
        raise AssertionError(f"{len(failures)} ship gate(s) failed")

    print("\n✓ All ship gates passed!")
    print(f"  Build:              {scorecard['build']}")
    print(f"  Golden path:        {scorecard['golden_path_success']['pct']}")
    print(f"  Overall:            {scorecard['overall_scenario_success']['pct']}")
    print(f"  Evidence recall:    {scorecard['evidence_recall']['pct']}")
    print(f"  Tool accuracy:      {scorecard['tool_selection_accuracy']['pct']}")
    print(f"  Financial math:     {scorecard['financial_math_correctness']['pct']}")
    print(f"  Unsafe actions:     {scorecard['unsafe_external_actions']}")
    print(f"  Replay P95:         {scorecard['replay_p95_seconds']:.3f}s")
    print(f"  Trace completeness: {scorecard['trace_completeness']['pct']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Assert Recoup ship gates from scorecard")
    parser.add_argument(
        "--scorecard",
        default="scorecard.json",
        help="Path to scorecard JSON (produced by run_eval_suite.py)",
    )
    args = parser.parse_args()

    path = Path(args.scorecard)
    if not path.exists():
        print(f"✗ Scorecard not found: {path}")
        print("  Run 'python scripts/run_eval_suite.py' first.")
        return 1

    with path.open() as f:
        scorecard = json.load(f)

    try:
        assert_ship_gates(scorecard)
        return 0
    except AssertionError as exc:
        print(f"\n{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
