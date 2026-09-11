# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-operator-primary.spec.ts >> @smoke J2-5 scan audit record written after demo scan
- Location: e2e/journey-operator-primary.spec.ts:111:5

# Error details

```
Error: expect(received).toBeTruthy()

Received: false
```

# Test source

```ts
  14  | import {
  15  |   resetBackend,
  16  |   runDemoScan,
  17  |   promoteFinding,
  18  |   approveOpportunity,
  19  | } from "./helpers";
  20  | 
  21  | const BACKEND = "http://localhost:8000";
  22  | 
  23  | // ---------------------------------------------------------------------------
  24  | // Helpers
  25  | // ---------------------------------------------------------------------------
  26  | 
  27  | async function getOpportunityState(
  28  |   request: import("@playwright/test").APIRequestContext,
  29  |   opportunityId: string
  30  | ): Promise<string> {
  31  |   const res = await request.get(`${BACKEND}/api/opportunities/${opportunityId}`);
  32  |   expect(res.ok()).toBeTruthy();
  33  |   const body = (await res.json()) as { state: string };
  34  |   return body.state;
  35  | }
  36  | 
  37  | async function getPendingApprovals(
  38  |   request: import("@playwright/test").APIRequestContext
  39  | ): Promise<unknown[]> {
  40  |   const res = await request.get(`${BACKEND}/api/approvals/pending`);
  41  |   expect(res.ok()).toBeTruthy();
  42  |   return res.json();
  43  | }
  44  | 
  45  | // ---------------------------------------------------------------------------
  46  | // J2 — @smoke: happy path
  47  | // ---------------------------------------------------------------------------
  48  | 
  49  | test.beforeEach(async ({ request }) => {
  50  |   await resetBackend(request);
  51  | });
  52  | 
  53  | test("@smoke J2-1 demo scan returns findings with positive total savings", async ({ request }) => {
  54  |   const scan = await runDemoScan(request);
  55  |   expect(scan.findings.length).toBeGreaterThanOrEqual(1);
  56  |   expect(scan.total_estimated_monthly_savings_usd).toBeGreaterThan(0);
  57  |   // Sprint 2: account_id should be masked (XXXXXXXX present or null)
  58  |   const result = scan as unknown as { account_id: string | null };
  59  |   if (result.account_id) {
  60  |     const isDemo = result.account_id === "unknown";
  61  |     const isMasked = result.account_id.includes("XXXXXXXX");
  62  |     expect(isDemo || isMasked).toBeTruthy();
  63  |   }
  64  | });
  65  | 
  66  | test("@smoke J2-2 promote finding creates opportunity in AWAITING_APPROVAL", async ({
  67  |   request,
  68  | }) => {
  69  |   const scan = await runDemoScan(request);
  70  |   const findings = scan.findings as Array<Record<string, unknown>>;
  71  |   expect(findings.length).toBeGreaterThan(0);
  72  | 
  73  |   const { opportunity_id } = await promoteFinding(request, findings[0]);
  74  |   expect(opportunity_id).toMatch(/^recovery-/);
  75  | 
  76  |   const state = await getOpportunityState(request, opportunity_id);
  77  |   expect(state).toBe("AWAITING_APPROVAL");
  78  | });
  79  | 
  80  | test("@smoke J2-3 promoted opportunity appears in Decision Inbox (pending list)", async ({
  81  |   request,
  82  | }) => {
  83  |   const scan = await runDemoScan(request);
  84  |   const findings = scan.findings as Array<Record<string, unknown>>;
  85  |   const { opportunity_id } = await promoteFinding(request, findings[0]);
  86  | 
  87  |   const pending = await getPendingApprovals(request);
  88  |   const ids = (pending as Array<{ opportunity_id: string }>).map((r) => r.opportunity_id);
  89  |   expect(ids).toContain(opportunity_id);
  90  | });
  91  | 
  92  | test("@smoke J2-4 approve changes state and approval record to APPROVED", async ({
  93  |   request,
  94  | }) => {
  95  |   const scan = await runDemoScan(request);
  96  |   const findings = scan.findings as Array<Record<string, unknown>>;
  97  |   const { opportunity_id } = await promoteFinding(request, findings[0]);
  98  | 
  99  |   // Approve with full claim binding
  100 |   const result = await approveOpportunity(request, opportunity_id);
  101 |   expect(result).toBeTruthy();
  102 | 
  103 |   // Decision Inbox should show APPROVED (or empty if record moved out of pending)
  104 |   const pending = await getPendingApprovals(request);
  105 |   const stillPending = (pending as Array<{ opportunity_id: string; state: string }>).find(
  106 |     (r) => r.opportunity_id === opportunity_id && r.state === "PENDING"
  107 |   );
  108 |   expect(stillPending).toBeUndefined();
  109 | });
  110 | 
  111 | test("@smoke J2-5 scan audit record written after demo scan", async ({ request }) => {
  112 |   await runDemoScan(request);
  113 |   const res = await request.get(`${BACKEND}/api/scan/audit`);
> 114 |   expect(res.ok()).toBeTruthy();
      |                    ^ Error: expect(received).toBeTruthy()
  115 |   const audit = (await res.json()) as Array<{ scan_id: string; finding_count: number }>;
  116 |   expect(audit.length).toBeGreaterThanOrEqual(1);
  117 |   expect(audit[0].scan_id).toBeTruthy();
  118 |   expect(audit[0].finding_count).toBeGreaterThanOrEqual(0);
  119 | });
  120 | 
  121 | // ---------------------------------------------------------------------------
  122 | // J2 — @full: edge cases
  123 | // ---------------------------------------------------------------------------
  124 | 
  125 | test("@full J2-6 promote is idempotent — same finding returns existing opportunity", async ({
  126 |   request,
  127 | }) => {
  128 |   const scan = await runDemoScan(request);
  129 |   const findings = scan.findings as Array<Record<string, unknown>>;
  130 |   const finding = findings[0];
  131 | 
  132 |   const first = await promoteFinding(request, finding);
  133 |   const second = await promoteFinding(request, finding);
  134 |   expect(second.opportunity_id).toBe(first.opportunity_id);
  135 | 
  136 |   // Only 1 pending approval for that opportunity
  137 |   const pending = await getPendingApprovals(request);
  138 |   const forOpp = (pending as Array<{ opportunity_id: string }>).filter(
  139 |     (r) => r.opportunity_id === first.opportunity_id
  140 |   );
  141 |   expect(forOpp.length).toBe(1);
  142 | });
  143 | 
  144 | test("@full J2-7 approve with tampered claim_hash returns 409", async ({ request }) => {
  145 |   const scan = await runDemoScan(request);
  146 |   const findings = scan.findings as Array<Record<string, unknown>>;
  147 |   const { opportunity_id } = await promoteFinding(request, findings[0]);
  148 | 
  149 |   // Fetch real approval record
  150 |   const pendingRes = await request.get(
  151 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}`
  152 |   );
  153 |   const pending = (await pendingRes.json()) as {
  154 |     claim_hash: string;
  155 |     amount: string;
  156 |     state_version: number;
  157 |   };
  158 | 
  159 |   // Tamper the hash
  160 |   const res = await request.post(
  161 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  162 |     {
  163 |       data: {
  164 |         principal: "playwright-attacker",
  165 |         claim_hash: "sha256:deadbeef000000000000000000000000000000000000000000000000000000000",
  166 |         amount: pending.amount,
  167 |         state_version: pending.state_version,
  168 |       },
  169 |     }
  170 |   );
  171 |   expect(res.status()).toBe(409);
  172 | });
  173 | 
  174 | test("@full J2-8 per-customer connect init returns unique external_id", async ({ request }) => {
  175 |   const res1 = await request.post(`${BACKEND}/api/scan/connect/init`);
  176 |   const res2 = await request.post(`${BACKEND}/api/scan/connect/init`);
  177 |   expect(res1.ok()).toBeTruthy();
  178 |   expect(res2.ok()).toBeTruthy();
  179 |   const c1 = (await res1.json()) as { customer_id: string; external_id: string };
  180 |   const c2 = (await res2.json()) as { customer_id: string; external_id: string };
  181 |   // Each customer gets a unique ID and ExternalId
  182 |   expect(c1.customer_id).not.toBe(c2.customer_id);
  183 |   expect(c1.external_id).not.toBe(c2.external_id);
  184 |   expect(c1.external_id.length).toBeGreaterThan(20);
  185 | });
  186 | 
  187 | test("@full J2-9 data deletion endpoint purges account scan cache", async ({ request }) => {
  188 |   await runDemoScan(request);
  189 | 
  190 |   // Get the __demo__ cache key (masked)
  191 |   const auditBefore = await request.get(`${BACKEND}/api/scan/audit`);
  192 |   const auditData = (await auditBefore.json()) as Array<{ account_id_masked: string }>;
  193 |   expect(auditData.length).toBeGreaterThan(0);
  194 | 
  195 |   // Delete using masked prefix (first 4 chars of masked account id)
  196 |   const maskedId = auditData[0].account_id_masked;
  197 |   const prefix = maskedId.slice(0, 4);
  198 | 
  199 |   // Delete via account ID (non-existing is graceful)
  200 |   const delRes = await request.delete(`${BACKEND}/api/scan/accounts/__demo__/data`);
  201 |   expect(delRes.ok()).toBeTruthy();
  202 |   const delBody = (await delRes.json()) as { status: string };
  203 |   expect(delBody.status).toBe("deleted");
  204 | });
  205 | 
```