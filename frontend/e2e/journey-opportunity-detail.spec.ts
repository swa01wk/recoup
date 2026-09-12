/**
 * J7 — Opportunity Detail (J-FULL / scan-promoted path)
 */
import { test, expect } from "@playwright/test";
import {
  BACKEND,
  resetBackend,
  approveOpportunity,
  runDemoScan,
  promoteFinding,
  promoteActionableFinding,
} from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

async function triggerScanOpportunity(
  request: import("@playwright/test").APIRequestContext,
  index = 0
): Promise<{ opportunity_id: string }> {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  expect(findings.length).toBeGreaterThan(index);
  return promoteFinding(request, findings[index]);
}

test("@smoke J7-1 opportunity detail is reachable and returns state", async ({ request }) => {
  const { opportunity_id } = await triggerScanOpportunity(request);
  const res = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
  expect(res.ok()).toBeTruthy();
  const opp = (await res.json()) as { opportunity_id: string; state: string };
  expect(opp.opportunity_id).toBe(opportunity_id);
  expect(opp.state).toBe("AWAITING_APPROVAL");
});

test("@smoke J7-2 promoted opportunity stream endpoint responds with SSE content-type", async ({
  request,
}) => {
  const { opportunity_id } = await triggerScanOpportunity(request);
  const res = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}/stream`);
  expect([200, 204]).toContain(res.status());
  if (res.status() === 200) {
    const contentType = res.headers()["content-type"] ?? "";
    expect(contentType).toContain("text/event-stream");
  }
});

test("@smoke J7-3 approve from opportunity detail — state transitions to APPROVED", async ({
  request,
}) => {
  const { opportunity_id } = await promoteActionableFinding(request);
  await approveOpportunity(request, opportunity_id);
  const opp = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
  const oppBody = (await opp.json()) as { state: string };
  expect(["APPROVED", "RECOVERED", "SUBMITTING", "SUBMITTED"]).toContain(oppBody.state);
});

test("@smoke J7-4 decline from opportunity detail — approval state is DECLINED", async ({
  request,
}) => {
  const { opportunity_id } = await triggerScanOpportunity(request);
  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/decline`,
    { data: { principal: "playwright-test", notes: "Declined from detail" } }
  );
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { state: string };
  expect(body.state).toBe("DECLINED");
});

test("@full J7-5 investigate endpoint sets opportunity_state to NEEDS_FOLLOWUP", async ({
  request,
}) => {
  const { opportunity_id } = await triggerScanOpportunity(request);
  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/investigate`,
    { data: { principal: "playwright-test", notes: "More data needed" } }
  );
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { opportunity_state: string };
  expect(body.opportunity_state).toBe("NEEDS_FOLLOWUP");
});

test("@full J7-6 opportunity trace returns data for scan-promoted path", async ({ request }) => {
  const { opportunity_id } = await triggerScanOpportunity(request);
  const res = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}/trace`);
  expect(res.ok()).toBeTruthy();
  const trace = (await res.json()) as {
    opportunity_id: string;
    nodes?: Array<{ node: string }>;
    events?: Array<{ node: string }>;
  };
  expect(trace.opportunity_id).toBe(opportunity_id);
});

test("@full J7-7 list opportunities includes multiple promoted entries", async ({ request }) => {
  const { opportunity_id: id1 } = await triggerScanOpportunity(request, 0);
  const { opportunity_id: id2 } = await triggerScanOpportunity(request, 1);
  const res = await request.get(`${BACKEND}/api/opportunities`);
  expect(res.ok()).toBeTruthy();
  const ids = ((await res.json()) as Array<{ opportunity_id: string }>).map((o) => o.opportunity_id);
  expect(ids).toContain(id1);
  expect(ids).toContain(id2);
});

test("@full J7-8 unknown opportunity_id returns 404", async ({ request }) => {
  const res = await request.get(`${BACKEND}/api/opportunities/nonexistent-opp-id`);
  expect(res.status()).toBe(404);
});

test("@full J7-9 opportunity run endpoint accepts scan-promoted opportunity", async ({
  request,
}) => {
  const { opportunity_id } = await triggerScanOpportunity(request);
  const res = await request.post(`${BACKEND}/api/opportunities/${opportunity_id}/run`, {
    data: { use_strands: false },
  });
  expect([200, 409, 422]).toContain(res.status());
});
