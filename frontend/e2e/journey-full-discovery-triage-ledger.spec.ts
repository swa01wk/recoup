/**
 * Full operator E2E — reset → Account Scanner → 3 distinct services →
 * approve / investigate / decline → Recovery Ledger + SNS outcomes.
 *
 * Tags: @e2e @smoke (mega journey) · @full (API guard tests)
 */
import { test, expect, type Page } from "@playwright/test";
import {
  BACKEND,
  resetBackend,
  pickFindingsByDistinctServices,
  getLastScan,
  listOutcomes,
  outcomeForOpportunity,
  getOpportunity,
  fetchLedgerBuckets,
  assertLedgerBalanced,
  runDemoScanFromUiOrSeed,
  syncScanToBrowser,
  startRecoveryFromOpportunitiesList,
  promoteFinding,
  promoteActionableFinding,
  approveOpportunity,
  investigateOpportunity,
  declineOpportunity,
  runExtendedInvestigationStream,
  assertRemainingUnchanged,
  detailApproveButton,
  detailApproveConfirmButton,
  type ScanFinding,
} from "./helpers";

function opportunityIdFromUrl(page: Page): string {
  const match = page.url().match(/\/opportunities\/([^/?#]+)/);
  if (!match?.[1]) {
    throw new Error(`No opportunity id in URL: ${page.url()}`);
  }
  return match[1];
}

async function clickApproveAndCaptureSns(page: Page): Promise<boolean> {
  const approveBtn = detailApproveButton(page);
  await expect(approveBtn).toBeVisible({ timeout: 15_000 });
  await approveBtn.scrollIntoViewIfNeeded();

  const responsePromise = page.waitForResponse(
    (r) =>
      r.url().includes("/api/approvals/opportunity/") &&
      r.url().includes("/approve") &&
      r.request().method() === "POST" &&
      r.status() === 200,
    { timeout: 30_000 }
  );

  await approveBtn.click();
  const confirmBtn = detailApproveConfirmButton(page);
  await expect(confirmBtn).toBeVisible({ timeout: 5_000 });
  await confirmBtn.click();
  const response = await responsePromise;
  const body = (await response.json()) as { sns_notification_sent?: boolean };
  return body.sns_notification_sent === true;
}

async function clickInvestigate(page: Page): Promise<void> {
  const btn = page.getByRole("button", { name: /investigate further/i });
  await expect(btn).toBeVisible({ timeout: 15_000 });
  const responsePromise = page.waitForResponse(
    (r) => r.url().includes("/investigate") && r.request().method() === "POST",
    { timeout: 30_000 }
  );
  await btn.click();
  await responsePromise;
}

async function clickDecline(page: Page): Promise<void> {
  const btn = page.getByRole("button", { name: /^decline$/i });
  await expect(btn).toBeVisible({ timeout: 15_000 });
  const responsePromise = page.waitForResponse(
    (r) => r.url().includes("/decline") && r.request().method() === "POST",
    { timeout: 30_000 }
  );
  await btn.click();
  await responsePromise;
}

// ---------------------------------------------------------------------------
// Single browser session — full closed loop (scan → 3 triage paths → ledger)
// ---------------------------------------------------------------------------

test("@smoke @e2e full journey — scan, 3 services, approve / investigate / decline, SNS, ledger", async ({
  page,
  request,
}) => {
  test.setTimeout(420_000);

  await resetBackend(request);
  await runDemoScanFromUiOrSeed(page, request);

  const scan = await getLastScan(request);
  expect(scan.findings.length).toBeGreaterThanOrEqual(3);
  expect(scan.total_estimated_monthly_savings_usd).toBeGreaterThan(0);

  const auditRes = await request.get(`${BACKEND}/api/scan/audit`);
  expect(auditRes.ok()).toBeTruthy();
  const audit = (await auditRes.json()) as Array<{ finding_count: number }>;
  expect(audit[0]?.finding_count).toBeGreaterThanOrEqual(3);

  const trio = pickFindingsByDistinctServices(scan.findings, 3);
  expect(trio.length).toBe(3);
  expect(new Set(trio.map((f) => f.service)).size).toBe(3);

  const [approveFinding, investigateFinding, declineFinding] = trio;
  const approveSavings = Number(approveFinding.estimated_monthly_savings_usd ?? 0);
  const investigateSavings = Number(investigateFinding.estimated_monthly_savings_usd ?? 0);

  await syncScanToBrowser(page, request);

  // —— Service 1: Start Recovery → Approve → SNS ——
  await startRecoveryFromOpportunitiesList(page, approveFinding);
  const approveOppId = opportunityIdFromUrl(page);
  await expect(page.getByText(/approval required/i).first()).toBeVisible({ timeout: 15_000 });
  expect(await clickApproveAndCaptureSns(page)).toBe(true);
  await page.waitForURL(/\/recovery/, { timeout: 25_000 }).catch(() => undefined);

  const approveOpp = await getOpportunity(request, approveOppId);
  expect(["APPROVED", "RECOVERED", "SUBMITTING", "SUBMITTED", "MONITORING"]).toContain(
    approveOpp.state.toUpperCase()
  );
  expect(outcomeForOpportunity(await listOutcomes(request), approveOppId)?.sns_sent).toBe(true);

  const ledgerAfterApprove = await fetchLedgerBuckets(request);
  assertLedgerBalanced(ledgerAfterApprove);
  expect(ledgerAfterApprove.recovered).toBeGreaterThanOrEqual(approveSavings - 0.02);

  // —— Service 2: Start Recovery → Investigate Further (no SNS) ——
  await syncScanToBrowser(page, request);
  await startRecoveryFromOpportunitiesList(page, investigateFinding);
  const investigateOppId = opportunityIdFromUrl(page);
  await expect(page.getByText(/approval required/i).first()).toBeVisible({ timeout: 15_000 });
  await clickInvestigate(page);
  await expect(
    page.getByText(/investigation|investigate further|under investigation/i).first()
  ).toBeVisible({ timeout: 15_000 });

  const investigateOpp = await getOpportunity(request, investigateOppId);
  expect(investigateOpp.state.toUpperCase()).toBe("NEEDS_FOLLOWUP");
  expect(outcomeForOpportunity(await listOutcomes(request), investigateOppId)?.sns_sent).not.toBe(
    true
  );

  const ledgerAfterInvestigate = await fetchLedgerBuckets(request);
  assertLedgerBalanced(ledgerAfterInvestigate);
  if (investigateSavings > 0) {
    expect(ledgerAfterInvestigate.pending).toBeGreaterThanOrEqual(investigateSavings - 0.02);
  }
  expect(ledgerAfterInvestigate.recovered).toBeGreaterThanOrEqual(ledgerAfterApprove.recovered - 0.02);

  // —— Service 3: Start Recovery → Decline (no SNS) ——
  await syncScanToBrowser(page, request);
  await startRecoveryFromOpportunitiesList(page, declineFinding);
  const declineOppId = opportunityIdFromUrl(page);
  await expect(page.getByText(/approval required/i).first()).toBeVisible({ timeout: 15_000 });
  await clickDecline(page);
  await expect(page.getByText(/declined/i).first()).toBeVisible({ timeout: 15_000 });

  const declineOpp = await getOpportunity(request, declineOppId);
  expect(["DECLINED", "DENIED"]).toContain(declineOpp.state.toUpperCase());
  expect(outcomeForOpportunity(await listOutcomes(request), declineOppId)?.sns_sent).not.toBe(
    true
  );

  // —— Promoted list + ledger invariants ——
  const promotedRes = await request.get(`${BACKEND}/api/scan/findings/promoted`);
  const promoted = (await promotedRes.json()) as Array<{ opportunity_id: string }>;
  const promotedIds = promoted.map((p) => p.opportunity_id);
  expect(promotedIds).toEqual(expect.arrayContaining([approveOppId, investigateOppId, declineOppId]));

  const ledger = await fetchLedgerBuckets(request);
  assertLedgerBalanced(ledger);
  expect(ledger.recovered).toBeGreaterThan(0);
  if (approveSavings > 0) {
    expect(ledger.recovered).toBeGreaterThanOrEqual(approveSavings - 0.02);
  }
  if (investigateSavings > 0) {
    expect(ledger.pending).toBeGreaterThanOrEqual(investigateSavings - 0.02);
  }
  expect(ledger.recovered).toBeLessThanOrEqual(ledger.totalDetected + 0.02);
  expect(ledger.pending).toBeLessThanOrEqual(ledger.totalDetected + 0.02);

  await page.goto("/recovery");
  await expect(page.getByText(/recovery ledger/i).first()).toBeVisible({ timeout: 15_000 });
  for (const label of [/potential savings/i, /remaining/i, /pending approval/i, /recovered/i]) {
    await expect(page.getByText(label).first()).toBeVisible({ timeout: 10_000 });
  }
  await expect(page.getByText(/\$\d+\.\d{2}/).first()).toBeVisible({ timeout: 10_000 });
});

// ---------------------------------------------------------------------------
// API-only guards (fast regression for SNS + ledger on triage paths)
// ---------------------------------------------------------------------------

test.describe("Triage API guards @full @e2e", () => {
  test.beforeEach(async ({ request }) => {
    await resetBackend(request);
  });

  test("@full approve path sets sns_notification_sent and outcome sns_sent", async ({
    request,
  }) => {
    await runDemoScanHelper(request);
    const { opportunity_id } = await promoteActionableFinding(request);

    const result = await approveOpportunity(request, opportunity_id);
    expect(result["sns_notification_sent"]).toBe(true);

    const outcomes = await listOutcomes(request);
    expect(outcomeForOpportunity(outcomes, opportunity_id)?.sns_sent).toBe(true);

    const ledger = await fetchLedgerBuckets(request);
    expect(ledger.recovered).toBeGreaterThan(0);
  });

  test("@full investigate path does not send SNS", async ({ request }) => {
    await runDemoScanHelper(request);
    const scan = await getLastScan(request);
    const [finding] = pickFindingsByDistinctServices(scan.findings, 1);
    const { opportunity_id } = await promoteFinding(request, finding);

    const data = await investigateOpportunity(request, opportunity_id);
    expect(data["opportunity_state"]).toBe("NEEDS_FOLLOWUP");
    expect(data["sns_notification_sent"]).toBeUndefined();

    const outcomes = await listOutcomes(request);
    expect(outcomeForOpportunity(outcomes, opportunity_id)?.sns_sent).not.toBe(true);

    const afterInvestigate = await fetchLedgerBuckets(request);
    assertLedgerBalanced(afterInvestigate);
    expect(afterInvestigate.pending).toBeGreaterThan(0);
  });

  test("@full investigate → stream → approve keeps Remaining stable (no double deduct)", async ({
    request,
  }) => {
    await runDemoScanHelper(request);
    const { opportunity_id } = await promoteActionableFinding(request);

    await investigateOpportunity(request, opportunity_id);
    const afterInvestigate = await fetchLedgerBuckets(request);
    assertLedgerBalanced(afterInvestigate);

    await runExtendedInvestigationStream(request, opportunity_id);
    await approveOpportunity(request, opportunity_id);

    const afterApprove = await fetchLedgerBuckets(request);
    assertRemainingUnchanged(afterInvestigate, afterApprove);
    assertLedgerBalanced(afterApprove);
    expect(afterApprove.recovered).toBeGreaterThan(0);
    expect(afterApprove.pending).toBeLessThan(0.02);
  });

  test("@full decline path does not send SNS and stays out of recovered bucket", async ({
    request,
  }) => {
    await runDemoScanHelper(request);
    const scan = await getLastScan(request);
    const [finding] = pickFindingsByDistinctServices(scan.findings, 1);
    const { opportunity_id } = await promoteFinding(request, finding);

    await declineOpportunity(request, opportunity_id);

    const opp = await getOpportunity(request, opportunity_id);
    expect(["DECLINED", "DENIED"]).toContain(opp.state.toUpperCase());

    const ledger = await fetchLedgerBuckets(request);
    assertLedgerBalanced(ledger);
    expect(ledger.recovered).toBe(0);
  });
});

async function runDemoScanHelper(
  request: import("@playwright/test").APIRequestContext
): Promise<void> {
  const res = await request.post(`${BACKEND}/api/scan/demo`);
  expect(res.ok()).toBeTruthy();
}
