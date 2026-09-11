# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-dashboard-ledger-consistency.spec.ts >> @smoke dashboard-ledger-consistency: both pages show the same Detected total
- Location: e2e/journey-dashboard-ledger-consistency.spec.ts:25:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Detected').first()
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByText('Detected').first() with timeout 10000ms
  - waiting for getByText('Detected').first()

```

```yaml
- complementary:
  - text: ⬡ Recoup Cloud Spend Recovery
  - navigation:
    - link "◈ Opportunities":
      - /url: /opportunities
    - link "⊕ Account Scanner":
      - /url: /scan
    - link "◉ Recovery Ledger":
      - /url: /recovery
  - text: Backend connected
  - paragraph: 127.0.0.1:8014
  - button "↺ Reset Demo Data"
- heading "Opportunities" [level=1]
- paragraph: Recoverable spend identified from your AWS account
- button "Refresh"
- link "New Scan":
  - /url: /scan
  - button "New Scan"
- paragraph: No recoverable opportunities yet
- paragraph: Scan your AWS account to discover idle resources and cost-saving actions.
- link "Go to Account Scanner":
  - /url: /scan
  - button "Go to Account Scanner"
- alert
```

# Test source

```ts
  1  | /**
  2  |  * Dashboard ↔ Ledger Consistency Journey
  3  |  *
  4  |  * Asserts that the Recovery Dashboard and Recovery Ledger show the same
  5  |  * Detected / Pending / Approved / Recovered bucket totals.
  6  |  * Both pages now consume the same useRecoveryData() hook, so their data
  7  |  * must be consistent.
  8  |  */
  9  | import { test, expect } from "@playwright/test";
  10 | import { resetBackend, runDemoScan, promoteFinding, approveOpportunity, pollUntilState } from "./helpers";
  11 | 
  12 | const BACKEND = "http://localhost:8000";
  13 | 
  14 | test.beforeEach(async ({ request }) => {
  15 |   await resetBackend(request);
  16 | });
  17 | 
  18 | /** Extract a dollar value from a text string like "$123.45/mo" */
  19 | function parseDollar(text: string | null): number {
  20 |   if (!text) return 0;
  21 |   const match = text.match(/\$([0-9]+(?:\.[0-9]+)?)/);
  22 |   return match ? parseFloat(match[1]) : 0;
  23 | }
  24 | 
  25 | test("@smoke dashboard-ledger-consistency: both pages show the same Detected total", async ({
  26 |   page,
  27 |   request,
  28 | }) => {
  29 |   await runDemoScan(request);
  30 | 
  31 |   // Load dashboard, capture Detected value
  32 |   await page.goto("/");
  33 |   await page.waitForLoadState("networkidle");
  34 |   // Wait for ledger strip to render
> 35 |   await expect(page.getByText("Detected").first()).toBeVisible({ timeout: 10_000 });
     |                                                    ^ Error: expect(locator).toBeVisible() failed
  36 | 
  37 |   // Navigate to ledger and verify same Detected value
  38 |   await page.goto("/recovery");
  39 |   await page.waitForLoadState("networkidle");
  40 |   await expect(page.getByText("Detected").first()).toBeVisible({ timeout: 10_000 });
  41 |   // If both pages render without error, the ledger strip data source is consistent
  42 | });
  43 | 
  44 | test("@full dashboard-ledger-consistency: Pending bucket matches after promote", async ({
  45 |   page,
  46 |   request,
  47 | }) => {
  48 |   const scan = await runDemoScan(request);
  49 |   const findings = scan.findings as Array<Record<string, unknown>>;
  50 |   await promoteFinding(request, findings[0]);
  51 | 
  52 |   // Give backend time to settle
  53 |   await page.waitForTimeout(500);
  54 | 
  55 |   // Load dashboard — capture Pending value
  56 |   await page.goto("/");
  57 |   await page.waitForLoadState("networkidle");
  58 |   await expect(page.getByText("Pending").first()).toBeVisible({ timeout: 10_000 });
  59 | 
  60 |   // Load Ledger — must also show Pending
  61 |   await page.goto("/recovery");
  62 |   await page.waitForLoadState("networkidle");
  63 |   await expect(page.getByText("Pending").first()).toBeVisible({ timeout: 10_000 });
  64 | });
  65 | 
  66 | test("@full dashboard-ledger-consistency: Approved bucket appears on both pages after approval", async ({
  67 |   page,
  68 |   request,
  69 | }) => {
  70 |   const scan = await runDemoScan(request);
  71 |   const findings = scan.findings as Array<Record<string, unknown>>;
  72 |   const { opportunity_id } = await promoteFinding(request, findings[0]);
  73 |   await pollUntilState(request, opportunity_id, "AWAITING_APPROVAL");
  74 |   await approveOpportunity(request, opportunity_id);
  75 |   await pollUntilState(request, opportunity_id, ["APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING", "RECOVERED"]);
  76 | 
  77 |   // Dashboard
  78 |   await page.goto("/");
  79 |   await page.waitForLoadState("networkidle");
  80 |   await expect(page.getByText("Approved").first()).toBeVisible({ timeout: 10_000 });
  81 | 
  82 |   // Ledger
  83 |   await page.goto("/recovery");
  84 |   await page.waitForLoadState("networkidle");
  85 |   await expect(page.getByText("Approved").first()).toBeVisible({ timeout: 10_000 });
  86 | });
  87 | 
```