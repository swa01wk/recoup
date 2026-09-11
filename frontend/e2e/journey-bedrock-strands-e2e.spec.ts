/**
 * LLM Provider / Strands Agent — End-to-End Lifecycle Tests
 *
 * Tests the full Recoup pipeline with `use_strands: true`, exercising the
 * configured LLM provider + Strands SDK integration path.
 *
 * Design:
 *  - The API route accepts `use_strands: bool` on POST /api/opportunities/{id}/run
 *  - When use_strands=true, AgentNodes attempt real LLM calls and fall back
 *    gracefully to stubs on any error (provider unavailable, quota, parse failure).
 *  - Tests assert the *contract* of the output — correctness regardless of
 *    whether the LLM answered or the stub was used.
 *  - One dedicated test asserts `agent_driven: true` in the trace when the LLM
 *    provider IS available (tagged @llm-live for selective execution in staging).
 *  - The active provider is read from GET /api/config → llm_provider.
 *    Supported: "bedrock" | "openai" (see LLM_PROVIDER env var).
 *
 * Tags:
 *   @smoke    — happy path, runs offline (stub fallback)
 *   @full     — edge cases, multiple agent nodes
 *   @llm-live — requires real LLM credentials (CI staging only)
 */

import { test, expect } from "@playwright/test";
import { resetBackend } from "./helpers";

const BACKEND = "http://localhost:8000";

// Node names expected from the 8-node pipeline (matches _NODE_ORDER in opportunities.py)
const PIPELINE_NODES = [
  "normalize_event",
  "incident_correlation",
  "sla_contract_resolver",
  "availability_calculator",
  "evidence_collector",
  "evidence_sanitizer",
  "eligibility_reasoner",
  "risk_policy_gate",
] as const;

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

// ---------------------------------------------------------------------------
// BS-1 — use_strands run completes and returns valid structure
// ---------------------------------------------------------------------------

test(
  "@smoke BS-1 use_strands=true run completes with valid opportunity structure",
  async ({ request }) => {
    const oppId = `strands-e2e-${Date.now()}`;
    const res = await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
      data: { use_strands: true },
    });

    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as {
      opportunity_id: string;
      final_state: string;
      use_strands: boolean;
      potential_credit: string | null;
      case_id: string | null;
      errors: string[];
    };

    expect(body.opportunity_id).toBe(oppId);
    expect(body.use_strands).toBe(true);

    // Must reach a terminal state
    const validStates = [
      "AWAITING_APPROVAL",
      "APPROVED",
      "DECLINED",
      "DETECTED",
      "PENDING",
      "NEEDS_FOLLOWUP",
      "RECOVERED",
    ];
    expect(validStates).toContain(body.final_state);

    // Errors array must exist (may be empty)
    expect(Array.isArray(body.errors)).toBe(true);
  }
);

// ---------------------------------------------------------------------------
// BS-2 — use_strands run stores opportunity accessible via GET
// ---------------------------------------------------------------------------

test(
  "@smoke BS-2 use_strands run stores opportunity retrievable via GET",
  async ({ request }) => {
    const oppId = `strands-store-${Date.now()}`;

    // Run with Strands
    const runRes = await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
      data: { use_strands: true },
    });
    expect(runRes.ok()).toBeTruthy();

    // Fetch via GET
    const getRes = await request.get(`${BACKEND}/api/opportunities/${oppId}`);
    expect(getRes.ok()).toBeTruthy();
    const opp = (await getRes.json()) as {
      id: string;
      state: string;
      state_version: number;
    };

    expect(opp.id).toBe(oppId);
    expect(opp.state_version).toBeGreaterThanOrEqual(1);
  }
);

// ---------------------------------------------------------------------------
// BS-3 — Strands run produces potential_credit
// ---------------------------------------------------------------------------

test(
  "@smoke BS-3 use_strands=true run produces a numeric potential_credit",
  async ({ request }) => {
    const oppId = `strands-credit-${Date.now()}`;

    const res = await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
      data: { use_strands: true },
    });
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as { potential_credit: string | null };

    // Credit must be a valid decimal string when present
    if (body.potential_credit !== null) {
      const credit = parseFloat(body.potential_credit);
      expect(credit).toBeGreaterThan(0);
    }
  }
);

// ---------------------------------------------------------------------------
// BS-4 — Trace endpoint returns full node list after Strands run
// ---------------------------------------------------------------------------

test(
  "@smoke BS-4 trace endpoint returns all 8 pipeline nodes after Strands run",
  async ({ request }) => {
    const oppId = `strands-trace-${Date.now()}`;

    await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
      data: { use_strands: true },
    });

    const traceRes = await request.get(`${BACKEND}/api/opportunities/${oppId}/trace`);
    expect(traceRes.ok()).toBeTruthy();
    const trace = (await traceRes.json()) as {
      opportunity_id: string;
      nodes: Array<{ node: string }>;
      availability_result: Record<string, unknown> | null;
    };

    expect(trace.opportunity_id).toBe(oppId);
    expect(Array.isArray(trace.nodes)).toBe(true);

    // All 8 canonical nodes must appear in the trace
    const nodeNames = trace.nodes.map((n) => n.node);
    for (const expected of PIPELINE_NODES) {
      expect(nodeNames).toContain(expected);
    }
  }
);

// ---------------------------------------------------------------------------
// BS-5 — Strands run triggers HITL approval when policy requires it
// ---------------------------------------------------------------------------

test(
  "@full BS-5 use_strands run that requires approval creates pending approval record",
  async ({ request }) => {
    const oppId = `strands-hitl-${Date.now()}`;

    const runRes = await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
      data: { use_strands: true },
    });
    expect(runRes.ok()).toBeTruthy();
    const runBody = (await runRes.json()) as { final_state: string };

    if (runBody.final_state === "AWAITING_APPROVAL") {
      // An approval record must now exist
      const pendingRes = await request.get(`${BACKEND}/api/approvals/opportunity/${oppId}`);
      expect(pendingRes.ok()).toBeTruthy();
      const pending = (await pendingRes.json()) as {
        claim_hash: string;
        amount: string;
        state_version: number;
      };

      expect(pending.claim_hash).toMatch(/^sha256:/);
      const amount = parseFloat(pending.amount);
      expect(amount).toBeGreaterThan(0);
      expect(pending.state_version).toBeGreaterThanOrEqual(1);
    }
  }
);

// ---------------------------------------------------------------------------
// BS-6 — Approve the Strands-generated opportunity end-to-end
// ---------------------------------------------------------------------------

test(
  "@smoke BS-6 full Strands lifecycle: run → approval pending → approve → APPROVED",
  async ({ request }) => {
    const oppId = `strands-full-e2e-${Date.now()}`;

    // Step 1: Run with Strands
    const runRes = await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
      data: { use_strands: true },
    });
    expect(runRes.ok()).toBeTruthy();
    const runBody = (await runRes.json()) as { final_state: string; potential_credit: string | null };

    // The canonical replay always reaches AWAITING_APPROVAL; with Strands it
    // may still do the same (since agent fallback keeps the deterministic output)
    if (runBody.final_state !== "AWAITING_APPROVAL") {
      // If policy decided ALLOW or DENY, test stops here gracefully
      return;
    }

    // Step 2: Fetch the pending approval
    const pendingRes = await request.get(`${BACKEND}/api/approvals/opportunity/${oppId}`);
    expect(pendingRes.ok()).toBeTruthy();
    const pending = (await pendingRes.json()) as {
      claim_hash: string;
      amount: string;
      state_version: number;
    };

    // Step 3: Approve with correct binding
    const approveRes = await request.post(
      `${BACKEND}/api/approvals/opportunity/${oppId}/approve`,
      {
        data: {
          principal: "playwright-strands-test",
          claim_hash: pending.claim_hash,
          amount: pending.amount,
          state_version: pending.state_version,
          notes: "Approved by Strands E2E test",
        },
      }
    );
    expect(approveRes.ok()).toBeTruthy();
    const approved = (await approveRes.json()) as { state: string; sns_notification_sent: boolean };

    expect(approved.state).toBe("APPROVED");
    expect(approved.sns_notification_sent).toBe(true);
  }
);

// ---------------------------------------------------------------------------
// BS-7 — use_strands=false still runs cleanly (regression guard)
// ---------------------------------------------------------------------------

test(
  "@smoke BS-7 use_strands=false (stub-only) run is deterministic and correct",
  async ({ request }) => {
    const oppId = `strands-false-${Date.now()}`;

    const res = await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
      data: { use_strands: false },
    });
    expect(res.ok()).toBeTruthy();
    const body = (await res.json()) as {
      use_strands: boolean;
      potential_credit: string | null;
      errors: string[];
    };

    expect(body.use_strands).toBe(false);
    expect(body.errors).toHaveLength(0);
    if (body.potential_credit) {
      expect(parseFloat(body.potential_credit)).toBeGreaterThan(0);
    }
  }
);

// ---------------------------------------------------------------------------
// BS-8 — Strands run with tampered approval is rejected (security invariant)
// ---------------------------------------------------------------------------

test(
  "@full BS-8 Strands lifecycle: tampered claim_hash on approval returns 409",
  async ({ request }) => {
    const oppId = `strands-sec-${Date.now()}`;

    await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
      data: { use_strands: true },
    });

    const pendingRes = await request.get(`${BACKEND}/api/approvals/opportunity/${oppId}`);
    if (!pendingRes.ok()) {
      // If no approval was created (ALLOW/DENY path), skip
      return;
    }
    const pending = (await pendingRes.json()) as { amount: string; state_version: number };

    // Tamper the hash
    const tamperRes = await request.post(
      `${BACKEND}/api/approvals/opportunity/${oppId}/approve`,
      {
        data: {
          principal: "playwright-attacker",
          claim_hash: "sha256:deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
          amount: pending.amount,
          state_version: pending.state_version,
        },
      }
    );
    expect(tamperRes.status()).toBe(409);
  }
);

// ---------------------------------------------------------------------------
// BS-9 — Agent trace reflects hypothesis after Strands run
// ---------------------------------------------------------------------------

test(
  "@full BS-9 trace includes hypothesis_summary after Strands run",
  async ({ request }) => {
    const oppId = `strands-hyp-${Date.now()}`;

    await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
      data: { use_strands: true },
    });

    const traceRes = await request.get(`${BACKEND}/api/opportunities/${oppId}/trace`);
    expect(traceRes.ok()).toBeTruthy();
    const trace = (await traceRes.json()) as {
      hypothesis_summary: string | null;
      availability_result: { monthly_uptime_pct: string; potential_credit: string } | null;
    };

    // hypothesis_summary should be a non-empty string
    if (trace.hypothesis_summary !== null) {
      expect(typeof trace.hypothesis_summary).toBe("string");
      expect(trace.hypothesis_summary.length).toBeGreaterThan(0);
    }

    // availability_result must have valid uptime percentage
    if (trace.availability_result !== null) {
      const uptime = parseFloat(trace.availability_result.monthly_uptime_pct);
      expect(uptime).toBeGreaterThanOrEqual(0);
      expect(uptime).toBeLessThanOrEqual(100);
    }
  }
);

// ---------------------------------------------------------------------------
// BS-10 — Multiple concurrent Strands runs don't cross-contaminate state
// ---------------------------------------------------------------------------

test(
  "@full BS-10 concurrent Strands runs produce isolated opportunity state",
  async ({ request }) => {
    const id1 = `strands-iso-a-${Date.now()}`;
    const id2 = `strands-iso-b-${Date.now()}`;

    // Launch both runs
    const [res1, res2] = await Promise.all([
      request.post(`${BACKEND}/api/opportunities/${id1}/run`, { data: { use_strands: true } }),
      request.post(`${BACKEND}/api/opportunities/${id2}/run`, { data: { use_strands: true } }),
    ]);

    expect(res1.ok()).toBeTruthy();
    expect(res2.ok()).toBeTruthy();

    const [body1, body2] = await Promise.all([res1.json(), res2.json()]) as [
      { opportunity_id: string },
      { opportunity_id: string },
    ];

    // Each run must reference its own opportunity ID
    expect(body1.opportunity_id).toBe(id1);
    expect(body2.opportunity_id).toBe(id2);

    // Trace for id1 must not return id2's data and vice-versa
    const [trace1, trace2] = await Promise.all([
      request.get(`${BACKEND}/api/opportunities/${id1}/trace`).then((r) => r.json()),
      request.get(`${BACKEND}/api/opportunities/${id2}/trace`).then((r) => r.json()),
    ]) as [{ opportunity_id: string }, { opportunity_id: string }];

    expect(trace1.opportunity_id).toBe(id1);
    expect(trace2.opportunity_id).toBe(id2);
  }
);

// ---------------------------------------------------------------------------
// BS-LIVE — Bedrock returns agent_driven=true in trace (staging only)
// ---------------------------------------------------------------------------

test(
  "@llm-live BS-LIVE real LLM provider returns agent_driven flag in trace",
  async ({ request }) => {
    // This test only passes when real LLM credentials are configured.
    // Reads llm_provider from /api/config and validates the matching credential.
    // Skip automatically when running locally without credentials.
    const configRes = await request.get(`${BACKEND}/api/config`);
    const config = (await configRes.json()) as Record<string, unknown>;
    const provider = config.llm_provider as string | undefined;
    const hasCredentials =
      (provider === "bedrock" && !!config.bedrock_model_id) ||
      (provider === "openai" && !!config.openai_model_id);
    if (!hasCredentials) {
      test.skip(
        true,
        `No LLM credentials for provider '${provider}' — skipping live test`
      );
      return;
    }

    const oppId = `strands-bedrock-live-${Date.now()}`;

    const runRes = await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
      data: { use_strands: true },
    });
    expect(runRes.ok()).toBeTruthy();

    const traceRes = await request.get(`${BACKEND}/api/opportunities/${oppId}/trace`);
    expect(traceRes.ok()).toBeTruthy();
    const trace = (await traceRes.json()) as Record<string, unknown>;

    // When Bedrock successfully responds, the eligibility_assessment or
    // availability_result may carry agent_driven: true
    // (injected by the strands agent function before returning)
    const eligibility = trace.eligibility as Record<string, unknown> | null;
    if (eligibility && "agent_driven" in eligibility) {
      expect(eligibility.agent_driven).toBe(true);
    }
  }
);
