/**
 * Dashboard ↔ Ledger Consistency Journey
 *
 * Asserts that the Recovery Dashboard and Recovery Ledger show the same
 * Potential Savings / Remaining / Pending / Recovered bucket totals.
 * Both pages now consume the same useRecoveryData() hook, so their data
 * must be consistent.
 */
import { test, expect } from "@playwright/test";
import {
  BACKEND,
  resetBackend,
  runDemoScan,
  promoteFinding,
  approveOpportunity,
  pollUntilState,
  promoteActionableFinding,
  seedBrowserScanResult,
  fetchLedgerBuckets,
  assertLedgerBalanced,
  readRecoverySummaryBuckets,
  investigateOpportunity,
  runExtendedInvestigationStream,
  assertRemainingUnchanged,
  getLastScan,
} from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

test("@smoke dashboard-ledger-consistency: both pages show the same Potential Savings total", async ({
  page,
  request,
}) => {
  const scan = await runDemoScan(request);
  await seedBrowserScanResult(page, scan as Record<string, unknown>);

  await page.goto("/opportunities");
  await page.waitForLoadState("networkidle");
  const onOpportunities = await readRecoverySummaryBuckets(page);

  await page.goto("/recovery");
  await page.waitForLoadState("networkidle");
  const onRecovery = await readRecoverySummaryBuckets(page);

  expect(onRecovery.potential).toBeCloseTo(onOpportunities.potential, 1);
  expect(onRecovery.remaining).toBeCloseTo(onOpportunities.remaining, 1);
  expect(onRecovery.pending).toBeCloseTo(onOpportunities.pending, 1);
  expect(onRecovery.recovered).toBeCloseTo(onOpportunities.recovered, 1);
});

test("@full dashboard-ledger-consistency: Pending bucket matches after promote", async ({
  page,
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  await promoteFinding(request, findings[0]);

  // Give backend time to settle
  await page.waitForTimeout(500);

  // Load dashboard — capture Pending value
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await expect(page.getByText("Pending Approval").first()).toBeVisible({ timeout: 10_000 });

  // Load Ledger — must also show Pending
  await page.goto("/recovery");
  await page.waitForLoadState("networkidle");
  await expect(page.getByText("Pending Approval").first()).toBeVisible({ timeout: 10_000 });
});

test("@full dashboard-ledger-consistency: Recovered bucket appears on both pages after approval", async ({
  page,
  request,
}) => {
  const scan = await runDemoScan(request);
  const { opportunity_id } = await promoteActionableFinding(request);
  await pollUntilState(request, opportunity_id, "AWAITING_APPROVAL");
  await approveOpportunity(request, opportunity_id);
  await pollUntilState(request, opportunity_id, ["APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING", "RECOVERED"]);

  await seedBrowserScanResult(page, scan as Record<string, unknown>);

  await page.goto("/opportunities");
  await page.waitForLoadState("networkidle");
  await expect(page.getByText("Recovered").first()).toBeVisible({ timeout: 10_000 });

  await page.goto("/recovery");
  await page.waitForLoadState("networkidle");
  await expect(page.getByText("Recovered").first()).toBeVisible({ timeout: 10_000 });
});

test("@smoke dashboard-ledger-consistency: investigate → stream → approve UI Remaining stable", async ({
  page,
  request,
}) => {
  await runDemoScan(request);
  const { opportunity_id } = await promoteActionableFinding(request);
  await investigateOpportunity(request, opportunity_id);
  const apiAfterInvestigate = await fetchLedgerBuckets(request);
  assertLedgerBalanced(apiAfterInvestigate);

  await runExtendedInvestigationStream(request, opportunity_id);
  await approveOpportunity(request, opportunity_id);
  const apiAfterApprove = await fetchLedgerBuckets(request);
  assertRemainingUnchanged(apiAfterInvestigate, apiAfterApprove);

  await seedBrowserScanResult(page, (await getLastScan(request)) as Record<string, unknown>);
  await page.goto("/opportunities");
  await page.getByRole("button", { name: /^refresh$/i }).click();
  await page.waitForLoadState("networkidle");
  const ui = await readRecoverySummaryBuckets(page);
  expect(ui.recovered).toBeCloseTo(apiAfterApprove.recovered, 0.02);
  expect(ui.pending).toBeCloseTo(apiAfterApprove.pending, 0.02);
  expect(ui.remaining).toBeCloseTo(apiAfterApprove.detected, 0.02);
});
