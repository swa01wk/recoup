"""Derive factual operational signals from scanner findings."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from ..models.recovery import OperationalSignal
from ..scanners.finding import Finding


def _sid(prefix: str, raw: str) -> str:
    h = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"{prefix}-{h}"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def signals_from_finding(finding: Finding) -> list[OperationalSignal]:
    """Map Finding + evidence dict to OperationalSignal list (deterministic)."""
    signals: list[OperationalSignal] = []
    rid = finding.resource_id
    rtype = finding.resource_type
    ev = finding.evidence or {}
    base_ref = f"scan:finding:{rid}"

    def add(
        signal_type: str,
        metric_or_event: str,
        value: str,
        unit: str = "",
        window: str = "",
        description: str = "",
        source: str = "scanner",
    ) -> None:
        raw = f"{rid}|{signal_type}|{metric_or_event}|{value}"
        signals.append(
            OperationalSignal(
                signal_id=_sid("sig", raw),
                resource_id=rid,
                resource_type=rtype,
                source=source,
                signal_type=signal_type,
                metric_or_event=metric_or_event,
                value=value,
                unit=unit,
                observation_window=window,
                observed_at=_now_iso(),
                raw_reference=base_ref,
                description=description or f"{metric_or_event} = {value}",
            )
        )

    add("finding", "issue", finding.issue, description=finding.issue)
    add("finding", "finding_type", finding.finding_type or "UNKNOWN")
    add("cost", "estimated_monthly_savings_usd", f"{finding.estimated_monthly_savings_usd:.2f}", unit="USD")

    if finding.severity:
        add("metadata", "severity", finding.severity)

    for key, val in ev.items():
        if val is None or val == "":
            continue
        stype = "utilization" if "cpu" in key.lower() or "util" in key.lower() else "metadata"
        if key == "cpu_utilization_7d_avg":
            stype = "utilization"
            window = "7d"
        add(stype, key, str(val), window=window if "window" in locals() else "")

    if finding.scenario_tag:
        add("metadata", "scenario_tag", finding.scenario_tag)
    if finding.is_demo_resource:
        add("metadata", "RecoupDemo", "true")

    # Demo counter-evidence: nightly workload scenario tag
    if finding.scenario_tag and "nightly" in finding.scenario_tag.lower():
        add(
            "activity",
            "periodic_workload",
            "detected",
            description="Nightly batch workload pattern indicated by scenario metadata",
            source="scenario",
        )

    return signals


def merge_signals(
    existing: list[OperationalSignal], new: list[OperationalSignal]
) -> list[OperationalSignal]:
    by_id = {s.signal_id: s for s in existing}
    for s in new:
        by_id[s.signal_id] = s
    return list(by_id.values())


def investigation_probe_signals(resource_id: str, probes: list[str]) -> list[OperationalSignal]:
    """Synthetic signals from investigate-further read-only probes (deterministic stub)."""
    out: list[OperationalSignal] = []
    for probe in probes:
        out.append(
            OperationalSignal(
                signal_id=f"probe-{uuid.uuid4().hex[:8]}",
                resource_id=resource_id,
                source="investigation",
                signal_type="probe",
                metric_or_event=probe,
                value="collected",
                observed_at=_now_iso(),
                raw_reference=f"investigation:{probe}",
                description=f"Additional probe completed: {probe}",
            )
        )
    return out
