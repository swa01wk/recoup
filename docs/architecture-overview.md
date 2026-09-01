# Recoup — Architecture Overview

**Version:** Phase 0 + Phase 1 complete  
**Last Updated:** Sep 1, 2026  
**Competition:** AWS Agents for Humans Hackathon (Aug 10 – Sep 14, 2026)

---

## System Purpose

Recoup is an autonomous cloud-spend recovery agent. It monitors AWS workloads, detects SLA breaches and cost anomalies, gathers evidence, calculates potential credits, and submits claims to AWS Support — involving humans only at genuine policy boundaries (irreversible financial actions).

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 14)                         │
│        Command Center · Decision Inbox · Agent Trace            │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────────────┐
│                  FastAPI Backend (Python 3.12)                   │
│         /api/opportunities · /api/approvals · /api/replay       │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│          Amazon Bedrock AgentCore Runtime                        │
│          recoup_recovery_agent-T9RRFljZUO                       │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │              Strands Agent Graph (11 nodes)              │  │
│   │                                                          │  │
│   │  normalize_event → incident_correlation                  │  │
│   │       → sla_contract_resolver → availability_calculator  │  │
│   │       → evidence_collector → evidence_sanitizer          │  │
│   │       → eligibility_reasoner → risk_policy_gate          │  │
│   │             ↓ REQUIRE_APPROVAL                           │  │
│   │       await_human_approval (HITL)                        │  │
│   │             ↓ APPROVED                                   │  │
│   │       claim_package_generator → submission_adapter        │  │
│   │       → case_monitor                                     │  │
│   └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ MCP (Model Context Protocol)
┌────────────────────────▼────────────────────────────────────────┐
│          AgentCore Gateway                                       │
│    recoup-tool-gateway-tpnzqdgixc                               │
│    14 narrow typed tools · action classes · Cedar policy        │
└──────┬──────────────────────────────────────────────────────────┘
       │ IAM role-scoped invocations
┌──────▼────────────────────────────────────────────────────────┐
│                   AWS Data Sources                             │
│  CloudWatch · Cost Explorer · CloudTrail · Health · Support   │
└───────────────────────────────────────────────────────────────┘
       │
┌──────▼────────────────────────────────────────────────────────┐
│                   Persistent Storage                           │
│  DynamoDB (4 tables) · S3 (3 buckets) · SQS · EventBridge    │
└───────────────────────────────────────────────────────────────┘
```

---

## Core Design Principles

| Principle | Implementation |
|-----------|---------------|
| **LLMs propose; contracts decide** | All financial arithmetic, SLA credit calculation, and state transitions are deterministic Python — no LLM involvement |
| **Default-deny writes** | READ tools are automatic; `submit_support_case` requires an unexpired `ApprovalRecord` + Cedar policy ALLOW |
| **Evidence never raw** | Raw evidence is encrypted in S3 (KMS CMK). Only SHA-256 hashes and sanitized previews reach the agent or UI |
| **Replay-first** | The primary demo is a Verified Replay — seeded, deterministic, no live AWS incident needed |
| **Auditable** | Every tool call produces a `ToolAudit` record. Every node execution produces a structured log event |
| **Idempotent** | Every external action carries an idempotency key. Duplicate events create exactly one opportunity |
| **Simulation-safe** | `simulation_mode=True` is the default on every `GraphState`. Live submission requires an explicit flag AND a valid approval |

---

## The Two Demo Proofs

### Proof 1 — Verified Replay (Primary)

A fully deterministic execution seeded from `eval_fixtures/`:

```
Synthetic API Gateway SLA breach
  → 6 bad 5-minute intervals in 8,640 total
  → 99.9306% uptime (below 99.95% commitment)
  → 10% credit tier
  → $18,400 billed × 10% = $1,840.00 potential credit
  → Human approves in Decision Inbox
  → Simulated case submitted (simulation_mode=True)
```

Expected result: **$1,840.00** on every run, P95 ≤ 60 s.

### Proof 2 — Live AWS Action (Phase 6)

```
Real EC2 t3.micro (RecoupDemo=true tag)
  → CloudWatch confirms idle CPU
  → Cedar policy evaluates REQUIRE_APPROVAL
  → Human approves in Decision Inbox
  → StopInstances call with CloudTrail evidence
  → CloudTrail confirms actual API call
```

---

## Repository Layout

```
recoup/
├── backend/src/recoup/
│   ├── models/          9 Pydantic v2 domain models
│   ├── engines/         calculator.py + sla_resolver.py (deterministic math)
│   ├── graph/           types.py · nodes.py · recoup_graph.py · state_machine.py
│   ├── tools/           aws_tools.py · internal_tools.py · ec2_tools.py · registry.py
│   ├── adapters/        replay.py · agentcore.py
│   ├── api/             FastAPI: main.py + routes (opportunities, approvals, replay)
│   ├── hooks/           tracing.py (RecoupTracingHooks)
│   ├── evidence/        (Phase 3 — not yet implemented)
│   ├── safety/          (Phase 3 — not yet implemented)
│   └── approval/        (Phase 3 — not yet implemented)
├── backend/tests/unit/  63 tests, 0 warnings, no LLM/AWS calls
├── frontend/src/app/    Next.js 14 stub (Phase 4)
├── infra/cdk/           RecoupInfraStack + RecoupDemoStack (TypeScript)
├── infra/agentcore-config.yaml  11 tools with action classes + policy guards
├── architecture/        architecture.svg (full Strands graph diagram)
├── scripts/             deploy.sh · verify_infra.sh · register_agentcore.py
├── docs/                This document and others (see index below)
├── sla_catalog/         Human-verified SLA contracts (source_hash enforced)
├── eval_fixtures/       Immutable replay seed artifacts
└── plans/               Phase-by-phase implementation plans
```

---

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Agent Framework | Amazon Bedrock AgentCore (Strands) | Latest (bedrock-agentcore-control API) |
| LLM | Amazon Bedrock Claude 3.5 Sonnet | claude-3-5-sonnet-20241022 |
| Backend | FastAPI + Uvicorn | Python 3.12 |
| Domain Models | Pydantic v2 | 2.x |
| Infrastructure | AWS CDK | 2.267+ (TypeScript) |
| Frontend | Next.js 14 + TypeScript | Node 20 |
| Database | Amazon DynamoDB | On-demand, PAY_PER_REQUEST |
| Evidence Storage | Amazon S3 + KMS CMK | — |
| Event Bus | Amazon EventBridge + SQS | — |
| Policy | AgentCore Policy (Cedar) | — |
| CI | GitHub Actions | ubuntu-latest |
| Linting | ruff + mypy | — |

---

## AWS Resources Provisioned

### RecoupInfraStack (CDK)

| Resource | Name | Purpose |
|---------|------|---------|
| KMS Key | `alias/recoup-evidence` | Encrypts evidence S3 + DynamoDB |
| S3 Bucket | `recoup-evidence-{acct}-{region}` | Raw evidence storage (KMS, versioned) |
| S3 Bucket | `recoup-sla-catalog-{acct}-{region}` | SLA contract YAML files (SSE, versioned) |
| S3 Bucket | `recoup-eval-fixtures-{acct}-{region}` | Replay seed artifacts (SSE, versioned) |
| DynamoDB | `recoup-opportunities` | Main opportunity records + GSIs |
| DynamoDB | `recoup-approvals` | HITL approval records (TTL) |
| DynamoDB | `recoup-tool-audits` | Tool call audit log |
| DynamoDB | `recoup-outcome-metadata` | Service/region/month outcome summaries |
| SQS Queue | `recoup-recovery-events` | Incoming health/anomaly events |
| SQS DLQ | `recoup-recovery-events-dlq` | Failed event dead-letter queue |
| EventBridge Rule | `RecoupHealthEventRule` | Routes AWS Health events → SQS |
| CloudWatch Log Group | `/recoup/runtime` | AgentCore Runtime logs |
| CloudWatch Log Group | `/recoup/gateway` | AgentCore Gateway logs |
| CloudWatch Log Group | `/recoup/api` | FastAPI backend logs |
| CloudWatch Alarm | `RecoupEstimatedChargesAlarm` | Fires at $10 estimated charges |
| SNS Topic | `recoup-alerts` | Cost alarm notification target |
| IAM Role | `RecoupRuntimeRole` | Bedrock AgentCore Runtime execution |
| IAM Role | `RecoupGatewayExecutionRole` | Gateway Lambda invocation |
| IAM Role | `RecoupReadConnectorRole` | Read-only tool Lambdas |

### RecoupDemoStack (CDK)

| Resource | Name | Purpose |
|---------|------|---------|
| EC2 Instance | `t3.micro` (tag: `RecoupDemo=true`) | Live AWS action demo target |

### AgentCore (registered via script)

| Resource | ID | Purpose |
|---------|-----|---------|
| AgentCore Harness | `recoup_recovery_agent-T9RRFljZUO` | Strands graph host |
| AgentCore Gateway | `recoup-tool-gateway-tpnzqdgixc` | MCP tool endpoint |
| Gateway URL | `https://recoup-tool-gateway-tpnzqdgixc.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp` | MCP endpoint |

---

## Data Flow — Full Pipeline

```
1. INGEST
   EventBridge Health event / SQS message / Replay seed
   → normalize_event node
   → IncidentSignal (typed, idempotency key generated)

2. CORRELATE (Agent)
   → incident_correlation node
   → CloudWatch metrics + Health events + CloudTrail
   → IncidentHypothesis (service, region, intervals, confidence)

3. RESOLVE
   → sla_contract_resolver node
   → sla_catalog/{service}/{date}.yaml
   → SLAContract (commitment %, credit tiers)

4. CALCULATE
   → availability_calculator node (pure Decimal math)
   → AvailabilityResult (uptime %, tier %, credit $)

5. COLLECT EVIDENCE (Agent)
   → evidence_collector node
   → CloudWatch + logs + billing → S3 (raw, KMS encrypted)
   → EvidenceManifest (evidence IDs only, no raw content)

6. SANITIZE
   → evidence_sanitizer node (deterministic redaction)
   → RedactionReport + sanitized EvidenceManifest

7. ASSESS ELIGIBILITY (Agent)
   → eligibility_reasoner node (reads evidence by ID only)
   → EligibilityAssessment (eligible?, confidence, satisfied requirements)

8. POLICY GATE
   → risk_policy_gate node (Cedar policy evaluation)
   → PolicyDecision: ALLOW / REQUIRE_APPROVAL / DENY

9. HUMAN-IN-THE-LOOP (if REQUIRE_APPROVAL)
   → await_human_approval (HITL pause)
   → Human reviews in Decision Inbox
   → ApprovalRecord stored in DynamoDB

10. PACKAGE CLAIM (Agent, post-approval)
    → claim_package_generator node
    → ClaimPackage (subject, body, evidence IDs, calculator hash)

11. SUBMIT
    → submission_adapter node
    → simulation_mode=True: deterministic case ID
    → simulation_mode=False: real AWS Support case (requires approval + Cedar ALLOW)

12. MONITOR (Agent)
    → case_monitor node
    → CaseOutcome (PENDING / RESOLVED_APPROVED / RESOLVED_REJECTED)
```

---

## Documentation Index

| Document | What it covers |
|---------|---------------|
| [agent-graph.md](agent-graph.md) | All 11 nodes, types, tools, inputs/outputs, edge conditions |
| [domain-models.md](domain-models.md) | All 9 Pydantic domain models with fields and validators |
| [api-reference.md](api-reference.md) | FastAPI endpoints: request/response shapes, error codes |
| [tool-registry.md](tool-registry.md) | 14 tools: action classes, Lambda targets, allowed nodes |
| [sla-calculator.md](sla-calculator.md) | SLA formula, credit tiers, golden test spec, Decimal precision |
| [replay-system.md](replay-system.md) | Verified Replay: canonical $1,840 scenario, how it works |
| [state-machine.md](state-machine.md) | Opportunity states, valid transitions, DynamoDB optimistic locking |
| [tracing-hooks.md](tracing-hooks.md) | Hook types, tool allowlists, redaction patterns, ToolAudit |
| [agentcore-integration.md](agentcore-integration.md) | AgentCore Runtime + Gateway: registration, config, IDs |
| [infrastructure-runbook.md](infrastructure-runbook.md) | Deploy, tear down, cost estimate, troubleshooting |
| [iam-roles.md](iam-roles.md) | All IAM roles, permissions, verification commands |
| [ci-guide.md](ci-guide.md) | CI jobs, adding tests, badges, troubleshooting |
