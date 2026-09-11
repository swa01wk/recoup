# Phase 8 — Frontend Redesign (Recovery Dashboard)

> **Historical implementation plan.** Targets below reflect mid-build intent. **Current product & metrics:** [docs/README.md](../docs/README.md) · [STATUS.md](../STATUS.md) · [docs/judge-demo.md](../docs/judge-demo.md).



**Timeline:** Sep 3–6, 2026 (before Sep 11 feature cutoff)  
**Status:** `[x] Complete` (superseded in part by opportunities-first IA, Sep 2026)  
**Depends on:** Phase 6e ✅ (IAM roles), Phase 6d ✅ (scanner), Phase 4 ✅ (supersedes)  
**Source documents:** `Recoup_AWS_Master_Hackathon_Plan.docx` §§ 17–22; backend audit Sep 3, 2026

---

## As-built (Sep 11, 2026)

Shipped: Recovery Ledger (`/recovery`), scan promote bridge, pipeline on opportunity detail, competitive tagline (Phase 9). **Later simplification:** `/` → **`/opportunities`** hub; sidebar = Opportunities · Account Scanner · Recovery Ledger only; HITL on **`/opportunities/[id]`**; `/approvals` and `/quality` **redirect**; **Viewer/Operator sidebar switch removed** (always operator-capable). Quality: **`GET /api/quality/scorecard`** (6 gates). See [docs/frontend-guide.md](../docs/frontend-guide.md).

---

## Why This Phase Exists

Phase 4 delivered the initial "SLA Recovery Command Center" UI. After the backend audit on Sep 3, 2026 two problems emerged:

1. **The UI does not match the product story.** The hackathon winning strategy (§15–17 of `Recoup_AWS_Master_Hackathon_Plan.docx`) requires Recoup to be positioned as a *closed-loop autonomous recovery agent*, not a FinOps dashboard. The Recovery Ledger (`Detected → Approved → Recovered → Pending`) is the core differentiator and does not exist anywhere in the current UI.

2. **The two data pipelines are visually disconnected.** The real AWS scanner (`/scan`) returns `Finding[]` objects that never enter the agent pipeline. The opportunity graph runs on fixture data. A judge sees two unrelated pages. The redesign bridges this with a `POST /api/scan/findings/promote` endpoint and a unified Recovery Dashboard.

3. **Judges get operator controls.** Section 22 of the hackathon plan explicitly requires "a read-only default experience for judges." The current UI has no role system; anyone can approve/decline.

---

## Goals

- [ ] Recovery Ledger banner on the dashboard: `Detected $X/mo → Approved $X/mo → Recovered $X/mo → Pending $X/mo`
- [ ] Role system: `Operator` (full access) and `Viewer` (read-only, for judges) with localStorage persistence
- [ ] Operator/Viewer switcher pill in sidebar — one click to switch demo mode
- [ ] 7-step pipeline visualization on dashboard: `Detect → Investigate → Policy → Approve → Execute → Verify → Ledger`
- [ ] 8 scenario tiles on dashboard with live status badges (detected / pending / recovered)
- [ ] `/recovery` page: full Recovery Ledger with per-finding timeline + recharts savings chart
- [ ] IAM Security Boundary card on `/scan`: `RecoupRuntimeRole → STS AssumeRole → RecoupReadOnlyRole → Demo Resources`
- [ ] "Start Recovery →" button on each finding card (operator only) → calls `POST /api/scan/findings/promote` → routes to `/opportunities/:id`
- [ ] All approve/decline buttons disabled in Viewer mode with "Read-only mode" tooltip
- [ ] `recharts` used (currently installed but unused) for savings-over-time chart on `/recovery`

---

## Backend Change

### `POST /api/scan/findings/promote`

**File:** `backend/src/recoup/api/routes/scan.py`

Minimal bridge (~30 lines) that accepts a `Finding` and creates an `Opportunity` record in the in-memory store (same shape as existing `_graph_states`). Returns the new `opportunity_id`.

```
Request body: Finding (from scan result)
Response:     { "opportunity_id": "opp-<uuid>", "status": "created" }
```

Field mapping:
- `finding.estimated_monthly_savings_usd` → `potential_credit`
- `finding.severity` → priority signal
- `finding.service` + `finding.resource_id` → incident signal identifier
- `finding.recommendation` → initial case note

---

## New Pages / Routes

| Route | Status | Description |
|-------|--------|-------------|
| `/` (redesigned) | replaces Command Center | Recovery Dashboard: ledger + pipeline + 8 tiles + unified table |
| `/recovery` (new) | new | Recovery Ledger: timeline + recharts savings chart |
| `/scan` (updated) | adds IAM viz + promote | IAM Security Boundary card + "Start Recovery" on finding cards |
| `/approvals` (updated) | role-gate | Viewer = read-only banner + disabled buttons |
| `/opportunities/[id]` (updated) | role-gate | Viewer = read-only inline actions |
| `/quality` | unchanged | No changes needed |

---

## Files Changed

### Backend (1 file)
- `backend/src/recoup/api/routes/scan.py` — add `POST /findings/promote` endpoint

### Frontend — modified
- `frontend/src/lib/api.ts` — add `scan.promote()`, `scan.listPromoted()`; update `Finding` type
- `frontend/src/app/layout.tsx` — wrap with `RoleProvider`
- `frontend/src/app/page.tsx` — full redesign: Recovery Dashboard
- `frontend/src/app/approvals/page.tsx` — role-gate approve/decline
- `frontend/src/app/opportunities/[id]/page.tsx` — role-gate inline actions
- `frontend/src/app/scan/page.tsx` — IAM viz + "Start Recovery" promote button per finding
- `frontend/src/components/layout/sidebar.tsx` — role switcher + rename nav + new Recovery Ledger link
- `frontend/src/components/ui/badge.tsx` — add `ViewerBadge`, `OperatorBadge`

### Frontend — new files
- `frontend/src/hooks/useRole.tsx` — `RoleProvider`, `useRole()`, localStorage persistence
- `frontend/src/components/ui/recovery-ledger.tsx` — hero metric banner component
- `frontend/src/app/recovery/page.tsx` — full Recovery Ledger page

---

## Implementation Order (for Composer 2.5)

1. **Backend bridge** — `scan.py`: `POST /findings/promote`
2. **`useRole.tsx`** — `RoleProvider` + `useRole()` hook; update `layout.tsx`
3. **`recovery-ledger.tsx`** + `ViewerBadge`/`OperatorBadge` in `badge.tsx`
4. **Sidebar** — role switcher pill + nav rename + new ledger link
5. **`/` Recovery Dashboard** — full page redesign
6. **`/recovery`** — Recovery Ledger page with recharts
7. **Role-gate** `approvals/page.tsx` + `opportunities/[id]/page.tsx`
8. **`/scan`** — IAM visualization + "Start Recovery" promote button
9. **`api.ts`** — `scan.promote()` + type updates

---

## Definition of Done

| Check | Criteria |
|-------|----------|
| Recovery Ledger | Banner renders on `/`; dollar amounts update from scan + opportunity data |
| Role system | Switcher in sidebar; Viewer disables all approve/decline buttons; persists on reload |
| Pipeline visualization | 7-step flow on dashboard; active step highlights correctly |
| 8 scenario tiles | All 8 shown with live status badge; clicking navigates to scan/opportunity |
| Promote endpoint | `POST /findings/promote` returns `opportunity_id`; finding navigates to `/opportunities/:id` |
| IAM viz | Security Boundary card on `/scan` shows role chain; External ID explained |
| `/recovery` page | recharts chart renders; timeline shows all opportunities in pipeline stages |
| Role-gated pages | Viewer sees read-only banner; approve/decline disabled; no errors |
| CI | `npm run build` passes; no TypeScript errors |

---

## Risks

| Risk | Mitigation |
|------|-----------|
| In-memory opportunity store lost on restart | Acceptable for hackathon demo; document in README |
| Scan Findings have no `opportunity_id` until promoted | Keep findings in localStorage on scan page; clear on new scan |
| recharts SSR incompatibility with Next.js App Router | Use `dynamic(() => import(...), { ssr: false })` for chart component |
| Role system bypassed in incognito | By design — default to Viewer in fresh sessions |
