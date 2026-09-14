# Recoup — System Architecture (canonical diagram)

**Primary product path:** **J-FULL** — demo scan → promote → HITL → Recovery Ledger (+ SNS on approve).  
**Production:** App Runner UI + API (see [docs/archive/ops/production-hosting.md](../docs/archive/ops/production-hosting.md)).  
**Last updated:** Sep 14, 2026

Narrative detail: [docs/recoup-overall-architecture.md](../docs/recoup-overall-architecture.md) · [docs/operator-journey.md](../docs/operator-journey.md).

---

## High-level stack

```mermaid
flowchart TB
    fe["Next.js 16 (frontend/)<br/>/opportunities · /scan · /recovery · /opportunities/[id]<br/>useRecoveryData + session header"]
    api["FastAPI (backend/)<br/>/api/scan · /api/opportunities · /api/approvals · /api/quality"]
    aws["AWS read path<br/>STS AssumeRole · 9 account scanners"]
    agent["Agent layer (optional depth)<br/>11-node Strands graph · Cedar · replay adapter<br/>recovery/ pipeline on promote"]
    persist["Persistence<br/>DynamoDB approvals/outcomes · S3 evidence · SNS · in-memory demo state"]

    fe -->|"HTTP JSON · SSE on investigate"| api
    api --> aws
    api --> agent
    aws --> persist
    agent --> persist
```

---

## J-FULL operator lifecycle

```mermaid
flowchart LR
    reset["1 Reset<br/>session reset"]
    scan["2 Demo scan<br/>POST /api/scan/demo"]
    pick["3 Pick findings<br/>/opportunities"]
    promote["4 Promote<br/>graph → policy gate · AWAITING_APPROVAL"]
    hitl["5 HITL<br/>approve · investigate · decline"]
    ledger["6 Ledger<br/>/recovery"]

    reset --> scan --> pick --> promote --> hitl --> ledger
    hitl -->|"approve → RECOVERED + SNS"| ledger
```

---

## Agent graph (optional — not streamed on promote)

```mermaid
flowchart TD
    n1["normalize_event"]
    n2["incident_correlation / recovery pipeline"]
    n3["sla_contract_resolver"]
    n4["availability_calculator"]
    n5["evidence_collector"]
    n6["evidence_sanitizer"]
    n7["eligibility_reasoner"]
    gate["risk_policy_gate (Cedar)"]
    hitl["await_human_approval"]
    tail["claim_package → submission → case_monitor"]

    n1 --> n2 --> n3 --> n4 --> n5 --> n6 --> n7 --> gate
    gate --> hitl
    gate --> tail
    hitl --> tail
```

Promote runs the graph **through `risk_policy_gate`** with the **recovery/** pipeline for scan findings. Full SSE replay: `GET /api/opportunities/{id}/stream` after investigate.
