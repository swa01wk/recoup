# Demo Workloads — RecoupDemoWorkloadsStack

**Phase:** 6f  
**Last updated:** Sep 13, 2026  
**CDK Stack:** `RecoupDemoWorkloadsStack` (Plane D — safe to stop/destroy for cost; does not remove App Runner or Infra)  
**Segregation:** [archive/ops/demo-vs-platform-segregation.md](archive/ops/demo-vs-platform-segregation.md)  
**Source:** `infra/cdk/lib/stacks/recoup-demo-workloads-stack.ts`  
**Playwright tests:** `scan.spec.ts` verifies all 8 scenario tags; see `USER_JOURNEY_CHECKLIST.md` J2, S6

---

## Overview

`RecoupDemoWorkloadsStack` deploys 8 controlled AWS waste scenarios for the Recoup demo.
All resources are tagged so Recoup scanners can identify them via `RecoupReadOnlyRole`
and display findings in the Account Scanner UI.

| # | Scenario Tag | Resource Type | Waste Signal | Scanner |
|---|---|---|---|---|
| 1 | `oversized-ec2` | EC2 `t3.medium` | CPU < 5% over 7 days | `EC2Scanner` |
| 2 | `unattached-ebs` | EBS `gp3` 100 GiB | Not attached to any instance | `EBSScanner` |
| 3 | `gp2-migration` | EBS `gp2` 50 GiB | Volume type is gp2 (gp3 is cheaper) | `EBSScanner` |
| 4 | `idle-eip` | Elastic IP | Allocated but not associated | `EIPScanner` |
| 5 | `idle-rds` | RDS `db.t3.micro` MySQL | CPU < 5%, connections ≈ 0 | `RDSScanner` |
| 6 | `s3-no-lifecycle` | S3 bucket | No lifecycle policy configured | `S3Scanner` |
| 7 | `oversized-lambda` | Lambda 1024 MB | < 5 invocations / 30 days | `LambdaScanner` |
| 8 | `stale-snapshot` | EBS snapshot | > 90 days old; source volume deleted | `EBSScanner` |

### Tagging Strategy

Every resource has all of these tags:

| Tag | Value |
|---|---|
| `Project` | `Recoup` |
| `Environment` | `hackathon-demo` |
| `RecoupDemo` | `true` |
| `ManagedBy` | `CDK` |
| `RecoupScenario` | `<type>` (e.g. `oversized-ec2`) |

---

## Pre-Deploy Checklist

Run these **before** `cdk deploy RecoupDemoWorkloadsStack`:

```bash
# 1. Set up budget alerts at $25 / $40 / $50 thresholds
./scripts/create_budget_alerts.sh

# 2. Opt in Compute Optimizer (takes 24–48h for first recommendations)
aws compute-optimizer update-enrollment-status --status Active

# 3. Verify your role ARN environment variable is set
echo $RECOUP_READONLY_ROLE_ARN   # should be non-empty
echo $RECOUP_EXTERNAL_ID         # should be non-empty
```

---

## Deploy

```bash
# From the infra/cdk directory
cd infra/cdk
npm install

# Deploy the demo workloads stack only
cdk deploy RecoupDemoWorkloadsStack

# Or deploy all stacks at once
cdk deploy --all
```

**Expected outputs** (copy these for later use):

- `OversizedEC2InstanceId` — needed for inject script
- `IdleRDSInstanceIdentifier` — needed for inject script
- `OversizedLambdaName` — needed for inject script
- `UnattachedEBSVolumeId` — needed for stale snapshot script
- `NoLifecycleBucketName` — reference for S3 scanner

---

## Post-Deploy: Inject Synthetic Activity

EC2, RDS, and Lambda need ≥ 7 days of CloudWatch history to appear idle.
Scenarios 2, 3, 4, 8 are detectable immediately (state-based).

```bash
# Inject near-zero metrics for scenarios 1, 5, 7
python scripts/inject_demo_activity.py

# Create scenario 8 (stale EBS snapshot)
python scripts/create_stale_snapshot.py

# Wait 15–30 minutes for CloudWatch to make metrics queryable
```

---

## Per-Scenario Resource Table

| Scenario | Lookup Command |
|---|---|
| oversized-ec2 | `aws ec2 describe-instances --filters "Name=tag:RecoupScenario,Values=oversized-ec2"` |
| unattached-ebs | `aws ec2 describe-volumes --filters "Name=tag:RecoupScenario,Values=unattached-ebs"` |
| gp2-migration | `aws ec2 describe-volumes --filters "Name=tag:RecoupScenario,Values=gp2-migration"` |
| idle-eip | `aws ec2 describe-addresses --filters "Name=tag:RecoupScenario,Values=idle-eip"` |
| idle-rds | `aws rds describe-db-instances` (look for `RecoupScenario=idle-rds` tag) |
| s3-no-lifecycle | `aws s3api list-buckets` (name contains `recoup-demo`) |
| oversized-lambda | `aws lambda list-functions` (look for `RecoupScenario=oversized-lambda`) |
| stale-snapshot | `aws ec2 describe-snapshots --filters "Name=tag:RecoupScenario,Values=stale-snapshot"` |

---

## Detection Timing

| Detection Type | Scenarios | Ready When? |
|---|---|---|
| **Immediate** (state-based) | unattached-ebs, idle-eip, gp2-migration, stale-snapshot | After `cdk deploy` |
| **Historical** (metric-based) | oversized-ec2, idle-rds, oversized-lambda | 15–30 min after `inject_demo_activity.py` |

---

## Resetting Between Demo Sessions

Stop the two most expensive resources to reduce hourly spend by ~70%:

```bash
# Get instance IDs from CDK outputs or AWS CLI
EC2_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:RecoupScenario,Values=oversized-ec2" \
  --query "Reservations[0].Instances[0].InstanceId" --output text)

RDS_ID=$(aws rds describe-db-instances \
  --query "DBInstances[?TagList[?Key=='RecoupScenario'&&Value=='idle-rds']].DBInstanceIdentifier" \
  --output text)

# Stop both (safely — CloudWatch history is preserved)
aws ec2 stop-instances --instance-ids $EC2_ID
aws rds stop-db-instance --db-instance-identifier $RDS_ID

echo "Stopped EC2 ($EC2_ID) and RDS ($RDS_ID). CloudWatch history preserved."
```

> **Finding still visible when stopped:** The EC2 scanner also flags `stopped` instances,
> and CloudWatch metric history persists. Both resources remain detectable.

---

## Destroy (Post-Hackathon)

```bash
cd infra/cdk
cdk destroy RecoupDemoWorkloadsStack

# Verify all 8 resources are removed
aws ec2 describe-instances \
  --filters "Name=tag:RecoupScenario,Values=oversized-ec2" \
  --query "Reservations"
# Should return []
```

> **Note:** The stale EBS snapshot (scenario 8) was created via script, not CDK.
> Delete it manually:
> ```bash
> SNAP_ID=$(aws ec2 describe-snapshots \
>   --filters "Name=tag:RecoupScenario,Values=stale-snapshot" \
>   --query "Snapshots[0].SnapshotId" --output text)
> aws ec2 delete-snapshot --snapshot-id $SNAP_ID
> ```

---

## Cost Breakdown

| Resource | Hourly Rate | Monthly (always-on) | Notes |
|---|---|---|---|
| EC2 `t3.medium` | ~$0.0416 | ~$30 | Stop between sessions |
| RDS `db.t3.micro` | ~$0.017 | ~$12 | Stop between sessions |
| EBS `gp3` 100 GiB | — | ~$8 | Always billed even if unattached |
| EBS `gp2` 50 GiB | — | ~$5 | Migration candidate |
| EIP (unassociated) | $0.005/hr | ~$3.65 | Fixed rate |
| Lambda (1024 MB) | — | ~$0 | Free at demo invocation scale |
| S3 bucket | — | ~$0.23/GiB | Minimal for empty bucket |
| EBS snapshot | — | ~$0.50 | 10 GiB at $0.05/GiB |
| **Total (running)** | | **~$59/mo** | |
| **Total (EC2+RDS stopped)** | | **~$17/mo** | Target when not filming |

> **Budget target:** Stay under $50/month. With stop/start strategy, typical spend is $17–$30.
