# Recoup — Frontend Guide

**Last updated:** Sep 11, 2026  
**Stack:** Next.js 16.x · React 19 · TypeScript · Tailwind 4  
**Dev:** `http://localhost:3000` · Backend default `http://localhost:8000` (8010 if using `.env.example` natively)  
**Operator flow:** [operator-journey.md](operator-journey.md) (J-FULL)

---

## Quick start

```bash
cd frontend && npm install && npm run dev
npx playwright test --grep @smoke
```

---

## Routes and navigation

**Sidebar** ([`sidebar.tsx`](../frontend/src/components/layout/sidebar.tsx)): only three links.

| Route | Behavior |
|-------|----------|
| `/` | Redirects to `/opportunities` |
| `/opportunities` | Primary hub — list, filters, inline recovery summary |
| `/opportunities/[id]` | Detail, pipeline strip, **HITL approve / decline / investigate** |
| `/scan` | Account Scanner — demo scan, promote findings |
| `/recovery` | Recovery Ledger — Remaining / Pending Approval / Recovered |
| `/replay` | **Removed** (404) — SLA replay engine is pytest/scorecard only (no public HTTP) |
| `/approvals` | Redirects to `/opportunities` |
| `/quality` | Redirects to `/opportunities` |

Scorecard data: `GET /api/quality/scorecard` (no dedicated quality page in current IA).

---

## Page notes

### `/opportunities`

List and triage. Promoted scan findings appear here as opportunities.

### `/opportunities/[id]`

- Pipeline strip (workflow stages)
- Trace / SSE: `GET /api/opportunities/{id}/trace`, `GET .../stream`
- Approval actions: `POST /api/approvals/opportunity/{id}/approve|decline|investigate` with `claim_hash`, `amount`, `state_version`

### `/scan`

```
POST /api/scan/demo
GET  /api/scan/last
POST /api/scan/findings/promote
POST /api/scan/connect/init
```

### `/recovery`

Ledger buckets and savings chart; data from opportunities + pending approvals + scan totals.

---

## Key files

| Path | Role |
|------|------|
| `src/lib/api.ts` | Typed API client |
| `src/components/layout/sidebar.tsx` | Nav + demo reset |
| `src/components/recovery/recovery-ledger.tsx` | Ledger buckets |
| `src/app/opportunities/[id]/page.tsx` | Detail + HITL |

---

## Environment

| Variable | Default | Notes |
|----------|---------|-------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Match backend port (8010 for native `.env`) |
| `PLAYWRIGHT_BACKEND_PORT` | `8000` | Set `8010` when backend uses `.env.example` port |

---

## API cheat sheet

```bash
curl http://localhost:8000/health/ready
curl -s -X POST http://localhost:8000/api/scan/demo | jq '.findings | length'
curl -s http://localhost:8000/api/approvals/pending | jq .
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
curl -s -X POST http://localhost:8000/api/test/reset   # non-production only
```

Deploy: [production-hosting.md](../ops/production-hosting.md) (App Runner; historical [deployment.md](../ops/deployment.md))
