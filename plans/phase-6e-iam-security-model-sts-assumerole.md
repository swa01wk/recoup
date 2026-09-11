# Phase 6e — IAM Security Model & STS AssumeRole Architecture

> **Historical implementation plan.** Targets below reflect mid-build intent. **Current product & metrics:** [docs/README.md](../docs/README.md) · [STATUS.md](../STATUS.md) · [docs/judge-demo.md](../docs/judge-demo.md).



**Timeline:** Sep 3–5, 2026  
**Status:** `[ ] Not Started`  
**Depends on:** Phase 6d ✅ (scanner module exists), Phase 6 ✅ (live EC2 path)  
**Source document:** `Recoup_AWS_Target_Account_Demo_Plan.docx` §§ 1–3, 7–8, 11

---

## Why This Phase Exists

The Account Scanner (Phase 6d) accepts arbitrary AWS credentials and calls services directly with a `boto3.Session`. The demo plan mandates a production-grade security boundary:

> *"Recoup should access demo resources through a dedicated IAM analysis role using STS AssumeRole — the same least-privilege, temporary-credential access pattern that will later be used for real customer AWS accounts."*

Without this phase:
- The demo has no security story beyond "trust the access key"
- The scanner cannot demonstrate the customer cross-account onboarding model judges expect
- A future cross-account deployment requires rewriting all discovery code

With this phase:
- Recoup has two roles with clean separation of concerns
- Every inventory/billing/telemetry read goes through `RecoupReadOnlyRole` via temporary STS credentials
- The same connection code works for same-account hackathon and future cross-account customers by only changing the role ARN

---

## Architecture

### Access Flow (Same Account)

```
Recoup runtime
  → assumes RecoupRuntimeRole        (application execution identity)
    → calls STS AssumeRole           (short-lived, scoped)
      → obtains RecoupReadOnlyRole   (read-only analysis permissions)
        → calls AWS APIs             (CloudWatch / Cost Explorer / CloudTrail / EC2-Describe / etc.)
```

### Access Flow (Future Customer Account)

```
Recoup control-plane account
  → RecoupRuntimeRole
    → STS AssumeRole  →  RecoupReadOnlyRole (in customer account)
        ↑ only role ARN + account ID changes; code path identical
```

---

## Goals

- [ ] `RecoupRuntimeRole` created/confirmed — application execution identity; only `sts:AssumeRole` for `RecoupReadOnlyRole`
- [ ] `RecoupReadOnlyRole` created — read-only permissions for inventory, billing, telemetry; no write actions
- [ ] Trust relationship: `RecoupRuntimeRole` can assume `RecoupReadOnlyRole` using `ExternalId`
- [ ] `CustomerConnection` model implemented — abstraction that holds role ARN + External ID + region
- [ ] All scanners (`BaseScanner` subclasses) accept a `boto3.Session` built from assumed-role credentials
- [ ] `GET /api/scan/preview` and `POST /api/scan/full` accept a `connection` object instead of raw access keys
- [ ] `/scan` frontend page updated — credential form replaced with connection form (role ARN + External ID)
- [ ] Same-account demo validated end-to-end through STS AssumeRole
- [ ] `ExternalId` field present in integration design; same-account hackathon exercises it

---

## Workstreams

### 6e.1 IAM Roles (AWS Console / CDK)

#### `RecoupRuntimeRole`

**Policy document — allow only AssumeRole for analysis role:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AssumeAnalysisRole",
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::625962218034:role/RecoupReadOnlyRole"
    }
  ]
}
```

**Trust policy** — allow the application runtime (EC2 instance profile / Lambda execution role / ECS task role) to use this role.

---

#### `RecoupReadOnlyRole`

**Purpose:** Broad analysis permissions for inventory, cost, and telemetry reads — no write actions.  
**Trust policy** — allow `RecoupRuntimeRole` to assume it with an `ExternalId` condition:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::625962218034:role/RecoupRuntimeRole"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "${RECOUP_EXTERNAL_ID}"
        }
      }
    }
  ]
}
```

**Permission policy — read-only inventory + telemetry:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EC2ReadOnly",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "ec2:GetConsoleOutput"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchReadOnly",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics",
        "cloudwatch:DescribeAlarms",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:FilterLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CostReadOnly",
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetReservationUtilization",
        "ce:GetSavingsPlanUtilization",
        "ce:GetAnomalies",
        "ce:ListCostAllocationTags",
        "cost-optimization-hub:ListRecommendations"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudTrailReadOnly",
      "Effect": "Allow",
      "Action": [
        "cloudtrail:LookupEvents",
        "cloudtrail:DescribeTrails"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EBSRDSLambdaS3ReadOnly",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:Describe*",
        "rds:Describe*",
        "lambda:List*",
        "lambda:GetFunction*",
        "s3:ListAllMyBuckets",
        "s3:GetBucketTagging",
        "s3:GetBucketLifecycleConfiguration",
        "s3:GetBucketLocation",
        "s3:GetBucketMetricsConfiguration"
      ],
      "Resource": "*"
    },
    {
      "Sid": "TaggingReadOnly",
      "Effect": "Allow",
      "Action": [
        "tag:GetResources",
        "tag:GetTagKeys",
        "tag:GetTagValues"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ComputeOptimizerReadOnly",
      "Effect": "Allow",
      "Action": [
        "compute-optimizer:GetEC2InstanceRecommendations",
        "compute-optimizer:GetEBSVolumeRecommendations",
        "compute-optimizer:GetLambdaFunctionRecommendations",
        "compute-optimizer:GetRDSInstanceRecommendations"
      ],
      "Resource": "*"
    }
  ]
}
```

> **No AdministratorAccess. No `*:*`. No write actions on any service.**

---

### 6e.2 Separate Remediation Role (for EC2 Stop)

A **third role** (`RecoupRemediationRole`) is scoped to the exact write actions permitted by Cedar policy.  
This keeps the analysis role completely read-only even when a stop is approved.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowStopOnly",
      "Effect": "Allow",
      "Action": "ec2:StopInstances",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "ec2:ResourceTag/RecoupDemo": "true"
        }
      }
    },
    {
      "Sid": "ExplicitlyDenyTerminate",
      "Effect": "Deny",
      "Action": "ec2:TerminateInstances",
      "Resource": "*"
    }
  ]
}
```

The `stop_demo_instance` tool uses `RecoupRemediationRole` credentials — never `RecoupReadOnlyRole`.

---

### 6e.3 `CustomerConnection` Model

**Location:** `backend/src/recoup/models/connection.py`

```python
from pydantic import BaseModel, Field
from typing import Optional
import boto3
import botocore

class CustomerConnection(BaseModel):
    """
    Abstraction for a Recoup–AWS integration point.
    Same-account: role_arn points to RecoupReadOnlyRole in hackathon account.
    Cross-account: role_arn points to RecoupReadOnlyRole in the customer account.
    Only this object needs to change between the two modes — no code rewrite.
    """
    role_arn: str = Field(..., description="ARN of the analysis role Recoup should assume")
    external_id: str = Field(..., description="External ID used in the trust policy condition")
    region: str = Field(default="us-east-1")
    session_name: str = Field(default="recoup-analysis-session")
    account_id: Optional[str] = None  # populated after STS assume

    def build_session(self) -> boto3.Session:
        """Assume the analysis role and return a scoped boto3.Session."""
        sts = boto3.client("sts")
        response = sts.assume_role(
            RoleArn=self.role_arn,
            RoleSessionName=self.session_name,
            ExternalId=self.external_id,
            DurationSeconds=3600,
        )
        creds = response["Credentials"]
        self.account_id = response["AssumedRoleUser"]["Arn"].split(":")[4]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=self.region,
        )
```

---

### 6e.4 Scanner Layer — Accept `CustomerConnection`

All scanner routes and `BaseScanner` already accept a `boto3.Session`. The only change needed is the **API endpoint contract**: instead of accepting raw `access_key_id` / `secret_access_key`, the `/api/scan/*` routes accept a `CustomerConnection` object and call `.build_session()` internally.

**Before (Phase 6d):**
```python
class ScanRequest(BaseModel):
    access_key_id: str
    secret_access_key: str
    region: str = "us-east-1"
```

**After (Phase 6e):**
```python
class ScanRequest(BaseModel):
    role_arn: str
    external_id: str
    region: str = "us-east-1"
```

**Route change** (`backend/src/recoup/api/routes/scan.py`):
```python
@router.post("/scan/full")
async def scan_full(req: ScanRequest):
    conn = CustomerConnection(
        role_arn=req.role_arn,
        external_id=req.external_id,
        region=req.region,
    )
    session = conn.build_session()   # STS AssumeRole happens here
    return await _run_scan(session, ALL_SCANNERS)
```

**Security improvement:** No long-lived access key ever touches the API layer. The assumed role credentials expire within the hour.

---

### 6e.5 Frontend — Connection Form & STS Status Panel

**File:** `frontend/src/app/scan/page.tsx`

#### Form Fields

Replace the raw access key form with a connection form:

| Field | Old | New |
|---|---|---|
| AWS Access Key ID | ✅ text input | ❌ removed |
| AWS Secret Access Key | ✅ password input | ❌ removed |
| Region | ✅ text input | ✅ kept |
| Role ARN | ❌ | ✅ text input |
| External ID | ❌ | ✅ text input (masked/password) |

Add a helper text: *"Recoup uses STS AssumeRole — no long-lived credentials are stored or transmitted."*

For the hackathon demo, pre-fill Role ARN from `NEXT_PUBLIC_RECOUP_READONLY_ROLE_ARN` env var.

#### STS Assume Status Badge

After a successful scan, show a green **"● Connected via STS AssumeRole"** badge in the scan header:

```tsx
// frontend/src/components/ui/badge.tsx — new variant
export function STSConnectedBadge({ accountId, roleArn }: { accountId?: string; roleArn: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-900/40 border border-emerald-500/30 px-3 py-1 text-xs font-medium text-emerald-300">
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
      STS AssumeRole ✓ {accountId ? `· Account ${accountId}` : ''}
    </span>
  );
}
```

Render it in the scan results header next to the scan count, pulling `assumed_role_account_id` from the API response.

#### API Response Change

Update `ScanResult` TypeScript type in `frontend/src/lib/api.ts`:

```typescript
// Add to ScanResult interface:
export interface ScanResult {
  findings: Finding[];
  errors: string[];
  duration_ms: number;
  assumed_role_arn?: string;      // new — returned by backend after STS assume
  assumed_role_account_id?: string; // new
  session_name?: string;          // new — e.g. "recoup-analysis-session"
}

// Replace ScanRequest (remove old access-key fields):
export interface ScanRequest {
  role_arn: string;
  external_id: string;
  region?: string;
}
```

#### Security Callout Panel

Below the form, add a static info panel explaining the security model:

```tsx
<div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 text-sm text-slate-400 space-y-1">
  <p className="font-medium text-slate-300">How Recoup connects to your AWS account</p>
  <ul className="list-disc pl-4 space-y-1">
    <li>Recoup calls <code>sts:AssumeRole</code> using your Role ARN + External ID</li>
    <li>Temporary credentials expire within 1 hour — never stored</li>
    <li>The analysis role has read-only permissions — no writes, no deletions</li>
    <li>Remediation actions use a <em>separate</em> scoped role, approved by you first</li>
  </ul>
</div>
```

#### Error Handling

When STS AssumeRole fails (wrong ARN, missing trust policy, wrong External ID), show a red error panel:

```tsx
<div className="rounded-lg border border-red-500/30 bg-red-900/20 p-4 text-sm text-red-300">
  <p className="font-medium">Could not assume role</p>
  <p className="text-red-400 font-mono text-xs mt-1">{error.detail}</p>
  <p className="mt-2 text-slate-400">Check that RecoupReadOnlyRole trusts this application and the External ID matches.</p>
</div>
```

#### New Env Var (Frontend)

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_RECOUP_READONLY_ROLE_ARN` | Pre-fills Role ARN field for demo |

---

### 6e.6 Env Vars

| Variable | Purpose | New? |
|---|---|---|
| `RECOUP_READONLY_ROLE_ARN` | ARN of `RecoupReadOnlyRole` | ✅ New |
| `RECOUP_EXTERNAL_ID` | External ID for the STS trust condition | ✅ New |
| `RECOUP_REMEDIATION_ROLE_ARN` | ARN of `RecoupRemediationRole` (EC2 stop) | ✅ New |
| `RECOUP_RUNTIME_ROLE_ARN` | ARN of `RecoupRuntimeRole` (informational) | ✅ New |

Add all four to `.env.example`.

---

### 6e.7 Demo Validation Steps (Section 11 of source document)

After IAM setup, validate in order:

1. ✅ Confirm `RecoupRuntimeRole` is the application execution identity
2. ✅ Confirm trust relationship: `RecoupRuntimeRole` → `RecoupReadOnlyRole` with `ExternalId`
3. Run `aws sts assume-role --role-arn $RECOUP_READONLY_ROLE_ARN --role-session-name test --external-id $RECOUP_EXTERNAL_ID` — should succeed
4. Run `POST /api/scan/preview` with connection form values — should return findings from the demo account
5. Confirm no API call in scanner logs uses a long-lived access key
6. Confirm `RecoupReadOnlyRole` cannot call `ec2:StopInstances` (negative test)
7. Confirm `RecoupRemediationRole` can call `ec2:StopInstances` for `RecoupDemo=true` instances only

---

## Files to Create / Modify

### Backend

| File | Change |
|---|---|
| `backend/src/recoup/models/connection.py` | New — `CustomerConnection` model with `build_session()` |
| `backend/src/recoup/api/routes/scan.py` | Replace raw creds with `CustomerConnection`; add `role_arn` + `external_id` params; return `assumed_role_arn`, `assumed_role_account_id` in response |
| `backend/src/recoup/config.py` | Add `recoup_readonly_role_arn`, `recoup_external_id`, `recoup_remediation_role_arn`, `recoup_runtime_role_arn` |
| `backend/src/recoup/tools/ec2_tools.py` | Use `RecoupRemediationRole` credentials for `stop_instances`; never `RecoupReadOnlyRole` |
| `infra/cdk/stacks/iam_stack.py` | New (or update existing) — CDK definitions for all three roles + trust policies |

### Frontend

| File | Change |
|---|---|
| `frontend/src/app/scan/page.tsx` | Replace access-key form with Role ARN + External ID form; add `STSConnectedBadge`; add STS error panel |
| `frontend/src/lib/api.ts` | Update `ScanRequest` (remove access keys, add `role_arn` + `external_id`); add `assumed_role_arn` + `assumed_role_account_id` to `ScanResult` |
| `frontend/src/components/ui/badge.tsx` | New `STSConnectedBadge` component with animated pulse indicator |

### Config / Docs

| File | Change |
|---|---|
| `.env.example` | Add four new backend role ARN / External ID variables |
| `frontend/.env.example` (or `.env.local`) | Add `NEXT_PUBLIC_RECOUP_READONLY_ROLE_ARN` for form pre-fill |
| `docs/iam-architecture.md` | New — documents role hierarchy, trust policies, External ID design |

---

## Demo Story Integration (Source Document §12)

The scan page demo sequence becomes:

1. Show the scan page with Role ARN pre-filled (`RecoupReadOnlyRole` ARN)
2. Click "Run Scan" — backend calls `STS AssumeRole` and receives temp credentials
3. Scanners discover 6+ findings across EC2, EBS, RDS, Lambda, S3, networking
4. Expand one finding — show evidence: CloudWatch CPU, Cost Explorer data, Compute Optimizer recommendation
5. Point out: *"Recoup's analysis role cannot modify infrastructure. Remediation requires a separate role and human approval."*
6. Explain: *"In production, RecoupReadOnlyRole lives in the customer's account and trusts Recoup's account. Onboarding is changing the role ARN in this form — no code changes."*

---

## Definition of Done

| Check | Criteria |
|---|---|
| `RecoupRuntimeRole` | Application identity confirmed; only `sts:AssumeRole` permission |
| `RecoupReadOnlyRole` | Read-only perms only; verified cannot call StopInstances |
| `RecoupRemediationRole` | `ec2:StopInstances` on `RecoupDemo=true` only; `TerminateInstances` explicitly denied |
| Trust relationship | STS AssumeRole succeeds with correct ExternalId; fails without it |
| `CustomerConnection` | `build_session()` returns a scoped session; credentials expire ≤ 1h |
| Scanner API | `/api/scan/preview` accepts `role_arn` + `external_id`; no raw access keys |
| Frontend | Scan form shows Role ARN + External ID fields; no access-key inputs |
| Negative test | `RecoupReadOnlyRole` call to `ec2:StopInstances` → `AccessDenied` |
| Demo script | End-to-end: form → STS assume → scan → findings displayed |
| `.env.example` | Four new env vars documented with descriptions |

---

---

## Documentation Updates (Phase 6e)

Complete all doc updates as part of this phase — before marking 6e Done.

### New Docs to Create

#### `docs/iam-architecture.md` *(new)*
Full reference for the three-role model introduced in this phase:

- Role hierarchy diagram: `RecoupRuntimeRole → STS AssumeRole → RecoupReadOnlyRole`
- Separate `RecoupRemediationRole` for write actions
- Trust policy JSON for each role
- Permission policy breakdown per role (what each can and cannot do)
- ExternalId design: why it exists, how it is set, how to rotate it
- Temporary credential lifecycle (1-hour expiry, no storage)
- How to verify each trust relationship with AWS CLI commands
- Security invariants: "Analysis role can never stop an instance"; "Remediation role can never read billing data"

#### `docs/cross-account-onboarding.md` *(new)*
Step-by-step guide for connecting any AWS account to Recoup:

- Customer-side IAM role creation (CloudFormation/CDK template snippet)
- Trust policy template with `sts:ExternalId` condition
- How to obtain and use the External ID from Recoup
- Minimum required permissions checklist (matches `RecoupReadOnlyRole` policy)
- How to test the connection: `aws sts assume-role` validation command
- Revoking access: delete/modify the trust policy — Recoup loses access immediately
- Same-account (hackathon) vs. cross-account (production): the only difference is the role ARN account ID

---

### Existing Docs to Update

#### `docs/iam-roles.md` — **Major update**

| Section | Change |
|---|---|
| Add `RecoupReadOnlyRole` | New role introduced in 6e — broad read-only analysis permissions (inventory, cost, telemetry); cannot write or stop any resource |
| Add `RecoupRemediationRole` | New role introduced in 6e — `ec2:StopInstances` on `RecoupDemo=true` only; `TerminateInstances` explicitly denied |
| Update `RecoupRuntimeRole` | Add `sts:AssumeRole` for `RecoupReadOnlyRole` and `RecoupRemediationRole` to its permissions table |
| Add ExternalId section | Explain External ID, where it is stored, what happens if it is wrong |
| Update "Key IAM Principles" | Add principle 6: "Temporary credentials via STS — no long-lived analysis keys" |
| Update role count | Header now says "5 roles" (was 4) |
| Update verification commands | Add `aws sts assume-role` test commands for new roles |

**Specific additions to write:**
```markdown
## RecoupReadOnlyRole (Phase 6e)
**Purpose:** Broad read-only analysis access assumed via STS AssumeRole ...
**Trust principal:** RecoupRuntimeRole (same account; ExternalId required)
**What it can do:** EC2 Describe*, CloudWatch Get*, Cost Explorer Get*, CloudTrail Lookup*, ...
**What it cannot do:** No ec2:StopInstances, no s3:PutObject, no any write action

## RecoupRemediationRole (Phase 6e)
**Purpose:** Narrowly scoped write role for approved remediation actions only ...
**What it can do:** ec2:StopInstances where RecoupDemo=true tag present
**What it cannot do:** ec2:TerminateInstances (explicitly denied); no read permissions
```

---

#### `docs/architecture-overview.md` — **Medium update**

| Section | Change |
|---|---|
| "High-Level Architecture" diagram | Add STS AssumeRole arrow from Recoup backend to `RecoupReadOnlyRole`; show `RecoupRemediationRole` as separate path for EC2 stop |
| Add "IAM Security Model" section | Explain the three-tier role separation; reference `docs/iam-architecture.md` |
| Update "AWS Services" table | Add `STS` row (AssumeRole for analysis and remediation); add `RecoupReadOnlyRole` and `RecoupRemediationRole` to the IAM section |
| Update "Security Properties" table | Add row: "Analysis ≠ Remediation — read role has no write permissions; separate role required for all EC2 actions" |
| Update version/date in header | `Version: Phases 0–6e complete` |

---

#### `docs/api-reference.md` — **Medium update**

| Section | Change |
|---|---|
| `POST /api/scan/full` request body | Replace `access_key_id` + `secret_access_key` with `role_arn: str` + `external_id: str` |
| `POST /api/scan/preview` request body | Same as above |
| Both scan response bodies | Add `assumed_role_arn: str`, `assumed_role_account_id: str`, `session_name: str` |
| Add error examples | `400 Bad Request` when STS AssumeRole fails (wrong ARN or External ID) |

```markdown
### `POST /api/scan/preview`
...
**Request body (updated Phase 6e):**
| Field | Type | Required | Description |
|---|---|---|---|
| `role_arn` | string | ✅ | ARN of RecoupReadOnlyRole to assume via STS |
| `external_id` | string | ✅ | External ID matching the trust policy condition |
| `region` | string | ❌ | AWS region (default: `us-east-1`) |

**Response additions:**
| Field | Type | Description |
|---|---|---|
| `assumed_role_arn` | string | Full ARN of the assumed role session |
| `assumed_role_account_id` | string | AWS account ID the role was assumed in |
```

---

#### `docs/README.md` (docs index) — **Minor update**

| Change | Detail |
|---|---|
| Add two rows to the Quick Links table | `iam-architecture.md` and `cross-account-onboarding.md` |
| Update Implementation Status table | Add Phase 6d row (✅ Complete), Phase 6e row (🔴 Not Started) |
| Update Key Numbers | IAM roles: 4 → 6; Frontend routes: 5 → 6 (add `/scan`) |
