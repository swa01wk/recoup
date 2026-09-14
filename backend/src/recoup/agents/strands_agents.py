"""
Strands agent implementations for Recoup reasoning nodes.

Each public function returns a dict of GraphState updates (same contract as
stub_fn) so AgentNode can swap between stub and Strands transparently.

Design rules:
- Every agent call is wrapped in try/except — LLM provider unavailability always
  falls back gracefully; the caller decides what to do with None.
- Agents receive evidence IDs only — raw evidence never enters LLM context.
- Financial math is NEVER delegated to the LLM — only narrative reasoning.
- `use_strands=False` in canonical replay so the 20/20 test stays deterministic.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# LLM model factory — extensible provider registry
# ---------------------------------------------------------------------------
# To add a new provider:
#   1. Write a _make_<name>() function below.
#   2. Register it in _MODEL_PROVIDERS.
#   3. Set LLM_PROVIDER=<name> in your .env.
# No other files need to change.
# ---------------------------------------------------------------------------


def _make_bedrock() -> Any:
    """Return a Strands BedrockModel using BEDROCK_MODEL_ID / BEDROCK_REGION."""
    from strands.models import BedrockModel  # noqa: PLC0415

    from ..config import settings  # noqa: PLC0415

    return BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.bedrock_region,
    )


def _make_openai() -> Any:
    """Return a Strands OpenAIModel using OPENAI_API_KEY / OPENAI_MODEL_ID."""
    from strands.models.openai import OpenAIModel  # noqa: PLC0415

    from ..config import settings  # noqa: PLC0415

    # Newer OpenAI models (o-series, gpt-5.x) use max_completion_tokens.
    # Classic models (gpt-4o, gpt-4-turbo) still accept max_tokens.
    # We pass max_completion_tokens which is accepted by both generations.
    return OpenAIModel(
        client_args={"api_key": settings.openai_api_key},
        model_id=settings.openai_model_id,
        params={"max_completion_tokens": 4096, "temperature": 0.3},
    )


# Registry — add future providers here, zero other code changes needed.
# Example future entries:
#   "litellm": _make_litellm,
#   "anthropic": _make_anthropic,
_MODEL_PROVIDERS: dict[str, Callable[[], Any]] = {
    "bedrock": _make_bedrock,
    "openai": _make_openai,
}


def _make_model() -> Any:
    """Dispatch to the configured LLM provider factory."""
    from ..config import settings  # noqa: PLC0415

    factory = _MODEL_PROVIDERS.get(settings.llm_provider)
    if factory is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{settings.llm_provider}'. "
            f"Valid options: {list(_MODEL_PROVIDERS)}"
        )
    log.debug("llm_provider.selected", provider=settings.llm_provider)
    return factory()


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract the last JSON block from an agent response string."""
    matches = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if matches:
        try:
            return cast(dict[str, Any], json.loads(matches[-1]))
        except json.JSONDecodeError:
            pass
    # Try bare JSON object as fallback
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return cast(dict[str, Any], json.loads(match.group()))
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# 1.  EC2 Stop Decision Agent
# ---------------------------------------------------------------------------

_EC2_SYSTEM_PROMPT = """\
You are an AWS cost optimization agent for Recoup, an autonomous cloud spend \
recovery system.

Your task: analyze an EC2 instance to determine whether it is genuinely idle \
and safe to stop.

Steps:
1. Call get_cpu_utilization to get 7-day CPU stats.
2. Call get_cloudtrail_events to check for recent ownership changes.
3. Call get_instance_details to confirm instance type and state.
4. Reason step-by-step about whether the instance is idle.

Safety rules you MUST follow:
- NEVER recommend stopping if blocking_changes = true.
- NEVER recommend stopping if avg_cpu > 5%.
- Always state your confidence level.

End your response with EXACTLY this JSON block (no extra text after it):
```json
{
  "idle": <true|false>,
  "avg_cpu_pct": <number>,
  "max_cpu_pct": <number>,
  "recent_events": <integer>,
  "blocking_changes": <true|false>,
  "verdict": "<idle_safe_to_stop|active_do_not_stop|blocked_changes_present>",
  "reasoning": "<one or two sentences>",
  "agent_driven": true
}
```"""


def run_ec2_stop_decision_agent(
    instance_id: str,
    region: str = "us-east-1",
) -> dict[str, Any] | None:
    """
    Run a Strands agent to decide whether an EC2 instance should be stopped.

    Returns a structured dict matching the EC2DemoAdapter check format,
    or None if Strands / Bedrock is unavailable (caller uses simulation stub).
    """
    try:
        import boto3
        from strands import Agent, tool

        cw_client = boto3.client("cloudwatch", region_name=region)
        ct_client = boto3.client("cloudtrail", region_name=region)
        ec2_client = boto3.client("ec2", region_name=region)

        @tool
        def get_cpu_utilization(instance_id: str, days: int = 7) -> str:
            """
            Get average and maximum CPU utilization for an EC2 instance
            over the specified number of days.
            """
            end = datetime.now(UTC)
            start = end - timedelta(days=days)
            resp = cw_client.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start,
                EndTime=end,
                Period=3600,
                Statistics=["Average", "Maximum"],
            )
            points = resp.get("Datapoints", [])
            if not points:
                return json.dumps({"avg_cpu": 0.0, "max_cpu": 0.0, "datapoints": 0})
            avg = sum(p["Average"] for p in points) / len(points)
            mx = max(p["Maximum"] for p in points)
            return json.dumps({
                "avg_cpu": round(avg, 2),
                "max_cpu": round(mx, 2),
                "datapoints": len(points),
                "period_days": days,
            })

        @tool
        def get_cloudtrail_events(instance_id: str, hours: int = 24) -> str:
            """
            Get recent CloudTrail events for an EC2 instance.
            Returns event names and usernames to detect ownership changes.
            """
            now = datetime.now(UTC)
            resp = ct_client.lookup_events(
                LookupAttributes=[
                    {"AttributeKey": "ResourceName", "AttributeValue": instance_id}
                ],
                StartTime=now - timedelta(hours=hours),
                EndTime=now,
                MaxResults=20,
            )
            events = resp.get("Events", [])
            blocking = {"ModifyInstanceAttribute", "AssociateIamInstanceProfile"}
            summary = [
                {
                    "event": e.get("EventName"),
                    "user": e.get("Username", "Unknown"),
                    "time": e["EventTime"].isoformat()
                    if hasattr(e.get("EventTime"), "isoformat")
                    else str(e.get("EventTime", "")),
                }
                for e in events
            ]
            has_blocking = any(e.get("EventName") in blocking for e in events)
            return json.dumps({
                "total_events": len(events),
                "blocking_changes": has_blocking,
                "recent_events": summary[:5],
            })

        @tool
        def get_instance_details(instance_id: str) -> str:
            """
            Get EC2 instance type, state, and key tags for the given instance.
            """
            resp = ec2_client.describe_instances(InstanceIds=[instance_id])
            reservations = resp.get("Reservations", [])
            if not reservations:
                return json.dumps({"error": "Instance not found"})
            inst = reservations[0]["Instances"][0]
            tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
            return json.dumps({
                "instance_id": instance_id,
                "instance_type": inst.get("InstanceType"),
                "state": inst.get("State", {}).get("Name"),
                "launch_time": str(inst.get("LaunchTime", "")),
                "tags": tags,
            })

        model = _make_model()
        agent = Agent(
            model=model,
            tools=[get_cpu_utilization, get_cloudtrail_events, get_instance_details],
            system_prompt=_EC2_SYSTEM_PROMPT,
        )

        prompt = (
            f"Analyze EC2 instance {instance_id} in {region}. "
            "Use all three tools, then provide your verdict."
        )
        result = agent(prompt)
        parsed = _extract_json(str(result))

        if parsed is None:
            log.warning("ec2_stop_agent.parse_failed", instance_id=instance_id)
            return None

        log.info(
            "ec2_stop_agent.completed",
            instance_id=instance_id,
            verdict=parsed.get("verdict"),
        )
        return parsed

    except Exception as exc:  # noqa: BLE001
        log.warning("ec2_stop_agent.failed", instance_id=instance_id, error=str(exc))
        return None


# ---------------------------------------------------------------------------
# 2.  Incident Correlation Agent  (SLA graph node)
# ---------------------------------------------------------------------------

_INCIDENT_SYSTEM_PROMPT = """\
You are a cloud reliability engineer working for Recoup, analyzing an AWS incident.

Your task: correlate an incident signal with real CloudWatch availability data \
to form a working hypothesis about the SLA impact.

Steps:
1. Review the incident signal (service, region, time window).
2. Use get_cloudwatch_availability to fetch 5-minute availability intervals.
3. Count unavailable intervals (availability_pct = 0).
4. Summarize the impact clearly and factually.

IMPORTANT:
- Output ONLY factual observations. Never conclude financial eligibility.
- Do not invent data points not returned by the tools.

End your response with EXACTLY this JSON block:
```json
{
  "total_intervals": <integer>,
  "unavailable_intervals": <integer>,
  "monthly_uptime_pct": <number with 6 decimal places>,
  "confidence": <0.0-1.0>,
  "summary": "<one sentence factual summary>",
  "agent_driven": true
}
```"""


def run_incident_correlation_agent(
    state: Any,
) -> dict[str, Any] | None:
    """
    Run a Strands agent to correlate the incident signal with CloudWatch data.

    Returns dict of GraphState updates or None on failure.
    """
    from ..graph.types import IncidentHypothesis

    signal = state.signal
    if signal is None:
        return None

    try:
        import boto3
        from strands import Agent, tool

        cw_client = boto3.client("cloudwatch", region_name="us-east-1")

        @tool
        def get_cloudwatch_availability(
            namespace: str,
            metric_name: str,
            start_time: str,
            end_time: str,
            period_seconds: int = 300,
        ) -> str:
            """
            Fetch CloudWatch metric data and compute availability per interval.
            Returns a list of 5-minute intervals with availability_pct (0 or 100).
            """
            resp = cw_client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                StartTime=datetime.fromisoformat(start_time),
                EndTime=datetime.fromisoformat(end_time),
                Period=period_seconds,
                Statistics=["Sum", "SampleCount"],
            )
            points = sorted(resp.get("Datapoints", []), key=lambda p: p["Timestamp"])
            summary = [
                {
                    "start": p["Timestamp"].isoformat(),
                    "availability_pct": 0 if p.get("Sum", 0) > 0 else 100,
                    "error_count": int(p.get("Sum", 0)),
                }
                for p in points
            ]
            return json.dumps({"intervals": summary, "count": len(summary)})

        model = _make_model()
        agent = Agent(
            model=model,
            tools=[get_cloudwatch_availability],
            system_prompt=_INCIDENT_SYSTEM_PROMPT,
        )

        prompt = (
            f"Analyze the incident for {signal.service} in {signal.region}.\n"
            f"Incident window: {signal.start.isoformat()} to {signal.end.isoformat()}.\n"
            f"Affected resources: {', '.join(signal.affected_resource_ids)}.\n\n"
            "Use get_cloudwatch_availability to fetch real metric data, "
            "then provide your correlation hypothesis."
        )

        result = agent(prompt)
        parsed = _extract_json(str(result))

        if parsed is None:
            log.warning("incident_correlation_agent.parse_failed")
            return None

        # Build AvailabilityInterval list from the golden fixtures as fallback
        # (the agent summary gives us counts, but we need the full interval list
        # for the calculator — so we merge agent reasoning with fixture intervals)
        replay_intervals = _intervals_from_fixtures(state.replay_fixtures, signal)

        hypothesis = IncidentHypothesis(
            service=signal.service,
            region=signal.region,
            incident_date=signal.start.date(),
            affected_resource_ids=signal.affected_resource_ids,
            availability_intervals=replay_intervals,
            billed_charges=_billed_from_fixtures(state.replay_fixtures),
            confidence=float(parsed.get("confidence", 0.92)),
            summary=parsed.get("summary", "Agent-driven correlation complete."),
            replay=signal.replay,
        )
        log.info("incident_correlation_agent.completed", service=signal.service)
        return {"hypothesis": hypothesis}

    except Exception as exc:  # noqa: BLE001
        log.warning("incident_correlation_agent.failed", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# 3.  Eligibility Reasoner Agent  (SLA graph node)
# ---------------------------------------------------------------------------

_ELIGIBILITY_SYSTEM_PROMPT = """\
You are a cloud billing specialist assessing an AWS SLA credit claim for Recoup.

Your task: review the SLA contract terms, availability calculation, and \
evidence manifest to determine whether the claim is contractually eligible.

Rules:
- Reference evidence ONLY by the IDs provided. Never invent evidence IDs.
- Do not make financial conclusions — only assess contractual eligibility.
- Be precise about which SLA requirements are satisfied vs. outstanding.

End your response with EXACTLY this JSON block:
```json
{
  "eligible_estimate": <true|false>,
  "confidence": <0.0-1.0>,
  "satisfied_requirements": ["<requirement>"],
  "unresolved": ["<unresolved item>"],
  "possible_exclusions": [],
  "reasoning": "<one or two sentences>",
  "agent_driven": true
}
```"""


def run_eligibility_reasoner_agent(
    state: Any,
) -> dict[str, Any] | None:
    """
    Run a Strands agent to assess SLA claim eligibility.

    No tool calls — agent reasons over provided context only.
    Returns dict of GraphState updates or None on failure.
    """
    from ..models.eligibility import EligibilityAssessment

    result_data = state.availability_result
    manifest = state.sanitized_manifest
    contract = state.contract

    if not all([result_data, manifest, contract]):
        return None

    try:
        from strands import Agent

        model = _make_model()
        agent = Agent(
            model=model,
            tools=[],
            system_prompt=_ELIGIBILITY_SYSTEM_PROMPT,
        )

        evidence_ids = [item.id for item in manifest.items]
        prompt = f"""Assess SLA credit claim eligibility:

CONTRACT
  Service: {contract.service} v{contract.version}
  SLA commitment: {contract.service_commitment}% monthly uptime
  Required evidence fields: {', '.join(contract.required_claim_fields)}

AVAILABILITY RESULT
  Measured uptime: {result_data.monthly_uptime_pct}%
  SLA threshold breached: {result_data.threshold_breached}
  Credit tier: {result_data.tier_pct}%
  Potential credit: ${result_data.potential_credit}

EVIDENCE MANIFEST
  Collected IDs: {', '.join(evidence_ids) if evidence_ids else 'none'}
  Missing fields: {', '.join(manifest.missing_fields) if manifest.missing_fields else 'none'}

Is this claim eligible for an SLA credit?"""

        result = agent(prompt)
        parsed = _extract_json(str(result))

        if parsed is None:
            log.warning("eligibility_reasoner_agent.parse_failed")
            return None

        assessment = EligibilityAssessment(
            eligible_estimate=bool(parsed.get("eligible_estimate", False)),
            confidence=float(parsed.get("confidence", 0.5)),
            satisfied_requirements=parsed.get("satisfied_requirements", []),
            unresolved=parsed.get("unresolved", []),
            possible_exclusions=parsed.get("possible_exclusions", []),
            evidence_refs=evidence_ids,
        )
        log.info(
            "eligibility_reasoner_agent.completed",
            eligible=assessment.eligible_estimate,
            confidence=assessment.confidence,
        )
        return {"eligibility_assessment": assessment}

    except Exception as exc:  # noqa: BLE001
        log.warning("eligibility_reasoner_agent.failed", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# 4.  Claim Package Generator Agent  (SLA graph node)
# ---------------------------------------------------------------------------

_CLAIM_SYSTEM_PROMPT = """\
You are a professional AWS SLA credit claim writer for Recoup.

Your task: draft a concise, factual AWS Support claim letter using ONLY the \
evidence IDs provided. Do NOT invent new evidence IDs.

The claim must:
- Be professional and factual
- Reference billed charges and credit amount accurately
- Include the evidence IDs as supporting references
- Be under 300 words

Return ONLY the claim body text (no JSON needed)."""


def run_claim_package_generator_agent(
    state: Any,
) -> dict[str, Any] | None:
    """
    Run a Strands agent to draft the SLA credit claim letter.

    Returns dict of GraphState updates or None on failure (caller uses stub).
    """
    from ..graph.nodes import claim_package_generator_stub

    result_data = state.availability_result
    manifest = state.sanitized_manifest
    contract = state.contract
    hypothesis = state.hypothesis

    if not all([result_data, manifest, contract, hypothesis]):
        return None

    try:
        from strands import Agent

        model = _make_model()
        agent = Agent(
            model=model,
            tools=[],
            system_prompt=_CLAIM_SYSTEM_PROMPT,
        )

        ev_ids = " ".join(item.id for item in manifest.items)
        billing_cycle = hypothesis.incident_date.strftime("%Y-%m")

        prompt = (
            f"Draft an AWS SLA credit claim for {contract.service} in {hypothesis.region}.\n"
            f"Billing cycle: {billing_cycle}\n"
            f"Measured uptime: {result_data.monthly_uptime_pct}% "
            f"(SLA commitment: {contract.service_commitment}%)\n"
            f"Credit tier: {result_data.tier_pct}% of ${result_data.billed_charges}\n"
            f"Potential credit: ${result_data.potential_credit}\n"
            f"Evidence IDs: {ev_ids}"
        )

        result = agent(prompt)
        claim_body = str(result).strip()

        # Use the stub to build the full ClaimPackage structure, then override
        # the body with the agent-generated text
        stub_result = claim_package_generator_stub(state)
        if "claim_package" in stub_result and stub_result["claim_package"] is not None:
            pkg = stub_result["claim_package"]
            stub_result["claim_package"] = pkg.model_copy(
                update={"body": claim_body, "_agent_driven": True}
            )
        log.info("claim_package_generator_agent.completed")
        return stub_result

    except Exception as exc:  # noqa: BLE001
        log.warning("claim_package_generator_agent.failed", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Recovery pipeline agents (optimization findings)
# ---------------------------------------------------------------------------


def run_recovery_investigator_agent(
    state: Any,
    finding: Any,
    ctx: Any,
    bundle: Any,
) -> dict[str, Any] | None:
    """
    Strands investigator for cost recovery — insights only, no scores or dollars.
    Returns None on failure so deterministic fallback is used.
    """
    try:
        from strands import Agent  # noqa: PLC0415

        from ..models.recovery import Insight  # noqa: PLC0415

        prompt = (
            "You are a cloud cost recovery investigator. Given resource context and "
            "evidence bundle summaries, output JSON with keys: hypothesis_summary (string), "
            "insights (list of {insight_id, text, signal_ids}), "
            "investigation_plan (list of strings). "
            "Do NOT invent metrics, costs, confidence, or risk scores."
        )
        agent = Agent(model=_make_model(), system_prompt=prompt)
        payload = {
            "issue": finding.issue,
            "claim": bundle.claim,
            "supporting": bundle.supporting_signal_ids,
            "counter": bundle.counter_signal_ids,
            "missing": bundle.missing_expected,
        }
        raw = agent(prompt=json.dumps(payload))
        text = str(raw)
        parsed = _extract_json(text)
        if parsed and parsed.get("insights"):
            parsed["insights"] = [
                Insight.model_validate(i) if isinstance(i, dict) else i
                for i in parsed["insights"]
            ]
        return parsed
    except Exception as exc:  # noqa: BLE001
        log.warning("recovery_investigator_agent.failed", error=str(exc))
        return None


def run_recovery_planner_agent(state: Any) -> dict[str, Any] | None:
    """Optional LLM recovery plan narrative — stub returns None."""
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _intervals_from_fixtures(replay_fixtures: dict[str, Any], signal: Any) -> list[Any]:
    """Build AvailabilityInterval list from replay fixtures or stub."""
    from ..graph.nodes import incident_correlation_stub
    from ..graph.types import GraphState

    # Build a minimal state to call the stub and get intervals
    stub_state = GraphState(
        opportunity_id="strands-helper",
        signal=signal,
        replay_fixtures=replay_fixtures,
    )
    stub_result = incident_correlation_stub(stub_state)
    hypothesis = stub_result.get("hypothesis")
    if hypothesis is not None:
        return list(hypothesis.availability_intervals)
    return []


def _billed_from_fixtures(replay_fixtures: dict[str, Any]) -> Decimal:
    """Extract billed amount from replay fixtures or return real inject default."""
    billing = replay_fixtures.get("billing_snapshot", {})
    if isinstance(billing, dict) and "billed_amount_usd" in billing:
        return Decimal(str(billing["billed_amount_usd"]))
    return Decimal("3.51")
