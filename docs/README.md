# Recoup — Documentation Index

**Project:** AWS Autonomous Cloud Spend Recovery Agent  
**Hackathon:** AWS Agents for Humans (Aug 10 – Sep 14, 2026)  
**Phases complete:** 0 (Foundation) + 1 (Core Agent Graph & Data Contracts)

---

## Quick Links

| Document | What it covers |
|---------|---------------|
| **[architecture-overview.md](architecture-overview.md)** | Full system architecture, tech stack, AWS resources, end-to-end data flow |
| **[agent-graph.md](agent-graph.md)** | All 11 graph nodes, their types (deterministic vs agent), tools, inputs/outputs, and edge conditions |
| **[domain-models.md](domain-models.md)** | All 9 Pydantic v2 domain models with fields, validators, and relationships |
| **[api-reference.md](api-reference.md)** | FastAPI endpoints: request/response shapes, error codes, curl examples |
| **[tool-registry.md](tool-registry.md)** | 14 tools: action classes, Lambda targets, per-node allowlists, function signatures |
| **[sla-calculator.md](sla-calculator.md)** | SLA formula, credit tiers, golden test spec ($1,840 proof), Decimal precision details |
| **[replay-system.md](replay-system.md)** | Verified Replay: canonical scenario, determinism guarantees, how to run and add scenarios |
| **[state-machine.md](state-machine.md)** | 15 opportunity states, valid transitions, DynamoDB optimistic locking, error types |
| **[tracing-hooks.md](tracing-hooks.md)** | 6 hook types, tool allowlist enforcement, high-risk redaction patterns, ToolAudit records |
| **[agentcore-integration.md](agentcore-integration.md)** | AgentCore Harness + Gateway: live IDs, registration script, Cedar policy guards, env vars |
| **[infrastructure-runbook.md](infrastructure-runbook.md)** | Deploy, tear down, resource inventory, cost estimate, troubleshooting |
| **[iam-roles.md](iam-roles.md)** | All 4 IAM roles, permissions, what each role cannot do, verification commands |
| **[ci-guide.md](ci-guide.md)** | 4 CI jobs, adding tests, ship-gates, badges, troubleshooting |
| **[DISCLOSURE.md](DISCLOSURE.md)** | Competition disclosure statement |

---

## Implementation Status

| Phase | Name | Status |
|-------|------|--------|
| 0 | Foundation & Infrastructure | ✅ Complete |
| 1 | Core Agent Graph & Data Contracts | ✅ Complete |
| 2 | Verified Replay & SLA Recovery Engine | 🔴 Not Started |
| 3 | Evidence System, Safety Layer & HITL | 🔴 Not Started |
| 4 | Frontend Command Center | 🟡 Scaffolded |
| 5 | Evaluation & Testing Suite | 🔴 Not Started |
| 6 | Live AWS Action Proof | 🔴 Not Started |
| 7 | Polish, Submission & Video | 🔴 Not Started |

See [STATUS.md](../STATUS.md) for the full project tracker.

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Unit tests | 63 / 63 passing |
| DeprecationWarnings | 0 |
| Domain models | 9 (Pydantic v2) |
| Graph nodes | 11 (4 deterministic · 5 agent · 2 hybrid) |
| Tools in registry | 14 |
| Golden credit value | **$1,840.00** |
| AWS resources provisioned | 20+ (CDK) |
| AgentCore Harness | `recoup_recovery_agent-T9RRFljZUO` |
| AgentCore Gateway | `recoup-tool-gateway-tpnzqdgixc` |
| CI jobs | 4 (backend · frontend · infra · ship-gates) |
