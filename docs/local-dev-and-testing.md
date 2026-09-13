# Recoup — Local Dev and Testing

**Last updated:** Sep 13, 2026

---

## Production (AWS)

Judges can run **J-FULL** without a local stack:

| | URL |
|--|-----|
| UI | https://nvqjc7nnif.us-east-1.awsapprunner.com |
| API | https://vxndciwupy.us-east-1.awsapprunner.com |

```bash
./scripts/smoke_production_api.sh https://vxndciwupy.us-east-1.awsapprunner.com
./scripts/post_change_segregation_smoke.sh
```

Deploy / CORS / SNS: [archive/ops/production-hosting.md](archive/ops/production-hosting.md).  
`POST /api/test/reset` returns **403** when `RECOUP_ENV=production`.  
Guest sessions: `POST /api/demo/session` + header **`X-Demo-Session`** on demo routes (UI sets this automatically).

Optional Playwright against prod (session API must be deployed):

```bash
cd frontend
PLAYWRIGHT_BACKEND_URL=https://vxndciwupy.us-east-1.awsapprunner.com \
PLAYWRIGHT_FRONTEND_URL=https://nvqjc7nnif.us-east-1.awsapprunner.com \
  npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts
```

---

## Ports

| Setup | Backend | Frontend env |
|-------|---------|----------------|
| **Docker Compose** | 8000 | `NEXT_PUBLIC_API_URL=http://localhost:8000` (default) |
| **Native + `.env.example`** | 8010 (`RECOUP_API_PORT`) | `NEXT_PUBLIC_API_URL=http://localhost:8010` |
| **Playwright** | Defaults to 8000; set `PLAYWRIGHT_BACKEND_PORT=8012` (or any free port) if 8000 is stale | — |

**Playwright note:** `PLAYWRIGHT_REUSE_SERVERS=1` reuses whatever is already listening. If that process is an **old** API build, `/api/demo/session` or offline scan fallback may be missing — prefer letting Playwright start a fresh backend, or restart uvicorn from current `main`.

---

## Start services

```bash
# Option A — Docker (recommended for judges)
docker compose up -d

# Option B — Native
cd backend && pip install -e ".[dev]"
uvicorn recoup.api.main:app --reload --port 8000   # or 8010 per .env

cd frontend && npm install && npm run dev
```

```bash
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/health/ready | jq .
```

---

## Playwright

| Command | Purpose |
|---------|---------|
| `cd frontend && npx playwright test` | Full suite |
| `npx playwright test --grep @smoke` | Smoke subset |
| `npx playwright test e2e/journey-demo-session-concurrency.spec.ts` | **PSC** — two isolated demo sessions (`@smoke`) |
| `npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts` | **Full operator user journey** (below) |

**Demo scan without AWS (local only):** When `RECOUP_ENV=local`, `POST /api/scan/demo` returns deterministic offline findings if STS AssumeRole fails or role env is unset — enough for PSC and most E2E without `recoup-admin` → `RecoupReadOnlyRole` trust.

**Primary operator journey (full doc):** [operator-journey.md](operator-journey.md)

Journey map: [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) · CI: [ci-guide.md](ci-guide.md)

---

## Backend tests

```bash
cd backend && pytest tests/ -W error::DeprecationWarning
# ~416 collected; live-mode skips as configured
pytest tests/unit/test_demo_session.py tests/unit/test_demo_control.py
pytest tests/unit/recovery/   # recovery pipeline unit tests
```

---

## Live AWS (optional)

Prerequisites: `aws sts get-caller-identity`, demo tags `RecoupScenario=*`.

Scenarios and curls: [demo-playbook.md](demo-playbook.md)

**Safety:** Use demo-tagged resources only; reset with `POST /api/test/reset` in non-production.

---

## Reset demo state

**Per-session (matches sidebar / Playwright helpers):**

```bash
SID=$(curl -s -X POST "http://localhost:8000/api/demo/session" | jq -r .session_id)
curl -s -X POST "http://localhost:8000/api/demo/session/reset?clear_scan_cache=true" \
  -H "X-Demo-Session: $SID"
```

**Legacy full default-session reset (Playwright fallback):**

```bash
curl -s -X POST "http://localhost:8000/api/test/reset"
curl -s -X POST "http://localhost:8000/api/admin/reset?clear_scan_cache=true" \
  -H "X-Demo-Session: $SID"
```

Session and test reset return **403** in production unless `RECOUP_ENABLE_ADMIN_RESET` is set for session reset.
