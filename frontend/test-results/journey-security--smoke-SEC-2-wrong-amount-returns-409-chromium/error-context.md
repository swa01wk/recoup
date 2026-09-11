# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-security.spec.ts >> @smoke SEC-2 wrong amount returns 409
- Location: e2e/journey-security.spec.ts:92:5

# Error details

```
Error: expect(received).toBeTruthy()

Received: false
```

# Test source

```ts
  1   | /**
  2   |  * Security Journey Tests (Sprint 5)
  3   |  *
  4   |  * Verifies all security hardening from Sprints 1–4:
  5   |  *   - Tampered claim_hash → 409 (Cedar binding holds)
  6   |  *   - Stale state_version → 409
  7   |  *   - Wrong amount → 409
  8   |  *   - Double-approve → 404 (no pending approval)
  9   |  *   - X-Request-ID on every response
  10  |  *   - CORS: X-Request-ID present for allowed origin
  11  |  *   - API key auth (when RECOUP_API_KEY is configured)
  12  |  *   - Scan audit records are masked (no raw account IDs)
  13  |  *   - Data deletion is graceful (no 500 on unknown account)
  14  |  *
  15  |  * Tags:
  16  |  *   @smoke  — claim_hash binding, X-Request-ID, double-approve
  17  |  *   @full   — CORS, API key, sanitization, data deletion
  18  |  */
  19  | import { test, expect } from "@playwright/test";
  20  | import { resetBackend } from "./helpers";
  21  | 
  22  | const BACKEND = "http://localhost:8000";
  23  | 
  24  | // ---------------------------------------------------------------------------
  25  | // Setup
  26  | // ---------------------------------------------------------------------------
  27  | 
  28  | test.beforeEach(async ({ request }) => {
  29  |   await resetBackend(request);
  30  | });
  31  | 
  32  | // ---------------------------------------------------------------------------
  33  | // Helpers
  34  | // ---------------------------------------------------------------------------
  35  | 
  36  | /**
  37  |  * Create a pending approval by running the SLA pipeline directly.
  38  |  * Does not require AWS scan credentials — uses the deterministic replay path
  39  |  * that always produces AWAITING_APPROVAL with a valid claim record.
  40  |  */
  41  | async function setupPending(
  42  |   request: import("@playwright/test").APIRequestContext
  43  | ): Promise<{
  44  |   opportunity_id: string;
  45  |   approval_id: string;
  46  |   claim_hash: string;
  47  |   amount: string;
  48  |   state_version: number;
  49  | }> {
  50  |   const oppId = `sec-pending-${Date.now()}`;
  51  |   const runRes = await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
  52  |     data: { use_strands: true },
  53  |   });
> 54  |   expect(runRes.ok()).toBeTruthy();
      |                       ^ Error: expect(received).toBeTruthy()
  55  | 
  56  |   const res = await request.get(
  57  |     `${BACKEND}/api/approvals/opportunity/${oppId}`
  58  |   );
  59  |   expect(res.ok()).toBeTruthy();
  60  |   const pending = (await res.json()) as {
  61  |     approval_id: string;
  62  |     claim_hash: string;
  63  |     amount: string;
  64  |     state_version: number;
  65  |   };
  66  |   return { opportunity_id: oppId, ...pending };
  67  | }
  68  | 
  69  | // ---------------------------------------------------------------------------
  70  | // Cedar binding — claim integrity
  71  | // ---------------------------------------------------------------------------
  72  | 
  73  | test("@smoke SEC-1 tampered claim_hash returns 409", async ({ request }) => {
  74  |   const { opportunity_id, amount, state_version } = await setupPending(request);
  75  | 
  76  |   const res = await request.post(
  77  |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  78  |     {
  79  |       data: {
  80  |         principal: "attacker",
  81  |         claim_hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  82  |         amount,
  83  |         state_version,
  84  |       },
  85  |     }
  86  |   );
  87  |   expect(res.status()).toBe(409);
  88  |   const body = (await res.json()) as { detail: string };
  89  |   expect(body.detail.toLowerCase()).toContain("claim_hash");
  90  | });
  91  | 
  92  | test("@smoke SEC-2 wrong amount returns 409", async ({ request }) => {
  93  |   const { opportunity_id, claim_hash, state_version } = await setupPending(request);
  94  | 
  95  |   const res = await request.post(
  96  |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  97  |     {
  98  |       data: {
  99  |         principal: "attacker",
  100 |         claim_hash,
  101 |         amount: "9999999.99",
  102 |         state_version,
  103 |       },
  104 |     }
  105 |   );
  106 |   expect(res.status()).toBe(409);
  107 | });
  108 | 
  109 | test("@smoke SEC-3 stale state_version returns 409", async ({ request }) => {
  110 |   const { opportunity_id, claim_hash, amount } = await setupPending(request);
  111 | 
  112 |   const res = await request.post(
  113 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  114 |     {
  115 |       data: {
  116 |         principal: "attacker",
  117 |         claim_hash,
  118 |         amount,
  119 |         state_version: 9999, // stale
  120 |       },
  121 |     }
  122 |   );
  123 |   expect(res.status()).toBe(409);
  124 | });
  125 | 
  126 | test("@smoke SEC-4 double-approve returns 404 (no pending record after first approve)", async ({
  127 |   request,
  128 | }) => {
  129 |   const { opportunity_id, claim_hash, amount, state_version } =
  130 |     await setupPending(request);
  131 | 
  132 |   // First approve — succeeds
  133 |   const first = await request.post(
  134 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  135 |     {
  136 |       data: { principal: "playwright-test", claim_hash, amount, state_version },
  137 |     }
  138 |   );
  139 |   expect(first.ok()).toBeTruthy();
  140 | 
  141 |   // Second approve — no pending record
  142 |   const second = await request.post(
  143 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  144 |     {
  145 |       data: {
  146 |         principal: "playwright-test",
  147 |         claim_hash: "sha256:anything",
  148 |         amount: "0.00",
  149 |         state_version: 1,
  150 |       },
  151 |     }
  152 |   );
  153 |   expect(second.status()).toBe(404);
  154 | });
```