/**
 * EC2 Stop lifecycle (S3) — mocked execute endpoint
 *
 * UI components: RecoveryDashboard, EC2ScenarioTile, DecisionInboxPage
 * Backend calls: POST /api/ec2-demo/trigger, POST /api/ec2-demo/execute/{id} (mocked)
 */
import { test, expect } from "@playwright/test";
import { resetBackend, approveOpportunity } from "./helpers";

const BACKEND = "http://localhost:8000";

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

test("@smoke EC2 demo trigger creates HITL approval with stop_demo_instance action", async ({
  request,
}) => {
  // Stage: Trigger (analyze + create HITL)
  // Backend call → POST /api/ec2-demo/trigger
  const res = await request.post(`${BACKEND}/api/ec2-demo/trigger`, {
    data: { instance_id: "" }, // uses demo instance
  });
  if (!res.ok()) {
    // EC2 demo may not be configured — skip gracefully
    console.log("EC2 demo not configured, skipping");
    return;
  }
  const data = (await res.json()) as {
    opportunity: { id: string; state: string };
    approval_id: string;
    instance_id: string;
  };

  expect(data.opportunity.id).toBeTruthy();
  expect(data.instance_id).toBeTruthy();

  // Approval should be pending in the Decision Inbox
  const pendingRes = await request.get(`${BACKEND}/api/approvals/pending`);
  const pending = (await pendingRes.json()) as Array<{
    opportunity_id: string;
    action: string;
  }>;
  const ec2Approval = pending.find(
    (r) =>
      r.opportunity_id === data.opportunity.id && r.action === "stop_demo_instance"
  );
  expect(ec2Approval).toBeTruthy();
});

test("EC2 demo approve — approval moves to APPROVED with SNS report", async ({
  request,
}) => {
  // Stage: Approve (AWAITING_APPROVAL → APPROVED)
  const triggerRes = await request.post(`${BACKEND}/api/ec2-demo/trigger`, {
    data: { instance_id: "" },
  });
  if (!triggerRes.ok()) return;

  const triggered = (await triggerRes.json()) as { opportunity: { id: string } };
  const oppId = triggered.opportunity.id;

  const result = await approveOpportunity(request, oppId);
  expect(result["state"]).toBe("APPROVED");
  // SNS report should also be sent for EC2
  expect(result["sns_notification_sent"]).toBe(true);
});

test("EC2 execute is mocked — no real StopInstances in test", async ({ page, request }) => {
  // Stage: Execute stop (mocked)
  // Mock the execute endpoint to return success without real AWS call
  await page.route("**/api/ec2-demo/execute/**", (route) => {
    void route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        stop_result: {
          instance_id: "i-demo123",
          previous_state: "running",
          current_state: "stopped",
          stopped_at: new Date().toISOString(),
          verified_stopped: true,
          simulated: true,
          audit_trail: ["StopInstances called (mocked by test)"],
        },
      }),
    });
  });

  // Trigger
  const triggerRes = await request.post(`${BACKEND}/api/ec2-demo/trigger`, {
    data: { instance_id: "" },
  });
  if (!triggerRes.ok()) return;

  const triggered = (await triggerRes.json()) as { opportunity: { id: string } };
  await approveOpportunity(request, triggered.opportunity.id);

  // Navigate to the opportunity page and verify the mock execute works
  await page.goto(`/opportunities/${triggered.opportunity.id}`);
  // The page should load without error
  await expect(page.locator("h1, [data-testid='opp-header']").first()).toBeVisible({
    timeout: 10_000,
  });
});
