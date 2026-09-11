# Recoup — Judge Demo Guide

**Event:** AWS Agents for Humans (Aug 10 – Sep 14, 2026)  
**Last updated:** Sep 11, 2026 · Target video ≤5:00  
**Canonical operator flow:** [operator-journey.md](operator-journey.md) (J-FULL)

---

## Pitch (30 seconds)

AWS customers lose money to unintended spend that scanners surface but teams rarely close. Recoup runs **real read-only AWS scanners**, packages findings into claim-bound recovery opportunities, and recovers value only after **Cedar policy** and explicit **human approval** — with a **Recovery Ledger** and **SNS recovery report** on approve.

---

## Scene 1 — Problem (0:00–0:25)

**Show:** `/opportunities` (hub; `/` redirects here)  
**Say:** Connected demo account has **~$87/mo** detectable waste from nine scanner types. Nothing is recovered until an operator approves bound actions.

---

## Scene 2 — Detect (0:25–1:05)

**Show:** `/scan`  
1. Security consent → **Demo Scan** (9 parallel scanners)  
2. Redirect to **`/opportunities`** — table of findings with estimated monthly savings  
**Say:** Real AWS read APIs via STS; account IDs masked in API responses.

---

## Scene 3 — Promote & breadth (1:05–1:45)

**Show:** `/opportunities`  
1. Pick **three findings from different services** (e.g. EC2, EBS, RDS)  
2. **Start Recovery** on each → detail page with **Approval Required**  
**Say:** Promote creates `AWAITING_APPROVAL` + HITL with **claim_hash**, amount, and **state_version** — no full agent graph stream on promote (fast path for cost recovery).

---

## Scene 4 — HITL triage (1:45–3:00)

**Show:** `/opportunities/{id}` for each of the three  

| Path | Button | Outcome |
|------|--------|---------|
| **Approve** | Approve recovery | `APPROVED` → `RECOVERED` (cost recovery) · **SNS email** with recovery report |
| **Investigate** | Investigate further | `NEEDS_FOLLOWUP` · pending bucket · no SNS |
| **Decline** | Decline | `DENIED` · excluded from recovered totals · no SNS |

**Say:** Tampered claim hash or amount → **409** (show curl or mention SEC tests).

(`/approvals` redirects — HITL lives on opportunity detail only.)

---

## Scene 5 — Recovery Ledger (3:00–3:30)

**Show:** `/recovery` (+ summary on `/opportunities`)  
**Say:** **Remaining → Pending Approval → Recovered** tied to scan total and operator decisions.

---

## Scene 6 — Safety & depth (3:30–4:15)

**Show:** `curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'`  
**Say:** Six gates — zero unsafe external actions, financial math, evidence sanitizer, etc.

**Optional talking points (not in sidebar):**

- **SLA verified replay** — `POST /api/replay/api-gateway-sla` or `/replay` — full 11-node graph, ~$0.35 credit ([replay-system.md](replay-system.md))  
- **Live EC2 stop** — `POST /api/ec2-demo/trigger` — bounded `StopInstances` after approve ([demo-playbook.md](demo-playbook.md) S3)  
- **Governance APIs** — CloudTrail / tags / Cost Explorer demo endpoints (J10–J12)

---

## Scene 7 — Architecture (4:15–5:00)

Next.js + FastAPI · promote path + optional Strands re-run · 13 tools · Bedrock AgentCore · Cedar · **279** Playwright tests · **420** backend tests.

Diagram: [architecture/architecture.svg](../architecture/architecture.svg)

**Automated proof of J-FULL:**

```bash
cd frontend && npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts
```

---

## Rubric quick map

| Criterion | Proof |
|-----------|--------|
| AWS depth | 9 scanners, STS read role, DynamoDB approvals, SNS, KMS evidence |
| Autonomy | Scanner detection + optional Strands investigation on detail |
| Human oversight | Claim-bound HITL on `/opportunities/{id}`, Cedar at promote |
| Verification | Recovery Ledger, SNS report, quality scorecard |

More Q&A: [README.md](../README.md) FAQ · Full API: [api-reference.md](api-reference.md)
