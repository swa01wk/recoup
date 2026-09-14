# Recoup — AWS Autonomous Cloud Spend Recovery Agent

> **AWS provides the FinOps intelligence; Recoup closes the recovery loop.**  
> **Investigate. Prove. Approve. Recover. Verify.**

Recoup is a background [Strands Agents](https://strandsagents.com) graph that detects unintended AWS spend, investigates surrounding evidence, applies deterministic Cedar policy, involves humans at real approval boundaries, executes bounded AWS actions, and records verified recovery — closing the complete loop from anomaly to auditable outcome.

Built for the [AWS Agents for Humans Hackathon](https://agentsforhumans.devpost.com/) (Aug 10 – Sep 14, 2026).

---

## Judge demo (AWS production — J-FULL)

| | URL |
|--|-----|
| **UI** | https://pdkeexzwxr.us-east-1.awsapprunner.com |
| **API** | https://qawwrm7kzy.us-east-1.awsapprunner.com |

Flow: `/scan` → **Demo Scan** → `/opportunities` → **Start Recovery** → Approve → `/recovery`.  
Ops: [docs/archive/ops/production-hosting.md](docs/archive/ops/production-hosting.md) · [docs/judge-demo.md](docs/judge-demo.md).  
Production: `POST /api/test/reset` returns **403**.

---

## Quick Start (Local Demo)

**Primary operator journey (J-FULL):** [docs/operator-journey.md](docs/operator-journey.md)

1. **Start stack:** `docker compose up -d` → frontend [http://localhost:3000](http://localhost:3000) · backend port **8000**
2. **`/scan`** — consent → **Demo Scan** (9 AWS scanners) → lands on **`/opportunities`**
3. Pick findings (demo: **three different services**) → **Start Recovery** → **`/opportunities/{id}`**
4. **Approve** (SNS recovery report) · **Investigate Further** · **Decline** — claim-bound HITL
5. **`/recovery`** — Recovery Ledger (Remaining / Pending Approval / Recovered)
6. Optional sidebar **↺ Reset Demo Data** between runs (your session only — other tabs unaffected)

**Changelog:** [release_notes.md](release_notes.md)

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

## Primary demo (J-FULL)

Real account scan → promote → HITL on opportunity detail → Recovery Ledger + SNS on approve.

**Sidebar:** Opportunities · Account Scanner · Recovery Ledger.

Canonical doc: [docs/operator-journey.md](docs/operator-journey.md). SLA replay engine remains for **unit tests / scorecard** only (no public `/api/replay` or `/replay` UI).

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
| Financial math correctness | 100% | ✓ **419** backend tests collected (0 warnings) |
| Playwright E2E tests | 127 tests | ✓ 16 specs · **J-FULL** + PSC + J2–J9 + 13 SEC |
| Unsafe external actions | 0 | ✓ quality gate |
| Replay P95 | < 60s | ✓ ~23 ms |
| Tampered claim rejection | 100% | ✓ 409 on hash/amount/version tamper |

See `GET /api/quality/scorecard` for live gate status.  
Primary journey: [docs/operator-journey.md](docs/operator-journey.md). Doc index: [docs/README.md](docs/README.md).

---

## Repository Structure

```
recoup/
├── backend/          FastAPI · Strands graph · scanners · HITL
├── frontend/         Next.js UI · e2e/ (Playwright)
├── docs/             Judge demo, operator journey, API reference (see docs/README.md)
├── infra/cdk/        AWS CDK stacks
├── architecture/     architecture.svg
└── eval_fixtures/    Golden replay fixtures
```

---

## Development Setup

**Prerequisites:** Python 3.12+, Node 20+, AWS CLI (optional for live demos)

Copy [`.env.example`](.env.example) to `.env` at the repo root (backend reads it via settings).

### LLM provider (Strands reasoning nodes)

Strands agent steps (investigate, explain, plan, etc.) call an LLM selected by **`LLM_PROVIDER`**. Financial math, Cedar policy, and approvals stay deterministic — the LLM only does narrative reasoning. If the provider is unavailable, nodes fall back to simulation stubs so local demos and CI still run.

| `LLM_PROVIDER` | When to use | Required config |
|----------------|-------------|-----------------|
| **`bedrock`** (default) | Production and AWS hackathon path | AWS credentials (or runtime IAM role); `BEDROCK_MODEL_ID` (default `us.amazon.nova-pro-v1:0`); `BEDROCK_REGION` (default `us-east-1`) |
| **`openai`** | Local dev when Bedrock model access is pending | `OPENAI_API_KEY`; optional `OPENAI_MODEL_ID` (default `gpt-4o`) |

Check active provider (no secrets): `curl -s http://localhost:8000/api/config | jq '.llm_provider, .bedrock_model, .openai_model_id'`

AgentCore runtime, gateway, and infra IAM are documented in [docs/archive/internal/plans/aws-requirements.md](docs/archive/internal/plans/aws-requirements.md). Provider wiring lives in `backend/src/recoup/agents/strands_agents.py`.

See [docs/archive/ops/production-hosting.md](docs/archive/ops/production-hosting.md) for the live App Runner demo.  
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
| Backend unit tests | 419 collected | `cd backend && pytest tests/` |
| Playwright E2E | 127 (16 specs) | `cd frontend && npx playwright test` |
| Primary operator journey | J-FULL | [docs/operator-journey.md](docs/operator-journey.md) |
| Extended test map | J1–J12 + SEC + J-FULL | [USER_JOURNEY_CHECKLIST.md](USER_JOURNEY_CHECKLIST.md) |
| Quality gates | 6 | `GET /api/quality/scorecard` |

---

## Disclosure

This project was created fresh during the AWS Agents for Humans Hackathon (Aug 10 – Sep 14, 2026). See [docs/archive/submit/DISCLOSURE.md](docs/archive/submit/DISCLOSURE.md).

---

## License

[MIT](LICENSE)
