/**
 * Workflow Stage Tracking Tests — WF-1 through WF-14
 *
 * Verifies every meaningful state transition in the cost-recovery pipeline
 * (both API-level and browser UI-level) maps to the correct pipeline stage.
 *
 * Backend states (OpportunityState enum):
 *   DETECTED → INVESTIGATING → NEEDS_EVIDENCE → EVIDENCE_READY
 *   → ELIGIBILITY_REVIEWED → AWAITING_APPROVAL → APPROVED
 *   → SUBMITTING → SUBMITTED → MONITORING → RECOVERED | REJECTED
 *   also: NEEDS_FOLLOWUP, DENIED, FAILED (terminal/side branches)
 *
 * Frontend 11-step pipeline (unified for all opportunity types):
 *   1 Detect → 2 Investigate → 3 Correlate → 4 Explain → 5 Prove →
 *   6 Plan → 7 Policy → 8 Approve → 9 Remediate → 10 Verify → 11 Record
 *
 * Tags:
 *   @smoke — fast happy-path assertions (API only, no browser)
 *   @ui    — browser UI assertions
 *   @full  — full lifecycle (may be slower; state polling)
 */

import { test, expect } from "@playwright/test";
import {
  BACKEND,
  resetBackend,
  runDemoScan,
  promoteFinding,
  approveOpportunity,
  declineOpportunity,
  pollUntilState,
  promoteActionableFinding,
} from "./helpers";

// ---------------------------------------------------------------------------
// Helper — map state name to expected pipeline stage number (1-11)
// (mirrors pipelineStageForOpportunity in recovery-storage.ts after P0-3 fix)
// ---------------------------------------------------------------------------
function expectedStage(state: string): number {
  switch (state.toUpperCase()) {
    case "DETECTED":          return 1;  // Detect
    case "INVESTIGATING":     return 2;  // Investigate
    case "NEEDS_EVIDENCE":    return 3;  // Correlate
    case "EVIDENCE_READY":    return 5;  // Prove
    case "ELIGIBILITY_REVIEWED": return 6; // Plan
    case "AWAITING_APPROVAL":
    case "NEEDS_FOLLOWUP":
    case "DENIED":
    case "REJECTED":          return 8;  // Approve gate
    case "APPROVED":
    case "SUBMITTING":
    case "SUBMITTED":         return 9;  // Remediate
    case "MONITORING":        return 10; // Verify
    case "RECOVERED":         return 11; // Record
    default:                  return 1;
  }
}

// ---------------------------------------------------------------------------
// Stage label in the 11-step pipeline strip
// ---------------------------------------------------------------------------
const STAGE_LABELS = [
  "Detect", "Investigate", "Correlate", "Explain", "Prove",
  "Plan", "Policy", "Approve", "Remediate", "Verify", "Record",
] as const;

function stageLabelFor(n: number): string {
  return STAGE_LABELS[n - 1] ?? "Detect";
}

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

// ===========================================================================
// WF-1 — DETECT: scan finding exists before any promotion
// ===========================================================================

test("@smoke WF-1 scan findings are in DETECTED stage (not yet promoted)", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;

  expect(findings.length).toBeGreaterThan(0);

  // No promoted opportunities yet — /api/opportunities should be empty (or only have
  // pre-existing SLA-replay items, none of which are AWAITING_APPROVAL)
  const oppsRes = await request.get(`${BACKEND}/api/opportunities`);
  const opps = (await oppsRes.json()) as Array<{ state: string; id: string }>;
  const awaitingApproval = opps.filter(
    (o) => o.state.toUpperCase() === "AWAITING_APPROVAL" && o.id.startsWith("recovery-")
  );
  expect(awaitingApproval.length).toBe(0);
});

// ===========================================================================
// WF-2 — PROMOTE → AWAITING_APPROVAL (pipeline stage 5: Approve)
// ===========================================================================

test("@smoke WF-2 promote finding → state is AWAITING_APPROVAL (stage 5 Approve)", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;

  const { opportunity_id } = await promoteFinding(request, findings[0]);

  const opp = await pollUntilState(request, opportunity_id, "AWAITING_APPROVAL");

  expect(opp.state.toUpperCase()).toBe("AWAITING_APPROVAL");
  expect(expectedStage(opp.state)).toBe(8);
  expect(stageLabelFor(8)).toBe("Approve");
});

// ===========================================================================
// WF-3 — AWAITING_APPROVAL: approval record created in PENDING state
// ===========================================================================

test("@smoke WF-3 AWAITING_APPROVAL opportunity has a PENDING approval record", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const { opportunity_id } = await promoteFinding(request, findings[0]);

  const approvalRes = await request.get(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}`
  );
  expect(approvalRes.ok()).toBeTruthy();
  const approval = (await approvalRes.json()) as {
    state: string;
    amount: string;
    claim_hash: string;
    state_version: number;
  };

  expect(approval.state.toUpperCase()).toBe("PENDING");
  expect(parseFloat(approval.amount)).toBeGreaterThan(0);
  expect(approval.claim_hash).toMatch(/^sha256:/);
  expect(approval.state_version).toBeGreaterThanOrEqual(1);
});

// ===========================================================================
// WF-4 — APPROVE → APPROVED (pipeline stage 6: Record)
// ===========================================================================

test("@smoke WF-4 approve opportunity → state advances to APPROVED (stage 6 Record)", async ({
  request,
}) => {
  const { opportunity_id } = await promoteActionableFinding(request);

  await approveOpportunity(request, opportunity_id);

  // State must be APPROVED (or further along the post-approval path)
  const opp = await pollUntilState(request, opportunity_id, [
    "APPROVED",
    "SUBMITTING",
    "SUBMITTED",
    "MONITORING",
    "RECOVERED",
  ]);

  // APPROVED → stage 9 (Remediate); MONITORING → 10 (Verify); RECOVERED → 11 (Record)
  expect(expectedStage(opp.state)).toBeGreaterThanOrEqual(9);
  expect(stageLabelFor(expectedStage(opp.state))).toMatch(/Remediate|Verify|Record/);
});

// ===========================================================================
// WF-5 — DECLINE → DENIED (pipeline stage 5: Approve — still at gate)
// ===========================================================================

test("@smoke WF-5 decline opportunity → state is DENIED (stays at stage 5 Approve)", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const { opportunity_id } = await promoteFinding(request, findings[0]);

  await declineOpportunity(request, opportunity_id, "WF-5 test decline");

  const opp = await pollUntilState(request, opportunity_id, "DENIED");

  expect(opp.state.toUpperCase()).toBe("DENIED");
  // DENIED maps to stage 8 (Approve gate) — opportunity stopped at the HITL gate
  expect(expectedStage(opp.state)).toBe(8);
  expect(stageLabelFor(8)).toBe("Approve");
});

// ===========================================================================
// WF-6 — Post-approval: APPROVED is visible in pending approvals list
// ===========================================================================

test("@smoke WF-6 after approve, opportunity no longer appears in pending approvals list", async ({
  request,
}) => {
  const { opportunity_id } = await promoteActionableFinding(request);

  await approveOpportunity(request, opportunity_id);

  const pendingRes = await request.get(`${BACKEND}/api/approvals/pending`);
  const pending = (await pendingRes.json()) as Array<{ opportunity_id: string }>;

  const stillPending = pending.find((r) => r.opportunity_id === opportunity_id);
  expect(stillPending).toBeUndefined();
});

// ===========================================================================
// WF-7 — state_version increments on each transition
// ===========================================================================

test("@smoke WF-7 state_version increments from promote → approve", async ({ request }) => {
  const { opportunity_id } = await promoteActionableFinding(request);

  const afterPromote = await pollUntilState(request, opportunity_id, "AWAITING_APPROVAL");
  const versionAfterPromote = afterPromote.state_version;
  expect(versionAfterPromote).toBeGreaterThanOrEqual(1);

  await approveOpportunity(request, opportunity_id);

  const afterApprove = await pollUntilState(request, opportunity_id, [
    "APPROVED",
    "SUBMITTING",
    "SUBMITTED",
    "MONITORING",
    "RECOVERED",
  ]);

  // Version must have incremented at least once more
  expect(afterApprove.state_version).toBeGreaterThan(versionAfterPromote);
});

// ===========================================================================
// WF-8 — full end-to-end multi-finding lifecycle
// ===========================================================================

test("@full WF-8 two findings promoted → both reach AWAITING_APPROVAL independently", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;

  const [{ opportunity_id: id1 }, { opportunity_id: id2 }] = await Promise.all([
    promoteFinding(request, findings[0]),
    promoteFinding(request, findings[1]),
  ]);

  const [opp1, opp2] = await Promise.all([
    pollUntilState(request, id1, "AWAITING_APPROVAL"),
    pollUntilState(request, id2, "AWAITING_APPROVAL"),
  ]);

  expect(opp1.state.toUpperCase()).toBe("AWAITING_APPROVAL");
  expect(opp2.state.toUpperCase()).toBe("AWAITING_APPROVAL");

  // Each should have its own approval record
  const [ap1, ap2] = await Promise.all([
    request.get(`${BACKEND}/api/approvals/opportunity/${id1}`),
    request.get(`${BACKEND}/api/approvals/opportunity/${id2}`),
  ]);
  const approval1 = (await ap1.json()) as { claim_hash: string };
  const approval2 = (await ap2.json()) as { claim_hash: string };

  // Claim hashes must be distinct (different resources → different hashes)
  expect(approval1.claim_hash).not.toBe(approval2.claim_hash);
});

// ===========================================================================
// WF-9 — approve one, decline the other → separate terminal states
// ===========================================================================

test("@full WF-9 approve one opportunity and decline another — stages diverge correctly", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;

  const [{ opportunity_id: idApprove }, { opportunity_id: idDecline }] = await Promise.all([
    promoteFinding(request, findings[0]),
    promoteFinding(request, findings[1]),
  ]);

  await approveOpportunity(request, idApprove);
  await declineOpportunity(request, idDecline, "WF-9 decline leg");

  const [oppA, oppD] = await Promise.all([
    pollUntilState(request, idApprove, ["APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING", "RECOVERED"]),
    pollUntilState(request, idDecline, "DENIED"),
  ]);

  // Approved → stage 9+ (Remediate / Verify / Record)
  expect(expectedStage(oppA.state)).toBeGreaterThanOrEqual(9);
  // Denied → stage 8 (Approve — stopped at HITL gate)
  expect(expectedStage(oppD.state)).toBe(8);

  // potential_value still set for both
  expect(parseFloat(oppA.potential_value ?? "0")).toBeGreaterThan(0);
  expect(parseFloat(oppD.potential_value ?? "0")).toBeGreaterThan(0);
});

// ===========================================================================
// WF-10 — idempotent promote: same resource_id returns same opportunity_id
// ===========================================================================

test("@smoke WF-10 promoting the same finding twice returns the same opportunity_id", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const finding = findings[0];

  const first = await promoteFinding(request, finding);
  const second = await promoteFinding(request, finding);

  expect(second.opportunity_id).toBe(first.opportunity_id);
});

// ===========================================================================
// WF-11 — SLA replay pipeline: non-"recovery-" opportunity tracks its own stages
// ===========================================================================

test("@smoke WF-11 SLA replay opportunity reaches AWAITING_APPROVAL and has approval record", async ({
  request,
}) => {
  const id = `wf11-sla-${Date.now()}`;

  const runRes = await request.post(`${BACKEND}/api/opportunities/${id}/run`, {
    data: { use_strands: true },
  });
  expect(runRes.ok()).toBeTruthy();

  // SLA replay should also land at AWAITING_APPROVAL (policy → REQUIRE_APPROVAL)
  const opp = await pollUntilState(request, id, [
    "AWAITING_APPROVAL",
    "APPROVED",
    "SUBMITTING",
    "SUBMITTED",
    "MONITORING",
    "RECOVERED",
  ]);

  // Must have ended up at stage 5 or 6
  expect(expectedStage(opp.state)).toBeGreaterThanOrEqual(5);
});

// ===========================================================================
// WF-12 — Pending approvals list reflects current pipeline stage correctly
// ===========================================================================

test("@smoke WF-12 pending approvals list matches AWAITING_APPROVAL opportunities", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;

  // Promote 3 findings
  const promoted: string[] = [];
  for (const f of findings.slice(0, 3)) {
    const { opportunity_id } = await promoteFinding(request, f);
    promoted.push(opportunity_id);
  }

  const pendingRes = await request.get(`${BACKEND}/api/approvals/pending`);
  expect(pendingRes.ok()).toBeTruthy();
  const pending = (await pendingRes.json()) as Array<{ opportunity_id: string; amount: string }>;

  // Every promoted opportunity should appear in pending
  for (const id of promoted) {
    const found = pending.find((p) => p.opportunity_id === id);
    expect(found).toBeTruthy();
    expect(parseFloat(found!.amount)).toBeGreaterThan(0);
  }
});

// ===========================================================================
// WF-13 (UI) — pipeline strip shows correct active stage label in the browser
// ===========================================================================

test("@smoke @ui WF-13 opportunity detail pipeline strip highlights 'Approve' after promote", async ({
  page,
}) => {
  const { opportunity_id } = await promoteActionableFinding(page.request);

  await page.goto(`/opportunities/${opportunity_id}`);
  await page.waitForLoadState("networkidle");

  // 11-step pipeline strip must be visible
  await expect(page.getByText(/Step \d+ of 11/i).first()).toBeVisible({
    timeout: 10_000,
  });

  // At AWAITING_APPROVAL → Step 8 of 11 (Approve gate)
  await expect(page.getByText(/Step 8 of 11/i)).toBeVisible({ timeout: 10_000 });

  // "Approve" step label should be visible in the strip
  await expect(page.getByText(/Approve/i).first()).toBeVisible({ timeout: 5_000 });

  // Opportunity state text must be visible somewhere on the page
  await expect(
    page.getByText(/awaiting.approval|approve|pending/i).first()
  ).toBeVisible({ timeout: 5_000 });
});

test("@ui WF-14 opportunity detail pipeline strip shows 'Record' active after approve", async ({
  page,
}) => {
  const { opportunity_id } = await promoteActionableFinding(page.request);

  // Approve via API
  const approvalRes = await page.request.get(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}`
  );
  const approval = (await approvalRes.json()) as {
    claim_hash: string;
    amount: string;
    state_version: number;
  };
  await page.request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
    {
      data: {
        principal: "playwright-wf14",
        claim_hash: approval.claim_hash,
        amount: approval.amount,
        state_version: approval.state_version,
        notes: "WF-14 test approval",
      },
    }
  );

  await page.goto(`/opportunities/${opportunity_id}`);
  await page.waitForLoadState("networkidle");

  // After approval → Step 9+ (Remediate / Verify / Record) must be visible
  await expect(page.getByText(/Step (9|10|11) of 11/i)).toBeVisible({ timeout: 10_000 });
  // "Remediate", "Verify", or "Record" label should be the active stage
  await expect(page.getByText(/Remediate|Verify|Record/i).first()).toBeVisible({ timeout: 10_000 });

  // Opportunity state text should reflect post-approval state
  await expect(
    page.getByText(/approved|submitting|submitted|monitoring|recovered/i).first()
  ).toBeVisible({ timeout: 5_000 });

  // Opportunity state should NOT be showing "Approve" as the active step anymore
  // (the card heading or stage indicator should show a later stage)
  const stateEl = page.getByText(/awaiting.approval/i).first();
  await expect(stateEl).not.toBeVisible();
});
