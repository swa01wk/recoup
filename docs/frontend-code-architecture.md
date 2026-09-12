# Recoup Frontend — Code & Architecture (J-FULL)

**Scope:** Code under `frontend/` only.  
**Operator journey reference:** [operator-journey.md](operator-journey.md) (steps 1–6).  
**Last updated:** Sep 13, 2026

---

## Purpose

The Next.js 16 app is the operator console for the **account-scanner lifecycle**: reset demo state → scan → pick findings → promote → HITL on opportunity detail → recovery ledger. It talks to the FastAPI backend via `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

**Production:** https://nvqjc7nnif.us-east-1.awsapprunner.com (image built with API URL baked in — see [archive/ops/production-hosting.md](archive/ops/production-hosting.md)).

---

## Stack & layout

| Layer | Location | Notes |
|-------|----------|--------|
| App Router | `frontend/src/app/` | Four primary routes + root redirect |
| Shared UI | `frontend/src/components/ui/` | shadcn-style primitives |
| Recoup domain UI | `frontend/src/components/recoup/` | HITL, evidence, lifecycle |
| API client | `frontend/src/lib/api.ts` | Typed fetch wrapper |
| Domain rules | `recoup-ui-rules.ts`, `recovery-storage.ts`, `service-presentation.ts`, `recovery-types.ts`, `recovery-presentation.ts`, `recovery-ledger-math.ts` | Pipeline labels, ledger buckets, assessment → UI copy |
| Data hook | `frontend/src/hooks/useRecoveryData.ts` | Single source of truth for opportunities + ledger |
| E2E | `frontend/e2e/` | J-FULL and related Playwright specs |

**Shell:** `frontend/src/components/providers.tsx` wraps every page with `RoleProvider` + fixed `Sidebar`. Root layout: `frontend/src/app/layout.tsx`.

**Navigation (sidebar):** `frontend/src/components/layout/sidebar.tsx`

- `/opportunities` — Opportunities  
- `/scan` — Account Scanner  
- `/recovery` — Recovery Ledger  
- **↺ Reset Demo Data** → `POST /api/admin/reset?clear_scan_cache=true` + `clearLocalScanData()`

**Removed from product UI (redirects only):** `frontend/next.config.ts` permanently redirects `/approvals` and `/quality` → `/opportunities`. HITL lives on `/opportunities/[id]`.

**Root:** `frontend/src/app/page.tsx` → `permanentRedirect("/opportunities")`.

---

## Architecture diagram (J-FULL data flow)

```text
┌─────────────────────────────────────────────────────────────────┐
│ Sidebar (reset, nav)                                             │
└────────────┬────────────────────────────────────────────────────┘
             │
   ┌─────────┼─────────┬─────────────────┐
   ▼         ▼         ▼                 ▼
 /scan   /opportunities  /opportunities/[id]   /recovery
   │         │                 │                  │
   │    localStorage      HITL + optional SSE      │
   │    + useRecoveryData     │                  │
   └─────────┴─────────────────┴──────────────────┘
                         │
                    api.ts (HTTP)
                         │
                   FastAPI backend
```

---

## Routes mapped to operator journey

### Step 1 — Reset

| Surface | Code |
|---------|------|
| UI reset | `sidebar.tsx` → `api.scan.adminReset(true)` |
| Tests | `frontend/e2e/helpers.ts` → `POST /api/test/reset` (no scan cache clear) |

### Step 2 — Account scan

| Surface | Code |
|---------|------|
| Page | `frontend/src/app/scan/page.tsx` |
| Consent | `frontend/src/components/recoup/security-access-summary.tsx` |
| Demo scan | `api.scan.demo()` → `saveLastScan()` → `recoup:scanComplete` event → `router.push("/opportunities")` |
| Persistence | `frontend/src/lib/recovery-storage.ts` — keys `recoup:lastScanResult`, `recoup:lastScanFindingCount`, `recoup:scanHistory` |

Backend mirror for refresh: `GET /api/scan/last` (used by hooks/tests; UI primarily uses localStorage after scan).

### Step 3 — Three distinct services

| Surface | Code |
|---------|------|
| Table + filters | `frontend/src/app/opportunities/page.tsx` — `buildOpportunityRows`, service filter dropdown |
| Row actions | `frontend/src/components/recoup/opportunity-row.tsx` |

Selection is client-side; E2E uses `pickFindingsByDistinctServices` in `helpers.ts`.

### Step 4 — Start Recovery (promote)

| Surface | Code |
|---------|------|
| Handler | `opportunities/page.tsx` → `handleStartRecovery` → `api.scan.promote(finding)` → `/opportunities/${id}` |
| Detail | `frontend/src/app/opportunities/[id]/page.tsx` — trace (`recovery_assessment`), evidence graph, recommendation/plan, safety-aware approve dialog |

### Step 5 — Human triage

| Path | Code |
|------|------|
| Approve (+ redirect ledger) | `[id]/page.tsx` → confirm dialog + `SafetyChecklist` → `handleApprove` — `claim_hash`, `amount`, `state_version` |
| Investigate | `handleInvestigate` → `api.approvals.investigate` |
| Decline | `handleDecline` → `api.approvals.decline` |
| HITL card | `frontend/src/components/recoup/decision-card.tsx` |
| Role | `frontend/src/hooks/useRole.tsx` — hardcoded **operator** (`principal: operator@recoup`); Viewer removed |

### Step 6 — Recovery ledger

| Surface | Code |
|---------|------|
| Summary banner | `opportunities/page.tsx` — `<RecoveryLedger variant="summary" />` |
| Full page | `frontend/src/app/recovery/page.tsx` |
| Bucket math | `frontend/src/components/ui/recovery-ledger.tsx` — `computeLedgerData` |
| Canonical buckets | `recovery-storage.ts` — `toCanonicalLifecycle` / `OPPORTUNITY_LEDGER_PENDING_STATES` (in-flight + HITL → PENDING; post-approve → RECOVERED; terminal negatives → Remaining). `recovery-data-events.ts` refreshes ledger after HITL actions. |

---

## Pipeline & lifecycle UI

Two parallel vocabularies (both in codebase):

| Concept | Source | J-FULL usage |
|---------|--------|----------------|
| **11-step strip** | `PIPELINE_STEPS` + `pipelineStageForOpportunity()` in `recovery-storage.ts`; labels in `recoup-ui-rules.ts` | Detail page `LifecycleStepper` — after promote, state `AWAITING_APPROVAL` → stage **8 (Approve)** |
| **6-step cost recovery** | `COST_RECOVERY_STAGES` in `recovery-storage.ts` | Coarser narrative on detail/analysis sections |

Badge colors and lifecycle labels: `LIFECYCLE_BADGE_VARIANT`, `formatLifecycleLabel` in `recoup-ui-rules.ts`.

Service-specific copy: `service-presentation.ts`. **Recovery assessment UI:** `finding-narrative.tsx`, `summary-metric-cards.tsx`, `confidence-indicator.tsx`, `evidence-graph-column.tsx`, `evidence-graph-summary.tsx`, `recommendation-panel.tsx`, `recovery-plan-collapsible.tsx`, `recommendation-updated-banner.tsx`, `safety-checklist.tsx`, plus `evidence-source-chips.tsx`, `technical-details.tsx`.

---

## `useRecoveryData` — central merge logic

`frontend/src/hooks/useRecoveryData.ts`:

- Polls (default 10s): `GET /api/opportunities`, `/api/approvals/pending`, `/api/scan/findings/promoted`, `/api/approvals/outcomes`
- Loads scan findings from `loadLastScan()` / scan history from localStorage
- Builds `ledgerData` via `computeLedgerData(scanTotal, opportunities, pendingAmount)`
- Exposes `snsStatusMap` from outcomes (`sns_sent`, `sns_sent_at`)

**Design intent:** Dashboard (`/opportunities`) and ledger (`/recovery`) share the same merged dataset to avoid bucket drift.

---

## API surface used by UI (`api.ts`)

J-FULL critical paths:

| Journey step | Client method |
|--------------|---------------|
| Reset (UI) | `api.scan.adminReset(clearScanCache)` |
| Scan | `api.scan.demo()`, `full`, `preview` |
| Promote | `api.scan.promote(finding)` |
| HITL | `api.approvals.forOpportunity`, `approve`, `investigate`, `decline` |
| Ledger | `api.opportunities.list`, `api.approvals.listOutcomes`, `api.scan.listPromoted` |
| Detail trace | `api.opportunities.trace`, `get` (trace includes `recovery_assessment`, `workflow`) |

Types: `Finding`, `ScanResult`, `ApprovalRecord`, `Opportunity`, `PromoteResponse`, `TraceResult` — `api.ts`; assessment shapes in `recovery-types.ts`.

---

## J-FULL-aligned E2E coverage

| Spec | Role |
|------|------|
| `e2e/journey-full-discovery-triage-ledger.spec.ts` | Authoritative steps 1–6 in one session |
| `e2e/journey-operator-primary.spec.ts` | Scan → promote → approve (single finding) |
| `e2e/journey-decision-inbox.spec.ts` | Approve / investigate / decline |
| `e2e/journey-recovery-ledger.spec.ts` | Ledger after approve |
| `e2e/journey-ui-browser.spec.ts` | Scan UI, Start Recovery, approve click |
| `e2e/scan.spec.ts` | Demo scan + promote |
| `e2e/helpers.ts` | `resetBackend`, ledger helpers, distinct-service picker |

Playwright webServer sets `RECOUP_SNS_DRY_RUN=1` (see `playwright.config.ts`).

---

## Additional frontend code (aligns with journey themes, not required for J-FULL walkthrough)

These exist in the repo and support depth, security, or ops — flag for judges/engineering, not the primary demo click path.

| Area | Code | Relation to journey |
|------|------|------------------------|
| **Optional agent re-run / SSE** | `[id]/page.tsx` — `startStream()`, `EventSource` on `api.opportunities.streamUrl`; maps SSE nodes → pipeline stages via `nodeToPipelineStage` | Same HITL contract after graph; **not** invoked on promote in J-FULL |
| **Re-run investigation** | `canRerunInvestigation` in `service-presentation.ts` | Optional depth on detail |
| **Cross-account connect UI** | `api.scan.initConnection` in `api.ts` | STS ExternalId flow for full/preview scan (step 2 variant) |
| **Scan history panel** | `opportunities/page.tsx` — `ScanHistoryPanel` | Audit/history UX beyond single demo scan |
| **Quality scorecard** | No dedicated page (redirect); tests in `e2e/journey-quality-gates.spec.ts`, `quality-dashboard.spec.ts` | Backend `GET /api/quality/scorecard` — agent depth gates |
| **Security journeys** | `e2e/journey-security.spec.ts` — 409 on wrong amount/claim_hash; uses `/run` to seed opportunities | Validates HITL binding from operator-journey step 5a |
| **Scan idempotency** | `e2e/journey-scan-idempotency.spec.ts` | Promote idempotency / content_hash behavior |
| **Dashboard/ledger consistency** | `e2e/journey-dashboard-ledger-consistency.spec.ts` | Same totals across surfaces (`useRecoveryData` contract) |
| **Workflow stage specs** | `e2e/workflow-stages.spec.ts` | 11-step pipeline vs states (uses `/run` + stream helpers) |
| **Competitive/demo copy fallbacks** | `frontend/src/lib/competitive-ui.ts` — `fallbackApprovalContext` | Detail page when approval metadata sparse |
| **Recovery verified hero** | `recovery-verified-hero.tsx` | Post-approve / RECOVERED UX on detail |
| **Savings chart** | `frontend/src/components/recovery/savings-chart.tsx` | Ledger visualization |

---

## Configuration

| Variable | Effect |
|----------|--------|
| `NEXT_PUBLIC_API_URL` | Backend base URL for `api.ts` |
| Build | `output: "standalone"` in `next.config.ts` for container deploy |

Backend feature flags for UI panels: `GET /api/config` (not wired to a dedicated settings page in current routes).

---

## File index (primary J-FULL)

```
frontend/src/app/
  page.tsx                    → redirect /opportunities
  scan/page.tsx               → step 2
  opportunities/page.tsx      → steps 3–4, ledger summary
  opportunities/[id]/page.tsx → steps 4–5
  recovery/page.tsx           → step 6
frontend/src/lib/
  api.ts                      → HTTP client
  recovery-storage.ts         → scan cache, pipeline stage mapping
  recoup-ui-rules.ts          → badges, PIPELINE_STEPS, fmtSavings
frontend/src/hooks/
  useRecoveryData.ts          → merged server + local state
  useRole.tsx                 → operator principal
frontend/src/components/
  layout/sidebar.tsx
  ui/recovery-ledger.tsx
  recoup/decision-card.tsx, opportunity-row.tsx, lifecycle-stepper.tsx
  recoup/evidence-graph-column.tsx, recommendation-panel.tsx, safety-checklist.tsx
frontend/src/lib/
  recovery-types.ts, recovery-presentation.ts, recovery-data-events.ts
```

---

## Related docs (not duplicated here)

Operator narrative: [operator-journey.md](operator-journey.md). Backend and agent layers: [backend-code-architecture.md](backend-code-architecture.md), [agent-code-architecture.md](agent-code-architecture.md). System-wide view: [recoup-overall-architecture.md](recoup-overall-architecture.md).
