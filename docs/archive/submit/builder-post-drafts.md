# Builder.aws — publish-ready drafts

Copy each section into a new post at [AWS Builder Center](https://builder.aws). Titles **must** include **Agents for Humans**. Attach screenshots from production demo + `architecture/architecture.svg`.

After publishing, paste URLs into [submission-record.md](submission-record.md) and Devpost.

---

## Post 1

**Title:** Building Recoup: Agents for Humans — How We Designed a Safe AWS Recovery Workflow with Strands Graph

**Body:**

FinOps tools excel at *finding* waste; teams still struggle to *close* recovery safely. For the **Agents for Humans** hackathon we built **Recoup** — an autonomous cloud-spend recovery agent with an **11-node Strands graph** on Amazon Bedrock, but keeps destructive power behind **deterministic Cedar policy** and **human approval**.

### The graph

Recoup’s pipeline is deliberately split:

- **5 agent nodes** — e.g. incident correlation, evidence collection, eligibility reasoning, claim packaging, case monitoring  
- **6 deterministic nodes** — normalization, SLA math, sanitization, Cedar policy gate, submission adapter, monitoring hooks  

The LLM proposes; **Cedar decides**; humans approve at the boundary.

Flow (simplified):

`normalize_event → incident_correlation [Strands] → evidence_collection → eligibility → claim_package [Strands] → risk_policy_gate [Cedar] → HITL → submission_adapter → case_monitor`

See the committed diagram in our repo: `architecture/architecture.svg`.

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

---

## Post 2

**Title:** Agents for Humans — Making AI Financial Decisions Trustworthy: Cedar Policies, Evidence Redaction, and HITL Approvals in Recoup

**Body:**

When an agent touches cloud spend, “trust” is not a vibe — it’s architecture. Recoup treats **evidence**, **policy**, and **approval** as first-class gates before any recovery action.

### Evidence sanitizer

Before model context sees customer data, we run an **8-pattern sanitizer** (`backend/src/recoup/evidence/sanitizer.py`): auth tokens, JWTs, API keys, cookies, emails, AWS account IDs, private IPs, and AWS secret patterns. Goal: **zero PII** in agent reasoning context.

### Cedar policy (deterministic gate)

The policy engine is **not** an LLM. Cedar evaluates whether a proposed action is permitted, requires approval, or is forbidden — including hard forbid on high-risk actions like `terminate_ec2_instance`.

Walkthrough file: `infra/policy/recoup-policy.cedar`

### HITL with cryptographic binding

The approval card is the demo “wow moment”: operator sees **why** Recoup believes spend is unintended, **risk tier**, **exact action**, and **rollback** — then approves.

Backend enforces binding:

- `claim_hash` — digest of the recovery claim  
- `amount` — exact USD/month at approval time  
- `state_version` — optimistic concurrency  

Any mismatch → **409 Conflict** (covered by Playwright SEC tests).

### Live path

Guest sessions on App Runner isolate concurrent judges (`X-Demo-Session`). Try approve / investigate / decline on three services: [operator journey doc](../../operator-journey.md).

---

## Post 3

**Title:** Agents for Humans — How We Proved Recoup Works: 419 Backend + 127 E2E Tests, Deterministic Math, and Zero Unsafe Actions

**Body:**

Agent demos are easy to hand-wave; we optimized for **ship gates** judges can re-run.

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

`/api/quality/scorecard` exposes six gates (unsafe external actions, sanitizer coverage, replay stability, etc.). CI runs `scripts/assert_ship_gates.py`.

Production API:

```bash
curl -s https://qawwrm7kzy.us-east-1.awsapprunner.com/api/quality/scorecard | jq .
```

_(If DynamoDB is degraded in prod, run scorecard locally for demo video Scene 6.)_

### Operator journey smoke

```bash
./scripts/prod_journey_hitl_smoke.sh
```

This script exercises approve / investigate / decline on three distinct services against production API with isolated demo sessions.

Repo: https://github.com/swa01wk/recoup
