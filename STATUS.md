# Recoup — Project Status

**Competition Deadline:** Sep 14, 2026 (AWS Agents for Humans Hackathon)  
**Last Updated:** Sep 1, 2026 — 7:09 PM IST  
**Days Remaining:** 13

---

## Overall Progress

| Phase | Name | Target | Status | Progress |
|-------|------|--------|--------|----------|
| 0 | Foundation & Infrastructure | Sep 3 | ✅ Complete | 100% |
| 1 | Core Agent Graph & Data Contracts | Sep 6 | ✅ Complete | 100% |
| 2 | Verified Replay & SLA Recovery Engine | Sep 9 | 🔴 Not Started | 0% |
| 3 | Evidence System, Safety Layer & HITL | Sep 10 | 🔴 Not Started | 0% |
| 4 | Frontend Command Center | Sep 11 | 🟡 Scaffolded | ~5% |
| 5 | Evaluation & Testing Suite | Sep 12 | 🔴 Not Started | 0% |
| 6 | Live AWS Action Proof | Sep 12 | 🔴 Not Started | 0% |
| 7 | Polish, Submission & Video | Sep 14 | 🔴 Not Started | 0% |

---

## Phase 0 — Foundation & Infrastructure
**Target:** Sep 3, 2026 | **Status:** ✅ Complete — all AWS resources live

### Done ✅
- [x] Repository created within competition window (first commit: `0bbe21e`)
- [x] Directory scaffold: `backend/`, `frontend/`, `infra/`, `plans/`, `sla_catalog/`, `eval_fixtures/`, `scripts/`, `docs/`, `architecture/`
- [x] 9 domain models typed + validated (Pydantic v2, zero deprecation warnings)
- [x] CDK stacks TypeScript-clean: `RecoupInfraStack` + `RecoupDemoStack`
  - DynamoDB: 4 tables with GSIs, TTL, PITR, KMS encryption
  - S3: 3 buckets (evidence/KMS, sla-catalog/SSE, eval-fixtures/SSE) versioned + lifecycle
  - SQS: `recoup-recovery-events` + DLQ
  - EventBridge: `RecoupHealthEventRule` → SQS
  - KMS: `alias/recoup-evidence` CMK with key rotation
  - CloudWatch: log groups `/recoup/runtime`, `/recoup/gateway`, `/recoup/api` + `$10` spend alarm
  - IAM: `RecoupRuntimeRole`, `RecoupGatewayExecutionRole`, `RecoupReadConnectorRole`
  - EC2: `t3.micro` demo instance with `RecoupDemo=true` tag
- [x] SLA catalog: `sla_catalog/api_gateway/2022-05-05.yaml`
- [x] CI workflow (4 jobs): backend lint+tests, frontend build, CDK synth, ship-gates
  - Hardened with `-W error::DeprecationWarning` — zero warnings tolerated
- [x] Calculator engine + golden unit tests (63/63 passing, 0 warnings)
- [x] SLA resolver engine with `_SERVICE_DIR_ALIASES` normalization
- [x] Python project: `pyproject.toml`, `.python-version`
- [x] Next.js 14 frontend initialized (`frontend/`)
- [x] `LICENSE` (MIT) at repo root
- [x] `README.md` with CI badge, project description, quick-start
- [x] `docs/DISCLOSURE.md` — competition disclosure
- [x] `architecture/architecture.svg` — full Strands graph SVG diagram
- [x] `infra/agentcore-config.yaml` — 11 tools wired with action classes + policy guards
- [x] `scripts/deploy.sh` — preflight → CDK bootstrap → deploy both stacks → S3 SLA upload
- [x] `scripts/verify_infra.sh` — post-deploy verification of all 20+ AWS resources
- [x] `scripts/register_agentcore.py` — AgentCore Harness + Gateway registration with dry-run (updated to new `bedrock-agentcore-control` API; classic Bedrock Agents is in maintenance mode for new accounts since Jul 30 2026)
- [x] `.env.example` — all 30+ environment variables documented with placeholders
- [x] `docs/infrastructure-runbook.md` — deploy, teardown, cost estimate, troubleshooting
- [x] `docs/iam-roles.md` — full role inventory with permissions + verification commands
- [x] `docs/ci-guide.md` — CI jobs, how to add tests, badge, troubleshooting
- [x] Public GitHub repository: [github.com/swa01wk/recoup](https://github.com/swa01wk/recoup) ✅

### Remaining — 3 user actions (no more code needed)
- [x] **Run `./scripts/deploy.sh`** → provisioned all AWS resources ✅
- [x] **Run `python scripts/register_agentcore.py`** → AgentCore Harness + Gateway live ✅
  - Harness: `recoup_recovery_agent-T9RRFljZUO`
  - Gateway: `recoup-tool-gateway-tpnzqdgixc` (`https://recoup-tool-gateway-tpnzqdgixc.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp`)
- [x] **Run `./scripts/verify_infra.sh`** → all 20+ checks pass ✅
- [x] **Subscribe email to `recoup-alerts` SNS topic** → `swaroop.shivakumar@webknot.in` subscribed, pending confirmation ✅
- [ ] **Verify AWS Builder ID** at [builder.aws](https://builder.aws)

---

## Phase 1 — Core Agent Graph & Data Contracts
**Target:** Sep 6, 2026 | **Status:** ✅ Complete (63/63 tests, 0 warnings)

### Done
- [x] All 9 domain models — Pydantic v2, zero deprecation warnings
- [x] SLA catalog with `source_hash` + `_SERVICE_DIR_ALIASES` normalization
- [x] **`graph/types.py`** — `Graph`, `DeterministicNode`, `AgentNode`, `GraphState`, `PolicyDecision`, `IncidentHypothesis`, `CaseOutcome`, `NodeContext`, `ToolContext`, `ErrorDisposition`, `Edge`, `ConditionalEdge`
- [x] **`graph/nodes.py`** — All 11 stub node implementations; deterministic, no LLM required
- [x] **`graph/recoup_graph.py`** — Full graph wired; conditional edge at `risk_policy_gate`; validated at import
- [x] **`graph/state_machine.py`** — DynamoDB atomic transitions; optimistic locking; in-memory fallback
- [x] **`hooks/tracing.py`** — `RecoupTracingHooks`: 6 hook types; tool allowlist enforced
- [x] **`tools/aws_tools.py`** — 8 AWS read tools (CloudWatch, Health, Cost, CloudTrail, Support)
- [x] **`tools/internal_tools.py`** — 3 internal tools (store_evidence, create_approval_request, simulate_support_case)
- [x] **`tools/ec2_tools.py`** — `stop_demo_instance` with allowlist guard (Phase 6 ready)
- [x] **`tools/registry.py`** — `TOOL_REGISTRY`: 14 tools, action classes, Lambda targets, allowed nodes
- [x] **`adapters/replay.py`** — `ReplayAdapter` + `CANONICAL_SCENARIO` ($1,840 golden scenario)
- [x] **`adapters/agentcore.py`** — `AgentCoreAdapter` with `register_all_tools()`
- [x] **`api/main.py`** — FastAPI + CORS + `/health` + `/api/config`
- [x] **`api/routes/`** — opportunities, approvals, replay endpoints
- [x] **63 unit tests pass** — 0 warnings, no LLM calls, no AWS calls

### Definition of Done
| Check | Result |
|-------|--------|
| Domain models import + validate | ✅ |
| Graph instantiates; all edges resolve | ✅ |
| State machine DynamoDB optimistic locking | ✅ |
| SLA catalog loads; source_hash CI test passes | ✅ |
| 14 tools in TOOL_REGISTRY with action classes | ✅ |
| Hooks fire on stub node calls | ✅ |
| 63/63 tests pass; no LLM/AWS calls | ✅ |
| `-W error::DeprecationWarning` clean | ✅ |

---

## Phase 2 — Verified Replay & SLA Recovery Engine
**Target:** Sep 9, 2026 | **Status:** 🔴 Not Started

### Remaining
- [ ] Canonical replay seed artifacts in `eval_fixtures/` (event JSON, metric series, billing snapshot)
- [ ] `normalize_event` node parses both replay and live event schema
- [ ] `incident_correlation` agent correlates synthetic API Gateway SLA incident
- [ ] `sla_contract_resolver` loads `2022-05-05` contract by incident date
- [ ] `availability_calculator` produces $1,840 deterministically
- [ ] `eligibility_checker` passes all canonical criteria
- [ ] `claim_packager` produces complete `ClaimPackage`
- [ ] Full end-to-end: reproducible $1,840 in ≤ 60 s
- [ ] `scripts/replay_run.py` — headless replay execution script

---

## Phase 3 — Evidence System, Safety Layer & HITL
**Target:** Sep 10, 2026 | **Status:** 🔴 Not Started

### Remaining
- [ ] `evidence/` module: collector, sanitizer, manifest builder
- [ ] Evidence stored to S3 with SHA-256 hash; raw evidence never in LLM context
- [ ] Deterministic redaction — fails closed on high-risk patterns
- [ ] `safety/` module: Cedar policy rules, autonomy class enforcement
- [ ] AgentCore Policy authorization on all mutating tools
- [ ] `approval/` module: HITL flow (request → token → decision)
- [ ] DynamoDB-backed approval record with TTL
- [ ] All `class_c_action` tools require explicit approval

---

## Phase 4 — Frontend Command Center
**Target:** Sep 11, 2026 | **Status:** 🟡 Scaffolded (~5%)

### Done
- [x] Next.js 14 + TypeScript initialized
- [x] `layout.tsx` and root `page.tsx` stub

### Remaining
- [ ] Tailwind CSS + shadcn/ui
- [ ] Command Center dashboard
- [ ] Opportunity Detail, Evidence Room, Decision Inbox, Agent Trace, Eval views
- [ ] SIMULATION / LIVE AWS ACTION badges on all demo paths
- [ ] Backend API integration (polling or WebSocket)

---

## Phase 5 — Evaluation & Testing Suite
**Target:** Sep 12, 2026 | **Status:** 🔴 Not Started

### Done
- [x] `test_calculator.py` — golden calculator unit tests (part of 63-test suite)

### Remaining
- [ ] ≥ 40 eval scenarios (golden-path, edge, adversarial, safety, HITL, evidence, SLA boundary, tool-failure)
- [ ] Eval runner + scorecard JSON
- [ ] 100% golden-path across 20 consecutive runs
- [ ] ≥ 92% overall, ≥ 98% evidence recall, 0 unsafe actions

---

## Phase 6 — Live AWS Action Proof
**Target:** Sep 12, 2026 | **Status:** 🔴 Not Started

### Remaining
- [ ] `RecoupDemoStack` EC2 deployed → instance ID in `RECOUP_DEMO_INSTANCE_ALLOWLIST`
- [ ] `stop_demo_instance` registered in AgentCore Gateway with Cedar policy guard
- [ ] CloudWatch + CloudTrail checks before and after stop
- [ ] HITL approval required; **LIVE AWS ACTION** badge in Decision Inbox
- [ ] CloudTrail confirms actual `StopInstances` API call in evidence

---

## Phase 7 — Polish, Submission & Video
**Target:** Sep 14, 2026 | **Status:** 🔴 Not Started

### Done
- [x] `architecture/architecture.svg` — Strands graph diagram committed

### Remaining
- [ ] README fully expanded (demo GIF, full setup instructions, architecture section)
- [ ] Video ≤ 5:00, public on YouTube/Vimeo
- [ ] Live URL accessible in incognito; replay works without AWS credentials
- [ ] Three builder.aws posts (+0.6 bonus points)
- [ ] Devpost submission form completed
- [ ] Final rubric check

---

## Repository Structure

```
recoup/
├── backend/
│   ├── src/recoup/
│   │   ├── models/          ✅ 9 domain models (0 warnings)
│   │   ├── engines/         ✅ calculator, sla_resolver
│   │   ├── graph/           ✅ types, nodes (×11), recoup_graph, state_machine
│   │   ├── tools/           ✅ aws_tools, internal_tools, ec2_tools, registry (14 tools)
│   │   ├── adapters/        ✅ replay ($1,840 canonical), agentcore
│   │   ├── api/             ✅ FastAPI: opportunities, approvals, replay routes
│   │   ├── hooks/           ✅ RecoupTracingHooks (6 hook types)
│   │   ├── evidence/        ❌ empty — Phase 3
│   │   ├── safety/          ❌ empty — Phase 3
│   │   └── approval/        ❌ empty — Phase 3
│   └── tests/unit/          ✅ 63 tests, 0 warnings
├── frontend/src/app/         🟡 stub — Phase 4
├── infra/
│   ├── cdk/lib/stacks/      ✅ RecoupInfraStack + RecoupDemoStack (TypeScript-clean)
│   └── agentcore-config.yaml ✅ 11 tools, action classes, policy guards
├── architecture/
│   └── architecture.svg     ✅ full Strands graph SVG
├── scripts/
│   ├── deploy.sh            ✅ preflight → CDK bootstrap → deploy → S3 sync
│   ├── verify_infra.sh      ✅ post-deploy resource verification (20+ checks)
│   └── register_agentcore.py ✅ AgentCore Runtime + Gateway registration
├── docs/
│   ├── DISCLOSURE.md        ✅
│   ├── infrastructure-runbook.md ✅ deploy, teardown, cost, troubleshooting
│   ├── iam-roles.md         ✅ all roles, permissions, verification commands
│   └── ci-guide.md          ✅ CI jobs, adding tests, troubleshooting
├── .env.example             ✅ all 30+ env vars documented
├── sla_catalog/api_gateway/ ✅ 2022-05-05.yaml
└── plans/                   ✅ all 8 phase plans
```

---

## Critical Path — 13 Days

| Day | Action |
|-----|--------|
| **Sep 1 (today)** | `./scripts/deploy.sh` · `python scripts/register_agentcore.py` · `./scripts/verify_infra.sh` |
| **Sep 2–3** | Phase 2: replay engine → $1,840 deterministic end-to-end |
| **Sep 4–6** | Phase 3: evidence, redaction, Cedar policy, HITL approval flow |
| **Sep 5–7** | Phase 4: frontend views (overlaps Phase 3) |
| **Sep 7–9** | Phase 5: eval suite (40 scenarios, scorecard) + Phase 6: live EC2 demo |
| **Sep 10–12** | Phase 7: README, video recording |
| **Sep 13–14** | Devpost submit · builder.aws posts · final rubric check |

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Complete |
| 🟡 | In progress / partial |
| 🔴 | Not started |
| ❌ | Needs work |
