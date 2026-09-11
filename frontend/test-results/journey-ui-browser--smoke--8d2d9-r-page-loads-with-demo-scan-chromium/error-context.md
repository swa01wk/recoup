# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-ui-browser.spec.ts >> @smoke @ui UI-2 Account Scanner page loads with demo scan
- Location: e2e/journey-ui-browser.spec.ts:38:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('button', { name: /run demo scan/i }).first()
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('button', { name: /run demo scan/i }).first() with timeout 5000ms
  - waiting for getByRole('button', { name: /run demo scan/i }).first()

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
- heading "Account Scanner" [level=1]
- paragraph: Connect your AWS account and scan for recoverable spend.
- heading "AWS Connection" [level=3]
- text: Not connected Role ARN
- textbox "arn:aws:iam::123456789012:role/RecoupReadOnlyRole"
- text: External ID
- textbox "••••••••••••••••"
- text: Region
- combobox:
  - option "us-east-1" [selected]
  - option "us-east-2"
  - option "us-west-1"
  - option "us-west-2"
  - option "eu-west-1"
  - option "eu-west-2"
  - option "eu-central-1"
  - option "ap-southeast-1"
  - option "ap-southeast-2"
  - option "ap-northeast-1"
  - option "ca-central-1"
  - option "sa-east-1"
- button "▸ New customer? Connect AWS account"
- text: 🔒
- heading "Security & Access Summary" [level=3]
- paragraph: Read-only access
- list:
  - listitem: ✓ STS AssumeRole
  - listitem: ✓ Temporary credentials
  - listitem: ✓ DenyAllWrites
  - listitem: ✓ No resource changes without approval
- button "▸ View access details"
- checkbox "I understand Recoup will make read-only API calls to my AWS account. No resources will be created, modified, or deleted without my explicit approval."
- text: I understand Recoup will make read-only API calls to my AWS account. No resources will be created, modified, or deleted without my explicit approval.
- paragraph: Accept the access consent above before scanning.
- button "Scan AWS Account" [disabled]
- button "Quick Preview" [disabled]
- button "Demo Scan"
- alert
```

# Test source

```ts
  1   | /**
  2   |  * UI Browser Journey — aligned with J-FULL (operator-journey.md)
  3   |  *
  4   |  * Click-through tests for the three-link IA: Opportunities · Account Scanner · Recovery Ledger.
  5   |  * HITL lives on /opportunities/[id] (/approvals and /quality redirect).
  6   |  *
  7   |  * Tags: @ui · @smoke
  8   |  */
  9   | import { test, expect, type Page } from "@playwright/test";
  10  | import { resetBackend } from "./helpers";
  11  | 
  12  | const BACKEND = "http://localhost:8000";
  13  | 
  14  | test.beforeEach(async ({ request, page }) => {
  15  |   await resetBackend(request);
  16  |   await page.goto("/");
  17  | });
  18  | 
  19  | async function promoteFirstFinding(page: Page): Promise<string> {
  20  |   const scanRes = await page.request.post(`${BACKEND}/api/scan/demo`);
  21  |   expect(scanRes.ok()).toBeTruthy();
  22  |   const scan = (await scanRes.json()) as { findings: Array<Record<string, unknown>> };
  23  |   const promoteRes = await page.request.post(`${BACKEND}/api/scan/findings/promote`, {
  24  |     data: scan.findings[0],
  25  |   });
  26  |   expect(promoteRes.ok()).toBeTruthy();
  27  |   const promoted = (await promoteRes.json()) as { opportunity_id: string };
  28  |   return promoted.opportunity_id;
  29  | }
  30  | 
  31  | test("@smoke @ui UI-1 Opportunities hub loads", async ({ page }) => {
  32  |   await page.goto("/opportunities");
  33  |   await expect(page.getByRole("heading", { name: /^Opportunities$/i })).toBeVisible({
  34  |     timeout: 15_000,
  35  |   });
  36  | });
  37  | 
  38  | test("@smoke @ui UI-2 Account Scanner page loads with demo scan", async ({ page }) => {
  39  |   await page.goto("/scan");
  40  |   await expect(page.getByRole("heading", { name: /Account Scanner/i })).toBeVisible({
  41  |     timeout: 10_000,
  42  |   });
  43  |   const scanBtn = page.getByRole("button", { name: /run demo scan/i }).first();
> 44  |   await expect(scanBtn).toBeVisible({ timeout: 5_000 });
      |                         ^ Error: expect(locator).toBeVisible() failed
  45  | });
  46  | 
  47  | test("@smoke @ui UI-3 Demo scan navigates to opportunities", async ({ page }) => {
  48  |   await page.goto("/scan");
  49  |   const consent = page.getByRole("checkbox").first();
  50  |   if (await consent.isVisible()) await consent.check();
  51  |   await page.getByRole("button", { name: /run demo scan/i }).first().click();
  52  |   await expect(page).toHaveURL(/\/opportunities/, { timeout: 60_000 });
  53  |   await expect(page.getByRole("heading", { name: /^Opportunities$/i })).toBeVisible({
  54  |     timeout: 15_000,
  55  |   });
  56  | });
  57  | 
  58  | test("@smoke @ui UI-4 HITL buttons on opportunity detail", async ({ page }) => {
  59  |   const oppId = await promoteFirstFinding(page);
  60  |   await page.goto(`/opportunities/${oppId}`);
  61  |   await expect(page.getByRole("button", { name: /approve recovery/i })).toBeVisible({
  62  |     timeout: 15_000,
  63  |   });
  64  |   await expect(page.getByRole("button", { name: /decline/i }).first()).toBeVisible();
  65  |   await expect(page.getByRole("button", { name: /investigate/i }).first()).toBeVisible();
  66  | });
  67  | 
  68  | test("@smoke @ui UI-5 Approve recovery from detail page", async ({ page }) => {
  69  |   const oppId = await promoteFirstFinding(page);
  70  |   await page.goto(`/opportunities/${oppId}`);
  71  | 
  72  |   const approveBtn = page.getByRole("button", { name: /approve recovery/i });
  73  |   await expect(approveBtn).toBeVisible({ timeout: 15_000 });
  74  | 
  75  |   const responsePromise = page.waitForResponse(
  76  |     (r) =>
  77  |       r.url().includes(`/api/approvals/opportunity/${oppId}/approve`) &&
  78  |       r.request().method() === "POST" &&
  79  |       r.status() === 200,
  80  |     { timeout: 30_000 }
  81  |   );
  82  |   await approveBtn.click();
  83  |   await responsePromise;
  84  | });
  85  | 
  86  | test("@smoke @ui UI-6 Recovery Ledger renders buckets", async ({ page }) => {
  87  |   await page.goto("/recovery");
  88  |   await expect(page.getByText(/recovery ledger/i).first()).toBeVisible({ timeout: 10_000 });
  89  |   await expect(page.getByText(/pending/i).first()).toBeVisible({ timeout: 5_000 });
  90  | });
  91  | 
  92  | test("@smoke @ui UI-8b cost-recovery detail shows Cost Recovery Analysis", async ({ page }) => {
  93  |   const oppId = await promoteFirstFinding(page);
  94  |   await page.goto(`/opportunities/${oppId}`);
  95  |   await expect(page.getByText(/cost recovery analysis/i).first()).toBeVisible({
  96  |     timeout: 10_000,
  97  |   });
  98  |   await expect(page.getByText(/availability result/i).first()).not.toBeVisible();
  99  | });
  100 | 
  101 | test("@smoke @ui UI-9 /quality redirects to opportunities", async ({ page }) => {
  102 |   await page.goto("/quality");
  103 |   await expect(page).toHaveURL(/\/opportunities/, { timeout: 10_000 });
  104 | });
  105 | 
  106 | test("@smoke @ui UI-10c Sidebar shows three nav links only", async ({ page }) => {
  107 |   await page.goto("/opportunities");
  108 |   const nav = page.locator("aside nav");
  109 |   await expect(nav.getByRole("link", { name: /Opportunities/i })).toBeVisible();
  110 |   await expect(nav.getByRole("link", { name: /Account Scanner/i })).toBeVisible();
  111 |   await expect(nav.getByRole("link", { name: /Recovery Ledger/i })).toBeVisible();
  112 |   await expect(nav.getByRole("link", { name: /SLA Replay/i })).toHaveCount(0);
  113 | });
  114 | 
  115 | test("@smoke @ui UI-replay-removed /replay route is not available", async ({ page }) => {
  116 |   const res = await page.goto("/replay");
  117 |   expect(res?.status()).toBe(404);
  118 | });
  119 | 
```