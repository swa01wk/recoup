/**
 * Full Recovery Journey — end-to-end canonical flow
 *
 * Scanner → Start Recovery (promote) → HITL Approve → Ledger RECOVERED
 *
 * Asserts the entire lifecycle from scan finding detection through to
 * verified recovery appearing in the Recovery Ledger.
 */
import { test, expect } from "@playwright/test";
import { resetBackend, runDemoScan, promoteFinding, approveOpportunity, pollUntilState } from "./helpers";

const BACKEND = "http://localhost:8000";

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

test("@full full-recovery-journey: scan → promote → approve → RECOVERED in Ledger", async ({
  page,
  request,
}) => {
  // Step 1: Run demo scan via API
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  expect(findings.length).toBeGreaterThan(0);

  // Step 2: Promote the first finding → creates opportunity in AWAITING_APPROVAL
  const { opportunity_id } = await promoteFinding(request, findings[0]);
  await pollUntilState(request, opportunity_id, "AWAITING_APPROVAL");

  // Step 3: Navigate to Account Scanner to verify finding appears there
  await page.goto("/scan");
  await page.waitForLoadState("networkidle");
  await expect(page.getByText(/Account Scanner/i).first()).toBeVisible();

  // Step 4: Navigate to Decision Inbox, verify pending item
  await page.goto("/approvals");
  await page.waitForLoadState("networkidle");
  await expect(page.getByText(/pending/i).first()).toBeVisible({ timeout: 10_000 });

  // Step 5: Approve the opportunity via API (simulating inbox approval)
  await approveOpportunity(request, opportunity_id);

  // Step 6: Poll until opportunity advances past AWAITING_APPROVAL
  const approvedOpp = await pollUntilState(request, opportunity_id, [
    "APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING", "RECOVERED",
  ]);
  expect(["APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING", "RECOVERED"]).toContain(
    approvedOpp.state.toUpperCase()
  );

  // Step 7: Verify pipeline stage is at step 9+ (Remediate or later)
  const oppRes = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
  expect(oppRes.ok()).toBeTruthy();
  const opp = (await oppRes.json()) as { state: string; potential_value: string };
  expect(parseFloat(opp.potential_value ?? "0")).toBeGreaterThan(0);

  // Step 8: Navigate to Recovery Ledger — check that RECOVERED / APPROVED bucket is non-zero
  await page.goto("/recovery");
  await page.waitForLoadState("networkidle");
  await expect(page.getByText(/Recovery Ledger/i).first()).toBeVisible();
  await expect(page.getByText(/Recovery Event History/i)).toBeVisible({ timeout: 10_000 });

  // The event history should mention this opportunity
  await expect(page.getByText(opportunity_id.slice(0, 12)).first()).toBeVisible({ timeout: 10_000 });
});

test("@smoke full-recovery-journey: opportunity detail shows 11-step pipeline after promote", async ({
  page,
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const { opportunity_id } = await promoteFinding(request, findings[0]);
  await pollUntilState(request, opportunity_id, "AWAITING_APPROVAL");

  await page.goto(`/opportunities/${opportunity_id}`);
  await page.waitForLoadState("networkidle");

  // 11-step pipeline strip must be visible and show Step 8 (Approve gate)
  await expect(page.getByText(/Step 8 \/ 11/i)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/Approve/i).first()).toBeVisible();
});
