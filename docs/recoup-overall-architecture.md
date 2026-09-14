# Recoup — Overall System Architecture (codebase view)

**Scope:** End-to-end system derived from repository code and [operator-journey.md](operator-journey.md).  
**Primary product path:** **J-FULL** — reset → demo scan → promote (×3 services) → approve / investigate / decline → recovery ledger (+ SNS on approve).  
**Last updated:** Sep 13, 2026

**Layer-specific docs:**

- [frontend-code-architecture.md](frontend-code-architecture.md)  
- [backend-code-architecture.md](backend-code-architecture.md)  
- [agent-code-architecture.md](agent-code-architecture.md)

---

## System purpose (as implemented)

Recoup connects **read-only AWS discovery** to **human-in-the-loop approval** and **auditable outcomes**. Recoverable spend is detected by parallel account scanners; each promoted finding becomes an opportunity with a **claim-bound** approval record; approved cost-recovery actions update ledger buckets and can emit an **SNS recovery report**.

An **11-node Strands recovery graph** (SLA/incident depth) remains for optional `POST /api/opportunities/{id}/run`, SSE streaming, pytest golden replay, and the quality scorecard. **J-FULL promote** runs the graph **through `risk_policy_gate`** and executes the dedicated **`recovery/` pipeline** for scan findings (evidence graph, recommendation, safety) without SSE on the wire.

---

## High-level diagram

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  Next.js 16 (frontend/)                                                  │
│  Routes: /opportunities · /scan · /recovery · /opportunities/[id]       │
│  localStorage scan cache + useRecoveryData → single ledger view          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ HTTP (JSON) · optional SSE (EventSource)
┌───────────────────────────────▼─────────────────────────────────────────┐
│  FastAPI (backend/src/recoup/api/)                                       │
│  /api/scan · /api/opportunities · /api/approvals · /api/quality          │
│  Lifespan: SQS poller (ack-only for Health in J-FULL mode)               │
└───────┬─────────────────────────────┬───────────────────────────────────┘
        │                             │
        ▼                             ▼
┌───────────────────┐       ┌─────────────────────────────────────────────┐
│ AWS APIs (read)   │       │ Agent layer (optional)                       │
│ STS AssumeRole    │       │ recoup_graph · Strands · replay adapter      │
│ 9 scanners        │       │ tools registry · Cedar · evidence pipeline   │
└───────────────────┘       └─────────────────────────────────────────────┘
        │                             │
        └─────────────┬───────────────┘
                      ▼
        ┌─────────────────────────────────────────┐
        │ Persistence (env-dependent)              │
        │ In-memory graph/promoted · DynamoDB      │
        │ approvals + outcomes · S3 evidence · SNS │
        └─────────────────────────────────────────┘
```

---

## J-FULL lifecycle (cross-stack)

```text
  [Reset]     [Demo scan]      [Pick findings]     [Promote]        [HITL]         [Ledger]
     │              │                 │                │               │                │
  admin/      POST           /opportunities      POST            POST approve/      /recovery
  test reset  /scan/demo     table + filters     .../promote       investigate/       + summary
                                                     │               decline          on /opportunities
                                                     │                               │
                                                     └─ graph.run → recovery/       │
                                                        pipeline + AWAITING_APPROVAL │
                                                        + HITLFlow PENDING           │
                                                                                      │
                                                        approve → RECOVERED + SNS ────┘
```

| Step | Frontend | Backend |
|------|----------|---------|
| 1 Reset | `sidebar.tsx` → admin reset; tests → `/api/test/reset` | `main.py` `_do_full_reset` |
| 2 Scan | `/scan` → `api.scan.demo()` → `saveLastScan` | `scan.py` + `_ALL_SCANNERS` + STS |
| 3 Pick 3 services | Filters + rows on `/opportunities` | (client/test selection) |
| 4 Promote | Start Recovery → `api.scan.promote` | `promote_finding` → `_graph_states` |
| 5 Triage | `/opportunities/[id]` DecisionCard | `approvals.py` + `HITLFlow` |
| 6 Ledger | `useRecoveryData` + `RecoveryLedger` | `opportunities` + `outcome_repo` + outcomes API |

---

## Major subsystems

### 1. Account scanner (discovery)

- **Backend:** `backend/src/recoup/scanners/*`, orchestrated from `api/routes/scan.py`
- **Credentials:** `models/connection.py` — cross-account `AssumeRole`; demo scan uses env-configured read role
- **Output:** `Finding` with `evidence`, `estimated_monthly_savings_usd`, optional `scenario_tag` for demo workloads
- **Caching:** `_last_scan_result`, `scan_hash` dedup, audit/history arrays

### 2. Promotion & opportunity state

- **Promote** creates `recovery-*` id, runs graph through policy gate with **`RecoveryAssessment`**, opens approval with `apply_cost_recovery`
- **State machine:** in-memory `InMemoryStateMachine` + `GraphState.current_state`
- **Idempotency:** resource + content hash; status `existing` when unchanged

### 3. HITL & trust

- **Binding:** claim_hash, amount, state_version — mismatches → HTTP 409; recovery path also blocks approve on **INSUFFICIENT** evidence, **blocking safety FAIL**, or **projected amount drift**
- **Store:** DynamoDB or memory (`approval/store.py`)
- **Audit:** CloudWatch log group `/recoup/runtime` from `approval/flow.py`
- **Notifications:** SNS via `notifications.py` (`RECOUP_SNS_TOPIC_ARN`, dry-run in tests)

### 4. Recovery ledger

- **Frontend buckets:** Detected / Pending / Recovered — `computeLedgerData`, `toCanonicalLifecycle`
- **Backend truth:** opportunity states + `GET /api/approvals/outcomes` (credit, `sns_sent`)

### 5. Agent & quality (depth, not demo-critical)

- **Graph:** `graph/recoup_graph.py` — 11 nodes, Cedar gate, virtual HITL pause
- **Replay:** `adapters/replay.py` + pytest golden scenarios
- **Scorecard:** `GET /api/quality/scorecard` — ship gates for judges/CI
- **AgentCore:** `adapters/agentcore.py` — optional runtime integration

### 6. Infrastructure (repo)

- **IaC:** `infra/cdk/` — `RecoupInfraStack`, `RecoupIamStack`, `RecoupDemoWorkloadsStack`, `RecoupAppStack` (API), `RecoupUiStack` (Next.js)
- **Production hosting (Plane A):** App Runner + ECR; UI `https://pdkeexzwxr.us-east-1.awsapprunner.com`, API `https://qawwrm7kzy.us-east-1.awsapprunner.com` — [archive/ops/production-hosting.md](archive/ops/production-hosting.md)
- **Policy:** `infra/policy/recoup-policy.cedar`
- **Scripts:** `scripts/` — `deploy_app_hosting.sh`, `deploy_ui_hosting.sh`, smoke, segregation, Plane D/E cost trims

---

## API surface (product vs depth)

| Category | Endpoints | J-FULL |
|----------|-----------|--------|
| Meta | `/health`, `/health/ready`, `/api/config`, `/api/test/reset`, `/api/admin/reset` | Reset + ops |
| Scan | `/api/scan/demo`, `/full`, `/preview`, `/last`, `/findings/promote`, `/findings/promoted`, `/connect/init` | Core |
| Approvals | `/api/approvals/opportunity/{id}/*`, `/outcomes`, `/pending` | Core |
| Opportunities | `GET` list/detail/trace | Core |
| Opportunities | `POST /run`, `GET /stream` | Optional |
| Quality | `/api/quality/scorecard` | CI / judge depth |

Removed from product (per codebase comments and frontend redirects): public `/api/replay/*`, dedicated `/approvals`, `/quality`, `/replay` UI pages.

---

## Data & trust model (cross-cutting)

1. **Collect** — scanner attaches service-specific evidence to findings.  
2. **Quantify** — `estimated_monthly_savings_usd` on each finding (scanner heuristics / pricing).  
3. **Promote** — freeze amount + claim_hash on approval record.  
4. **Approve** — operator confirms; `HITLFlow.approve()` enforces bindings.  
5. **Record** — outcome repository + ledger UI; SNS on successful approve.

Optional **agent re-run** on detail deepens investigation without changing the J-FULL promote contract.

---

## Design principles (visible in code)

| Principle | Where |
|-----------|--------|
| LLMs propose; contracts decide | Deterministic nodes for SLA math; Strands for narrative only |
| Scanner-first demo | Promote runs recovery pipeline + graph through policy gate |
| Default-deny destructive writes | Cedar + HITL; J-FULL action is cost recovery not EC2 stop |
| Evidence hygiene | Sanitizer node + quality gates |
| Idempotent promote | content_hash + promoted registry |
| Live-first with fallbacks | DynamoDB/S3 when configured; in-memory locally |

---

## Testing architecture

| Layer | Tooling | J-FULL anchor |
|-------|---------|---------------|
| E2E | Playwright `frontend/e2e/journey-full-discovery-triage-ledger.spec.ts` | Full operator loop |
| E2E overlap | J2, J6, J7, J9, scan, UI browser specs | Partial paths |
| Backend unit/integration | pytest ~416 tests | Graph, recovery pipeline, replay, approvals, scanners, demo sessions |
| Golden replay | `test_golden_replay.py` | SLA credit determinism |
| Quality | `journey-quality-gates.spec.ts` | Scorecard structure |

---

## Additional system capabilities (align with operator-journey themes)

Flagged for completeness — present in repo, not required to demo J-FULL:

| Capability | Stack location |
|------------|----------------|
| Cross-account ExternalId onboarding | `POST /api/scan/connect/init`, e2e `journey-cross-account-connect.spec.ts` |
| Full/preview scan (non-demo) | `/scan` UI modes, `POST /api/scan/full` |
| Scan idempotency & history | Backend `_scan_history`; frontend `ScanHistoryPanel` |
| SSE pipeline visualization | `GET .../stream`, detail page EventSource |
| Security / 409 HITL tests | `journey-security.spec.ts` |
| SQS event ingestion (no auto-replay) | `sqs_poller.py` |
| Ship gates script | `scripts/assert_ship_gates.py` |
| OpenAI as alternate LLM provider | `strands_agents.py`, `LLM_PROVIDER=openai` |
| Per-account data delete | `DELETE /api/scan/accounts/{account_id}/data` |
| Stale approval purge | `POST /api/approvals/purge-stale` |

---

## Repository map (top level)

```
recoup/
  frontend/          Next.js operator UI
  backend/           FastAPI + recoup package
  infra/cdk/         AWS infrastructure
  docs/              Product & architecture markdown
  scripts/           Demo ops, fixtures, CI helpers
  docs/archive/internal/plans/   Historical phase notes (optional)
```

---

## Environment coupling (typical local demo)

| Variable | Subsystem |
|----------|-----------|
| `NEXT_PUBLIC_API_URL` | Frontend → backend |
| Demo read role ARNs / external ID | `scan.py` demo path |
| `RECOUP_SNS_TOPIC_ARN`, `RECOUP_SNS_DRY_RUN` | Notifications |
| `APPROVALS_TABLE`, `OUTCOME_METADATA_TABLE` | DynamoDB persistence |
| `RECOVERY_EVENTS_QUEUE_URL` | SQS poller |
| `LLM_PROVIDER`, Bedrock/OpenAI keys | Strands agents |
| `RECOVERY_LLM_ON_PROMOTE`, `RECOVERY_LLM_ON_INVESTIGATE` | Optional LLM in recovery pipeline |
| `RECOUP_ENV` | CORS, reset gates |

Project-root `.env` loaded by `backend/src/recoup/config.py`.

---

## Documentation lineage

This overview is **code-first** and aligned to [operator-journey.md](operator-journey.md). Older broad docs (e.g. [archive/superseded/architecture-overview.md](archive/superseded/architecture-overview.md)) may mention removed routes or UI; prefer the **code-architecture** documents above for current structure.

**Related:** [api-reference.md](api-reference.md) · [scanner-coverage.md](scanner-coverage.md) · [demo-playbook.md](demo-playbook.md) · [judge-demo.md](judge-demo.md)
