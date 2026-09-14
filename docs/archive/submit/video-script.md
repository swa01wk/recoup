# Video Script — Recoup Demo (≤ 5:00)

**Target length:** 4:40 (20s buffer)  
**Last updated:** Sep 14, 2026  
**Canonical flow:** [operator-journey.md](../../operator-journey.md) (J-FULL) · [judge-demo.md](../../judge-demo.md)

**Production tabs (no reset):**

- https://pdkeexzwxr.us-east-1.awsapprunner.com/scan  
- https://pdkeexzwxr.us-east-1.awsapprunner.com/opportunities  
- https://pdkeexzwxr.us-east-1.awsapprunner.com/recovery  

---

## Pre-recording setup

**Local:**

```bash
curl -X POST http://localhost:8000/api/test/reset

cd frontend && npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts

# Browser tabs:
#   Tab 1: http://localhost:3000/scan
#   Tab 2: http://localhost:3000/opportunities
#   Tab 3: http://localhost:3000/recovery
#   (HITL on /opportunities/{id} as you promote)
# Quality: curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
```

**Production:** use the HTTPS tabs above; quality: `curl -s https://qawwrm7kzy.us-east-1.awsapprunner.com/api/quality/scorecard | jq '.all_gates_pass'`

**Demo scan numbers (don’t mix these on camera):**

| Environment | Findings | Potential Savings (typical) |
|-------------|----------|-----------------------------|
| **Production** (STS + read role) | **8+** scenario findings | **~$87.82/mo** |
| **Local offline fallback** (no STS) | **3** (EC2, EBS, RDS) | **~$119/mo** |

J-FULL only needs **three different services** — works in both modes. Prefer **production tabs** for the hackathon video.

---

## Scene 1 — Problem (0:00–0:25)

**On screen:** `/opportunities`

> *"FinOps finds waste. Teams rarely close the loop. Recoup scans a real AWS account, packages recoverable spend, and records recovery only after explicit human approval."*

Show ledger summary: **~$87/mo** detected on production (or **~$119/mo** if recording offline local), buckets empty before scan.

---

## Scene 2 — Detect (0:25–1:05)

**On screen:** `/scan`

1. Consent → **Demo Scan**  
2. Land on **`/opportunities`** — **8+ findings** on production (**3** on offline local)  
3. Call out **three different services** (e.g. EC2, EBS, RDS)

---

## Scene 3 — Promote (1:05–1:40)

**On screen:** `/opportunities`

**Start Recovery** on three rows → detail pages → **Approval Required**

> *"Promote is fast: Cedar already set REQUIRE_APPROVAL. Claim hash binds the exact savings amount."*

---

## Scene 4 — HITL triage (1:40–3:10)

**On screen:** `/opportunities/{id}` × 3

| Opp | Action | Talking point |
|-----|--------|----------------|
| 1 | **Approve** | SNS recovery report; ledger **Recovered** |
| 2 | **Investigate further** | **Pending**; no SNS |
| 3 | **Decline** | Not counted as recovered |

Mention **409** on tampered claim (optional curl).

---

## Scene 5 — Ledger (3:10–3:40)

**On screen:** `/recovery`

Remaining / Pending / Recovered aligned with the three decisions.

---

## Scene 6 — Safety + architecture (3:40–4:40)

**On screen:** terminal — quality scorecard six gates

> *"127 Playwright tests (16 specs) including J-FULL and guest-session PSC; 419 backend tests; Cedar default deny."*

Diagram: [architecture/architecture.svg](../../../architecture/architecture.svg) in the repo root.

---

## Optional appendix (if time) — not in sidebar

- **Quality / agent depth:** `curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'` — six gates including golden replay P95 (pytest-backed)  
- **Graph re-run (API):** `POST /api/opportunities/{id}/run` on a promoted opportunity — optional SSE on detail page  

Removed Sep 2026 (do not demo): `/api/replay/*`, `/api/ec2-demo/*`, `/replay` page.

---

## Recording checklist

- [ ] Reset demo data  
- [ ] J-FULL Playwright green once  
- [ ] Full screen; sidebar visible (3 links only)  
- [ ] SNS: live topic or mention dry-run in CI
