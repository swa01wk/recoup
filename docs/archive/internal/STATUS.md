# Recoup — Project Status

> **Historical phase log — not for judges.** Current product: [operator-journey.md](../../operator-journey.md) · [judge-demo.md](../../judge-demo.md).  
> **Production:** App Runner — [production-hosting.md](../ops/production-hosting.md). Metrics: [docs/README.md](../../README.md).

**Competition Deadline:** Sep 14, 2026 (AWS Agents for Humans Hackathon)  
**Last Updated:** Sep 14, 2026 — README LLM provider docs · PSC-2/PSC-4 E2E · CloudWatch `Recoup/Graph` + `Recoup/Tools` metrics · [release_notes.md](../../../release_notes.md)  
**Days Remaining:** 0 (submission day)  
**Feature Cutoff:** Sep 11, 2026

### Production (judge demo)

| | URL |
|--|-----|
| UI | https://pdkeexzwxr.us-east-1.awsapprunner.com |
| API | https://qawwrm7kzy.us-east-1.awsapprunner.com |

Plane B/C/D stacks deployed; Plane E trimmed; budgets `$100/$150/$180`; segregation smoke: `./scripts/post_change_segregation_smoke.sh`.

### Key Numbers (current)

Canonical metrics: [docs/README.md](docs/README.md#key-numbers-canonical--update-here-first)

| Metric | Value |
|--------|-------|
| Backend unit tests | **419** collected (live-mode skips as configured) · 0 DeprecationWarnings |
| Playwright E2E tests | **127** (16 specs) · J-FULL + PSC + J2–J9 + 13 SEC adversarial |
| Frontend nav | **3** sidebar links: `/opportunities`, `/scan`, `/recovery` (`/replay` removed) |
| Scanners | **9** (EC2, EBS, EIP, RDS, S3, Lambda, ELB, CW Logs, Cost Explorer) |
| Demo scenarios | **8/8** detected — $87.82/mo (full scan aggregate) |
| Golden replay | 20/20 · $0.35 · P95 ~23 ms |
| Tools in registry | **13** |
| Quality gates | **6** (`/api/quality/scorecard`) |
| IAM roles | **6** (Runtime, Gateway, ReadConnector, ReadOnly, Remediation, + demo) |
| Phases complete | 0–6f, 8, 9 ✅ · Phase 7 code/docs ✅ · submission artifacts 🟡 |
| User journeys | **12** (J1–J12) + **13** security adversarial tests |

> **Note:** Phase sections below are historical snapshots (Sep 8, 2026). They may mention older test counts (397, ~133). Use **Key Numbers** above and [docs/README.md](docs/README.md) for current metrics.

### Production Gap Analysis — Sprint Completion (Sep 8, 2026)

| Sprint | Focus | Items | Status |
|--------|-------|-------|--------|
| Sprint 1 | Cross-account workflow | 7 gaps | ✅ All resolved |
| Sprint 2 | Trust & data safety | 6 gaps | ✅ All resolved |
| Sprint 3 | Pipeline integrity | 14 gaps | ✅ All resolved |
| Sprint 4 | Production hardening | 14 gaps | ✅ All resolved |
| Sprint 5 | Docs + Playwright | All tracks | ✅ Complete — 28 Playwright specs (279 tests), J1–J12 + 13 SEC adversarial |

**Sprint 1 key fixes:** `sts:AssumeRole` on RuntimeRole, per-customer ExternalId gen, CORS restriction, connect wizard, disclosure + consent gate, DenyAllWrites in CF template.

**Sprint 2 key fixes:** Scanner output sanitized (account IDs/ARNs masked), tenant isolation by account_id, ScanAuditRecord + GET /api/scan/audit, CMK extended to approvals/SQS/tool-audits, enforceSSL on all S3 buckets, DELETE /api/accounts/{id}/data, IAM permissions scoped to 9 scanners.

**Sprint 3 key fixes:** FindingToSignalAdapter, OutcomeRepository, graph checkpoint (DynamoDB + in-memory), state machine wired through approve/decline/investigate, SQS ack-on-success + DLQ routing, EC2DemoCard restored on `/`, GovernanceInsightsCard wired to all 3 governance APIs, Investigate button fixed (calls investigate not decline), pipeline strip relabelled "Architecture Overview", quality page loading skeleton (no DEMO_SCORECARD flash), badge corrected.

**Sprint 4 key fixes:** API-key auth middleware (`RECOUP_API_KEY` → `X-API-Key` / `Authorization: Bearer`); approval store fails hard in production (no silent in-memory fallback); AWS Secrets Manager loading at startup (`RECOUP_SECRETS_ARN`); Sentry SDK initialisation (`SENTRY_DSN`); global exception handler with `{error, request_id}`; request_id middleware; RECOUP_ENV / RECOUP_LOG_LEVEL settings; centralised structlog; /health/ready probe; test reset gated in production; slowapi rate limiting; quality page loading skeleton.

**Sprint 5 key fixes:** Playwright suite expanded (now 28 specs / 279 tests; was 18 / ~133 at sprint time): `scan.spec.ts`, `decision-inbox.spec.ts`, `sla-replay.spec.ts`, `ec2-stop.spec.ts`, `opportunity-detail.spec.ts`, `recovery-ledger.spec.ts`, `governance.spec.ts`, `quality-dashboard.spec.ts` + journey specs J2–J12 + `journey-security.spec.ts` (13 SEC adversarial). `USER_JOURNEY_CHECKLIST.md` created with full coverage map. All docs updated Sep 8, 2026.

---

## Overall Progress

| Phase | Name | Target | Status | Progress |
|-------|------|--------|--------|----------|
| 0 | Foundation & Infrastructure | Sep 3 | ✅ Complete | 100% |
| 1 | Core Agent Graph & Data Contracts | Sep 6 | ✅ Complete | 100% |
| 2 | Verified Replay & SLA Recovery Engine | Sep 9 | ✅ Complete | 100% |
| 3 | Evidence System, Safety Layer & HITL | Sep 10 | ✅ Complete | 100% |
| 4 | Frontend Command Center | Sep 11 | ✅ Complete | 100% |
| 5 | Evaluation & Testing Suite | Sep 12 | ✅ Complete | 100% |
| 6 | Live AWS Action Proof | Sep 12 | ✅ Complete | 100% |
| 6b | Demo Realism & AWS Integration | Sep 5 | ✅ Complete | 100% |
| 6c | Strands SDK & Bedrock Deep Integration | Sep 6 | ✅ Complete | 100% |
| 6d | Remove Simulation Mode + Account Scanner | Sep 2 | ✅ Complete | 100% |
| 6e | IAM Security Model & STS AssumeRole | Sep 5 | ✅ Complete | 100% |
| 6f | RecoupDemoWorkloadsStack & 8 Scenario Coverage | Sep 6 | ✅ Complete | 100% |
| 8 | Frontend Redesign — Recovery Dashboard | Sep 6 | ✅ Complete | 100% |
| 9 | Competitive UI Gaps (from positioning doc) | Sep 11 | ✅ Complete | 100% |
| 7 | Polish, Submission & Video | Sep 14 | 🟡 Submission artifacts | 85% |

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
  - **All 4 jobs green** — ruff (0 errors), mypy strict (0 errors), 63/63 tests, CDK synth clean (fixed Sep 1)
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
- [x] **Verify AWS Builder ID** at [profile.aws.amazon.com](https://profile.aws.amazon.com) ✅

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
- [x] **`adapters/replay.py`** — `ReplayAdapter` + `CANONICAL_SCENARIO` ($0.35 golden scenario)
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
| `ruff check` — 0 errors | ✅ |
| `mypy --strict` — 0 errors | ✅ |
| CI all 4 jobs green | ✅ |

---

## Phase 2 — Verified Replay & SLA Recovery Engine
**Target:** Sep 9, 2026 | **Status:** ✅ Complete (114/114 tests, 0 warnings)

### Done ✅
- [x] Canonical replay seed artifacts committed to `eval_fixtures/sla/api_gateway/canonical/`:
  - `health_event.json` — synthetic AWS Health event (full EventBridge schema)
  - `metric_series.json` — 8,640 five-minute intervals; 6 at 0% (02:00–02:30 UTC Aug 1)
  - `billing_snapshot.json` — August 2026 billing: $3.51 for API Gateway us-east-1
  - `cloudtrail_events.json` — benign events; `verdict: no_customer_caused_errors`
  - `sla_contract_ref.yaml` — points to `sla_catalog/api_gateway/2022-05-05.yaml`
  - `expected_output.json` — calculator result: 99.930556%, tier=10%, credit=$0.35
- [x] `GraphState.replay_fixtures` — carries fixture data through the pipeline
- [x] `ReplayAdapter._load_fixtures()` — loads fixture files into `GraphState.replay_fixtures`; falls back gracefully when files absent
- [x] `incident_correlation_stub` — Phase 2 path: parses intervals from `metric_series.json`; billing from `billing_snapshot.json`; falls back to golden stub when no fixtures
- [x] `normalize_event` — already correct; parses both replay and live event schemas
- [x] `sla_contract_resolver` — loads `2022-05-05` contract from local catalog by incident date ✓
- [x] `availability_calculator` — produces `99.930556%` and `$0.35` deterministically ✓
- [x] `eligibility_reasoner` — passes all canonical criteria ✓
- [x] `claim_package_generator` — produces complete `ClaimPackage` (after HITL approval) ✓
- [x] Full end-to-end: reproducible `$0.35` on 20/20 consecutive runs; P95 = 23ms ✓
- [x] `Graph.run()` — `on_node_start` / `on_node_complete` callbacks for SSE streaming
- [x] `POST /api/replay/api-gateway-sla` — canonical replay trigger endpoint
- [x] `GET /api/opportunities/{id}/stream` — SSE stream; streams node events from fixture run or from background execution using `asyncio.to_thread`
- [x] `scripts/generate_canonical_fixtures.py` — generates `metric_series.json`; validates golden invariants; prints SHA-256
- [x] `scripts/replay_run.py` — headless replay; `--runs N` for timing; exits 1 on assertion failure
- [x] 51 new Phase 2 tests (114/114 total pass; 0 warnings)

### Definition of Done
| Check | Result |
|-------|--------|
| Seed artifacts committed; `_recoup_replay: true` flag present | ✅ |
| All golden acceptance tests pass (12 calculator + 51 Phase 2) | ✅ |
| SLA resolver picks correct contract version by date | ✅ |
| Replay adapter loads fixture files; falls back cleanly | ✅ |
| `POST /api/replay/api-gateway-sla` triggers workflow | ✅ |
| SSE streams node-by-node progress | ✅ |
| P95 replay < 60 s (measured: 23 ms) | ✅ |
| Deterministic fixture-based execution | ✅ |
| 20/20 consecutive runs: identical $0.35 | ✅ |
| ruff — 0 errors | ✅ |
| mypy --strict — 0 errors | ✅ |

---

## Phase 3 — Evidence System, Safety Layer & HITL
**Target:** Sep 10, 2026 | **Status:** ✅ Complete (180/180 tests, 0 warnings)

### Done ✅
- [x] **`evidence/collector.py`** — `EvidenceCollector`: collects all required SLA fields; loads from replay fixtures when present; stores raw evidence to S3 (KMS-encrypted; skipped when `live_evidence=False`); manifest carries only S3 URIs + SHA-256 hashes — raw content never in LLM context
- [x] **`evidence/sanitizer.py`** — `EvidenceSanitizer`: 8 compiled regex patterns (auth tokens, JWT, API keys, cookies, emails, AWS account IDs, private IPs, AWS secrets); two-pass design with HIGH_RISK_SCANNER; fails closed on any surviving high-risk pattern (`SanitizationError`); updates manifest with `REDACTED` status
- [x] **`safety/exceptions.py`** — `SanitizationError`, `ToolDeniedError`, `ApprovalRequiredError` — typed, structured, carry full context for logging
- [x] **`safety/autonomy.py`** — `AutonomyClass` enum (GREEN/YELLOW/RED/BLACK); `TOOL_AUTONOMY_CLASS` map for all 18 tools; `check_autonomy()` enforced pre-tool (not in prompt); BLACK → `ToolDeniedError`; RED without valid approval → `ApprovalRequiredError`
- [x] **`safety/cedar.py`** — `PolicyContext` dataclass + `evaluate_policy()`: Python simulation of all Cedar rules; all 5 `submit_support_case` preconditions; `stop_demo_instance` allowlist guard; destructive tool forbid; default deny
- [x] **`infra/policy/recoup-policy.cedar`** — Full Cedar policy file: GREEN/YELLOW permits, RED submit_support_case (5 preconditions), RED stop_demo_instance, BLACK forbid rules
- [x] **`approval/store.py`** — DynamoDB-backed approval store with in-memory fallback; `save_approval`, `get_approval`, `list_pending_approvals`, `get_pending_for_opportunity`, `update_approval_state`; DynamoDB TTL on `expires_at_epoch`
- [x] **`approval/flow.py`** — `HITLFlow`: `create_request` (revokes superseded pending approvals), `approve` (claim_hash + amount + state_version binding assertions), `decline`, `get_pending`, `approval_card_text`
- [x] **Updated `graph/nodes.py`** — `evidence_collector_stub` → real `EvidenceCollector`; `evidence_sanitizer_fn` → real `EvidenceSanitizer`; `risk_policy_gate_fn` → real Cedar evaluation via `build_context_from_graph_state` + `evaluate_policy`
- [x] **Updated `api/routes/approvals.py`** — DynamoDB-backed store; `GET /api/approvals/pending`; `POST /api/approvals/{id}/approve|decline`; `GET /api/approvals/opportunity/{id}`; `POST /api/approvals/opportunity/{id}/approve|decline` (with binding validation)
- [x] **66 new Phase 3 tests** (180/180 total pass; 0 warnings): evidence collector, sanitizer (6 redaction scenarios + fail-closed), autonomy class, Cedar policy (all 5 preconditions), approval store, HITL flow (binding assertions, expiry, revocation), graph integration

### Definition of Done
| Check | Result |
|-------|--------|
| Evidence collector stores to S3 with hash; manifest complete | ✅ |
| Sanitizer: 6 redaction scenarios pass; fail-closed on high-risk | ✅ |
| Raw evidence never in LLM context, trace, or API response | ✅ |
| Cedar policies: all 5 precondition tests pass; destructive deny | ✅ |
| Approval flow: approve/decline + binding assertions work | ✅ |
| Approval expiry → policy DENY | ✅ |
| Stale state_version → `ValueError` on approve | ✅ |
| Amount mismatch → `ValueError` on approve | ✅ |
| BLACK tools → `ToolDeniedError` | ✅ |
| GREEN tools auto-pass without approval | ✅ |
| Zero unsafe actions in all 66 Phase 3 tests | ✅ |
| ruff — 0 errors | ✅ |
| mypy --strict — 0 errors | ✅ |
| 180/180 tests pass; 0 DeprecationWarnings | ✅ |

---

## Phase 4 — Frontend Command Center
**Target:** Sep 11, 2026 | **Status:** ✅ Complete

### Done ✅
- [x] Next.js 16 + TypeScript + Tailwind 4 (dark slate theme)
- [x] Sidebar navigation (Recovery Dashboard / Replay / Decision Inbox / Quality / Account Scanner / Recovery Ledger)
- [x] **Recovery Dashboard** (`/`) — Recovery Ledger, 11-step pipeline, 8 scenario tiles, promote flow
- [x] **Replay Engine** (`/replay`) — trigger canonical replay, live result panel, big $0.35 credit readout, S3 evidence panel
- [x] **Decision Inbox** (`/approvals`) — HITL approval queue; risk tier + action + rollback context; approve/decline with binding validation
- [x] **Opportunity Detail** (`/opportunities/[id]`) — SSE agent trace, hypothesis card, verification panel, intent badge, inline approve/decline
- [x] **Quality Dashboard** (`/quality`) — live scorecard, ship gate checklist
- [x] **Account Scanner** (`/scan`) — STS role form, 8-scenario map, savings banner
- [x] **Recovery Ledger** (`/recovery`) — recharts savings chart, full ledger view
- [x] Operator/Viewer role system with localStorage persistence
- [x] Backend API integration: polling every 8–10 s + live SSE streaming
- [x] `npm run build` — 0 TypeScript errors, 8 routes clean

---

## Phase 5 — Evaluation & Testing Suite
**Target:** Sep 12, 2026 | **Status:** ✅ Complete (334/334 tests, 0 warnings)

### Done ✅
- [x] Test directory structure: `tool_contracts/`, `trajectory/`, `e2e/`, `adversarial/`, `fixtures/scenarios/`
- [x] **47 YAML scenario definitions** across 8 categories (7 valid SLA, 6 not-eligible, 6 evidence-gaps, 4 exclusions, 6 sanitization, 6 policy/HITL, 7 resilience, 5 anomaly)
- [x] **`tests/tool_contracts/test_tool_contracts.py`** — 37 tests: TOOL_REGISTRY schema, all 8 tool contracts (CW metrics, CW logs, health events, cost & usage, CloudTrail, store_evidence, create_approval_request, simulate_support_case, stop_demo_instance, get_support_case_status)
- [x] **`tests/trajectory/test_trajectory.py`** — 27 tests: node ordering, sanitizer-before-claim-package, policy enforcement, tool allowlists, simulation mode, financial math integrity, 20-consecutive-run determinism
- [x] **`tests/e2e/test_golden_replay.py`** — 17 tests: single canonical run, 20-run golden path (100%), P95 < 60s, trace completeness
- [x] **`tests/e2e/test_scenario_suite.py`** — 40+ scenario-driven tests across all 8 categories + count/uniqueness/category coverage checks
- [x] **`tests/adversarial/test_adversarial.py`** — 19 tests: prompt injection, evidence hallucination prevention, binding assertion tampering (7 scenarios), BLACK tool enforcement, Decimal precision
- [x] **`scripts/run_eval_suite.py`** — eval runner producing scorecard JSON; all 6 ship gates
- [x] **`scripts/assert_ship_gates.py`** — CI gate: asserts all 9 ship-gate metrics from scorecard JSON
- [x] **`backend/src/recoup/api/routes/quality.py`** — `/api/quality/scorecard` endpoint running live eval
- [x] **`frontend/src/app/quality/page.tsx`** — `/quality` Quality Dashboard: live scorecard, gauge bars, 8-category breakdown, ship gate checklist
- [x] Sidebar updated with Quality Dashboard nav entry
- [x] 334/334 tests pass, 0 warnings, ruff/mypy clean
- [x] `npm run build` — 0 TypeScript errors, `/quality` route added

### Definition of Done
| Check | Result |
|-------|--------|
| 40+ scenarios | ✅ 47 YAML definitions |
| Golden path | ✅ 20/20 consecutive runs pass |
| Scenario success | ✅ ≥ 92% |
| Evidence recall | ✅ ≥ 98% |
| Tool accuracy | ✅ ≥ 95% |
| Financial math | ✅ 100% deterministic |
| Unsafe actions | ✅ 0 |
| Hallucinated evidence | ✅ 0 |
| P95 replay | ✅ < 60s (measured: ~30ms) |
| Trace completeness | ✅ 100% |
| CI gate | ✅ `assert_ship_gates.py` ready |
| Quality view | ✅ `/quality` live scorecard |

---

## Phase 6 — Live AWS Action Proof
**Target:** Sep 12, 2026 | **Status:** ✅ Complete — delivered Sep 2 (10 days early)

### Done ✅
- [x] **`tools/ec2_tools.py`** — Full live implementation with 5 safety guards:
  1. Allowlist check (env-configured `RECOUP_DEMO_INSTANCE_ALLOWLIST`)
  2. Live tag verification via `DescribeTags` (`RecoupDemo=true` required)
  3. Approval validation + binding hash assertion
  4. Idempotency guard (duplicate stop → returns prior result)
  5. Actual `StopInstances` call + `instance_stopped` waiter + final state verification
- [x] **`adapters/ec2_demo.py`** — `EC2DemoAdapter`: CloudWatch CPU check (idle < 1% over 7 days), CloudTrail ownership check, waste calculation, OPTIMIZATION opportunity creation, HITL approval request
- [x] **`api/routes/ec2_demo.py`** — 4 routes: `POST /trigger`, `GET /opportunities`, `GET /opportunity/{id}`, `POST /execute/{id}`
- [x] **`api/main.py`** — ec2_demo router registered at `/api/ec2-demo`
- [x] **`scripts/reset_demo_instance.sh`** — reset script: auto-discovers by `RecoupDemo=true` tag, starts instance, waits for running state
- [x] **Cedar policy** — `stop_demo_instance` permit rule (5 preconditions); `terminate_ec2_instance` hard-forbid
- [x] **LIVE AWS ACTION badge** — visible in Decision Inbox for `stop_demo_instance` approvals (red border, animated pulse badge, safety checklist)
- [x] **Frontend Command Center** — EC2 Demo card with trigger button, CloudWatch/CloudTrail check summary, waste estimate, link to Decision Inbox
- [x] **28 Phase 6 tests** — allowlist enforcement, simulation mode, Cedar policy (7 scenarios), adapter workflow, action hash binding, full e2e simulation
- [x] **Validated Sep 2** — full test suite run: 362 passed, 15 skipped (live-mode), 0 failures
- [x] `ruff check src/ tests/` — 0 errors (35 auto-fixed + 11 manually fixed Sep 2)
- [x] `mypy --strict` — 0 errors (49 source files)
- [x] `npm run build` — 0 TypeScript errors, all 5 routes clean
- [x] `npm run lint` — 0 ESLint errors

### Definition of Done
| Check | Result |
|-------|--------|
| `stop_demo_instance` allowlist + tag enforcement | ✅ |
| EC2 stop requires valid HITL approval + allowlist | ✅ |
| Cedar policy: 5 preconditions for `stop_demo_instance` | ✅ |
| `terminate_ec2_instance` hard-forbid | ✅ |
| Action hash binding (tampered hash rejected) | ✅ |
| Idempotency: duplicate stop returns prior result | ✅ |
| EC2DemoAdapter full workflow (CW → CT → HITL) | ✅ |
| LIVE AWS ACTION badge in Decision Inbox | ✅ |
| EC2 Demo card in Command Center frontend | ✅ |
| 28 Phase 6 tests pass | ✅ |
| 397/397 total tests pass; 0 warnings | ✅ |
| `ruff check` — 0 errors | ✅ |
| `mypy --strict` — 0 errors | ✅ |
| `npm run build` — 0 errors | ✅ |

### Pre-Demo User Actions (before live demo only)
- [ ] Set `RECOUP_DEMO_INSTANCE_ALLOWLIST=<real-instance-id>` in `.env`
- [ ] Ensure AWS credentials / IAM roles are configured (see `.env.example`)
- [ ] Run `./scripts/reset_demo_instance.sh` before demo to ensure instance is running

---

## Phase 6b — Demo Realism & AWS Integration
**Target:** Sep 5, 2026 | **Status:** ✅ Complete | **Completed:** Sep 2, 2026  
**Plan:** [`plans/phase-6b-demo-realism-aws-integration.md`](plans/phase-6b-demo-realism-aws-integration.md)

**Goal:** Every video scene touches real AWS services. Close the data gaps caused by a new account (no API GW, no Cost Explorer history, no Health events) using AWS services that ARE provisioned and have real data today.

### Done ✅ (Sep 2, 2026)

- [x] **S3 evidence writes during SLA replay** — `live_evidence` flag in `EvidenceCollector`; evidence JSONs land in real `recoup-evidence` bucket with KMS encryption; `evidence_s3_uris` returned in replay response; Replay page shows "Evidence Written to S3 — LIVE AWS" panel
- [x] **CloudWatch Logs audit trail for HITL approvals** — `HITLFlow` writes `APPROVAL_REQUESTED / GRANTED / DECLINED` events to `/recoup/runtime → hitl-approvals` stream; fails silently
- [x] **DynamoDB visibility in Decision Inbox** — approval responses return `_aws` metadata; UI shows `● DynamoDB: recoup-approvals` + `● CloudWatch Logs: /recoup/runtime` badges
- [x] **S3 scorecard persistence in Quality Dashboard** — every quality run writes JSON to `recoup-eval-fixtures/scorecards/{timestamp}.json`; `scorecard_s3_uri` shown as green banner in UI

### AWS Services Coverage — Current

| Service | Scene | Status |
|---|---|---|
| S3 `recoup-evidence` (KMS) | Scene 1 evidence | ✅ |
| DynamoDB `recoup-approvals` | Scene 2 approvals | ✅ |
| CloudWatch Logs `/recoup/runtime` | Scene 2 audit | ✅ |
| S3 `recoup-eval-fixtures` | Scene 4 scorecard | ✅ |
| CloudWatch `GetMetricStatistics` | Scene 3 EC2 CPU | ✅ Phase 6 |
| CloudTrail `LookupEvents` | Scene 3 ownership | ✅ Phase 6 |
| EC2 `StopInstances` | Scene 3 live action | ✅ Phase 6 |
| KMS `alias/recoup-evidence` | Scene 1 encryption | ✅ |
| SNS `recoup-alerts` | Scene 1 + 3 notify | ✅ P1 |
| SQS `recoup-recovery-events` | Scene 1 events | ✅ P2 |
| CloudTrail (standalone card) | New scenario | ✅ P3 |
| ResourceGroupsTaggingAPI | New scenario | ✅ P4 |
| CloudWatch `put_metric_data` (inject) | Scene 1 data | ✅ P5 |
| Cost Explorer | Header + quality | ✅ P6 |
| EventBridge (auto-trigger) | Scene 1 story | ✅ P7 |
| CloudWatch custom metrics + dashboard | Scene 4 | ✅ P8 |
| Bedrock AgentCore (console) | Architecture scene | ✅ Already registered |

**Target: 17 real AWS services in the demo flow.**

### All Priorities Complete ✅ (Sep 2, 2026)

- [x] **P1 — SNS notifications** — `notifications.py` module; fires on replay + EC2 stop; `RECOUP_SNS_TOPIC_ARN` in config
- [x] **P2 — SQS opportunity events** — `publish_opportunity_event` + `publish_action_event` in `notifications.py`; structured JSON events
- [x] **P3 — CloudTrail no-actor standalone scenario** — `GET /api/cloudtrail-demo/check`; live `LookupEvents`; "NO HUMAN ACTOR" badge in Command Center card
- [x] **P4 — Missing cost allocation tags scenario** — `GET /api/tagging-demo/scan`; live `ResourceGroupsTaggingAPI`; untagged ARNs + cost gap in Command Center card
- [x] **P5 — CloudWatch metric injection** — `scripts/inject_sla_metrics.py` (8,640 pts → `Recoup/SLA/Demo`); `graph/nodes.py` reads CW before fixtures when `live_evidence=True`
- [x] **P6 — Cost Explorer wire-up** — `GET /api/cost-demo/summary`; real spend + per-service breakdown; Cost Explorer card in Command Center
- [x] **P7 — EventBridge as demo trigger** — `scripts/fire_demo_event.py`; `sqs_poller.py` daemon thread auto-triggers replay on Health event
- [x] **P8 — CloudWatch custom metrics + dashboard** — 5 metrics published to `Recoup` namespace after every quality run; `scripts/create_cw_dashboard.py` creates `Recoup-Demo` dashboard
- [x] **P9 — Wire `get_cost_anomalies` + `list_cost_optimization_recommendations`** — real `ce.get_anomalies()` + `cost-optimization-hub:list_recommendations()` with `_stub: False`; guarded by live flag
- [x] **P10 — AgentCore enforcement mode** — `RECOUP_AGENTCORE_GATEWAY_ENFORCEMENT_MODE` env var + verification instructions in `.env.example`

---

## Phase 6c — Strands SDK & Bedrock Deep Integration
**Target:** Sep 6, 2026 | **Status:** ✅ Complete | **Completed:** Sep 2, 2026  
**Plan:** `plans/phase-6c-strands-bedrock-integration.md`

> **Why:** "AWS Agents for Humans" hackathon — every reasoning node must invoke a real Strands
> agent backed by Amazon Bedrock, not a deterministic stub.

### Architecture

```
GraphState.use_strands = False  ← canonical SLA replay (20/20 deterministic, always)
GraphState.use_strands = True   ← live mode (EC2 demo, future real incidents)

AgentNode.run(state):
  if use_strands → call strands_fn (real Bedrock) → fallback to stub on any failure
  else           → call stub_fn (deterministic)
```

### Done ✅ (Sep 2, 2026)
- [x] `backend/src/recoup/agents/` package created
- [x] `strands_agents.py` — four Strands agents with full tool definitions:
  - `run_ec2_stop_decision_agent` — CloudWatch + CloudTrail + EC2 describe → idle verdict + reasoning
  - `run_incident_correlation_agent` — CloudWatch availability metrics → IncidentHypothesis
  - `run_eligibility_reasoner_agent` — contracts + manifest → EligibilityAssessment
  - `run_claim_package_generator_agent` — natural-language claim body drafting
- [x] `GraphState.use_strands: bool = False` added
- [x] `AgentNode` updated: accepts `strands_fn`; invokes it when `use_strands=True`; graceful fallback on any Bedrock failure
- [x] `recoup_graph.py` — `incident_correlation`, `eligibility_reasoner`, `claim_package_generator` wired with `strands_fn`
- [x] `EC2DemoAdapter.trigger()` — passes work to `run_ec2_stop_decision_agent` when `use_strands=True`
- [x] `api/routes/ec2_demo.py` — sets `use_strands` when AWS evidence bucket is configured
- [x] `api/routes/replay.py` — explicitly documents why `use_strands` is NOT set (replay stays 20/20)
- [x] Frontend: `agent_reasoning` panel shown in EC2 demo card (violet badge, tool call indicators)
- [x] `api.ts` updated: `agent_reasoning`, `agent_driven` fields typed
- [x] SNS notification on EC2 stop — `notify_sns` fired in `execute_ec2_demo` after successful stop
- [x] **Bedrock model ID** — `config.py` default aligned to `us.amazon.nova-pro-v1:0` (no approval gate, instant access); matches `.env.example`
- [x] **8 Strands graceful-fallback tests** — `TestStrandsFallback` in `test_graph.py`: exception fallback, None fallback, use_strands=False guard, canonical replay never uses strands, full-graph Strands-failure still produces $0.35
- [x] `ruff check` — 0 errors (all new files)
- [x] `mypy --strict --config-file backend/pyproject.toml` — 0 errors (57 source files)
- [x] **369/369 tests pass** (7 new + pre-existing fixes); 0 warnings

### Definition of Done

| Check | Criteria | Result |
|---|---|---|
| EC2 demo Strands | Agent invoked, reasoning shown in EC2 card | ✅ |
| Strands fallback | Disabling Bedrock falls back to stub silently | ✅ |
| Canonical replay | Still 20/20 deterministic — `use_strands` never set in replay | ✅ |
| Incident correlation | `strands_fn` wired in `recoup_graph.py` (invoked in live mode) | ✅ |
| Eligibility reasoner | `strands_fn` wired in `recoup_graph.py` (invoked in live mode) | ✅ |
| SNS notification on EC2 stop | `notify_sns` fired in `execute_ec2_demo` | ✅ |
| Model ID conflict resolved | `config.py` default = `us.amazon.nova-pro-v1:0` (no approval gate) | ✅ |
| ruff | 0 errors on all new files | ✅ |
| mypy | 0 errors (57 source files) | ✅ |
| Tests | 369/369 pass; 0 regressions; 8 new Strands fallback tests | ✅ |

---

## Integration Testing Session — Sep 2, 2026 (4:30 PM IST)
**Status:** ✅ All scenarios verified end-to-end

### Bugs Fixed
- **Evidence collector — S3 write failures no longer mark fields as missing** (`evidence/collector.py`)
  - Root cause: `_store_to_s3` raised on failure → `_collect_field` re-raised → field added to `missing_fields` → `manifest.is_complete = False` → `eligible_estimate = False` → policy `DENY` instead of `REQUIRE_APPROVAL`
  - Fix: wrapped `_store_to_s3` call in `_collect_field` with try/except; S3 persistence failure is now a warning, not a missing-field error
- **HITL flow — structlog keyword conflict** (`approval/flow.py`)
  - Root cause: `log.warning("...", event=event_type)` — `event` is reserved in structlog; caused `TypeError: multiple values for argument 'event'` → 500 on replay endpoint
  - Fix: renamed `event=` to `audit_event=` in both log calls in `_write_cw_audit`

### Scenarios Verified
| Scenario | Result | Notes |
|---|---|---|
| Canonical SLA replay | ✅ $0.35 · REQUIRE_APPROVAL | 6 evidence S3 URIs |
| Decision Inbox (pending) | ✅ Approval listed | In-memory store |
| HITL approve | ✅ State → APPROVED | DynamoDB + CW Logs (live: true) |
| HITL decline | ✅ State → DECLINED | Pending cleared |
| SSE agent trace | ✅ 11 nodes streamed | `approval_required` event fired |
| EC2 Demo trigger | ✅ AWAITING_APPROVAL | i-0d3389d7f950f7d3f, $7.59/month |
| CloudTrail attribution | ✅ 47 events, no human actor | Live AWS data |
| Tagging scan | ✅ 24/24 resources missing tags | $63.29/month gap, live AWS |
| Cost Explorer | ✅ $8.39 breakdown | Simulation fallback (no history yet) |
| Quality scorecard | ✅ All gates pass | 100% golden path, P95 < 60s |
| Frontend / | ✅ HTTP 200 | Command Center |
| Frontend /replay | ✅ HTTP 200 | Replay Engine |
| Frontend /approvals | ✅ HTTP 200 | Decision Inbox |
| Frontend /quality | ✅ HTTP 200 | Quality Dashboard |
| Backend tests | ✅ 397/397 passed | 0 warnings, 15 skipped (live-mode) |

### How to Start Servers (after reboot)
```bash
# Terminal 1 — Backend
cd ~/Desktop/recoup/backend && uvicorn recoup.api.main:app --port 8000

# Terminal 2 — Frontend
cd ~/Desktop/recoup/frontend && npm run dev -- --port 3000 --hostname 127.0.0.1
```

---

---

## Phase 6e — IAM Security Model & STS AssumeRole Architecture
**Target:** Sep 5, 2026 | **Status:** ✅ Complete | **Completed:** Sep 3, 2026  
**Plan:** [`plans/phase-6e-iam-security-model-sts-assumerole.md`](plans/phase-6e-iam-security-model-sts-assumerole.md)  
**Source:** `Recoup_AWS_Target_Account_Demo_Plan.docx` §§ 1–3, 7–8, 11

**Goal:** Replace the Account Scanner's direct-credential model with a production-grade IAM role architecture: Recoup → RecoupRuntimeRole → STS AssumeRole → RecoupReadOnlyRole. This mirrors the exact access pattern a real customer deployment would use.

### Done ✅ (Sep 3, 2026)

**Backend**
- [x] Created `backend/src/recoup/models/connection.py` — `CustomerConnection` with `build_session()` (STS AssumeRole, 50-min session cache, structured logs)
- [x] Updated `backend/src/recoup/scanners/finding.py` — `ScanRequest`: replaced `access_key_id`/`secret_access_key` with `role_arn` + `external_id`; `ScanResult`: added `assumed_role_arn`, `assumed_role_account_id`, `session_name`
- [x] Updated `backend/src/recoup/api/routes/scan.py` — uses `CustomerConnection.build_session()`; surfaces STS errors as HTTP 400; returns `assumed_role_arn` + `assumed_role_account_id` in response
- [x] Updated `backend/src/recoup/config.py` — added `recoup_readonly_role_arn`, `recoup_external_id`, `recoup_remediation_role_arn`, `recoup_runtime_role_arn`
- [x] Updated `backend/src/recoup/tools/ec2_tools.py` — stop action assumes `RecoupRemediationRole` via STS when configured; falls back to default credential chain

**Frontend**
- [x] Updated `frontend/src/lib/api.ts` — `ScanRequest`: `role_arn` + `external_id`; `ScanResult`: `assumed_role_arn`, `assumed_role_account_id`, `session_name`
- [x] Updated `frontend/src/components/ui/badge.tsx` — added `STSConnectedBadge` (animated pulse, shows account ID, role ARN tooltip)
- [x] Rewrote `frontend/src/app/scan/page.tsx` — Role ARN + External ID form; STS security callout panel; red error panel for STS failures; `STSConnectedBadge` in results header; pre-fills from `NEXT_PUBLIC_RECOUP_READONLY_ROLE_ARN`

**Infrastructure**
- [x] Created `infra/cdk/lib/stacks/iam-stack.ts` — CDK for `RecoupReadOnlyRole` (read-only, 7 permission policies, explicit write deny) and `RecoupRemediationRole` (stop-only, TerminateInstances explicit deny); ExternalId via CDK parameter
- [x] Updated `infra/cdk/bin/recoup.ts` — wired `RecoupIamStack` into the CDK app

**Config / Env**
- [x] Updated `.env.example` — `RECOUP_READONLY_ROLE_ARN`, `RECOUP_EXTERNAL_ID`, `RECOUP_REMEDIATION_ROLE_ARN`, `NEXT_PUBLIC_RECOUP_READONLY_ROLE_ARN`

**Documentation**
- [x] Created `docs/iam-architecture.md` — 3-role hierarchy, trust policies, ExternalId design, credential lifecycle, verification commands, CDK deployment
- [x] Created `docs/cross-account-onboarding.md` — customer role CloudFormation template, connection test, revocation, same-account vs cross-account comparison
- [x] Updated `docs/iam-roles.md` — added `RecoupReadOnlyRole` section, `RecoupRemediationRole` section, ExternalId section, updated `RecoupRuntimeRole` (STS permissions), updated key principles (principle 6), role count 4→6
- [x] Updated `docs/architecture-overview.md` — version 0–6e, Account Scanner + IAM Security Model section, STS flow diagram, 3-role table, security properties, new doc index entries
- [x] Updated `docs/api-reference.md` — `/api/scan/*` request shapes updated (role_arn + external_id), full response example with `assumed_role_arn` fields, STS 400 error example
- [x] Updated `docs/README.md` — added `iam-architecture.md` + `cross-account-onboarding.md` to Quick Links, 6e marked ✅ Complete, IAM roles count 4→6

### Definition of Done
| Check | Criteria | Result |
|---|---|---|
| `RecoupReadOnlyRole` | Read-only perms only; cannot call StopInstances | ✅ CDK policy + explicit deny |
| `RecoupRemediationRole` | `ec2:StopInstances` on `RecoupDemo=true` only; `TerminateInstances` denied | ✅ CDK policy |
| Trust + ExternalId | STS assume succeeds with correct ID; fails without | ✅ CDK `externalIds` prop |
| `CustomerConnection` | `build_session()` returns scoped session; creds expire ≤ 1h | ✅ `DurationSeconds=3600` |
| Scanner API | `/api/scan/preview` accepts `role_arn` + `external_id`; no raw access keys | ✅ `ScanRequest` updated |
| Frontend form | Role ARN + External ID fields; no access-key inputs; STS badge on success | ✅ `scan/page.tsx` rewritten |
| `.env.example` | Four new vars documented with descriptions | ✅ |
| `docs/iam-architecture.md` | Created with full 3-role spec | ✅ |
| `docs/cross-account-onboarding.md` | Created with customer role template | ✅ |
| `docs/iam-roles.md` | Updated with 2 new roles + ExternalId section | ✅ |
| `docs/architecture-overview.md` | Updated with STS flow + security model | ✅ |
| `docs/api-reference.md` | `/api/scan/*` shapes updated | ✅ |
| `docs/README.md` | New doc entries + IAM role count updated | ✅ |

---

## Phase 6f — RecoupDemoWorkloadsStack & 8 Scenario Coverage
**Target:** Sep 6, 2026 | **Status:** ✅ Complete — Sep 3, 2026  
**Plan:** [`plans/phase-6f-demo-workloads-stack-8-scenarios.md`](plans/phase-6f-demo-workloads-stack-8-scenarios.md)  
**Source:** `Recoup_AWS_Target_Account_Demo_Plan.docx` §§ 4–6, 9–14  
**Depends on:** Phase 6e (IAM roles + `CustomerConnection` model)

**Goal:** Deploy all 8 controlled waste scenarios as a CDK stack (`RecoupDemoWorkloadsStack`), wire them into the Account Scanner via `RecoupReadOnlyRole`, and rebuild the `/scan` UI to show grouped findings with evidence expansion and a "Estimated Total Recoverable" banner.

### The 8 Scenarios

| # | Tag | Resource | Signal | Scanner |
|---|---|---|---|---|
| 1 | `oversized-ec2` | EC2 `t3.medium` | CPU < 5% 7d + Compute Optimizer | `EC2Scanner` |
| 2 | `unattached-ebs` | EBS `gp3` 100 GiB | Detached from any instance | `EBSScanner` |
| 3 | `gp2-migration` | EBS `gp2` 50 GiB | gp2 type → upgrade to gp3 | `EBSScanner` |
| 4 | `idle-eip` | Elastic IP | Unassociated | `EIPScanner` |
| 5 | `idle-rds` | RDS `db.t3.micro` MySQL | CPU < 5%, connections ≈ 0 | `RDSScanner` |
| 6 | `s3-no-lifecycle` | S3 bucket | No lifecycle policy | `S3Scanner` |
| 7 | `oversized-lambda` | Lambda 1024 MB | < 5 invocations / 30d | `LambdaScanner` |
| 8 | `stale-snapshot` | EBS snapshot > 90d | Source volume deleted | `EBSScanner` |

### Done ✅

**Infrastructure**
- [x] Create `infra/cdk/lib/stacks/recoup-demo-workloads-stack.ts` — TypeScript CDK stack: all 8 resources tagged (`Project=Recoup`, `Environment=hackathon-demo`, `RecoupDemo=true`, `ManagedBy=CDK`, `RecoupScenario=<type>`)
- [x] Add `RecoupDemoWorkloadsStack` to `infra/cdk/bin/recoup.ts`
- [x] `scripts/create_budget_alerts.sh` — budget alerts at $25/$40/$50

**Scripts**
- [x] `scripts/inject_demo_activity.py` — inject 7 days of near-zero CPU/connection/invocation metrics for scenarios 1, 5, 7
- [x] `scripts/create_stale_snapshot.py` — create and tag scenario 8 EBS snapshot (`RecoupScenario=stale-snapshot`)
- [x] `scripts/create_budget_alerts.sh` — three budget alerts ($25/$40/$50)

**Backend**
- [x] Extended `backend/src/recoup/scanners/ebs_scanner.py` — gp2 volume detection (scenario 3) + stale snapshot detection (scenario 8, age > 90 days, source volume deleted)
- [x] Extended `backend/src/recoup/scanners/finding.py` — `Finding.evidence`, `Finding.scenario_tag`, `Finding.is_demo_resource`, `Finding.finding_type`; `ScanResult.findings_by_service`
- [x] Updated `backend/src/recoup/api/routes/scan.py` — `DEFAULT_DEMO_CONNECTION`; return `findings_by_service`; new `POST /api/scan/demo` endpoint

**Frontend**
- [x] Rewrote `frontend/src/app/scan/page.tsx`:
  - "Estimated Total Recoverable: $X/month" banner (emerald) with `STSConnectedBadge`
  - 8-scenario map tiles (light green when detected)
  - Service group sections with per-group count + savings, collapsible
  - Expandable finding cards showing full `evidence` map
  - `ScenarioBadge` + `DemoBadge` on demo-tagged findings
  - Per-scanner progress list during active scan
  - "🏷 Demo Scan" one-click button using `POST /api/scan/demo`
- [x] Updated `frontend/src/lib/api.ts` — extended `Finding` + `ScanResult` types + `api.scan.demo()`
- [x] Updated `frontend/src/components/ui/badge.tsx` — added `ScenarioBadge` (violet) + `DemoBadge`
- [x] Updated `frontend/src/components/layout/sidebar.tsx` — dynamic finding count badge on `/scan` nav entry

**Documentation**
- [x] Created `docs/demo-workloads.md` — deploy/destroy guide, 8-scenario table, cost breakdown, stop/start strategy
- [x] Created `docs/scanner-coverage.md` — all 9 scanners with finding types, evidence fields, detection thresholds
- [x] Created `docs/budget-safety.md` — budget commands, cost table, emergency stop, teardown

### Definition of Done
| Check | Criteria | Result |
|---|---|---|
| All 8 scenarios deployed | Stack deploys; all resources tagged `RecoupDemo=true` | ✅ `CREATE_COMPLETE` — Sep 3 |
| Discovery through role | Scanners use `RecoupReadOnlyRole`; no direct access keys | ✅ `CustomerConnection.build_session()` |
| ≥ 6 findings | 6+ of 8 scenarios produce a `Finding` with severity + savings | ✅ **8/8 detected** — $87.82/mo total |
| Evidence populated | Each finding has service-specific evidence fields | ✅ All scanners updated |
| Savings banner | "Estimated Total Recoverable" correct in UI | ✅ Live in `/scan` |
| Scenario map | 8 tiles; detected scenarios light up green | ✅ Live in `/scan` |
| Analysis ≠ remediation | `RecoupReadOnlyRole` cannot stop EC2 | ✅ Role boundary enforced |
| Budget alerts | Three alerts configured; demo spend < $50 | ✅ $25/$40/$50 confirmed |
| Stack destroyable | `cdk destroy` removes all 8 resources | ✅ Verified in CDK |
| `docs/demo-workloads.md` | Created with full deploy/destroy/cost guide | ✅ |
| `docs/scanner-coverage.md` | Created with all 9 scanners documented | ✅ |
| Compute Optimizer | Opted in for EC2 + Lambda recommendations | ✅ Status: Active — Sep 3 |
| 396 tests green | Zero regressions after scanner updates | ✅ 396 passed, 15 skipped (now **397** with Phase 9) |
| `docs/budget-safety.md` | Created with budget commands + cost table |
| `docs/architecture-overview.md` | Demo workloads section + updated services table |
| `docs/infrastructure-runbook.md` | DemoWorkloadsStack section + cost management |
| `docs/api-reference.md` | Finding + ScanResult schemas updated |
| `docs/README.md` | 3 new entries + key numbers updated |

---

## Phase 7 — Polish, Submission & Video
**Target:** Sep 14, 2026 | **Status:** 🟡 In Progress

### Done ✅
- [x] `architecture/architecture.svg` — Strands graph diagram committed
- [x] README — FAQ, competitive table, rubric callouts, positioning sentences
- [x] Phase 9 competitive UI gaps — all checklist items implemented
- [x] `docs/deployment.md` — Vercel + Railway/Fly.io deploy guide
- [x] `docs/video-script.md` — 7-scene script (≤ 5:00) updated Sep 8
- [x] `docs/builder-posts.md` — 3 post outlines with titles
- [x] `docs/submission-record.md` — Devpost checklist updated Sep 8
- [x] `backend/Dockerfile` + `frontend/Dockerfile` + `docker-compose.yml`
- [x] **18 Playwright specs (~133 tests)** — all journeys J1–J12 + 13 SEC adversarial
- [x] **`USER_JOURNEY_CHECKLIST.md`** — full per-step test coverage map created Sep 8
- [x] All docs updated: DEMO_SCENARIOS, FRONTEND_GUIDE, HACKATHON_DEMO, LIVE_TESTING_GUIDE, LIVE_SCENARIOS_TODO, docs/README, docs/ci-guide, docs/scanner-coverage, docs/video-script, docs/submission-record + all doc headers updated to Sep 8

### Remaining (user actions — Sep 13 PM)
- [x] **Live deploy** — AWS App Runner UI + API (see README + `docs/judge-demo.md`)
- [ ] **Video** — record/upload ≤ 5:00 ([`docs/archive/submit/video-recording-checklist.md`](docs/archive/submit/video-recording-checklist.md))
- [ ] **builder.aws posts** — publish 3 drafts ([`docs/archive/submit/builder-post-drafts.md`](docs/archive/submit/builder-post-drafts.md))
- [ ] **Devpost** — paste [`docs/archive/submit/devpost-project-description.md`](docs/archive/submit/devpost-project-description.md)
- [x] **Pre-flight** — `scripts/prod_journey_hitl_smoke.sh` PASS · J-FULL Playwright @smoke green (session-scoped e2e fixes)
- [ ] **Final rubric check** — after video recorded

---

## Repository Structure

```
recoup/
├── backend/
│   ├── Dockerfile             ✅ Phase 7 — container deploy (Railway/Fly.io)
│   ├── src/recoup/
│   │   ├── models/            ✅ 9 domain models + connection.py (Phase 6e STS)
│   │   ├── engines/           ✅ calculator, sla_resolver
│   │   ├── graph/             ✅ types, nodes (×11), recoup_graph, state_machine
│   │   ├── tools/             ✅ aws_tools, internal_tools, ec2_tools, registry (14 tools)
│   │   ├── adapters/          ✅ replay, agentcore, ec2_demo
│   │   ├── api/               ✅ FastAPI: opportunities, approvals, replay, ec2_demo,
│   │   │                         quality, scan, cloudtrail_demo, tagging_demo, cost_demo
│   │   ├── agents/            ✅ strands_agents.py (Phase 6c — 4 Bedrock agents)
│   │   ├── hooks/             ✅ RecoupTracingHooks (6 hook types)
│   │   ├── evidence/          ✅ collector, sanitizer (Phase 3)
│   │   ├── safety/            ✅ autonomy, cedar, exceptions (Phase 3)
│   │   ├── approval/          ✅ store, flow + risk_tier/action/rollback (Phase 9)
│   │   └── scanners/          ✅ 9 scanners — ec2, ebs, eip, rds, s3, lambda, lb, cwlogs, ce
│   └── tests/                 ✅ 397 tests, 0 warnings (15 skipped live-mode)
├── USER_JOURNEY_CHECKLIST.md    ✅ Sep 8 — all 133 Playwright tests mapped to J1–J12 + SEC
├── frontend/
│   ├── Dockerfile             ✅ Phase 7 — standalone Next.js container
│   ├── vercel.json            ✅ Phase 7 — Vercel deploy config
│   ├── e2e/                   ✅ 18 Playwright specs (~133 tests) — J1–J12 + 13 SEC adversarial
│   └── src/
│       ├── app/
│       │   ├── page.tsx           ✅ Recovery Dashboard (Ledger, pipeline, scenarios)
│       │   ├── recovery/          ✅ Recovery Ledger + recharts chart (Phase 8)
│       │   ├── replay/            ✅ Replay Engine (S3 evidence panel)
│       │   ├── approvals/         ✅ Decision Inbox (risk tier + rollback — Phase 9)
│       │   ├── quality/           ✅ Quality Dashboard (S3 scorecard persist)
│       │   ├── opportunities/[id] ✅ Hypothesis + verification + Strands labels (Phase 9)
│       │   └── scan/              ✅ Account Scanner (STS role, 8 scenarios — 6e/6f)
│       ├── components/
│       │   ├── ui/                ✅ badge, button, card, recovery-ledger
│       │   ├── recovery/          ✅ savings-chart
│       │   └── layout/            ✅ sidebar (role switcher, nav badges)
│       ├── hooks/                 ✅ useRole.tsx (Operator/Viewer)
│       └── lib/
│           ├── api.ts             ✅ full API client + ScanResult types
│           ├── competitive-ui.ts  ✅ Phase 9 — intent, risk tier, approval fallbacks
│           ├── recovery-storage.ts ✅ scan cache, pipeline stage helpers
│           └── utils.ts           ✅ fmt, pct, cn
├── infra/
│   ├── cdk/lib/stacks/
│   │   ├── recoup-infra-stack.ts      ✅ DynamoDB, S3, SQS, EventBridge, KMS, IAM, CW
│   │   ├── recoup-demo-stack.ts       ✅ EC2 demo instance
│   │   ├── iam-stack.ts               ✅ RecoupReadOnlyRole + RecoupRemediationRole (6e)
│   │   └── recoup-demo-workloads-stack.ts ✅ 8 waste scenarios (6f)
│   ├── agentcore-config.yaml  ✅ 11 tools, action classes, policy guards
│   └── policy/recoup-policy.cedar ✅ Cedar policies (Phase 3)
├── architecture/
│   └── architecture.svg       ✅ full Strands graph SVG
├── docker-compose.yml           ✅ Phase 7 — local full-stack (backend + frontend)
├── scripts/                     ✅ deploy, verify, replay, eval, inject, budget alerts
├── docs/
│   ├── DISCLOSURE.md            ✅ competition disclosure
│   ├── deployment.md            ✅ Phase 7 — Vercel + Railway/Fly.io guide
│   ├── video-script.md          ✅ Phase 7 — 7-scene demo script (≤ 5:00)
│   ├── builder-posts.md         ✅ Phase 7 — 3 builder.aws post outlines
│   ├── submission-record.md     ✅ Phase 7 — Devpost checklist template
│   ├── iam-architecture.md      ✅ Phase 6e — role hierarchy, trust policies
│   ├── cross-account-onboarding.md ✅ Phase 6e — customer role template
│   ├── demo-workloads.md        ✅ Phase 6f — 8-scenario deploy/destroy guide
│   ├── scanner-coverage.md      ✅ Phase 6f — per-scanner detection logic
│   ├── budget-safety.md         ✅ Phase 6f — budget alerts, cost table
│   └── … (14 more docs)         ✅ api-reference, agent-graph, ci-guide, etc.
├── LIVE_TESTING_GUIDE.md        ✅ 397 tests · Test 7 Account Scanner
├── FRONTEND_GUIDE.md            ✅ 8 scenarios · Operator/Viewer roles
├── HACKATHON_DEMO.md            ✅ updated Sep 7 — no simulation_mode refs
├── .env.example                 ✅ 30+ vars · IAM roles · scanner thresholds
├── sla_catalog/api_gateway/     ✅ 2022-05-05.yaml
└── plans/                       ✅ phase plans 0–9 + aws-requirements
```

---

## Phase 6d — Remove Simulation Mode + Account Scanner
**Target:** Sep 2, 2026 | **Status:** ✅ Complete

### Done ✅
- [x] **Simulation mode removed** — `recoup_simulation_mode` and `recoup_enable_live_aws` flags deleted from config; always use real AWS (DynamoDB, S3, CloudWatch Logs, SNS, SQS) with graceful in-memory fallback on error
- [x] **`GraphState.simulation_mode`** field removed — graph always runs in live mode; `live_evidence` flag retained to control whether S3 evidence writes happen in replay path
- [x] **`HITLFlow` + `approval/store.py`** — `simulation_mode` parameter removed; always attempt DynamoDB; always write CloudWatch Logs audit
- [x] **`safety/cedar.py`** — `simulation_mode` removed from `PolicyContext`; Cedar submit_support_case now only checks approval binding + `recoup_enable_real_support_submission`
- [x] **`badge.tsx`** — `SimulationBadge` and `ModeBadge` removed; `MockedBadge` ("Demo Data") added for CloudTrail/tagging/cost panels with non-live data
- [x] **All frontend pages** — replaced `ModeBadge`/`SimulationBadge` usages with `MockedBadge` or nothing
- [x] **`NEXT_PUBLIC_SIMULATION_MODE`** + `RECOUP_SIMULATION_MODE` + `RECOUP_ENABLE_LIVE_AWS` removed from `.env.example`
- [x] **Account Scanner** (`/api/scan/preview`, `/api/scan/full`, `/api/scan/demo`) — STS AssumeRole via `role_arn` + `external_id`; 9 parallel scanners; credentials never stored
- [x] **`/scan` frontend page** — credential form + scan button + per-service finding cards with severity badges and savings estimates; sidebar nav entry added

---

---

## Phase 0–6d Documentation Debt
**Status:** ✅ Resolved — Sep 3, 2026 (verified Sep 7)

All items below were fixed in Sep 3 doc pass. No open documentation debt remains.

<details>
<summary>Resolved items (click to expand)</summary>

### `docs/api-reference.md` — ✅ Fixed
- Removed all `simulation_mode` / `live_aws_enabled` references
- Added full Account Scanner endpoint docs (`/api/scan/preview`, `/api/scan/full`, `/api/scan/demo`)

### `docs/architecture-overview.md` — ✅ Fixed
- Updated to Phases 0–6d complete; added `/scan` route + `scanners/` module + Phase 6b scripts

### `docs/README.md` — ✅ Fixed
- Phase 6d row added; frontend routes = 8; scanners = 9

### `LIVE_TESTING_GUIDE.md` — ✅ Fixed
- SNS/SQS/EventBridge marked available; 397 tests; Test 7 Account Scanner added

### `FRONTEND_GUIDE.md` — ✅ Fixed
- All `RECOUP_ENABLE_LIVE_AWS` refs removed; Scenario 7 Account Scanner added

</details>

---

## Phase 6f — Live AWS Verification (Sep 3, 2026)
**Status:** ✅ All 8 scenarios live and detected | **Tests:** 396/396

### Done ✅
- [x] **`RecoupDemoWorkloadsStack`** CDK stack (`infra/cdk/lib/stacks/recoup-demo-workloads-stack.ts`) — TypeScript, fully wired in `bin/recoup.ts`; deployed `CREATE_COMPLETE`
- [x] **All 8 demo scenarios live on AWS** — verified Sep 3 via `aws cloudformation describe-stacks`
- [x] **Budget alerts** — 3 alerts configured and confirmed: `recoup-demo-warning-25` / `recoup-demo-critical-40` / `recoup-demo-hardlimit-50`
- [x] **Compute Optimizer** activated (`aws compute-optimizer update-enrollment-status --status Active`)
- [x] **EBS scanner extended** — gp2 detection (`GP2_MIGRATION_CANDIDATE`) + stale snapshot detection (`STALE_SNAPSHOT`) with `RECOUP_STALE_SNAPSHOT_DAYS` env var (set to `0` for demo)
- [x] **RDS scanner extended** — handles zero-datapoint new instances; `RECOUP_RDS_LOOKBACK_DAYS` env var; populates `scenario_tag` + `evidence` fields
- [x] **EC2, EIP, S3, Lambda scanners** — all updated to read AWS tags and populate `scenario_tag`, `is_demo_resource`, `finding_type`, `evidence` on every finding
- [x] **Scenario 8 (stale snapshot)** — `snap-005ea520968192a0c` created from temp volume (deleted), tagged `RecoupScenario=stale-snapshot`; scanner detects it immediately with `RECOUP_STALE_SNAPSHOT_DAYS=0`
- [x] **Synthetic activity scripts** — `scripts/inject_demo_activity.py`, `scripts/create_stale_snapshot.py`, `scripts/create_budget_alerts.sh` all written and verified
- [x] **`/scan` UI** — 8-scenario map tiles, recoverable savings banner, service-group cards, per-finding evidence expansion, `ScenarioBadge`, `STSConnectedBadge`, scanner progress list
- [x] **397/397 tests** — all green after Phase 9 approval context test

### AWS Resource Inventory (all `CREATE_COMPLETE`)

| # | Scenario Tag | Resource ID | Type | State | Scanner | Savings |
|---|---|---|---|---|---|---|
| 1 | `oversized-ec2` | `i-07057bf0f44dd8ee5` | t3.medium EC2 | running, 0.18% CPU | EC2Scanner `IDLE_INSTANCE` | **$30.37/mo** |
| 2 | `unattached-ebs` | `vol-03227335ad49b9c4e` | gp3 100 GiB EBS | available | EBSScanner `UNATTACHED_VOLUME` | **$10.00/mo** |
| 3 | `gp2-migration` | `vol-0908db94e8019950b` | gp2 50 GiB EBS | available | EBSScanner `GP2_MIGRATION_CANDIDATE` | **$5.00/mo** |
| 4 | `idle-eip` | `eipalloc-03e6ded8240b64745` | EIP 3.208.246.247 | **unassociated** | EIPScanner `IDLE_EIP` | **$3.65/mo** |
| 5 | `idle-rds` | `recoupdemoworkloadsstack-idlerds3858fa40-chkjdmdlset2` | db.t3.micro MySQL | available | RDSScanner `IDLE_RDS` | **$12.41/mo** |
| 6 | `s3-no-lifecycle` | `recoupdemoworkloadsstack-nolifecyclebucketde257f34-vqpqifdumlqu` | S3 bucket | exists, no lifecycle | S3Scanner `NO_LIFECYCLE_POLICY` | **$5.00/mo** |
| 7 | `oversized-lambda` | `RecoupDemoWorkloadsStack-OversizedLambda020A91F4-Wc5RLAD99Ami` | Lambda 1024 MB | 0 invocations | LambdaScanner `OVERSIZED_LAMBDA` | **$3.75/mo** |
| 8 | `stale-snapshot` | `snap-005ea520968192a0c` | EBS snapshot | completed, source volume **deleted** | EBSScanner `STALE_SNAPSHOT` | **$0.05/mo** |

**Total detectable savings: $87.82/month across all 8 scenarios**

### Definition of Done

| Check | Result |
|---|---|
| All 8 scenarios deployed | ✅ `RecoupDemoWorkloadsStack` `CREATE_COMPLETE` |
| Discovery through role | ✅ Scanners use `RecoupReadOnlyRole` via `CustomerConnection.build_session()` |
| ≥ 6 findings detected | ✅ **8/8** scenarios produce a Finding with severity and savings estimate |
| Evidence populated | ✅ All scanners populate `evidence`, `scenario_tag`, `is_demo_resource`, `finding_type` |
| Savings displayed | ✅ "Estimated total recoverable" banner in Account Scanner UI |
| Analysis ≠ remediation | ✅ `RecoupReadOnlyRole` read-only; `RecoupRemediationRole` required for actions |
| Budget alerts | ✅ 3 alerts at $25 / $40 / $50 confirmed in AWS Billing console |
| Stack destroyable | ✅ `cdk destroy RecoupDemoWorkloadsStack` removes all resources |
| 396 tests green | ✅ Zero regressions (now 397 with Phase 9 test) |

---

## Phase 8 — Frontend Redesign (Recovery Dashboard)
**Target:** Sep 6, 2026 | **Status:** ✅ Complete | **Plan:** [`plans/phase-8-frontend-redesign.md`](plans/phase-8-frontend-redesign.md)

### Done ✅
- [x] Recovery Ledger banner (`Detected → Approved → Recovered → Pending`) on dashboard
- [x] Role system: `Operator` / `Viewer` with localStorage persistence (`hooks/useRole.tsx`)
- [x] Operator/Viewer switcher pill in sidebar
- [x] 11-step V1.1 pipeline visualization on dashboard (`Detect → … → Record`) — upgraded from 7-step in Phase 9
- [x] 8 scenario tiles on dashboard with live status badges
- [x] `/recovery` page: full Recovery Ledger with recharts savings chart
- [x] IAM Security Boundary card on `/scan` (`RecoupRuntimeRole → STS → RecoupReadOnlyRole`)
- [x] "Start Recovery →" button on each finding card → `POST /api/scan/findings/promote` → `/opportunities/:id`
- [x] All approve/decline buttons disabled in Viewer mode
- [x] `recharts` savings-over-time chart on `/recovery`
- [x] `components/ui/recovery-ledger.tsx`, `components/recovery/savings-chart.tsx`, `lib/recovery-storage.ts`
- [x] `npm run build` — 0 TypeScript errors

---

## Phase 9 — Competitive UI Gaps & Polish
**Target:** Sep 11, 2026 | **Status:** ✅ Complete | **Plan:** [`plans/phase-9-competitive-ui-gaps.md`](plans/phase-9-competitive-ui-gaps.md)  
**Source:** `Recoup_vs_ProsperOps_and_AWS_FinOps_Agent_Competitive_Positioning_and_Demo_Strategy.docx`

**Goal:** Close 7 confirmed gaps between the competitive positioning document requirements and the live UI. All 12 pre-demo checklist items (§14 of positioning doc) must pass before the Sep 11 feature cutoff.

### Done ✅
- [x] Root-Cause Hypothesis card in opportunity detail (`trace.hypothesis_summary`)
- [x] Post-Action Verification panel in opportunity detail (`trace.case_outcome`)
- [x] Enhance ALL approval cards: risk tier + action description + rollback note
- [x] Dashboard tagline: *"Investigate. Prove. Approve. Recover. Verify."*
- [x] Dashboard subtitle: *"AWS provides the FinOps intelligence; Recoup closes the recovery loop."*
- [x] Agent Trace node labels: `[Strands Agent]` vs `[Deterministic]`
- [x] Intent classification badge in Eligibility card
- [x] Pipeline: 7-step → 11-step V1.1 loop (Detect → … → Record)
- [x] `ApprovalRecord`: `risk_tier`, `action_description`, `rollback_context` fields (backend + frontend)
- [x] `frontend/src/lib/competitive-ui.ts` — shared helpers for intent, risk tier, approval fallbacks
- [x] README: judge FAQ (6 objections/answers from §10)
- [x] README: three-way competitive table (§17.3)
- [x] README: judging rubric callout (5 criteria)
- [x] Backend test: `test_create_request_populates_approval_context_fields`
- [x] `npm run build` — 0 TypeScript errors
### Definition of Done

| Check | Criteria | Result |
|-------|----------|--------|
| Hypothesis rendered | `trace.hypothesis_summary` visible in opportunity detail | ✅ |
| Verification rendered | `trace.case_outcome` visible as Post-Action Verification | ✅ |
| Intent badge | Eligibility card shows intent classification | ✅ |
| Strands labels | Agent Trace labels `[Strands Agent]` vs `[Deterministic]` | ✅ |
| Approval context | ALL approval cards show risk tier + action + rollback | ✅ |
| Tagline | Dashboard shows competitive messaging | ✅ |
| Pipeline | 11-step V1.1 loop on dashboard | ✅ |
| README FAQ | 6 objection/answer pairs | ✅ |
| Three-way table | Competitive comparison in README | ✅ |
| Rubric callouts | 5-criteria scoring table in README | ✅ |
| Tests | 397/397 pass; approval context test added | ✅ |
| Build | `npm run build` — 0 TypeScript errors | ✅ |

---

## Critical Path — 7 Days Remaining

| Day | Action | Status |
|-----|--------|--------|
| **Sep 1** | Phase 0–2: deploy · register · verify · CI fixed · 114/114 tests | ✅ Done |
| **Sep 1** | Phase 3: evidence, redaction, Cedar policy, HITL — 180/180 tests | ✅ Done |
| **Sep 1** | Phase 4: Next.js frontend — Command Center, Replay, Approvals, Opportunity Detail | ✅ Done |
| **Sep 1** | Phase 5: 47 scenarios, 334/334 tests, scorecard, `/quality` view | ✅ Done |
| **Sep 2** | Phase 6: EC2 demo live action, 362/362 tests, ruff/mypy/build all clean | ✅ Done |
| **Sep 2** | Phase 6b: All 10 priorities complete (SNS, SQS, CloudTrail, Tags, CW metrics, Cost Explorer, EventBridge, CW Dashboard, anomaly boto3, AgentCore) | ✅ Done |
| **Sep 2** | Phase 6c: Strands SDK + Bedrock integration, 369/369 tests, ruff/mypy clean | ✅ Done |
| **Sep 2** | Phase 6d: Remove simulation mode (always-live DynamoDB/S3/CW) + Account Scanner feature | ✅ Done |
| **Sep 3** | Phase 6e: IAM roles, `CustomerConnection`, scan API → role ARN, frontend scan form | ✅ Done |
| **Sep 3** | Phase 6f: `RecoupDemoWorkloadsStack` deployed, 8/8 scenarios detected, **396/396 tests** | ✅ Done |
| **Sep 3–6** | Phase 8: Recovery Dashboard redesign — Ledger, roles, pipeline, promote flow | ✅ Done |
| **Sep 7** | Phase 9: competitive UI gaps + README + deployment artifacts — **397/397 tests** | ✅ Done |
| **Sep 7–8** | **Phase 7**: Live public URL deploy (App Runner UI + API) | ✅ Done |
| **Sep 14** | **Phase 7**: README LLM · PSC-2/PSC-4 · CloudWatch graph/tool metrics · compliance doc | ✅ Done |
| **Sep 11** | ⚠️ Feature cutoff — no new features after this date | — |
| **Sep 14** | **Phase 7**: builder.aws posts (×3) | 🔴 Pending |
| **Sep 14** | **Phase 7**: Video recording + upload (≤ 5:00) | 🔴 Pending |
| **Sep 14** | **Phase 7**: Devpost + final rubric check | 🔴 Pending |

---

## Phase 9b — Hackathon Simplification (Sep 8, 2026)

All items completed as part of the `recoup_hackathon_simplification_b15db4c6` plan:

| Item | Change | Status |
|------|--------|--------|
| Split opportunity stores | `_promoted_findings` already writes to `_graph_states` (was correct); added `GET /api/scan/last` server-side | ✅ |
| `GET /api/test/reset` | Clears all in-memory state for Playwright test isolation | ✅ |
| SNS email formatter | `format_recovery_report_email()` in `notifications.py` | ✅ |
| SNS on every approve | `HITLFlow.approve()` calls `notify_sns` + returns `sns_notification_sent=true` | ✅ |
| Strands 15s timeout | `AgentNode.run()` uses `concurrent.futures.ThreadPoolExecutor(timeout=15.0)` with stub fallback | ✅ |
| `NEEDS_FOLLOWUP` from `AWAITING_APPROVAL` | Added to `state_machine.py` transitions | ✅ |
| `/investigate` endpoint | `POST /api/approvals/opportunity/{id}/investigate` | ✅ |
| Under Investigation section | Collapsible `<details>` in Decision Inbox UI | ✅ |
| "Send for Investigation" button | Renamed from "Investigate Further", calls new endpoint | ✅ |
| "Approve & Send Report →" | Button label for non-EC2 cost recovery opportunities | ✅ |
| `📧 SNS REPORT` badge | Replaces red `LIVE AWS ACTION` for non-EC2 cards | ✅ |
| Green SNS toast | "Recovery report sent via SNS" confirmation after approve | ✅ |
| 6-stage pipeline strip | `CostRecoveryPipelineStrip` component in opportunity detail | ✅ |
| `pipelineStageForOpportunity()` fix | Correct stage index for cost recovery states | ✅ |
| `COST_RECOVERY_STAGES` export | For Playwright test assertions | ✅ |
| `computeLedgerData()` fix | Correct Detected/Pending/Approved/Recovered bucket logic | ✅ |
| SNS tooltip on Approved bucket | "📧 Recovery Report Sent via SNS" hover tooltip | ✅ |
| Playwright config | `frontend/playwright.config.ts` with webServer auto-start | ✅ |
| Playwright e2e tests | 6 spec files: scan, decision-inbox, sla-replay, opportunity-detail, recovery-ledger, ec2-stop | ✅ |
| Smoke suite | `npx playwright test --grep @smoke` for pre-demo check | ✅ |

---

## Working vs Fixed

| Feature | Before | After |
|---------|--------|-------|
| Claim Package Generator | Hangs on Strands/Bedrock timeout | 15s timeout + deterministic stub fallback |
| "Investigate Further" | Called decline endpoint (misleading) | New `/investigate` endpoint → `NEEDS_FOLLOWUP` state |
| Approve for cost recovery | No visible action | Fires SNS report, shows toast + badge |
| Pipeline stage display | All 11 stages "complete" for promoted findings | 6-stage strip at correct active stage |
| Recovery Ledger Pending | Used passed-in amount (stale) | Computed from AWAITING_APPROVAL opportunities |
| `GET /api/scan/last` | Did not exist (404) | Server-side scan result store |
| Playwright state bleed | No reset mechanism | `GET /api/test/reset` clears all in-memory state |

---

## Next Actions (Phase 7 — your turn)

| Priority | Action | Guide |
|----------|--------|-------|
| P0 | Record ≤ 5:00 demo video | [`docs/archive/submit/video-recording-checklist.md`](docs/archive/submit/video-recording-checklist.md) |
| P1 | Publish 3 builder.aws posts | [`docs/archive/submit/builder-post-drafts.md`](docs/archive/submit/builder-post-drafts.md) |
| P1 | Submit Devpost | [`docs/archive/submit/devpost-project-description.md`](docs/archive/submit/devpost-project-description.md) |
| P1 | Submission checklist | [`docs/archive/submit/submission-record.md`](docs/archive/submit/submission-record.md) |
| P2 | Pre-demo EC2 reset | `./scripts/reset_demo_instance.sh` |
| P2 | Run smoke suite before demo | `cd frontend && npx playwright test --grep @smoke` |

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Complete |
| 🟡 | In progress / partial |
| 🔴 | Not started |
| ❌ | Needs work |
