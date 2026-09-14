# Devpost — Project Description (paste-ready)

**Project name:** Recoup  
**Tagline:** Autonomous AWS cloud spend recovery — detect, prove, approve, recover  
**Track:** Professional Agents  
**Demo URL:** https://pdkeexzwxr.us-east-1.awsapprunner.com  
**Repository:** https://github.com/swa01wk/recoup  

---

## Elevator pitch

AWS customers lose money to unintended spend that scanners surface but teams rarely close. **Recoup** is an autonomous cloud-spend recovery agent: it runs real read-only AWS scanners, investigates findings with a **Strands Agents** graph on Amazon Bedrock, packages **evidence-backed recovery cases**, gates actions with **Cedar policy**, and executes recovery only after **explicit human approval** — then records verified outcomes in a **Recovery Ledger** and sends an **SNS recovery report** on approve.

> AWS provides the FinOps intelligence; Recoup closes the recovery loop.

---

## What we built

- **J-FULL operator journey (live demo):** `/scan` → Demo Scan → `/opportunities` → Start Recovery on three services → Approve / Investigate / Decline on `/opportunities/{id}` → `/recovery` ledger buckets.
- **11-node recovery graph:** 3 Strands reasoning nodes + 8 deterministic nodes (policy, math, adapters).
- **Safety:** Cedar default-deny, evidence sanitizer, claim-bound HITL (`claim_hash`, amount, `state_version`), autonomy classes, zero unsafe external actions (ship gates).
- **AWS depth:** 9 waste scanners, STS AssumeRole, AgentCore integration, per-guest demo sessions on App Runner.
- **Proof:** 416 backend tests + 125 Playwright tests; golden SLA replay math in CI (deterministic, not LLM-generated).

---

## Try it (judges)

1. Open https://pdkeexzwxr.us-east-1.awsapprunner.com/scan  
2. Consent → **Demo Scan**  
3. **Start Recovery** on three findings (different services)  
4. **Approve** one · **Investigate further** one · **Decline** one  
5. Open **Recovery Ledger** — buckets reflect your decisions  

No AWS credentials required. Sidebar **Reset Demo Data** clears your session only.

Walkthrough: [docs/judge-demo.md](../../judge-demo.md) · Video script: [video-script.md](video-script.md)

---

## What makes Recoup different

Recoup is a **closed-loop recovery operator**: real AWS scanners → evidence-backed cases → **Cedar policy** → **claim-bound human approval** → Recovery Ledger and SNS report — not a read-only recommendation feed.

FAQ: [README.md](../../../README.md)

---

## Built with

Amazon Bedrock · Strands Agents · AgentCore · Cedar · FastAPI · Next.js · DynamoDB · SNS · STS · CloudWatch · (9 AWS service scanners)

---

## Video

_Paste public YouTube/Vimeo URL after upload (≤ 5:00, captions on). Follow [video-script.md](video-script.md)._

---

## Builder community

_Paste three builder.aws post URLs (titles must include "Agents for Humans"). Drafts: [builder-posts.md](builder-posts.md)._
