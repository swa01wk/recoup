# Devpost — Project Description (paste-ready)

**Project name:** Recoup  
**Tagline:** Autonomous AWS cloud spend recovery — detect, prove, approve, recover  
**Track:** Professional Agents  
**Demo URL:** https://pdkeexzwxr.us-east-1.awsapprunner.com  
**Repository:** https://github.com/swa01wk/recoup  

---

## Elevator pitch

AWS customers lose money to unintended spend that scanners surface but teams rarely close. **Recoup** runs **real read-only AWS scanners**, turns findings into **evidence-backed recovery cases** with **deterministic confidence, safety checks, and Cedar-style policy**, and moves spend into **Recovered** only after **explicit human approval** bound to **claim hash, amount, and state version** — then **Recovery Ledger** and **SNS recovery report** on approve.

Built with **Strands Agents on Amazon Bedrock**: an **11-node graph** for SLA credit recovery (golden replay in CI) plus an **operator-focused waste-recovery pipeline** for the live demo.

> AWS provides the FinOps intelligence; Recoup closes the recovery loop.

---

## What we built

- **J-FULL operator journey (live demo):** `/scan` → Demo Scan → `/opportunities` → Start Recovery on three services → Approve / Investigate / Decline on `/opportunities/{id}` → `/recovery` ledger buckets.
- **Two complementary architectures:** (1) **Demo path** — scan → promote runs the **deterministic recovery assessment pipeline** through the graph policy gate to HITL; (2) **11-node Strands graph** — incident correlation, eligibility, claim packaging on Bedrock Nova Pro, with deterministic stubs for replay/tests (`use_strands` on `POST /api/opportunities/{id}/run`).
- **Safety:** Cedar default-deny (in-repo policy + deterministic evaluation on App Runner), evidence sanitizer, claim-bound HITL (`claim_hash`, amount, `state_version`), autonomy classes, zero unsafe external actions (ship gates).
- **AWS depth:** 9 waste scanners, STS AssumeRole, AgentCore-oriented CDK/IAM and tool registry, per-guest demo sessions on App Runner.
- **Proof:** **419** backend tests + **127** Playwright tests (16 specs, J-FULL + PSC + SEC); golden SLA replay math in CI (deterministic, not LLM-generated). Quality scorecard: run **locally** for all six gates (`curl localhost:8000/api/quality/scorecard`).

---

## Try it (judges)

1. Open https://pdkeexzwxr.us-east-1.awsapprunner.com/scan  
2. Consent → **Demo Scan**  
3. **Start Recovery** on three findings (different services)  
4. **Approve** one · **Investigate further** one · **Decline** one  
5. Open **Recovery Ledger** — buckets reflect your decisions  

No AWS credentials required. Sidebar **Reset Demo Data** clears your session only.

On approve, Recoup **records recovery in the ledger** and sends **SNS**; V1 demo emphasizes **governed closure and auditability** (estimated monthly savings from scan), not unattended remediation on every resource type.

Walkthrough: [docs/judge-demo.md](../../judge-demo.md) · Video script: [video-script.md](video-script.md)

---

## Screenshot captions (Devpost gallery)

Paste one line per image (J-FULL order):

| Screen | Caption |
|--------|---------|
| **Account Scanner** (`/scan`) | STS read-only role, consent, and Demo Scan — no stored keys. |
| **Opportunities** (`/opportunities`, empty) | Hub before scan; findings appear after Demo Scan. |
| **Opportunities** (`/opportunities`, list) | Ranked recoverable spend by service, risk, and status. |
| **Recovery case** (`/opportunities/{id}`) | Evidence, impact, confidence, and 11-step lifecycle at Approve. |
| **Recovery case** (detail) | Why Recoup believes it + safety-checked recommended action. |
| **Recovery case** (approval) | Evidence graph and claim-bound Approve / Investigate / Decline. |
| **Recovery verified** (`/opportunities/{id}`) | Bounded action verified; monthly savings recorded. |
| **Recovery Ledger** (`/recovery`) | Remaining → Pending Approval → Recovered audit trail. |

---

## What makes Recoup different

Recoup is a **closed-loop recovery operator**: real AWS scanners → evidence-backed cases → **policy gate** → **claim-bound human approval** → Recovery Ledger and SNS report — not a read-only recommendation feed.

FAQ: [README.md](../../../README.md)

---

## Built with

Amazon Bedrock · Strands Agents · Cedar (in-repo policy) · AgentCore-oriented CDK/IAM · FastAPI · Next.js · DynamoDB · SNS · STS · CloudWatch · (9 AWS service scanners)

---

## Video

_Paste public YouTube/Vimeo URL after upload (≤ 5:00, captions on). Follow [video-script.md](video-script.md)._

---

## Builder community

Paste into Devpost (one URL per line or as the form requires). Titles include **Agents for Humans**.

1. **Architecture / Strands graph:** https://builder.aws.com/content/3JKKaMeu6Cbc2HQQjmAiOosEVOH/building-recoup-agents-for-humans-and-how-we-designed-a-safe-aws-recovery-workflow-with-strands-graph  
2. **Trust (Cedar, redaction, HITL):** https://builder.aws.com/content/3JKron5aTHK1KpAaoIbxNdSd9IH/agents-for-humans-and-making-ai-financial-decisions-trustworthy-cedar-evidence-redaction-and-hitl-in-recoup  
3. **Proof (419+127 tests, scorecard):** https://builder.aws.com/content/3JKtrHzpq4RFxt6kXlNYT5uY1uJ/agents-for-humans-and-how-we-proved-recoup-works-419-backend-127-e2e-tests-and-zero-unsafe-actions
