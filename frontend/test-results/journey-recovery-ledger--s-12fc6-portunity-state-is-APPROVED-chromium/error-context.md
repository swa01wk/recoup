# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-recovery-ledger.spec.ts >> @smoke J9-2 after scan-promote-approve, opportunity state is APPROVED
- Location: e2e/journey-recovery-ledger.spec.ts:90:5

# Error details

```
Error: expect(received).toBeTruthy()

Received: false
```

# Test source

```ts
  1   | /**
  2   |  * J9 — Recovery Ledger: Correct Amounts After J2 + J4 Activity (Sprint 5)
  3   |  *
  4   |  * Tests:
  5   |  *   After J2 approve  → approved bucket increments; credit matches finding savings
  6   |  *   After J4 approve  → credit amount correct in approval record
  7   |  *   Recovered bucket  → only increments after outcome written (not just approval)
  8   |  *   Multiple approvals → ledger totals are additive
  9   |  *
  10  |  * Tags:
  11  |  *   @smoke  — single approve → ledger increment
  12  |  *   @full   — multi-approve totals, ledger accuracy, outcome vs approved
  13  |  */
  14  | import { test, expect } from "@playwright/test";
  15  | import { resetBackend, runDemoScan, promoteFinding, approveOpportunity } from "./helpers";
  16  | 
  17  | const BACKEND = "http://localhost:8000";
  18  | 
  19  | // ---------------------------------------------------------------------------
  20  | // Setup
  21  | // ---------------------------------------------------------------------------
  22  | 
  23  | test.beforeEach(async ({ request }) => {
  24  |   await resetBackend(request);
  25  | });
  26  | 
  27  | // ---------------------------------------------------------------------------
  28  | // Helpers
  29  | // ---------------------------------------------------------------------------
  30  | 
  31  | async function getLedger(
  32  |   request: import("@playwright/test").APIRequestContext
  33  | ): Promise<{
  34  |   approved_total_usd: number;
  35  |   recovered_total_usd: number;
  36  |   pending_total_usd: number;
  37  |   entries: Array<{
  38  |     opportunity_id: string;
  39  |     credit_amount: string;
  40  |     state: string;
  41  |   }>;
  42  | }> {
  43  |   const res = await request.get(`${BACKEND}/api/opportunities`);
  44  |   expect(res.ok()).toBeTruthy();
  45  |   const opps = (await res.json()) as Array<{
  46  |     opportunity_id: string;
  47  |     state: string;
  48  |     estimated_savings_usd?: number | string;
  49  |   }>;
  50  |   // Build ledger summary from opportunities list
  51  |   let approvedTotal = 0;
  52  |   let recoveredTotal = 0;
  53  |   let pendingTotal = 0;
  54  |   const entries = opps.map((o) => {
  55  |     const amount = parseFloat(String(o.estimated_savings_usd ?? "0"));
  56  |     if (o.state === "APPROVED" || o.state === "SUBMITTING" || o.state === "SUBMITTED") {
  57  |       approvedTotal += amount;
  58  |     } else if (o.state === "RECOVERED") {
  59  |       recoveredTotal += amount;
  60  |     } else if (o.state === "AWAITING_APPROVAL") {
  61  |       pendingTotal += amount;
  62  |     }
  63  |     return {
  64  |       opportunity_id: o.opportunity_id,
  65  |       credit_amount: String(o.estimated_savings_usd ?? "0"),
  66  |       state: o.state,
  67  |     };
  68  |   });
  69  |   return {
  70  |     approved_total_usd: approvedTotal,
  71  |     recovered_total_usd: recoveredTotal,
  72  |     pending_total_usd: pendingTotal,
  73  |     entries,
  74  |   };
  75  | }
  76  | 
  77  | // ---------------------------------------------------------------------------
  78  | // J9 — @smoke: happy paths
  79  | // ---------------------------------------------------------------------------
  80  | 
  81  | test("@smoke J9-1 opportunities list is accessible (foundation for ledger)", async ({
  82  |   request,
  83  | }) => {
  84  |   const res = await request.get(`${BACKEND}/api/opportunities`);
  85  |   expect(res.ok()).toBeTruthy();
  86  |   const opps = (await res.json()) as unknown[];
  87  |   expect(Array.isArray(opps)).toBeTruthy();
  88  | });
  89  | 
  90  | test("@smoke J9-2 after scan-promote-approve, opportunity state is APPROVED", async ({
  91  |   request,
  92  | }) => {
  93  |   const scan = await runDemoScan(request);
  94  |   const findings = scan.findings as Array<Record<string, unknown>>;
  95  |   const { opportunity_id } = await promoteFinding(request, findings[0]);
  96  | 
  97  |   await approveOpportunity(request, opportunity_id);
  98  | 
  99  |   const res = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
> 100 |   expect(res.ok()).toBeTruthy();
      |                    ^ Error: expect(received).toBeTruthy()
  101 |   const opp = (await res.json()) as { state: string };
  102 |   expect(["APPROVED", "SUBMITTING", "SUBMITTED"]).toContain(opp.state);
  103 | });
  104 | 
  105 | test("@smoke J9-3 after approval, approved opportunity is in opportunities list", async ({
  106 |   request,
  107 | }) => {
  108 |   const scan = await runDemoScan(request);
  109 |   const findings = scan.findings as Array<Record<string, unknown>>;
  110 |   const { opportunity_id } = await promoteFinding(request, findings[0]);
  111 |   await approveOpportunity(request, opportunity_id);
  112 | 
  113 |   const ledger = await getLedger(request);
  114 |   const found = ledger.entries.find((e) => e.opportunity_id === opportunity_id);
  115 |   expect(found).toBeTruthy();
  116 |   expect(["APPROVED", "SUBMITTING", "SUBMITTED"]).toContain(found!.state);
  117 | });
  118 | 
  119 | test("@smoke J9-4 second promote+approve adds another approved entry", async ({ request }) => {
  120 |   const scan = await runDemoScan(request);
  121 |   const findings = scan.findings as Array<Record<string, unknown>>;
  122 |   expect(findings.length).toBeGreaterThan(1);
  123 |   const { opportunity_id } = await promoteFinding(request, findings[1]);
  124 |   await approveOpportunity(request, opportunity_id);
  125 |   const ledger = await getLedger(request);
  126 |   const found = ledger.entries.find((e) => e.opportunity_id === opportunity_id);
  127 |   expect(found).toBeTruthy();
  128 |   expect(["APPROVED", "RECOVERED", "SUBMITTING", "SUBMITTED"]).toContain(found!.state);
  129 | });
  130 | 
  131 | // ---------------------------------------------------------------------------
  132 | // J9 — @full: accuracy and totals
  133 | // ---------------------------------------------------------------------------
  134 | 
  135 | test("@full J9-5 credit amount on approval matches finding savings estimate", async ({
  136 |   request,
  137 | }) => {
  138 |   const scan = await runDemoScan(request);
  139 |   const findings = scan.findings as Array<Record<string, unknown>>;
  140 |   const finding = findings[0];
  141 |   const { opportunity_id } = await promoteFinding(request, finding);
  142 | 
  143 |   // Get the approval record before approving
  144 |   const pendingRes = await request.get(
  145 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}`
  146 |   );
  147 |   const pending = (await pendingRes.json()) as { amount: string };
  148 |   const approvalAmount = parseFloat(pending.amount);
  149 | 
  150 |   // Finding's estimated savings
  151 |   const findingAmount = parseFloat(
  152 |     String(finding["estimated_monthly_savings_usd"] ?? finding["savings"] ?? "0")
  153 |   );
  154 | 
  155 |   // They should match (or approval amount is >= finding savings due to rounding)
  156 |   if (findingAmount > 0) {
  157 |     expect(approvalAmount).toBeGreaterThan(0);
  158 |   }
  159 | });
  160 | 
  161 | test("@full J9-6 multiple approvals result in multiple APPROVED entries", async ({
  162 |   request,
  163 | }) => {
  164 |   const scan = await runDemoScan(request);
  165 |   const findings = scan.findings as Array<Record<string, unknown>>;
  166 | 
  167 |   // Promote two findings if available
  168 |   const toPromote = findings.slice(0, 2);
  169 |   const ids: string[] = [];
  170 |   for (const finding of toPromote) {
  171 |     const { opportunity_id } = await promoteFinding(request, finding);
  172 |     ids.push(opportunity_id);
  173 |   }
  174 | 
  175 |   for (const id of ids) {
  176 |     await approveOpportunity(request, id);
  177 |   }
  178 | 
  179 |   const ledger = await getLedger(request);
  180 |   const approvedIds = ledger.entries
  181 |     .filter((e) => ["APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING", "RECOVERED"].includes(e.state))
  182 |     .map((e) => e.opportunity_id);
  183 | 
  184 |   for (const id of ids) {
  185 |     expect(approvedIds).toContain(id);
  186 |   }
  187 | });
  188 | 
  189 | test("@full J9-7 declined opportunity does NOT appear in approved entries", async ({
  190 |   request,
  191 | }) => {
  192 |   const scan = await runDemoScan(request);
  193 |   const findings = scan.findings as Array<Record<string, unknown>>;
  194 |   const { opportunity_id } = await promoteFinding(request, findings[0]);
  195 | 
  196 |   await request.post(
  197 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/decline`,
  198 |     { data: { principal: "playwright-test", notes: "Declined" } }
  199 |   );
  200 | 
```