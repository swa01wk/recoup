# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-decision-inbox.spec.ts >> @smoke J6-1 pending approval appears in Decision Inbox list
- Location: e2e/journey-decision-inbox.spec.ts:75:5

# Error details

```
Error: expect(received).toBeTruthy()

Received: false
```

# Test source

```ts
  1   | /**
  2   |  * J6 — Decision Inbox: approve / decline / investigate flows (Sprint 5)
  3   |  *
  4   |  * Tests all three action paths through the Decision Inbox, verifying:
  5   |  * - Approve: approval moves to APPROVED, no longer in pending list
  6   |  * - Decline: approval moves to DECLINED, not in pending (DENIED)
  7   |  * - Investigate: approval state becomes NEEDS_FOLLOWUP (not DECLINED)
  8   |  * - Tamper guard: tampered claim_hash returns 409
  9   |  * - CORS: X-Request-ID header present on all responses
  10  |  *
  11  |  * Tags:
  12  |  *   @smoke  — approve + decline + investigate happy paths
  13  |  *   @full   — tamper, re-approve, expiry edge cases
  14  |  */
  15  | import { test, expect } from "@playwright/test";
  16  | import {
  17  |   resetBackend,
  18  |   runDemoScan,
  19  |   promoteFinding,
  20  |   approveOpportunity,
  21  | } from "./helpers";
  22  | 
  23  | const BACKEND = "http://localhost:8000";
  24  | 
  25  | // ---------------------------------------------------------------------------
  26  | // Setup
  27  | // ---------------------------------------------------------------------------
  28  | 
  29  | test.beforeEach(async ({ request }) => {
  30  |   await resetBackend(request);
  31  | });
  32  | 
  33  | // ---------------------------------------------------------------------------
  34  | // Helpers
  35  | // ---------------------------------------------------------------------------
  36  | 
  37  | async function setupPendingApproval(
  38  |   request: import("@playwright/test").APIRequestContext
  39  | ): Promise<{
  40  |   opportunity_id: string;
  41  |   approval_id: string;
  42  |   claim_hash: string;
  43  |   amount: string;
  44  |   state_version: number;
  45  | }> {
  46  |   const scan = await runDemoScan(request);
  47  |   const findings = scan.findings as Array<Record<string, unknown>>;
  48  |   const { opportunity_id } = await promoteFinding(request, findings[0]);
  49  | 
  50  |   const pendingRes = await request.get(
  51  |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}`
  52  |   );
> 53  |   expect(pendingRes.ok()).toBeTruthy();
      |                           ^ Error: expect(received).toBeTruthy()
  54  |   const pending = (await pendingRes.json()) as {
  55  |     approval_id: string;
  56  |     claim_hash: string;
  57  |     amount: string;
  58  |     state_version: number;
  59  |   };
  60  |   return { opportunity_id, ...pending };
  61  | }
  62  | 
  63  | async function listAllApprovals(
  64  |   request: import("@playwright/test").APIRequestContext
  65  | ): Promise<Array<{ approval_id: string; state: string; opportunity_id: string }>> {
  66  |   const res = await request.get(`${BACKEND}/api/approvals/pending`);
  67  |   expect(res.ok()).toBeTruthy();
  68  |   return res.json();
  69  | }
  70  | 
  71  | // ---------------------------------------------------------------------------
  72  | // J6 — @smoke: happy paths
  73  | // ---------------------------------------------------------------------------
  74  | 
  75  | test("@smoke J6-1 pending approval appears in Decision Inbox list", async ({ request }) => {
  76  |   const { opportunity_id, approval_id } = await setupPendingApproval(request);
  77  |   const pending = await listAllApprovals(request);
  78  |   const found = pending.find((r) => r.opportunity_id === opportunity_id);
  79  |   expect(found).toBeTruthy();
  80  |   expect(found!.approval_id).toBe(approval_id);
  81  | });
  82  | 
  83  | test("@smoke J6-2 approve path — approval no longer in PENDING list after approve", async ({
  84  |   request,
  85  | }) => {
  86  |   const { opportunity_id } = await setupPendingApproval(request);
  87  |   await approveOpportunity(request, opportunity_id);
  88  | 
  89  |   const pending = await listAllApprovals(request);
  90  |   const stillPending = pending.find(
  91  |     (r) => r.opportunity_id === opportunity_id && r.state === "PENDING"
  92  |   );
  93  |   expect(stillPending).toBeUndefined();
  94  | });
  95  | 
  96  | test("@smoke J6-2b approve path — opportunity advances to pipeline stage 9 (Remediate) after approval", async ({
  97  |   request,
  98  | }) => {
  99  |   const { opportunity_id } = await setupPendingApproval(request);
  100 | 
  101 |   // Verify opportunity is at stage 8 (AWAITING_APPROVAL) before approval
  102 |   const beforeRes = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
  103 |   expect(beforeRes.ok()).toBeTruthy();
  104 |   const before = (await beforeRes.json()) as { state: string };
  105 |   expect(before.state).toBe("AWAITING_APPROVAL");
  106 | 
  107 |   // Approve
  108 |   await approveOpportunity(request, opportunity_id);
  109 | 
  110 |   // Opportunity state must be APPROVED (stage 9 — Remediate)
  111 |   const afterRes = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
  112 |   expect(afterRes.ok()).toBeTruthy();
  113 |   const after = (await afterRes.json()) as { state: string; lifecycle_state?: string };
  114 |   expect(after.state).toBe("APPROVED");
  115 |   // lifecycle_state canonical bucket must be APPROVED (stage 9 in the 11-step pipeline)
  116 |   if (after.lifecycle_state !== undefined) {
  117 |     expect(after.lifecycle_state).toBe("APPROVED");
  118 |   }
  119 | });
  120 | 
  121 | test("@smoke J6-3 decline path — approval state is DECLINED after decline", async ({
  122 |   request,
  123 | }) => {
  124 |   const { opportunity_id, approval_id } = await setupPendingApproval(request);
  125 | 
  126 |   const res = await request.post(
  127 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/decline`,
  128 |     {
  129 |       data: { principal: "playwright-test", notes: "Declined via test" },
  130 |     }
  131 |   );
  132 |   expect(res.ok()).toBeTruthy();
  133 |   const body = (await res.json()) as { approval_id: string; state: string };
  134 |   expect(body.approval_id).toBe(approval_id);
  135 |   expect(body.state).toBe("DECLINED");
  136 | 
  137 |   // Should not appear in pending list
  138 |   const pending = await listAllApprovals(request);
  139 |   const stillPending = pending.find((r) => r.opportunity_id === opportunity_id);
  140 |   expect(stillPending).toBeUndefined();
  141 | });
  142 | 
  143 | test("@smoke J6-4 investigate path — state is DECLINED with [INVESTIGATE] notes (NEEDS_FOLLOWUP)", async ({
  144 |   request,
  145 | }) => {
  146 |   const { opportunity_id } = await setupPendingApproval(request);
  147 | 
  148 |   const res = await request.post(
  149 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/investigate`,
  150 |     {
  151 |       data: { principal: "playwright-test", notes: "Need more data" },
  152 |     }
  153 |   );
```