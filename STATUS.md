# Recoup — Project Status

**Competition Deadline:** Sep 14, 2026 (AWS Agents for Humans Hackathon)  
**Last Updated:** Sep 1, 2026 — 3:59 PM IST  
**Days Remaining:** 13

---

## ⚠️ Next Action — Commit & Push
All Phase 0 enhancements and the entire Phase 1 codebase exist locally but are **not yet committed**.  
Run before doing anything else:
```bash
git add -A
git commit -m "feat: Phase 0 enhancements + Phase 1 complete — 63 tests passing"
git push origin main
```

---

## Overall Progress

| Phase | Name | Target | Status | Progress |
|-------|------|--------|--------|----------|
| 0 | Foundation & Infrastructure | Sep 3 | 🟡 Code done, deploy pending | ~85% |
| 1 | Core Agent Graph & Data Contracts | Sep 6 | ✅ Complete | 100% |
| 2 | Verified Replay & SLA Recovery Engine | Sep 9 | 🔴 Not Started | 0% |
| 3 | Evidence System, Safety Layer & HITL | Sep 10 | 🔴 Not Started | 0% |
| 4 | Frontend Command Center | Sep 11 | 🟡 Scaffolded | ~5% |
| 5 | Evaluation & Testing Suite | Sep 12 | 🔴 Not Started | 0% |
| 6 | Live AWS Action Proof | Sep 12 | 🔴 Not Started | 0% |
| 7 | Polish, Submission & Video | Sep 14 | 🔴 Not Started | 0% |

---

## Phase 0 — Foundation & Infrastructure
**Target:** Sep 3, 2026 | **Status:** 🟡 Code complete — AWS deploy pending

### Done (local, uncommitted)
- [x] Repository created within competition window (first commit: `0bbe21e`)
- [x] Directory scaffold: `backend/`, `frontend/`, `infra/`, `plans/`, `sla_catalog/`, `eval_fixtures/`, `scripts/`
- [x] 9 domain models committed (`approval`, `audit`, `availability`, `claim`, `eligibility`, `evidence`, `opportunity`, `signal`, `sla`)
- [x] CDK stacks TypeScript-clean: `recoup-infra-stack.ts`, `recoup-demo-stack.ts`
- [x] CloudWatch log groups in CDK: `/recoup/runtime`, `/recoup/gateway`, `/recoup/api`
- [x] IAM roles in CDK: `RecoupRuntimeRole`, `RecoupGatewayExecutionRole`, `RecoupReadConnectorRole`
- [x] SLA catalog: `sla_catalog/api_gateway/2022-05-05.yaml`
- [x] CI workflow: `.github/workflows/ci.yml`
- [x] Calculator engine (`engines/calculator.py`) + golden unit tests
- [x] SLA resolver engine (`engines/sla_resolver.py`)
- [x] Python project: `pyproject.toml`, `.python-version`
- [x] Next.js frontend initialized (`frontend/`)
- [x] `LICENSE` (MIT) at repo root
- [x] `README.md` (140 lines — stub; full docs in Phase 7)
- [x] `DISCLOSURE.md` at `docs/DISCLOSURE.md`
- [x] Architecture diagram: `architecture/architecture.svg` (full Strands graph SVG)
- [x] AgentCore config: `infra/agentcore-config.yaml` (11 tools, action classes, policy guards)
- [x] Deploy script: `scripts/deploy.sh` (preflight → CDK bootstrap → deploy → S3 sync)
- [x] `@types/node` + `@types/source-map-support` installed; `tsconfig.json` updated

### Remaining — AWS deploy (needs credentials)
- [ ] Run `./scripts/deploy.sh` → CDK deploy to sandbox account
- [ ] Verify DynamoDB tables, S3 buckets, SQS queue, EventBridge rule exist in console
- [ ] AgentCore Runtime instance reachable (register via `infra/agentcore-config.yaml`)
- [ ] AgentCore Gateway: at least one stub tool registered and logged to CloudWatch
- [ ] Cost alarm confirmed in OK state ($10 threshold)
- [ ] Confirm GitHub repository is **public**
- [ ] AWS Builder ID verified at [builder.aws](https://builder.aws)

---

## Phase 1 — Core Agent Graph & Data Contracts
**Target:** Sep 6, 2026 | **Status:** ✅ Complete (63/63 tests, 0 warnings)

### Done
- [x] All 9 domain models — typed, validated, Pydantic v2
- [x] SLA catalog with `source_hash` + `_SERVICE_DIR_ALIASES` normalization
- [x] **`graph/types.py`** — `Graph`, `DeterministicNode`, `AgentNode`, `GraphState`, `PolicyDecision`, `IncidentHypothesis`, `CaseOutcome`, `NodeContext`, `ToolContext`, `ErrorDisposition`, `Edge`, `ConditionalEdge`
- [x] **`graph/nodes.py`** — All 11 stub node implementations; deterministic, no LLM required
- [x] **`graph/recoup_graph.py`** — Full graph wired; conditional edge at `risk_policy_gate`; `build_recoup_graph()` validated at import time
- [x] **`graph/state_machine.py`** — DynamoDB atomic transitions with optimistic locking; in-memory fallback for unit tests
- [x] **`hooks/tracing.py`** — `RecoupTracingHooks`: BeforeNodeCall, AfterNodeCall, BeforeToolCall, AfterToolCall, OnError, RedactionHook; tool allowlist enforced
- [x] **`tools/aws_tools.py`** — 8 AWS read tools (CloudWatch, Health, Cost Explorer, CloudTrail, Support)
- [x] **`tools/internal_tools.py`** — 3 internal tools (`store_evidence`, `create_approval_request`, `simulate_support_case`)
- [x] **`tools/ec2_tools.py`** — `stop_demo_instance` with allowlist guard (Phase 6 ready)
- [x] **`tools/registry.py`** — `TOOL_REGISTRY`: 14 tools, action classes, Lambda targets, allowed nodes
- [x] **`adapters/replay.py`** — `ReplayAdapter` + `CANONICAL_SCENARIO` ($1,840 golden scenario)
- [x] **`adapters/agentcore.py`** — `AgentCoreAdapter` with `register_all_tools()`
- [x] **`api/main.py`** — FastAPI + CORS + `/health` + `/api/config`
- [x] **`api/routes/opportunities.py`** — list, get, run, trace endpoints
- [x] **`api/routes/approvals.py`** — list pending, approve, decline endpoints
- [x] **`api/routes/replay.py`** — `POST /api/replay/run`, `GET /api/replay/scenarios`
- [x] **63 unit tests pass** — models, graph structure, graph end-to-end, state machine, SLA catalog
- [x] **Zero `DeprecationWarning`s** — `datetime.utcnow()` replaced with `datetime.now(timezone.utc)` everywhere

### Definition of Done — All checks green
| Check | Result |
|-------|--------|
| Domain models import + validate | ✅ |
| Graph instantiates; all edges resolve | ✅ |
| State machine DynamoDB optimistic locking | ✅ |
| SLA catalog loads; source_hash CI test passes | ✅ |
| 14 tools registered with action classes | ✅ |
| Hooks fire on stub node calls | ✅ |
| 63/63 unit tests pass; no LLM calls | ✅ |
| `-W error::DeprecationWarning` clean | ✅ |

---

## Phase 2 — Verified Replay & SLA Recovery Engine
**Target:** Sep 9, 2026 | **Status:** 🔴 Not Started

### Remaining
- [ ] Canonical replay seed artifacts committed to `eval_fixtures/` (immutable event JSON, metric series, billing snapshot)
- [ ] `normalize_event` node parses both replay and live schema
- [ ] `incident_correlation` agent correlates synthetic API Gateway SLA incident
- [ ] `sla_contract_resolver` loads correct `2022-05-05` contract by incident date
- [ ] `availability_calculator` produces $1,840 claim value (deterministic)
- [ ] `eligibility_checker` passes all canonical criteria
- [ ] `claim_packager` produces complete `ClaimPackage`
- [ ] Full replay run: reproducible $1,840 result in ≤ 60 s wall time
- [ ] `scripts/replay_run.py` seeds + executes replay headlessly

---

## Phase 3 — Evidence System, Safety Layer & HITL
**Target:** Sep 10, 2026 | **Status:** 🔴 Not Started

### Remaining
- [ ] `evidence/` module: collector, sanitizer, manifest builder
- [ ] Evidence stored to S3 with SHA-256 hash
- [ ] Deterministic redaction — fails closed on high-risk patterns; raw evidence never in LLM context
- [ ] `safety/` module: Cedar policy rules, autonomy class enforcement
- [ ] AgentCore Policy authorization on all mutating tools
- [ ] `approval/` module: HITL flow (request → token → decision)
- [ ] DynamoDB-backed approval record with TTL
- [ ] All `class_c_action` tools require explicit approval before execution

---

## Phase 4 — Frontend Command Center
**Target:** Sep 11, 2026 | **Status:** 🟡 Scaffolded (~5%)

### Done
- [x] Next.js 14 + TypeScript initialized (`frontend/`)
- [x] `layout.tsx` and root `page.tsx` stub

### Remaining
- [ ] Tailwind CSS + shadcn/ui installed and configured
- [ ] Command Center dashboard (opportunity list, recovered value, system status)
- [ ] Opportunity Detail view (status timeline, financial summary, confidence)
- [ ] Evidence Room view (checklist, sanitized preview, redaction count, hashes)
- [ ] Decision Inbox view (pending approvals with approve/reject)
- [ ] Agent Trace view (Strands graph visualization, per-node logs)
- [ ] Evaluation / Quality view (scorecard, pass/fail table)
- [ ] SIMULATION / LIVE AWS ACTION badges visible on all demo paths
- [ ] Backend API integration (polling or WebSocket for live trace)
- [ ] Correct empty / loading / error states on all views

---

## Phase 5 — Evaluation & Testing Suite
**Target:** Sep 12, 2026 | **Status:** 🔴 Not Started

### Done
- [x] `test_calculator.py` — golden calculator unit tests (part of 63-test suite)

### Remaining
- [ ] ≥ 40 eval scenarios across 8 categories (golden-path, edge, adversarial, safety, HITL, evidence, SLA boundary, tool-failure)
- [ ] Evaluation runner script + scorecard JSON output
- [ ] 100% golden-path success rate across 20 consecutive replay runs
- [ ] ≥ 92% overall scenario success rate
- [ ] ≥ 98% evidence recall rate
- [ ] Zero unsafe action tolerance (all `class_c_action` tests reject without approval)
- [ ] Scorecard visible in frontend Evaluation view
- [ ] `eval_fixtures/` populated with scenario JSON files

---

## Phase 6 — Live AWS Action Proof
**Target:** Sep 12, 2026 | **Status:** 🔴 Not Started

### Remaining
- [ ] EC2 instance (`RecoupDemo=true` tag) deployed via `RecoupDemoStack`
- [ ] `stop_demo_instance` registered in AgentCore Gateway with Cedar policy guard
- [ ] CloudWatch utilization check before recommending stop
- [ ] CloudTrail lookup to confirm no blocking ownership
- [ ] HITL approval required before stop executes
- [ ] CloudTrail confirms actual `StopInstances` API call in evidence
- [ ] Live path visible in frontend Decision Inbox with **LIVE AWS ACTION** badge

---

## Phase 7 — Polish, Submission & Video
**Target:** Sep 14, 2026 | **Status:** 🔴 Not Started

### Done
- [x] Architecture diagram: `architecture/architecture.svg`

### Remaining
- [ ] README fully expanded (problem, demo GIF, architecture, full setup instructions)
- [ ] Video ≤ 5:00, public on YouTube/Vimeo (problem / audience / why / demo)
- [ ] Live URL accessible in incognito; replay works without AWS credentials
- [ ] Three builder.aws posts published (+0.6 bonus points)
- [ ] Devpost submission form completed
- [ ] Final review against judging rubric

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
│   └── deploy.sh            ✅ full deploy sequence
├── sla_catalog/api_gateway/ ✅ 2022-05-05.yaml
├── docs/DISCLOSURE.md       ✅
├── eval_fixtures/           ❌ empty — Phase 5
└── plans/                   ✅ all 8 phase plans
```

---

## Critical Path — 13 Days

| Day | Action |
|-----|--------|
| **Sep 1 (today)** | `git push` all local work · `./scripts/deploy.sh` · verify AWS resources |
| **Sep 2–3** | Phase 2: replay engine → $1,840 deterministic end-to-end |
| **Sep 4–6** | Phase 3: evidence, redaction, Cedar policy, HITL approval flow |
| **Sep 5–7** | Phase 4: frontend views (overlaps Phase 3) |
| **Sep 7–9** | Phase 5: eval suite (40 scenarios, scorecard) + Phase 6: live EC2 demo |
| **Sep 10–12** | Phase 7: README expansion, video recording |
| **Sep 13–14** | Devpost submit · builder.aws posts · final rubric check |

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Complete |
| 🟡 | In progress / partial |
| 🔴 | Not started |
| ❌ | Needs work |
