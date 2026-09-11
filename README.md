# Recoup — AWS Autonomous Cloud Spend Recovery Agent

[![CI](https://github.com/swa01wk/recoup/actions/workflows/ci.yml/badge.svg)](https://github.com/swa01wk/recoup/actions/workflows/ci.yml)

> **AWS provides the FinOps intelligence; Recoup closes the recovery loop.**  
> **Investigate. Prove. Approve. Recover. Verify.**

Recoup is a background [Strands Agents](https://strandsagents.com) graph that detects unintended AWS spend, investigates surrounding evidence, applies deterministic Cedar policy, involves humans at real approval boundaries, executes bounded AWS actions, and records verified recovery — closing the complete loop from anomaly to auditable outcome.

Built for the [AWS Agents for Humans Hackathon](https://agentsforhumans.devpost.com/) (Aug 10 – Sep 14, 2026).

---

## Quick Start (Local Demo)

**Primary operator journey (J-FULL):** [docs/operator-journey.md](docs/operator-journey.md)

1. **Start stack:** `docker compose up -d` → frontend [http://localhost:3000](http://localhost:3000) · backend port **8000**
2. **`/scan`** — consent → **Demo Scan** (9 AWS scanners) → lands on **`/opportunities`**
3. Pick findings (demo: **three different services**) → **Start Recovery** → **`/opportunities/{id}`**
4. **Approve** (SNS recovery report) · **Investigate Further** · **Decline** — claim-bound HITL
5. **`/recovery`** — Recovery Ledger (Remaining / Pending Approval / Recovered)
6. Optional sidebar **↺ Reset Demo Data** between runs

**Verify:** `curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'`

**E2E proof:** `cd frontend && npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts`

> **Native dev:** `.env.example` uses backend port **8010** — set `NEXT_PUBLIC_API_URL=http://localhost:8010`.  
> **Docs index:** [docs/README.md](docs/README.md) · **Judge walkthrough:** [docs/judge-demo.md](docs/judge-demo.md)

---

## How It Works (V1.1 Execution Loop)

| Step | Label | What happens |
|------|-------|--------------|
| 1 | **Detect** | Cost anomaly or waste pattern opens a spend incident |
| 2 | **Investigate** | Strands agent collects cost, utilization, CloudTrail, tag, dependency evidence |
| 3 | **Correlate** | Connect spend to underlying resource graph and recent changes |
| 4 | **Explain** | Generate root-cause hypothesis; classify spend intent |
| 5 | **Prove** | Assemble Recovery Case with confidence and supporting evidence |
| 6 | **Plan** | Strands agent drafts claim package / recovery plan |
| 7 | **Policy** | Cedar policy gate (deterministic, not LLM) evaluates action risk |
| 8 | **Approve** | HITL approval: evidence + impact + risk + exact action + rollback |
| 9 | **Remediate** | Execute only approved/bounded AWS actions via scoped IAM role |
| 10 | **Verify** | Validate resource state, application health, financial impact |
| 11 | **Record** | Close case in Recovery Ledger (estimated vs realized recovery) |

---

## Primary demo vs optional depth

| Layer | What it shows |
|-------|----------------|
| **J-FULL (product UI)** | Real account scan → promote → HITL on opportunity detail → Recovery Ledger + SNS on approve — **sidebar: Opportunities · Account Scanner · Recovery Ledger** |
| **Optional — SLA verified replay** | API Gateway credit path (~**$0.35**), full 11-node graph + SSE — **`/replay` or API only** (not in sidebar). See [docs/replay-system.md](docs/replay-system.md) |
| **Optional — EC2 live stop** | `POST /api/ec2-demo/*` after approve — no dashboard card; see [docs/demo-playbook.md](docs/demo-playbook.md) S3 |

---

## Why Not [X]?

**Why not ProsperOps?**  
ProsperOps is a mature autonomous FinOps optimizer, especially for commitments and workload scheduling. Recoup is an autonomous cloud-spend investigator and recovery operator focused on cross-signal causal investigation, evidence, risk-tiered HITL remediation, and technical + financial verification.

**Why not AWS FinOps Agent?**  
AWS FinOps Agent investigates anomalies and surfaces recommendations. Recoup goes further: evidence-backed Recovery Case, Cedar policy, explicit human approval, bounded AWS action, verification, and Recovery Ledger.

**Why not AWS Compute Optimizer?**  
Compute Optimizer identifies opportunities. Recoup investigates context, establishes intent, packages evidence, chooses a safe recovery workflow, executes under policy, and verifies the outcome.

---

## Frequently Asked Questions

**"How do you prevent hallucinated destructive actions?"**  
Evidence requirements, allowlists, environment protections, and approval rules are deterministic. Execution validates identifiers and policy before acting.

**"How do you prove savings?"**  
The Recovery Ledger stores baseline, estimated recovery, executed change, post-action checks, and cost delta. Estimated and realized savings stay separate.

More detail: [docs/judge-demo.md](docs/judge-demo.md) · [docs/demo-playbook.md](docs/demo-playbook.md)

---

## Architecture

![Recoup Architecture](architecture/architecture.svg)

```
Frontend (Next.js 16)
  → FastAPI (auth · session · SSE streaming)
    → Amazon Bedrock AgentCore Runtime
      → Strands Graph (11 nodes: 5 agent · 6 deterministic)
        → AgentCore Gateway (13 narrow typed tools)
          → AgentCore Policy (Cedar · default deny for RED/BLACK)
            → AWS services (CloudWatch · Cost Explorer · CloudTrail · EventBridge)
              → DynamoDB (state) · S3 (evidence) · SQS (events)
```

---

## Evaluation Results

| Metric | Target | Status |
|--------|--------|--------|
| Golden-path success (20 runs) | 20/20 (100%) | ✓ 100% |
| Overall scenario success | ≥ 92% | ✓ 47/47 scenarios defined |
| Financial math correctness | 100% | ✓ **420** backend tests collected (0 warnings) |
| Playwright E2E tests | 279 tests | ✓ 28 specs · **J-FULL** + J1–J12 + 13 SEC |
| Unsafe external actions | 0 | ✓ quality gate |
| Replay P95 | < 60s | ✓ ~23 ms |
| Tampered claim rejection | 100% | ✓ 409 on hash/amount/version tamper |

See `GET /api/quality/scorecard` for live gate status.  
Primary journey: [docs/operator-journey.md](docs/operator-journey.md). Full test map: [USER_JOURNEY_CHECKLIST.md](USER_JOURNEY_CHECKLIST.md). **Now vs later (code):** [docs/code-changes-timing.md](docs/code-changes-timing.md). Stale code cleanup: [docs/stale-code-removal-plan.md](docs/stale-code-removal-plan.md).

---

## Repository Structure

```
recoup/
├── backend/               FastAPI API + Strands graph + deterministic engines
├── frontend/              Next.js UI (opportunities-first) · e2e/ (28 Playwright specs)
├── docs/                  Documentation index + playbooks (see docs/README.md)
├── infra/cdk/             AWS CDK stacks
├── eval_fixtures/         Immutable replay seed artifacts
├── USER_JOURNEY_CHECKLIST.md   Test ↔ journey map
├── STATUS.md              Phase tracker
└── DEMO_SCENARIOS.md      → stub; see docs/demo-playbook.md
```

---

## Development Setup

**Prerequisites:** Python 3.12+, Node 20+, AWS CLI (optional for live demos)

See [docs/deployment.md](docs/deployment.md) for public demo deployment (Vercel + Railway/Fly.io).  
See [docs/local-dev-and-testing.md](docs/local-dev-and-testing.md) for ports and Playwright.

```bash
# Backend
cd backend && pip install -e ".[dev]"
pytest tests/ -v -W error::DeprecationWarning

# Frontend
cd frontend && npm install && npm run dev

# Playwright
cd frontend && npx playwright test --grep @smoke
cd frontend && npx playwright test
```

### Test coverage

| Suite | Count | Command |
|-------|------:|---------|
| Backend unit tests | 420 collected | `cd backend && pytest tests/` |
| Playwright E2E | 279 (28 specs) | `cd frontend && npx playwright test` |
| Primary operator journey | J-FULL | [docs/operator-journey.md](docs/operator-journey.md) |
| Extended test map | J1–J12 + SEC + J-FULL | [USER_JOURNEY_CHECKLIST.md](USER_JOURNEY_CHECKLIST.md) |
| Quality gates | 6 | `GET /api/quality/scorecard` |

---

## Disclosure

This project was created fresh during the AWS Agents for Humans Hackathon (Aug 10 – Sep 14, 2026). See [docs/DISCLOSURE.md](docs/DISCLOSURE.md).

---

## License

[MIT](LICENSE)
