# Recoup — Implementation Plans

This folder contains the full phase-by-phase implementation plan for **Recoup: AWS Autonomous Cloud Spend Recovery Agent**, built for the AWS Agents for Humans Hackathon (Aug 10 – Sep 14, 2026).

---

## Phase Overview

| Phase | Name | Timeline | Priority | Depends On |
|-------|------|----------|----------|-----------|
| [Phase 0](./phase-0-foundation-infrastructure.md) | Foundation & Infrastructure Setup | Day 1–3 (→ Sep 3) | P0 | — |
| [Phase 1](./phase-1-core-agent-graph-data-contracts.md) | Core Agent Graph & Data Contracts | Day 3–6 (→ Sep 6) | P0 | Phase 0 |
| [Phase 2](./phase-2-verified-replay-sla-engine.md) | Verified Replay & SLA Recovery Engine | Day 6–9 (→ Sep 9) | P0 | Phase 1 |
| [Phase 3](./phase-3-evidence-system-safety-layer.md) | Evidence System, Safety Layer & HITL | Day 7–10 (→ Sep 10) | P0 | Phase 1 |
| [Phase 4](./phase-4-frontend-command-center.md) | Frontend Command Center | Day 8–11 (→ Sep 11) | P1 | Phase 1 (API) |
| [Phase 5](./phase-5-evaluation-testing-suite.md) | Evaluation & Testing Suite | Day 9–12 (→ Sep 12) | P1 | Phases 1–3 |
| [Phase 6](./phase-6-live-aws-action-proof.md) | Live AWS Action Proof | Day 10–12 (→ Sep 12) | P1 | Phases 3, 4 |
| [Phase 7](./phase-7-polish-submission-video.md) | Polish, Submission & Video | Day 12–14 (→ Sep 14) | P0 | All |

**Sep 11 is the feature cutoff.** Only bug fixes and polish after that date.

---

## Supporting Documents

| Document | Purpose |
|----------|---------|
| [AWS Requirements](./aws-requirements.md) | Complete AWS service inventory, IAM roles, CDK resources, cost estimates, and compliance checklist |

---

## What Recoup Builds

```
OBSERVE  →  INVESTIGATE  →  RECOVER  →  PREVENT
          humans enter only at policy boundaries
```

Recoup is a background Strands agent that:
1. **Observes** AWS Health events and cost signals via EventBridge
2. **Investigates** incidents by correlating CloudWatch metrics, billing, and CloudTrail
3. **Recovers** cloud spend by assembling SLA credit claims with deterministic evidence
4. **Prevents** recurrence by proposing governed optimization actions
5. **Proves** every decision with an auditable trace, deterministic math, and policy receipts

---

## The Two Demo Proofs

### Proof 1 — Verified Replay (SLA Claim)
- Synthetic API Gateway SLA breach in August 2026
- `99.9306%` monthly uptime → 10% credit tier
- `$18,400` affected charges × 10% = **`$1,840` potential credit**
- Full workflow: normalize → correlate → resolve SLA → calculate → collect evidence → sanitize → assess eligibility → risk gate → human approval → simulate submission
- VERIFIED REPLAY badge; no real AWS Support case created

### Proof 2 — Live AWS Action (EC2 Stop)
- Real `t3.micro` EC2 instance with `RecoupDemo=true` tag
- CloudWatch confirms 0.2% average CPU — idle resource
- Decision Inbox shows LIVE AWS ACTION card with all safety checks
- Human approval → AgentCore Cedar policy → `StopInstances` (NOT terminate)
- Verified stopped state confirmed; reset script available

---

## Architecture Summary

```
Frontend (Next.js)
  → FastAPI (auth, session, SSE)
    → Amazon Bedrock AgentCore Runtime
      → Strands Graph (11 nodes: 4 deterministic, 5 agent, 2 hybrid)
        → AgentCore Gateway (12 typed tools)
          → AgentCore Policy (Cedar; default deny for RED/BLACK tools)
            → AWS Services (CloudWatch, Cost Explorer, CloudTrail, EventBridge)
              → DynamoDB (state) + S3 (evidence) + SQS (events)
```

---

## Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| LLMs propose; contracts decide | Deterministic nodes own all financial math, authorization, and state transitions |
| Default-deny writes | READ tools automatic; WRITE_EXTERNAL requires approval + Cedar policy |
| Evidence never raw | Raw evidence encrypted in S3; only sanitized previews reach agent context or UI |
| Replay-first | Full demo works without a live AWS incident; fixture-seeded and deterministic |
| Auditable | Every tool call has a `ToolAudit` record; every node has a trace span |
| Idempotent | Every external action has an idempotency key; duplicate events create one opportunity |

---

## Documentation

After each phase is implemented, the phase plan specifies documentation files to be created in `plans/docs/`. These docs capture how the system works post-implementation and serve as the basis for the README, architecture documentation, and builder.aws posts.

---

## Ship Gates (Must All Pass Before Submission)

### Technical
- [ ] 20/20 consecutive golden replay passes
- [ ] 0 unsafe external actions across full test suite
- [ ] 100% deterministic financial math
- [ ] AgentCore Runtime, Gateway, Policy deployed and demonstrable

### Product
- [ ] Non-developer understands problem within 20 seconds of seeing the UI
- [ ] "Potential" vs "confirmed" money is never ambiguous
- [ ] Exactly one human approval in the hero flow
- [ ] No screen looks like a debug prototype

### Submission
- [ ] Video ≤ 5:00; public; covers problem/audience/why/demo
- [ ] Live URL works in incognito; no AWS credentials required for judges
- [ ] Repo public with license visible, README, architecture diagram
- [ ] 3 builder.aws posts with "Agents for Humans" in each title
- [ ] AWS Builder ID verified
- [ ] Submitted before Sep 13 internal deadline
