# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-opportunity-detail.spec.ts >> @smoke J7-3 approve from opportunity detail — state transitions to APPROVED
- Location: e2e/journey-opportunity-detail.spec.ts:44:5

# Error details

```
Error: expect(received).toContain(expected) // indexOf

Expected value: undefined
Received array: ["APPROVED", "RECOVERED", "SUBMITTING", "SUBMITTED"]
```

# Test source

```ts
  1   | /**
  2   |  * J7 — Opportunity Detail (J-FULL / scan-promoted path)
  3   |  */
  4   | import { test, expect } from "@playwright/test";
  5   | import { resetBackend, approveOpportunity, runDemoScan, promoteFinding } from "./helpers";
  6   | 
  7   | const BACKEND = "http://localhost:8000";
  8   | 
  9   | test.beforeEach(async ({ request }) => {
  10  |   await resetBackend(request);
  11  | });
  12  | 
  13  | async function triggerScanOpportunity(
  14  |   request: import("@playwright/test").APIRequestContext,
  15  |   index = 0
  16  | ): Promise<{ opportunity_id: string }> {
  17  |   const scan = await runDemoScan(request);
  18  |   const findings = scan.findings as Array<Record<string, unknown>>;
  19  |   expect(findings.length).toBeGreaterThan(index);
  20  |   return promoteFinding(request, findings[index]);
  21  | }
  22  | 
  23  | test("@smoke J7-1 opportunity detail is reachable and returns state", async ({ request }) => {
  24  |   const { opportunity_id } = await triggerScanOpportunity(request);
  25  |   const res = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
  26  |   expect(res.ok()).toBeTruthy();
  27  |   const opp = (await res.json()) as { opportunity_id: string; state: string };
  28  |   expect(opp.opportunity_id).toBe(opportunity_id);
  29  |   expect(opp.state).toBe("AWAITING_APPROVAL");
  30  | });
  31  | 
  32  | test("@smoke J7-2 promoted opportunity stream endpoint responds with SSE content-type", async ({
  33  |   request,
  34  | }) => {
  35  |   const { opportunity_id } = await triggerScanOpportunity(request);
  36  |   const res = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}/stream`);
  37  |   expect([200, 204]).toContain(res.status());
  38  |   if (res.status() === 200) {
  39  |     const contentType = res.headers()["content-type"] ?? "";
  40  |     expect(contentType).toContain("text/event-stream");
  41  |   }
  42  | });
  43  | 
  44  | test("@smoke J7-3 approve from opportunity detail — state transitions to APPROVED", async ({
  45  |   request,
  46  | }) => {
  47  |   const { opportunity_id } = await triggerScanOpportunity(request);
  48  |   await approveOpportunity(request, opportunity_id);
  49  |   const opp = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
  50  |   const oppBody = (await opp.json()) as { state: string };
> 51  |   expect(["APPROVED", "RECOVERED", "SUBMITTING", "SUBMITTED"]).toContain(oppBody.state);
      |                                                                ^ Error: expect(received).toContain(expected) // indexOf
  52  | });
  53  | 
  54  | test("@smoke J7-4 decline from opportunity detail — approval state is DECLINED", async ({
  55  |   request,
  56  | }) => {
  57  |   const { opportunity_id } = await triggerScanOpportunity(request);
  58  |   const res = await request.post(
  59  |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/decline`,
  60  |     { data: { principal: "playwright-test", notes: "Declined from detail" } }
  61  |   );
  62  |   expect(res.ok()).toBeTruthy();
  63  |   const body = (await res.json()) as { state: string };
  64  |   expect(body.state).toBe("DECLINED");
  65  | });
  66  | 
  67  | test("@full J7-5 investigate endpoint sets opportunity_state to NEEDS_FOLLOWUP", async ({
  68  |   request,
  69  | }) => {
  70  |   const { opportunity_id } = await triggerScanOpportunity(request);
  71  |   const res = await request.post(
  72  |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/investigate`,
  73  |     { data: { principal: "playwright-test", notes: "More data needed" } }
  74  |   );
  75  |   expect(res.ok()).toBeTruthy();
  76  |   const body = (await res.json()) as { opportunity_state: string };
  77  |   expect(body.opportunity_state).toBe("NEEDS_FOLLOWUP");
  78  | });
  79  | 
  80  | test("@full J7-6 opportunity trace returns data for scan-promoted path", async ({ request }) => {
  81  |   const { opportunity_id } = await triggerScanOpportunity(request);
  82  |   const res = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}/trace`);
  83  |   expect(res.ok()).toBeTruthy();
  84  |   const trace = (await res.json()) as {
  85  |     opportunity_id: string;
  86  |     nodes?: Array<{ node: string }>;
  87  |     events?: Array<{ node: string }>;
  88  |   };
  89  |   expect(trace.opportunity_id).toBe(opportunity_id);
  90  | });
  91  | 
  92  | test("@full J7-7 list opportunities includes multiple promoted entries", async ({ request }) => {
  93  |   const { opportunity_id: id1 } = await triggerScanOpportunity(request, 0);
  94  |   const { opportunity_id: id2 } = await triggerScanOpportunity(request, 1);
  95  |   const res = await request.get(`${BACKEND}/api/opportunities`);
  96  |   expect(res.ok()).toBeTruthy();
  97  |   const ids = ((await res.json()) as Array<{ opportunity_id: string }>).map((o) => o.opportunity_id);
  98  |   expect(ids).toContain(id1);
  99  |   expect(ids).toContain(id2);
  100 | });
  101 | 
  102 | test("@full J7-8 unknown opportunity_id returns 404", async ({ request }) => {
  103 |   const res = await request.get(`${BACKEND}/api/opportunities/nonexistent-opp-id`);
  104 |   expect(res.status()).toBe(404);
  105 | });
  106 | 
  107 | test("@full J7-9 opportunity run endpoint accepts scan-promoted opportunity", async ({
  108 |   request,
  109 | }) => {
  110 |   const { opportunity_id } = await triggerScanOpportunity(request);
  111 |   const res = await request.post(`${BACKEND}/api/opportunities/${opportunity_id}/run`, {
  112 |     data: { use_strands: false },
  113 |   });
  114 |   expect([200, 409, 422]).toContain(res.status());
  115 | });
  116 | 
```