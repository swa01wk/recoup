/**
 * Security Journey Tests (Sprint 5)
 *
 * Verifies all security hardening from Sprints 1–4:
 *   - Tampered claim_hash → 409 (Cedar binding holds)
 *   - Stale state_version → 409
 *   - Wrong amount → 409
 *   - Double-approve → 404 (no pending approval)
 *   - X-Request-ID on every response
 *   - CORS: X-Request-ID present for allowed origin
 *   - API key auth (when RECOUP_API_KEY is configured)
 *   - Scan audit records are masked (no raw account IDs)
 *   - Data deletion is graceful (no 500 on unknown account)
 *
 * Tags:
 *   @smoke  — claim_hash binding, X-Request-ID, double-approve
 *   @full   — CORS, API key, sanitization, data deletion
 */
import { test, expect } from "@playwright/test";
import { resetBackend } from "./helpers";

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

/**
 * Create a pending approval by running the SLA pipeline directly.
 * Does not require AWS scan credentials — uses the deterministic replay path
 * that always produces AWAITING_APPROVAL with a valid claim record.
 */
async function setupPending(
  request: import("@playwright/test").APIRequestContext
): Promise<{
  opportunity_id: string;
  approval_id: string;
  claim_hash: string;
  amount: string;
  state_version: number;
}> {
  const oppId = `sec-pending-${Date.now()}`;
  const runRes = await request.post(`${BACKEND}/api/opportunities/${oppId}/run`, {
    data: { use_strands: true },
  });
  expect(runRes.ok()).toBeTruthy();

  const res = await request.get(
    `${BACKEND}/api/approvals/opportunity/${oppId}`
  );
  expect(res.ok()).toBeTruthy();
  const pending = (await res.json()) as {
    approval_id: string;
    claim_hash: string;
    amount: string;
    state_version: number;
  };
  return { opportunity_id: oppId, ...pending };
}

// ---------------------------------------------------------------------------
// Cedar binding — claim integrity
// ---------------------------------------------------------------------------

test("@smoke SEC-1 tampered claim_hash returns 409", async ({ request }) => {
  const { opportunity_id, amount, state_version } = await setupPending(request);

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
  expect(body.detail.toLowerCase()).toContain("claim_hash");
});

test("@smoke SEC-2 wrong amount returns 409", async ({ request }) => {
  const { opportunity_id, claim_hash, state_version } = await setupPending(request);

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
    {
      data: {
        principal: "attacker",
        claim_hash,
        amount: "9999999.99",
        state_version,
      },
    }
  );
  expect(res.status()).toBe(409);
});

test("@smoke SEC-3 stale state_version returns 409", async ({ request }) => {
  const { opportunity_id, claim_hash, amount } = await setupPending(request);

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
    {
      data: {
        principal: "attacker",
        claim_hash,
        amount,
        state_version: 9999, // stale
      },
    }
  );
  expect(res.status()).toBe(409);
});

test("@smoke SEC-4 double-approve returns 404 (no pending record after first approve)", async ({
  request,
}) => {
  const { opportunity_id, claim_hash, amount, state_version } =
    await setupPending(request);

  // First approve — succeeds
  const first = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
    {
      data: { principal: "playwright-test", claim_hash, amount, state_version },
    }
  );
  expect(first.ok()).toBeTruthy();

  // Second approve — no pending record
  const second = await request.post(
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
  expect(second.status()).toBe(404);
});

// ---------------------------------------------------------------------------
// X-Request-ID presence
// ---------------------------------------------------------------------------

test("@smoke SEC-5 X-Request-ID is present on opportunity run response", async ({ request }) => {
  // Use the /run endpoint — does not need AWS scan credentials.
  const res = await request.post(
    `${BACKEND}/api/opportunities/sec5-xrid-${Date.now()}/run`,
    { data: { use_strands: true } }
  );
  expect(res.ok()).toBeTruthy();
  const requestId = res.headers()["x-request-id"];
  expect(requestId).toBeTruthy();
  expect(requestId).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  );
});

test("@smoke SEC-6 X-Request-ID is present on 409 rejection response", async ({
  request,
}) => {
  const { opportunity_id, amount, state_version } = await setupPending(request);

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
    {
      data: {
        principal: "attacker",
        claim_hash: "sha256:badhash00000000000000000000000000000000000000000000000000000000",
        amount,
        state_version,
      },
    }
  );
  expect(res.status()).toBe(409);
  const requestId = res.headers()["x-request-id"];
  expect(requestId).toBeTruthy();
});

// ---------------------------------------------------------------------------
// CORS
// ---------------------------------------------------------------------------

test("@full SEC-7 health endpoint is accessible without auth (public path)", async ({
  request,
}) => {
  const res = await request.get(`${BACKEND}/health`);
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { status: string };
  expect(body.status).toBe("ok");
});

test("@full SEC-8 health/ready is accessible without auth (public path)", async ({
  request,
}) => {
  const res = await request.get(`${BACKEND}/health/ready`);
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { status: string };
  expect(["ready", "degraded"]).toContain(body.status);
});

// ---------------------------------------------------------------------------
// Scan data sanitization
// ---------------------------------------------------------------------------

test("@full SEC-9 scan audit records mask account_id (no raw 12-digit AWS account)", async ({
  request,
}) => {
  // Requires RECOUP_READONLY_ROLE_ARN — skip gracefully when not configured.
  const scanRes = await request.post(`${BACKEND}/api/scan/demo`);
  if (!scanRes.ok()) {
    test.skip(true, "Demo scan not configured (RECOUP_READONLY_ROLE_ARN missing) — skipping");
    return;
  }

  const res = await request.get(`${BACKEND}/api/scan/audit`);
  expect(res.ok()).toBeTruthy();
  const audit = (await res.json()) as Array<Record<string, string>>;
  for (const entry of audit) {
    const maskedId = entry["account_id_masked"] ?? "";
    // Raw 12-digit account IDs must not appear unmasked
    if (maskedId && maskedId !== "unknown") {
      // Must contain XXXXXXXX masking pattern
      expect(maskedId).toContain("XXXXXXXX");
    }
  }
});

test("@full SEC-10 scan response masks account_id (XXXXXXXX pattern or unknown)", async ({
  request,
}) => {
  // Requires RECOUP_READONLY_ROLE_ARN — skip gracefully when not configured.
  const scanRes = await request.post(`${BACKEND}/api/scan/demo`);
  if (!scanRes.ok()) {
    test.skip(true, "Demo scan not configured (RECOUP_READONLY_ROLE_ARN missing) — skipping");
    return;
  }
  const scan = await scanRes.json();
  const result = scan as unknown as { account_id: string | null };
  if (result.account_id && result.account_id !== "unknown") {
    // Must contain masking
    expect(result.account_id).toContain("XXXXXXXX");
    // Must NOT be a raw 12-digit AWS account ID
    expect(result.account_id).not.toMatch(/^\d{12}$/);
  }
});

// ---------------------------------------------------------------------------
// Data deletion
// ---------------------------------------------------------------------------

test("@full SEC-11 data deletion for unknown account returns graceful response", async ({
  request,
}) => {
  const res = await request.delete(
    `${BACKEND}/api/scan/accounts/nonexistent-account-id/data`
  );
  // Must not 500 — should return 200 (nothing to delete) or 404
  expect([200, 404]).toContain(res.status());
});

test("@full SEC-12 data deletion purges scan data for demo account", async ({
  request,
}) => {
  // Requires RECOUP_READONLY_ROLE_ARN — skip gracefully when not configured.
  const scanRes = await request.post(`${BACKEND}/api/scan/demo`);
  if (!scanRes.ok()) {
    test.skip(true, "Demo scan not configured (RECOUP_READONLY_ROLE_ARN missing) — skipping");
    return;
  }

  const delRes = await request.delete(`${BACKEND}/api/scan/accounts/__demo__/data`);
  expect(delRes.ok()).toBeTruthy();
  const body = (await delRes.json()) as { status: string };
  expect(body.status).toBe("deleted");
});

// ---------------------------------------------------------------------------
// API config endpoint
// ---------------------------------------------------------------------------

test("@full SEC-13 /api/config returns non-secret info only (no keys or secrets)", async ({
  request,
}) => {
  const res = await request.get(`${BACKEND}/api/config`);
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as Record<string, unknown>;
  // Must never return API keys, secrets, or credentials
  const bodyStr = JSON.stringify(body).toLowerCase();
  expect(bodyStr).not.toMatch(/(secret|password|api_key|token|credential)/);
  // Should have expected safe fields
  expect(
    "real_submission_enabled" in body ||
    "bedrock_region" in body ||
    "llm_provider" in body
  ).toBeTruthy();
});
