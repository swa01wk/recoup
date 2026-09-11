# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-scan-idempotency.spec.ts >> @smoke scan-idempotency: promoting the same finding twice returns the same opportunity_id
- Location: e2e/journey-scan-idempotency.spec.ts:32:5

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: "existing"
Received: undefined
```

# Test source

```ts
  1  | /**
  2  |  * Scan Idempotency Journey
  3  |  *
  4  |  * Verifies that running the demo scan twice does not create duplicate
  5  |  * opportunities and does not increase the opportunity count.
  6  |  */
  7  | import { test, expect } from "@playwright/test";
  8  | import { resetBackend, runDemoScan, promoteFinding } from "./helpers";
  9  | 
  10 | const BACKEND = "http://localhost:8000";
  11 | 
  12 | test.beforeEach(async ({ request }) => {
  13 |   await resetBackend(request);
  14 | });
  15 | 
  16 | test("@smoke scan-idempotency: running demo scan twice does not duplicate findings", async ({
  17 |   request,
  18 | }) => {
  19 |   // First scan
  20 |   const scan1 = await runDemoScan(request);
  21 |   const findingCount1 = (scan1.findings as unknown[]).length;
  22 |   expect(findingCount1).toBeGreaterThan(0);
  23 | 
  24 |   // Second scan — should return same data (cached)
  25 |   const scan2 = await runDemoScan(request);
  26 |   const findingCount2 = (scan2.findings as unknown[]).length;
  27 | 
  28 |   // Finding count must be identical — no duplicates
  29 |   expect(findingCount2).toBe(findingCount1);
  30 | });
  31 | 
  32 | test("@smoke scan-idempotency: promoting the same finding twice returns the same opportunity_id", async ({
  33 |   request,
  34 | }) => {
  35 |   const scan = await runDemoScan(request);
  36 |   const findings = scan.findings as Array<Record<string, unknown>>;
  37 |   const finding = findings[0];
  38 | 
  39 |   const res1 = await request.post(`${BACKEND}/api/scan/findings/promote`, { data: finding });
  40 |   const data1 = (await res1.json()) as { opportunity_id: string; status: string };
  41 | 
  42 |   const res2 = await request.post(`${BACKEND}/api/scan/findings/promote`, { data: finding });
  43 |   const data2 = (await res2.json()) as { opportunity_id: string; status: string };
  44 | 
  45 |   // Same opportunity_id returned
  46 |   expect(data2.opportunity_id).toBe(data1.opportunity_id);
  47 |   // Second call returns "existing" status
> 48 |   expect(data2.status).toBe("existing");
     |                        ^ Error: expect(received).toBe(expected) // Object.is equality
  49 | });
  50 | 
  51 | test("@smoke scan-idempotency: opportunity count stays same after second scan + re-promote", async ({
  52 |   request,
  53 | }) => {
  54 |   // Promote first finding from first scan
  55 |   const scan = await runDemoScan(request);
  56 |   const findings = scan.findings as Array<Record<string, unknown>>;
  57 |   await promoteFinding(request, findings[0]);
  58 | 
  59 |   // Get opportunity count
  60 |   const oppsBefore = (await (await request.get(`${BACKEND}/api/opportunities`)).json()) as unknown[];
  61 |   const countBefore = oppsBefore.length;
  62 | 
  63 |   // Run scan again + re-promote same finding
  64 |   await runDemoScan(request);
  65 |   await request.post(`${BACKEND}/api/scan/findings/promote`, { data: findings[0] });
  66 | 
  67 |   // Opportunity count must not increase
  68 |   const oppsAfter = (await (await request.get(`${BACKEND}/api/opportunities`)).json()) as unknown[];
  69 |   expect(oppsAfter.length).toBe(countBefore);
  70 | });
  71 | 
  72 | test("@smoke scan-idempotency: Dashboard totals unchanged after second scan", async ({
  73 |   page,
  74 |   request,
  75 | }) => {
  76 |   const scan = await runDemoScan(request);
  77 |   const findings = scan.findings as Array<Record<string, unknown>>;
  78 |   await promoteFinding(request, findings[0]);
  79 | 
  80 |   // Load dashboard
  81 |   await page.goto("/");
  82 |   await page.waitForLoadState("networkidle");
  83 | 
  84 |   // Capture a reference number visible in the ledger strip
  85 |   const ledgerText = await page.locator("text=/\\$[0-9]+\\.[0-9]+\\/mo/").first().textContent();
  86 | 
  87 |   // Run second scan
  88 |   await runDemoScan(request);
  89 | 
  90 |   // Reload and verify ledger strip shows same amount (within tolerance)
  91 |   await page.reload();
  92 |   await page.waitForLoadState("networkidle");
  93 |   const ledgerText2 = await page.locator("text=/\\$[0-9]+\\.[0-9]+\\/mo/").first().textContent();
  94 | 
  95 |   // Values should be the same (idempotent)
  96 |   expect(ledgerText2).toBe(ledgerText);
  97 | });
  98 | 
```