/**
 * Scan Idempotency Journey
 *
 * Verifies that running the demo scan twice does not create duplicate
 * opportunities and does not increase the opportunity count.
 */
import { test, expect } from "@playwright/test";
import { BACKEND, resetBackend, runDemoScan, promoteFinding } from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

test("@smoke scan-idempotency: running demo scan twice does not duplicate findings", async ({
  request,
}) => {
  // First scan
  const scan1 = await runDemoScan(request);
  const findingCount1 = (scan1.findings as unknown[]).length;
  expect(findingCount1).toBeGreaterThan(0);

  // Second scan — should return same data (cached)
  const scan2 = await runDemoScan(request);
  const findingCount2 = (scan2.findings as unknown[]).length;

  // Finding count must be identical — no duplicates
  expect(findingCount2).toBe(findingCount1);
});

test("@smoke scan-idempotency: promoting the same finding twice returns the same opportunity_id", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const finding = findings[0];

  const res1 = await request.post(`${BACKEND}/api/scan/findings/promote`, { data: finding });
  const data1 = (await res1.json()) as { opportunity_id: string; status: string };

  const res2 = await request.post(`${BACKEND}/api/scan/findings/promote`, { data: finding });
  const data2 = (await res2.json()) as { opportunity_id: string; status: string };

  // Same opportunity_id returned
  expect(data2.opportunity_id).toBe(data1.opportunity_id);
  // Second call returns "existing" status
  expect(data2.status).toBe("existing");
});

test("@smoke scan-idempotency: opportunity count stays same after second scan + re-promote", async ({
  request,
}) => {
  // Promote first finding from first scan
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  await promoteFinding(request, findings[0]);

  // Get opportunity count
  const oppsBefore = (await (await request.get(`${BACKEND}/api/opportunities`)).json()) as unknown[];
  const countBefore = oppsBefore.length;

  // Run scan again + re-promote same finding
  await runDemoScan(request);
  await request.post(`${BACKEND}/api/scan/findings/promote`, { data: findings[0] });

  // Opportunity count must not increase
  const oppsAfter = (await (await request.get(`${BACKEND}/api/opportunities`)).json()) as unknown[];
  expect(oppsAfter.length).toBe(countBefore);
});

test("@smoke scan-idempotency: Dashboard totals unchanged after second scan", async ({
  page,
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  await promoteFinding(request, findings[0]);

  // Load dashboard
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  // Capture a reference number visible in the ledger strip
  const ledgerText = await page.locator("text=/\\$[0-9]+\\.[0-9]+\\/mo/").first().textContent();

  // Run second scan
  await runDemoScan(request);

  // Reload and verify ledger strip shows same amount (within tolerance)
  await page.reload();
  await page.waitForLoadState("networkidle");
  const ledgerText2 = await page.locator("text=/\\$[0-9]+\\.[0-9]+\\/mo/").first().textContent();

  // Values should be the same (idempotent)
  expect(ledgerText2).toBe(ledgerText);
});
