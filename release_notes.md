# Recoup — Release notes

Maintained changelog for shipped behavior, ops flags, and test baselines.  
**Canonical test counts:** [docs/README.md](docs/README.md#key-numbers-canonical--update-here-first).

---

## Unreleased (on branch — deploy required for production)

### Opportunity detail UI (text-first layout)

- **`/opportunities/[id]`** — six KPI cards, clickable 11-step journey, two-column narrative (found / evidence / graph | action / safety / plan), HITL below main content with **`Approve $X/mo Recovery`** CTA, collapsed confidence / policy / raw evidence sections.
- **E2E** — `detailApproveButton()` in `frontend/e2e/helpers.ts` for dynamic approve label.

### Guest demo sessions (hybrid Plan A + B)

**Why:** Public judge URL with concurrent visitors — each browser gets an isolated scan → promote → approve → ledger path; reset no longer wipes other users’ data.

**API**

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/demo/session` | Issue `{ session_id, expires_at }` (no session header) |
| POST | `/api/demo/session/reset?clear_scan_cache=true` | Clears **caller’s session only** |
| POST | `/api/admin/reset?scope=session` | Same as session reset when admin gate allows (default scope) |
| POST | `/api/admin/reset?scope=global` | Ops wipe — requires `RECOUP_ENABLE_GLOBAL_RESET` |

**Client**

- UI stores `session_id` in `localStorage` and sends **`X-Demo-Session`** on API calls (`frontend/src/lib/api.ts`).
- Sidebar **↺ Reset Demo Data** → `POST /api/demo/session/reset` (confirm copy: *your demo only — other visitors unaffected*).

**Backend**

- In-memory scan/graph/promote caches partitioned by `session_id`.
- Approvals/outcomes tagged with `demo_session_id`; list/get filtered by session.
- **Session epoch** — long mutations (scan, promote, approve) return **409** `session_reset` if reset bumped epoch mid-flight; **409** `reset_in_progress` on concurrent session reset lock.
- **Global epoch** — middleware syncs multi-instance memory after ops global reset.
- **Local dev:** when `RECOUP_ENV=local`, `POST /api/scan/demo` falls back to deterministic offline findings if STS AssumeRole fails or role env is unset (Playwright / IAM-less laptops). **Production always requires real AssumeRole.**

**Infrastructure**

- DynamoDB table `recoup-demo-control` (global epoch + per-session records); env `DEMO_CONTROL_TABLE`.
- CDK: `RecoupInfraStack` table + IAM on `RecoupAppRunnerRole`; `RecoupAppStack` env var.

**Flags**

| Variable | Purpose |
|----------|---------|
| `RECOUP_ENABLE_ADMIN_RESET` | Allow sidebar / session reset in **production** |
| `RECOUP_ENABLE_GLOBAL_RESET` | Allow `POST /api/admin/reset?scope=global` |
| `DEMO_CONTROL_TABLE` | DynamoDB demo control (empty → in-memory fallback locally) |

**Tests**

- Backend: `tests/unit/test_demo_session.py`, `tests/unit/test_demo_control.py`; extended `test_admin_reset_gate.py`.
- Playwright: `e2e/journey-demo-session-concurrency.spec.ts` (PSC-1, PSC-3 `@smoke`).
- Baselines: **416** pytest collected · **125** Playwright tests in **16** spec files.

**Local PSC smoke**

```bash
cd frontend
PLAYWRIGHT_BACKEND_PORT=8012 npx playwright test e2e/journey-demo-session-concurrency.spec.ts
```

Use a **fresh** uvicorn (Playwright `webServer` or manual). Avoid `PLAYWRIGHT_REUSE_SERVERS=1` on ports still running an **older** API build.

**Production verification (after API + UI deploy)**

```bash
curl -sf -X POST https://vxndciwupy.us-east-1.awsapprunner.com/api/demo/session | jq .
./scripts/smoke_production_api.sh https://vxndciwupy.us-east-1.awsapprunner.com
```

Until deploy completes, production returns **404** on `/api/demo/session`.

**Docs updated:** `docs/archive/ops/production-hosting.md`, `docs/local-dev-and-testing.md`, `docs/api-reference.md`, `USER_JOURNEY_CHECKLIST.md`, `docs/demo-playbook.md`, `docs/operator-journey.md` (Step 1).

---

## Prior releases (summary)

| Date | Theme |
|------|--------|
| Sep 2026 | J-FULL cleanup — removed `/replay` HTTP, governance demo routes; 3-link sidebar; App Runner Plane A hosting |
| Sep 2026 | Phase 6f — 8 demo workload scenarios, one-click demo scan, scanner evidence fields |
| Sep 2026 | Phase 6e — STS AssumeRole, RecoupReadOnlyRole / RemediationRole |

Older detail: [docs/archive/submit/submission-record.md](docs/archive/submit/submission-record.md), git history.
