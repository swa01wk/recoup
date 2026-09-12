# Recoup Frontend

Next.js app for the Recoup operator UI.

- **Project overview:** [../README.md](../README.md)
- **UI architecture:** [../docs/frontend-code-architecture.md](../docs/frontend-code-architecture.md)
- **Local dev & E2E:** [../docs/local-dev-and-testing.md](../docs/local-dev-and-testing.md)
- **Production hosting:** [../docs/archive/ops/production-hosting.md](../docs/archive/ops/production-hosting.md)

## Production

**UI:** https://nvqjc7nnif.us-east-1.awsapprunner.com  
**API (`NEXT_PUBLIC_API_URL` at build):** https://vxndciwupy.us-east-1.awsapprunner.com

Redeploy UI: `NEXT_PUBLIC_API_URL=... ./scripts/deploy_ui_hosting.sh` from repo root.  
Amplify (optional): `frontend/amplify.yml` + `scripts/deploy_amplify_frontend.sh`.

## Local

```bash
npm install
npm run dev          # http://localhost:3000
npx playwright test --grep @smoke
```

Set `NEXT_PUBLIC_API_URL` to match the backend (default **8000** with Docker; **8010** with native `.env.example`).
