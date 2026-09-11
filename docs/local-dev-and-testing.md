# Recoup — Local Dev and Testing

**Last updated:** Sep 11, 2026

---

## Ports

| Setup | Backend | Frontend env |
|-------|---------|----------------|
| **Docker Compose** | 8000 | `NEXT_PUBLIC_API_URL=http://localhost:8000` (default) |
| **Native + `.env.example`** | 8010 (`RECOUP_API_PORT`) | `NEXT_PUBLIC_API_URL=http://localhost:8010` |
| **Playwright** | Defaults to 8000; set `PLAYWRIGHT_BACKEND_PORT=8010` if needed | — |

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
| `npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts` | **Full operator user journey** (below) |

**Primary operator journey (full doc):** [operator-journey.md](operator-journey.md)

Journey map: [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) · CI: [ci-guide.md](ci-guide.md)

---

## Backend tests

```bash
cd backend && pytest tests/ -W error::DeprecationWarning
# 420 collected; 15 skipped (live-mode)
```

---

## Live AWS (optional)

Prerequisites: `aws sts get-caller-identity`, demo tags `RecoupScenario=*`.

Scenarios and curls: [demo-playbook.md](demo-playbook.md)

**Safety:** Use demo-tagged resources only; reset with `POST /api/test/reset` in non-production.

---

## Reset demo state

```bash
curl -s -X POST "http://localhost:8000/api/test/reset"
curl -s -X POST "http://localhost:8000/api/admin/reset?clear_scan_cache=true"
```

Both return **403** when `RECOUP_ENV=production`.
