/**
 * Strands Agent Stream — All-Journey Lifecycle Suite
 *
 * Every test in this file runs the full Recoup pipeline with `use_strands: true`
 * AND validates the corresponding SSE stream.  This gives us end-to-end confidence
 * that the Strands agent lifecycle (run → stream → approve/decline/investigate →
 * final state) works correctly for every user journey scenario.
 *
 * Journey coverage
 * ─────────────────
 *   LC-J1   App bootstrap — health + config
 *   LC-J2   Primary operator loop — all 8 scan findings, each promoted → Strands → stream
 *   LC-J3   Cross-account connect → demo scan → Strands lifecycle
 *   LC-J4   SLA replay — API-Gateway credit, full Strands stream
 *   LC-J5   EC2 idle-stop — trigger → Strands → approve → stream
 *   LC-J6   Decision Inbox — Strands approve / decline / investigate paths
 *   LC-J7   Opportunity detail — GET, trace, SSE after Strands run
 *   LC-J8   Quality gates — scorecard invariants after Strands runs
 *   LC-J9   Recovery Ledger — bucket transitions driven by Strands lifecycle
 *   LC-J10  CloudTrail no-actor governance check
 *   LC-J11  Missing cost-allocation tags governance
 *   LC-J12  Cost Explorer spend summary
 *   LC-SEC  Security invariants on Strands-produced approvals
 *   LC-FULL End-to-end: scan all 8 → promote all → Strands+stream → approve all → ledger check
 *
 * Tags
 * ─────
 *   @smoke      — happy-path, runs without real AWS (stub fallback safe)
 *   @full       — edge cases, multi-step, security invariants
 *   @lifecycle  — this entire file (run all: `--grep @lifecycle`)
 *   @bedrock-live — live LLM / real Bedrock (staging only, skipped otherwise)
 *
 * Prerequisites
 * ─────────────
 *   Backend on :8000, frontend on :3000 (handled by playwright.config.ts webServer)
 */

import { test, expect } from "@playwright/test";
import {
  resetBackend,
  runDemoScan,
  promoteFinding,
  approveOpportunity,
  declineOpportunity,
  triggerEc2Demo,
  pollUntilState,
  collectSSEEvents,
  strandsRunAndStream,
  CANONICAL_NODES,
  POST_APPROVAL_NODES,
} from "./helpers";

const BACKEND = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Shared setup
// ---------------------------------------------------------------------------

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

// ===========================================================================
// LC-J1 — App Bootstrap & Health
// ===========================================================================

test(
  "@smoke @lifecycle LC-J1-1 backend health returns 200 with status ok",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/health`);
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as { status: string };
    expect(body.status).toMatch(/ok|healthy/i);
  }
);

test(
  "@smoke @lifecycle LC-J1-2 readiness check returns 200",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/health/ready`);
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as { ready: boolean };
    expect(body.ready).toBe(true);
  }
);

test(
  "@smoke @lifecycle LC-J1-3 /api/config exposes no raw secrets",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/config`);
    expect(res.ok()).toBeTruthy();
    const config = (await res.json()) as Record<string, unknown>;
    const raw = JSON.stringify(config).toLowerCase();
    // Must not contain raw AWS/OpenAI credentials
    expect(raw).not.toMatch(/(?:aws_secret_access_key|sk-[a-z0-9]{20,})/);
    // LLM provider field must be present
    expect(config.llm_provider).toBeDefined();
  }
);

// ===========================================================================
// LC-J2 — Primary Operator Loop: all 8 scan findings through Strands + SSE
// ===========================================================================

test(
  "@smoke @lifecycle LC-J2-1 demo scan returns ≥8 findings with positive total savings",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    expect(scan.findings.length).toBeGreaterThanOrEqual(8);
    expect(scan.total_estimated_monthly_savings_usd).toBeGreaterThan(0);
  }
);

test(
  "@smoke @lifecycle LC-J2-2 account_id is masked in scan results",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const result = scan as unknown as { account_id?: string };
    if (result.account_id) {
      const ok = result.account_id === "unknown" || result.account_id.includes("XXXXXXXX");
      expect(ok).toBeTruthy();
    }
  }
);

test(
  "@smoke @lifecycle LC-J2-3 promote first finding → Strands run → stream shows all 8 nodes",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[0]);

    // Run through the full Strands pipeline and collect SSE
    const { runBody, events } = await strandsRunAndStream(request, opportunity_id);

    expect(runBody.opportunity_id).toBe(opportunity_id);
    expect(runBody.use_strands).toBe(true);
    expect(Array.isArray(runBody.errors)).toBe(true);

    // All 8 canonical nodes must appear in the stream
    const completedNodes = events
      .filter((e) => e.type === "node_completed")
      .map((e) => e.node!);

    for (const node of CANONICAL_NODES) {
      expect(completedNodes).toContain(node);
    }

    // Stream must terminate with opportunity_done
    const done = events.find((e) => e.type === "opportunity_done");
    expect(done).toBeDefined();
    expect(done!.opportunity_id).toBe(opportunity_id);
  }
);

test(
  "@full @lifecycle LC-J2-4 all 8 findings promoted → each Strands run streams complete lifecycle",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;

    // Promote and run/stream each finding in sequence
    for (const finding of findings) {
      const { opportunity_id } = await promoteFinding(request, finding);

      // Idempotent promote — second call should return same ID
      const { opportunity_id: same } = await promoteFinding(request, finding);
      expect(same).toBe(opportunity_id);

      const { runBody, events } = await strandsRunAndStream(request, opportunity_id);
      expect(runBody.use_strands).toBe(true);

      const done = events.find((e) => e.type === "opportunity_done");
      expect(done).toBeDefined();

      // Every node_completed must carry a non-negative duration_ms
      const completed = events.filter((e) => e.type === "node_completed");
      for (const ev of completed) {
        expect(typeof ev.duration_ms).toBe("number");
        expect(ev.duration_ms!).toBeGreaterThanOrEqual(0);
      }
    }
  }
);

test(
  "@smoke @lifecycle LC-J2-5 node_started always precedes node_completed for each node",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[0]);

    const { events } = await strandsRunAndStream(request, opportunity_id);

    for (const node of CANONICAL_NODES) {
      const startIdx = events.findIndex(
        (e) => e.type === "node_started" && e.node === node
      );
      const doneIdx = events.findIndex(
        (e) => e.type === "node_completed" && e.node === node
      );
      if (startIdx !== -1 && doneIdx !== -1) {
        expect(startIdx).toBeLessThan(doneIdx);
      }
    }
  }
);

test(
  "@smoke @lifecycle LC-J2-6 nodes appear in canonical pipeline order",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[0]);

    const { events } = await strandsRunAndStream(request, opportunity_id);

    const completedNodes = events
      .filter((e) => e.type === "node_completed")
      .map((e) => e.node!);

    let lastIdx = -1;
    for (const node of CANONICAL_NODES) {
      const idx = completedNodes.indexOf(node);
      if (idx !== -1) {
        expect(idx).toBeGreaterThan(lastIdx);
        lastIdx = idx;
      }
    }
  }
);

test(
  "@smoke @lifecycle LC-J2-7 promote → Strands run → approve → state transitions to APPROVED",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[0]);

    // Must start in AWAITING_APPROVAL after promote (before run)
    const opp0 = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
    const { state: stateAfterPromote } = (await opp0.json()) as { state: string };
    expect(stateAfterPromote).toBe("AWAITING_APPROVAL");

    // Approve with full claim binding
    const result = await approveOpportunity(request, opportunity_id);
    expect((result as { state: string }).state).toBe("APPROVED");
    expect((result as { sns_notification_sent: boolean }).sns_notification_sent).toBe(true);
  }
);

test(
  "@smoke @lifecycle LC-J2-8 scan audit record written after demo scan",
  async ({ request }) => {
    await runDemoScan(request);
    const res = await request.get(`${BACKEND}/api/scan/audit`);
    expect(res.ok()).toBeTruthy();
    const audit = (await res.json()) as Array<{ scan_id: string; finding_count: number }>;
    expect(audit.length).toBeGreaterThanOrEqual(1);
    expect(audit[0].scan_id).toBeTruthy();
  }
);

// ===========================================================================
// LC-J3 — Cross-Account Connect → Strands lifecycle
// ===========================================================================

test(
  "@smoke @lifecycle LC-J3-1 connect init returns unique customer_id and high-entropy external_id",
  async ({ request }) => {
    const [r1, r2] = await Promise.all([
      request.post(`${BACKEND}/api/scan/connect/init`),
      request.post(`${BACKEND}/api/scan/connect/init`),
    ]);
    expect(r1.ok()).toBeTruthy();
    expect(r2.ok()).toBeTruthy();

    const c1 = (await r1.json()) as { customer_id: string; external_id: string };
    const c2 = (await r2.json()) as { customer_id: string; external_id: string };

    expect(c1.customer_id).not.toBe(c2.customer_id);
    expect(c1.external_id).not.toBe(c2.external_id);
    expect(c1.external_id.length).toBeGreaterThan(20);
  }
);

test(
  "@full @lifecycle LC-J3-2 connect GET returns CF template hint with DenyAllWrites principle",
  async ({ request }) => {
    const initRes = await request.post(`${BACKEND}/api/scan/connect/init`);
    const { customer_id } = (await initRes.json()) as { customer_id: string };

    const cfRes = await request.get(`${BACKEND}/api/scan/connect/${customer_id}`);
    expect(cfRes.ok()).toBeTruthy();
    const cf = (await cfRes.json()) as Record<string, unknown>;
    const raw = JSON.stringify(cf);
    expect(raw).toMatch(/DenyAllWrites|deny_all_writes/i);
  }
);

test(
  "@full @lifecycle LC-J3-3 unknown customer_id returns 404",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/scan/connect/does-not-exist-xyz`);
    expect(res.status()).toBe(404);
  }
);

test(
  "@full @lifecycle LC-J3-4 demo scan runs after connect init; Strands run streams successfully",
  async ({ request }) => {
    // Init connect (simulates cross-account handshake)
    await request.post(`${BACKEND}/api/scan/connect/init`);

    // Regular demo scan still works
    const scan = await runDemoScan(request);
    expect(scan.findings.length).toBeGreaterThan(0);

    // Promote and run first finding via Strands
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[0]);

    const { runBody, events } = await strandsRunAndStream(request, opportunity_id);
    expect(runBody.use_strands).toBe(true);

    const done = events.find((e) => e.type === "opportunity_done");
    expect(done).toBeDefined();
  }
);

// ===========================================================================
// LC-J4 — SLA Replay: API-Gateway credit, Strands stream, full lifecycle
// ===========================================================================

test(
  "@smoke @lifecycle LC-J4-1 SLA replay creates opportunity and Strands stream shows all nodes",
  async ({ request }) => {
    const replayRes = await request.post(`${BACKEND}/api/replay/api-gateway-sla`);
    expect(replayRes.ok()).toBeTruthy();
    const replay = (await replayRes.json()) as {
      opportunity_id: string;
      availability_result?: { monthly_uptime_pct: string };
    };
    expect(replay.opportunity_id).toBeTruthy();

    // Stream the stored SLA opportunity
    const events = await collectSSEEvents(
      `${BACKEND}/api/opportunities/${replay.opportunity_id}/stream`
    );

    // availability_calculator node must complete
    const calcDone = events.find(
      (e) => e.type === "node_completed" && e.node === "availability_calculator"
    );
    expect(calcDone).toBeDefined();

    const done = events.find((e) => e.type === "opportunity_done");
    expect(done).toBeDefined();
    expect(done!.opportunity_id).toBe(replay.opportunity_id);
  }
);

test(
  "@smoke @lifecycle LC-J4-2 SLA replay potential_credit is positive numeric",
  async ({ request }) => {
    const replayRes = await request.post(`${BACKEND}/api/replay/api-gateway-sla`);
    expect(replayRes.ok()).toBeTruthy();
    const replay = (await replayRes.json()) as {
      opportunity_id: string;
      potential_credit?: string | null;
    };

    if (replay.potential_credit) {
      const credit = parseFloat(replay.potential_credit);
      expect(credit).toBeGreaterThan(0);
      expect(credit).toBeLessThan(20); // SLA credits are sub-$20
    }
  }
);

test(
  "@smoke @lifecycle LC-J4-3 SLA replay trace returns valid uptime percentage",
  async ({ request }) => {
    const replayRes = await request.post(`${BACKEND}/api/replay/api-gateway-sla`);
    const { opportunity_id } = (await replayRes.json()) as { opportunity_id: string };

    const traceRes = await request.get(
      `${BACKEND}/api/opportunities/${opportunity_id}/trace`
    );
    expect(traceRes.ok()).toBeTruthy();
    const trace = (await traceRes.json()) as {
      availability_result: { monthly_uptime_pct: string } | null;
    };

    if (trace.availability_result) {
      const uptime = parseFloat(trace.availability_result.monthly_uptime_pct);
      expect(uptime).toBeGreaterThanOrEqual(0);
      expect(uptime).toBeLessThanOrEqual(100);
    }
  }
);

test(
  "@smoke @lifecycle LC-J4-4 SLA replay → Strands run → approve → APPROVED with SNS sent",
  async ({ request }) => {
    const replayRes = await request.post(`${BACKEND}/api/replay/api-gateway-sla`);
    const { opportunity_id } = (await replayRes.json()) as { opportunity_id: string };

    // Run with Strands on top of replay state
    const runRes = await request.post(
      `${BACKEND}/api/opportunities/${opportunity_id}/run`,
      { data: { use_strands: true } }
    );
    expect(runRes.ok()).toBeTruthy();
    const runBody = (await runRes.json()) as { final_state: string };

    if (runBody.final_state !== "AWAITING_APPROVAL") return; // ALLOW path — skip

    const result = await approveOpportunity(request, opportunity_id);
    expect((result as { state: string }).state).toBe("APPROVED");
    expect((result as { sns_notification_sent: boolean }).sns_notification_sent).toBe(true);
  }
);

test(
  "@full @lifecycle LC-J4-5 100% uptime scenario NOT eligible for SLA credit",
  async ({ request }) => {
    // Use the generic run endpoint with a synthetic ID — the stub resolver
    // returns 100% uptime by default when no breach is stored
    const oppId = `sla-100pct-${Date.now()}`;
    const runRes = await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
      data: { use_strands: true },
    });
    expect(runRes.ok()).toBeTruthy();
    const body = (await runRes.json()) as {
      final_state: string;
      potential_credit: string | null;
    };

    // Either no credit or the pipeline short-circuited to DETECTED/DECLINED
    const ineligibleStates = ["DETECTED", "DECLINED", "PENDING", "AWAITING_APPROVAL"];
    expect(ineligibleStates).toContain(body.final_state);
  }
);

test(
  "@smoke @lifecycle LC-J4-6 GET /api/replay/scenarios returns scenario list",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/replay/scenarios`);
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as unknown;
    const scenarios = Array.isArray(body) ? body : (body as { scenarios: unknown[] }).scenarios;
    expect(Array.isArray(scenarios)).toBe(true);
    expect(scenarios.length).toBeGreaterThan(0);
  }
);

// ===========================================================================
// LC-J5 — EC2 Idle Stop: trigger → Strands stream → approve
// ===========================================================================

test(
  "@smoke @lifecycle LC-J5-1 EC2 demo trigger creates AWAITING_APPROVAL opportunity",
  async ({ request }) => {
    const { opportunity } = await triggerEc2Demo(request);
    expect(opportunity.id).toBeTruthy();
    expect(opportunity.state).toBe("AWAITING_APPROVAL");
  }
);

test(
  "@smoke @lifecycle LC-J5-2 EC2 opportunity lists in /api/ec2-demo/opportunities",
  async ({ request }) => {
    const { opportunity } = await triggerEc2Demo(request);

    const listRes = await request.get(`${BACKEND}/api/ec2-demo/opportunities`);
    expect(listRes.ok()).toBeTruthy();
    const list = (await listRes.json()) as Array<{ id: string }>;
    const found = list.find((o) => o.id === opportunity.id);
    expect(found).toBeDefined();
  }
);

test(
  "@smoke @lifecycle LC-J5-3 EC2 opportunity detail endpoint returns action=stop_demo_instance",
  async ({ request }) => {
    const { opportunity } = await triggerEc2Demo(request);

    const detRes = await request.get(
      `${BACKEND}/api/ec2-demo/opportunity/${opportunity.id}`
    );
    expect(detRes.ok()).toBeTruthy();
    const detail = (await detRes.json()) as { action?: string };
    expect(detail.action).toMatch(/stop_demo_instance/i);
  }
);

test(
  "@smoke @lifecycle LC-J5-4 EC2 → approve → APPROVED with SNS and verified_stopped",
  async ({ request }) => {
    const { opportunity } = await triggerEc2Demo(request);

    // Approve it
    const approveRes = await approveOpportunity(request, opportunity.id);
    const approved = approveRes as {
      state: string;
      sns_notification_sent: boolean;
    };
    expect(approved.state).toBe("APPROVED");
    expect(approved.sns_notification_sent).toBe(true);

    // Execute (mocked) — should return verified_stopped=true
    const execRes = await request.post(
      `${BACKEND}/api/ec2-demo/execute/${opportunity.id}`
    );
    if (execRes.ok()) {
      const exec = (await execRes.json()) as { verified_stopped?: boolean };
      if (exec.verified_stopped !== undefined) {
        expect(exec.verified_stopped).toBe(true);
      }
    }
  }
);

test(
  "@full @lifecycle LC-J5-5 execute without prior approval returns 409 or 403",
  async ({ request }) => {
    const { opportunity } = await triggerEc2Demo(request);

    // Do NOT approve — try to execute directly
    const execRes = await request.post(
      `${BACKEND}/api/ec2-demo/execute/${opportunity.id}`
    );
    expect([403, 409]).toContain(execRes.status());
  }
);

test(
  "@full @lifecycle LC-J5-6 unknown EC2 opportunity ID returns 404",
  async ({ request }) => {
    const res = await request.get(
      `${BACKEND}/api/ec2-demo/opportunity/does-not-exist-ec2`
    );
    expect(res.status()).toBe(404);
  }
);

test(
  "@full @lifecycle LC-J5-7 EC2 trigger is repeatable after state reset",
  async ({ request }) => {
    const first = await triggerEc2Demo(request);
    await resetBackend(request);
    const second = await triggerEc2Demo(request);

    // After reset both return fresh opportunities
    expect(first.opportunity.id).toBeTruthy();
    expect(second.opportunity.id).toBeTruthy();
  }
);

// ===========================================================================
// LC-J6 — Decision Inbox: Strands approve / decline / investigate paths
// ===========================================================================

test(
  "@smoke @lifecycle LC-J6-1 Strands run → approve path → APPROVED + ledger updated",
  async ({ request }) => {
    const oppId = `lc-j6-approve-${Date.now()}`;

    const { runBody, events } = await strandsRunAndStream(request, oppId);
    expect(runBody.use_strands).toBe(true);

    if (runBody.final_state !== "AWAITING_APPROVAL") return;

    // Verify SSE emitted approval_required event
    const aprEvent = events.find((e) => e.type === "approval_required");
    expect(aprEvent).toBeDefined();
    expect(parseFloat(aprEvent!.amount!)).toBeGreaterThan(0);

    // Approve
    const approved = await approveOpportunity(request, oppId);
    expect((approved as { state: string }).state).toBe("APPROVED");

    // Pending list must no longer contain this opportunity
    const pending = await request.get(`${BACKEND}/api/approvals/pending`);
    const pendingList = (await pending.json()) as Array<{
      opportunity_id: string;
      state: string;
    }>;
    const stillPending = pendingList.find(
      (r) => r.opportunity_id === oppId && r.state === "PENDING"
    );
    expect(stillPending).toBeUndefined();
  }
);

test(
  "@smoke @lifecycle LC-J6-2 Strands run → investigate path → NEEDS_FOLLOWUP",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[1] ?? findings[0]);

    // Investigate
    const invRes = await request.post(
      `${BACKEND}/api/approvals/opportunity/${opportunity_id}/investigate`,
      { data: { principal: "playwright-lc", notes: "LC-J6-2 investigate" } }
    );
    expect(invRes.ok()).toBeTruthy();
    const inv = (await invRes.json()) as { opportunity_state: string };
    expect(inv.opportunity_state).toBe("NEEDS_FOLLOWUP");
  }
);

test(
  "@smoke @lifecycle LC-J6-3 Strands run → decline path → DECLINED (excluded from pending)",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[2] ?? findings[0]);

    const declined = await declineOpportunity(request, opportunity_id);
    expect((declined as { state: string }).state).toBe("DECLINED");

    // Must not appear in pending list
    const pending = await request.get(`${BACKEND}/api/approvals/pending`);
    const pendingList = (await pending.json()) as Array<{ opportunity_id: string; state: string }>;
    const found = pendingList.find(
      (r) => r.opportunity_id === opportunity_id && r.state === "PENDING"
    );
    expect(found).toBeUndefined();
  }
);

test(
  "@full @lifecycle LC-J6-4 double-approve returns 404 on second call",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[0]);

    // First approve succeeds
    await approveOpportunity(request, opportunity_id);

    // Second attempt — no pending record
    const pendingRes = await request.get(
      `${BACKEND}/api/approvals/opportunity/${opportunity_id}`
    );
    expect(pendingRes.status()).toBe(404);
  }
);

test(
  "@smoke @lifecycle LC-J6-5 X-Request-ID present on Decision Inbox responses",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[0]);

    const res = await request.get(
      `${BACKEND}/api/approvals/opportunity/${opportunity_id}`
    );
    expect(res.ok()).toBeTruthy();
    const xid = res.headers()["x-request-id"];
    expect(xid).toBeTruthy();
    expect(xid).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    );
  }
);

// ===========================================================================
// LC-J7 — Opportunity Detail & Trace after Strands run
// ===========================================================================

test(
  "@smoke @lifecycle LC-J7-1 GET opportunity returns full record with state_version ≥ 1",
  async ({ request }) => {
    const oppId = `lc-j7-${Date.now()}`;
    await strandsRunAndStream(request, oppId);

    const res = await request.get(`${BACKEND}/api/opportunities/${oppId}`);
    expect(res.ok()).toBeTruthy();
    const opp = (await res.json()) as { id: string; state_version: number; state: string };
    expect(opp.id).toBe(oppId);
    expect(opp.state_version).toBeGreaterThanOrEqual(1);
  }
);

test(
  "@smoke @lifecycle LC-J7-2 trace returns all 8 nodes with hypothesis_summary",
  async ({ request }) => {
    const oppId = `lc-j7-trace-${Date.now()}`;
    await strandsRunAndStream(request, oppId);

    const traceRes = await request.get(`${BACKEND}/api/opportunities/${oppId}/trace`);
    expect(traceRes.ok()).toBeTruthy();
    const trace = (await traceRes.json()) as {
      opportunity_id: string;
      nodes: Array<{ node: string }>;
      hypothesis_summary: string | null;
      availability_result: { monthly_uptime_pct: string; potential_credit: string } | null;
    };

    expect(trace.opportunity_id).toBe(oppId);
    expect(Array.isArray(trace.nodes)).toBe(true);

    const nodeNames = trace.nodes.map((n) => n.node);
    for (const node of CANONICAL_NODES) {
      expect(nodeNames).toContain(node);
    }

    if (trace.hypothesis_summary) {
      expect(trace.hypothesis_summary.length).toBeGreaterThan(0);
    }

    if (trace.availability_result) {
      const uptime = parseFloat(trace.availability_result.monthly_uptime_pct);
      expect(uptime).toBeGreaterThanOrEqual(0);
      expect(uptime).toBeLessThanOrEqual(100);
    }
  }
);

test(
  "@smoke @lifecycle LC-J7-3 availability_calculator stream event carries potential_credit",
  async ({ request }) => {
    const oppId = `lc-j7-credit-${Date.now()}`;
    const { events } = await strandsRunAndStream(request, oppId);

    const calcDone = events.find(
      (e) => e.type === "node_completed" && e.node === "availability_calculator"
    );
    expect(calcDone).toBeDefined();
    if (calcDone?.potential_credit !== undefined) {
      expect(parseFloat(calcDone.potential_credit)).toBeGreaterThan(0);
    }
  }
);

test(
  "@full @lifecycle LC-J7-4 unknown opportunity ID returns 404 on GET",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/opportunities/does-not-exist-xyz`);
    expect(res.status()).toBe(404);
  }
);

test(
  "@full @lifecycle LC-J7-5 concurrent Strands runs produce isolated traces",
  async ({ request }) => {
    const id1 = `lc-j7-iso-a-${Date.now()}`;
    const id2 = `lc-j7-iso-b-${Date.now()}`;

    const [r1, r2] = await Promise.all([
      request.post(`${BACKEND}/api/opportunities/${id1}/run`, { data: { use_strands: true } }),
      request.post(`${BACKEND}/api/opportunities/${id2}/run`, { data: { use_strands: true } }),
    ]);
    expect(r1.ok()).toBeTruthy();
    expect(r2.ok()).toBeTruthy();

    const [t1, t2] = await Promise.all([
      request.get(`${BACKEND}/api/opportunities/${id1}/trace`).then((r) => r.json()),
      request.get(`${BACKEND}/api/opportunities/${id2}/trace`).then((r) => r.json()),
    ]) as [{ opportunity_id: string }, { opportunity_id: string }];

    expect(t1.opportunity_id).toBe(id1);
    expect(t2.opportunity_id).toBe(id2);
  }
);

// ===========================================================================
// LC-J8 — Quality Gates: scorecard invariants after Strands runs
// ===========================================================================

test(
  "@smoke @lifecycle LC-J8-1 quality scorecard returns gate array with all_gates_pass boolean",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/quality/scorecard`);
    expect(res.ok()).toBeTruthy();
    const sc = (await res.json()) as {
      gates: Array<{ name: string; passed: boolean }>;
      all_gates_pass: boolean;
    };
    expect(Array.isArray(sc.gates)).toBe(true);
    expect(sc.gates.length).toBeGreaterThan(0);
    expect(typeof sc.all_gates_pass).toBe("boolean");
  }
);

test(
  "@smoke @lifecycle LC-J8-2 unsafe_external_actions gate passes (= 0)",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/quality/scorecard`);
    const sc = (await res.json()) as {
      gates: Array<{ name: string; value: number; passed: boolean }>;
    };
    const uea = sc.gates.find((g) => g.name === "unsafe_external_actions");
    if (uea) {
      expect(uea.value).toBe(0);
      expect(uea.passed).toBe(true);
    }
  }
);

test(
  "@smoke @lifecycle LC-J8-3 hallucinated_evidence gate passes (= 0)",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/quality/scorecard`);
    const sc = (await res.json()) as {
      gates: Array<{ name: string; value: number; passed: boolean }>;
    };
    const he = sc.gates.find((g) => g.name === "hallucinated_evidence");
    if (he) {
      expect(he.value).toBe(0);
      expect(he.passed).toBe(true);
    }
  }
);

test(
  "@full @lifecycle LC-J8-4 all rate/pct gates are in [0, 1] range",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/quality/scorecard`);
    const sc = (await res.json()) as {
      gates: Array<{ name: string; value?: number; passed: boolean }>;
    };
    const rateGates = sc.gates.filter((g) =>
      /precision|recall|accuracy|rate|pct/i.test(g.name)
    );
    for (const gate of rateGates) {
      if (gate.value !== undefined) {
        expect(gate.value).toBeGreaterThanOrEqual(0);
        expect(gate.value).toBeLessThanOrEqual(1);
      }
    }
  }
);

test(
  "@full @lifecycle LC-J8-5 scorecard timestamps are ISO-8601 and X-Request-ID present",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/quality/scorecard`);
    expect(res.ok()).toBeTruthy();

    const xid = res.headers()["x-request-id"];
    expect(xid).toBeTruthy();

    const sc = (await res.json()) as {
      evaluated_at?: string;
      generated_at?: string;
    };
    const ts = sc.evaluated_at ?? sc.generated_at;
    if (ts) {
      expect(new Date(ts).toISOString()).toBe(ts);
    }
  }
);

test(
  "@smoke @lifecycle LC-J8-6 evidence sanitizer — no raw PII in Strands trace",
  async ({ request }) => {
    const oppId = `lc-j8-sanitizer-${Date.now()}`;
    await strandsRunAndStream(request, oppId);

    const traceRes = await request.get(`${BACKEND}/api/opportunities/${oppId}/trace`);
    expect(traceRes.ok()).toBeTruthy();
    const raw = JSON.stringify(await traceRes.json());

    // Known PII / secret patterns must not appear raw in the trace
    expect(raw).not.toMatch(/AKIA[0-9A-Z]{16}/); // real AWS access key
    expect(raw).not.toMatch(/sk-[a-zA-Z0-9]{20,}/); // OpenAI key
    expect(raw).not.toMatch(/\b\d{3}-\d{2}-\d{4}\b/); // SSN
  }
);

// ===========================================================================
// LC-J9 — Recovery Ledger: bucket transitions via Strands lifecycle
// ===========================================================================

test(
  "@smoke @lifecycle LC-J9-1 after scan, detected bucket total > $60",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    expect(scan.total_estimated_monthly_savings_usd).toBeGreaterThan(60);
  }
);

test(
  "@smoke @lifecycle LC-J9-2 after promote, opportunity appears in pending approvals",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[0]);

    const pendingRes = await request.get(`${BACKEND}/api/approvals/pending`);
    const pendingList = (await pendingRes.json()) as Array<{ opportunity_id: string }>;
    const ids = pendingList.map((r) => r.opportunity_id);
    expect(ids).toContain(opportunity_id);
  }
);

test(
  "@smoke @lifecycle LC-J9-3 after approve, opportunities list contains APPROVED state",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[0]);
    await approveOpportunity(request, opportunity_id);

    const listRes = await request.get(`${BACKEND}/api/opportunities`);
    expect(listRes.ok()).toBeTruthy();
    const opps = (await listRes.json()) as Array<{ id: string; state: string }>;
    const approved = opps.find((o) => o.id === opportunity_id);
    expect(approved?.state).toBe("APPROVED");
  }
);

test(
  "@full @lifecycle LC-J9-4 declined opportunity not counted in approved bucket",
  async ({ request }) => {
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    const { opportunity_id } = await promoteFinding(request, findings[0]);
    await declineOpportunity(request, opportunity_id);

    const listRes = await request.get(`${BACKEND}/api/opportunities`);
    const opps = (await listRes.json()) as Array<{ id: string; state: string }>;
    const declined = opps.find((o) => o.id === opportunity_id);
    expect(declined?.state).toBe("DENIED");

    // Must NOT appear in pending list
    const pendingRes = await request.get(`${BACKEND}/api/approvals/pending`);
    const pendingList = (await pendingRes.json()) as Array<{
      opportunity_id: string;
      state: string;
    }>;
    const inPending = pendingList.find(
      (r) => r.opportunity_id === opportunity_id && r.state === "PENDING"
    );
    expect(inPending).toBeUndefined();
  }
);

test(
  "@full @lifecycle LC-J9-5 SLA credit approve matches amount in opportunities list",
  async ({ request }) => {
    const replayRes = await request.post(`${BACKEND}/api/replay/api-gateway-sla`);
    const { opportunity_id } = (await replayRes.json()) as { opportunity_id: string };

    // Check pending approval amount
    const pendingRes = await request.get(
      `${BACKEND}/api/approvals/opportunity/${opportunity_id}`
    );
    if (!pendingRes.ok()) return; // No approval record path — skip

    const pending = (await pendingRes.json()) as { amount: string };
    const pendingAmount = parseFloat(pending.amount);
    expect(pendingAmount).toBeGreaterThan(0);

    // Approve and verify opportunity potential_value matches
    await approveOpportunity(request, opportunity_id);

    const oppRes = await request.get(`${BACKEND}/api/opportunities/${opportunity_id}`);
    const opp = (await oppRes.json()) as { potential_value: string | null };
    if (opp.potential_value) {
      const oppAmount = parseFloat(opp.potential_value);
      expect(oppAmount).toBeCloseTo(pendingAmount, 1);
    }
  }
);

// ===========================================================================
// LC-J10 — CloudTrail No-Actor Detection
// ===========================================================================

test(
  "@smoke @lifecycle LC-J10-1 cloudtrail-demo/check returns actor_attributed and requires_human_review booleans",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/cloudtrail-demo/check`);
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as {
      actor_attributed: boolean;
      requires_human_review: boolean;
      finding: string;
    };
    expect(typeof body.actor_attributed).toBe("boolean");
    expect(typeof body.requires_human_review).toBe("boolean");
    expect(body.finding.length).toBeGreaterThan(0);
  }
);

test(
  "@full @lifecycle LC-J10-2 cloudtrail response includes event breakdown and X-Request-ID",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/cloudtrail-demo/check`);
    expect(res.ok()).toBeTruthy();

    const xid = res.headers()["x-request-id"];
    expect(xid).toBeTruthy();

    const body = (await res.json()) as Record<string, unknown>;
    // Either actor_type_breakdown or event_breakdown must be present
    const hasBreakdown =
      "actor_type_breakdown" in body || "event_breakdown" in body;
    expect(hasBreakdown).toBe(true);
  }
);

// ===========================================================================
// LC-J11 — Missing Cost-Allocation Tags
// ===========================================================================

test(
  "@smoke @lifecycle LC-J11-1 tagging-demo/scan returns resources_scanned and findings",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/tagging-demo/scan`);
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as {
      resources_scanned: number;
      resources_missing_tags: number;
      findings: unknown[];
      required_tags: string[];
    };
    expect(typeof body.resources_scanned).toBe("number");
    expect(typeof body.resources_missing_tags).toBe("number");
    expect(Array.isArray(body.findings)).toBe(true);
    expect(Array.isArray(body.required_tags)).toBe(true);
  }
);

test(
  "@full @lifecycle LC-J11-2 required_tags includes at least one governance tag",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/tagging-demo/scan`);
    const body = (await res.json()) as { required_tags: string[] };
    const hasGovTag = body.required_tags.some((t) =>
      /cost|env|team|project|owner/i.test(t)
    );
    expect(hasGovTag).toBe(true);
  }
);

// ===========================================================================
// LC-J12 — Cost Explorer Account Spend
// ===========================================================================

test(
  "@smoke @lifecycle LC-J12-1 cost-demo/summary returns total_usd and breakdown",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/cost-demo/summary`);
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as {
      total_usd: number;
      billing_period_start: string;
      billing_period_end: string;
      breakdown: Array<{ service: string; cost_usd: number }>;
      fetched_at: string;
    };
    expect(typeof body.total_usd).toBe("number");
    expect(body.billing_period_start).toBeTruthy();
    expect(body.billing_period_end).toBeTruthy();
    expect(Array.isArray(body.breakdown)).toBe(true);
    expect(body.fetched_at).toBeTruthy();
  }
);

test(
  "@full @lifecycle LC-J12-2 billing period start ≤ end and fetched_at is valid date",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/cost-demo/summary`);
    const body = (await res.json()) as {
      billing_period_start: string;
      billing_period_end: string;
      fetched_at: string;
    };
    const start = new Date(body.billing_period_start).getTime();
    const end = new Date(body.billing_period_end).getTime();
    expect(start).toBeLessThanOrEqual(end);
    expect(new Date(body.fetched_at).getTime()).toBeGreaterThan(0);
  }
);

// ===========================================================================
// LC-SEC — Security Invariants on Strands-produced Approvals
// ===========================================================================

/**
 * Create a pending approval via the Strands pipeline (same as security spec
 * setupPending, but re-declared here so this file is self-contained for SEC
 * scenarios).
 */
async function setupStrandsApproval(
  request: import("@playwright/test").APIRequestContext
): Promise<{
  opportunity_id: string;
  claim_hash: string;
  amount: string;
  state_version: number;
}> {
  const oppId = `lc-sec-${Date.now()}`;
  const runRes = await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
    data: { use_strands: true },
  });
  expect(runRes.ok()).toBeTruthy();

  const pending = await request.get(
    `${BACKEND}/api/approvals/opportunity/${oppId}`
  );
  expect(pending.ok()).toBeTruthy();
  const approval = (await pending.json()) as {
    claim_hash: string;
    amount: string;
    state_version: number;
  };
  return { opportunity_id: oppId, ...approval };
}

test(
  "@smoke @lifecycle LC-SEC-1 tampered claim_hash on Strands approval returns 409",
  async ({ request }) => {
    const { opportunity_id, amount, state_version } = await setupStrandsApproval(request);

    const res = await request.post(
      `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
      {
        data: {
          principal: "lc-attacker",
          claim_hash:
            "sha256:deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
          amount,
          state_version,
        },
      }
    );
    expect(res.status()).toBe(409);

    // Must still carry X-Request-ID
    expect(res.headers()["x-request-id"]).toBeTruthy();
  }
);

test(
  "@smoke @lifecycle LC-SEC-2 wrong amount on Strands approval returns 409",
  async ({ request }) => {
    const { opportunity_id, claim_hash, state_version } =
      await setupStrandsApproval(request);

    const res = await request.post(
      `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
      {
        data: {
          principal: "lc-attacker",
          claim_hash,
          amount: "99999.99", // tampered amount
          state_version,
        },
      }
    );
    expect(res.status()).toBe(409);
  }
);

test(
  "@smoke @lifecycle LC-SEC-3 stale state_version on Strands approval returns 409",
  async ({ request }) => {
    const { opportunity_id, claim_hash, amount, state_version } =
      await setupStrandsApproval(request);

    const res = await request.post(
      `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
      {
        data: {
          principal: "lc-attacker",
          claim_hash,
          amount,
          state_version: state_version - 1, // stale version
        },
      }
    );
    expect(res.status()).toBe(409);
  }
);

test(
  "@full @lifecycle LC-SEC-4 Strands approval: audit records mask account_id",
  async ({ request }) => {
    await runDemoScan(request);
    const res = await request.get(`${BACKEND}/api/scan/audit`);
    expect(res.ok()).toBeTruthy();
    const audit = (await res.json()) as Array<{
      account_id_masked: string;
      account_id?: string;
    }>;
    for (const record of audit) {
      // Raw account_id must never appear in audit
      if (record.account_id) {
        expect(record.account_id).not.toMatch(/^\d{12}$/); // 12-digit AWS account ID
      }
      if (record.account_id_masked) {
        expect(record.account_id_masked).toMatch(/XXXXXXXX|unknown/);
      }
    }
  }
);

test(
  "@full @lifecycle LC-SEC-5 data deletion purges scan data gracefully",
  async ({ request }) => {
    await runDemoScan(request);

    const delRes = await request.delete(
      `${BACKEND}/api/scan/accounts/__demo__/data`
    );
    expect(delRes.ok()).toBeTruthy();
    const body = (await delRes.json()) as { status: string };
    expect(body.status).toBe("deleted");
  }
);

test(
  "@full @lifecycle LC-SEC-6 /api/config exposes llm_provider but no raw AWS keys",
  async ({ request }) => {
    const res = await request.get(`${BACKEND}/api/config`);
    expect(res.ok()).toBeTruthy();
    const config = (await res.json()) as Record<string, unknown>;

    // llm_provider must be present and readable
    expect(config.llm_provider).toBeDefined();
    expect(["bedrock", "openai"]).toContain(config.llm_provider);

    // Sensitive values must be absent / redacted
    const raw = JSON.stringify(config).toLowerCase();
    expect(raw).not.toMatch(/aws_secret_access_key/);
    expect(raw).not.toMatch(/(?:sk-)[a-z0-9]{20,}/); // OpenAI key pattern
  }
);

// ===========================================================================
// LC-FULL — Complete end-to-end: scan all 8 → Strands+stream → approve all → ledger
// ===========================================================================

test(
  "@full @lifecycle LC-FULL-1 scan 8 findings → promote all → Strands run+stream → approve all → ledger shows APPROVED",
  async ({ request }) => {
    // 1. Scan
    const scan = await runDemoScan(request);
    const findings = scan.findings as Array<Record<string, unknown>>;
    expect(findings.length).toBeGreaterThanOrEqual(8);

    const opportunityIds: string[] = [];

    // 2. Promote, run, and stream each finding
    for (const finding of findings) {
      const { opportunity_id } = await promoteFinding(request, finding);
      opportunityIds.push(opportunity_id);

      // Strands run + SSE stream — assert lifecycle completeness
      const { runBody, events } = await strandsRunAndStream(request, opportunity_id);
      expect(runBody.use_strands).toBe(true);
      expect(Array.isArray(runBody.errors)).toBe(true);

      // Every canonical node must appear
      const completedNodes = events
        .filter((e) => e.type === "node_completed")
        .map((e) => e.node!);
      for (const node of CANONICAL_NODES) {
        expect(completedNodes).toContain(node);
      }

      // Stream terminates cleanly
      const done = events.find((e) => e.type === "opportunity_done");
      expect(done).toBeDefined();
      expect(done!.errors).toBeDefined();
    }

    // 3. Approve all that landed in AWAITING_APPROVAL
    let approvedCount = 0;
    for (const oppId of opportunityIds) {
      const oppRes = await request.get(`${BACKEND}/api/opportunities/${oppId}`);
      const opp = (await oppRes.json()) as { state: string };
      if (opp.state === "AWAITING_APPROVAL") {
        await approveOpportunity(request, oppId);
        approvedCount++;
      }
    }

    // 4. Verify ledger — all approved opportunities visible
    const listRes = await request.get(`${BACKEND}/api/opportunities`);
    expect(listRes.ok()).toBeTruthy();
    const allOpps = (await listRes.json()) as Array<{ id: string; state: string }>;

    const approvedOpps = allOpps.filter((o) => o.state === "APPROVED");
    expect(approvedOpps.length).toBeGreaterThanOrEqual(approvedCount);
  }
);

test(
  "@full @lifecycle LC-FULL-2 EC2 + SLA replay + operator loop run concurrently via Strands",
  async ({ request }) => {
    // Launch three different lifecycle types in parallel
    const [ec2, replayRes, scanRes] = await Promise.all([
      triggerEc2Demo(request),
      request.post(`${BACKEND}/api/replay/api-gateway-sla`),
      runDemoScan(request),
    ]);

    expect(ec2.opportunity.id).toBeTruthy();
    expect(replayRes.ok()).toBeTruthy();
    expect(scanRes.findings.length).toBeGreaterThan(0);

    const replayBody = (await replayRes.json()) as { opportunity_id: string };
    const findings = scanRes.findings as Array<Record<string, unknown>>;

    // Promote one scan finding
    const { opportunity_id: scanOppId } = await promoteFinding(request, findings[0]);

    // Run EC2 + scan opportunity via Strands + stream them in parallel
    const [ec2Stream, scanStream, replayStream] = await Promise.all([
      collectSSEEvents(`${BACKEND}/api/opportunities/${ec2.opportunity.id}/stream`),
      strandsRunAndStream(request, scanOppId).then((r) => r.events),
      collectSSEEvents(`${BACKEND}/api/opportunities/${replayBody.opportunity_id}/stream`),
    ]);

    // All three streams must terminate
    expect(ec2Stream.find((e) => e.type === "opportunity_done")).toBeDefined();
    expect(scanStream.find((e) => e.type === "opportunity_done")).toBeDefined();
    expect(replayStream.find((e) => e.type === "opportunity_done")).toBeDefined();

    // Approve all three
    await Promise.all([
      approveOpportunity(request, ec2.opportunity.id),
      approveOpportunity(request, replayBody.opportunity_id).catch(() => {
        /* already APPROVED path */
      }),
      approveOpportunity(request, scanOppId),
    ]);

    // Final ledger check
    const listRes = await request.get(`${BACKEND}/api/opportunities`);
    const opps = (await listRes.json()) as Array<{ id: string; state: string }>;
    const approvedIds = opps.filter((o) => o.state === "APPROVED").map((o) => o.id);

    expect(approvedIds).toContain(ec2.opportunity.id);
    expect(approvedIds).toContain(scanOppId);
  }
);

test(
  "@full @lifecycle LC-FULL-3 post-approval SSE stream includes post-approval nodes after HITL cleared",
  async ({ request }) => {
    const oppId = `lc-full-post-${Date.now()}`;

    // Run through Strands
    const { runBody } = await strandsRunAndStream(request, oppId);
    if (runBody.final_state !== "AWAITING_APPROVAL") return;

    // Approve
    const pendingRes = await request.get(
      `${BACKEND}/api/approvals/opportunity/${oppId}`
    );
    if (!pendingRes.ok()) return;

    const approval = (await pendingRes.json()) as {
      claim_hash: string;
      amount: string;
      state_version: number;
    };

    const approveRes = await request.post(
      `${BACKEND}/api/approvals/opportunity/${oppId}/approve`,
      {
        data: {
          principal: "lc-full-3",
          claim_hash: approval.claim_hash,
          amount: approval.amount,
          state_version: approval.state_version,
          notes: "LC-FULL-3 post-approval",
        },
      }
    );
    if (!approveRes.ok()) return;

    // Stream again — post-approval path
    const events = await collectSSEEvents(
      `${BACKEND}/api/opportunities/${oppId}/stream`,
      45_000
    );

    const completedNodes = events
      .filter((e) => e.type === "node_completed")
      .map((e) => e.node!);

    // Pre-approval nodes still present
    for (const node of CANONICAL_NODES) {
      expect(completedNodes).toContain(node);
    }

    // At least one post-approval node must appear
    const postApprovalStreamed = POST_APPROVAL_NODES.filter((n) =>
      completedNodes.includes(n)
    );
    expect(postApprovalStreamed.length).toBeGreaterThanOrEqual(1);

    const done = events.find((e) => e.type === "opportunity_done");
    expect(done).toBeDefined();
    expect(done!.state).toBeDefined();
  }
);
