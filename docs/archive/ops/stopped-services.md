# Stopped Services — Demo Cost Savings

**Last updated:** Sep 13, 2026  
**Region:** `us-east-1`  
**Account:** `625962218034`  
**Related:** [oct-demo-ops.md](./oct-demo-ops.md) · [demo-vs-platform-segregation.md](./demo-vs-platform-segregation.md) · `./scripts/stop_demo_scanner_compute.sh`

This file tracks AWS compute resources we have **stopped** to reduce demo spend between sessions. Use the start commands below before live testing, filming, or scanner demos that need these workloads running. **Does not** stop App Runner (UI/API) or Infra tables.

> CloudWatch metric history is preserved while EC2 and RDS are stopped. Scanners can still flag idle resources using historical data, but live RDS/EC2 connectivity tests require starting them first.

---

## Stopped (as of Sep 4, 2026)

| # | Scenario | Resource | Identifier | Type | Status | Monthly savings |
|---|----------|----------|------------|------|--------|-----------------|
| 1 | `oversized-ec2` | EC2 | `i-07057bf0f44dd8ee5` | `t3.medium` | **stopped** | ~$30/mo |
| 5 | `idle-rds` | RDS MySQL | `recoupdemoworkloadsstack-idlerds3858fa40-chkjdmdlset2` | `db.t3.micro` | **stopped** *(was stopping when last checked)* | ~$12/mo |

**Combined savings while stopped:** ~$42/mo (EC2 + RDS compute only; EBS/EIP/S3/Lambda still bill).

### Stop history

| Date | Action | Command / notes |
|------|--------|-----------------|
| Sep 4, 2026 | Stopped oversized EC2 | `aws ec2 stop-instances --instance-ids i-07057bf0f44dd8ee5` |
| Sep 4, 2026 | Stopped idle RDS | `aws rds stop-db-instance --db-instance-identifier recoupdemoworkloadsstack-idlerds3858fa40-chkjdmdlset2` *(RDS was already stopping when re-run; final state: stopped)* |

---

## Still running (not stopped)

These demo resources **cannot be stopped** the same way, or were intentionally left running:

| Resource | Identifier | Type | State | Notes |
|----------|------------|------|-------|-------|
| Live EC2 demo (Phase 6 stop action) | `i-0d3389d7f950f7d3f` | `t3.micro` | **running** | `RecoupDemoStack/RecoupDemoInstance` — used for Scene 3 live `StopInstances` demo |
| Unattached EBS | `vol-03227335ad49b9c4e` | gp3 100 GiB | available | Scenario 2 — always billed |
| gp2 EBS | `vol-0908db94e8019950b` | gp2 50 GiB | available | Scenario 3 — always billed |
| Idle EIP | `eipalloc-03e6ded8240b64745` | 3.208.246.247 | unassociated | Scenario 4 — always billed |
| S3 bucket | `recoupdemoworkloadsstack-nolifecyclebucketde257f34-vqpqifdumlqu` | S3 | exists | Scenario 6 |
| Oversized Lambda | `RecoupDemoWorkloadsStack-OversizedLambda020A91F4-Wc5RLAD99Ami` | 1024 MB | active | Scenario 7 — negligible cost at demo scale |
| Stale snapshot | `snap-005ea520968192a0c` | EBS snapshot | completed | Scenario 8 |

**Estimated spend with EC2+RDS stopped:** ~$17/mo (see [budget-safety.md](./budget-safety.md)).

---

## Start before testing

Run from any shell with AWS credentials configured for the demo account.

### Start both stopped resources (recommended)

```bash
# 1. Start oversized EC2 (scenario 1)
aws ec2 start-instances --instance-ids i-07057bf0f44dd8ee5

# 2. Start idle RDS (scenario 5) — takes ~3–5 minutes to reach "available"
aws rds start-db-instance \
  --db-instance-identifier recoupdemoworkloadsstack-idlerds3858fa40-chkjdmdlset2

# 3. Wait for RDS
aws rds wait db-instance-available \
  --db-instance-identifier recoupdemoworkloadsstack-idlerds3858fa40-chkjdmdlset2

echo "EC2 and RDS are ready for testing."
```

### Start using tags (portable — works if IDs change after redeploy)

```bash
EC2_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:RecoupScenario,Values=oversized-ec2" \
  --query "Reservations[0].Instances[0].InstanceId" --output text)

RDS_ID=$(aws rds describe-db-instances \
  --query "DBInstances[?TagList[?Key=='RecoupScenario'&&Value=='idle-rds']].DBInstanceIdentifier | [0]" \
  --output text)

aws ec2 start-instances --instance-ids "$EC2_ID"
aws rds start-db-instance --db-instance-identifier "$RDS_ID"
aws rds wait db-instance-available --db-instance-identifier "$RDS_ID"
```

### Verify everything is up

```bash
aws ec2 describe-instances --instance-ids i-07057bf0f44dd8ee5 \
  --query "Reservations[0].Instances[0].State.Name" --output text
# Expected: running

aws rds describe-db-instances \
  --db-instance-identifier recoupdemoworkloadsstack-idlerds3858fa40-chkjdmdlset2 \
  --query "DBInstances[0].DBInstanceStatus" --output text
# Expected: available
```

---

## Stop again after testing

```bash
aws ec2 stop-instances --instance-ids i-07057bf0f44dd8ee5

aws rds stop-db-instance \
  --db-instance-identifier recoupdemoworkloadsstack-idlerds3858fa40-chkjdmdlset2
```

Update the **Last updated** date and status table at the top of this file when you stop or start resources.

---

## Related docs

- [demo-workloads.md](./demo-workloads.md) — full 8-scenario inventory and deploy/destroy
- [budget-safety.md](./budget-safety.md) — cost breakdown, budget alerts, emergency stop
- [local-dev-and-testing.md](../../local-dev-and-testing.md) — end-to-end live test flows
