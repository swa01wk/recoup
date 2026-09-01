# Recoup — AWS Autonomous Cloud Spend Recovery Agent

> **Every cloud dollar accounted for — humans only make the decisions that require humans.**

Recoup is a background [Strands Agents](https://strandsagents.com) graph that finds recoverable or preventable AWS spend, investigates the cause, assembles evidence, and safely handles the operational work. It involves humans only at real policy boundaries.

```
OBSERVE  →  INVESTIGATE  →  RECOVER  →  PREVENT
              humans enter only at policy boundaries
```

Built for the [AWS Agents for Humans Hackathon](https://agentsforhumans.devpost.com/) (Aug 10 – Sep 14, 2026).

---

## The Two Demo Proofs

| Proof | What it shows |
|-------|--------------|
| **Verified Replay** | Synthetic API Gateway SLA breach → `99.9306%` uptime → 10% tier → **$1,840 potential credit** — complete workflow, deterministic math, human approval, simulated Support submission |
| **Live AWS Action** | Real EC2 `t3.micro` with `RecoupDemo=true` → CloudWatch confirms idle → human approval → Cedar policy → `StopInstances` → verified stopped state |

---

## Quick Start (Judge Demo)

1. Visit **[https://recoup.example.com]** — no AWS credentials required
2. Click **▶ Run Canonical Replay**
3. Watch the Strands graph execute node-by-node in real time
4. Approve the `$1,840` SLA claim in the **Decision Inbox**
5. View the complete **Agent Trace** with policy decisions and evidence hashes

---

## Architecture

![Recoup Architecture](architecture/architecture.png)

```
Frontend (Next.js)
  → FastAPI (auth · session · SSE streaming)
    → Amazon Bedrock AgentCore Runtime
      → Strands Graph (11 nodes: 4 deterministic · 5 agent · 2 hybrid)
        → AgentCore Gateway (12 narrow typed tools)
          → AgentCore Policy (Cedar · default deny for RED/BLACK)
            → AWS services (CloudWatch · Cost Explorer · CloudTrail · EventBridge)
              → DynamoDB (state) · S3 (evidence) · SQS (events)
```

---

## Repository Structure

```
recoup/
├── backend/               FastAPI API + Strands graph + deterministic engines
│   ├── src/recoup/
│   │   ├── models/        Pydantic domain models (all typed, no raw dicts)
│   │   ├── engines/       Deterministic SLA calculator + contract resolver
│   │   ├── graph/         Strands Graph node definitions + edges
│   │   ├── hooks/         BeforeNodeCall / AfterToolCall / redaction hooks
│   │   ├── evidence/      Evidence collector + sanitizer (fail-closed redaction)
│   │   ├── adapters/      Live AWS adapter + Verified Replay adapter
│   │   ├── tools/         Narrow tool implementations (no raw boto3 to agents)
│   │   ├── api/           FastAPI routers + SSE streaming
│   │   ├── safety/        Autonomy class enforcement
│   │   └── approval/      HITL approval lifecycle
│   └── tests/             Unit · tool-contract · trajectory · semantic · e2e
├── frontend/              Next.js 14 Command Center UI
├── infra/cdk/             AWS CDK stacks (infra + demo)
├── infra/policy/          Cedar policies for AgentCore Policy
├── sla_catalog/           Human-verified SLA contracts (source_hash required)
├── eval_fixtures/         Immutable replay seed artifacts
├── scripts/               Reset demo instance · generate fixtures · assert ship gates
├── plans/                 Phase-by-phase implementation plans
└── architecture/          Architecture diagram
```

---

## Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| **LLMs propose; contracts decide** | Deterministic nodes own all financial math, authorization, and state transitions |
| **Default-deny writes** | READ tools automatic; `submit_support_case` requires approval + Cedar policy |
| **Evidence never raw** | Raw evidence encrypted in S3; only sanitized previews reach agent or UI |
| **Replay-first** | Full demo works without a live AWS incident — seeded, deterministic, 20/20 |
| **Auditable** | Every tool call has a `ToolAudit` record; every node has a trace span |
| **Idempotent** | Every external action has an idempotency key; duplicate events create one opportunity |

---

## Evaluation Results

| Metric | Target | Status |
|--------|--------|--------|
| Golden-path success (20 runs) | 20/20 (100%) | — |
| Overall scenario success | ≥ 92% | — |
| Financial math correctness | 100% | ✓ 12/12 golden tests |
| Unsafe external actions | 0 | — |
| Replay P95 | < 60s | — |

See `/quality` in the live demo for the current scorecard.

---

## Development Setup

**Prerequisites:** Python 3.12+, Node 20+, AWS CLI, CDK CLI

```bash
# Backend
cd backend
pip install -e ".[dev]"
pytest tests/unit/ -v          # 12 golden tests must pass

# Frontend
cd frontend
npm install
npm run dev                     # http://localhost:3000

# Infrastructure (requires AWS credentials + CDK bootstrap)
cd infra/cdk
npm install
npx cdk diff
npx cdk deploy --all
```

---

## Disclosure

This project was created fresh during the AWS Agents for Humans Hackathon (Aug 10 – Sep 14, 2026). See [`docs/DISCLOSURE.md`](docs/DISCLOSURE.md) for full disclosure details.

---

## License

[MIT](LICENSE)
