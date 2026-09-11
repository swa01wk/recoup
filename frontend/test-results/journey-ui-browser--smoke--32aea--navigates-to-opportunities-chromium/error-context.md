# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-ui-browser.spec.ts >> @smoke @ui UI-3 Demo scan navigates to opportunities
- Location: e2e/journey-ui-browser.spec.ts:47:5

# Error details

```
Test timeout of 360000ms exceeded.
```

```
Error: locator.click: Test timeout of 360000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: /run demo scan/i }).first()

```

# Page snapshot

```yaml
- generic [ref=f1e1]:
  - complementary [ref=f1e2]:
    - generic [ref=f1e3]:
      - generic [ref=f1e4]: ⬡
      - generic [ref=f1e5]:
        - generic [ref=f1e6]: Recoup
        - text: Cloud Spend Recovery
    - navigation [ref=f1e7]:
      - link "◈ Opportunities" [ref=f1e8] [cursor=pointer]:
        - /url: /opportunities
        - generic [ref=f1e9]: ◈
        - generic [ref=f1e10]: Opportunities
      - link "⊕ Account Scanner" [ref=f1e11] [cursor=pointer]:
        - /url: /scan
        - generic [ref=f1e12]: ⊕
        - generic [ref=f1e13]: Account Scanner
      - link "◉ Recovery Ledger" [ref=f1e14] [cursor=pointer]:
        - /url: /recovery
        - generic [ref=f1e15]: ◉
        - generic [ref=f1e16]: Recovery Ledger
    - generic [ref=f1e17]:
      - generic [ref=f1e18]:
        - generic [ref=f1e19]: Backend connected
        - paragraph [ref=f1e22]: 127.0.0.1:8014
      - button "↺ Reset Demo Data" [ref=f1e24]:
        - generic [ref=f1e25]: ↺
        - text: Reset Demo Data
  - generic [ref=f1e27]:
    - generic [ref=f1e28]:
      - heading "Account Scanner" [level=1] [ref=f1e29]
      - paragraph [ref=f1e30]: Connect your AWS account and scan for recoverable spend.
    - generic [ref=f1e31]:
      - generic [ref=f1e32]:
        - heading "AWS Connection" [level=3] [ref=f1e33]
        - generic [ref=f1e34]: Not connected
      - generic [ref=f1e35]:
        - generic [ref=f1e36]:
          - generic [ref=f1e37]:
            - generic [ref=f1e38]: Role ARN
            - textbox "arn:aws:iam::123456789012:role/RecoupReadOnlyRole" [ref=f1e39]
          - generic [ref=f1e40]:
            - generic [ref=f1e41]:
              - generic [ref=f1e42]: External ID
              - textbox "••••••••••••••••" [ref=f1e43]
            - generic [ref=f1e44]:
              - generic [ref=f1e45]: Region
              - combobox [ref=f1e46]:
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
        - button "▸ New customer? Connect AWS account" [ref=f1e48]:
          - generic [ref=f1e49]: ▸
          - text: New customer? Connect AWS account
    - generic [ref=f1e50]:
      - generic [ref=f1e51]:
        - generic [ref=f1e52]: 🔒
        - heading "Security & Access Summary" [level=3] [ref=f1e53]
      - generic [ref=f1e54]:
        - paragraph [ref=f1e55]: Read-only access
        - list [ref=f1e56]:
          - listitem [ref=f1e57]:
            - generic [ref=f1e58]: ✓
            - text: STS AssumeRole
          - listitem [ref=f1e59]:
            - generic [ref=f1e60]: ✓
            - text: Temporary credentials
          - listitem [ref=f1e61]:
            - generic [ref=f1e62]: ✓
            - text: DenyAllWrites
          - listitem [ref=f1e63]:
            - generic [ref=f1e64]: ✓
            - text: No resource changes without approval
      - button "▸ View access details" [ref=f1e66]:
        - generic [ref=f1e67]: ▸
        - text: View access details
      - generic [ref=f1e68] [cursor=pointer]:
        - checkbox "I understand Recoup will make read-only API calls to my AWS account. No resources will be created, modified, or deleted without my explicit approval." [checked] [active] [ref=f1e69]
        - generic [ref=f1e70]: I understand Recoup will make read-only API calls to my AWS account. No resources will be created, modified, or deleted without my explicit approval.
    - generic [ref=f1e72]:
      - button "Scan AWS Account" [ref=f1e73] [cursor=pointer]
      - generic [ref=f1e74]:
        - button "Quick Preview" [ref=f1e75] [cursor=pointer]
        - button "Demo Scan" [ref=f1e76] [cursor=pointer]
  - button "Open Next.js Dev Tools" [ref=f1e82] [cursor=pointer]
  - alert [ref=f1e86]
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
  44  |   await expect(scanBtn).toBeVisible({ timeout: 5_000 });
  45  | });
  46  | 
  47  | test("@smoke @ui UI-3 Demo scan navigates to opportunities", async ({ page }) => {
  48  |   await page.goto("/scan");
  49  |   const consent = page.getByRole("checkbox").first();
  50  |   if (await consent.isVisible()) await consent.check();
> 51  |   await page.getByRole("button", { name: /run demo scan/i }).first().click();
      |                                                                      ^ Error: locator.click: Test timeout of 360000ms exceeded.
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