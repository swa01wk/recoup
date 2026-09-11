# Phase 6d — Remove Simulation Mode + Account Scanner

> **Historical implementation plan.** Targets below reflect mid-build intent. **Current product & metrics:** [docs/README.md](../docs/README.md) · [STATUS.md](../STATUS.md) · [docs/judge-demo.md](../docs/judge-demo.md).



**Timeline:** Sep 2, 2026  
**Status:** `[x] Complete`  
**Depends on:** Phase 6 ✅, Phase 6b ✅, Phase 6c ✅  
**Plan file:** `plans/phase-6d-remove-simulation-mode-account-scanner.md`

---

## Why This Phase Exists

Two motivations drove this phase:

1. **Simulation mode was a crutch.** `recoup_simulation_mode` and `recoup_enable_live_aws` were opposing boolean flags that had accumulated throughout phases 0–6c. Every call site had an `if simulation_mode:` branch that returned stub data instead of hitting real AWS. With all AWS infrastructure live and tested, these flags added complexity without benefit — and confused the Cedar policy, the HITL flow, and the frontend. Removing them makes the system always-live, with graceful in-memory fallbacks only on error.

2. **Account Scanner adds direct user value.** A user who wants to find waste in their *own* AWS account shouldn't have to trigger the SLA recovery graph. The Account Scanner lets them paste credentials, click scan, and get a ranked list of savings opportunities across 9 services — all without any data leaving their browser scope (credentials never persisted).

---

## Design Decisions

### Simulation Mode Removal

**Old model:** two explicit flags controlled every branch
```
RECOUP_SIMULATION_MODE=true   ← stub all AWS calls
RECOUP_ENABLE_LIVE_AWS=true   ← enable real calls
```

**New model:** infer live capability from configured resources
```python
@property
def live_aws_enabled(self) -> bool:
    return bool(
        self.evidence_bucket
        or self.recoup_sns_topic_arn
        or self.recovery_events_queue_url
        or self.approvals_table
    )
```

Real AWS calls are always attempted. If they fail (no credentials, no table), the system falls back to in-memory stores and logs a warning — the demo never hard-fails.

### EC2 Demo Stub Detection

The EC2 demo adapter replaced its `simulation_mode: bool` parameter with an instance-based check:

```python
def _is_stub_instance(self, instance_id: str) -> bool:
    allowed_ids = settings.demo_instance_ids
    return instance_id == "i-demo0000000000000" or not allowed_ids
```

This means the demo runs with deterministic stub data when no real instance is allowlisted, without any explicit flag.

### Account Scanner Architecture

```
POST /api/scan/full     ← all 9 scanners in parallel (~15–30s)
POST /api/scan/preview  ← EC2 + Cost Explorer only (~5s)

_build_session(creds) → boto3.Session (scoped to request, never stored)
_get_account_id(session) → str
_run_scan(session, scanners) → ScanResult
```

Each scanner is a class inheriting from `BaseScanner`:
```python
class BaseScanner:
    def scan(self, session: boto3.Session) -> list[Finding]: ...
```

Findings are sorted by `estimated_monthly_savings_usd` descending. Scanner errors (insufficient permissions, service not enabled) are collected in `errors[]` and do not abort the scan.

**Security:** Only the first 4 characters of the access key are logged. Credentials are never written to DynamoDB, S3, CloudWatch, or returned in any response body.

---

## Files Created

### New — Scanner Module (`backend/src/recoup/scanners/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker + public re-exports |
| `base.py` | `BaseScanner` ABC + `ScanResult` dataclass |
| `finding.py` | `Finding` Pydantic model (service, type, resource_id, severity, savings) |
| `ec2_scanner.py` | Idle EC2 instances (CPU < 5% over 7 days via CloudWatch) |
| `ebs_scanner.py` | Unattached EBS volumes |
| `eip_scanner.py` | Unused Elastic IPs |
| `rds_scanner.py` | Idle RDS instances (CPU < 5% over 7 days) |
| `s3_scanner.py` | Oversized S3 buckets with no lifecycle policy |
| `lambda_scanner.py` | Never-invoked Lambda functions (last 30 days) |
| `lb_scanner.py` | Load balancers with zero healthy targets |
| `cwlogs_scanner.py` | CloudWatch Log Groups with no retention policy |
| `cost_explorer_scanner.py` | Right-sizing recommendations from Cost Explorer |

### New — API Route

| File | Purpose |
|------|---------|
| `backend/src/recoup/api/routes/scan.py` | `/api/scan/full` + `/api/scan/preview` handlers |

### New — Frontend Page

| File | Purpose |
|------|---------|
| `frontend/src/app/scan/page.tsx` | Credential form, scan buttons, per-service finding cards |

---

## Files Modified

### Backend

| File | Change |
|------|--------|
| `config.py` | Removed `recoup_simulation_mode`, `recoup_enable_live_aws`; added `live_aws_enabled` computed property |
| `graph/types.py` | Removed `simulation_mode` field from `GraphState` |
| `models/opportunity.py` | Removed `simulation_mode` field from `RecoveryOpportunity` |
| `approval/store.py` | Removed `simulation_mode` parameter from all 5 functions |
| `approval/flow.py` | Removed `simulation_mode` from `HITLFlow.__init__` and all methods |
| `safety/cedar.py` | Removed `simulation_mode` from `PolicyContext`; removed simulation-based DENY shortcuts |
| `adapters/ec2_demo.py` | Removed `simulation_mode` parameter; added `_is_stub_instance()` check |
| `adapters/replay.py` | Removed `simulation_mode=True` from `GraphState` constructor |
| `hooks/tracing.py` | Removed `simulation_mode` from `AgentTraceHook` |
| `tools/ec2_tools.py` | Removed `simulation_mode` references; stub now triggered by allowlist absence |
| `graph/nodes.py` | Removed `simulation_mode` from `EvidenceCollector`/`EvidenceSanitizer` instantiations |
| `api/routes/opportunities.py` | Removed `simulation_mode` from `RunRequest`, `OpportunityResponse`, internal logic |
| `api/routes/approvals.py` | Removed `simulation_mode` from all approval store calls |
| `api/routes/replay.py` | Removed `simulation_mode` from `ReplayResponse` |
| `api/routes/ec2_demo.py` | Removed `simulation_mode` from `TriggerRequest`; removed from `trigger()` call |
| `api/routes/quality.py` | Removed `simulation_mode=True` from `EvidenceCollector` instantiation |
| `api/main.py` | Removed `simulation_mode`/`live_aws_enabled` from `/api/config`; added `scan_router` |
| `_live_flag.py` | Updated to use `settings.live_aws_enabled` |
| `notifications.py` | Updated to use `settings.live_aws_enabled` |
| `sqs_poller.py` | Updated to use `settings.live_aws_enabled` |
| `evidence/collector.py` | Updated stale docstring |
| `evidence/sanitizer.py` | Updated stale docstring |
| `tests/tool_contracts/test_tool_contracts.py` | Replaced `settings.recoup_enable_live_aws` with `settings.live_aws_enabled` |
| `tests/unit/test_ec2_demo.py` | Removed `recoup_enable_live_aws` from `_FakeSettings` stub |

### Frontend

| File | Change |
|------|--------|
| `components/ui/badge.tsx` | Removed `SimulationBadge`, `ModeBadge`; added `MockedBadge` |
| `lib/api.ts` | Removed `simulation_mode` from all interfaces; added `Finding`, `ScanRequest`, `ScanResult`, `api.scan` |
| `app/page.tsx` | Removed `ModeBadge`; replaced `SimulationBadge` with `MockedBadge` |
| `app/replay/page.tsx` | Removed `ModeBadge` |
| `app/approvals/page.tsx` | Removed `SimulationBadge`; removed "no AWS action in simulation mode" note |
| `app/opportunities/[id]/page.tsx` | Removed `ModeBadge` |
| `components/layout/sidebar.tsx` | Added Account Scanner nav entry (`/scan`) |

### Docs & Config

| File | Change |
|------|--------|
| `.env.example` | Removed `RECOUP_SIMULATION_MODE`, `NEXT_PUBLIC_SIMULATION_MODE` |
| `STATUS.md` | Added Phase 6d section; updated file tree; updated critical path |
| `LIVE_SCENARIOS_TODO.md` | Added Account Scanner + simulation mode removal as completed |
| `FRONTEND_GUIDE.md` | Added `/scan` to navigation table; updated live mode setup |
| `LIVE_TESTING_GUIDE.md` | Removed simulation flag references; added Test 6 — Account Scanner |
| `docs/architecture-overview.md` | Updated safety properties table; updated SUBMIT node description; added Account Scanner section |

---

## Definition of Done

| Check | Criteria | Status |
|-------|----------|--------|
| `simulation_mode` removed | Zero matches for `simulation_mode` in `backend/src/` | ✅ |
| `recoup_simulation_mode` removed | Zero matches across all `.py` and `.ts` source files | ✅ |
| `RECOUP_ENABLE_LIVE_AWS` removed | Not present in `.env.example` or any source comment | ✅ |
| Approval store | `save_approval` / `get_approval` / `list_pending` work without `simulation_mode` arg | ✅ |
| Cedar policy | `PolicyContext` has no `simulation_mode` field; submit_support_case rule unchanged | ✅ |
| EC2 demo stub | `i-demo0000000000000` triggers deterministic stub; real instance ID hits AWS | ✅ |
| Scanner module | 9 scanners importable; `ScanResult` serialises to JSON | ✅ |
| `/api/scan/preview` | Returns findings + errors + duration in < 10s for empty account | ✅ |
| `/scan` frontend page | Credential form renders; preview scan calls API; findings display with severity | ✅ |
| `MockedBadge` | Renders in CloudTrail / tagging / cost panels | ✅ |
| No `SimulationBadge` | Zero matches in `frontend/src/` | ✅ |
| Tests | Existing suite unaffected; tool contract tests use `settings.live_aws_enabled` | ✅ |
| ruff / mypy | 0 errors on all modified files | ✅ |

---

## Documentation Debt (Post-Phase 6d)

**Status: ✅ All resolved — Sep 3, 2026**

### `docs/api-reference.md` — 7 issues ✅

- [x] Remove `"simulation_mode": true` from `GET /api/opportunities` + `GET /api/opportunities/{id}` response examples
- [x] Remove `simulation_mode` field from `POST /api/opportunities/{id}/run` request body schema + JSON example
- [x] Remove `simulation_mode` from the run response example
- [x] Update `GET /api/config` response — remove `simulation_mode` + `live_aws_enabled` from JSON example and field table
- [x] Remove `simulation_mode` parameter row from `POST /api/ec2-demo/trigger` request table
- [x] Replace `RECOUP_ENABLE_LIVE_AWS=true` references in cloudtrail-demo, cost-demo, tagging-demo sections
- [x] **Add missing Account Scanner section** — `POST /api/scan/preview` + `POST /api/scan/full` with full schema

### `docs/architecture-overview.md` — 5 issues ✅

- [x] Update version header: "Phases 0–6c complete" → "Phases 0–6d complete"
- [x] Add `/scan` to the frontend routes list in Repository Layout
- [x] Add `scan` to the FastAPI routes list in Repository Layout
- [x] Add `scanners/` module to backend tree in Repository Layout
- [x] Phase 6b scripts already present — verified

### `docs/README.md` — 4 issues ✅

- [x] Update header: "Phases complete: 0–6c" → "Phases complete: 0–6d"
- [x] Add Phase 6d, 6e, 6f rows to Implementation Status table
- [x] Update Key Numbers — Frontend routes: 5 → 6
- [x] Update Key Numbers — add `Scanners \| 9` row

### `LIVE_TESTING_GUIDE.md` — 3 issues ✅

- [x] Remove stale "Not yet available" bullets for SNS/SQS/EventBridge (all completed in Phase 6b)
- [x] Update Test 6 count: "362 tests" → "369 tests"
- [x] Rename existing "Test 6 — Account Scanner" → **Test 7** (was mislabelled)

### `FRONTEND_GUIDE.md` — 2 issues ✅

- [x] Remove all `RECOUP_ENABLE_LIVE_AWS=true` references (3 occurrences)
- [x] Add **Scenario 7 — Account Scanner** walkthrough section
