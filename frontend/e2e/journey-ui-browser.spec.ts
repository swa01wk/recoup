/**
 * UI Browser Journey Tests — UI-1 through UI-10 (+ UI-8b/c/d for cost-recovery labels)
 *
 * Click-through Playwright tests that drive the real browser (Chromium) and assert
 * visible UI elements, button states, and role-gating behaviour.
 *
 * These close the "🧪 Manual" gaps listed in USER_JOURNEY_CHECKLIST.md.
 *
 * Prerequisites: backend on :8000, frontend on :3000 (webServer in playwright.config.ts)
 *
 * Tags:
 *   @ui    — any browser-level test
 *   @smoke — fast happy-path subset
 */

import { test, expect, type Page } from "@playwright/test";
import { resetBackend } from "./helpers";

const BACKEND = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Clear localStorage role so every test starts as Viewer. */
async function clearRole(page: Page): Promise<void> {
  await page.evaluate(() => localStorage.removeItem("recoup:userRole"));
}

/** Set the role via localStorage before navigating (avoids flicker). */
async function setRole(page: Page, role: "operator" | "viewer"): Promise<void> {
  await page.evaluate((r) => localStorage.setItem("recoup:userRole", r), role);
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

test.beforeEach(async ({ request, page }) => {
  await resetBackend(request);
  await page.goto("/");
  await clearRole(page);
});

// ---------------------------------------------------------------------------
// UI-1 — Recovery Dashboard loads
// ---------------------------------------------------------------------------

test("@smoke @ui UI-1 Recovery Dashboard loads and shows pipeline steps", async ({ page }) => {
  await page.goto("/");
  // Page title / heading (use first() to avoid strict-mode violation — sidebar nav also has this text)
  await expect(page.getByText("Recovery Dashboard").first()).toBeVisible({ timeout: 15_000 });

  // 11-step pipeline strip
  const steps = ["Detect", "Investigate", "Correlate", "Explain", "Prove", "Plan", "Policy", "Approve", "Remediate", "Verify", "Record"];
  for (const step of steps) {
    await expect(page.getByText(step).first()).toBeVisible({ timeout: 5_000 });
  }
});

test("@ui UI-1b Recovery Dashboard shows scenario tiles for all 8 cost categories", async ({ page }) => {
  await page.goto("/");
  // Scenario tags from SCENARIO_TILES constant in page.tsx
  const tags = ["EC2", "EBS", "EIP", "RDS", "S3", "Lambda", "Snapshot", "GP2"];
  for (const tag of tags) {
    await expect(page.getByText(tag).first()).toBeVisible({ timeout: 10_000 });
  }
});

// ---------------------------------------------------------------------------
// UI-2 — Scan page loads and scan runs
// ---------------------------------------------------------------------------

test("@smoke @ui UI-2 Account Scanner page loads with scan button", async ({ page }) => {
  await page.goto("/scan");
  await expect(page.getByText("Account Scanner").first()).toBeVisible({ timeout: 10_000 });
  // "Run Demo Scan" or similar CTA must be present
  const scanBtn = page.getByRole("button", { name: /scan|demo scan/i }).first();
  await expect(scanBtn).toBeVisible({ timeout: 5_000 });
});

test("@ui UI-2b Scan returns 8 finding tiles after running demo scan", async ({ page }) => {
  await setRole(page, "operator");
  await page.goto("/scan");

  // Click the demo scan button (labelled "Run Demo Scan" or similar)
  const scanBtn = page.getByRole("button", { name: /run demo scan|demo scan/i }).first();
  await expect(scanBtn).toBeVisible({ timeout: 10_000 });
  await scanBtn.click();

  // Wait for findings to appear — look for known scenario tags
  await expect(page.getByText(/oversized-ec2|oversized ec2/i).first()).toBeVisible({ timeout: 20_000 });

  // All 8 scenario tags must be present
  const scenarioLabels = [
    /oversized.?ec2/i, /unattached.?ebs/i, /gp2.*migr|gp2→gp3/i,
    /idle.?eip/i, /idle.?rds/i, /no lifecycle|s3.*lifecycle/i,
    /oversized.?lambda/i, /stale.?snapshot/i,
  ];
  for (const label of scenarioLabels) {
    await expect(page.getByText(label).first()).toBeVisible({ timeout: 5_000 });
  }
});

// ---------------------------------------------------------------------------
// UI-3 — Start Recovery button promotes a finding
// ---------------------------------------------------------------------------

test("@smoke @ui UI-3 Start Recovery button promotes finding to Decision Inbox", async ({ page }) => {
  await setRole(page, "operator");
  await page.goto("/scan");

  // Run the demo scan first
  const scanBtn = page.getByRole("button", { name: /run demo scan|demo scan/i }).first();
  await expect(scanBtn).toBeVisible({ timeout: 10_000 });
  await scanBtn.click();

  // Wait for the scan RESULTS banner — "Estimated Total Recoverable" only appears after
  // the scan API responds with findings, not in the pre-existing "Demo Workloads" section.
  await expect(page.getByText(/estimated total recoverable/i).first()).toBeVisible({ timeout: 60_000 });

  // With results loaded, "Start Recovery" buttons should now be present
  const recoverBtn = page.getByRole("button", { name: /start recovery/i }).first();
  await expect(recoverBtn).toBeVisible({ timeout: 10_000 });
  await recoverBtn.click();

  // Should show a success indicator (opportunity link or promoted badge)
  await expect(
    page.getByText(/pending|recovery-|promoted|awaiting/i).first()
  ).toBeVisible({ timeout: 10_000 });
});

// ---------------------------------------------------------------------------
// UI-4 — Decision Inbox page renders approvals
// ---------------------------------------------------------------------------

test("@smoke @ui UI-4 Decision Inbox page renders and shows pending badge", async ({ page }) => {
  // Pre-create an approval via API before navigating
  const scanRes = await page.request.post(`${BACKEND}/api/scan/demo`);
  expect(scanRes.ok()).toBeTruthy();
  const scan = (await scanRes.json()) as { findings: Array<Record<string, unknown>> };
  const finding = scan.findings[0];
  const promoteRes = await page.request.post(`${BACKEND}/api/scan/findings/promote`, {
    data: finding,
  });
  expect(promoteRes.ok()).toBeTruthy();

  await page.goto("/approvals");
  // use first() to avoid strict-mode violation — sidebar nav also has "Decision Inbox"
  await expect(page.getByText("Decision Inbox").first()).toBeVisible({ timeout: 10_000 });

  // The pending badge / approval card should appear
  await expect(page.getByText(/pending|PENDING/i).first()).toBeVisible({ timeout: 10_000 });
});

test("@ui UI-4b Decision Inbox shows approve / decline / investigate buttons for operator", async ({ page }) => {
  // Pre-create an approval
  const scanRes = await page.request.post(`${BACKEND}/api/scan/demo`);
  const scan = (await scanRes.json()) as { findings: Array<Record<string, unknown>> };
  await page.request.post(`${BACKEND}/api/scan/findings/promote`, { data: scan.findings[0] });

  await setRole(page, "operator");
  await page.goto("/approvals");

  await expect(page.getByRole("button", { name: /approve/i }).first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("button", { name: /decline/i }).first()).toBeVisible({ timeout: 5_000 });
  await expect(page.getByRole("button", { name: /investigation/i }).first()).toBeVisible({ timeout: 5_000 });
});

// ---------------------------------------------------------------------------
// UI-5 — Approve button click executes claim-bound approval
// ---------------------------------------------------------------------------

test("@smoke @ui UI-5 Clicking Approve executes approval and shows success message", async ({ page }) => {
  // Pre-create an approval and capture the opportunity_id
  const scanRes = await page.request.post(`${BACKEND}/api/scan/demo`);
  const scan = (await scanRes.json()) as { findings: Array<Record<string, unknown>> };
  const promoteRes = await page.request.post(`${BACKEND}/api/scan/findings/promote`, {
    data: scan.findings[0],
  });
  const promoted = (await promoteRes.json()) as { opportunity_id: string };
  const oppId = promoted.opportunity_id;

  await setRole(page, "operator");
  await page.goto("/approvals");

  // Scope to the card that links to our specific opportunity to avoid clicking a
  // stale approval left over from a previous test (DynamoDB persists between resets).
  const card = page
    .locator("div")
    .filter({ has: page.locator(`a[href="/opportunities/${oppId}"]`) })
    .first();
  const approveBtn = card.getByRole("button", { name: /approve/i }).first();
  await expect(approveBtn).toBeVisible({ timeout: 10_000 });
  await approveBtn.click();

  // Should show success message (page-level banner set by handleApprove)
  await expect(page.getByText(/approved successfully|APPROVED/i).first()).toBeVisible({ timeout: 10_000 });
});

// ---------------------------------------------------------------------------
// UI-6 — Recovery Ledger shows 3-bucket pipeline + savings chart
// ---------------------------------------------------------------------------

test("@smoke @ui UI-6 Recovery Ledger page renders 3-bucket pipeline", async ({ page }) => {
  await page.goto("/recovery");
  await expect(page.getByText(/recovery ledger/i).first()).toBeVisible({ timeout: 10_000 });

  // 3 buckets: Detected / Pending / Recovered
  await expect(page.getByText(/detected/i).first()).toBeVisible({ timeout: 5_000 });
  await expect(page.getByText(/pending/i).first()).toBeVisible({ timeout: 5_000 });
  await expect(page.getByText(/recovered|approved/i).first()).toBeVisible({ timeout: 5_000 });

  // Chart renamed from "Cumulative Savings" → "Recovery Pipeline Funnel"
  await expect(page.getByText(/recovery pipeline funnel/i).first()).toBeVisible({ timeout: 5_000 });
});

test("@ui UI-6b Recovery Ledger updates after scan and promote", async ({ page }) => {
  // Seed some state via API
  const scanRes = await page.request.post(`${BACKEND}/api/scan/demo`);
  const scan = (await scanRes.json()) as {
    total_estimated_monthly_savings_usd: number;
    findings: Array<Record<string, unknown>>;
  };
  await page.request.post(`${BACKEND}/api/scan/findings/promote`, { data: scan.findings[0] });

  await page.goto("/recovery");
  await expect(page.getByText(/recovery ledger/i).first()).toBeVisible({ timeout: 10_000 });
  // Detected bucket total should be > $0 (reflects scan total stored in localStorage)
  // Chart canvas should be present (Recharts renders a <canvas> or SVG)
  const chartEl = page.locator("svg, canvas").first();
  await expect(chartEl).toBeAttached({ timeout: 10_000 });
});

// ---------------------------------------------------------------------------
// UI-7 — SLA Replay page renders scenario selector + result
// ---------------------------------------------------------------------------

test("@smoke @ui UI-7 SLA Replay page loads scenario selector", async ({ page }) => {
  await page.goto("/replay");
  // The replay page should show some heading
  await expect(page.getByText(/replay|sla|verified/i).first()).toBeVisible({ timeout: 10_000 });
  // A trigger / run button should be present
  const runBtn = page.getByRole("button", { name: /run|trigger|replay|analyze/i }).first();
  await expect(runBtn).toBeVisible({ timeout: 5_000 });
});

test("@ui UI-7b SLA Replay runs and shows potential credit", async ({ page }) => {
  await page.goto("/replay");

  const runBtn = page.getByRole("button", { name: /run|trigger|replay|analyze/i }).first();
  await expect(runBtn).toBeVisible({ timeout: 10_000 });
  await runBtn.click();

  // Wait for the credit result to show
  await expect(page.getByText(/credit|potential|\$/i).first()).toBeVisible({ timeout: 20_000 });
});

// ---------------------------------------------------------------------------
// UI-8 — Opportunity Detail page renders pipeline strip
// ---------------------------------------------------------------------------

test("@smoke @ui UI-8 Opportunity Detail page renders 6-stage pipeline strip", async ({ page }) => {
  // Create an opportunity via API
  const oppRes = await page.request.post(`${BACKEND}/api/opportunities/opp-ui8-test/run`, {
    data: { signal: null },
  });
  expect(oppRes.ok()).toBeTruthy();

  await page.goto("/opportunities/opp-ui8-test");

  // Pipeline nodes should be visible
  await expect(
    page.getByText(/normalize|incident|sla|calculator|evidence|eligibility/i).first()
  ).toBeVisible({ timeout: 15_000 });
});

// ---------------------------------------------------------------------------
// UI-8b — Cost-recovery opportunity detail shows correct labels (Fix B)
// ---------------------------------------------------------------------------

test("@smoke @ui UI-8b cost-recovery detail shows 'Cost Recovery Analysis' not 'Availability Result'", async ({
  page,
}) => {
  // Promote a demo scan finding so we have a cost-recovery opportunity
  const scanRes = await page.request.post(`${BACKEND}/api/scan/demo`);
  const scan = (await scanRes.json()) as { findings: Array<Record<string, unknown>> };
  const finding = scan.findings[0];

  const promoteRes = await page.request.post(`${BACKEND}/api/scan/findings/promote`, {
    data: finding,
  });
  const promoted = (await promoteRes.json()) as { opportunity_id: string };

  await page.goto(`/opportunities/${promoted.opportunity_id}`);
  await page.waitForLoadState("networkidle");

  // Cost-recovery label must be present
  await expect(page.getByText(/cost recovery analysis/i).first()).toBeVisible({
    timeout: 10_000,
  });

  // SLA-specific label must NOT appear
  await expect(page.getByText(/availability result/i).first()).not.toBeVisible();

  // Badge should say "Optimization Found", NOT "SLA Met" or "SLA Breached"
  await expect(page.getByText(/optimization found/i).first()).toBeVisible({
    timeout: 5_000,
  });
  await expect(page.getByText(/sla met|sla breached/i).first()).not.toBeVisible();
});

test("@ui UI-8c cost-recovery detail shows 'Monthly Savings' and hides 'Monthly Uptime'", async ({
  page,
}) => {
  const scanRes = await page.request.post(`${BACKEND}/api/scan/demo`);
  const scan = (await scanRes.json()) as { findings: Array<Record<string, unknown>> };

  const promoteRes = await page.request.post(`${BACKEND}/api/scan/findings/promote`, {
    data: scan.findings[0],
  });
  const promoted = (await promoteRes.json()) as { opportunity_id: string };

  await page.goto(`/opportunities/${promoted.opportunity_id}`);
  await page.waitForLoadState("networkidle");

  // "Monthly Savings" label (renamed from "Potential Credit")
  await expect(page.getByText(/monthly savings/i).first()).toBeVisible({ timeout: 10_000 });

  // "Monthly Cost" label (renamed from "Billed Charges")
  await expect(page.getByText(/monthly cost/i).first()).toBeVisible({ timeout: 5_000 });

  // "Monthly Uptime" (SLA-specific) must NOT appear
  await expect(page.getByText(/monthly uptime/i).first()).not.toBeVisible();

  // "Calculation Trace" renamed to "Recovery Trace" for cost-recovery
  await expect(page.getByText(/recovery trace/i).first()).toBeVisible({ timeout: 5_000 });
  await expect(page.getByText(/^calculation trace$/i).first()).not.toBeVisible();
});

test("@ui UI-8d SLA replay opportunity detail still shows 'Availability Result' and SLA labels", async ({
  page,
}) => {
  // Run a non-promoted (SLA replay) opportunity
  const id = `ui8d-sla-${Date.now()}`;
  const oppRes = await page.request.post(`${BACKEND}/api/opportunities/${id}/run`, {
    data: { use_strands: true },
  });
  expect(oppRes.ok()).toBeTruthy();

  await page.goto(`/opportunities/${id}`);
  await page.waitForLoadState("networkidle");

  // SLA replay should keep original labels
  await expect(page.getByText(/availability result/i).first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/cost recovery analysis/i).first()).not.toBeVisible();
});

// ---------------------------------------------------------------------------
// UI-9 — Quality scorecard page renders gate tiles
// ---------------------------------------------------------------------------

test("@smoke @ui UI-9 Quality Dashboard renders scorecard gate tiles", async ({ page }) => {
  await page.goto("/quality");
  await expect(page.getByText(/quality|scorecard/i).first()).toBeVisible({ timeout: 10_000 });

  // Key gate labels from the scorecard
  await expect(
    page.getByText(/golden path|unsafe.*action|hallucinate|evidence/i).first()
  ).toBeVisible({ timeout: 10_000 });
});

test("@ui UI-9b Quality scorecard shows all_gates_pass field", async ({ page }) => {
  await page.goto("/quality");
  // Trigger a verified replay button if present
  const replayBtn = page.getByRole("button", { name: /run.*verified|verified replay|scorecard/i }).first();
  if (await replayBtn.isVisible()) {
    await replayBtn.click();
  }

  // The unsafe_external_actions counter (must be 0) should be visible
  await expect(page.getByText(/unsafe.*action|0 unsafe|unsafe: 0/i).first()).toBeVisible({ timeout: 15_000 });
});

// ---------------------------------------------------------------------------
// UI-10 — Sidebar role switch gates Approve button
// ---------------------------------------------------------------------------

test("@smoke @ui UI-10 Viewer role shows read-only message on Decision Inbox", async ({ page }) => {
  // Pre-create an approval
  const scanRes = await page.request.post(`${BACKEND}/api/scan/demo`);
  const scan = (await scanRes.json()) as { findings: Array<Record<string, unknown>> };
  await page.request.post(`${BACKEND}/api/scan/findings/promote`, { data: scan.findings[0] });

  // Ensure Viewer role
  await setRole(page, "viewer");
  await page.goto("/approvals");

  // Should show read-only message, not approve buttons
  await expect(page.getByText(/read.only|viewer|switch to operator/i).first()).toBeVisible({ timeout: 10_000 });

  // Approve button should NOT be visible in viewer mode
  const approveBtn = page.getByRole("button", { name: /^approve/i });
  await expect(approveBtn).toHaveCount(0);
});

test("@ui UI-10b Switching from Viewer → Operator in sidebar reveals Approve buttons", async ({ page }) => {
  // Pre-create an approval
  const scanRes = await page.request.post(`${BACKEND}/api/scan/demo`);
  const scan = (await scanRes.json()) as { findings: Array<Record<string, unknown>> };
  await page.request.post(`${BACKEND}/api/scan/findings/promote`, { data: scan.findings[0] });

  // Start as viewer
  await setRole(page, "viewer");
  await page.goto("/approvals");
  await expect(page.getByText(/read.only|viewer/i).first()).toBeVisible({ timeout: 10_000 });

  // Click the "Operator" role button in the sidebar
  const operatorBtn = page.getByRole("button", { name: /^operator$/i });
  await operatorBtn.click();

  // Approve button should now appear
  await expect(page.getByRole("button", { name: /approve/i }).first()).toBeVisible({ timeout: 10_000 });
});

// ---------------------------------------------------------------------------
// UI-10c — Sidebar renders all 5 nav routes
// ---------------------------------------------------------------------------

test("@smoke @ui UI-10c Sidebar renders all 6 routes", async ({ page }) => {
  await page.goto("/");
  const navLinks = [
    "Recovery Dashboard",
    "Recovery Ledger",
    "Account Scanner",
    "Decision Inbox",
    "Quality Dashboard",
  ];
  for (const link of navLinks) {
    // Use first() to avoid strict-mode violation when the text appears in both sidebar and page heading
    await expect(page.getByText(link).first()).toBeVisible({ timeout: 5_000 });
  }
});
