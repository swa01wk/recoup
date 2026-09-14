# Deployment — superseded by AWS-all hosting

> **Canonical (Sep 2026):** [production-hosting.md](./production-hosting.md) — App Runner API + UI on AWS account **625962218034** (`us-east-1`).  
> The Vercel + Railway/Fly guide below is **historical** only.

---

## Live judge URLs

| Role | URL |
|------|-----|
| UI | https://pdkeexzwxr.us-east-1.awsapprunner.com |
| API | https://qawwrm7kzy.us-east-1.awsapprunner.com |

Scripts: `scripts/deploy_app_hosting.sh`, `scripts/deploy_ui_hosting.sh`, `scripts/smoke_production_api.sh`, `scripts/post_change_segregation_smoke.sh`.  
Optional Amplify (GitHub): `scripts/connect_amplify_github.sh`, `scripts/deploy_amplify_frontend.sh`.

---

## Historical — Vercel + Railway (pre–Sep 2026)

<details>
<summary>Old third-party hosting notes</summary>

Deploy Recoup as a public judge demo: **frontend on Vercel** + **backend on Railway or Fly.io**.

```
Browser → Vercel (Next.js) → Railway/Fly.io (FastAPI) → AWS (DynamoDB, S3, Bedrock, …)
```

See git history for full Railway/Vercel steps. CORS is now `FRONTEND_URL`-scoped in production (`backend/src/recoup/api/main.py`).

</details>
