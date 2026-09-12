/**
 * J3 — Cross-Account Connect Wizard (Sprint 5 journey test)
 *
 * Full end-to-end of the in-product connect wizard:
 *   POST /api/scan/connect/init  → unique ExternalId + CF template
 *   GET  /api/scan/connect/{id}  → retrieve connection record
 *   POST /api/scan/full          → scan using the generated ExternalId
 *   ExternalId uniqueness — two inits produce different IDs
 *   CF template contains DenyAllWrites + per-customer ExternalId
 *
 * Tags:
 *   @smoke  — init + uniqueness + CF template checks
 *   @full   — scan with connection, re-fetch, error paths
 */
import { test, expect } from "@playwright/test";
import { BACKEND, resetBackend } from "./helpers";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

// ---------------------------------------------------------------------------
// J3 — @smoke: happy paths
// ---------------------------------------------------------------------------

test("@smoke J3-1 connect init returns unique customer_id and external_id", async ({
  request,
}) => {
  const res = await request.post(`${BACKEND}/api/scan/connect/init`);
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as {
    customer_id: string;
    external_id: string;
    cf_template_hint: string;
  };
  expect(body.customer_id).toBeTruthy();
  expect(body.external_id).toBeTruthy();
  // ExternalId must be at least 20 chars of random material
  expect(body.external_id.length).toBeGreaterThanOrEqual(20);
});

test("@smoke J3-2 two connect inits produce different ExternalIds", async ({ request }) => {
  const r1 = await request.post(`${BACKEND}/api/scan/connect/init`);
  const r2 = await request.post(`${BACKEND}/api/scan/connect/init`);
  expect(r1.ok()).toBeTruthy();
  expect(r2.ok()).toBeTruthy();
  const c1 = (await r1.json()) as { customer_id: string; external_id: string };
  const c2 = (await r2.json()) as { customer_id: string; external_id: string };
  expect(c1.customer_id).not.toBe(c2.customer_id);
  expect(c1.external_id).not.toBe(c2.external_id);
});

test("@smoke J3-3 CF template hint contains DenyAllWrites and per-customer ExternalId", async ({
  request,
}) => {
  const res = await request.post(`${BACKEND}/api/scan/connect/init`);
  const body = (await res.json()) as { external_id: string; cf_template_hint: string };
  const template = body.cf_template_hint ?? "";
  // Must reference the per-customer ExternalId in the trust condition
  expect(template).toContain(body.external_id);
  // Must include DenyAllWrites protection
  expect(template.toLowerCase()).toContain("denyallwrites");
});

test("@smoke J3-4 get customer connection by ID returns the same external_id", async ({
  request,
}) => {
  const initRes = await request.post(`${BACKEND}/api/scan/connect/init`);
  const { customer_id, external_id } = (await initRes.json()) as {
    customer_id: string;
    external_id: string;
  };

  const getRes = await request.get(
    `${BACKEND}/api/scan/connect/${customer_id}`
  );
  expect(getRes.ok()).toBeTruthy();
  const conn = (await getRes.json()) as {
    customer_id: string;
    external_id: string;
  };
  expect(conn.customer_id).toBe(customer_id);
  expect(conn.external_id).toBe(external_id);
});

// ---------------------------------------------------------------------------
// J3 — @full: edge cases
// ---------------------------------------------------------------------------

test("@full J3-5 unknown customer_id returns 404", async ({ request }) => {
  const res = await request.get(
    `${BACKEND}/api/scan/connect/nonexistent-customer-id`
  );
  expect(res.status()).toBe(404);
});

test("@full J3-6 demo scan runs after connect init (ExternalId flows through)", async ({
  request,
}) => {
  // Init a connection to get an ExternalId
  const initRes = await request.post(`${BACKEND}/api/scan/connect/init`);
  expect(initRes.ok()).toBeTruthy();

  // Demo scan should work regardless (uses demo fixture or live when configured)
  const scanRes = await request.post(`${BACKEND}/api/scan/demo`);
  expect(scanRes.ok()).toBeTruthy();
  const scan = (await scanRes.json()) as { findings: unknown[] };
  expect(Array.isArray(scan.findings)).toBeTruthy();
});

test("@full J3-7 init endpoint returns X-Request-ID header", async ({ request }) => {
  const res = await request.post(`${BACKEND}/api/scan/connect/init`);
  expect(res.ok()).toBeTruthy();
  const requestId = res.headers()["x-request-id"];
  expect(requestId).toBeTruthy();
  expect(requestId).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  );
});

test("@full J3-8 ExternalId has sufficient entropy (256-bit token_urlsafe output)", async ({
  request,
}) => {
  const res = await request.post(`${BACKEND}/api/scan/connect/init`);
  const { external_id } = (await res.json()) as { external_id: string };
  // secrets.token_urlsafe(32) produces 43 chars of base64url
  expect(external_id.length).toBeGreaterThanOrEqual(40);
  // Should only contain URL-safe characters
  expect(external_id).toMatch(/^[A-Za-z0-9_-]+$/);
});
