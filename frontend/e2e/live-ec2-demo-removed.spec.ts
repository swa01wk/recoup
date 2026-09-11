/**
 * EC2 Demo Removed — UI Absence Checks
 *
 * Asserts that the "Live EC2 Stop Demo" card and the "SLA Replay" nav item
 * are NOT present in the DOM anywhere in the dashboard navigation.
 */
import { test, expect } from "@playwright/test";
import { resetBackend } from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

test("@smoke ec2-demo-removed: Live EC2 Stop Demo card is absent from Recovery Dashboard", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  // EC2 Demo card must NOT be present
  await expect(page.getByText(/Live EC2 Stop Demo/i)).not.toBeVisible();
  await expect(page.getByText(/Trigger EC2 Analysis/i)).not.toBeVisible();
  await expect(page.getByText(/Execute Stop/i)).not.toBeVisible();
});

test("@smoke ec2-demo-removed: SLA Replay nav item is absent from sidebar", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  // SLA Replay must NOT appear in the sidebar navigation
  await expect(page.locator("nav").getByText("SLA Replay")).not.toBeVisible();
  await expect(page.locator("nav a[href='/replay']")).toHaveCount(0);
});

test("@smoke ec2-demo-removed: Governance Insights card is absent from Dashboard", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  await expect(page.getByText(/Governance Insights/i)).not.toBeVisible();
});

test("@smoke ec2-demo-removed: 8 Demo Scenarios grid is absent from Dashboard", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  // The scenario grid section header should not appear
  await expect(page.getByText("8 Demo Scenarios")).not.toBeVisible();
});

test("@smoke ec2-demo-removed: Role switcher Viewer button absent from sidebar", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  // Viewer role toggle must not be in the sidebar
  await expect(page.locator("aside").getByText("Viewer")).not.toBeVisible();
  await expect(page.locator("aside").getByRole("button", { name: /Viewer/i })).toHaveCount(0);
});
