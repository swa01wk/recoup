# Recoup — Demo Scenarios Playbook

**Last updated:** Sep 11, 2026  
**Primary operator journey:** [operator-journey.md](operator-journey.md) (**J-FULL** / **S5**)  
**Test suite:** 279 Playwright tests in 28 specs · `@smoke` + `@full`  
See [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) for per-step coverage.

---

## Overview

Recoup’s **shipped operator story** is account-scanner cost recovery: real AWS read scanners → promote finding → claim-bound HITL → Recovery Ledger (+ SNS on approve). Optional paths (SLA replay, EC2 stop, governance APIs) remain in the repo for depth and CI but are **not** in the three-link sidebar.

**Product loop (J-FULL):** Scan → Start Recovery → Approve / Investigate / Decline → Ledger

**V1.1 narrative (marketing / detail UI):** Detect → Investigate → … → Record — see [operator-journey.md](operator-journey.md)

**Primary UI (sidebar):** `/opportunities` · `/scan` · `/recovery` · HITL on `/opportunities/[id]`

---

## S5 — Primary operator loop (J-FULL) — start here

1. Sidebar **↺ Reset Demo Data** (optional) or `POST /api/test/reset` in tests  
2. **`/scan`** → consent → **Demo Scan** → **`/opportunities`**  
3. Three findings, **three distinct services** (breadth demo)  
4. **Start Recovery** on each → **`/opportunities/{id}`**  
5. **Approve** (SNS) · **Investigate Further** · **Decline** on separate opportunities  
6. **`/recovery`** — Remaining / Pending Approval / Recovered  

**Playwright:** `npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts`

`/approvals` redirects to `/opportunities`.

---

## Savings totals (do not conflate)

| Metric | Value | Meaning |
|--------|-------|---------|
| **$87.82/mo** | Full demo scan aggregate | Sum reported by `POST /api/scan/demo` across all findings |
| **~$63.38/mo** | S6 line-item sum | Sum of the 8 tagged scenario resources in the table below (subset definition) |

Use **$87.82** when describing “what the scanner detects in one demo run.”

---

## Scenario map

| Scenario | ID | Role in demo | Live AWS | Playwright |
|----------|----|--------------|----------|------------|
| **Operator loop (J-FULL)** | **S5** | **Primary judge UI path** | ✅ | ✅ `journey-full-discovery-triage-ledger` |
| Scanner coverage | S6 | Same scan as S5; 8 tagged workloads | ✅ | ✅ J2 |
| Cross-Account Connect | S2 | Onboarding depth | ✅ | ✅ J3 |
| Evidence Sanitizer | S4 | Quality gates / replay trace | ✅ | ✅ J8 |
| SLA Credit Recovery | S1 | Optional — full graph, not in nav | ✅ | ✅ J4 |
| EC2 Idle Stop | S3 | Optional — API-only trigger | ✅ | ✅ J5 |
| CloudTrail No-Actor | S7 | Optional — governance API | ✅ | ✅ J10 |
| Missing Tags | S8 | Optional — governance API | ✅ | ✅ J11 |
| Cost Explorer | S9 | Optional — governance API | ✅ | ✅ J12 |

---

## S1 — SLA Credit Recovery (optional depth)

1. Open **`/replay`** or `POST /api/replay/api-gateway-sla`
2. Graph runs through policy → `REQUIRE_APPROVAL`
3. Open **`/opportunities/{id}`** — approve with claim-bound amount
4. **`/recovery`** — ledger updates

**API:** `POST /api/replay/run`, `GET /api/opportunities/{id}/stream` (SSE), `POST /api/approvals/opportunity/{id}/approve`

**Verified credit:** ~$0.35 (canonical SLA math)

---

## S2 — Cross-Account Connect

1. **`/scan`** → connect flow or `POST /api/scan/connect/init`
2. CloudFormation hint with `DenyAllWrites`
3. `DELETE /api/scan/accounts/{account_id}/data` for purge demo

---

## S3 — EC2 Idle Stop

1. `POST /api/ec2-demo/trigger` (API or tests)
2. **`/opportunities/{id}`** — approve `stop_demo_instance`
3. Live: `POST /api/ec2-demo/execute/{id}` after approval

Note: There is no EC2 tile on `/`; trigger via API or Playwright journeys.

---

## S6 — Eight scenario tags (demo scan)

| Tag | Service | Est. savings/mo |
|-----|---------|-----------------|
| `oversized-ec2` | EC2 | $30.37 |
| `unattached-ebs` | EBS | $2.00 |
| `gp2-migration` | EBS | $5.00 |
| `idle-eip` | EIP | $3.60 |
| `idle-rds` | RDS | $14.60 |
| `s3-no-lifecycle` | S3 | $2.30 |
| `oversized-lambda` | Lambda | $3.75 |
| `stale-snapshot` | EBS | $1.76 |

Nine scanner types: EC2 · EBS · EIP · RDS · S3 · Lambda · ELB · CloudWatch Logs · Cost Explorer

---

## S7–S9 — Governance (API-first)

| Scenario | Endpoint |
|----------|----------|
| S7 CloudTrail | `GET /api/cloudtrail-demo/check` |
| S8 Tagging | `GET /api/tagging-demo/scan` |
| S9 Cost Explorer | `GET /api/cost-demo/summary` |

Surfaced in opportunity/governance UI where wired; primary proof is API + Playwright `governance.spec.ts`.

---

## Quality scorecard (6 gates)

```bash
curl -s http://localhost:8000/api/quality/scorecard | jq '.gates'
```

Gate IDs: `golden_path_success`, `financial_math_correctness`, `evidence_recall`, `tool_selection_accuracy`, `trace_completeness`, `unsafe_actions`

---

## Pre-demo checklist

```bash
# Docker (port 8000)
docker compose up -d

# Or native backend on 8010 — set NEXT_PUBLIC_API_URL=http://localhost:8010

curl -s http://localhost:8000/health/ready | jq .
curl -s -X POST http://localhost:8000/api/scan/demo | jq '.findings | length'
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
curl -s -X POST http://localhost:8000/api/test/reset   # dev/test only
```

```bash
cd frontend && npx playwright test --grep @smoke
```

See [local-dev-and-testing.md](local-dev-and-testing.md) for full test commands.
