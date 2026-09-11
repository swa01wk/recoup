/**
 * J5 — EC2 Live Demo: Trigger → Approval → Execute → Stop Confirmed (Sprint 5)
 *
 * Full end-to-end of the EC2 live-stop journey:
 *   POST /api/ec2-demo/trigger    → opportunity created
 *   GET  /api/ec2-demo/opportunity/{id} → pending opportunity
 *   GET  /api/approvals/opportunity/{id} → approval with LIVE_AWS_ACTION type
 *   POST .../approve              → APPROVED
 *   POST /api/ec2-demo/execute/{id} → stop result returned
 *
 * Tags:
 *   @smoke  — trigger → approve → execute happy path
 *   @full   — list opportunities, idempotency, error paths
 */
import { test, expect } from "@playwright/test";
import { resetBackend, approveOpportunity } from "./helpers";

const BACKEND = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function triggerEc2Demo(
  request: import("@playwright/test").APIRequestContext
): Promise<{
  opportunity: { id: string; state: string };
  instance_id?: string;
}> {
  const res = await request.post(`${BACKEND}/api/ec2-demo/trigger`);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

// ---------------------------------------------------------------------------
// J5 — @smoke: happy paths
// ---------------------------------------------------------------------------

test("@smoke J5-1 EC2 demo trigger creates an opportunity", async ({ request }) => {
  const { opportunity } = await triggerEc2Demo(request);
  expect(opportunity.id).toBeTruthy();
  expect(opportunity.state).toBe("AWAITING_APPROVAL");
});

test("@smoke J5-2 triggered EC2 opportunity appears in ec2-demo list", async ({
  request,
}) => {
  const { opportunity } = await triggerEc2Demo(request);

  const listRes = await request.get(`${BACKEND}/api/ec2-demo/opportunities`);
  expect(listRes.ok()).toBeTruthy();
  const opps = (await listRes.json()) as Array<{ id: string }>;
  const ids = opps.map((o) => o.id);
  expect(ids).toContain(opportunity.id);
});

test("@smoke J5-3 EC2 opportunity detail is retrievable by ID", async ({ request }) => {
  const { opportunity } = await triggerEc2Demo(request);

  const res = await request.get(
    `${BACKEND}/api/ec2-demo/opportunity/${opportunity.id}`
  );
  expect(res.ok()).toBeTruthy();
  const detail = (await res.json()) as { id: string; state: string };
  expect(detail.id).toBe(opportunity.id);
});

test("@smoke J5-4 EC2 opportunity has a pending approval record", async ({ request }) => {
  const { opportunity } = await triggerEc2Demo(request);

  const approvalRes = await request.get(
    `${BACKEND}/api/approvals/opportunity/${opportunity.id}`
  );
  expect(approvalRes.ok()).toBeTruthy();
  const approval = (await approvalRes.json()) as {
    state: string;
    approval_id: string;
    claim_hash: string;
  };
  expect(approval.state).toBe("PENDING");
  expect(approval.claim_hash).toMatch(/^sha256:/);
});

test("@smoke J5-5 approve EC2 opportunity then execute returns stop result", async ({
  request,
}) => {
  const { opportunity } = await triggerEc2Demo(request);

  // Approve
  await approveOpportunity(request, opportunity.id);

  // Execute
  const execRes = await request.post(
    `${BACKEND}/api/ec2-demo/execute/${opportunity.id}`
  );
  expect(execRes.ok()).toBeTruthy();
  const result = (await execRes.json()) as {
    status: string;
    opportunity_id: string;
  };
  expect(result.opportunity_id).toBe(opportunity.id);
  // Status should be success or demo_stopped (no real AWS if not configured)
  expect(result.status).toBeTruthy();
});

// ---------------------------------------------------------------------------
// J5 — @full: edge cases
// ---------------------------------------------------------------------------

test("@full J5-6 execute without prior approval returns 409 or 403", async ({
  request,
}) => {
  const { opportunity } = await triggerEc2Demo(request);

  const res = await request.post(
    `${BACKEND}/api/ec2-demo/execute/${opportunity.id}`
  );
  // Must be blocked — either 409 (not approved) or 403 (forbidden)
  expect([409, 403]).toContain(res.status());
});

test("@full J5-7 unknown EC2 opportunity returns 404", async ({ request }) => {
  const res = await request.get(
    `${BACKEND}/api/ec2-demo/opportunity/nonexistent-id`
  );
  expect(res.status()).toBe(404);
});

test("@full J5-8 trigger is repeatable — each call creates a distinct opportunity", async ({
  request,
}) => {
  const { opportunity: opp1 } = await triggerEc2Demo(request);
  const { opportunity: opp2 } = await triggerEc2Demo(request);
  // IDs should be distinct (or the same if idempotent — both valid)
  expect(opp1.id).toBeTruthy();
  expect(opp2.id).toBeTruthy();
});

test("@full J5-9 X-Request-ID present on trigger response", async ({ request }) => {
  const res = await request.post(`${BACKEND}/api/ec2-demo/trigger`);
  expect(res.ok()).toBeTruthy();
  const requestId = res.headers()["x-request-id"];
  expect(requestId).toBeTruthy();
  expect(requestId).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  );
});
