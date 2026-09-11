# Scanner Coverage Reference

**Phase:** 6f  
**Last updated:** Sep 11, 2026  
**Module:** `backend/src/recoup/scanners/`  
**Playwright tests:** `scan.spec.ts` (8 tests) · `journey-operator-primary.spec.ts` (9 tests)

---

## Overview

Recoup ships 9 account scanners. Each scanner implements `BaseScanner` and returns
a list of `Finding` objects. The full scan runs all 9; the preview runs only
`CostExplorerScanner` and `EC2Scanner` for speed.

```
BaseScanner.scan(session, region) → (list[Finding], list[str])
  └─ _scan(session, region)  ← override in each scanner
```

Errors are caught per-scanner; a failure in one scanner never blocks others.

---

## Scanner Reference

### `EC2Scanner`

| Field | Value |
|---|---|
| **Module** | `ec2_scanner.py` |
| **Service name** | `EC2` |
| **Finding types** | `IDLE_INSTANCE`, `STOPPED_INSTANCE` (when set) |

**Detection logic:**
- Flags running instances with 7-day average CPU < 5% (via `cloudwatch:GetMetricStatistics`)
- Flags stopped instances (no CPU check needed — still incur EBS costs)

**Key evidence fields:**

| Field | Source |
|---|---|
| `instance_type` | `ec2:DescribeInstances` |
| `state` | `ec2:DescribeInstances` |
| `cpu_utilization_7d_avg` | `cloudwatch:GetMetricStatistics` (AWS/EC2/CPUUtilization) |

**Thresholds:** CPU < 5% over 7 days  
**Demo scenario:** `oversized-ec2` (t3.medium, near-zero CPU via synthetic injection)

---

### `EBSScanner`

| Field | Value |
|---|---|
| **Module** | `ebs_scanner.py` |
| **Service name** | `EBS` |
| **Finding types** | `UNATTACHED_VOLUME`, `GP2_MIGRATION_CANDIDATE`, `STALE_SNAPSHOT` |

**Detection logic:**

1. **UNATTACHED_VOLUME** — volumes with `status=available` (not attached to any instance)  
   Savings = size_GiB × $0.10/GiB/month

2. **GP2_MIGRATION_CANDIDATE** — attached volumes with `volume_type=gp2`  
   gp3 delivers equal/better performance at ~20% lower cost  
   Savings = size_GiB × ($0.10 − $0.08)/GiB/month

3. **STALE_SNAPSHOT** — snapshots older than 90 days whose source volume no longer exists  
   Savings = size_GiB × $0.05/GiB/month

**Key evidence fields:**

| Field | Source |
|---|---|
| `volume_type` | `ec2:DescribeVolumes` |
| `size_gib` | `ec2:DescribeVolumes` |
| `attachment_state` | `ec2:DescribeVolumes` |
| `age_days` | Computed from `StartTime` (snapshots only) |
| `source_volume_state` | `ec2:DescribeVolumes` on `VolumeId` (snapshots only) |

**Demo scenarios:** `unattached-ebs` (scenario 2), `gp2-migration` (scenario 3), `stale-snapshot` (scenario 8)

---

### `EIPScanner`

| Field | Value |
|---|---|
| **Module** | `eip_scanner.py` |
| **Service name** | `EIP` |
| **Finding types** | `IDLE_EIP` |

**Detection logic:** EIPs with no `AssociationId` (not associated with any running resource)  
Fixed cost: $3.65/month per unused EIP

**Demo scenario:** `idle-eip` (scenario 4)

---

### `RDSScanner`

| Field | Value |
|---|---|
| **Module** | `rds_scanner.py` |
| **Service name** | `RDS` |
| **Finding types** | `IDLE_RDS` |

**Detection logic:**
- 7-day average `DatabaseConnections < 1.0` via CloudWatch
- Also flags single-AZ production DBs (no estimated savings, severity: medium)

**Key evidence fields:**

| Field | Source |
|---|---|
| `instance_class` | `rds:DescribeDBInstances` |
| `engine` | `rds:DescribeDBInstances` |
| `avg_connections_7d` | `cloudwatch:GetMetricStatistics` (AWS/RDS/DatabaseConnections) |
| `multi_az` | `rds:DescribeDBInstances` |

**Demo scenario:** `idle-rds` (scenario 5)

---

### `S3Scanner`

| Field | Value |
|---|---|
| **Module** | `s3_scanner.py` |
| **Service name** | `S3` |
| **Finding types** | `NO_LIFECYCLE_POLICY` |

**Detection logic:** Buckets without any lifecycle configuration  
Buckets without lifecycle policies keep all objects in STANDARD storage indefinitely

**Demo scenario:** `s3-no-lifecycle` (scenario 6)

---

### `LambdaScanner`

| Field | Value |
|---|---|
| **Module** | `lambda_scanner.py` |
| **Service name** | `Lambda` |
| **Finding types** | `OVERSIZED_LAMBDA` |

**Detection logic:**
- Functions with `MemorySize >= 512 MB` AND average duration < 10ms
- Recommendation: reduce to `max(128, memory_mb // 4)`

**Demo scenario:** `oversized-lambda` (scenario 7)

---

### `LBScanner`

| Field | Value |
|---|---|
| **Module** | `lb_scanner.py` |
| **Service name** | `ELB` |
| **Finding types** | _(optional — many findings omit `finding_type`)_ |

**Detection logic:** Idle load balancers via CloudWatch (ALB `RequestCount`; NLB may use `ProcessedBytes`)

---

### `CWLogsScanner`

| Field | Value |
|---|---|
| **Module** | `cwlogs_scanner.py` |
| **Service name** | `CloudWatch Logs` |
| **Finding types** | _(often unset)_ |

**Detection logic:** Log groups with `retention_in_days = None` (never expire)

---

### `CostExplorerScanner`

| Field | Value |
|---|---|
| **Module** | `cost_explorer_scanner.py` |
| **Service name** | `Cost Explorer` |
| **Finding types** | `TOP_SPEND_SERVICE` |

**Detection logic:** Top 5 services by monthly spend via `ce:GetCostAndUsage`

---

## Detection Strategy: Immediate vs Historical

| Type | Scanners | Requires CloudWatch History? |
|---|---|---|
| **Immediate** (state-based) | EBSScanner, EIPScanner, S3Scanner, CWLogsScanner | ❌ No |
| **Historical** (metric-based) | EC2Scanner, RDSScanner, LambdaScanner, LBScanner | ✅ Yes — 7+ days |
| **Billing-based** | CostExplorerScanner | ✅ Yes — 1+ day of spend |

For new accounts or freshly-deployed demo resources, run `scripts/inject_demo_activity.py`
to seed 7 days of near-zero CloudWatch metrics before scanning.

---

## How to Add a New Scanner

1. Create `backend/src/recoup/scanners/my_scanner.py`:

```python
from .base import BaseScanner
from .finding import Finding

class MyScanner(BaseScanner):
    service_name = "MyService"

    def _scan(self, session, region):
        findings = []
        client = session.client("my-service", region_name=region)
        # ... detection logic ...
        findings.append(Finding(
            service="MyService",
            resource_id="...",
            resource_type="AWS::MyService::Resource",
            finding_type="MY_FINDING",
            issue="...",
            estimated_monthly_savings_usd=10.0,
            recommendation="...",
            severity="medium",
            region=region,
            evidence={"key": "value"},
        ))
        return findings
```

2. Add to `_ALL_SCANNERS` in `backend/src/recoup/api/routes/scan.py`

3. Wire labels in the scan UI components as needed (see `frontend/src/app/scan/`)

4. Update this doc with the new scanner entry

---

## Known Limitations

- **New account / freshly deployed:** EC2, RDS, Lambda scanners return no findings until
  7+ days of metric history exist. Use `scripts/inject_demo_activity.py` to seed metrics.
- **Stale snapshots:** The 90-day threshold means scenario 8 requires either real age or
  lowering `RECOUP_STALE_SNAPSHOT_DAYS` env var in the scanner.
- **Cost Explorer:** Requires at least 24h of billing data; returns empty on brand-new accounts.
- **Multi-region:** Pass `regions` array in `ScanRequest` to scan additional regions.
  Each scanner runs per-region independently.

---

## Playwright Test Coverage

The following Playwright tests verify scanner behavior end-to-end:

| Test | File | What it verifies |
|------|------|-----------------|
| All 8 `scenario_tags` present | `scan.spec.ts` | Every scanner produces a tagged finding |
| Total savings > $60/mo | `scan.spec.ts` | Combined scanner output meets minimum |
| `oversized-ec2` has `service=EC2`, `resource_id=i-*` | `scan.spec.ts` | EC2 scanner field shape |
| Each tag → separate opportunity | `scan.spec.ts` | Promote creates unique records per resource |
| Finding fields (resource_id, severity, savings) | `scan.spec.ts` | All required fields present |
| Scan audit record written | `journey-operator-primary.spec.ts` | Audit trail after demo scan |
| `account_id` masked | `journey-operator-primary.spec.ts` | No raw 12-digit IDs |
| Idempotent scan (last) | `scan.spec.ts` | `GET /api/scan/last` returns cached data |

Run with:
```bash
cd frontend && npx playwright test scan.spec.ts
```
