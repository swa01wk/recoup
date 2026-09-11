# Deployment Guide — Public Demo URL

Deploy Recoup as a public judge demo: **frontend on Vercel** + **backend on Railway or Fly.io**.

## Architecture

```
Browser → Vercel (Next.js) → Railway/Fly.io (FastAPI) → AWS (DynamoDB, S3, Bedrock, …)
```

The frontend reads `NEXT_PUBLIC_API_URL` at build time. The backend needs AWS credentials via IAM role (preferred) or environment variables.

---

## 1. Backend (Railway)

1. Create a new Railway project from this repo; set **Root Directory** to `backend`.
2. Railway auto-detects `backend/Dockerfile`.
3. Add environment variables from `.env.example` (fill real ARNs, bucket names, table names).
4. Assign a public domain (e.g. `recoup-api.up.railway.app`).
5. Verify: `curl https://<backend-url>/health` → `{"status":"ok"}`

### Fly.io alternative

```bash
cd backend
fly launch --name recoup-api --region iad
fly secrets import < ../.env
fly deploy
```

---

## 2. Frontend (Vercel)

1. Import the GitHub repo in [vercel.com](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Add build environment variable:
   - `NEXT_PUBLIC_API_URL=https://<your-backend-url>`
   - `NEXT_PUBLIC_RECOUP_READONLY_ROLE_ARN=arn:aws:iam::…:role/RecoupReadOnlyRole`
4. Deploy. Assign a custom domain (e.g. `recoup-demo.vercel.app`).
5. Update `README.md` demo URL with the live link.

---

## 3. CORS

The backend allows all origins (`allow_origins=["*"]`) for hackathon demo access. Restrict to your Vercel domain before production:

```python
# backend/src/recoup/api/main.py
allow_origins=["https://your-demo.vercel.app"]
```

---

## 4. Judge-Safe Demo Mode

Judges can use the app **without their own AWS credentials** (Docker/public backend):

- Canonical replay runs server-side with fixture data
- Quality scorecard: `GET /api/quality/scorecard` (no separate `/quality` page in current UI)
- Account Scanner live scan requires Role ARN (optional pre-fill via `NEXT_PUBLIC_RECOUP_READONLY_ROLE_ARN`)

Live EC2 stop and real Support submission require configured AWS resources and explicit approval on the opportunity detail page.

---

## 5. Local Docker Compose

```bash
cp .env.example .env   # fill in values
docker compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

Native uvicorn with `.env.example` uses port **8010** — set `NEXT_PUBLIC_API_URL=http://localhost:8010` when not using Docker.

---

## 6. Cost & Uptime

- Target demo spend: **< $50/month** (budget alerts at $25/$40/$50)
- Keep Railway/Fly backend running through **Oct 8, 2026** (Devpost requirement)
- Monitor with Railway metrics or an external uptime checker

---

## 7. Pre-Deploy Checklist

- [ ] `./scripts/verify_infra.sh` passes
- [ ] `pytest tests/ -q` → 420 collected, all pass (15 live skipped OK)
- [ ] `cd frontend && npm run build` → 0 errors
- [ ] Canonical replay returns a positive credit from public URL (from real billing_snapshot.json)
- [ ] Opportunity detail shows HITL approve with claim-bound amount
- [ ] README demo URL updated
