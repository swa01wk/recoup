"""LLM investigator interface + deterministic fallback."""

from __future__ import annotations

import uuid
from typing import Any

from ..models.recovery import EvidenceBundle, Insight, OperationalSignal, ResourceContext
from ..scanners.finding import Finding


def deterministic_investigator(
    finding: Finding,
    ctx: ResourceContext,
    bundle: EvidenceBundle,
    signals: list[OperationalSignal],
) -> dict[str, Any]:
    """Rule-based insights and investigation plan (no LLM)."""
    insights: list[Insight] = []
    claim = bundle.claim or finding.issue

    if bundle.counter_signal_ids:
        text = (
            "Independent signals conflict: utilization suggests waste but "
            "periodic activity indicates the resource may still be in use."
        )
        summary = (
            "Conflicting utilization and activity signals require conservative remediation."
        )
        insights.append(
            Insight(
                insight_id=f"ins-{uuid.uuid4().hex[:8]}",
                text=text,
                title="Conflicting signals",
                summary=summary,
                signal_ids=bundle.counter_signal_ids + bundle.supporting_signal_ids[:2],
                contradicting_signal_ids=list(bundle.counter_signal_ids),
            )
        )
    else:
        text = (
            f"The {ctx.identity.service} resource shows aligned utilization and "
            f"activity signals supporting: {claim[:120]}"
        )
        summary = (
            "No meaningful compute or operational activity was detected while the "
            "resource continued to incur recurring cost."
        )
        insights.append(
            Insight(
                insight_id=f"ins-{uuid.uuid4().hex[:8]}",
                text=text,
                title="Sustained inactivity",
                summary=summary,
                signal_ids=bundle.supporting_signal_ids[:5],
                contradicting_signal_ids=list(bundle.counter_signal_ids),
            )
        )

    missing = list(bundle.missing_expected)
    investigation_plan = [f"Collect: {m}" for m in missing] if missing else []

    return {
        "insights": insights,
        "investigation_plan": investigation_plan,
        "hypothesis_summary": insights[0].text if insights else finding.issue,
    }


def merge_llm_investigator_result(
    base: dict[str, Any],
    llm: dict[str, Any] | None,
) -> dict[str, Any]:
    if not llm:
        return base
    out = dict(base)
    if llm.get("insights"):
        out["insights"] = [Insight.model_validate(i) for i in llm["insights"]]
    if llm.get("hypothesis_summary"):
        out["hypothesis_summary"] = llm["hypothesis_summary"]
    if llm.get("investigation_plan"):
        out["investigation_plan"] = llm["investigation_plan"]
    return out
