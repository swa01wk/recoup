# App Runner deployment runbook (Plane A)

**Account:** 625962218034 · **Region:** us-east-1  
**Purpose:** Repeatable deploy, verify, and troubleshoot for `recoup-api` + `recoup-ui` on AWS App Runner.  
**Companion:** [production-hosting.md](./production-hosting.md) (short reference)

---

## 1. Architecture (what you are deploying)

| Piece | Stack | ECR repo | App Runner name | Notes |
|-------|--------|----------|-----------------|--------|
| FastAPI API | `RecoupAppStack` | `recoup-api` | `recoup-api` | Instance role: `RecoupAppRunnerRole` |
| Next.js UI | `RecoupUiStack` | `recoup-ui` | `recoup-ui` | No instance role; public read-only UI |

Both stacks use a **two-phase CDK deploy**:

1. **Phase 1** — ECR repository + IAM (ECR pull role) + auto-scaling config. Context flags **off** → no App Runner service yet.
2. **Build & push** — Docker image to ECR (`linux/amd64`, no provenance/SBOM attestation manifests).
3. **Phase 2** — CDK with `-c createAppRunnerService=true` or `-c createUiService=true` → creates/updates App Runner service.

**Account constraint:** Plan assumes at most **two** App Runner services (`recoup-api`, `recoup-ui`) in `us-east-1`. UI stack uses **512 CPU / 1024 MiB**; API uses **1024 CPU / 2048 MiB** to leave headroom.

---

## 2. URL coupling (root cause of most “it works in curl but not in browser” issues)

Two independent settings must stay aligned:

| Setting | Where set | Effect |
|---------|-----------|--------|
| `NEXT_PUBLIC_API_URL` | **UI Docker build** (`--build-arg`) | Baked into Next.js client + sidebar label. Browser calls this host. |
| `FRONTEND_URL` → `RECOUP_FRONTEND_URL` | **API App Runner env** (CDK `RecoupAppStack`) | FastAPI CORS: only this origin gets `Access-Control-Allow-Origin`. |
| `demo_session` query param | **UI** `EventSource` on `GET …/stream` | Browser SSE cannot send `X-Demo-Session`; API accepts `?demo_session=<uuid>` on stream only. |

**Symptoms when misaligned:**

- Sidebar shows old API host (e.g. deleted `hp32eyu3yr…`).
- Network tab: requests to dead host → **Failed to fetch**, **Provisional headers are shown**.
- CORS preflight returns **400** or missing `access-control-allow-origin` for the UI you are actually using.
- **Investigate Further** works but **Run Extended Investigation** fails with **401** on `…/stream` (missing session on SSE).

**Rule after any deploy that changes a public URL:**

1. Note new **API** URL from `RecoupAppStack` → `AppRunnerServiceUrl`.
2. Note new **UI** URL from `RecoupUiStack` → `UiAppRunnerServiceUrl` (App Runner assigns a new subdomain when the service is recreated).
3. Rebuild/redeploy UI with `NEXT_PUBLIC_API_URL=<api>`.
4. Redeploy API stack with `RECOUP_FRONTEND_URL=<ui>` (phase 2 CDK only is enough; no API image rebuild required for CORS-only).

---

## 3. Current production URLs (Sep 13, 2026 PM — update after redeploy)

| Service | URL |
|---------|-----|
| UI | https://pdkeexzwxr.us-east-1.awsapprunner.com |
| API | https://qawwrm7kzy.us-east-1.awsapprunner.com |

Always confirm live values:

```bash
aws cloudformation describe-stacks --stack-name RecoupAppStack --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='AppRunnerServiceUrl'].OutputValue" --output text

aws cloudformation describe-stacks --stack-name RecoupUiStack --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='UiAppRunnerServiceUrl'].OutputValue" --output text
```

---

## 4. Prerequisites

```bash
export CDK_DEFAULT_ACCOUNT=625962218034
export CDK_DEFAULT_REGION=us-east-1
export RECOUP_EXTERNAL_ID='recoup-demo-external-id'   # must match IAM trust
```

- AWS CLI authenticated to the account.
- Docker Desktop (or engine) for **linux/amd64** builds.
- `infra/cdk`: `npm ci` / `npm run build` as needed.
- Infra + IAM already deployed (`RecoupInfraStack`, `RecoupIamStack`) — see `./scripts/deploy.sh` if greenfield.

---

## 5. Standard deploy procedures

### 5.1 Deploy API (full)

From repo root:

```bash
export RECOUP_FRONTEND_URL='https://pdkeexzwxr.us-east-1.awsapprunner.com'   # current UI origin
./scripts/deploy_app_hosting.sh
```

Script flow:

1. `cdk deploy RecoupAppStack` (ECR only).
2. `docker build --platform linux/amd64 --provenance=false --sbom=false` from repo root (`Dockerfile`).
3. Push to `625962218034.dkr.ecr.us-east-1.amazonaws.com/recoup-api:latest`.
4. `cdk deploy RecoupAppStack -c createAppRunnerService=true`.

**CORS-only update** (UI URL changed, API code unchanged):

```bash
export RECOUP_FRONTEND_URL='https://<new-ui-host>.us-east-1.awsapprunner.com'
cd infra/cdk && npm run build
npx cdk deploy RecoupAppStack --exclusively -c createAppRunnerService=true --require-approval never
```

### 5.2 Deploy UI (full)

```bash
# Optional explicit API; otherwise script reads RecoupAppStack output
export NEXT_PUBLIC_API_URL='https://qawwrm7kzy.us-east-1.awsapprunner.com'
./scripts/deploy_ui_hosting.sh
```

Script flow:

1. Resolve API URL (env or CloudFormation).
2. `cdk deploy RecoupUiStack` (ECR only).
3. Build `frontend/` with `NEXT_PUBLIC_API_URL` build-arg (`node:20-bookworm-slim`, standalone output).
4. Push to `recoup-ui:latest`.
5. **Phase 2:**
   - If `recoup-ui` **already exists** → `aws apprunner start-deployment` (rolling update, no CFN recreate).
   - Else → `cdk deploy RecoupUiStack -c createUiService=true` with **up to 3 attempts**, 90s between failures.

Then **always** sync API CORS (section 5.1 CORS-only) if the UI URL is new.

### 5.3 Recommended order (greenfield or full refresh)

1. Deploy **API** (with best-guess `RECOUP_FRONTEND_URL`; update again after UI if URL unknown).
2. Deploy **UI** with `NEXT_PUBLIC_API_URL` from step 1 output.
3. **Redeploy API** with `RECOUP_FRONTEND_URL` = UI output from step 2.

---

## 6. Post-deploy verification

### 6.1 API health

```bash
API=https://qawwrm7kzy.us-east-1.awsapprunner.com
curl -sf "$API/health" | grep '"status":"ok"'
./scripts/smoke_production_api.sh "$API"
```

### 6.2 CORS (replace hosts with current UI/API)

```bash
curl -sI -X OPTIONS "$API/api/scan/demo" \
  -H "Origin: https://pdkeexzwxr.us-east-1.awsapprunner.com" \
  -H "Access-Control-Request-Method: POST" \
  | grep access-control-allow-origin
```

Expected:

```http
access-control-allow-origin: https://pdkeexzwxr.us-east-1.awsapprunner.com
```

### 6.3 UI

```bash
UI=https://pdkeexzwxr.us-east-1.awsapprunner.com
curl -sf "$UI/api/health"    # Next route for App Runner HTTP health
curl -sf -o /dev/null -w "%{http_code}\n" "$UI/scan"
```

Browser: hard refresh (Cmd+Shift+R). Sidebar backend host must match **live API**, not a deleted App Runner URL.

### 6.4 Operator journey (manual)

| Step | Path |
|------|------|
| Demo scan | `{UI}/scan` |
| Opportunities | `{UI}/opportunities` |
| Detail / HITL | `{UI}/opportunities/{id}` |
| Ledger | `{UI}/recovery` |

---

## 7. Troubleshooting

### 7.1 CloudFormation: `NotStabilized` / “Your service failed to create”

**Typical CloudFormation message:**

```text
AWS::AppRunner::Service … HandlerErrorCode: NotStabilized
Your service failed to create. Review the application logs …
```

**What we observed:**

- ECR pull **succeeds**.
- ~15–20s later: `[AppRunner] Failed to deploy your application image` **without** reaching “Provisioning instances” (no application log group).
- Same image often **runs locally**: `docker run --platform linux/amd64 …`.
- **Intermittent:** API and UI sometimes succeed on retry after a prior **DELETE** of the same service name.

**Actions:**

1. Read **service** logs (not application) for the failed deployment id:

   ```bash
   aws logs describe-log-groups --log-group-name-prefix "/aws/apprunner/recoup-api/" --region us-east-1 \
     --query 'sort_by(logGroups,&creationTime)[-1].logGroupName' --output text
   # Use the printed path — do NOT paste literal "<that-log-group>"
   aws logs tail "/aws/apprunner/recoup-api/<service-id>/service" --region us-east-1 --since 3h --format short
   ```

2. If **application** log group exists, tail it for uvicorn/node stack traces.

3. **Retry** phase 2 (UI script retries automatically; API: re-run `cdk deploy … createAppRunnerService=true`).

4. Wait **30–90 minutes** after deleting a service before recreating the same `serviceName` if failures repeat.

5. Confirm image **amd64** single manifest:

   ```bash
   docker build --platform linux/amd64 --provenance=false --sbom=false …
   ```

**UI-specific fixes applied in repo (Sep 2026 incident):**

- `frontend/Dockerfile`: **bookworm-slim** instead of Alpine for Next standalone on App Runner.
- `GET /api/health` for HTTP health checks.
- CDK: HTTP health on `/api/health`, observability enabled, 512/1024 instance size.

**API-specific CDK notes:**

- TCP health on port **8080**; `PORT=8080` in container env.
- See comments in `infra/cdk/lib/stacks/recoup-app-stack.ts`.

### 7.2 Stack `UPDATE_ROLLBACK_COMPLETE`

Failed App Runner **create** rolls back and **deletes** the in-progress service resource. ECR repos and images remain.

- Check resources: `aws cloudformation describe-stack-resources --stack-name RecoupUiStack --region us-east-1`
- Re-run phase 2 only after fixing image/config or retrying.

### 7.3 UI works but all API calls fail

| Check | Fix |
|-------|-----|
| Sidebar API host | Rebuild UI with correct `NEXT_PUBLIC_API_URL` |
| CORS preflight | Set `RECOUP_FRONTEND_URL` to exact UI origin (scheme + host, no trailing slash) |
| Deleted API URL | Redeploy API; update UI build arg |

### 7.4 “Backend connected” but scan fails

The sidebar label is **configuration**, not a live probe. Trust Network tab and CORS curl (section 6.2).

### 7.5 App Runner service limit

Only **one** of each name. `list-services`:

```bash
aws apprunner list-services --region us-east-1 --output table
```

Do **not** run phase 2 “create” if the service already exists and is managed outside CFN — use `start-deployment` (UI script does this when `recoup-ui` exists).

### 7.6 Local workaround (UI down, API up)

```bash
cd frontend
NEXT_PUBLIC_API_URL='https://qawwrm7kzy.us-east-1.awsapprunner.com' npm run dev -- --port 3000
```

Open http://localhost:3000/scan — ensure API CORS allows `http://localhost:3000` (production API allows localhost in code for staging; confirm `main.py` CORS if needed).

---

## 8. Incident timeline (Sep 2026) — lessons learned

Summary of what happened and what fixed it:

1. **API recreate** — New App Runner URL `vxndciwupy…`; old `hp32eyu3yr…` **DELETED**.
2. **UI still built against old API** — Browser called dead host; Demo Scan / opportunities failed.
3. **UI redeploy attempts** — Several `CREATE_FAILED` / fast “Failed to deploy application image”; stack rollbacks removed running UI.
4. **Resolution**
   - UI: bookworm-slim image, `/api/health`, CDK HTTP health + smaller instance, retry loop on create.
   - Successful UI URL: `nvqjc7nnif…`.
   - UI image built with `NEXT_PUBLIC_API_URL=https://vxndciwupy…`.
   - API `RECOUP_FRONTEND_URL` updated to `https://nvqjc7nnif…` → CORS preflight confirmed.
5. **Deploy script hardening**
   - `deploy_ui_hosting.sh`: resolve API URL from `RecoupAppStack`; existing service → `start-deployment`; create retries.
   - Removed default stale API URL (`hp32eyu3yr…`).
6. **Sep 13 PM — guest sessions + investigate SSE** — `recoup-demo-control` DynamoDB + `?demo_session=` on `GET …/stream` (EventSource cannot send headers). **Current** Plane A URLs: §3 (`pdkeexzwxr` UI, `qawwrm7kzy` API).

---

## 9. Quick reference commands

```bash
# Status
aws apprunner list-services --region us-east-1
aws cloudformation describe-stacks --stack-name RecoupAppStack --region us-east-1 --query 'Stacks[0].StackStatus'
aws cloudformation describe-stacks --stack-name RecoupUiStack --region us-east-1 --query 'Stacks[0].StackStatus'

# API FRONTEND_URL on running service
aws apprunner describe-service --service-arn "$(aws apprunner list-services --region us-east-1 \
  --query \"ServiceSummaryList[?ServiceName=='recoup-api'].ServiceArn|[0]\" --output text)" \
  --region us-east-1 \
  --query 'Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables.FRONTEND_URL'

# Roll UI to latest ECR without CFN
aws apprunner start-deployment --service-arn "<recoup-ui-arn>" --region us-east-1
```

---

## 10. Files to know

| File | Role |
|------|------|
| `scripts/deploy_app_hosting.sh` | API ECR + image + App Runner phase 2 |
| `scripts/deploy_ui_hosting.sh` | UI ECR + image + create or roll deploy |
| `Dockerfile` (repo root) | Production API image |
| `frontend/Dockerfile` | Production UI image |
| `infra/cdk/lib/stacks/recoup-app-stack.ts` | API App Runner, env vars, TCP :8080 |
| `infra/cdk/lib/stacks/recoup-ui-stack.ts` | UI App Runner, HTTP `/api/health`, :3000 |
| `frontend/src/app/api/health/route.ts` | UI health endpoint |
| `scripts/smoke_production_api.sh` | Post-deploy API smoke |

---

## 11. When URLs change — checklist

- [ ] Record new API URL from `RecoupAppStack` output  
- [ ] Record new UI URL from `RecoupUiStack` or `describe-service`  
- [ ] Rebuild UI with `NEXT_PUBLIC_API_URL=<api>`  
- [ ] Deploy UI (script or `start-deployment`)  
- [ ] `cdk deploy RecoupAppStack -c createAppRunnerService=true` with `RECOUP_FRONTEND_URL=<ui>`  
- [ ] CORS curl (section 6.2)  
- [ ] Browser hard refresh; verify sidebar API host  
- [ ] Demo scan on `{UI}/scan`  
- [ ] `curl -sf -X POST {API}/api/demo/session` returns 200 + `session_id` (guest sessions)  
- [ ] `DEMO_CONTROL_TABLE=recoup-demo-control` on API if infra stack deployed  
- [ ] Update this doc’s table in section 3 (and [production-hosting.md](./production-hosting.md))  
