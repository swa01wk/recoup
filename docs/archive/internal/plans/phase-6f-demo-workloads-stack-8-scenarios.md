# Phase 6f — RecoupDemoWorkloadsStack & 8 Scenario Coverage

> **Historical — internal only.** Current product: [docs index](../../../README.md) · [judge-demo.md](../../../judge-demo.md) · [STATUS.md](../STATUS.md).



**Timeline:** Sep 3–6, 2026  
**Status:** `[ ] Not Started`  
**Depends on:** Phase 6e ✅ (IAM roles), Phase 6d ✅ (scanner module)  
**Source document:** `Recoup_AWS_Target_Account_Demo_Plan.docx` §§ 4–6, 9–14

---

## Why This Phase Exists

Phase 6 (Live AWS Action Proof) proved one scenario: idle EC2 stop. The document's vision is richer — **8 controlled waste scenarios** deployed as a self-contained CDK stack, each with its own `RecoupScenario` tag and dedicated scanner. A judge who clicks "Scan" should see a diverse ranked list of findings, not just one.

This phase:
1. Deploys `RecoupDemoWorkloadsStack` — all 8 waste scenarios as IaC
2. Generates synthetic activity so EC2, RDS, and Lambda accumulate useful CloudWatch history
3. Wires the 9 existing scanners to discover these resources through `RecoupReadOnlyRole` (Phase 6e)
4. Surfaces all findings in the Account Scanner UI with evidence and estimated savings

---

## The 8 Demo Scenarios

| # | Scenario Tag | Resource Type | Waste Signal | Scanner |
|---|---|---|---|---|
| 1 | `oversized-ec2` | EC2 `t3.medium` (or `t3.large`) | CPU < 5% over 7 days + Compute Optimizer recommends downsize | `EC2Scanner` |
| 2 | `unattached-ebs` | EBS `gp3` 100 GiB | Not attached to any instance | `EBSScanner` |
| 3 | `gp2-migration` | EBS `gp2` 50 GiB | Volume type is gp2 (AWS default → gp3 is cheaper at same perf) | `EBSScanner` |
| 4 | `idle-eip` | Elastic IP (EIP) | Allocated but not associated with any running resource | `EIPScanner` |
| 5 | `idle-rds` | RDS `db.t3.micro` MySQL | CPU < 5%, connections ≈ 0 over 7 days | `RDSScanner` |
| 6 | `s3-no-lifecycle` | S3 bucket ~10 GiB | No lifecycle policy; all objects in `STANDARD` storage class | `S3Scanner` |
| 7 | `oversized-lambda` | Lambda 1024 MB memory | < 5 invocations last 30 days; Compute Optimizer recommends 256 MB | `LambdaScanner` |
| 8 | `stale-snapshot` | EBS snapshot > 90 days | Source volume deleted; no restore needed | `EBSScanner` (snapshot variant) |

> **Budget constraint:** The demo spend target is $30–$50 total (§10 of source document). Resource sizes are intentionally modest — the goal is convincing waste signals, not enterprise scale.

---

## Goals

- [ ] `RecoupDemoWorkloadsStack` CDK stack deploys all 8 scenarios cleanly
- [ ] All demo resources tagged: `Project=Recoup`, `Environment=hackathon-demo`, `RecoupDemo=true`, `ManagedBy=CDK`, `RecoupScenario=<type>`
- [ ] Synthetic activity script runs for EC2, RDS, Lambda so CloudWatch has 7 days of near-zero metrics
- [ ] At least 6 of 8 scenarios produce a finding via the scanner (two may have zero signal in new account)
- [ ] Each finding shows: resource ID, type, severity, estimated monthly savings, supporting evidence
- [ ] Stack is independently destroyable via CDK (`cdk destroy RecoupDemoWorkloadsStack`)
- [ ] AWS Budget alerts set before stack deploy ($25, $40, $50 thresholds)
- [ ] Compute Optimizer opted in; at least one recommendation appears after 24h of metric history

---

## Workstreams

### 6f.1 CDK Stack Definition

**File:** `infra/cdk/stacks/demo_workloads_stack.py`

```python
from aws_cdk import (
    Stack, Tags, RemovalPolicy, Duration,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_iam as iam,
)
from constructs import Construct

DEMO_TAGS = {
    "Project": "Recoup",
    "Environment": "hackathon-demo",
    "RecoupDemo": "true",
    "ManagedBy": "CDK",
}

class RecoupDemoWorkloadsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Scenario 1 — Oversized EC2
        oversized_ec2 = ec2.Instance(
            self, "OversizedEC2",
            instance_type=ec2.InstanceType("t3.medium"),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
            vpc=vpc,
        )
        Tags.of(oversized_ec2).add("RecoupScenario", "oversized-ec2")
        self._apply_demo_tags(oversized_ec2)

        # Scenario 2 — Unattached EBS
        unattached_vol = ec2.Volume(
            self, "UnattachedEBS",
            availability_zone=f"{self.region}a",
            size=ec2.Size.gibibytes(100),
            volume_type=ec2.EbsDeviceVolumeType.GP3,
            removal_policy=RemovalPolicy.DESTROY,
        )
        Tags.of(unattached_vol).add("RecoupScenario", "unattached-ebs")
        self._apply_demo_tags(unattached_vol)

        # Scenario 3 — gp2 Volume (migration candidate)
        gp2_vol = ec2.Volume(
            self, "GP2Volume",
            availability_zone=f"{self.region}a",
            size=ec2.Size.gibibytes(50),
            volume_type=ec2.EbsDeviceVolumeType.GP2,
            removal_policy=RemovalPolicy.DESTROY,
        )
        Tags.of(gp2_vol).add("RecoupScenario", "gp2-migration")
        self._apply_demo_tags(gp2_vol)

        # Scenario 4 — Idle EIP (allocated, not associated)
        idle_eip = ec2.CfnEIP(self, "IdleEIP")
        Tags.of(idle_eip).add("RecoupScenario", "idle-eip")
        self._apply_demo_tags(idle_eip)

        # Scenario 5 — Idle RDS (smallest practical)
        idle_rds = rds.DatabaseInstance(
            self, "IdleRDS",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0_35
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=False,
            backup_retention=Duration.days(0),
        )
        Tags.of(idle_rds).add("RecoupScenario", "idle-rds")
        self._apply_demo_tags(idle_rds)

        # Scenario 6 — S3 with no lifecycle policy
        no_lifecycle_bucket = s3.Bucket(
            self, "NoLifecycleBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        Tags.of(no_lifecycle_bucket).add("RecoupScenario", "s3-no-lifecycle")
        self._apply_demo_tags(no_lifecycle_bucket)

        # Scenario 7 — Oversized Lambda
        oversized_lambda = _lambda.Function(
            self, "OversizedLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=_lambda.Code.from_inline("def handler(e, c): return {}"),
            memory_size=1024,  # deliberately oversized
        )
        Tags.of(oversized_lambda).add("RecoupScenario", "oversized-lambda")
        self._apply_demo_tags(oversized_lambda)

        # Scenario 8 — Stale EBS Snapshot (created manually or via script)
        # Note: CDK doesn't create snapshots natively; use scripts/generate_stale_snapshot.py

    def _apply_demo_tags(self, resource):
        for k, v in DEMO_TAGS.items():
            Tags.of(resource).add(k, v)
```

> **Scenario 8 (stale snapshot)** is created via a one-time script since CDK cannot create standalone EBS snapshots. See `scripts/create_stale_snapshot.py`.

---

### 6f.2 Budget Alerts (Pre-Deploy)

**Create before deploying the stack** (AWS console or CLI):

```bash
# Budget 1 — Warning at $25
aws budgets create-budget \
  --account-id 625962218034 \
  --budget '{
    "BudgetName": "recoup-demo-warning",
    "BudgetLimit": {"Amount": "25", "Unit": "USD"},
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }' \
  --notifications-with-subscribers '[{
    "Notification": {
      "NotificationType": "ACTUAL",
      "ComparisonOperator": "GREATER_THAN",
      "Threshold": 100
    },
    "Subscribers": [{
      "SubscriptionType": "EMAIL",
      "Address": "swaroop.shivakumar@webknot.in"
    }]
  }]'

# Repeat for $40 and $50 thresholds
```

**Target:** Total demo spend ≤ $30–$50 including RDS (largest cost driver).

---

### 6f.3 Synthetic Activity Injection

EC2, RDS, and Lambda need ≥ 7 days of CloudWatch history to appear idle. For a new account, inject minimal synthetic activity to populate the metric namespace.

**File:** `scripts/inject_demo_activity.py`

```python
"""
Inject minimal activity so demo resources appear meaningfully idle in CloudWatch.
Run once after stack deploy; metrics appear within 5–15 minutes.
"""
import boto3

cloudwatch = boto3.client("cloudwatch")

def put_near_zero_cpu(instance_id: str, days: int = 7):
    """Write 288 data points (5-min intervals × 24h × days) at ~0.2% CPU."""
    import datetime, random
    now = datetime.datetime.utcnow()
    for i in range(288 * days):
        ts = now - datetime.timedelta(minutes=5 * i)
        cloudwatch.put_metric_data(
            Namespace="AWS/EC2",
            MetricData=[{
                "MetricName": "CPUUtilization",
                "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                "Timestamp": ts,
                "Value": round(random.uniform(0.1, 0.4), 2),
                "Unit": "Percent",
            }]
        )

# Equivalent helpers for RDS (DatabaseConnections ≈ 0) and Lambda (Invocations = 0)
```

> **Cost:** Custom metric writes ~$0.01 (first 10 custom metrics/month free tier).

---

### 6f.4 Scanner Integration — Discovery Through Role

After Phase 6e, scanners run through `CustomerConnection.build_session()`. For the demo workloads, the default connection uses `RecoupReadOnlyRole`:

```python
# backend/src/recoup/api/routes/scan.py

DEFAULT_DEMO_CONNECTION = CustomerConnection(
    role_arn=settings.recoup_readonly_role_arn,
    external_id=settings.recoup_external_id,
    region="us-east-1",
)

@router.post("/scan/preview")
async def scan_preview(req: Optional[ScanRequest] = None):
    conn = req.to_connection() if req else DEFAULT_DEMO_CONNECTION
    session = conn.build_session()
    return await _run_scan(session, [EC2Scanner, EBSScanner])
```

**Discovery by `RecoupScenario` tag:** Each scanner should filter (or annotate) findings by `RecoupScenario` tag to clearly identify demo resources vs real waste.

---

### 6f.5 EBS Scanner Enhancement — gp2 Detection + Stale Snapshots

The existing `EBSScanner` detects unattached volumes. Extend it to cover scenarios 3 and 8:

**gp2 detection:**
```python
# In EBSScanner.scan()
for vol in volumes:
    if vol["VolumeType"] == "gp2":
        savings = _estimate_gp2_to_gp3_savings(vol)
        yield Finding(
            service="ebs",
            finding_type="GP2_MIGRATION_CANDIDATE",
            resource_id=vol["VolumeId"],
            severity="MEDIUM",
            estimated_monthly_savings_usd=savings,
            evidence={"volume_type": "gp2", "size_gib": vol["Size"]},
        )
```

**Stale snapshot detection (scenario 8):**
```python
# New method or separate SnapshotScanner
for snap in snapshots:
    age_days = (datetime.utcnow() - snap["StartTime"].replace(tzinfo=None)).days
    if age_days > 90:
        source_volume_exists = _check_volume_exists(snap.get("VolumeId"))
        if not source_volume_exists:
            yield Finding(
                service="ebs",
                finding_type="STALE_SNAPSHOT",
                resource_id=snap["SnapshotId"],
                severity="LOW",
                estimated_monthly_savings_usd=_snapshot_cost(snap["VolumeSize"]),
                evidence={"age_days": age_days, "source_volume": "deleted"},
            )
```

---

### 6f.6 Per-Service Telemetry (Source Document §6)

Each finding must include the specific telemetry signals listed in §6 of the source document:

| Service | Required Evidence Fields |
|---|---|
| EC2 | `instance_type`, `state`, `tags`, `cpu_utilization_7d_avg`, `network_in_out`, `cost_context`, `compute_optimizer_recommendation` |
| EBS | `volume_type`, `size_gib`, `attachment_state`, `iops_config`, `throughput_config`, `snapshot_relationships` |
| RDS | `instance_class`, `engine`, `cpu_avg`, `connection_count_avg`, `io_signals`, `cost_context` |
| Lambda | `configured_memory_mb`, `p99_duration_ms`, `invocation_count_30d`, `error_rate`, `compute_optimizer_recommendation` |
| S3 | `storage_class_distribution`, `object_age_profile`, `lifecycle_policy_state`, `estimated_size_gib` |
| Networking | `eip_association_state`, `public_ipv4_owner`, `allocation_id` |
| Cost | `cost_explorer_monthly_estimate`, `tag_dimensions`, `resource_dimensions` |
| Compute Optimizer | `recommendation_type`, `current_config`, `recommended_config`, `estimated_savings_pct` |

Scanners should populate `Finding.evidence` with these fields where available.

---

### 6f.7 Frontend — Account Scanner Full Redesign

The `/scan` page needs a significant upgrade to showcase all 8 scenarios clearly. This is the primary UI surface for the multi-scenario demo story.

**File:** `frontend/src/app/scan/page.tsx`  
**Related:** `frontend/src/lib/api.ts`, `frontend/src/components/ui/badge.tsx`

#### Recoverable Savings Banner

At the top of scan results, a full-width highlight banner:

```tsx
<div className="rounded-xl border border-emerald-500/30 bg-emerald-900/20 p-5 flex items-center justify-between">
  <div>
    <p className="text-sm text-emerald-400 font-medium uppercase tracking-wide">Estimated Total Recoverable</p>
    <p className="text-3xl font-bold text-emerald-300 mt-1">${totalSavings.toFixed(2)}<span className="text-lg text-slate-400">/month</span></p>
  </div>
  <STSConnectedBadge roleArn={result.assumed_role_arn} accountId={result.assumed_role_account_id} />
</div>
```

#### Service Group Cards

Group findings by AWS service using collapsible sections:

```tsx
// Service groups: EC2, EBS, RDS, Lambda, S3, Networking
{SERVICE_GROUPS.map(group => (
  <ServiceGroupSection
    key={group.service}
    service={group.service}
    icon={group.icon}
    findings={findingsByService[group.service] ?? []}
    totalSavings={savingsByService[group.service]}
  />
))}
```

Each service group header shows:
- Service icon + name
- Finding count badge (e.g., `2 findings`)
- Per-service estimated savings

#### Finding Detail Expansion

Each finding card is expandable. Collapsed state shows:

| Element | Content |
|---|---|
| Severity badge | `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` (color-coded) |
| Resource ID | truncated, monospace |
| Finding type | human-readable (e.g., "Idle EC2 Instance", "gp2 → gp3 Migration") |
| Savings | `$XX.XX/month` in green |
| RecoupScenario tag | pill badge if present (e.g., `oversized-ec2`) |

Expanded state (click to open) shows full evidence panel:

```tsx
<div className="mt-3 border-t border-slate-700 pt-3 space-y-2 text-xs font-mono text-slate-400">
  {Object.entries(finding.evidence).map(([k, v]) => (
    <div key={k} className="flex gap-2">
      <span className="text-slate-500 min-w-[180px]">{k}</span>
      <span className="text-slate-300">{String(v)}</span>
    </div>
  ))}
</div>
```

#### RecoupScenario Tag Badge

For findings from demo workloads (tagged `RecoupDemo=true`), show a distinct `DEMO` badge and the specific scenario:

```tsx
export function ScenarioBadge({ scenario }: { scenario: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-violet-900/40 border border-violet-500/30 px-2 py-0.5 text-[10px] font-medium text-violet-300 uppercase tracking-wide">
      🏷 {scenario}
    </span>
  );
}
```

Add to `badge.tsx` alongside `LiveBadge`, `MockedBadge`, etc.

#### 8-Scenario Demo Map Panel

Add a visual panel above the scan form showing all 8 expected scenarios (for demo context):

```tsx
const DEMO_SCENARIOS = [
  { tag: 'oversized-ec2',    icon: '🖥',  label: 'Oversized EC2',         service: 'EC2' },
  { tag: 'unattached-ebs',   icon: '💾',  label: 'Unattached EBS Volume',  service: 'EBS' },
  { tag: 'gp2-migration',    icon: '⚡',  label: 'gp2 → gp3 Migration',    service: 'EBS' },
  { tag: 'idle-eip',         icon: '🌐',  label: 'Idle Elastic IP',        service: 'Networking' },
  { tag: 'idle-rds',         icon: '🗄',  label: 'Idle RDS Instance',      service: 'RDS' },
  { tag: 's3-no-lifecycle',  icon: '🪣',  label: 'S3 No Lifecycle Policy', service: 'S3' },
  { tag: 'oversized-lambda', icon: '⚙',  label: 'Oversized Lambda',       service: 'Lambda' },
  { tag: 'stale-snapshot',   icon: '📸',  label: 'Stale EBS Snapshot',     service: 'EBS' },
];
```

Each tile shows the scenario tag as a badge. After scanning, tiles light up green when their corresponding finding is detected (match on `finding.evidence.scenario_tag`).

#### Updated TypeScript Types

```typescript
// frontend/src/lib/api.ts — additions for Phase 6f

export interface Finding {
  service: string;
  finding_type: string;
  resource_id: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  estimated_monthly_savings_usd: number;
  evidence: Record<string, unknown>;       // new — expanded evidence map
  scenario_tag?: string;                   // new — from RecoupScenario tag
  is_demo_resource?: boolean;              // new — RecoupDemo=true
}

export interface ScanResult {
  findings: Finding[];
  errors: string[];
  duration_ms: number;
  total_estimated_savings_usd: number;     // new — pre-computed sum
  findings_by_service: Record<string, Finding[]>; // new — pre-grouped
  assumed_role_arn?: string;
  assumed_role_account_id?: string;
  session_name?: string;
}
```

#### Scan Progress Indicator

Replace the existing loading spinner with a per-scanner progress list (matches the 9 scanner names):

```tsx
const SCANNER_LABELS: Record<string, string> = {
  ec2: 'EC2 instances (CPU utilization)',
  ebs: 'EBS volumes & snapshots',
  eip: 'Elastic IPs',
  rds: 'RDS instances',
  s3: 'S3 buckets (lifecycle policies)',
  lambda: 'Lambda functions',
  lb: 'Load balancers',
  cwlogs: 'CloudWatch Log Groups',
  cost_explorer: 'Cost Explorer right-sizing',
};
```

Show each scanner as: `⟳ Scanning EC2...` → `✓ EC2: 1 finding` using SSE or polling.

#### Sidebar Navigation Update

The existing `/scan` sidebar entry already exists. Update the label to:

```
Account Scanner          (was: plain text)
→ Account Scanner  ↗ 6 findings   (after a scan completes — badge count)
```

#### Summary

| Frontend File | Change Type | Description |
|---|---|---|
| `frontend/src/app/scan/page.tsx` | Major rewrite | Savings banner, service groups, finding expansion, scenario map |
| `frontend/src/lib/api.ts` | Extend types | `Finding.evidence`, `Finding.scenario_tag`, `ScanResult.total_savings`, `ScanResult.findings_by_service` |
| `frontend/src/components/ui/badge.tsx` | Add variants | `ScenarioBadge`, `STSConnectedBadge` |
| `frontend/src/components/layout/sidebar.tsx` | Minor | Dynamic finding count badge on `/scan` nav entry |

---

### 6f.8 Compute Optimizer Opt-In

```bash
# One-time opt-in (takes 24–48h for first recommendations)
aws compute-optimizer update-enrollment-status --status Active
```

After 24h, `EC2Scanner` and `LambdaScanner` can pull real Compute Optimizer recommendations into finding evidence.

---

### 6f.9 Demo Story Integration (Source Document §12)

The complete 9-step demo story from the document maps to the Recoup UI as follows:

| Step | Document | Recoup UI Location |
|---|---|---|
| 1 | Show Recoup and demo workloads in same account, separated by IAM roles | `/scan` form — Role ARN pre-filled |
| 2 | Show STS AssumeRole temp credentials | Backend log / `_aws.assumed_role` in scan response |
| 3 | Discover tagged demo inventory across all 6 services | `/scan` results page — 6+ finding cards |
| 4 | Display multiple recovery opportunities and estimated impact | `/scan` "Estimated total recoverable: $X/month" banner |
| 5 | Open one strong finding (oversized EC2) — full evidence | Finding detail panel (CW CPU, Cost Explorer, Compute Optimizer) |
| 6 | Strands agent explains recommendation using assembled evidence | EC2 opportunity card with Strands reasoning (Phase 6c) |
| 7 | Run through deterministic policy checks | Risk gate / Cedar policy evaluation shown in trace |
| 8 | Analysis role cannot modify; remediation needs separate role + approval | Decision Inbox → LIVE AWS ACTION → `RecoupRemediationRole` |
| 9 | Explain cross-account production path | Verbal + `/scan` form helper text |

---

### 6f.10 Stale Snapshot Script

**File:** `scripts/create_stale_snapshot.py`

```bash
# Create a snapshot and immediately tag it as the stale demo scenario
VOLUME_ID=$(aws ec2 describe-volumes \
  --filters "Name=tag:RecoupScenario,Values=unattached-ebs" \
  --query "Volumes[0].VolumeId" --output text)

SNAP_ID=$(aws ec2 create-snapshot \
  --volume-id $VOLUME_ID \
  --description "Recoup demo stale snapshot" \
  --query SnapshotId --output text)

aws ec2 create-tags --resources $SNAP_ID --tags \
  Key=RecoupDemo,Value=true \
  Key=RecoupScenario,Value=stale-snapshot \
  Key=Project,Value=Recoup \
  Key=Environment,Value=hackathon-demo \
  Key=ManagedBy,Value=CDK
```

> After creation, update the snapshot timestamp by letting it age 90+ days, or mock the detection threshold to 1 day for demo purposes.

---

## Detection Strategy — Immediate vs Historical (Source Document §9)

| Detection Type | Scenarios | Requires CloudWatch History? |
|---|---|---|
| **Immediate** (state-based) | unattached-ebs, idle-eip, gp2-migration, stale-snapshot | ❌ No — detected from resource metadata alone |
| **Historical** (metric-based) | oversized-ec2, idle-rds, oversized-lambda | ✅ Yes — need 7+ days of near-zero metrics |

**Implication for demo timing:**
- Scenarios 2, 3, 4, 8 are detectable immediately after stack deploy
- Scenarios 1, 5, 7 need 24–48h of metric history (or synthetic injection from §6f.3)
- Target: ≥ 6 findings reliably detectable on demo day

---

## Cost Estimate

| Resource | Monthly Cost | Notes |
|---|---|---|
| EC2 `t3.medium` (running) | ~$30 | Largest cost; consider stopping between demo runs |
| RDS `db.t3.micro` | ~$15 | Second largest; stop when not filming |
| EBS `gp3` 100 GiB | ~$8 | Unattached but still billed |
| EBS `gp2` 50 GiB | ~$5 | Migration candidate |
| Lambda (oversized) | ~$0 | Nearly free if never invoked |
| S3 bucket | ~$0.23/GiB | Minimal for small dataset |
| EIP (unassociated) | ~$3.65 | Fixed rate per unused EIP |
| **Total estimate** | **~$62/month** | Stop EC2+RDS between sessions → ~$30 |

> **Mitigation:** Stop `oversized-ec2` and `idle-rds` after each demo session. They remain detectable from CloudWatch history even when stopped.

---

## Files to Create / Modify

### Backend & Infrastructure

| File | Purpose |
|---|---|
| `infra/cdk/stacks/demo_workloads_stack.py` | New — CDK stack for all 8 demo scenarios |
| `infra/cdk/app.py` | Add `RecoupDemoWorkloadsStack` instantiation |
| `backend/src/recoup/scanners/ebs_scanner.py` | Extend: add gp2 detection + stale snapshot detection |
| `backend/src/recoup/api/routes/scan.py` | Add `DEFAULT_DEMO_CONNECTION`; return `total_estimated_savings_usd` + `findings_by_service` + `scenario_tag` per finding |

### Scripts

| File | Purpose |
|---|---|
| `scripts/inject_demo_activity.py` | New — synthetic CloudWatch activity for EC2, RDS, Lambda |
| `scripts/create_stale_snapshot.py` | New — create and tag scenario 8 EBS snapshot |
| `scripts/create_budget_alerts.sh` | New — pre-deploy budget alerts at $25/$40/$50 |

### Frontend

| File | Change |
|---|---|
| `frontend/src/app/scan/page.tsx` | Major rewrite — savings banner, service groups, per-finding evidence expansion, 8-scenario map tiles, scanner progress list |
| `frontend/src/lib/api.ts` | Extend `Finding` (add `evidence`, `scenario_tag`, `is_demo_resource`); extend `ScanResult` (add `total_estimated_savings_usd`, `findings_by_service`) |
| `frontend/src/components/ui/badge.tsx` | Add `ScenarioBadge` (violet, scenario tag display) |
| `frontend/src/components/layout/sidebar.tsx` | Dynamic finding count badge on `/scan` nav entry after scan completes |

### Docs

| File | Purpose |
|---|---|
| `docs/demo-workloads.md` | New — deploy, reset, and destroy guide for all 8 scenarios |
| `docs/scanner-coverage.md` | New — per-scanner detection logic, evidence fields, and test scenarios |
| `docs/budget-safety.md` | New — budget alert setup, cost estimate, teardown procedure |

---

## Definition of Done (Source Document §13)

| Check | Criteria |
|---|---|
| All 8 scenarios deployed | `RecoupDemoWorkloadsStack` deploys without errors; all resources tagged |
| Discovery through role | Scanners use `RecoupReadOnlyRole` credentials exclusively; no direct access keys |
| ≥ 6 findings detected | At least 6 of 8 scenarios produce a Finding with severity and savings estimate |
| Evidence populated | Each finding includes service-specific evidence fields from §6f.6 |
| Savings displayed | "Estimated total recoverable" banner visible in Account Scanner UI |
| Analysis ≠ remediation | `RecoupReadOnlyRole` cannot stop EC2; separate `RecoupRemediationRole` required |
| Budget alerts | Three alerts configured before stack deploy; demo spend < $50 |
| Stack destroyable | `cdk destroy RecoupDemoWorkloadsStack` removes all 8 resources cleanly |
| Demo story runnable | 9-step demo story from §12 executable end-to-end in < 5 minutes |
| Connection abstraction | Changing `role_arn` to a different account's role is the only cross-account change |

---

---

## Documentation Updates (Phase 6f)

Complete all doc updates as part of this phase — before marking 6f Done.

### New Docs to Create

#### `docs/demo-workloads.md` *(new)*
Operational guide for the `RecoupDemoWorkloadsStack`:

- Stack overview: 8 scenarios, tagging strategy, naming convention
- Pre-deploy checklist: budget alerts, Compute Optimizer opt-in
- Deploy command: `cdk deploy RecoupDemoWorkloadsStack`
- Synthetic activity injection: when to run it, how long metrics take to appear
- Per-scenario resource table: resource type, ID lookup command, expected scanner finding
- Resetting between demo sessions: which resources to stop/start to save cost
- Destroy command: `cdk destroy RecoupDemoWorkloadsStack`; confirm all 8 resources removed
- Cost breakdown: EC2 (~$30), RDS (~$15), EBS (~$13), EIP (~$3.65) — total ≤ $50 with stop/start strategy

#### `docs/scanner-coverage.md` *(new)*
Reference for all 9 scanners:

| Scanner | Finding Type(s) | Key Evidence Fields | Threshold / Condition |
|---|---|---|---|
| `EC2Scanner` | IDLE_INSTANCE | cpu_7d_avg, instance_type, optimizer_rec | CPU < 5% over 7 days |
| `EBSScanner` | UNATTACHED_VOLUME | attachment_state, size_gib, volume_type | State = `available` |
| `EBSScanner` | GP2_MIGRATION | volume_type, size_gib, estimated_savings | type = `gp2` |
| `EBSScanner` | STALE_SNAPSHOT | age_days, source_volume_state | age > 90d AND source deleted |
| `EIPScanner` | IDLE_EIP | association_id, allocation_id | Not associated |
| `RDSScanner` | IDLE_RDS | cpu_7d_avg, connection_count_avg, instance_class | CPU < 5%, connections ≈ 0 |
| `S3Scanner` | NO_LIFECYCLE_POLICY | bucket_name, lifecycle_policy_state, size_gib | No lifecycle config |
| `LambdaScanner` | OVERSIZED_LAMBDA | memory_mb, invocation_count_30d, optimizer_rec | < 5 invocations / 30d |
| `LBScanner` | IDLE_LOAD_BALANCER | healthy_target_count, lb_type | 0 healthy targets |
| `CWLogsScanner` | NO_RETENTION_POLICY | log_group_name, retention_days | retention = Never Expire |
| `CostExplorerScanner` | RIGHT_SIZING | current_type, recommended_type, saving_pct | CE recommendation present |

- Detection strategy section: immediate (state-based) vs. historical (metric-based)
- How to add a new scanner (BaseScanner interface, Finding schema)
- Known limitations: new account has no metric history; use `inject_demo_activity.py` to seed

#### `docs/budget-safety.md` *(new)*
Cost management and safety controls for the demo environment:

- Pre-deploy: three AWS Budget alerts ($25/$40/$50) with email notification
- Resource cost breakdown table (monthly estimate per resource)
- Daily cost optimization: stop EC2 + RDS between demo sessions (~$45/month → ~$8/month when stopped)
- Free-tier eligibility: Lambda (always free at demo scale), S3 (first 5 GiB), CloudWatch metrics
- Emergency stop: `aws ec2 stop-instances` + `aws rds stop-db-instance` commands
- Stack teardown: full destroy sequence with verification

---

### Existing Docs to Update

#### `docs/architecture-overview.md` — **Major update**

| Section | Change |
|---|---|
| Add "Demo Workloads Architecture" section | Show `RecoupDemoWorkloadsStack` and how scanners reach it via `RecoupReadOnlyRole`; 8-scenario table |
| Update "AWS Services" table | Add `Compute Optimizer`, `RDS` (demo), `Lambda` (demo) to the services inventory |
| Update "Account Scanner" section | Explain it now uses `CustomerConnection` (STS AssumeRole) rather than direct credentials |
| Update architecture diagram description | Add `RecoupDemoWorkloadsStack` box showing 8 tagged resources |
| Update version/date | `Version: Phases 0–6f complete` |

**New section to add:**
```markdown
## Demo Workloads (Phase 6f)

RecoupDemoWorkloadsStack deploys 8 controlled waste scenarios...

| Scenario | Resource | Monthly Cost | Finding Type |
|---|---|---|---|
| oversized-ec2 | t3.medium EC2 | ~$30 | IDLE_INSTANCE |
...

All resources are tagged RecoupDemo=true and RecoupScenario=<type>.
Recoup discovers them exclusively through RecoupReadOnlyRole credentials.
```

---

#### `docs/infrastructure-runbook.md` — **Major update**

| Section | Change |
|---|---|
| Add "Demo Workloads Stack" section | Full deploy/destroy instructions for `RecoupDemoWorkloadsStack` |
| Add "Budget Safety" subsection | Pre-deploy budget alert commands; links to `docs/budget-safety.md` |
| Add "Synthetic Activity" subsection | When and how to run `scripts/inject_demo_activity.py` |
| Add "Demo Cost Management" subsection | Stop/start strategy to stay under $50/month |
| Update "Resource Inventory" table | Add all 8 demo scenario resources |
| Update "Cost Estimate" table | Add EC2, RDS, EBS volumes, EIP, Lambda, S3 bucket with monthly costs |

**Specific new content:**
```markdown
## RecoupDemoWorkloadsStack

### Pre-Deploy (run once)
1. Set up budget alerts: `./scripts/create_budget_alerts.sh`
2. Opt in Compute Optimizer: `aws compute-optimizer update-enrollment-status --status Active`

### Deploy
cdk deploy RecoupDemoWorkloadsStack

### Inject Synthetic Activity (run after deploy)
python scripts/inject_demo_activity.py
# Wait 15-30 minutes for CloudWatch to populate

### Between Demo Sessions (cost saving)
aws ec2 stop-instances --instance-ids <oversized-ec2-id>
aws rds stop-db-instance --db-instance-identifier <idle-rds-id>

### Destroy (post-hackathon)
cdk destroy RecoupDemoWorkloadsStack
# Verify: aws ec2 describe-instances --filters Name=tag:RecoupScenario,Values=oversized-ec2
```

---

#### `docs/api-reference.md` — **Medium update**

| Section | Change |
|---|---|
| `/api/scan/preview` response | Add `total_estimated_savings_usd`, `findings_by_service` (dict keyed by service name) |
| `/api/scan/full` response | Same additions |
| `Finding` object description | Add `evidence` (object), `scenario_tag` (string, optional), `is_demo_resource` (bool) |
| Add "Scan — Response Fields" reference table | Full field list with types for `ScanResult` and `Finding` |

**New Finding fields to document:**
```markdown
| Field | Type | Description |
|---|---|---|
| `evidence` | object | Service-specific evidence fields (CPU avg, volume type, etc.) |
| `scenario_tag` | string? | `RecoupScenario` tag value if resource is a demo workload |
| `is_demo_resource` | bool | True if resource has `RecoupDemo=true` tag |
```

---

#### `docs/iam-roles.md` — **Minor update** *(also updated in Phase 6e)*

| Section | Change |
|---|---|
| Update `RecoupReadOnlyRole` | Add EC2, EBS, RDS, Lambda, S3, Networking read permissions added in Phase 6f (Compute Optimizer, ResourceGroupsTaggingAPI) |
| Update "Key IAM Principles" | Add note: "Demo workloads are discoverable by RecoupReadOnlyRole via tag filters (RecoupDemo=true)" |

---

#### `docs/README.md` (docs index) — **Medium update**

| Change | Detail |
|---|---|
| Add three rows to Quick Links table | `demo-workloads.md`, `scanner-coverage.md`, `budget-safety.md` |
| Update Implementation Status table | Add Phase 6f row (🔴 Not Started) |
| Update Key Numbers | Scanners: 9; Demo scenarios: 8; CDK stacks: 3 (InfraStack + DemoStack + DemoWorkloadsStack); Frontend routes: 6 |

**New Quick Links entries:**
```markdown
| **[demo-workloads.md](demo-workloads.md)** | RecoupDemoWorkloadsStack: deploy, reset, destroy; 8 scenario resources |
| **[scanner-coverage.md](scanner-coverage.md)** | 9 scanners: detection logic, evidence fields, thresholds |
| **[budget-safety.md](budget-safety.md)** | Budget alerts, cost breakdown, daily stop/start strategy |
```
