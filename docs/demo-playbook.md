# Recoup — Demo Scenarios Playbook

**Last updated:** Sep 13, 2026  
**Primary operator journey:** [operator-journey.md](operator-journey.md) (**J-FULL** / **S5**)  
**Production UI:** https://pdkeexzwxr.us-east-1.awsapprunner.com · **API:** https://qawwrm7kzy.us-east-1.awsapprunner.com  
**Test suite:** 127 Playwright tests in 16 specs · `@smoke` + `@full` (`npx playwright test --list`)  
See [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) for per-step coverage.

---

## Overview

Recoup’s **shipped operator story** is account-scanner cost recovery: real AWS read scanners → promote finding → claim-bound HITL → Recovery Ledger (+ SNS on approve). SLA replay **adapter** and golden pytest remain for scorecard depth; **HTTP** demo routes for replay, EC2 stop, and governance (S1/S3/S7–S9) were **removed** Sep 2026 — not in the three-link sidebar.

**Product loop (J-FULL):** Scan → Start Recovery → Approve / Investigate / Decline → Ledger

**V1.1 narrative (marketing / detail UI):** Detect → Investigate → … → Record — see [operator-journey.md](operator-journey.md)

**Primary UI (sidebar):** `/opportunities` · `/scan` · `/recovery` · HITL on `/opportunities/[id]`

---

## S5 — Primary operator loop (J-FULL) — start here

**Production:** same steps on the public UI; skip reset (403 in production).

1. Sidebar **↺ Reset Demo Data** (clears **your** session only) or Playwright `POST /api/demo/session/reset`  
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
| Parallel guest sessions | PSC | Concurrent judges / isolation | ✅ (App Runner role) | ✅ `journey-demo-session-concurrency` @smoke |
| Scanner coverage | S6 | Same scan as S5; 8 tagged workloads | ✅ | ✅ J2 |
| Cross-Account Connect | S2 | Onboarding depth | ✅ | ✅ J3 |
| Evidence Sanitizer | S4 | Quality gates / replay trace | ✅ | ✅ J8 |
| SLA Credit Recovery | S1 | Engine only — pytest + scorecard | ✅ | ⛔ HTTP/J4 e2e removed |
| EC2 Idle Stop | S3 | Removed — was API-only | — | ⛔ J5 removed |
| CloudTrail No-Actor | S7 | Removed governance HTTP | — | ⛔ J10 removed |
| Missing Tags | S8 | Removed governance HTTP | — | ⛔ J11 removed |
| Cost Explorer | S9 | Removed governance HTTP | — | ⛔ J12 removed |

---

## S1 — SLA Credit Recovery (engine only — not a demo curl)

Public `/api/replay/*` and `/replay` UI were removed. SLA math is proven in CI:

```bash
cd backend && pytest tests/unit/test_replay_phase2.py tests/e2e/test_golden_replay.py -q
curl -s http://localhost:8000/api/quality/scorecard | jq '.gates[] | select(.gate_id | contains("credit"))'
```

Optional graph smoke (not J-FULL): `workflow-stages.spec.ts` WF-11 uses `POST /api/opportunities/{id}/run`.

**Verified credit:** ~$0.35 (canonical fixture)

---

## S2 — Cross-Account Connect

1. **`/scan`** → connect flow or `POST /api/scan/connect/init`
2. CloudFormation hint with `DenyAllWrites`
3. `DELETE /api/scan/accounts/{account_id}/data` for purge demo

---

## S3 — EC2 Idle Stop (removed)

`POST /api/ec2-demo/*` and EC2-focused Playwright journeys were removed in the J-FULL cleanup. Scan findings promote with **`apply_cost_recovery`** only.

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

## S7–S9 — Governance (removed HTTP)

CloudTrail / tagging / Cost Explorer **demo routes** were removed. Governance narrative for judges: scanner findings + HITL + ledger (J-FULL).

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
