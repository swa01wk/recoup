# AWS Builder Center — article drafts

Create each article at [AWS Builder Center → Create an article](https://builder.aws). Copy fields below in order: **Title** → **Description** → **Body** → optional **Cover image** → **Tags** (5 max). Use **Preview**, then **Publish**. Drafts auto-save.

Titles **must** include **Agents for Humans** (hackathon requirement).

**Status (Sep 15, 2026):** All **three** articles published — URLs in [submission-record.md](submission-record.md) and [devpost-project-description.md](devpost-project-description.md).

**Cover image (all posts):** 1200×675 px recommended; jpg/jpeg/png/webp; max 2 MB. **Article 1:** [published — keep as-is](https://builder.aws.com/content/3JKKaMeu6Cbc2HQQjmAiOosEVOH/building-recoup-agents-for-humans-and-how-we-designed-a-safe-aws-recovery-workflow-with-strands-graph) (cover: [assets/builder-cover-recoup-stack.png](assets/builder-cover-recoup-stack.png)). **Articles 2–3:** copy below; covers [assets/builder-cover-recoup-trust.png](assets/builder-cover-recoup-trust.png) (Art. 2) or scorecard terminal (Art. 3). Regenerate: `node docs/archive/submit/assets/export-builder-cover.mjs`.

**Publish strategy:** Article **1** stays unchanged. Articles **2** and **3** carry the **J-FULL live-demo scope** and **re-runnable proof** so judges (Devpost + video + repo) see one consistent story without a fourth post.

---

## Article 1 — Strands graph & safe recovery workflow

### Title `(100/255)`

Building Recoup: Agents for Humans — How We Designed a Safe AWS Recovery Workflow with Strands Graph

### Description `(~280/512)` — update count in Builder UI

FinOps tools excel at finding waste; teams still struggle to close recovery safely. Recoup pairs a live operator recovery pipeline with an 11-node Strands graph on Bedrock for SLA paths—Cedar policy and human approval gate every sensitive action, not LLM execution.

### Body

FinOps tools excel at *finding* waste; teams still struggle to *close* recovery safely. For the **Agents for Humans** hackathon we built **Recoup** — a cloud-spend **recovery operator** with two deliberate layers:

1. **Live demo (J-FULL)** — real AWS scanners → **deterministic recovery assessment pipeline** (evidence graph, confidence, safety checks) → **policy requires approval** → claim-bound HITL → Recovery Ledger + SNS.  
2. **Agent depth in repo** — an **11-node Strands graph** on **Amazon Bedrock (Nova Pro)** for **SLA credit recovery**, with deterministic stubs for golden replay in CI.

We keep destructive power behind **Cedar policy** (in-repo rules + deterministic evaluation on App Runner) and **human approval** — not “LLM executes.”

### The SLA Strands graph (repo + CI)

Recoup’s **11-node** workflow is deliberately split:

- **5 agent nodes** — incident correlation, evidence collection, eligibility reasoning, claim packaging, case monitoring (Strands where wired; stubs for replay)  
- **6 deterministic nodes** — normalization, SLA math, sanitization, Cedar policy gate, submission adapter, monitoring hooks  

The LLM proposes on agent nodes; **Cedar decides**; humans approve at the boundary.

Flow (SLA path, simplified):

`normalize_event → incident_correlation [Strands] → evidence_collection → eligibility [Strands] → claim_package [Strands] → risk_policy_gate [Cedar] → HITL → submission_adapter → case_monitor`

**Scan / waste path:** promote runs the **optimization recovery pipeline** inside the graph through `risk_policy_gate` (see `docs/operator-journey.md`) — reliable for judges without Bedrock latency on every click. Optional Bedrock on promote: `RECOVERY_LLM_ON_PROMOTE`.

See the canonical diagrams (Mermaid) in our repo: [architecture/architecture.md](https://github.com/swa01wk/recoup/blob/main/architecture/architecture.md) — stack, J-FULL lifecycle, and agent graph.

### Why not “LLM executes”?

Financial remediation is high stakes. We enforce:

- Tool allowlists and autonomy classes (GREEN / YELLOW / RED / BLACK)  
- Cedar **default deny** on writes  
- Explicit `REQUIRE_APPROVAL` for sensitive actions  
- Claim binding: `claim_hash`, amount, and `state_version` must match on approve (tamper → HTTP 409)

Code pointers:

- Graph nodes: `backend/src/recoup/graph/nodes.py`  
- Cedar policy: `infra/policy/recoup-policy.cedar`  

### Try the live demo

No AWS keys required: https://pdkeexzwxr.us-east-1.awsapprunner.com/scan → Demo Scan → **Start Recovery** on three services → approve / investigate / decline on opportunity detail → Recovery Ledger. Guest sessions: `X-Demo-Session` + sidebar **Reset Demo Data**.

Repo: https://github.com/swa01wk/recoup

### Tags `(max 5)`

- Amazon Bedrock  
- Generative AI  
- Agents for Humans  
- Cloud Financial Management  
- AWS App Runner  

### Cover image

Upload **`docs/archive/submit/assets/builder-cover-recoup-stack.png`** (1200×675, under 2 MB) — polished stack diagram with title; do not use a raw GitHub Mermaid screenshot.

---

## Article 2 — Trust: Cedar, redaction, HITL

### Title `(108/255)`

Agents for Humans — Making AI Financial Decisions Trustworthy: Cedar, Evidence Redaction, and HITL in Recoup

### Description `(~318/512)` — verify count in Builder UI

When an agent touches cloud spend, trust is architecture not marketing. Building Recoup: Agents for Humans and How We Designed a Safe AWS Recovery Workflow with Strands Graph covers our Strands SLA graph; this post is what the live hackathon demo enforces: sanitizer, Cedar (not LLM policy), and claim-bound HITL on Start Recovery.

### Body

When an agent touches cloud spend, “trust” is not a vibe — it’s architecture. Recoup treats **evidence**, **policy**, and **approval** as first-class gates before any recovery action.

[Building Recoup: Agents for Humans and How We Designed a Safe AWS Recovery Workflow with Strands Graph](https://builder.aws.com/content/3JKKaMeu6Cbc2HQQjmAiOosEVOH/building-recoup-agents-for-humans-and-how-we-designed-a-safe-aws-recovery-workflow-with-strands-graph) describes our **11-node Strands graph** on Bedrock for the **SLA credit path** in repo and CI. **This post** covers what the **public judge demo (J-FULL)** actually enforces when an operator clicks **Start Recovery** and reaches the approval card — aligned with [operator-journey.md](https://github.com/swa01wk/recoup/blob/main/docs/operator-journey.md) and [judge-demo.md](https://github.com/swa01wk/recoup/blob/main/docs/judge-demo.md).

### Live demo path (J-FULL)

On **Start Recovery**, Recoup runs a **deterministic recovery assessment pipeline** (evidence graph, confidence, safety checks) through the same **policy semantics** as production Cedar — then **`REQUIRE_APPROVAL`** before ledger or SNS. That path prioritizes **reliable latency** on App Runner (`RECOVERY_LLM_ON_PROMOTE=false` by default); optional Bedrock on promote exists for depth demos. **Approve** closes the case in the **Recovery Ledger** with **claim-bound** fields — not unattended remediation on every resource in the public UI.

### Evidence sanitizer

Before model context sees customer data, we run an **8-pattern sanitizer** (`backend/src/recoup/evidence/sanitizer.py`): auth tokens, JWTs, API keys, cookies, emails, AWS account IDs, private IPs, and AWS secret patterns. Goal: **zero PII** in agent reasoning context.

### Cedar policy (deterministic gate)

The policy engine is **not** an LLM. Cedar rules in-repo define whether a proposed action is permitted, requires approval, or is forbidden — including hard forbid on high-risk actions like `terminate_ec2_instance`. On the **App Runner demo**, we evaluate the same semantics **deterministically in Python** (`backend/src/recoup/safety/cedar.py`); CDK/IAM remain **AgentCore-oriented** for production hardening.

Policy source: [infra/policy/recoup-policy.cedar](https://github.com/swa01wk/recoup/blob/main/infra/policy/recoup-policy.cedar)

### HITL with cryptographic binding

The approval card is the demo “wow moment”: operator sees **why Recoup believes** spend is unintended, **safety checks**, **risk tier**, **exact action**, and **rollback** — then **Approve**, **Investigate further**, or **Decline**.

Backend enforces binding:

- `claim_hash` — digest of the recovery claim  
- `amount` — exact USD/month at approval time  
- `state_version` — optimistic concurrency  

Any mismatch → **409 Conflict** (covered by Playwright SEC tests).

### Try the live demo

No AWS keys required: https://pdkeexzwxr.us-east-1.awsapprunner.com/scan → Demo Scan → **Start Recovery** on three services → on opportunity detail, use **Approve**, **Investigate further**, or **Decline** and watch binding on tamper (Playwright SEC suite). Guest sessions: `X-Demo-Session` header + sidebar **Reset Demo Data**.

Step-by-step operator guide: [docs/operator-journey.md](https://github.com/swa01wk/recoup/blob/main/docs/operator-journey.md)

Repo: https://github.com/swa01wk/recoup

### Tags `(max 5)` — pick in Builder UI

Pick **5** (include **Agents for Humans** — hackathon tag):

- Agents for Humans  
- Amazon Bedrock  
- Generative AI  
- Cloud Financial Management  
- Security or cloud-security (if listed)  

### Cover image

Upload **`docs/archive/submit/assets/builder-cover-recoup-trust.jpg`** (1200×675; JPEG often passes Builder moderation—use `.png` only if JPG is rejected). Regenerate: `node docs/archive/submit/assets/export-builder-cover.mjs article2`

---

## Article 3 — Proof: tests, math, ship gates

### Title `(99/255)`

Agents for Humans — How We Proved Recoup Works: 419 Backend + 127 E2E Tests and Zero Unsafe Actions

### Description `(~268/512)` — verify count in Builder UI

Agent demos are easy to hand-wave; we built ship gates judges can re-run. [Building Recoup: Agents for Humans and How We Designed a Safe AWS Recovery Workflow with Strands Graph](https://builder.aws.com/content/3JKKaMeu6Cbc2HQQjmAiOosEVOH/building-recoup-agents-for-humans-and-how-we-designed-a-safe-aws-recovery-workflow-with-strands-graph) covers architecture; this post is proof: J-FULL Playwright, golden SLA Strands replay, 419+127 tests, six scorecard gates, zero unsafe actions.

### Body

Agent demos are easy to hand-wave; we optimized for **ship gates** judges can re-run — the same bar as our Devpost submission and demo video.

[Building Recoup: Agents for Humans and How We Designed a Safe AWS Recovery Workflow with Strands Graph](https://builder.aws.com/content/3JKKaMeu6Cbc2HQQjmAiOosEVOH/building-recoup-agents-for-humans-and-how-we-designed-a-safe-aws-recovery-workflow-with-strands-graph) explains the **Strands SLA graph**; [Agents for Humans and Making AI Financial Decisions Trustworthy: Cedar, Evidence Redaction, and HITL in Recoup](https://builder.aws.com/content/3JKron5aTHK1KpAaoIbxNdSd9IH/agents-for-humans-and-making-ai-financial-decisions-trustworthy-cedar-evidence-redaction-and-hitl-in-recoup) explains **trust on the live demo**. Here we show **two complementary proofs**:

1. **Operator journey (J-FULL)** — scan → three **Start Recovery** paths → HITL triage → Recovery Ledger (+ SNS on approve), exercised in Playwright and `./scripts/prod_journey_hitl_smoke.sh` against production API.  
2. **Agent depth (repo + CI)** — golden **SLA replay** through the **11-node graph** with **Decimal math** (never LLM numbers) and adversarial policy/safety tests.

Canonical judge walkthrough: [judge-demo.md](https://github.com/swa01wk/recoup/blob/main/docs/judge-demo.md).

### Test pyramid

- **419** backend tests (pytest), including golden SLA replay and adversarial policy/safety cases  
- **127** Playwright tests across **16** specs — including **J-FULL** (scan → three triage paths → ledger + SNS) and **PSC** guest-session isolation  

Run locally:

```bash
cd frontend && npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts
cd backend && pytest -q
```

### Deterministic financial math

SLA credit recovery uses **Decimal arithmetic** and golden fixtures — **never LLM-generated numbers**. The replay adapter lives in `backend/src/recoup/adapters/replay.py`; CI enforces P95 latency and consecutive pass counts.

### Ship gates

`/api/quality/scorecard` exposes six gates (golden SLA replay through the Strands graph, financial math, evidence recall, tool autonomy, trace completeness, zero unsafe external actions). CI runs `scripts/assert_ship_gates.py`.

**For judges and demo video Scene 6 — run locally** (all gates pass when fixtures are present):

```bash
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
```

Production API may be used for smoke checks; golden replay gates on App Runner can fail if fixture paths differ — prefer local for “all gates pass” claims.

### Operator journey smoke

```bash
./scripts/prod_journey_hitl_smoke.sh
```

This script exercises approve / investigate / decline on three distinct services against production API with isolated demo sessions — **no browser, no AWS keys** (matches hackathon “try it” expectations).

### Try the live demo (same as Articles 1–2)

https://pdkeexzwxr.us-east-1.awsapprunner.com/scan → Demo Scan → **Start Recovery** on three services → triage on detail → **Recovery Ledger**. Guest sessions: sidebar **Reset Demo Data**.

Repo: https://github.com/swa01wk/recoup

### Tags `(max 5)`

- Amazon Bedrock  
- Testing  
- Agents for Humans  
- Cloud Financial Management  
- Continuous Integration  

### Cover image

Scorecard JSON snippet, CI badge, or terminal output from `prod_journey_hitl_smoke.sh` (redact secrets).

---

## Publish checklist

| Step | Article 1 | Article 2 | Article 3 |
|------|-----------|-----------|-----------|
| Title ≤ 255 | ☑ | ☑ | ☑ |
| Description ≤ 512 | ☑ | ☑ | ☑ |
| Body pasted (Markdown) | ☑ | ☑ | ☑ |
| Cover uploaded | ☑ | ☑ | ☑ |
| Tags (≤ 5) | ☑ | ☑ | ☑ |
| Preview | ☑ | ☑ | ☑ |
| Publish + URL in submission-record | ☑ [live](https://builder.aws.com/content/3JKKaMeu6Cbc2HQQjmAiOosEVOH/building-recoup-agents-for-humans-and-how-we-designed-a-safe-aws-recovery-workflow-with-strands-graph) | ☑ [live](https://builder.aws.com/content/3JKron5aTHK1KpAaoIbxNdSd9IH/agents-for-humans-and-making-ai-financial-decisions-trustworthy-cedar-evidence-redaction-and-hitl-in-recoup) | ☑ [live](https://builder.aws.com/content/3JKtrHzpq4RFxt6kXlNYT5uY1uJ/agents-for-humans-and-how-we-proved-recoup-works-419-backend-127-e2e-tests-and-zero-unsafe-actions) |
