# Recoup — User Journey Checklist

> **Last updated:** Sep 11, 2026  
> **Primary operator lifecycle (product):** **[J-FULL](docs/operator-journey.md)** — scan → 3 distinct services → approve / investigate / decline → Recovery Ledger + SNS.  
> **Authoritative E2E:** `frontend/e2e/journey-full-discovery-triage-ledger.spec.ts`  
> **Test suite:** 28 Playwright specs · 279 tests (`cd frontend && npx playwright test --list`)  
> **UI:** Sidebar = Opportunities · Account Scanner · Recovery Ledger only. HITL on `/opportunities/[id]`. `/approvals` and `/quality` redirect to `/opportunities`.  
> **Not primary UI:** `/replay`, EC2 demo card, governance dashboard tiles (API/tests may still exist).  
> **Tags:** `@smoke` · `@full` · `@e2e` (J-FULL mega journey)

---

## J-FULL — Full operator journey (primary)

**Full doc:** [docs/operator-journey.md](docs/operator-journey.md)

| Step | Operator action |
|------|-----------------|
| 1 | Reset demo data |
| 2 | AWS Account Scanner → Demo Scan |
| 3 | Three findings, **three distinct services** |
| 4 | **Start Recovery** on each |
| 5 | **Approve** (SNS) · **Investigate Further** · **Decline** |
| 6 | **Recovery Ledger** |

**Playwright:** `cd frontend && npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts`

Overlaps: **J2** (single-finding loop), **J6** (HITL paths), **J9** (ledger). Distinct from **J4** (SLA replay) and **J5** (EC2 demo API).

---

## Quick-reference legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Playwright test exists & passing |
| 🧪 | Manual / UI walkthrough only (no automated test) |
| ❌ | Not yet tested |
| 🔒 | Security/adversarial test |
| 🚀 | Live AWS (real cloud call) |

---

## Journey Map

```
Detect → Investigate → Correlate → Explain → Prove → Plan → Policy → Approve → Remediate → Verify → Record
```

---

## J1 — App Bootstrap & Health

| # | Step | Test file | Tag | Status |
|---|------|-----------|-----|--------|
| J1-1 | Backend health (`GET /health`) | `journey-security.spec.ts` SEC-7 | `@full` | ✅ |
| J1-2 | Readiness check (`GET /health/ready`) | `journey-security.spec.ts` SEC-8 | `@full` | ✅ |
| J1-3 | Config endpoint exposes no secrets | `journey-security.spec.ts` SEC-13 | `@full` | ✅ |
| J1-4 | State reset (`POST /api/test/reset`) | `helpers.ts resetBackend()` | — | ✅ |
| J1-5 | Frontend loads at `/` | `journey-ui-browser.spec.ts` UI-1 | `@ui @smoke` | ✅ |
| J1-6 | Sidebar shows **3** nav links (no SLA Replay) | `live-ec2-demo-removed.spec.ts` | `@smoke` | ✅ |

---

## J2 — Operator Loop (single finding; subset of J-FULL)

> **File:** `journey-operator-primary.spec.ts` · `scan.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| J2-1 | Demo scan returns ≥8 findings with total savings > $60 | scan J2-1, scan @smoke | `@smoke` | ✅ |
| J2-2 | `account_id` masked (XXXXXXXX or "unknown") | scan J2-1 | `@smoke` | ✅ |
| J2-3 | `GET /api/scan/last` returns cached results | scan.spec | — | ✅ |
| J2-4 | Promote finding → `AWAITING_APPROVAL` state | scan J2-2, scan @smoke | `@smoke` | ✅ |
| J2-5 | Promoted `opportunity_id` matches `recovery-` prefix | scan J2-2 | `@smoke` | ✅ |
| J2-6 | Promoted opportunity is `AWAITING_APPROVAL` and listed in `/api/approvals/pending` | scan J2-3 | `@smoke` | ✅ |
| J2-7 | Approve with full claim binding → `APPROVED` state | scan J2-4 | `@smoke` | ✅ |
| J2-8 | SNS notification flag (`sns_notification_sent=true`) | decision-inbox.spec | `@smoke` | ✅ |
| J2-9 | Pending list decrements after approve | decision-inbox.spec | — | ✅ |
| J2-10 | Scan audit record written (`GET /api/scan/audit`) | scan J2-5 | `@smoke` | ✅ |
| J2-11 | Promote is idempotent (same resource → same opportunity) | scan J2-6 | `@full` | ✅ |
| J2-12 | Each of 8 scenario_tags produces separate opportunity | scan.spec S6 | — | ✅ |
| J2-13 | All promoted IDs appear in `/api/approvals/pending` | scan.spec S6 | — | ✅ |

**8 Scenario Tags covered:**

| Tag | Resource | Est. Savings/mo |
|-----|----------|-----------------|
| `oversized-ec2` | Stopped EC2 t3.medium | $30.37 |
| `unattached-ebs` | Unattached 20 GiB gp2 | $2.00 |
| `gp2-migration` | gp2→gp3 50 GiB migration | $5.00 |
| `idle-eip` | Idle Elastic IP | $3.60 |
| `idle-rds` | Idle RDS db.t3.micro | $14.60 |
| `s3-no-lifecycle` | S3 no lifecycle policy | $2.30 |
| `oversized-lambda` | Lambda 1024 MB, 0 invocations | $3.75 |
| `stale-snapshot` | Stale EBS snapshot | $1.76 |

---

## J3 — Cross-Account Connect (ExternalId Onboarding)

> **File:** `journey-cross-account-connect.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| J3-1 | `POST /api/scan/connect/init` returns unique `customer_id` + `external_id` | J3, J2-8 | `@smoke` | ✅ |
| J3-2 | Two successive inits return different IDs (uniqueness) | journey-cross-account | `@smoke` | ✅ |
| J3-3 | `external_id` entropy ≥ 20 chars | journey-cross-account | `@smoke` | ✅ |
| J3-4 | `GET /api/scan/connect/{customer_id}` returns CF template hint | journey-cross-account | `@full` | ✅ |
| J3-5 | Unknown `customer_id` returns 404 | journey-cross-account | `@full` | ✅ |
| J3-6 | Demo scan works after connect init | journey-cross-account | `@full` | ✅ |
| J3-7 | `DenyAllWrites` principle present in CF hint | journey-cross-account | `@full` | ✅ |
| J3-8 | Data deletion (`DELETE /api/scan/accounts/{id}/data`) | J2-9, SEC-11, SEC-12 | `@full` | ✅ |

---

## J4 — SLA Verified Replay (optional — not primary UI)

> **File:** `journey-sla-replay-full.spec.ts` · `sla-replay.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| J4-1 | `POST /api/replay/api-gateway-sla` creates opportunity | sla-replay @smoke, journey-sla J4 | `@smoke` | ✅ |
| J4-2 | Policy decision is `REQUIRE_APPROVAL` or `ALLOW` (Cedar) | sla-replay @smoke | `@smoke` | ✅ |
| J4-3 | `potential_credit` is numeric and > $0 | journey-sla | `@smoke` | ✅ |
| J4-4 | Credit amount is < $20 (not cost savings scale) | sla-replay approve-button | `@smoke` | ✅ |
| J4-5 | Trace returns `availability_result.monthly_uptime_pct` | sla-replay detail | — | ✅ |
| J4-6 | Uptime % is in valid range (0–100) | sla-replay detail | — | ✅ |
| J4-7 | 100% uptime scenario is NOT eligible for credit | journey-sla | `@full` | ✅ |
| J4-8 | Replay scorecard / quality gate passes | journey-sla | `@full` | ✅ |
| J4-9 | Idempotent replay (re-running same period) | journey-sla | `@full` | ✅ |
| J4-10 | Wrong amount on approve returns 409 | journey-sla | `@full` | ✅ |
| J4-11 | SSE stream endpoint (`GET /api/opportunities/{id}/stream`) responds | sla-replay SSE | — | ✅ |
| J4-12 | `GET /api/replay/scenarios` returns scenario list | journey-sla | `@smoke` | ✅ |
| J4-13 | Approve SLA credit → `APPROVED` state | journey-sla | `@smoke` | ✅ |
| J4-14 | SLA replay UI page (`/replay`) renders | `journey-ui-browser.spec.ts` UI-7 | `@ui @smoke` | ✅ |

---

## J5 — EC2 Idle Stop (Live AWS Action)

> **File:** `journey-ec2-stop.spec.ts` · `ec2-stop.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| J5-1 | `POST /api/ec2-demo/trigger` creates HITL opportunity | ec2-stop @smoke, journey-ec2 J5 | `@smoke` | ✅ |
| J5-2 | Triggered approval has `action=stop_demo_instance` | ec2-stop @smoke | `@smoke` | ✅ |
| J5-3 | EC2 opportunity detail visible (`GET /api/ec2-demo/opportunity/{id}`) | journey-ec2 | `@smoke` | ✅ |
| J5-4 | Opportunity list (`GET /api/ec2-demo/opportunities`) returns entry | journey-ec2 | `@smoke` | ✅ |
| J5-5 | Opportunity is `AWAITING_APPROVAL` before approve | journey-ec2 | `@smoke` | ✅ |
| J5-6 | Approve → `APPROVED` + `sns_notification_sent=true` | ec2-stop approve | `@smoke` | ✅ |
| J5-7 | Execute without prior approval returns 409/403 | journey-ec2 | `@full` | ✅ |
| J5-8 | Execute mocked — response has `verified_stopped=true` | ec2-stop mock | — | ✅ |
| J5-9 | Unknown opportunity ID returns 404 | journey-ec2 | `@full` | ✅ |
| J5-10 | Trigger is repeatable (fresh state after reset) | journey-ec2 | `@full` | ✅ |
| J5-11 | Live `StopInstances` (real AWS) | 🚀 Live only | — | 🚀 |

---

## J6 — HITL approval (Approve / Decline / Investigate)

> **UI:** `/opportunities/[id]` · **API:** `/api/approvals/opportunity/{id}/…`  
> **Files:** `journey-decision-inbox.spec.ts` · `decision-inbox.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| J6-1 | Approve path → `APPROVED` | decision-inbox @smoke | `@smoke` | ✅ |
| J6-2 | Investigate path → `NEEDS_FOLLOWUP` | decision-inbox @smoke | `@smoke` | ✅ |
| J6-3 | Decline path → `DECLINED` | decision-inbox decline | — | ✅ |
| J6-4 | `claim_hash` binds approve to exact claim | journey-decision J6, SEC-1 | `@smoke` | ✅ |
| J6-5 | `X-Request-ID` UUID on every response | SEC-5, SEC-6 | `@smoke` | ✅ |
| J6-6 | Double-approve returns 404 (no pending record) | SEC-4 | `@smoke` | ✅ |
| J6-7 | Pending list decrements after any terminal action | decision-inbox bucket invariant | — | ✅ |
| J6-8 | `/api/approvals/pending` lists all queued items | multiple specs | — | ✅ |
| J6-9 | Declined opportunities excluded from Recovery Ledger | journey-recovery | `@full` | ✅ |
| J6-10 | UI opportunity detail renders Approve / Decline / Investigate | `journey-opportunity-detail.spec.ts`, `opportunity-detail.spec.ts` | `@ui` | ✅ |

---

## J7 — Opportunity Detail & SSE Agent Trace

> **File:** `journey-opportunity-detail.spec.ts` · `opportunity-detail.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| J7-1 | `GET /api/opportunities/{id}` returns full record | opp-detail @smoke | `@smoke` | ✅ |
| J7-2 | `state_version ≥ 1` on opportunity | opp-detail @smoke | `@smoke` | ✅ |
| J7-3 | `potential_value > 0` on cost recovery opp | opp-detail @smoke | `@smoke` | ✅ |
| J7-4 | `GET /api/opportunities/{id}/trace` returns node data | journey-opp detail+SSE | `@smoke` | ✅ |
| J7-5 | SSE stream (`GET /api/opportunities/{id}/stream`) responds | sla-replay SSE, journey-opp | — | ✅ |
| J7-6 | Approve via opp-level endpoint → `APPROVED` | journey-opp | `@smoke` | ✅ |
| J7-7 | Decline via opp-level endpoint → `DECLINED` | journey-opp | `@smoke` | ✅ |
| J7-8 | Investigate via opp-level endpoint → `NEEDS_FOLLOWUP` | journey-opp | `@smoke` | ✅ |
| J7-9 | 404 for unknown opportunity ID | journey-opp | `@full` | ✅ |
| J7-10 | `POST /api/opportunities/{id}/run` triggers agent | journey-opp | `@full` | ✅ |
| J7-11 | Opportunities list mixes states (APPROVED + AWAITING) | journey-opp | `@full` | ✅ |
| J7-12 | UI `/opportunities/[id]` page renders pipeline strip | `journey-ui-browser.spec.ts` UI-8 | `@ui @smoke` | ✅ |

---

## J8 — Quality Gates & Ship Scorecard

> **File:** `journey-quality-gates.spec.ts` · `quality-dashboard.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| J8-1 | `GET /api/quality/scorecard` returns gate array | quality @smoke | `@smoke` | ✅ |
| J8-2 | `all_gates_pass` field is boolean | quality all_gates_pass | — | ✅ |
| J8-3 | `unsafe_external_actions = 0` gate passes | journey-quality, S4 | `@smoke` | ✅ |
| J8-4 | `hallucinated_evidence = 0` gate passes | S4 evidence sanitizer | `@smoke` | ✅ |
| J8-5 | All rate fields (precision, recall, etc.) in range [0,1] | journey-quality | `@full` | ✅ |
| J8-6 | SLA replay `p95_credit_accuracy_pct` gate | journey-quality | `@full` | ✅ |
| J8-7 | Timestamps on scorecard are ISO-8601 | journey-quality | `@full` | ✅ |
| J8-8 | `X-Request-ID` on scorecard response | journey-quality | `@full` | ✅ |
| J8-9 | S4 evidence sanitizer: no PII in replay trace | quality-dashboard S4 | `@smoke` | ✅ |
| J8-10 | S4 unit: auth tokens / API keys pattern redacted | quality-dashboard S4 unit | — | ✅ |
| J8-11 | UI `/quality` page renders scorecard tiles | `journey-ui-browser.spec.ts` UI-9 | `@ui @smoke` | ✅ |

---

## J9 — Recovery Ledger (State Buckets)

> **File:** `journey-recovery-ledger.spec.ts` · `recovery-ledger.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| J9-1 | After scan: Detected bucket total > $60 | ledger @smoke | `@smoke` | ✅ |
| J9-2 | After promote: Pending bucket shows opportunity value | ledger pending bucket | — | ✅ |
| J9-3 | After approve: APPROVED state in opportunities list | ledger approved bucket | — | ✅ |
| J9-4 | Pending decrements, Approved increments | ledger buckets invariant | — | ✅ |
| J9-5 | Bucket invariant: scan total ≥ sum of opp values | ledger bucket invariant | — | ✅ |
| J9-6 | Credit from SLA replay matches approved amount | journey-recovery | `@full` | ✅ |
| J9-7 | DECLINED opportunities NOT counted in ledger | journey-recovery | `@full` | ✅ |
| J9-8 | APPROVED via ledger endpoint reflects correctly | journey-recovery | `@smoke` | ✅ |
| J9-9 | UI `/recovery` page renders savings chart | `journey-ui-browser.spec.ts` UI-6 | `@ui @smoke` | ✅ |

---

## J10 — CloudTrail No-Actor Detection (Governance S7)

> **File:** `journey-governance.spec.ts` · `governance.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| J10-1 | `GET /api/cloudtrail-demo/check` returns 200 | governance @smoke S7 | `@smoke` | ✅ |
| J10-2 | `actor_attributed` field is boolean | governance S7 | `@smoke` | ✅ |
| J10-3 | `requires_human_review` field is boolean | governance S7 | `@smoke` | ✅ |
| J10-4 | `finding` text is non-empty | governance S7 | `@smoke` | ✅ |
| J10-5 | Live mode: `actor_attributed=false`, `human_events=0` | governance S7 live | 🚀 Live | 🚀 |
| J10-6 | Event breakdown array and `actor_type_breakdown` map | governance S7 breakdown | — | ✅ |
| J10-7 | Response includes `X-Request-ID` header | journey-governance | `@full` | ✅ |

---

## J11 — Missing Cost-Allocation Tags (Governance S8)

> **File:** `journey-governance.spec.ts` · `governance.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| J11-1 | `GET /api/tagging-demo/scan` returns 200 | governance @smoke S8 | `@smoke` | ✅ |
| J11-2 | `resources_scanned` is a number | governance S8 | `@smoke` | ✅ |
| J11-3 | `resources_missing_tags` is a number | governance S8 | `@smoke` | ✅ |
| J11-4 | `findings` is an array | governance S8 | `@smoke` | ✅ |
| J11-5 | `required_tags` includes governance tag (cost/env/team) | governance S8 tags | — | ✅ |
| J11-6 | Live mode: ≥5 resources missing tags, ARNs valid | governance S8 live | 🚀 Live | 🚀 |
| J11-7 | `estimated_attribution_gap_usd_monthly > 0` in live mode | governance S8 live | 🚀 Live | 🚀 |

---

## J12 — Cost Explorer Account Spend (Governance S9)

> **File:** `journey-governance.spec.ts` · `governance.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| J12-1 | `GET /api/cost-demo/summary` returns 200 | governance @smoke S9 | `@smoke` | ✅ |
| J12-2 | `total_usd` is a number | governance S9 | `@smoke` | ✅ |
| J12-3 | `billing_period_start` / `_end` are valid dates | governance S9 | `@smoke` | ✅ |
| J12-4 | `breakdown` array items have `service` + `cost_usd` | governance S9 | `@smoke` | ✅ |
| J12-5 | `fetched_at` is present | governance S9 | `@smoke` | ✅ |
| J12-6 | Billing period start ≤ end | governance S9 | — | ✅ |
| J12-7 | `total_usd` can be 0 or negative (credits OK) | governance S9 invariant | — | ✅ |

---

## SEC — Security & Adversarial Tests

> **File:** `journey-security.spec.ts`

| # | Step | Test ID | Tag | Status |
|---|------|---------|-----|--------|
| SEC-1 | Tampered `claim_hash` → 409 | SEC-1, J2-7 | `@smoke` | 🔒✅ |
| SEC-2 | Wrong `amount` → 409 | SEC-2 | `@smoke` | 🔒✅ |
| SEC-3 | Stale `state_version` → 409 | SEC-3 | `@smoke` | 🔒✅ |
| SEC-4 | Double-approve → 404 | SEC-4 | `@smoke` | 🔒✅ |
| SEC-5 | `X-Request-ID` present on scan response | SEC-5 | `@smoke` | 🔒✅ |
| SEC-6 | `X-Request-ID` present on 409 rejection | SEC-6 | `@smoke` | 🔒✅ |
| SEC-7 | Health endpoint public (no auth) | SEC-7 | `@full` | 🔒✅ |
| SEC-8 | Ready endpoint public (no auth) | SEC-8 | `@full` | 🔒✅ |
| SEC-9 | Audit records mask account_id (XXXXXXXX) | SEC-9 | `@full` | 🔒✅ |
| SEC-10 | Scan response masks account_id | SEC-10 | `@full` | 🔒✅ |
| SEC-11 | Delete unknown account → graceful 200/404 | SEC-11 | `@full` | 🔒✅ |
| SEC-12 | Delete demo account purges scan data | SEC-12 | `@full` | 🔒✅ |
| SEC-13 | `/api/config` exposes no secrets/keys | SEC-13 | `@full` | 🔒✅ |

---

## UI Smoke Walk (Browser — Automated)

> **Current product IA:** `/opportunities`, `/scan`, `/recovery`, `/opportunities/[id]`, `/replay` (deep link).  
> Prefer **`live-ec2-demo-removed.spec.ts`**, **`journey-opportunity-detail.spec.ts`**, and journey specs for current UI.  
> `journey-ui-browser.spec.ts` still targets legacy `/approvals`, `/quality`, and Viewer role — may conflict with redirects; treat as cleanup candidate.

| # | Page / Action | Spec | Tag | Status |
|---|---------------|------|-----|--------|
| UI-1 | `/opportunities` hub loads | `live-ec2-demo-removed`, journey specs | `@smoke` | ✅ |
| UI-2 | `/scan` — demo scan finding tiles | `scan.spec.ts`, journeys | `@ui` | ✅ |
| UI-3 | "Start Recovery" promotes finding | journey-operator-primary | `@smoke` | ✅ |
| UI-4 | HITL on `/opportunities/[id]` (not `/approvals` redirect) | opportunity-detail, decision-inbox API | `@smoke` | ✅ |
| UI-5 | Claim-bound approve | journey-decision-inbox | `@smoke` | ✅ |
| UI-6 | `/recovery` ledger buckets | recovery-ledger | `@smoke` | ✅ |
| UI-7 | `/replay` SLA replay | sla-replay, journey-sla-replay-full | `@smoke` | ✅ |
| UI-8 | Pipeline strip on opportunity detail | opportunity-detail | `@ui` | ✅ |
| UI-9 | Quality gates via API (`/api/quality/scorecard`) | journey-quality-gates | `@full` | ✅ |

---

## Test Counts Summary

| Spec file | Tests | Journeys |
|-----------|------:|---------|
| `scan.spec.ts` | 8 | J2 |
| `decision-inbox.spec.ts` | 4 | J6 |
| `sla-replay.spec.ts` | 4 | J4 |
| `ec2-stop.spec.ts` | 3 | J5 |
| `opportunity-detail.spec.ts` | 3 | J7 |
| `recovery-ledger.spec.ts` | 4 | J9 |
| `governance.spec.ts` | 6 | J10–J12 |
| `quality-dashboard.spec.ts` | 4 | J8 |
| `journey-operator-primary.spec.ts` | 9 | J2 |
| `journey-cross-account-connect.spec.ts` | 8 | J3 |
| `journey-sla-replay-full.spec.ts` | 10 | J4 |
| `journey-ec2-stop.spec.ts` | 9 | J5 |
| `journey-decision-inbox.spec.ts` | 10 | J6 |
| `journey-opportunity-detail.spec.ts` | 9 | J7 |
| `journey-quality-gates.spec.ts` | 8 | J8 |
| `journey-recovery-ledger.spec.ts` | 8 | J9 |
| `journey-governance.spec.ts` | 13 | J10–J12 |
| `journey-security.spec.ts` | 13 | SEC |
| `journey-ui-browser.spec.ts` | 18 | UI-1–UI-10 |
| `journey-bedrock-strands-e2e.spec.ts` | 11 | BS-1–BS-10 + BS-LIVE |
| `journey-sse-stream-nodes.spec.ts` | 10 | SSE-1–SSE-10 |
| `journey-strands-all-lifecycles.spec.ts` | 64 | LC-J1–J12 + LC-SEC + LC-FULL |
| `journey-full-discovery-triage-ledger.spec.ts` | 4 | **J-FULL** (see below) |
| **Total** | run `npx playwright test --list` to refresh | **J1–J12 + SEC + UI + BS + SSE + LC + J-FULL** |

---

## How to run

```bash
# All tests (API + Browser UI + SSE + Bedrock)
cd frontend && npx playwright test

# Smoke tests only (fast, ~2 min)
npx playwright test --grep @smoke

# Full suite including edge cases
npx playwright test --grep @full

# UI browser click-through tests only
npx playwright test journey-ui-browser --grep @ui

# Bedrock/Strands E2E lifecycle (stub-safe, no real AWS needed)
npx playwright test journey-bedrock-strands-e2e

# SSE node-by-node stream assertions
npx playwright test journey-sse-stream-nodes

# All-journey Strands agent stream lifecycle suite (J1–J12 + SEC + FULL)
npx playwright test journey-strands-all-lifecycles

# Strands lifecycle smoke only (~60 s, no real AWS required)
npx playwright test journey-strands-all-lifecycles --grep @smoke

# Strands + SSE full lifecycle (@lifecycle tag)
npx playwright test --grep @lifecycle

# Live Bedrock tests (requires AWS credentials + staging env)
npx playwright test --grep @bedrock-live

# Specific journey
npx playwright test journey-operator-primary

# With interactive UI
npx playwright test --ui

# Report
npx playwright show-report
```

---

## Coverage gaps (remaining)

| Gap | Priority | Notes |
|-----|----------|-------|
| EC2 live `StopInstances` E2E | Low | Tested in AWS demo account manually (🚀 Live) |
| Savings chart pixel-accurate values | Low | Recharts SVG — needs screenshot comparison |
| AgentCore / Bedrock live invocation | Low | `@bedrock-live` tag gates it; runs in staging with real creds |

### ✅ Recently closed gaps (Sep 8 sprint)

| Gap | Closed by |
|-----|-----------|
| Browser click-through (Approve button in UI) | `journey-ui-browser.spec.ts` UI-5 |
| SLA replay full node-by-node SSE assertion | `journey-sse-stream-nodes.spec.ts` SSE-1–SSE-10 |
| Role switch gates Approve button correctly | `journey-ui-browser.spec.ts` UI-10, UI-10b |
| AgentCore / Bedrock Strands full E2E lifecycle | `journey-bedrock-strands-e2e.spec.ts` BS-1–BS-10 |
| `use_strands` param wired into `/api/opportunities/{id}/run` | `opportunities.py` RunRequest |

### ✅ Recently closed gaps (Sep 9 sprint)

| Gap | Closed by |
|-----|-----------|
| All-journey Strands+SSE combined lifecycle in a single spec | `journey-strands-all-lifecycles.spec.ts` LC-J1–J12 + LC-SEC + LC-FULL (64 tests) |
| Concurrent EC2 + SLA + operator loop Strands lifecycle | `LC-FULL-2` |
| Post-approval SSE stream (claim_package_generator + downstream) | `LC-FULL-3` / `SSE-12` |
| `collectSSEEvents` + `strandsRunAndStream` helpers shared across specs | `helpers.ts` |
