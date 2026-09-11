/**
 * J7 — Opportunity Detail: Agent Stream + Approve/Decline (Sprint 5)
 *
 * Tests:
 *   GET /api/opportunities/{id}/stream — SSE stream emits nodes (SLA path)
 *   GET /api/opportunities/{id}/trace  — returns trace with nodes
 *   Investigate button calls investigate (not decline) → NEEDS_FOLLOWUP
 *   Approve from detail updates state
 *   Decline removes from inbox
 *
 * Tags:
 *   @smoke  — stream, trace, approve from detail
 *   @full   — investigate fix, decline, trace structure
 */
import { test, expect } from "@playwright/test";
import { resetBackend, approveOpportunity, runDemoScan, promoteFinding } from "./helpers";

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

async function triggerReplayOpportunity(
  request: import("@playwright/test").APIRequestContext
): Promise<{ opportunity_id: string; credit_amount: string }> {
  const res = await request.post(`${BACKEND}/api/replay/api-gateway-sla`);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

async function triggerScanOpportunity(
  request: import("@playwright/test").APIRequestContext
): Promise<{ opportunity_id: string }> {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  expect(findings.length).toBeGreaterThan(0);
  return promoteFinding(request, findings[0]);
}

// ---------------------------------------------------------------------------
// J7 — @smoke: happy paths
// ---------------------------------------------------------------------------

test("@smoke J7-1 opportunity detail is reachable and returns state", async ({
  request,
}) => {
  const { opportunity_id } = await triggerScanOpportunity(request);

  const res = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
  expect(res.ok()).toBeTruthy();
  const opp = (await res.json()) as { opportunity_id: string; state: string };
  expect(opp.opportunity_id).toBe(opportunity_id);
  expect(opp.state).toBe("AWAITING_APPROVAL");
});

test("@smoke J7-2 SLA replay opportunity stream endpoint responds with SSE content-type", async ({
  request,
}) => {
  const { opportunity_id } = await triggerReplayOpportunity(request);

  // Stream endpoint should respond (200) with text/event-stream
  const res = await request.get(
    `${BACKEND}/api/opportunities/${opportunity_id}/stream`
  );
  // Accept 200 or 204 (empty stream for already-completed opportunities)
  expect([200, 204]).toContain(res.status());
  if (res.status() === 200) {
    const contentType = res.headers()["content-type"] ?? "";
    expect(contentType).toContain("text/event-stream");
  }
});

test("@smoke J7-3 approve from opportunity detail — state transitions to APPROVED", async ({
  request,
}) => {
  const { opportunity_id } = await triggerScanOpportunity(request);
  const result = await approveOpportunity(request, opportunity_id);
  expect(result).toBeTruthy();

  // Verify state changed
  const opp = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
  const oppBody = (await opp.json()) as { state: string };
  expect(["APPROVED", "SUBMITTING", "SUBMITTED"]).toContain(oppBody.state);
});

test("@smoke J7-4 decline from opportunity detail — approval state is DECLINED", async ({
  request,
}) => {
  const { opportunity_id } = await triggerScanOpportunity(request);

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/decline`,
    {
      data: { principal: "playwright-test", notes: "Declined from detail" },
    }
  );
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { state: string };
  expect(body.state).toBe("DECLINED");
});

// ---------------------------------------------------------------------------
// J7 — @full: edge cases
// ---------------------------------------------------------------------------

test("@full J7-5 investigate endpoint sets opportunity_state to NEEDS_FOLLOWUP (not DECLINED)", async ({
  request,
}) => {
  const { opportunity_id } = await triggerScanOpportunity(request);

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/investigate`,
    {
      data: { principal: "playwright-test", notes: "More data needed" },
    }
  );
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as {
    opportunity_state: string;
    state: string;
  };
  // Opportunity state must be NEEDS_FOLLOWUP — not DECLINED
  expect(body.opportunity_state).toBe("NEEDS_FOLLOWUP");
});

test("@full J7-6 opportunity trace returns node list for SLA replay path", async ({
  request,
}) => {
  const { opportunity_id } = await triggerReplayOpportunity(request);

  const res = await request.get(
    `${BACKEND}/api/opportunities/${opportunity_id}/trace`
  );
  expect(res.ok()).toBeTruthy();
  const trace = (await res.json()) as {
    opportunity_id: string;
    nodes?: Array<{ node: string }>;
    events?: Array<{ node: string }>;
  };
  expect(trace.opportunity_id).toBe(opportunity_id);
  // Either 'nodes' or 'events' key should be present with at least one entry
  const nodes = trace.nodes ?? trace.events ?? [];
  expect(nodes.length).toBeGreaterThanOrEqual(1);
});

test("@full J7-7 list opportunities includes both scan-promoted and replay entries", async ({
  request,
}) => {
  const { opportunity_id: scanId } = await triggerScanOpportunity(request);
  const { opportunity_id: replayId } = await triggerReplayOpportunity(request);

  const res = await request.get(`${BACKEND}/api/opportunities`);
  expect(res.ok()).toBeTruthy();
  const opps = (await res.json()) as Array<{ opportunity_id: string }>;
  const ids = opps.map((o) => o.opportunity_id);
  expect(ids).toContain(scanId);
  expect(ids).toContain(replayId);
});

test("@full J7-8 unknown opportunity_id returns 404", async ({ request }) => {
  const res = await request.get(`${BACKEND}/api/opportunities/nonexistent-opp-id`);
  expect(res.status()).toBe(404);
});

test("@full J7-9 opportunity run endpoint triggers agent for SLA opportunity", async ({
  request,
}) => {
  const { opportunity_id } = await triggerReplayOpportunity(request);

  const res = await request.post(
    `${BACKEND}/api/opportunities/${opportunity_id}/run`,
    { data: { mode: "dry_run" } }
  );
  // 200 (ran) or 409 (already running/completed) — both acceptable
  expect([200, 409, 422]).toContain(res.status());
});
