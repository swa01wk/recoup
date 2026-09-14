# Recoup — Judge Demo Guide

**Event:** AWS Agents for Humans (Aug 10 – Sep 14, 2026)  
**Last updated:** Sep 14, 2026 · Target video ≤5:00  
**Canonical operator flow:** [operator-journey.md](operator-journey.md) (J-FULL)

## Judge narrative (honest scope)

**Live demo (J-FULL):** real AWS scan → **deterministic recovery assessment pipeline** (evidence graph, confidence, safety) through the graph **policy gate** → **claim-bound HITL** → Recovery Ledger + SNS on approve.

**Strands + Bedrock in repo:** full **11-node graph** for SLA credit recovery; golden replay and scorecard in **CI/local** (`use_strands` optional on `POST /api/opportunities/{id}/run`). Production promote defaults to **no Bedrock on promote** (`RECOVERY_LLM_ON_PROMOTE=false`) for reliable judge latency.

**AgentCore:** CDK/IAM/tool registry; Cedar rules in `infra/policy/`; App Runner path uses **deterministic policy evaluation** aligned with those rules.

**“Recover” on approve:** ledger closure + SNS report + tracked **estimated** monthly savings — not claiming unattended remediation on every resource in the public demo.

## Live demo (AWS production)

| | URL |
|--|-----|
| **UI** | https://pdkeexzwxr.us-east-1.awsapprunner.com |
| **API** | https://qawwrm7kzy.us-east-1.awsapprunner.com |

Use the same scenes below on the public UI (`/scan` → Demo Scan → `/opportunities` → …). Ops: [archive/ops/production-hosting.md](archive/ops/production-hosting.md).  
**Note:** Sidebar **Reset Demo Data** clears **your session only** (`POST /api/demo/session/reset`). `POST /api/test/reset` remains **403** in production (Playwright local only).

---

## Pitch (30 seconds)

For **FinOps and platform teams**: unintended AWS spend shows up in scans and recommendations, but recovery rarely gets **governed and recorded**. Recoup runs **real read-only AWS scanners**, builds **evidence-backed recovery cases** with deterministic safety and policy gates, and moves dollars to **Recovered** only after **claim-bound human approval** — **Recovery Ledger** and **SNS recovery report** on approve. **Strands on Bedrock** powers the full SLA agent graph in repo and CI; the live demo path prioritizes the **operator recovery pipeline** for reliability.

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
**Say:** **Start Recovery** runs the recovery assessment pipeline (evidence graph, recommendation, safety checks), then **REQUIRE_APPROVAL**. HITL binds **claim_hash**, amount, and **state_version**. Scroll the detail page — **Why Recoup believes**, safety checks, risk tier, action, rollback — that is the assessment judges should see (not a separate replay UI).

---

## Scene 4 — HITL triage (1:45–3:00)

**Show:** `/opportunities/{id}` for each of the three  

| Path | Button | Outcome |
|------|--------|---------|
| **Approve** | Approve recovery | `APPROVED` → `RECOVERED` (cost recovery) · **SNS email** with recovery report |
| **Investigate** | Investigate further | `NEEDS_FOLLOWUP` · pending bucket · no SNS |
| **Decline** | Decline | `DENIED` · excluded from recovered totals · no SNS |

**Say:** Approve means an **authorized human** accepted the bound case — we **record recovery** and **notify via SNS**. Tampered claim hash or amount → **409** (mention SEC Playwright tests).

(`/approvals` redirects — HITL lives on opportunity detail only.)

---

## Scene 5 — Recovery Ledger (3:00–3:30)

**Show:** `/recovery` (+ summary on `/opportunities`)  
**Say:** **Remaining → Pending Approval → Recovered** tied to scan total and operator decisions.

---

## Scene 6 — Safety & depth (3:30–4:15)

**Show:** Quality scorecard on **local backend only** (all six gates pass in dev/CI):

```bash
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
```

Do not rely on production scorecard for video — App Runner may not pass golden replay gates.

**Say:** Six ship gates — golden **SLA replay through the full Strands graph** (deterministic math, not LLM), financial correctness, evidence recall, tool autonomy classes, trace completeness, zero unsafe external actions. **419** pytest + **127** Playwright (J-FULL).

**Optional talking points (not in sidebar):**

- **SLA verified replay (engine only)** — deterministic ~$0.35 credit via `adapters/replay.py`; no public `/api/replay` ([archive/optional-depth/replay-system.md](archive/optional-depth/replay-system.md))  
- **Strands depth** — `docs/agent-code-architecture.md`; optional `POST /api/opportunities/{id}/run` with `use_strands` (canonical SLA scenario; not required for J-FULL)

Removed Sep 2026 (do not demo): `/api/replay/*`, EC2 demo HTTP, governance demo HTTP.

---

## Scene 7 — Architecture (4:15–5:00)

Next.js + FastAPI · **recovery pipeline on promote** (live demo) · **11-node Strands graph** (SLA / CI) · Cedar in-repo · AgentCore-oriented CDK · **127** Playwright · **419** backend tests · per-guest demo sessions (`X-Demo-Session`, PSC E2E).

Diagram: [architecture/architecture.md](../architecture/architecture.md)

**Automated proof of J-FULL:**

```bash
# Local (default)
cd frontend && npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts

# Optional — public URLs
PLAYWRIGHT_BACKEND_URL=https://qawwrm7kzy.us-east-1.awsapprunner.com \
PLAYWRIGHT_FRONTEND_URL=https://pdkeexzwxr.us-east-1.awsapprunner.com \
  npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts
```

---

## Rubric quick map

| Criterion | Proof |
|-----------|--------|
| AWS depth | 9 scanners, STS read role, DynamoDB approvals, SNS, KMS evidence |
| Strands / Bedrock | 11-node graph + `strands_agents.py`; golden replay in CI; optional `use_strands` on `/run` |
| Human oversight | Claim-bound HITL on `/opportunities/{id}`, safety + sufficiency gates on approve |
| Verification | Recovery Ledger, SNS report, local quality scorecard + Playwright J-FULL |

More Q&A: [README.md](../README.md) FAQ · Full API: [api-reference.md](api-reference.md)
