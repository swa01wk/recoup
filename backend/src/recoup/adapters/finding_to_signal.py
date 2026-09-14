"""
FindingToSignalAdapter — Sprint 3.

Maps a scanner Finding to an IncidentSignal that can be passed to
recoup_graph.run(). This adapter bridges the scan pipeline to the AI graph
so that promoted findings are analysed by Bedrock/Strands rather than
receiving a hardcoded verdict.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ..models.signal import IncidentSignal
from ..scanners.finding import Finding


class FindingToSignalAdapter:
    """
    Convert a :class:`Finding` into an :class:`IncidentSignal` suitable for
    passing to ``recoup_graph.run()``.

    The mapping is:
    - source: "optimization" (scanner-originated, not a health event)
    - event_id: "scan-{resource_id}"
    - service / region: from the finding
    - start/end: scan time (both set to now — a point-in-time snapshot)
    - affected_resource_ids: [resource_id]
    - raw_ref: "scan:finding:{resource_id}"
    - replay: False (live finding, not an eval replay)

    Confidence is mapped from severity:
      high   → 0.90
      medium → 0.75
      low    → 0.65
    """

    CONFIDENCE_MAP: dict[str, float] = {
        "high": 0.90,
        "medium": 0.75,
        "low": 0.65,
    }

    def adapt(self, finding: Finding) -> IncidentSignal:
        """Return an IncidentSignal built from *finding*."""
        now = datetime.now(UTC)
        return IncidentSignal(
            source="optimization",
            event_id=f"scan-{finding.resource_id}",
            service=finding.service,
            region=finding.region,
            start=now,
            end=now,
            affected_resource_ids=[finding.resource_id],
            raw_ref=f"scan:finding:{finding.resource_id}",
            replay=False,
        )

    def confidence(self, finding: Finding) -> float:
        """Return the confidence score for *finding*'s severity."""
        return self.CONFIDENCE_MAP.get(finding.severity, 0.65)

    def estimated_credit(self, finding: Finding) -> Decimal:
        """Return the estimated monthly credit as a Decimal."""
        return Decimal(str(finding.estimated_monthly_savings_usd)).quantize(Decimal("0.01"))
