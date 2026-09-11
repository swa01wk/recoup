/**
 * Opportunity detail page wiring
 *
 * UI components: OpportunityDetailPage, PipelineStrip (6-stage vs 9-node),
 *                HitlGateMessageBanner
 * Backend calls: GET /api/opportunities/{id}, GET /api/opportunities/{id}/trace
 */
import { test, expect } from "@playwright/test";
import { resetBackend, runDemoScan } from "./helpers";

const BACKEND = "http://localhost:8000";

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

test("@smoke cost recovery opportunity exists and has AWAITING_APPROVAL state", async ({
  request,
}) => {
  // Stage: Cost recovery finding (promoted scan)
  // Backend call → GET /api/opportunities/{id}
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const finding = findings[0];

  const promoteRes = await request.post(`${BACKEND}/api/scan/findings/promote`, {
    data: finding,
  });
  const promoted = (await promoteRes.json()) as { opportunity_id: string };

  const oppRes = await request.get(
    `${BACKEND}/api/opportunities/${promoted.opportunity_id}`
  );
  expect(oppRes.ok()).toBeTruthy();
  const opp = (await oppRes.json()) as {
    id: string;
    state: string;
    state_version: number;
    potential_value: string | null;
    service: string | null;
  };
  expect(opp.state).toBe("AWAITING_APPROVAL");
  expect(opp.state_version).toBeGreaterThanOrEqual(1);
  // Cost recovery opportunities should have a service and potential value
  expect(opp.service).toBeTruthy();
  expect(parseFloat(opp.potential_value ?? "0")).toBeGreaterThan(0);
});

test("promoted finding is retrievable via /api/opportunities list", async ({ request }) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;

  // Promote 3 findings
  const promoted: string[] = [];
  for (const finding of findings.slice(0, 3)) {
    const res = await request.post(`${BACKEND}/api/scan/findings/promote`, { data: finding });
    const data = (await res.json()) as { opportunity_id: string };
    promoted.push(data.opportunity_id);
  }

  // All should appear in the opportunities list
  const listRes = await request.get(`${BACKEND}/api/opportunities`);
  const list = (await listRes.json()) as Array<{ id: string }>;
  const ids = list.map((o) => o.id);
  for (const id of promoted) {
    expect(ids).toContain(id);
  }
});

test("HITL gate — pending approval exists after promote", async ({ request }) => {
  // Stage: HITL gate message
  // Backend call → GET /api/approvals/opportunity/{id}
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const finding = findings[0];

  const promoteRes = await request.post(`${BACKEND}/api/scan/findings/promote`, {
    data: finding,
  });
  const promoted = (await promoteRes.json()) as { opportunity_id: string };

  const approvalRes = await request.get(
    `${BACKEND}/api/approvals/opportunity/${promoted.opportunity_id}`
  );
  expect(approvalRes.ok()).toBeTruthy();
  const approval = (await approvalRes.json()) as { state: string; claim_hash: string };
  expect(approval.state).toBe("PENDING");
  expect(approval.claim_hash).toMatch(/^sha256:/);
});

// ---------------------------------------------------------------------------
// Fix-B tests — cost-recovery detail page uses correct terminology
// ---------------------------------------------------------------------------

test("cost recovery detail returns potential_value matching finding savings", async ({
  request,
}) => {
  // The opportunity detail for a promoted finding must expose the original
  // finding's estimated_monthly_savings_usd as potential_value.
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const finding = findings[0];
  const expectedSavings = parseFloat(
    String(finding["estimated_monthly_savings_usd"] ?? "0")
  );

  const promoteRes = await request.post(`${BACKEND}/api/scan/findings/promote`, {
    data: finding,
  });
  const promoted = (await promoteRes.json()) as { opportunity_id: string };

  const oppRes = await request.get(
    `${BACKEND}/api/opportunities/${promoted.opportunity_id}`
  );
  expect(oppRes.ok()).toBeTruthy();
  const opp = (await oppRes.json()) as { potential_value: string | null };

  if (expectedSavings > 0) {
    expect(parseFloat(opp.potential_value ?? "0")).toBeGreaterThan(0);
    // Value must match to within $0.01 (rounding)
    expect(
      Math.abs(parseFloat(opp.potential_value ?? "0") - expectedSavings)
    ).toBeLessThan(0.01);
  }
});

test("cost recovery trace has calculation_trace without SLA-specific content", async ({
  request,
}) => {
  // The calculation_trace for a promoted finding should describe the resource issue,
  // not SLA breach intervals.
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const finding = findings[0];

  const promoteRes = await request.post(`${BACKEND}/api/scan/findings/promote`, {
    data: finding,
  });
  const promoted = (await promoteRes.json()) as { opportunity_id: string };

  const traceRes = await request.get(
    `${BACKEND}/api/opportunities/${promoted.opportunity_id}/trace`
  );
  expect(traceRes.ok()).toBeTruthy();
  const trace = (await traceRes.json()) as {
    availability_result?: {
      calculation_trace: string[];
      tier_pct: string;
      monthly_uptime_pct: string;
    } | null;
  };

  if (!trace.availability_result) return; // no result yet — skip

  const traceLines = trace.availability_result.calculation_trace;
  expect(traceLines.length).toBeGreaterThan(0);

  // Cost-recovery trace should mention the resource, not "uptime intervals"
  const combined = traceLines.join(" ").toLowerCase();
  expect(combined).toMatch(/resource:|issue:|recommendation:|savings/i);

  // Credit tier must be 0 for cost-recovery (no SLA credit tier applies)
  expect(parseFloat(trace.availability_result.tier_pct)).toBe(0);

  // Monthly uptime must be 100% for cost-recovery opportunities
  expect(parseFloat(trace.availability_result.monthly_uptime_pct)).toBe(100);
});
