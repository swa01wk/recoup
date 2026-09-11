/**
 * UI Browser Journey — aligned with J-FULL (operator-journey.md)
 *
 * Click-through tests for the three-link IA: Opportunities · Account Scanner · Recovery Ledger.
 * HITL lives on /opportunities/[id] (/approvals and /quality redirect).
 *
 * Tags: @ui · @smoke
 */
import { test, expect, type Page } from "@playwright/test";
import { resetBackend } from "./helpers";

const BACKEND = "http://localhost:8000";

test.beforeEach(async ({ request, page }) => {
  await resetBackend(request);
  await page.goto("/");
});

async function promoteFirstFinding(page: Page): Promise<string> {
  const scanRes = await page.request.post(`${BACKEND}/api/scan/demo`);
  expect(scanRes.ok()).toBeTruthy();
  const scan = (await scanRes.json()) as { findings: Array<Record<string, unknown>> };
  const promoteRes = await page.request.post(`${BACKEND}/api/scan/findings/promote`, {
    data: scan.findings[0],
  });
  expect(promoteRes.ok()).toBeTruthy();
  const promoted = (await promoteRes.json()) as { opportunity_id: string };
  return promoted.opportunity_id;
}

test("@smoke @ui UI-1 Opportunities hub loads", async ({ page }) => {
  await page.goto("/opportunities");
  await expect(page.getByRole("heading", { name: /^Opportunities$/i })).toBeVisible({
    timeout: 15_000,
  });
});

test("@smoke @ui UI-2 Account Scanner page loads with demo scan", async ({ page }) => {
  await page.goto("/scan");
  await expect(page.getByRole("heading", { name: /Account Scanner/i })).toBeVisible({
    timeout: 10_000,
  });
  const scanBtn = page.getByRole("button", { name: /run demo scan/i }).first();
  await expect(scanBtn).toBeVisible({ timeout: 5_000 });
});

test("@smoke @ui UI-3 Demo scan navigates to opportunities", async ({ page }) => {
  await page.goto("/scan");
  const consent = page.getByRole("checkbox").first();
  if (await consent.isVisible()) await consent.check();
  await page.getByRole("button", { name: /run demo scan/i }).first().click();
  await expect(page).toHaveURL(/\/opportunities/, { timeout: 60_000 });
  await expect(page.getByRole("heading", { name: /^Opportunities$/i })).toBeVisible({
    timeout: 15_000,
  });
});

test("@smoke @ui UI-4 HITL buttons on opportunity detail", async ({ page }) => {
  const oppId = await promoteFirstFinding(page);
  await page.goto(`/opportunities/${oppId}`);
  await expect(page.getByRole("button", { name: /approve recovery/i })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("button", { name: /decline/i }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /investigate/i }).first()).toBeVisible();
});

test("@smoke @ui UI-5 Approve recovery from detail page", async ({ page }) => {
  const oppId = await promoteFirstFinding(page);
  await page.goto(`/opportunities/${oppId}`);

  const approveBtn = page.getByRole("button", { name: /approve recovery/i });
  await expect(approveBtn).toBeVisible({ timeout: 15_000 });

  const responsePromise = page.waitForResponse(
    (r) =>
      r.url().includes(`/api/approvals/opportunity/${oppId}/approve`) &&
      r.request().method() === "POST" &&
      r.status() === 200,
    { timeout: 30_000 }
  );
  await approveBtn.click();
  await responsePromise;
});

test("@smoke @ui UI-6 Recovery Ledger renders buckets", async ({ page }) => {
  await page.goto("/recovery");
  await expect(page.getByText(/recovery ledger/i).first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/pending/i).first()).toBeVisible({ timeout: 5_000 });
});

test("@smoke @ui UI-8b cost-recovery detail shows Cost Recovery Analysis", async ({ page }) => {
  const oppId = await promoteFirstFinding(page);
  await page.goto(`/opportunities/${oppId}`);
  await expect(page.getByText(/cost recovery analysis/i).first()).toBeVisible({
    timeout: 10_000,
  });
  await expect(page.getByText(/availability result/i).first()).not.toBeVisible();
});

test("@smoke @ui UI-9 /quality redirects to opportunities", async ({ page }) => {
  await page.goto("/quality");
  await expect(page).toHaveURL(/\/opportunities/, { timeout: 10_000 });
});

test("@smoke @ui UI-10c Sidebar shows three nav links only", async ({ page }) => {
  await page.goto("/opportunities");
  const nav = page.locator("aside nav");
  await expect(nav.getByRole("link", { name: /Opportunities/i })).toBeVisible();
  await expect(nav.getByRole("link", { name: /Account Scanner/i })).toBeVisible();
  await expect(nav.getByRole("link", { name: /Recovery Ledger/i })).toBeVisible();
  await expect(nav.getByRole("link", { name: /SLA Replay/i })).toHaveCount(0);
});

test("@smoke @ui UI-replay-removed /replay route is not available", async ({ page }) => {
  const res = await page.goto("/replay");
  expect(res?.status()).toBe(404);
});
