# Production hosting (Plane A) — App Runner

**Account:** 625962218034 · **Region:** us-east-1

**Judge access (hackathon):** Keep both App Runner services running and URLs stable through **Oct 8, 2026**. Avoid `cdk destroy` on demo stacks until after judging; monitor AWS billing alerts.

**Detailed deploy / troubleshoot:** [app-runner-deployment-runbook.md](./app-runner-deployment-runbook.md)

| Service | URL | CDK stack |
|---------|-----|-----------|
| API (FastAPI) | https://qawwrm7kzy.us-east-1.awsapprunner.com | `RecoupAppStack` |
| UI (Next.js) | https://pdkeexzwxr.us-east-1.awsapprunner.com | `RecoupUiStack` |

App Runner assigns a **new subdomain** when a service is recreated — always read stack outputs after deploy and sync **UI build arg** + **API CORS** (see runbook §2).

Amplify is optional when GitHub is connected (see below).

## Deploy API (App Runner)

```bash
export CDK_DEFAULT_ACCOUNT=625962218034
export CDK_DEFAULT_REGION=us-east-1
export RECOUP_EXTERNAL_ID='your-external-id'   # match .env
export RECOUP_FRONTEND_URL='https://pdkeexzwxr.us-east-1.awsapprunner.com'

./scripts/deploy_app_hosting.sh
```

CORS-only (no API image rebuild): runbook §5.1.

## Deploy UI

```bash
export NEXT_PUBLIC_API_URL='https://qawwrm7kzy.us-east-1.awsapprunner.com'
./scripts/deploy_ui_hosting.sh
```

Then set `RECOUP_FRONTEND_URL` to the **UiAppRunnerServiceUrl** output and redeploy API (CORS-only) if the UI URL changed.

### Amplify (preferred when GitHub is connected)

1. `./scripts/connect_amplify_github.sh` — complete pending CodeStar connection in console.
2. `export GITHUB_OAUTH_TOKEN=... NEXT_PUBLIC_API_URL=... && ./scripts/deploy_amplify_frontend.sh`
3. **Root directory:** `frontend` · build spec: [frontend/amplify.yml](../../../frontend/amplify.yml)
4. Set `RECOUP_FRONTEND_URL` to Amplify URL and update API CORS (runbook §5.1).

## SNS (J-FULL approve)

- Topic: `recoup-alerts` (`RECOUP_SNS_TOPIC_ARN` on App Runner).
- **Recommended:** SNS → **Email** subscription (confirm inbox).
- Optional: SNS → **SQS** queue for AWS-only audit copy.
- Production: `RECOUP_SNS_DRY_RUN` must **not** be `1`.
- Remove webhook.site HTTPS subscription when email is confirmed.

## Production gates

- `RECOUP_ENV=production` on App Runner (set in CDK).
- `POST /api/test/reset` returns **403** in production (Playwright uses session reset locally).
- **Guest demo sessions** — each browser gets `POST /api/demo/session` → `X-Demo-Session` on API calls (UI handles this). Deploy **API + UI** together when releasing session work.
- Sidebar **Reset Demo Data** → `POST /api/demo/session/reset?clear_scan_cache=true` (clears **that visitor only**). Requires `RECOUP_ENABLE_ADMIN_RESET=true` in production.
- Ops global wipe: `POST /api/admin/reset?scope=global` only when `RECOUP_ENABLE_GLOBAL_RESET=true` (not for normal judges).
- DynamoDB **`recoup-demo-control`** via env `DEMO_CONTROL_TABLE` (session records + global epoch). Table + IAM on `RecoupAppRunnerRole` must exist in production — deploy `RecoupInfraStack` + `RecoupIamStack` (see [runbook §4](./app-runner-deployment-runbook.md)); if infra stack update rolls back, create table + grant `dynamodb:*Item` on that table before guest sessions work.
- **Extended investigation SSE:** UI passes `?demo_session=` on `GET /api/opportunities/{id}/stream` (EventSource cannot send headers).

## Smoke (J-FULL)

1. Demo Scan on `{UI}/scan`
2. Three services → Start Recovery → Approve
3. Ledger on `{UI}/recovery`
4. Confirm SNS email or `sns_notification_sent` on approve response

```bash
./scripts/smoke_production_api.sh 'https://qawwrm7kzy.us-east-1.awsapprunner.com'
curl -sf -X POST 'https://qawwrm7kzy.us-east-1.awsapprunner.com/api/demo/session' | jq .
./scripts/prod_journey_hitl_smoke.sh   # approve + investigate + decline (API-only J-FULL §5)
```

Optional E2E (after session API is deployed):

```bash
PLAYWRIGHT_BACKEND_URL=https://qawwrm7kzy.us-east-1.awsapprunner.com \
  npx playwright test e2e/journey-demo-session-concurrency.spec.ts --grep @smoke
```

Optional J-FULL E2E:

```bash
PLAYWRIGHT_BACKEND_URL=https://qawwrm7kzy.us-east-1.awsapprunner.com \
PLAYWRIGHT_FRONTEND_URL=https://pdkeexzwxr.us-east-1.awsapprunner.com \
npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts
```
