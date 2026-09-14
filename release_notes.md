# Recoup — Release notes

Maintained changelog for shipped behavior, ops flags, and test baselines.  
**Canonical test counts:** [docs/README.md](docs/README.md#key-numbers-canonical--update-here-first).

---

## Sep 14, 2026 (hackathon repo cleanup)

- Removed third-party competitive case-study docx; moved build plans + STATUS to `docs/archive/internal/`.
- Judge-facing README/Devpost copy no longer names ProsperOps or other case-study products.
- Untracked Playwright report/test-result artifacts; `.gitignore` updated.
- Doc pass: fixed stale paths (`plans/` → `internal/plans/`), deployment links → App Runner, test counts **416/125**, video-script + meta index updated.

---

## Sep 13, 2026 (Phase 7 — submission prep)

- **E2E:** Playwright helpers reuse one `X-Demo-Session` per test (`resetBackend` → browser bind → API calls); J-FULL @smoke green on isolated ports.
- **Backend:** Offline demo scan includes a third finding (RDS) for three-service J-FULL; HITL approve writes outcome before SNS so `sns_sent` persists; in-memory outcome merge preserves SNS flags.
- **Ops:** [`scripts/prod_journey_hitl_smoke.sh`](../scripts/prod_journey_hitl_smoke.sh) — production approve / investigate / decline smoke.
- **Docs:** Devpost paste-ready copy, video checklist, builder.aws drafts under `docs/archive/submit/`.

---

## Sep 13, 2026 (production — `feat/agent_enhancements`)

**Live URLs:** UI https://pdkeexzwxr.us-east-1.awsapprunner.com · API https://qawwrm7kzy.us-east-1.awsapprunner.com

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

### Extended investigation SSE fix

- **Bug:** `GET …/stream` returned **401** in production after **Investigate Further** — `EventSource` cannot send `X-Demo-Session`.
- **Fix:** Middleware accepts **`?demo_session=<uuid>`** on stream requests; UI `api.opportunities.streamUrl()` appends the param.
- **Test:** `test_sse_stream_accepts_demo_session_query_param_in_production` in `tests/unit/test_demo_session.py`.

**Production verification**

```bash
curl -sf -X POST https://qawwrm7kzy.us-east-1.awsapprunner.com/api/demo/session | jq .
./scripts/smoke_production_api.sh https://qawwrm7kzy.us-east-1.awsapprunner.com
./scripts/prod_journey_hitl_smoke.sh
```

Browser: https://pdkeexzwxr.us-east-1.awsapprunner.com/scan → Demo Scan → three HITL paths (approve / investigate + **Run Extended Investigation** / decline).

**Tests**

- Backend: `tests/unit/test_demo_session.py`, `tests/unit/test_demo_control.py`; extended `test_admin_reset_gate.py`.
- Playwright: `e2e/journey-demo-session-concurrency.spec.ts` (PSC-1, PSC-3 `@smoke`).
- Baselines: **416** pytest collected · **125** Playwright tests in **16** spec files.

**Docs synced:** production URLs, SSE session query param, runbook §2/§3, `api-reference.md`, `operator-journey.md`, `production-hosting.md`, judge/operator guides, `stale-documents.md`.

---

## Prior releases (summary)

| Date | Theme |
|------|--------|
| Sep 2026 | J-FULL cleanup — removed `/replay` HTTP, governance demo routes; 3-link sidebar; App Runner Plane A hosting |
| Sep 2026 | Phase 6f — 8 demo workload scenarios, one-click demo scan, scanner evidence fields |
| Sep 2026 | Phase 6e — STS AssumeRole, RecoupReadOnlyRole / RemediationRole |

Older detail: [docs/archive/submit/submission-record.md](docs/archive/submit/submission-record.md), git history.
