# Recoup Backend — Code & Architecture (J-FULL)

**Scope:** Code under `backend/src/recoup/` and `backend/tests/` references.  
**Operator journey reference:** [operator-journey.md](operator-journey.md) (steps 1–6).  
**Last updated:** Sep 13, 2026

---

## Purpose

FastAPI (`recoup.api.main:app`) exposes HTTP APIs for **read-only AWS account scanning**, **finding promotion into HITL-gated opportunities**, **approval workflows**, and **outcome/ledger persistence**. On **promote**, the backend runs `recoup_graph.run(..., stop_at="risk_policy_gate")`: for scan findings (`signal.source == "optimization"`), the **`incident_correlation`** node executes the **`recovery/` pipeline** (evidence graph, sufficiency, safety checks, recommendation/plan) and later graph nodes **no-op** once `recovery_assessment` is populated. The UI does **not** SSE-stream promote; trace comes from `GET .../trace`.

**Production:** App Runner `https://qawwrm7kzy.us-east-1.awsapprunner.com` — Docker image from repo root `Dockerfile`, `RECOUP_ENV=production`, CORS via `FRONTEND_URL` ([production-hosting.md](archive/ops/production-hosting.md)).

Run locally:

```bash
cd backend && uvicorn recoup.api.main:app --reload --port 8000
```

---

## Application shell

**Entry:** `backend/src/recoup/api/main.py`

| Concern | Implementation |
|---------|------------------|
| Lifespan | Starts/stops `sqs_poller` background thread |
| Routers | `/api/opportunities`, `/api/approvals`, `/api/quality`, `/api/scan` |
| CORS | `RECOUP_ENV=local` → `*`; else `frontend_url` + localhost |
| Rate limiting | `slowapi` optional on expensive routes |
| Health | `GET /health`, `GET /health/ready` (DynamoDB probe when configured) |
| Reset | `POST /api/test/reset`, `POST /api/admin/reset` → `_do_full_reset()` |
| Config exposure | `GET /api/config` — LLM provider, SNS, SQS flags (no secrets) |

**Reset clears:** `_graph_states`, promoted findings, scan audit/history, approvals (memory + DynamoDB when configured), `outcome_repo`. Test reset **keeps** demo scan cache (`_last_scan_result`) for Playwright performance; admin reset can clear cache via query param.

---

## Architecture diagram (J-FULL request path)

```text
                    ┌──────────────────────────────────────┐
                    │           FastAPI main.py             │
                    └───────────┬──────────────────────────┘
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   routes/scan.py         routes/approvals.py    routes/opportunities.py
        │                       │                       │
   9 × scanners            HITLFlow + store          list/get/trace/run/stream
   STS CustomerConnection       │                       │
        │                  notifications.py            │
        ▼                       ▼                       ▼
   Finding + ScanResult    outcome_repository      _graph_states (in-memory)
        │                       │
        └──────── promote ──────┴── GraphState + ApprovalRecord
```

---

## Route modules

### `routes/scan.py` — discovery & promote (steps 2, 4)

**Scanners** (`_ALL_SCANNERS`):

| Scanner | Module |
|---------|--------|
| EC2 | `scanners/ec2_scanner.py` |
| EBS | `scanners/ebs_scanner.py` |
| EIP | `scanners/eip_scanner.py` |
| RDS | `scanners/rds_scanner.py` |
| S3 | `scanners/s3_scanner.py` |
| Lambda | `scanners/lambda_scanner.py` |
| LB | `scanners/lb_scanner.py` |
| CloudWatch Logs | `scanners/cwlogs_scanner.py` |
| Cost Explorer | `scanners/cost_explorer_scanner.py` |

Preview subset: `_PREVIEW_SCANNERS` = Cost Explorer + EC2.

**Connection model:** `models/connection.py` — `CustomerConnection` builds boto3 session via STS `AssumeRole` (role ARN + external ID).

**Key endpoints:**

| Method | Path | J-FULL role |
|--------|------|-------------|
| POST | `/api/scan/demo` | One-click demo scan (env read role) |
| POST | `/api/scan/full`, `/preview` | Cross-account scan with `ScanRequest` |
| GET | `/api/scan/last` | Last scan payload |
| GET | `/api/scan/audit`, `/history` | Audit trail |
| POST | `/api/scan/findings/promote` | Finding → opportunity + HITL |
| GET | `/api/scan/findings/promoted` | Promoted registry |
| POST | `/api/scan/connect/init` | Customer ExternalId (full scan setup) |
| DELETE | `/api/accounts/{account_id}/data` | Admin data purge |

**Promote (`promote_finding`):**

- Idempotency: account namespace + resource_id + `content_hash` on `Finding` (`scanners/finding.py`)
- Creates `recovery-{uuid}` opportunity id
- `FindingToSignalAdapter` → `GraphState` with `promoted_finding`; optional LLM via `RECOVERY_LLM_ON_PROMOTE` (default **false**)
- `recoup_graph.run(initial_state, stop_at="risk_policy_gate")` — optimization path fills **`RecoveryAssessment`** via `recovery/pipeline.py` inside `graph/nodes.py` (`incident_correlation_stub`)
- Forces `policy_decision=REQUIRE_APPROVAL`, `current_state=AWAITING_APPROVAL`
- Action: `_recovery_action_for_finding()` → always **`apply_cost_recovery`**
- `HITLFlow.create_request` with **amount** = finding savings, **claim_hash** over `availability_result` JSON; risk/action/rollback copy from `recovery/approval_ui.py` when assessment present
- Registers state in `opportunities._graph_states` and `_promoted_findings`

**Scan metadata:** `scan_hash`, dedup/cached rescans, `_scan_audit_log`, `_scan_history`.

### `routes/approvals.py` — HITL (step 5)

| Method | Path | Effect |
|--------|------|--------|
| GET | `/api/approvals/pending` | Pending inbox |
| GET | `/api/approvals/opportunity/{id}` | Approval for detail UI |
| POST | `/api/approvals/opportunity/{id}/approve` | Claim-bound approve; **409** if evidence INSUFFICIENT, blocking safety FAIL, or projected amount ≠ pending amount; SNS flag; state → APPROVED → RECOVERED for cost recovery |
| POST | `/api/approvals/opportunity/{id}/investigate` | Decline approval with investigate notes; **NEEDS_FOLLOWUP** |
| POST | `/api/approvals/opportunity/{id}/decline` | **DENIED** |
| GET | `/api/approvals/outcomes` | Ledger / SNS metadata |
| POST | `/api/approvals/purge-stale` | Revoke stale pending approvals |

Legacy by-approval-id routes: `POST /{approval_id}/approve|decline`.

**Core logic:** `approval/flow.py` — `HITLFlow` (create, approve, decline, claim_hash / amount / state_version binding, 409 on mismatch).

**Persistence:** `approval/store.py` — DynamoDB table when `settings.approvals_table` set; in-memory fallback.

**Notifications:** `notifications.py` — `format_recovery_report_email`, `notify_sns` (respects dry-run env used in tests).

**Outcomes:** `graph/outcome_repository.py` — `mark_recovered`, `record_sns_notification`; DynamoDB `outcome_metadata_table` or in-memory.

### `routes/opportunities.py` — opportunity read & optional agent run

| Method | Path | J-FULL |
|--------|------|--------|
| GET | `/api/opportunities` | Ledger list |
| GET | `/api/opportunities/{id}` | Detail state |
| GET | `/api/opportunities/{id}/trace` | Trace for UI — includes **`recovery_assessment`**, **`workflow`** snapshot (promote or post-run) |
| POST | `/api/opportunities/{id}/run` | **Optional** — full graph run (replay signal or body) |
| GET | `/api/opportunities/{id}/stream` | SSE node progress (optional depth) |

Shared store: `_graph_states: dict[str, GraphState]` (imported by `scan.py` on promote).

State machine: `graph/state_machine.py` — `InMemoryStateMachine` for opportunity state transitions from approval routes.

### `routes/quality.py` — scorecard (not J-FULL UI)

`GET /api/quality/scorecard` — runs calculator/replay checks, autonomy gates, optional S3 persist. Used by pytest and Playwright J8, not the primary operator click path.

---

## Domain packages (supporting J-FULL)

| Package | Role in J-FULL |
|---------|----------------|
| `scanners/base.py`, `finding.py` | Finding model, evidence, `content_hash`, severity |
| `recovery/` | Cost recovery pipeline: signals → evidence graph → sufficiency/safety → recommendation + plan (`pipeline.py`, `engines/*`, `evidence_graph.py`) |
| `models/recovery.py` | `RecoveryAssessment`, evidence graph types, sufficiency/safety enums |
| `models/opportunity.py` | `OpportunityState` enum |
| `models/approval.py` | `ApprovalRecord`, states |
| `models/signal.py`, `eligibility.py`, `availability.py` | Populated by recovery pipeline on promote |
| `graph/types.py` | `GraphState` (+ `recovery_assessment`, `promoted_finding`) |
| `safety/cedar.py` | Policy evaluation (SLA replay path; optimization uses `recovery/policy.py` at pipeline) |
| `config.py` | Env: SNS, DynamoDB, demo roles, Bedrock, **`recovery_llm_on_promote`**, **`recovery_llm_on_investigate`** |

---

## J-FULL HTTP map (quick reference)

| Step | HTTP |
|------|------|
| Reset (test) | `POST /api/test/reset` |
| Reset (admin UI) | `POST /api/admin/reset?clear_scan_cache=true` |
| Scan | `POST /api/scan/demo` |
| Promote | `POST /api/scan/findings/promote` |
| Approve | `POST /api/approvals/opportunity/{id}/approve` |
| Investigate | `POST /api/approvals/opportunity/{id}/investigate` |
| Decline | `POST /api/approvals/opportunity/{id}/decline` |
| Ledger | `GET /api/opportunities`, `GET /api/approvals/outcomes`, `GET /api/scan/findings/promoted` |

---

## Background & integration

**SQS poller** (`sqs_poller.py`): Daemon thread when `recovery_events_queue_url` configured. Health events **acked only** — auto SLA replay disabled for J-FULL product path.

**AgentCore adapter** (`adapters/agentcore.py`): Bedrock AgentCore Runtime wrapper — separate from promote hot path; configured via `agentcore_runtime_arn`, `agentcore_gateway_url`.

---

## Testing (backend ↔ journey)

| Test area | Location |
|-----------|----------|
| Golden replay / SLA math | `backend/tests/e2e/test_golden_replay.py`, fixtures under `backend/tests/fixtures/scenarios/` |
| Replay adapter | `adapters/replay.py` — used by `/run`, quality scorecard, pytest |
| Unit graph | `backend/tests/unit/test_graph.py`, `test_replay_phase2.py` |
| Approvals / HITL | Unit tests under `backend/tests/unit/` |
| Recovery pipeline | `backend/tests/unit/recovery/` — pipeline, safety/sufficiency, approve gates, trace API |

Playwright hits running API; backend pytest proves agent/scorecard depth without the removed `/api/replay/*` HTTP surface.

---

## Additional backend code (aligns with journey themes, outside J-FULL promote path)

| Component | Location | Notes |
|-----------|----------|--------|
| **Full graph execution** | `graph/recoup_graph.py`, `graph/nodes.py` | 11 nodes; invoked via `POST .../run` and SSE stream, not on promote |
| **Strands agents** | `agents/strands_agents.py` | LLM nodes when `use_strands=True` |
| **Engines** | `engines/calculator.py`, `engines/sla_resolver.py` | Deterministic SLA credit math |
| **Evidence pipeline** | `evidence/collector.py`, `evidence/sanitizer.py` | Graph + quality gates |
| **Tools** | `tools/registry.py`, `aws_tools.py`, `ec2_tools.py`, `internal_tools.py` | MCP-style tool surface for agents |
| **Finding → signal adapter** | `adapters/finding_to_signal.py` | Bridge scan findings to graph inputs |
| **Autonomy / Cedar** | `safety/autonomy.py`, `safety/cedar.py` | Action classes for scorecard and graph gate |
| **Hooks / tracing** | `hooks/tracing.py` | Observability |
| **HITL legacy actions** | `approval/flow.py` — `stop_demo_instance`, `submit_support_case` context strings | Still in code for non-J-FULL actions; J-FULL promote uses `apply_cost_recovery` only |
| **Rate-limited scan** | `POST /api/scan/full/rate-limited` | Ops protection |
| **Account data delete** | `DELETE /api/scan/accounts/{account_id}/data` | Tenant cleanup |
| **Live flag** | `_live_flag.py` | Live AWS behavior toggles |

---

## Persistence model (as implemented)

| Store | When configured | J-FULL usage |
|-------|-----------------|--------------|
| In-memory `_graph_states`, `_promoted_findings` | Always (dev/demo) | Opportunities + promote registry |
| DynamoDB approvals | `APPROVALS_TABLE` | HITL records survive restart |
| DynamoDB outcomes | `OUTCOME_METADATA_TABLE` | Recovered credits, SNS flags |
| S3 evidence | `EVIDENCE_BUCKET` | Optional agent run / collector |
| CloudWatch Logs | HITL audit in `flow.py` | `/recoup/runtime` stream `hitl-approvals` |

Local/demo mode works fully in-memory when tables are unset.

---

## Package layout

```
backend/src/recoup/
  api/main.py, routes/{scan,approvals,opportunities,quality}.py
  scanners/          # 9 AWS read scanners
  approval/          # HITL flow + store
  graph/             # GraphState, nodes, outcome_repository, state_machine
  recovery/          # Cost recovery pipeline (promote + investigate enrichment)
  models/recovery.py # RecoveryAssessment domain types
  agents/            # Strands LLM wrappers (+ recovery investigator)
  adapters/          # replay, agentcore, finding_to_signal
  engines/           # SLA calculator
  evidence/          # collect + sanitize
  tools/             # agent tool registry
  safety/            # Cedar, autonomy
  notifications.py   # SNS recovery report
  sqs_poller.py
  config.py
```

---

## Related docs

[operator-journey.md](operator-journey.md) · [agent-code-architecture.md](agent-code-architecture.md) · [frontend-code-architecture.md](frontend-code-architecture.md) · [recoup-overall-architecture.md](recoup-overall-architecture.md)
