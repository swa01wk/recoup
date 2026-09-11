/**
 * @smoke
 * HITL Decision Inbox — approve / investigate / decline lifecycles
 *
 * UI components: DecisionInboxPage (/approvals), ApprovalCard, ApproveButton,
 *                InvestigateButton, DeclineButton
 * Backend calls: POST /api/approvals/opportunity/{id}/approve|investigate|decline
 */
import { test, expect } from "@playwright/test";
import { resetBackend, runDemoScan, approveOpportunity } from "./helpers";

const BACKEND = "http://localhost:8000";

async function promoteFirstFinding(
  request: import("@playwright/test").APIRequestContext
): Promise<string> {
  const scan = await runDemoScan(request);
  const findings = (scan.findings as Array<Record<string, unknown>>).filter(
    (f) => (f.scenario_tag as string) !== "s1_sla_credit" // skip SLA finding
  );
  const finding = findings[0] ?? scan.findings[0];
  const res = await request.post(`${BACKEND}/api/scan/findings/promote`, { data: finding });
  const data = (await res.json()) as { opportunity_id: string };
  return data.opportunity_id;
}

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

// ---------------------------------------------------------------------------
// Approve path
// ---------------------------------------------------------------------------
test("@smoke approve — AWAITING_APPROVAL → APPROVED, sns_notification_sent=true", async ({
  request,
}) => {
  // Stage: Approve
  // Backend call → POST /api/approvals/opportunity/{id}/approve (+ notify_sns internally)
  const oppId = await promoteFirstFinding(request);
  const result = await approveOpportunity(request, oppId);

  expect(result["state"]).toBe("APPROVED");
  // SNS flag should be returned by the approve endpoint
  expect(result["sns_notification_sent"]).toBe(true);

  // Verify no longer in pending list
  const pendingRes = await request.get(`${BACKEND}/api/approvals/pending`);
  const pending = (await pendingRes.json()) as Array<{ opportunity_id: string; state: string }>;
  const stillPending = pending.filter(
    (r) => r.opportunity_id === oppId && r.state === "PENDING"
  );
  expect(stillPending.length).toBe(0);
});

// ---------------------------------------------------------------------------
// Investigate path
// ---------------------------------------------------------------------------
test("@smoke investigate — AWAITING_APPROVAL → NEEDS_FOLLOWUP (approval declined with [INVESTIGATE] note)", async ({
  request,
}) => {
  // Stage: Investigate
  // Backend call → POST /api/approvals/opportunity/{id}/investigate
  const oppId = await promoteFirstFinding(request);

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${oppId}/investigate`,
    {
      data: {
        principal: "playwright-test",
        notes: "Needs further review",
      },
    }
  );
  expect(res.ok()).toBeTruthy();
  const data = (await res.json()) as { opportunity_state: string };
  expect(data.opportunity_state).toBe("NEEDS_FOLLOWUP");

  // Opportunity should no longer be in the PENDING list
  const pendingRes = await request.get(`${BACKEND}/api/approvals/pending`);
  const pending = (await pendingRes.json()) as Array<{ opportunity_id: string; state: string }>;
  const stillPending = pending.filter(
    (r) => r.opportunity_id === oppId && r.state === "PENDING"
  );
  expect(stillPending.length).toBe(0);
});

// ---------------------------------------------------------------------------
// Decline path
// ---------------------------------------------------------------------------
test("decline — AWAITING_APPROVAL → DECLINED, removed from pending", async ({ request }) => {
  // Stage: Decline
  // Backend call → POST /api/approvals/opportunity/{id}/decline
  const oppId = await promoteFirstFinding(request);

  const pendingBefore = (await (
    await request.get(`${BACKEND}/api/approvals/opportunity/${oppId}`)
  ).json()) as { approval_id: string; principal: string; notes: string };

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${oppId}/decline`,
    {
      data: { principal: "playwright-test", notes: "Declined by test" },
    }
  );
  expect(res.ok()).toBeTruthy();
  const data = (await res.json()) as { state: string };
  expect(data.state).toBe("DECLINED");

  // Should no longer appear in pending list
  const pendingRes = await request.get(`${BACKEND}/api/approvals/pending`);
  const pending = (await pendingRes.json()) as Array<{ opportunity_id: string; state: string }>;
  const stillPending = pending.filter(
    (r) => r.opportunity_id === oppId && r.state === "PENDING"
  );
  expect(stillPending.length).toBe(0);
});

// ---------------------------------------------------------------------------
// Stage advancement: after approve, opportunity advances to stage 9 (Remediate)
// ---------------------------------------------------------------------------
test("@smoke inbox-journey: after approve, opportunity is at stage 9+ and not in pending list", async ({
  request,
}) => {
  const oppId = await promoteFirstFinding(request);

  await approveOpportunity(request, oppId);

  // Opportunity must be in a post-approval state (stage 9+)
  const oppRes = await request.get(`${BACKEND}/api/opportunities/${oppId}`);
  expect(oppRes.ok()).toBeTruthy();
  const opp = (await oppRes.json()) as { state: string };
  const postApprovalStates = ["APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING", "RECOVERED"];
  expect(postApprovalStates).toContain(opp.state.toUpperCase());

  // Must no longer appear in pending approvals list
  const pendingRes = await request.get(`${BACKEND}/api/approvals/pending`);
  const pending = (await pendingRes.json()) as Array<{ opportunity_id: string; state: string }>;
  const stillPending = pending.filter((r) => r.opportunity_id === oppId && r.state === "PENDING");
  expect(stillPending.length).toBe(0);
});

// ---------------------------------------------------------------------------
// Bucket invariant
// ---------------------------------------------------------------------------
test("pending list decrements after approve", async ({ request }) => {
  const oppId1 = await promoteFirstFinding(request);

  // Promote a second finding
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const second = findings.find(
    (f) => f.resource_id !== (findings[0] as Record<string, unknown>).resource_id
  );
  if (second) {
    await request.post(`${BACKEND}/api/scan/findings/promote`, { data: second });
  }

  const before = (await (
    await request.get(`${BACKEND}/api/approvals/pending`)
  ).json()) as unknown[];

  await approveOpportunity(request, oppId1);

  const after = (await (
    await request.get(`${BACKEND}/api/approvals/pending`)
  ).json()) as unknown[];

  expect(after.length).toBe(before.length - 1);
});
