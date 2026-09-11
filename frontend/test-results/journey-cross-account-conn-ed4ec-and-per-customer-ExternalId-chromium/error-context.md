# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-cross-account-connect.spec.ts >> @smoke J3-3 CF template hint contains DenyAllWrites and per-customer ExternalId
- Location: e2e/journey-cross-account-connect.spec.ts:59:5

# Error details

```
TypeError: expect.toContain(undefined) // indexOf

Matcher error: expected value must be a string if received value is a string

Expected has value: undefined
Received has type:  string
Received has value: ""
```

# Test source

```ts
  1   | /**
  2   |  * J3 — Cross-Account Connect Wizard (Sprint 5 journey test)
  3   |  *
  4   |  * Full end-to-end of the in-product connect wizard:
  5   |  *   POST /api/scan/connect/init  → unique ExternalId + CF template
  6   |  *   GET  /api/scan/connect/{id}  → retrieve connection record
  7   |  *   POST /api/scan/full          → scan using the generated ExternalId
  8   |  *   ExternalId uniqueness — two inits produce different IDs
  9   |  *   CF template contains DenyAllWrites + per-customer ExternalId
  10  |  *
  11  |  * Tags:
  12  |  *   @smoke  — init + uniqueness + CF template checks
  13  |  *   @full   — scan with connection, re-fetch, error paths
  14  |  */
  15  | import { test, expect } from "@playwright/test";
  16  | import { resetBackend } from "./helpers";
  17  | 
  18  | const BACKEND = "http://localhost:8000";
  19  | 
  20  | // ---------------------------------------------------------------------------
  21  | // Setup
  22  | // ---------------------------------------------------------------------------
  23  | 
  24  | test.beforeEach(async ({ request }) => {
  25  |   await resetBackend(request);
  26  | });
  27  | 
  28  | // ---------------------------------------------------------------------------
  29  | // J3 — @smoke: happy paths
  30  | // ---------------------------------------------------------------------------
  31  | 
  32  | test("@smoke J3-1 connect init returns unique customer_id and external_id", async ({
  33  |   request,
  34  | }) => {
  35  |   const res = await request.post(`${BACKEND}/api/scan/connect/init`);
  36  |   expect(res.ok()).toBeTruthy();
  37  |   const body = (await res.json()) as {
  38  |     customer_id: string;
  39  |     external_id: string;
  40  |     cf_template_hint: string;
  41  |   };
  42  |   expect(body.customer_id).toBeTruthy();
  43  |   expect(body.external_id).toBeTruthy();
  44  |   // ExternalId must be at least 20 chars of random material
  45  |   expect(body.external_id.length).toBeGreaterThanOrEqual(20);
  46  | });
  47  | 
  48  | test("@smoke J3-2 two connect inits produce different ExternalIds", async ({ request }) => {
  49  |   const r1 = await request.post(`${BACKEND}/api/scan/connect/init`);
  50  |   const r2 = await request.post(`${BACKEND}/api/scan/connect/init`);
  51  |   expect(r1.ok()).toBeTruthy();
  52  |   expect(r2.ok()).toBeTruthy();
  53  |   const c1 = (await r1.json()) as { customer_id: string; external_id: string };
  54  |   const c2 = (await r2.json()) as { customer_id: string; external_id: string };
  55  |   expect(c1.customer_id).not.toBe(c2.customer_id);
  56  |   expect(c1.external_id).not.toBe(c2.external_id);
  57  | });
  58  | 
  59  | test("@smoke J3-3 CF template hint contains DenyAllWrites and per-customer ExternalId", async ({
  60  |   request,
  61  | }) => {
  62  |   const res = await request.post(`${BACKEND}/api/scan/connect/init`);
  63  |   const body = (await res.json()) as { external_id: string; cf_template_hint: string };
  64  |   const template = body.cf_template_hint ?? "";
  65  |   // Must reference the per-customer ExternalId in the trust condition
> 66  |   expect(template).toContain(body.external_id);
      |                    ^ TypeError: expect.toContain(undefined) // indexOf
  67  |   // Must include DenyAllWrites protection
  68  |   expect(template.toLowerCase()).toContain("denyallwrites");
  69  | });
  70  | 
  71  | test("@smoke J3-4 get customer connection by ID returns the same external_id", async ({
  72  |   request,
  73  | }) => {
  74  |   const initRes = await request.post(`${BACKEND}/api/scan/connect/init`);
  75  |   const { customer_id, external_id } = (await initRes.json()) as {
  76  |     customer_id: string;
  77  |     external_id: string;
  78  |   };
  79  | 
  80  |   const getRes = await request.get(
  81  |     `${BACKEND}/api/scan/connect/${customer_id}`
  82  |   );
  83  |   expect(getRes.ok()).toBeTruthy();
  84  |   const conn = (await getRes.json()) as {
  85  |     customer_id: string;
  86  |     external_id: string;
  87  |   };
  88  |   expect(conn.customer_id).toBe(customer_id);
  89  |   expect(conn.external_id).toBe(external_id);
  90  | });
  91  | 
  92  | // ---------------------------------------------------------------------------
  93  | // J3 — @full: edge cases
  94  | // ---------------------------------------------------------------------------
  95  | 
  96  | test("@full J3-5 unknown customer_id returns 404", async ({ request }) => {
  97  |   const res = await request.get(
  98  |     `${BACKEND}/api/scan/connect/nonexistent-customer-id`
  99  |   );
  100 |   expect(res.status()).toBe(404);
  101 | });
  102 | 
  103 | test("@full J3-6 demo scan runs after connect init (ExternalId flows through)", async ({
  104 |   request,
  105 | }) => {
  106 |   // Init a connection to get an ExternalId
  107 |   const initRes = await request.post(`${BACKEND}/api/scan/connect/init`);
  108 |   expect(initRes.ok()).toBeTruthy();
  109 | 
  110 |   // Demo scan should work regardless (uses demo fixture or live when configured)
  111 |   const scanRes = await request.post(`${BACKEND}/api/scan/demo`);
  112 |   expect(scanRes.ok()).toBeTruthy();
  113 |   const scan = (await scanRes.json()) as { findings: unknown[] };
  114 |   expect(Array.isArray(scan.findings)).toBeTruthy();
  115 | });
  116 | 
  117 | test("@full J3-7 init endpoint returns X-Request-ID header", async ({ request }) => {
  118 |   const res = await request.post(`${BACKEND}/api/scan/connect/init`);
  119 |   expect(res.ok()).toBeTruthy();
  120 |   const requestId = res.headers()["x-request-id"];
  121 |   expect(requestId).toBeTruthy();
  122 |   expect(requestId).toMatch(
  123 |     /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  124 |   );
  125 | });
  126 | 
  127 | test("@full J3-8 ExternalId has sufficient entropy (256-bit token_urlsafe output)", async ({
  128 |   request,
  129 | }) => {
  130 |   const res = await request.post(`${BACKEND}/api/scan/connect/init`);
  131 |   const { external_id } = (await res.json()) as { external_id: string };
  132 |   // secrets.token_urlsafe(32) produces 43 chars of base64url
  133 |   expect(external_id.length).toBeGreaterThanOrEqual(40);
  134 |   // Should only contain URL-safe characters
  135 |   expect(external_id).toMatch(/^[A-Za-z0-9_-]+$/);
  136 | });
  137 | 
```