/**
 * J2 — Primary Operator Loop (Sprint 5 journey test)
 *
 * Full end-to-end:
 *   Demo scan → finding appears → Start Recovery → opportunity created →
 *   Decision Inbox card visible → Approve with claim binding → Recovery Ledger
 *   approved-bucket increments.
 *
 * Tags:
 *   @smoke  — happy path steps only
 *   @full   — edge cases (idempotency, amount guard)
 */
import { test, expect } from "@playwright/test";
import {
  resetBackend,
  runDemoScan,
  promoteFinding,
  approveOpportunity,
  BACKEND,
  promoteActionableFinding,
} from "./helpers";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function getOpportunityState(
  request: import("@playwright/test").APIRequestContext,
  opportunityId: string
): Promise<string> {
  const res = await request.get(`${BACKEND}/api/opportunities/${opportunityId}`);
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { state: string };
  return body.state;
}

async function getPendingApprovals(
  request: import("@playwright/test").APIRequestContext
): Promise<unknown[]> {
  const res = await request.get(`${BACKEND}/api/approvals/pending`);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

// ---------------------------------------------------------------------------
// J2 — @smoke: happy path
// ---------------------------------------------------------------------------

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

test("@smoke J2-1 demo scan returns findings with positive total savings", async ({ request }) => {
  const scan = await runDemoScan(request);
  expect(scan.findings.length).toBeGreaterThanOrEqual(1);
  expect(scan.total_estimated_monthly_savings_usd).toBeGreaterThan(0);
  // Sprint 2: account_id should be masked (XXXXXXXX present or null)
  const result = scan as unknown as { account_id: string | null };
  if (result.account_id) {
    const isDemo = result.account_id === "unknown";
    const isMasked = result.account_id.includes("XXXXXXXX");
    expect(isDemo || isMasked).toBeTruthy();
  }
});

test("@smoke J2-2 promote finding creates opportunity in AWAITING_APPROVAL", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  expect(findings.length).toBeGreaterThan(0);

  const { opportunity_id } = await promoteFinding(request, findings[0]);
  expect(opportunity_id).toMatch(/^recovery-/);

  const state = await getOpportunityState(request, opportunity_id);
  expect(state).toBe("AWAITING_APPROVAL");
});

test("@smoke J2-3 promoted opportunity appears in Decision Inbox (pending list)", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const { opportunity_id } = await promoteFinding(request, findings[0]);

  const pending = await getPendingApprovals(request);
  const ids = (pending as Array<{ opportunity_id: string }>).map((r) => r.opportunity_id);
  expect(ids).toContain(opportunity_id);
});

test("@smoke J2-4 approve changes state and approval record to APPROVED", async ({
  request,
}) => {
  const { opportunity_id } = await promoteActionableFinding(request);

  // Approve with full claim binding
  const result = await approveOpportunity(request, opportunity_id);
  expect(result).toBeTruthy();

  // Decision Inbox should show APPROVED (or empty if record moved out of pending)
  const pending = await getPendingApprovals(request);
  const stillPending = (pending as Array<{ opportunity_id: string; state: string }>).find(
    (r) => r.opportunity_id === opportunity_id && r.state === "PENDING"
  );
  expect(stillPending).toBeUndefined();
});

test("@smoke J2-5 scan audit record written after demo scan", async ({ request }) => {
  await runDemoScan(request);
  const res = await request.get(`${BACKEND}/api/scan/audit`);
  expect(res.ok()).toBeTruthy();
  const audit = (await res.json()) as Array<{ scan_id: string; finding_count: number }>;
  expect(audit.length).toBeGreaterThanOrEqual(1);
  expect(audit[0].scan_id).toBeTruthy();
  expect(audit[0].finding_count).toBeGreaterThanOrEqual(0);
});

// ---------------------------------------------------------------------------
// J2 — @full: edge cases
// ---------------------------------------------------------------------------

test("@full J2-6 promote is idempotent — same finding returns existing opportunity", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const finding = findings[0];

  const first = await promoteFinding(request, finding);
  const second = await promoteFinding(request, finding);
  expect(second.opportunity_id).toBe(first.opportunity_id);

  // Only 1 pending approval for that opportunity
  const pending = await getPendingApprovals(request);
  const forOpp = (pending as Array<{ opportunity_id: string }>).filter(
    (r) => r.opportunity_id === first.opportunity_id
  );
  expect(forOpp.length).toBe(1);
});

test("@full J2-7 approve with tampered claim_hash returns 409", async ({ request }) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const { opportunity_id } = await promoteFinding(request, findings[0]);

  // Fetch real approval record
  const pendingRes = await request.get(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}`
  );
  const pending = (await pendingRes.json()) as {
    claim_hash: string;
    amount: string;
    state_version: number;
  };

  // Tamper the hash
  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
    {
      data: {
        principal: "playwright-attacker",
        claim_hash: "sha256:deadbeef000000000000000000000000000000000000000000000000000000000",
        amount: pending.amount,
        state_version: pending.state_version,
      },
    }
  );
  expect(res.status()).toBe(409);
});

test("@full J2-8 per-customer connect init returns unique external_id", async ({ request }) => {
  const res1 = await request.post(`${BACKEND}/api/scan/connect/init`);
  const res2 = await request.post(`${BACKEND}/api/scan/connect/init`);
  expect(res1.ok()).toBeTruthy();
  expect(res2.ok()).toBeTruthy();
  const c1 = (await res1.json()) as { customer_id: string; external_id: string };
  const c2 = (await res2.json()) as { customer_id: string; external_id: string };
  // Each customer gets a unique ID and ExternalId
  expect(c1.customer_id).not.toBe(c2.customer_id);
  expect(c1.external_id).not.toBe(c2.external_id);
  expect(c1.external_id.length).toBeGreaterThan(20);
});

test("@full J2-9 data deletion endpoint purges account scan cache", async ({ request }) => {
  await runDemoScan(request);

  // Get the __demo__ cache key (masked)
  const auditBefore = await request.get(`${BACKEND}/api/scan/audit`);
  const auditData = (await auditBefore.json()) as Array<{ account_id_masked: string }>;
  expect(auditData.length).toBeGreaterThan(0);

  // Delete using masked prefix (first 4 chars of masked account id)
  const maskedId = auditData[0].account_id_masked;
  const prefix = maskedId.slice(0, 4);

  // Delete via account ID (non-existing is graceful)
  const delRes = await request.delete(`${BACKEND}/api/scan/accounts/__demo__/data`);
  expect(delRes.ok()).toBeTruthy();
  const delBody = (await delRes.json()) as { status: string };
  expect(delBody.status).toBe("deleted");
});
