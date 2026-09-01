#!/usr/bin/env python3
"""
Recoup — AgentCore Runtime & Gateway Registration Script

Run AFTER ./scripts/deploy.sh has completed successfully.
Requires CDK outputs at infra/cdk-outputs.json.

Usage:
    python scripts/register_agentcore.py [--dry-run] [--region us-east-1]

Outputs:
    infra/agentcore-ids.json  — runtime ID + gateway ID (add these to .env)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CDK_OUTPUTS_FILE = REPO_ROOT / "infra" / "cdk-outputs.json"
IDS_OUTPUT_FILE = REPO_ROOT / "infra" / "agentcore-ids.json"
AGENTCORE_CONFIG_FILE = REPO_ROOT / "infra" / "agentcore-config.yaml"

# ── Tool definitions (mirrors infra/agentcore-config.yaml) ──────────────────
STUB_TOOLS = [
    {
        "name": "get_cloudwatch_metrics",
        "description": "Retrieve CloudWatch metric statistics for a given namespace/metric/period.",
        "actionType": "READ",
        "inputSchema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string"},
                "metric_name": {"type": "string"},
                "dimensions": {"type": "object"},
                "start_time": {"type": "string", "format": "date-time"},
                "end_time": {"type": "string", "format": "date-time"},
                "period": {"type": "integer", "default": 300},
                "stat": {"type": "string", "default": "Average"},
            },
            "required": ["namespace", "metric_name", "start_time", "end_time"],
        },
    },
    {
        "name": "get_health_event",
        "description": "Retrieve AWS Health event details by event ARN.",
        "actionType": "READ",
        "inputSchema": {
            "type": "object",
            "properties": {"event_arn": {"type": "string"}},
            "required": ["event_arn"],
        },
    },
    {
        "name": "store_evidence",
        "description": "Store sanitized evidence to S3 and record hash in DynamoDB.",
        "actionType": "WRITE_INTERNAL",
        "inputSchema": {
            "type": "object",
            "properties": {
                "opportunity_id": {"type": "string"},
                "evidence_type": {"type": "string"},
                "content": {"type": "object"},
                "sensitivity": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH"],
                },
            },
            "required": ["opportunity_id", "evidence_type", "content"],
        },
    },
]


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


def get_boto3_client(service: str, region: str):
    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 not installed — run: pip install boto3")
        sys.exit(1)
    return boto3.client(service, region_name=region)


def create_agentcore_runtime(client, runtime_role_arn: str, region: str, dry_run: bool) -> str:
    """Create (or fetch existing) Bedrock Agent (AgentCore Runtime)."""
    # Correct boto3 bedrock-agent parameter names (from botocore validation error)
    create_params = {
        "agentName": "recoup-recovery-agent",
        "description": "Recoup autonomous cloud spend recovery agent",
        "agentResourceRoleArn": runtime_role_arn,
        "foundationModel": os.getenv(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
        ),
        "instruction": (
            "You are a Recoup recovery agent. You investigate AWS SLA breaches, "
            "collect evidence, and prepare support cases for human approval. "
            "You NEVER make financial conclusions — all credit calculations are "
            "performed by deterministic engines. You NEVER take destructive actions "
            "without explicit human approval."
        ),
        "idleSessionTTLInSeconds": 3600,
    }

    if dry_run:
        print("  [DRY RUN] Would create Bedrock Agent: recoup-recovery-agent")
        print(f"  Params: {json.dumps(create_params, indent=2)}")
        return "dry-run-runtime-id"

    try:
        bedrock = get_boto3_client("bedrock-agent", region)
        response = bedrock.create_agent(**create_params)
        runtime_id = response["agent"]["agentId"]
        print(f"  Created Bedrock Agent: {runtime_id}")

        # Prepare the agent so it becomes invokable
        print("  Preparing agent (building draft version)...")
        bedrock.prepare_agent(agentId=runtime_id)
        print("  Agent prepared")
        return runtime_id

    except Exception as e:
        if "already exists" in str(e).lower() or "ConflictException" in type(e).__name__:
            bedrock = get_boto3_client("bedrock-agent", region)
            agents = bedrock.list_agents()["agentSummaries"]
            for agent in agents:
                if agent["agentName"] == "recoup-recovery-agent":
                    print(f"  Agent already exists: {agent['agentId']}")
                    return agent["agentId"]
        raise


def register_gateway_tools(
    client,
    runtime_id: str,
    gateway_role_arn: str,
    region: str,
    dry_run: bool,
) -> str:
    """Register stub tools with AgentCore Gateway (action group)."""
    if dry_run:
        print(f"  [DRY RUN] Would register {len(STUB_TOOLS)} tools as action group")
        for t in STUB_TOOLS:
            print(f"    - {t['name']} ({t['actionType']})")
        return "dry-run-gateway-id"

    try:
        bedrock = get_boto3_client("bedrock-agent", region)
        response = bedrock.create_agent_action_group(
            agentId=runtime_id,
            agentVersion="DRAFT",
            actionGroupName="recoup-tools",
            description="Recoup read and write tools for AWS investigation",
            # RETURN_CONTROL tells Bedrock to return tool calls to the caller
            # rather than invoking a Lambda directly — correct for Strands integration
            actionGroupExecutor={"customControl": "RETURN_CONTROL"},
            functionSchema={
                "functions": [
                    {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": {
                            k: {
                                "type": v.get("type", "string"),
                                "description": v.get("description", k),
                                "required": k in t["inputSchema"].get("required", []),
                            }
                            for k, v in t["inputSchema"]
                            .get("properties", {})
                            .items()
                        },
                    }
                    for t in STUB_TOOLS
                ]
            },
        )
        group_id = response["agentActionGroup"]["actionGroupId"]
        print(f"  Registered {len(STUB_TOOLS)} tools — action group: {group_id}")

        # Re-prepare after adding action group
        bedrock.prepare_agent(agentId=runtime_id)
        print("  Agent re-prepared with tools")
        return group_id

    except Exception as e:
        if "already exists" in str(e).lower():
            print("  Action group already exists — skipping registration")
            return "existing"
        raise


def prepare_agent(client, runtime_id: str, region: str, dry_run: bool) -> None:
    """No-op — prepare is now called inside create and register steps."""
    if dry_run:
        print("  [DRY RUN] Agent prepare already handled in prior steps")
        return
    print("  Agent is ready to invoke")


def main() -> None:
    parser = argparse.ArgumentParser(description="Register Recoup AgentCore Runtime + Gateway")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen, don't call AWS")
    parser.add_argument("--region", default=os.getenv("CDK_DEFAULT_REGION", "us-east-1"))
    args = parser.parse_args()

    print("=" * 60)
    print("  Recoup — AgentCore Registration")
    print(f"  Region : {args.region}")
    print(f"  Dry run: {args.dry_run}")
    print("=" * 60)

    # Load CDK outputs
    outputs = load_cdk_outputs(args.region)
    runtime_role_arn = outputs.get("RuntimeRoleArn", os.getenv("RECOUP_RUNTIME_ROLE_ARN", ""))
    gateway_role_arn = outputs.get("GatewayExecutionRoleArn", os.getenv("RECOUP_GATEWAY_EXECUTION_ROLE_ARN", ""))

    if not runtime_role_arn:
        print("ERROR: RuntimeRoleArn not found — deploy CDK stack first")
        sys.exit(1)

    print(f"\n[1/3] Creating AgentCore Runtime...")
    client = None if args.dry_run else get_boto3_client("bedrock-agent", args.region)
    runtime_id = create_agentcore_runtime(client, runtime_role_arn, args.region, args.dry_run)

    print(f"\n[2/3] Registering Gateway tools...")
    gateway_id = register_gateway_tools(client, runtime_id, gateway_role_arn, args.region, args.dry_run)

    print(f"\n[3/3] Preparing agent...")
    prepare_agent(client, runtime_id, args.region, args.dry_run)

    # Write IDs to file
    ids = {
        "runtime_id": runtime_id,
        "gateway_id": gateway_id,
        "region": args.region,
    }
    if not args.dry_run:
        IDS_OUTPUT_FILE.write_text(json.dumps(ids, indent=2))
        print(f"\n  IDs written to {IDS_OUTPUT_FILE}")

    print("\n" + "=" * 60)
    print("  Registration complete")
    print(f"  RECOUP_AGENTCORE_RUNTIME_ID={runtime_id}")
    print(f"  RECOUP_AGENTCORE_GATEWAY_ID={gateway_id}")
    print("\n  Add these to your .env file.")
    print("=" * 60)


if __name__ == "__main__":
    main()
