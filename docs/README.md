# Recoup — Documentation Index

**Project:** AWS Autonomous Cloud Spend Recovery Agent  
**Hackathon:** AWS Agents for Humans (Aug 10 – Sep 14, 2026)  
**Last updated:** Sep 11, 2026  
**Phases complete:** 0–6f, 8, 9 · Phase 7 (video/submission) in progress

---

## Key numbers (canonical — update here first)

| Metric | Value | Verify with |
|--------|-------|-------------|
| Backend unit tests | **420** collected (15 skipped live-mode) | `cd backend && pytest --collect-only -q` |
| Playwright E2E | **279** tests in **28** spec files | `cd frontend && npx playwright test --list` |
| Smoke tests | run `npx playwright test --grep @smoke` | count changes over time |
| Graph nodes | **11** (6 deterministic · 5 agent) | `backend/src/recoup/graph/recoup_graph.py` |
| Tools in `TOOL_REGISTRY` | **13** | `backend/src/recoup/tools/registry.py` |
| Tools in Gateway YAML | **12** | `infra/agentcore-config.yaml` (no `get_support_case_status` entry yet) |
| Scanners | **9** | `backend/src/recoup/api/routes/scan.py` |
| Quality scorecard gates | **6** | `backend/src/recoup/api/routes/quality.py` |
| Primary UI nav | **3** links: `/opportunities`, `/scan`, `/recovery` | `frontend/src/components/layout/sidebar.tsx` |
| App routes | `/` → `/opportunities`; `/approvals`, `/quality` redirect; `/replay` deep link (not in nav) | `frontend/src/app/` |
| Local backend port | **8000** (Docker, Playwright); **8010** (native uvicorn per `.env.example`) | `docker-compose.yml`, `.env.example` |
| Golden credit value | **~$0.35** | canonical SLA replay |
| Demo scan savings | **$87.82/mo** (full scan aggregate) | Account Scanner full run |
| Domain models | 9 core Pydantic v2 models | `docs/domain-models.md` |
| **Primary operator journey** | **J-FULL** (scan → 3 HITL paths → ledger + SNS) | **[operator-journey.md](operator-journey.md)** |
| Extended test map | J1–J12 + 13 SEC + J-FULL | `USER_JOURNEY_CHECKLIST.md` |
| Stale code cleanup plan | Phased removal of non–J-FULL surfaces | **[stale-code-removal-plan.md](stale-code-removal-plan.md)** |
| Code changes timing | **Now vs later** — freeze before submit | **[code-changes-timing.md](code-changes-timing.md)** |
| Stale documents | Misleading vs historical vs canonical | **[stale-documents.md](stale-documents.md)** |

---

## Operator guides

| Document | What it covers |
|---------|---------------|
| **[operator-journey.md](operator-journey.md)** | **Start here — primary lifecycle (J-FULL)** — frontend, backend, HITL, ledger, SNS, testing |
| **[judge-demo.md](judge-demo.md)** | Judge-facing walkthrough aligned with J-FULL |
| **[demo-playbook.md](demo-playbook.md)** | S5/J-FULL first; optional S1–S4, S7–S9 (API / legacy proofs) |
| **[frontend-guide.md](frontend-guide.md)** | Three-link nav, routes, components, API cheat sheet |
| **[local-dev-and-testing.md](local-dev-and-testing.md)** | Local setup, ports, Playwright, live AWS safety |

---

## Technical reference

| Document | What it covers |
|---------|---------------|
| **[architecture-overview.md](architecture-overview.md)** | System architecture, tech stack, data flow |
| **[agent-graph.md](agent-graph.md)** | 11 graph nodes, tools, edge conditions |
| **[domain-models.md](domain-models.md)** | Pydantic v2 domain models |
| **[api-reference.md](api-reference.md)** | FastAPI endpoints, errors, curl examples |
| **[tool-registry.md](tool-registry.md)** | 13 tools: action classes, allowlists |
| **[sla-calculator.md](sla-calculator.md)** | SLA formula, credit tiers, golden test |
| **[replay-system.md](replay-system.md)** | Verified Replay, determinism, scenarios |
| **[state-machine.md](state-machine.md)** | Opportunity states, transitions, locking |
| **[tracing-hooks.md](tracing-hooks.md)** | Hooks, allowlists, ToolAudit |
| **[agentcore-integration.md](agentcore-integration.md)** | AgentCore Harness + Gateway |
| **[scanner-coverage.md](scanner-coverage.md)** | 9 scanners: logic and evidence fields |
| **[iam-roles.md](iam-roles.md)** | IAM roles and permissions |
| **[iam-architecture.md](iam-architecture.md)** | STS AssumeRole hierarchy |
| **[cross-account-onboarding.md](cross-account-onboarding.md)** | Customer onboarding |
| **[demo-workloads.md](demo-workloads.md)** | RecoupDemoWorkloadsStack |
| **[infrastructure-runbook.md](infrastructure-runbook.md)** | Deploy, inventory, troubleshooting |
| **[budget-safety.md](budget-safety.md)** | Budget alerts, teardown |
| **[deployment.md](deployment.md)** | Vercel + Railway/Fly.io |
| **[submission-record.md](submission-record.md)** | Devpost checklist |
| **[ci-guide.md](ci-guide.md)** | CI jobs, ship gates |
| **[video-script.md](video-script.md)** | Demo video script |
| **[builder-posts.md](builder-posts.md)** | builder.aws post outlines |
| **[stopped-services.md](stopped-services.md)** | Stopped demo service savings |
| **[DISCLOSURE.md](DISCLOSURE.md)** | Competition disclosure |

---

## Root-level pointers (stubs)

Legacy filenames at repo root redirect here:

| Stub | Canonical doc |
|------|----------------|
| [../DEMO_SCENARIOS.md](../DEMO_SCENARIOS.md) | [demo-playbook.md](demo-playbook.md) |
| [../FRONTEND_GUIDE.md](../FRONTEND_GUIDE.md) | [frontend-guide.md](frontend-guide.md) |
| [../HACKATHON_DEMO.md](../HACKATHON_DEMO.md) | [judge-demo.md](judge-demo.md) |
| [../LIVE_TESTING_GUIDE.md](../LIVE_TESTING_GUIDE.md) | [local-dev-and-testing.md](local-dev-and-testing.md) |
| [../USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) | Test coverage source of truth |
| [../README.md](../README.md) | Project overview |
| [../STATUS.md](../STATUS.md) | Internal phase tracker |

**Archive:** [archive/](archive/) — completed checklists (not maintained)

---

## Test quick start

```bash
# All Playwright tests (backend on 8000 by default)
cd frontend && npx playwright test

# Smoke only
cd frontend && npx playwright test --grep @smoke

# Backend unit tests
cd backend && pytest tests/

# Quality scorecard (6 gates)
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
```

Native dev with `.env` on port **8010**: set `NEXT_PUBLIC_API_URL=http://localhost:8010` and `PLAYWRIGHT_BACKEND_PORT=8010` for E2E.
