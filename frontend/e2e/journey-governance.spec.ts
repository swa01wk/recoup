/**
 * J10–J12 — Governance Insights: CloudTrail / Tagging / Cost Explorer (Sprint 5)
 *
 * Tests three complete governance journeys:
 *   J10 GET /api/cloudtrail-demo/check   → actor attribution, event count
 *   J11 GET /api/tagging-demo/scan       → untagged resources, tag coverage
 *   J12 GET /api/cost-demo/summary       → cost breakdown, top services
 *
 * Each endpoint has both a live AWS path and a demo/stub path — tests
 * accept either and verify the response structure is valid.
 *
 * Tags:
 *   @smoke  — each endpoint returns valid structure
 *   @full   — field types, amounts, finding counts, X-Request-ID
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
// J10 — CloudTrail Actor Attribution
// ---------------------------------------------------------------------------

test("@smoke J10-1 cloudtrail-demo/check returns 200 with valid structure", async ({
  request,
}) => {
  const res = await request.get(`${BACKEND}/api/cloudtrail-demo/check`);
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as Record<string, unknown>;
  // Should have either events, actor, or findings key
  expect(
    "events" in body || "actor" in body || "findings" in body || "events_analysed" in body
  ).toBeTruthy();
});

test("@smoke J10-2 cloudtrail response has X-Request-ID header", async ({ request }) => {
  const res = await request.get(`${BACKEND}/api/cloudtrail-demo/check`);
  expect(res.ok()).toBeTruthy();
  const requestId = res.headers()["x-request-id"];
  expect(requestId).toBeTruthy();
  expect(requestId).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  );
});

test("@full J10-3 cloudtrail events_analysed or event_count is a non-negative number", async ({
  request,
}) => {
  const res = await request.get(`${BACKEND}/api/cloudtrail-demo/check`);
  const body = (await res.json()) as {
    events_analysed?: number;
    event_count?: number;
    events?: unknown[];
  };
  const count =
    body.events_analysed ??
    body.event_count ??
    (Array.isArray(body.events) ? body.events.length : undefined);
  if (count !== undefined) {
    expect(count).toBeGreaterThanOrEqual(0);
  }
});

test("@full J10-4 cloudtrail actor field is a string when present", async ({ request }) => {
  const res = await request.get(`${BACKEND}/api/cloudtrail-demo/check`);
  const body = (await res.json()) as { actor?: string; attributed_actor?: string };
  const actor = body.actor ?? body.attributed_actor;
  if (actor !== undefined) {
    expect(typeof actor).toBe("string");
  }
});

// ---------------------------------------------------------------------------
// J11 — Tagging Scan
// ---------------------------------------------------------------------------

test("@smoke J11-1 tagging-demo/scan returns 200 with valid structure", async ({
  request,
}) => {
  const res = await request.get(`${BACKEND}/api/tagging-demo/scan`);
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as Record<string, unknown>;
  expect(
    "untagged" in body ||
    "findings" in body ||
    "resources" in body ||
    "untagged_count" in body ||
    "tag_coverage_pct" in body
  ).toBeTruthy();
});

test("@smoke J11-2 tagging response has X-Request-ID header", async ({ request }) => {
  const res = await request.get(`${BACKEND}/api/tagging-demo/scan`);
  expect(res.ok()).toBeTruthy();
  const requestId = res.headers()["x-request-id"];
  expect(requestId).toBeTruthy();
});

test("@full J11-3 tag coverage is between 0 and 100 when present", async ({ request }) => {
  const res = await request.get(`${BACKEND}/api/tagging-demo/scan`);
  const body = (await res.json()) as {
    tag_coverage_pct?: number;
    coverage_pct?: number;
  };
  const coverage = body.tag_coverage_pct ?? body.coverage_pct;
  if (coverage !== undefined) {
    expect(coverage).toBeGreaterThanOrEqual(0);
    expect(coverage).toBeLessThanOrEqual(100);
  }
});

test("@full J11-4 untagged_count is a non-negative integer when present", async ({
  request,
}) => {
  const res = await request.get(`${BACKEND}/api/tagging-demo/scan`);
  const body = (await res.json()) as {
    untagged_count?: number;
    untagged?: unknown[];
  };
  const count =
    body.untagged_count ??
    (Array.isArray(body.untagged) ? body.untagged.length : undefined);
  if (count !== undefined) {
    expect(count).toBeGreaterThanOrEqual(0);
    expect(Number.isInteger(count)).toBeTruthy();
  }
});

// ---------------------------------------------------------------------------
// J12 — Cost Explorer Summary
// ---------------------------------------------------------------------------

test("@smoke J12-1 cost-demo/summary returns 200 with valid structure", async ({
  request,
}) => {
  const res = await request.get(`${BACKEND}/api/cost-demo/summary`);
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as Record<string, unknown>;
  expect(
    "total_usd" in body ||
    "total_cost_usd" in body ||
    "services" in body ||
    "findings" in body ||
    "month" in body
  ).toBeTruthy();
});

test("@smoke J12-2 cost summary has X-Request-ID header", async ({ request }) => {
  const res = await request.get(`${BACKEND}/api/cost-demo/summary`);
  expect(res.ok()).toBeTruthy();
  const requestId = res.headers()["x-request-id"];
  expect(requestId).toBeTruthy();
});

test("@full J12-3 total cost is a non-negative number when present", async ({ request }) => {
  const res = await request.get(`${BACKEND}/api/cost-demo/summary`);
  const body = (await res.json()) as {
    total_usd?: number | string;
    total_cost_usd?: number | string;
  };
  const total = body.total_usd ?? body.total_cost_usd;
  if (total !== undefined) {
    expect(parseFloat(String(total))).toBeGreaterThanOrEqual(0);
  }
});

test("@full J12-4 services list contains valid entries when present", async ({ request }) => {
  const res = await request.get(`${BACKEND}/api/cost-demo/summary`);
  const body = (await res.json()) as {
    services?: Array<{ service: string; cost_usd: number | string }>;
  };
  if (Array.isArray(body.services) && body.services.length > 0) {
    for (const svc of body.services.slice(0, 3)) {
      expect(typeof svc.service).toBe("string");
      expect(parseFloat(String(svc.cost_usd))).toBeGreaterThanOrEqual(0);
    }
  }
});

// ---------------------------------------------------------------------------
// Cross-journey: all three governance endpoints respond in parallel
// ---------------------------------------------------------------------------

test("@full J10-J12-all three governance endpoints all return 200", async ({ request }) => {
  const [ct, tags, cost] = await Promise.all([
    request.get(`${BACKEND}/api/cloudtrail-demo/check`),
    request.get(`${BACKEND}/api/tagging-demo/scan`),
    request.get(`${BACKEND}/api/cost-demo/summary`),
  ]);
  expect(ct.ok()).toBeTruthy();
  expect(tags.ok()).toBeTruthy();
  expect(cost.ok()).toBeTruthy();
});
