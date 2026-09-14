# Recoup — Documentation Index

**Project:** AWS Autonomous Cloud Spend Recovery Agent  
**Hackathon:** AWS Agents for Humans (Aug 10 – Sep 14, 2026)  
**Last updated:** Sep 14, 2026  
**Shipped:** J-FULL on App Runner · **Submission:** video + Devpost ([submit/submission-record.md](archive/submit/submission-record.md))

**Archived docs:** [archive/](archive/) — meta, superseded, optional depth, ops, submit (moved, not deleted)

---

## Key numbers (canonical — update here first)

| Metric | Value | Verify with |
|--------|-------|-------------|
| Backend unit tests | **416** collected (live-mode skips as configured) | `cd backend && pytest --collect-only -q` |
| Playwright E2E | **125** tests in **16** spec files | `cd frontend && npx playwright test --list` |
| Smoke tests | run `npx playwright test --grep @smoke` | count changes over time |
| Graph nodes | **11** (6 deterministic · 5 agent) | `backend/src/recoup/graph/recoup_graph.py` |
| Tools in `TOOL_REGISTRY` | **13** | `backend/src/recoup/tools/registry.py` |
| Tools in Gateway YAML | **12** | `infra/agentcore-config.yaml` (no `get_support_case_status` entry yet) |
| Scanners | **9** | `backend/src/recoup/api/routes/scan.py` |
| Quality scorecard gates | **6** | `backend/src/recoup/api/routes/quality.py` |
| Primary UI nav | **3** links: `/opportunities`, `/scan`, `/recovery` | `frontend/src/components/layout/sidebar.tsx` |
| App routes | `/` → `/opportunities`; `/approvals`, `/quality` redirect; `/replay` **removed** (API replay remains) | `frontend/src/app/` |
| Local backend port | **8000** (Docker, Playwright); **8010** (native uvicorn per `.env.example`) | `docker-compose.yml`, `.env.example` |
| **Production UI (J-FULL)** | https://pdkeexzwxr.us-east-1.awsapprunner.com | [production-hosting.md](archive/ops/production-hosting.md) · [runbook](archive/ops/app-runner-deployment-runbook.md) |
| **Production API** | https://qawwrm7kzy.us-east-1.awsapprunner.com | `./scripts/smoke_production_api.sh` |
| Golden credit value | **~$0.35** | canonical SLA replay |
| Demo scan savings | **$87.82/mo** (full scan aggregate) | Account Scanner full run |
| **Primary operator journey** | **J-FULL** (scan → 3 HITL paths → ledger + SNS) | **[operator-journey.md](operator-journey.md)** |
| Extended test map | J1–J12 + 13 SEC + J-FULL | [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) |
| Recovery on promote | `backend/src/recoup/recovery/` → `RecoveryAssessment` on trace + approve gates | [backend-code-architecture.md](backend-code-architecture.md) · [operator-journey.md](operator-journey.md) |

---

## Operator guides (start here)

| Document | What it covers |
|---------|---------------|
| **[operator-journey.md](operator-journey.md)** | **Primary lifecycle (J-FULL)** — frontend, backend, HITL, ledger, SNS, testing |
| **[judge-demo.md](judge-demo.md)** | Judge-facing walkthrough |
| **[demo-playbook.md](demo-playbook.md)** | S5/J-FULL first; optional legacy scenarios |
| **[local-dev-and-testing.md](local-dev-and-testing.md)** | Local setup, ports, Playwright, live AWS safety |
| **[archive/ops/production-hosting.md](archive/ops/production-hosting.md)** | AWS-all deploy (App Runner API + UI, Amplify optional, SNS, smoke) |
| **[archive/ops/app-runner-deployment-runbook.md](archive/ops/app-runner-deployment-runbook.md)** | App Runner deploy troubleshooting, CORS/URL coupling, verification |
| **[archive/ops/demo-vs-platform-segregation.md](archive/ops/demo-vs-platform-segregation.md)** | Platform vs demo scanner stacks, safe teardown |
| **[archive/ops/oct-demo-ops.md](archive/ops/oct-demo-ops.md)** | Credits / $150 plan ops through Oct 31 |

---

## Architecture (code-first)

| Document | What it covers |
|---------|---------------|
| **[recoup-overall-architecture.md](recoup-overall-architecture.md)** | End-to-end system (J-FULL + optional agent depth) |
| **[frontend-code-architecture.md](frontend-code-architecture.md)** | Next.js routes, hooks, components |
| **[backend-code-architecture.md](backend-code-architecture.md)** | FastAPI, scanners, HITL, persistence |
| **[agent-code-architecture.md](agent-code-architecture.md)** | 11-node graph, Strands, replay adapter, tools |

---

## API & demo data

| Document | What it covers |
|---------|---------------|
| **[api-reference.md](api-reference.md)** | FastAPI endpoints, errors, curl examples |
| **[scanner-coverage.md](scanner-coverage.md)** | 9 scanners: logic and evidence fields |
| **[demo-workloads.md](demo-workloads.md)** | RecoupDemoWorkloadsStack / scenario tags |

---

## Archive (reference only)

| Folder | Examples |
|--------|----------|
| [archive/meta/](archive/meta/) | stale-documents, code-changes-timing, stale-code-removal-plan |
| [archive/superseded/](archive/superseded/) | architecture-overview, agent-graph, frontend-guide |
| [archive/optional-depth/](archive/optional-depth/) | replay-system, sla-calculator, tool-registry, … |
| [archive/ops/](archive/ops/) | **production-hosting**, segregation, oct-demo-ops, IAM, cross-account, stopped-services |
| [archive/submit/](archive/submit/) | video-script, submission-record, DISCLOSURE, ci-guide |

---

## Repo root (related)

| File | Role |
|------|------|
| [../release_notes.md](../release_notes.md) | **Shipped changes & ops flags** (maintain on each release) |
| [../USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) | Test ↔ journey map |
| [../README.md](../README.md) | Project overview |
| [archive/internal/](archive/internal/) | Internal phase tracker & build plans (optional for judges) |

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

**Production smoke (no local stack):**

```bash
./scripts/smoke_production_api.sh https://qawwrm7kzy.us-east-1.awsapprunner.com
./scripts/prod_journey_hitl_smoke.sh
./scripts/post_change_segregation_smoke.sh
# Browser: https://pdkeexzwxr.us-east-1.awsapprunner.com/scan → Demo Scan (J-FULL)
```
