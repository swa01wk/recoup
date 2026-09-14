# Phase 6 — Live AWS Action Proof

> **Historical — internal only.** Current product: [docs index](../../../README.md) · [judge-demo.md](../../../judge-demo.md) · [STATUS.md](../STATUS.md).



**Timeline:** Day 10–12 (Target: by Sep 12, 2026)  
**Status:** `[x] Complete`  
**Depends on:** Phase 3 (safety layer), Phase 4 (frontend with approve flow)

---

## Objective

Implement and demonstrate the second complementary proof: a real, reversible, governed AWS action against a deliberately tagged sandbox EC2 instance. This path proves Recoup can actually execute — not just replay or recommend — while maintaining the same safety invariants as the full SLA workflow. **As-built:** `POST /api/ec2-demo/trigger` → HITL on **`/opportunities/{id}`** → optional `POST /api/ec2-demo/execute/{id}` (LIVE AWS ACTION badge on approval card when applicable).

---

## Goals

- [ ] A dedicated EC2 instance with tag `RecoupDemo=true` deployed in sandbox account
- [ ] `stop_demo_instance` tool registered in AgentCore Gateway with full policy guard
- [ ] CloudWatch utilization check confirms the instance is idle before recommending stop
- [ ] CloudTrail lookup confirms no blocking ownership or recent changes
- [ ] Decision Inbox shows explicit LIVE AWS ACTION card with full detail
- [ ] Human approval triggers AgentCore Policy evaluation; Cedar rule allows only for allowlisted resource
- [ ] Instance stops successfully; verified stopped state confirmed
- [ ] Instance never terminates; `TerminateInstances` is hard-denied in policy
- [ ] Reset script brings demo instance back to running state
- [ ] LIVE AWS ACTION badge clearly shown throughout the demo path
- [ ] Idempotency prevents duplicate stop calls

---

## Workstreams

### 6.1 Demo EC2 Instance

**CDK resource:**

```python
# infra/cdk/stacks/demo_stack.py
class RecoupDemoStack(Stack):
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Deliberately oversized for demo purposes (illustrates cost waste)
        self.demo_instance = ec2.Instance(
            self, "RecoupDemoInstance",
            instance_type=ec2.InstanceType("t3.micro"),
            machine_image=ec2.AmazonLinuxImage(),
            vpc=vpc,
            # Critical tags — stop_demo_instance checks these before acting
            user_data=ec2.UserData.for_linux(),
        )
        Tags.of(self.demo_instance).add("RecoupDemo", "true")
        Tags.of(self.demo_instance).add("ManagedBy", "recoup")
        Tags.of(self.demo_instance).add("Purpose", "hackathon-demo-reversible")
        Tags.of(self.demo_instance).add("Owner", "recoup-demo")
        Tags.of(self.demo_instance).add("Environment", "sandbox")
```

**Reset script (used between demo runs):**
```bash
#!/bin/bash
# scripts/reset_demo_instance.sh
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:RecoupDemo,Values=true" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text)

echo "Resetting demo instance: $INSTANCE_ID"
aws ec2 start-instances --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
echo "✓ Instance running: $INSTANCE_ID"
```

### 6.2 stop_demo_instance Tool

**Location:** `backend/src/recoup/tools/ec2_demo.py`

This tool is the most safety-critical in the codebase. Multiple overlapping guards.

```python
class StopDemoInstanceInput(BaseModel):
    opportunity_id: str
    instance_id: str
    approval_id: str
    idempotency_key: str

class StopDemoInstanceOutput(BaseModel):
    instance_id: str
    previous_state: str
    current_state: str
    verified_stopped: bool
    action_timestamp: datetime
    audit_trail: list[str]

async def stop_demo_instance(input: StopDemoInstanceInput) -> StopDemoInstanceOutput:
    """
    Stop only an explicitly allowlisted EC2 instance with RecoupDemo=true tag.
    
    Guards (all must pass before any AWS call):
    1. Instance ID must be in the allowlist (env-configured)
    2. Instance must have RecoupDemo=true tag (verified live from AWS)
    3. Approval must be valid and not expired
    4. Approval must be bound to this specific opportunity_id + instance_id hash
    5. AgentCore Policy must ALLOW this action (Cedar evaluated externally)
    6. Idempotency: check DynamoDB for prior completion of this idempotency_key
    """
    
    # Guard 1: Allowlist check
    allowed_instances = os.environ.get("RECOUP_DEMO_INSTANCE_ALLOWLIST", "").split(",")
    if input.instance_id not in allowed_instances:
        raise ToolDeniedError(
            f"Instance {input.instance_id} is not in the demo allowlist. "
            "stop_demo_instance can only target explicitly allowlisted resources."
        )
    
    # Guard 2: Live tag verification
    ec2 = boto3.client("ec2")
    tags = ec2.describe_tags(
        Filters=[
            {"Name": "resource-id", "Values": [input.instance_id]},
            {"Name": "key", "Values": ["RecoupDemo"]},
        ]
    )["Tags"]
    if not any(t["Value"] == "true" for t in tags):
        raise ToolDeniedError(
            f"Instance {input.instance_id} does not have RecoupDemo=true tag. "
            "Refusing to stop untagged instance."
        )
    
    # Guard 3 & 4: Approval validation
    approval = await fetch_approval(input.approval_id)
    if approval.state != "APPROVED":
        raise ApprovalRequiredError("Valid APPROVED approval required")
    if approval.expires_at < datetime.utcnow():
        raise ApprovalExpiredError("Approval has expired")
    
    expected_action_hash = sha256(
        f"{input.opportunity_id}:stop_demo_instance:{input.instance_id}".encode()
    ).hexdigest()
    if approval.claim_hash != expected_action_hash:
        raise ApprovalMismatchError("Approval is not bound to this instance_id")
    
    # Guard 5: Idempotency
    existing = await check_idempotency(input.idempotency_key)
    if existing:
        return existing  # Already done; return prior result
    
    # Audit trail before action
    audit_trail = [
        f"[{datetime.utcnow().isoformat()}] Guard checks passed for {input.instance_id}",
        f"Approval: {input.approval_id}, expires: {approval.expires_at.isoformat()}",
        f"Allowlist verified: {input.instance_id} in allowed instances",
        f"Tag verified: RecoupDemo=true confirmed via DescribeTags",
    ]
    
    # Get current state
    desc = ec2.describe_instances(InstanceIds=[input.instance_id])
    instance = desc["Reservations"][0]["Instances"][0]
    previous_state = instance["State"]["Name"]
    
    if previous_state == "stopped":
        # Already stopped — idempotent success
        audit_trail.append(f"Instance already stopped — idempotent return")
        return StopDemoInstanceOutput(
            instance_id=input.instance_id,
            previous_state=previous_state,
            current_state="stopped",
            verified_stopped=True,
            action_timestamp=datetime.utcnow(),
            audit_trail=audit_trail,
        )
    
    # Execute stop (NOT terminate)
    audit_trail.append(f"Issuing StopInstances for {input.instance_id}")
    ec2.stop_instances(InstanceIds=[input.instance_id])
    
    # Wait for stopped state (timeout 60s)
    waiter = ec2.get_waiter("instance_stopped")
    waiter.wait(
        InstanceIds=[input.instance_id],
        WaiterConfig={"Delay": 5, "MaxAttempts": 12},
    )
    
    # Verify final state
    desc2 = ec2.describe_instances(InstanceIds=[input.instance_id])
    final_state = desc2["Reservations"][0]["Instances"][0]["State"]["Name"]
    audit_trail.append(f"Verified state: {final_state}")
    
    result = StopDemoInstanceOutput(
        instance_id=input.instance_id,
        previous_state=previous_state,
        current_state=final_state,
        verified_stopped=final_state == "stopped",
        action_timestamp=datetime.utcnow(),
        audit_trail=audit_trail,
    )
    
    # Save idempotency record
    await save_idempotency(input.idempotency_key, result)
    return result
```

### 6.3 Cedar Policy for stop_demo_instance

```cedar
// Append to infra/policy/recoup-policy.cedar

permit(
  principal is RecoupRuntime,
  action == Action::"stop_demo_instance",
  resource is RecoupGateway
) when {
  // Approval must be present and valid
  context.approval_state == "APPROVED" &&
  context.approval_expires_at > context.current_time &&
  
  // Must be targeting exactly the demo instance
  context.target_instance_tag == "RecoupDemo=true" &&
  
  // Must be the allowlisted demo account
  context.target_account_id == context.allowlisted_demo_account_id &&
  
  // Not a simulation
  context.simulation_mode == false
};

// Absolutely forbid TerminateInstances — ever
forbid(
  principal,
  action == Action::"terminate_ec2_instance",
  resource
);
```

### 6.4 EC2 Demo Workflow

**This is a separate opportunity type, distinct from the SLA path:**

```
RecoupDemo=true EC2 instance
         ↓
CloudWatch CPU utilization check (last 7 days avg < 1%)
         ↓
CloudTrail ownership check (who created it; any recent changes)
         ↓
Estimated monthly waste calculation
  (instance type × hours × on-demand rate)
         ↓
Risk / Policy Gate → REQUIRE_APPROVAL (RED autonomy class)
         ↓
Decision Inbox (LIVE AWS ACTION card)
         ↓
Human approval
         ↓
AgentCore Policy → Cedar evaluation → ALLOW
         ↓
stop_demo_instance() → verify stopped state
         ↓
Audit trail displayed in Trace view
```

**LIVE AWS ACTION card in Decision Inbox:**
```
┌──────────────────────────────────────────────────────────┐
│ DECISION INBOX                         ⏱ 23:58:44        │
├──────────────────────────────────────────────────────────┤
│ 🔴 LIVE AWS ACTION                                       │
│ This will execute a real change in your AWS account.     │
├──────────────────────────────────────────────────────────┤
│ ACTION       Stop EC2 Instance                           │
│ INSTANCE     i-0abc123def456...                          │
│ TYPE         t3.micro                                    │
│ REGION       us-east-1                                   │
│ TAG          RecoupDemo=true (verified ✓)                │
│ AVG CPU      0.2% over 7 days                            │
│ EST. WASTE   ~$8.64/month at on-demand rate              │
│                                                          │
│ SAFETY CHECKS                                            │
│ ✓ Instance is in allowlist                               │
│ ✓ RecoupDemo=true tag confirmed via AWS API              │
│ ✓ No recent critical changes in CloudTrail               │
│ ✓ NOT terminate — only stop (reversible)                 │
│                                                          │
│ POLICY       AgentCore Cedar policy will be evaluated    │
│              before execution.                           │
│                                                          │
│         [Decline]              [Approve Stop →]          │
└──────────────────────────────────────────────────────────┘
```

### 6.5 Opportunity Type: OPTIMIZATION

```python
class RecoveryOpportunity(BaseModel):
    type: Literal["SLA", "ANOMALY", "OPTIMIZATION"]
    ...

# EC2 demo uses type="OPTIMIZATION"
# SLA replay uses type="SLA"
```

### 6.6 Live vs Replay Routing for EC2 Demo

```python
class EC2DemoAdapter:
    """Routes stop_demo_instance to real or replay based on simulation_mode."""

    async def stop_instance(self, input: StopDemoInstanceInput, simulation_mode: bool):
        if simulation_mode:
            # Replay mode: record expected outcome without touching AWS
            return StopDemoInstanceOutput(
                instance_id=input.instance_id,
                previous_state="running",
                current_state="stopped",  # what would happen
                verified_stopped=True,
                action_timestamp=datetime.utcnow(),
                audit_trail=["[REPLAY] No real AWS action taken"],
            )
        return await stop_demo_instance(input)
```

### 6.7 Verification After Stop

```python
async def verify_instance_stopped(instance_id: str) -> dict:
    ec2 = boto3.client("ec2")
    desc = ec2.describe_instances(InstanceIds=[instance_id])
    state = desc["Reservations"][0]["Instances"][0]["State"]
    return {
        "instance_id": instance_id,
        "state_name": state["Name"],
        "state_code": state["Code"],
        "verified": state["Name"] == "stopped",
    }
```

### 6.8 Demo Video Scripting (EC2 Path)

**Intended demo sequence (part of 5-minute video):**

```
0:00–0:30 — Command Center: show OPTIMIZATION opportunity alongside SLA opportunity
0:30–1:00 — Opportunity Detail: CPU utilization graph, CloudTrail context, estimated waste
1:00–1:30 — Decision Inbox: LIVE AWS ACTION card (read all safety checks aloud)
1:30–2:00 — Click Approve → trace shows policy evaluation → instance stops
2:00–2:15 — Trace view: show verify_instance_stopped confirmation
2:15–2:30 — "Real action, reversible, governed. Same architecture as the SLA claim."
```

---

## Definition of Done

| Check | Criteria |
|-------|----------|
| Demo instance | EC2 with `RecoupDemo=true` running in sandbox account |
| Allowlist | Instance ID in `RECOUP_DEMO_INSTANCE_ALLOWLIST` env var |
| Tool guards | All 6 guards pass before any EC2 API call |
| Policy | Cedar rule for `stop_demo_instance` evaluates ALLOW/DENY correctly |
| Terminate blocked | `terminate_ec2_instance` test → DENY; no waiver |
| Idempotency | Duplicate call returns prior result without second stop call |
| Reset script | Instance returns to `running` state within 30 seconds |
| LIVE badge | Clearly visible throughout the approval and trace views |
| Trace | Complete audit trail in Trace view including before/after state |
| Replay mode | EC2 demo can also run in replay mode (for dry-run testing) |

---

## Post-Implementation Documentation

> Created in `plans/docs/` after phase completion.

- `docs/live-action-demo.md` — How to set up and run the live EC2 demo, reset procedure
- `docs/ec2-demo-safety.md` — Safety guard design, allowlist configuration, and policy enforcement
- `docs/reversibility-guarantee.md` — How Recoup ensures live actions are reversible and targeted

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Instance accidentally terminated | `TerminateInstances` hard-denied in Cedar; tool only calls `StopInstances` |
| Instance targeted wrong resource | Allowlist + live tag verification both required before stop |
| Demo instance is stopped before demo | Reset script; check state before filming; consider auto-restart if stopped |
| Policy not evaluating correctly in live mode | End-to-end integration test against real AgentCore Policy endpoint |
| Stop takes > 60 seconds | Use waiter with timeout; show "stopping" state in UI during wait |
