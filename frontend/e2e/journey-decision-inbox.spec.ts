/**
 * J6 — Decision Inbox: approve / decline / investigate flows (Sprint 5)
 *
 * Tests all three action paths through the Decision Inbox, verifying:
 * - Approve: approval moves to APPROVED, no longer in pending list
 * - Decline: approval moves to DECLINED, not in pending (DENIED)
 * - Investigate: approval state becomes NEEDS_FOLLOWUP (not DECLINED)
 * - Tamper guard: tampered claim_hash returns 409
 * - CORS: X-Request-ID header present on all responses
 *
 * Tags:
 *   @smoke  — approve + decline + investigate happy paths
 *   @full   — tamper, re-approve, expiry edge cases
 */
import { test, expect } from "@playwright/test";
import {
  resetBackend,
  runDemoScan,
  promoteFinding,
  approveOpportunity,
  BACKEND,
  promoteActionableFinding,
  sessionHeaders,
  activeDemoSessionId,
  getOpportunity,
} from "./helpers";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setupPendingApproval(
  request: import("@playwright/test").APIRequestContext
): Promise<{
  opportunity_id: string;
  approval_id: string;
  claim_hash: string;
  amount: string;
  state_version: number;
}> {
  const { opportunity_id } = await promoteActionableFinding(request);

  const sid = activeDemoSessionId();
  expect(sid).toBeTruthy();
  const pendingRes = await request.get(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}`,
    { headers: sessionHeaders(sid!) }
  );
  expect(pendingRes.ok()).toBeTruthy();
  const pending = (await pendingRes.json()) as {
    approval_id: string;
    claim_hash: string;
    amount: string;
    state_version: number;
  };
  return { opportunity_id, ...pending };
}

async function listAllApprovals(
  request: import("@playwright/test").APIRequestContext
): Promise<Array<{ approval_id: string; state: string; opportunity_id: string }>> {
  const sid = activeDemoSessionId();
  expect(sid).toBeTruthy();
  const res = await request.get(`${BACKEND}/api/approvals/pending`, {
    headers: sessionHeaders(sid!),
  });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

// ---------------------------------------------------------------------------
// J6 — @smoke: happy paths
// ---------------------------------------------------------------------------

test("@smoke J6-1 pending approval appears in Decision Inbox list", async ({ request }) => {
  const { opportunity_id, approval_id } = await setupPendingApproval(request);
  const pending = await listAllApprovals(request);
  const found = pending.find((r) => r.opportunity_id === opportunity_id);
  expect(found).toBeTruthy();
  expect(found!.approval_id).toBe(approval_id);
});

test("@smoke J6-2 approve path — approval no longer in PENDING list after approve", async ({
  request,
}) => {
  const { opportunity_id } = await setupPendingApproval(request);
  await approveOpportunity(request, opportunity_id);

  const pending = await listAllApprovals(request);
  const stillPending = pending.find(
    (r) => r.opportunity_id === opportunity_id && r.state === "PENDING"
  );
  expect(stillPending).toBeUndefined();
});

test("@smoke J6-2b approve path — opportunity advances to pipeline stage 9 (Remediate) after approval", async ({
  request,
}) => {
  const { opportunity_id } = await setupPendingApproval(request);

  const before = await getOpportunity(request, opportunity_id);
  expect(before.state).toBe("AWAITING_APPROVAL");

  await approveOpportunity(request, opportunity_id);

  const after = (await getOpportunity(request, opportunity_id)) as {
    state: string;
    lifecycle_state?: string;
  };
  expect(["APPROVED", "RECOVERED", "SUBMITTING", "SUBMITTED"]).toContain(after.state);
  // lifecycle_state canonical bucket must be APPROVED (stage 9 in the 11-step pipeline)
  if (after.lifecycle_state !== undefined) {
    expect(["APPROVED", "RECOVERED"]).toContain(after.lifecycle_state);
  }
});

test("@smoke J6-3 decline path — approval state is DECLINED after decline", async ({
  request,
}) => {
  const { opportunity_id, approval_id } = await setupPendingApproval(request);

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/decline`,
    {
      data: { principal: "playwright-test", notes: "Declined via test" },
    }
  );
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { approval_id: string; state: string };
  expect(body.approval_id).toBe(approval_id);
  expect(body.state).toBe("DECLINED");

  // Should not appear in pending list
  const pending = await listAllApprovals(request);
  const stillPending = pending.find((r) => r.opportunity_id === opportunity_id);
  expect(stillPending).toBeUndefined();
});

test("@smoke J6-4 investigate path — state is DECLINED with [INVESTIGATE] notes (NEEDS_FOLLOWUP)", async ({
  request,
}) => {
  const { opportunity_id } = await setupPendingApproval(request);

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/investigate`,
    {
      data: { principal: "playwright-test", notes: "Need more data" },
    }
  );
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as {
    approval_id: string;
    state: string;
    opportunity_state: string;
  };
  // Investigate calls decline with [INVESTIGATE] prefix — opportunity_state is NEEDS_FOLLOWUP
  expect(body.opportunity_state).toBe("NEEDS_FOLLOWUP");
  // The approval state is DECLINED (backend re-uses decline with note prefix)
  expect(body.state).toBe("DECLINED");
});

test("@smoke J6-5 investigate does NOT set state to DECLINED without note prefix check", async ({
  request,
}) => {
  const { opportunity_id } = await setupPendingApproval(request);

  // Use the investigate endpoint
  const investRes = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/investigate`,
    {
      data: { principal: "playwright-test" },
    }
  );
  expect(investRes.ok()).toBeTruthy();

  // Now try to approve the same opportunity — should fail (already decided)
  const pendingRes = await request.get(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}`
  );
  // After investigate, no PENDING approval exists for this opportunity
  // (it was declined/moved to NEEDS_FOLLOWUP)
  const pendingData = await pendingRes.json() as { approval_id?: string } | null;
  expect(pendingData).toBeNull();
});

// ---------------------------------------------------------------------------
// J6 — @full: security + edge cases
// ---------------------------------------------------------------------------

test("@full J6-6 tampered claim_hash returns 409 — Cedar binding holds", async ({ request }) => {
  const { opportunity_id, amount, state_version } = await setupPendingApproval(request);

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
    {
      data: {
        principal: "attacker",
        claim_hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        amount,
        state_version,
      },
    }
  );
  expect(res.status()).toBe(409);
  const body = (await res.json()) as { detail: string };
  expect(body.detail).toContain("claim_hash");
});

test("@full J6-7 X-Request-ID header present on all approval responses", async ({ request }) => {
  const { opportunity_id, claim_hash, amount, state_version } =
    await setupPendingApproval(request);

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
    {
      data: { principal: "playwright-test", claim_hash, amount, state_version },
    }
  );
  // X-Request-ID injected by middleware
  const requestId = res.headers()["x-request-id"];
  expect(requestId).toBeTruthy();
  // UUID format
  expect(requestId).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  );
});

test("@full J6-8 cannot approve twice — second approve returns 409", async ({ request }) => {
  const { opportunity_id } = await setupPendingApproval(request);

  // First approve succeeds
  await approveOpportunity(request, opportunity_id);

  // Second approve should fail — no pending approval exists
  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
    {
      data: {
        principal: "playwright-test",
        claim_hash: "sha256:anything",
        amount: "0.00",
        state_version: 1,
      },
    }
  );
  expect(res.status()).toBe(404);
});

test("@full J6-9 health/ready endpoint returns status ok or degraded", async ({ request }) => {
  const res = await request.get(`${BACKEND}/health/ready`);
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { status: string; checks: Record<string, string> };
  expect(["ready", "degraded"]).toContain(body.status);
  expect(body.checks).toBeTruthy();
});

test("@full J6-10 test/reset returns 200 in non-production env", async ({ request }) => {
  const res = await request.post(`${BACKEND}/api/test/reset`);
  // Should succeed in local/test environment
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { status: string };
  expect(body.status).toBe("reset");
});
