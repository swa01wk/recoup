#!/usr/bin/env python3
"""
Recoup — AgentCore Harness & Gateway Registration Script

Registers the Recoup agent using the Amazon Bedrock AgentCore APIs
(bedrock-agentcore-control).  Classic Bedrock Agents is in maintenance
mode for new accounts as of July 30 2026; this script targets the new
service exclusively.

Run AFTER ./scripts/deploy.sh has completed successfully.
Requires CDK outputs at infra/cdk-outputs.json.

Usage:
    python scripts/register_agentcore.py [--dry-run] [--region us-east-1]

Outputs:
    infra/agentcore-ids.json  — harness ID + harness ARN + gateway ID
                                (add these to .env)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CDK_OUTPUTS_FILE = REPO_ROOT / "infra" / "cdk-outputs.json"
IDS_OUTPUT_FILE = REPO_ROOT / "infra" / "agentcore-ids.json"

HARNESS_NAME = "recoup_recovery_agent"
GATEWAY_NAME = "recoup-tool-gateway"

SYSTEM_PROMPT = (
    "You are a Recoup recovery agent. You investigate AWS SLA breaches, "
    "collect evidence, and prepare support cases for human approval. "
    "You NEVER make financial conclusions — all credit calculations are "
    "performed by deterministic engines. You NEVER take destructive actions "
    "without explicit human approval."
)

# Tool descriptions for the MCP gateway targets (registered against Lambda ARNs
# once those are deployed in Phase 1+).  Presence here is informational for the
# dry-run output; actual registration happens in register_gateway_targets().
TOOL_MANIFEST = [
    {"name": "get_cloudwatch_metrics",   "action_class": "READ"},
    {"name": "query_cloudwatch_logs",    "action_class": "READ_SENSITIVE"},
    {"name": "get_health_event",         "action_class": "READ"},
    {"name": "get_cost_and_usage",       "action_class": "READ_FINANCIAL"},
    {"name": "get_cost_anomalies",       "action_class": "READ_FINANCIAL"},
    {"name": "list_cost_opt_recs",       "action_class": "READ_FINANCIAL"},
    {"name": "lookup_cloudtrail_events", "action_class": "READ_SENSITIVE"},
    {"name": "store_evidence",           "action_class": "WRITE_INTERNAL"},
    {"name": "create_approval_request",  "action_class": "WRITE_INTERNAL"},
    {"name": "simulate_support_case",    "action_class": "WRITE_INTERNAL"},
    {"name": "submit_support_case",      "action_class": "WRITE_EXTERNAL_FINANCIAL"},
    {"name": "stop_demo_instance",       "action_class": "MUTATE_RED"},
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_boto3_client(service: str, region: str):
    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 not installed — run: pip install boto3")
        sys.exit(1)
    return boto3.client(service, region_name=region)


def load_cdk_outputs(region: str) -> dict:
    if not CDK_OUTPUTS_FILE.exists():
        print(f"ERROR: {CDK_OUTPUTS_FILE} not found — run ./scripts/deploy.sh first")
        sys.exit(1)
    outputs = json.loads(CDK_OUTPUTS_FILE.read_text())
    stack = outputs.get("RecoupInfraStack", {})
    if not stack:
        print("ERROR: RecoupInfraStack outputs not found in cdk-outputs.json")
        sys.exit(1)
    return stack


# ── Step 1: AgentCore Harness (replaces classic create_agent) ────────────────

def create_agentcore_harness(control, runtime_role_arn: str, region: str, dry_run: bool) -> tuple[str, str]:
    """Create (or fetch existing) AgentCore Harness.

    Returns (harness_id, harness_arn).
    """
    model_id = os.getenv(
        "BEDROCK_MODEL_ID",
        "us.amazon.nova-pro-v1:0",  # Nova Pro: instant access, no approval gate
    )

    create_params: dict = {
        "harnessName": HARNESS_NAME,
        "executionRoleArn": runtime_role_arn,
        # Model configuration — new AgentCore harness API shape
        "model": {
            "bedrockModelConfig": {
                "modelId": model_id,
            }
        },
        # System prompt as a list of content blocks
        "systemPrompt": [{"text": SYSTEM_PROMPT}],
        # Lifecycle: 1-hour idle session timeout
        "environment": {
            "agentCoreRuntimeEnvironment": {
                "lifecycleConfiguration": {
                    "idleRuntimeSessionTimeout": 3600,
                },
                "networkConfiguration": {
                    "networkMode": "PUBLIC",
                },
            }
        },
    }

    if dry_run:
        print(f"  [DRY RUN] Would create AgentCore Harness: {HARNESS_NAME}")
        print(f"  Params: {json.dumps(create_params, indent=2)}")
        return "dry-run-harness-id", "arn:dry-run:harness/dry-run-harness-id"

    try:
        response = control.create_harness(**create_params)
        h = response["harness"]
        harness_id = h["harnessId"]
        harness_arn = h["arn"]
        print(f"  Created AgentCore Harness: {harness_id}")
        print(f"  Harness ARN : {harness_arn}")
        _wait_for_harness_ready(control, harness_id)
        return harness_id, harness_arn

    except Exception as e:
        err_name = type(e).__name__
        if "already exists" in str(e).lower() or "ConflictException" in err_name:
            print(f"  Harness '{HARNESS_NAME}' already exists — fetching ID…")
            resp = control.list_harnesses()
            for h in resp.get("harnesses", []):
                if h["harnessName"] == HARNESS_NAME:
                    harness_id = h["harnessId"]
                    harness_arn = h.get("arn", "")
                    print(f"  Found existing harness: {harness_id}")
                    return harness_id, harness_arn
            print("  ERROR: Could not find existing harness in list — check AWS console")
        raise


def _wait_for_harness_ready(control, harness_id: str, timeout: int = 300) -> None:
    """Poll GetHarness until status is READY (or timeout)."""
    print("  Waiting for harness to reach READY status…", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = control.get_harness(harnessId=harness_id)
        # response is nested: resp['harness']['status']
        harness = resp.get("harness", resp)
        status = harness.get("status", "UNKNOWN")
        if status == "READY":
            print(" READY")
            return
        if status in ("FAILED", "CREATE_FAILED", "DELETED"):
            print(f" {status}")
            print(f"  ERROR: Harness entered terminal state: {status}")
            sys.exit(1)
        print(".", end="", flush=True)
        time.sleep(10)
    print(" TIMEOUT")
    print(f"  WARNING: Harness not READY after {timeout}s — continuing anyway")


# ── Step 2: AgentCore Gateway (replaces create_agent_action_group) ───────────

def create_agentcore_gateway(control, gateway_role_arn: str, region: str, dry_run: bool) -> str:
    """Create (or fetch existing) AgentCore Gateway.

    Returns gateway_id.
    """
    create_params: dict = {
        "name": GATEWAY_NAME,
        "roleArn": gateway_role_arn,
        "protocolType": "MCP",
        # AWS_IAM: all calls must be SigV4-signed — fits internal agent-to-gateway use
        "authorizerType": "AWS_IAM",
        "description": "Recoup tool gateway — read/write AWS investigation tools",
    }

    if dry_run:
        print(f"  [DRY RUN] Would create AgentCore Gateway: {GATEWAY_NAME}")
        print(f"  Params: {json.dumps(create_params, indent=2)}")
        return "dry-run-gateway-id"

    try:
        response = control.create_gateway(**create_params)
        # response may be top-level or nested under 'gateway'
        gw = response.get("gateway", response)
        gateway_id = gw["gatewayId"]
        gateway_url = gw.get("gatewayUrl", "")
        print(f"  Created AgentCore Gateway: {gateway_id}")
        if gateway_url:
            print(f"  Gateway URL: {gateway_url}")
        return gateway_id

    except Exception as e:
        err_name = type(e).__name__
        if "already exists" in str(e).lower() or "ConflictException" in err_name:
            print(f"  Gateway '{GATEWAY_NAME}' already exists — fetching ID…")
            resp = control.list_gateways()
            for gw in resp.get("gateways", resp.get("gatewaySummaries", [])):
                if gw.get("name") == GATEWAY_NAME:
                    gw_id = gw["gatewayId"]
                    print(f"  Found existing gateway: {gw_id}")
                    return gw_id
        raise


# ── Step 3: Optional — register Lambda targets when ARNs are available ───────

def register_gateway_targets(control, gateway_id: str, outputs: dict, dry_run: bool) -> list[str]:
    """Register Lambda-backed gateway targets for each tool group.

    This step is optional for Phase 0 — Lambda ARNs are only available once
    Phase 1–3 deploys the tool Lambdas.  Missing ARNs are skipped gracefully.
    """
    # Map env-var keys to logical target names (one Lambda per tool group)
    target_groups = {
        "RECOUP_CW_TOOL_LAMBDA_ARN":       "recoup-cloudwatch-tools",
        "RECOUP_HEALTH_TOOL_LAMBDA_ARN":   "recoup-health-tools",
        "RECOUP_COST_TOOL_LAMBDA_ARN":     "recoup-cost-tools",
        "RECOUP_CLOUDTRAIL_TOOL_LAMBDA_ARN": "recoup-cloudtrail-tools",
        "RECOUP_EVIDENCE_TOOL_LAMBDA_ARN": "recoup-evidence-tools",
        "RECOUP_APPROVAL_TOOL_LAMBDA_ARN": "recoup-approval-tools",
        "RECOUP_SIMULATE_TOOL_LAMBDA_ARN": "recoup-simulate-tools",
        "RECOUP_SUPPORT_TOOL_LAMBDA_ARN":  "recoup-support-tools",
        "RECOUP_EC2_DEMO_TOOL_LAMBDA_ARN": "recoup-ec2-demo-tools",
    }

    registered: list[str] = []
    skipped: list[str] = []

    for env_key, target_name in target_groups.items():
        # Check CDK outputs first, fall back to env var
        lambda_arn = outputs.get(env_key.replace("RECOUP_", "").replace("_ARN", "Arn"), "") or os.getenv(env_key, "")
        if not lambda_arn:
            skipped.append(target_name)
            continue

        if dry_run:
            print(f"  [DRY RUN] Would register target: {target_name} → {lambda_arn}")
            registered.append(f"dry-run-{target_name}")
            continue

        try:
            response = control.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=target_name,
                description=f"Recoup tool Lambda: {target_name}",
                targetConfiguration={
                    "lambda": {
                        "lambdaArn": lambda_arn,
                        "toolSchema": {
                            "inlinePayload": [
                                {
                                    "name": target_name.replace("recoup-", "").replace("-tools", "").replace("-", "_"),
                                    "description": f"Tool group: {target_name}",
                                    "inputSchema": {"json": {"type": "object", "properties": {}}},
                                }
                            ]
                        },
                    }
                },
                credentialProviderConfigurations=[
                    {"credentialProviderType": "GATEWAY_IAM_ROLE"}
                ],
            )
            target_id = response["gatewayTargetId"]
            print(f"  Registered target: {target_name} → {target_id}")
            registered.append(target_id)
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  Target '{target_name}' already registered — skipping")
                registered.append("existing")
            else:
                print(f"  WARNING: Could not register target '{target_name}': {e}")

    if skipped:
        print(f"\n  ⚠  Skipped {len(skipped)} targets (Lambda ARNs not yet available):")
        for t in skipped:
            print(f"     • {t}")
        print("  Re-run this script after Phase 1–3 Lambdas are deployed.")

    return registered


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register Recoup AgentCore Harness + Gateway (new bedrock-agentcore-control API)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen without calling AWS",
    )
    parser.add_argument(
        "--region", default=os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
    )
    parser.add_argument(
        "--skip-targets", action="store_true",
        help="Skip gateway target registration (useful for Phase 0 before Lambdas exist)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Recoup — AgentCore Registration")
    print(f"  Service : bedrock-agentcore-control (new API)")
    print(f"  Region  : {args.region}")
    print(f"  Dry run : {args.dry_run}")
    print("=" * 60)

    outputs = load_cdk_outputs(args.region)
    runtime_role_arn = outputs.get("RuntimeRoleArn") or os.getenv("RECOUP_RUNTIME_ROLE_ARN", "")
    gateway_role_arn = outputs.get("GatewayExecutionRoleArn") or os.getenv("RECOUP_GATEWAY_EXECUTION_ROLE_ARN", "")

    if not runtime_role_arn:
        print("ERROR: RuntimeRoleArn not found — deploy CDK stack first")
        sys.exit(1)
    if not gateway_role_arn:
        print("ERROR: GatewayExecutionRoleArn not found — deploy CDK stack first")
        sys.exit(1)

    control = None if args.dry_run else get_boto3_client("bedrock-agentcore-control", args.region)

    # ── 1. Harness ────────────────────────────────────────────────────────────
    print("\n[1/3] Creating AgentCore Harness…")
    harness_id, harness_arn = create_agentcore_harness(control, runtime_role_arn, args.region, args.dry_run)

    # ── 2. Gateway ────────────────────────────────────────────────────────────
    print("\n[2/3] Creating AgentCore Gateway…")
    gateway_id = create_agentcore_gateway(control, gateway_role_arn, args.region, args.dry_run)

    # ── 3. Gateway targets (optional) ─────────────────────────────────────────
    target_ids: list[str] = []
    if not args.skip_targets:
        print("\n[3/3] Registering Gateway targets (Lambda ARNs)…")
        target_ids = register_gateway_targets(control, gateway_id, outputs, args.dry_run)
    else:
        print("\n[3/3] Skipping gateway target registration (--skip-targets set)")

    # ── Persist IDs ───────────────────────────────────────────────────────────
    ids = {
        "harness_id": harness_id,
        "harness_arn": harness_arn,
        "gateway_id": gateway_id,
        "gateway_target_ids": target_ids,
        "region": args.region,
    }
    if not args.dry_run:
        IDS_OUTPUT_FILE.write_text(json.dumps(ids, indent=2))
        print(f"\n  IDs written to {IDS_OUTPUT_FILE}")

    print("\n" + "=" * 60)
    print("  Registration complete")
    print(f"  RECOUP_AGENTCORE_HARNESS_ID={harness_id}")
    print(f"  RECOUP_AGENTCORE_HARNESS_ARN={harness_arn}")
    print(f"  RECOUP_AGENTCORE_GATEWAY_ID={gateway_id}")
    print("\n  Add these to your .env file.")
    print("=" * 60)


if __name__ == "__main__":
    main()
