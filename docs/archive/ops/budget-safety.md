# Budget Safety — Demo Cost Management

**Phase:** 6f  
**Last updated:** Sep 11, 2026  
**Target spend:** ≤ $50/month total (EC2+RDS stopped between sessions → ≤ $20/month)

---

## Pre-Deploy: Create Budget Alerts

Run this **before** deploying `RecoupDemoWorkloadsStack`:

```bash
./scripts/create_budget_alerts.sh
```

This creates three AWS Budget cost alerts:

| Budget Name | Threshold | Purpose |
|---|---|---|
| `recoup-demo-warning-25` | $25 | Early warning — review spend |
| `recoup-demo-critical-40` | $40 | Critical — stop EC2+RDS now |
| `recoup-demo-hardlimit-50` | $50 | Hard limit — demo must stay under this |

All alerts send email to `RECOUP_ALERT_EMAIL` (default: `swaroop.shivakumar@webknot.in`).

**Manual setup (AWS Console):**  
Billing → Budgets → Create budget → Cost budget → Monthly → ACTUAL > 100% → Email subscriber

---

## Resource Cost Breakdown

Monthly estimates at us-east-1 on-demand pricing:

| Resource | Type | Monthly Cost | State When Not Filming |
|---|---|---|---|
| EC2 oversized instance | `t3.medium` | ~$30 | **Stop** (saves $30) |
| RDS idle instance | `db.t3.micro` MySQL | ~$12 | **Stop** (saves $12) |
| EBS unattached volume | `gp3` 100 GiB | ~$8 | Always billed |
| EBS gp2 volume | `gp2` 50 GiB | ~$5 | Always billed |
| EIP (unassociated) | Elastic IP | ~$3.65 | Always billed |
| EBS snapshot | ~10 GiB | ~$0.50 | Always billed |
| S3 bucket | Empty | ~$0.00 | Always billed |
| Lambda (oversized) | 1024 MB | ~$0.00 | Free at demo scale |
| **Total (all running)** | | **~$59/mo** | |
| **Total (EC2+RDS stopped)** | | **~$17/mo** | **Demo target** |

> **Free tier coverage:**
> - Lambda: first 1M requests/month free — demo never exceeds this
> - S3: first 5 GiB storage free — demo bucket starts empty
> - CloudWatch custom metrics: first 10 metrics/month free

---

## Daily Cost Optimization

### Before each demo session (start resources)

```bash
# Start EC2 instance
EC2_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:RecoupScenario,Values=oversized-ec2" \
  --query "Reservations[0].Instances[0].InstanceId" --output text)
aws ec2 start-instances --instance-ids $EC2_ID

# Start RDS instance (takes ~5 minutes)
RDS_ID=$(aws rds describe-db-instances \
  --query "DBInstances[?TagList[?Key=='RecoupScenario'&&Value=='idle-rds']].DBInstanceIdentifier | [0]" \
  --output text)
aws rds start-db-instance --db-instance-identifier $RDS_ID

echo "Starting EC2 ($EC2_ID) and RDS ($RDS_ID)..."
echo "Wait 3-5 minutes for RDS to be available."
```

### After each demo session (stop resources)

```bash
# Stop EC2 instance
aws ec2 stop-instances --instance-ids $EC2_ID
echo "EC2 stopped. CloudWatch history preserved ✓"

# Stop RDS instance
aws rds stop-db-instance --db-instance-identifier $RDS_ID
echo "RDS stopped. CloudWatch history preserved ✓"
```

> **CloudWatch history is preserved when instances are stopped.**
> The Recoup scanners will still flag them using the injected metric history.

---

## Emergency Cost Controls

If you receive a $40 or $50 budget alert:

```bash
# Emergency stop all demo compute resources
EC2_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:RecoupDemo,Values=true" "Name=instance-state-name,Values=running" \
  --query "Reservations[].Instances[].InstanceId" --output text)

RDS_IDS=$(aws rds describe-db-instances \
  --query "DBInstances[?TagList[?Key=='RecoupDemo'&&Value=='true']].DBInstanceIdentifier" \
  --output text)

[ -n "$EC2_ID"  ] && aws ec2 stop-instances --instance-ids $EC2_ID
for rds_id in $RDS_IDS; do
  aws rds stop-db-instance --db-instance-identifier $rds_id
done

echo "Emergency stop complete."
```

---

## Stack Teardown (Post-Hackathon)

After the hackathon deadline (Sep 14, 2026):

```bash
cd infra/cdk

# 1. Destroy demo workloads
cdk destroy RecoupDemoWorkloadsStack

# 2. Delete stale snapshot (created via script, not CDK)
SNAP_ID=$(aws ec2 describe-snapshots \
  --filters "Name=tag:RecoupScenario,Values=stale-snapshot" \
  --query "Snapshots[0].SnapshotId" --output text)
[ "$SNAP_ID" != "None" ] && aws ec2 delete-snapshot --snapshot-id $SNAP_ID

# 3. Optionally destroy all stacks (removes all Recoup infrastructure)
# cdk destroy --all

echo "Teardown complete. Verify in AWS Console — all RecoupDemo=true resources should be gone."
```

**Verify teardown:**

```bash
# Should return empty results
aws ec2 describe-instances \
  --filters "Name=tag:RecoupDemo,Values=true" \
  --query "Reservations"

aws rds describe-db-instances \
  --query "DBInstances[?TagList[?Key=='RecoupDemo'&&Value=='true']]"
```

---

## Budget Alert Verification

```bash
# List all Recoup budgets
aws budgets describe-budgets \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --query "Budgets[?contains(BudgetName,'recoup')].{Name:BudgetName,Limit:BudgetLimit.Amount,Type:BudgetType}"
```
