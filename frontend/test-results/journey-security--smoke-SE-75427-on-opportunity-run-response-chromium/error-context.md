# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-security.spec.ts >> @smoke SEC-5 X-Request-ID is present on opportunity run response
- Location: e2e/journey-security.spec.ts:160:5

# Error details

```
Error: expect(received).toBeTruthy()

Received: false
```

# Test source

```ts
  66  |   return { opportunity_id: oppId, ...pending };
  67  | }
  68  | 
  69  | // ---------------------------------------------------------------------------
  70  | // Cedar binding — claim integrity
  71  | // ---------------------------------------------------------------------------
  72  | 
  73  | test("@smoke SEC-1 tampered claim_hash returns 409", async ({ request }) => {
  74  |   const { opportunity_id, amount, state_version } = await setupPending(request);
  75  | 
  76  |   const res = await request.post(
  77  |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  78  |     {
  79  |       data: {
  80  |         principal: "attacker",
  81  |         claim_hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  82  |         amount,
  83  |         state_version,
  84  |       },
  85  |     }
  86  |   );
  87  |   expect(res.status()).toBe(409);
  88  |   const body = (await res.json()) as { detail: string };
  89  |   expect(body.detail.toLowerCase()).toContain("claim_hash");
  90  | });
  91  | 
  92  | test("@smoke SEC-2 wrong amount returns 409", async ({ request }) => {
  93  |   const { opportunity_id, claim_hash, state_version } = await setupPending(request);
  94  | 
  95  |   const res = await request.post(
  96  |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  97  |     {
  98  |       data: {
  99  |         principal: "attacker",
  100 |         claim_hash,
  101 |         amount: "9999999.99",
  102 |         state_version,
  103 |       },
  104 |     }
  105 |   );
  106 |   expect(res.status()).toBe(409);
  107 | });
  108 | 
  109 | test("@smoke SEC-3 stale state_version returns 409", async ({ request }) => {
  110 |   const { opportunity_id, claim_hash, amount } = await setupPending(request);
  111 | 
  112 |   const res = await request.post(
  113 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  114 |     {
  115 |       data: {
  116 |         principal: "attacker",
  117 |         claim_hash,
  118 |         amount,
  119 |         state_version: 9999, // stale
  120 |       },
  121 |     }
  122 |   );
  123 |   expect(res.status()).toBe(409);
  124 | });
  125 | 
  126 | test("@smoke SEC-4 double-approve returns 404 (no pending record after first approve)", async ({
  127 |   request,
  128 | }) => {
  129 |   const { opportunity_id, claim_hash, amount, state_version } =
  130 |     await setupPending(request);
  131 | 
  132 |   // First approve — succeeds
  133 |   const first = await request.post(
  134 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  135 |     {
  136 |       data: { principal: "playwright-test", claim_hash, amount, state_version },
  137 |     }
  138 |   );
  139 |   expect(first.ok()).toBeTruthy();
  140 | 
  141 |   // Second approve — no pending record
  142 |   const second = await request.post(
  143 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  144 |     {
  145 |       data: {
  146 |         principal: "playwright-test",
  147 |         claim_hash: "sha256:anything",
  148 |         amount: "0.00",
  149 |         state_version: 1,
  150 |       },
  151 |     }
  152 |   );
  153 |   expect(second.status()).toBe(404);
  154 | });
  155 | 
  156 | // ---------------------------------------------------------------------------
  157 | // X-Request-ID presence
  158 | // ---------------------------------------------------------------------------
  159 | 
  160 | test("@smoke SEC-5 X-Request-ID is present on opportunity run response", async ({ request }) => {
  161 |   // Use the /run endpoint — does not need AWS scan credentials.
  162 |   const res = await request.post(
  163 |     `${BACKEND}/api/opportunities/sec5-xrid-${Date.now()}/run`,
  164 |     { data: { use_strands: true } }
  165 |   );
> 166 |   expect(res.ok()).toBeTruthy();
      |                    ^ Error: expect(received).toBeTruthy()
  167 |   const requestId = res.headers()["x-request-id"];
  168 |   expect(requestId).toBeTruthy();
  169 |   expect(requestId).toMatch(
  170 |     /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  171 |   );
  172 | });
  173 | 
  174 | test("@smoke SEC-6 X-Request-ID is present on 409 rejection response", async ({
  175 |   request,
  176 | }) => {
  177 |   const { opportunity_id, amount, state_version } = await setupPending(request);
  178 | 
  179 |   const res = await request.post(
  180 |     `${BACKEND}/api/approvals/opportunity/${opportunity_id}/approve`,
  181 |     {
  182 |       data: {
  183 |         principal: "attacker",
  184 |         claim_hash: "sha256:badhash00000000000000000000000000000000000000000000000000000000",
  185 |         amount,
  186 |         state_version,
  187 |       },
  188 |     }
  189 |   );
  190 |   expect(res.status()).toBe(409);
  191 |   const requestId = res.headers()["x-request-id"];
  192 |   expect(requestId).toBeTruthy();
  193 | });
  194 | 
  195 | // ---------------------------------------------------------------------------
  196 | // CORS
  197 | // ---------------------------------------------------------------------------
  198 | 
  199 | test("@full SEC-7 health endpoint is accessible without auth (public path)", async ({
  200 |   request,
  201 | }) => {
  202 |   const res = await request.get(`${BACKEND}/health`);
  203 |   expect(res.ok()).toBeTruthy();
  204 |   const body = (await res.json()) as { status: string };
  205 |   expect(body.status).toBe("ok");
  206 | });
  207 | 
  208 | test("@full SEC-8 health/ready is accessible without auth (public path)", async ({
  209 |   request,
  210 | }) => {
  211 |   const res = await request.get(`${BACKEND}/health/ready`);
  212 |   expect(res.ok()).toBeTruthy();
  213 |   const body = (await res.json()) as { status: string };
  214 |   expect(["ready", "degraded"]).toContain(body.status);
  215 | });
  216 | 
  217 | // ---------------------------------------------------------------------------
  218 | // Scan data sanitization
  219 | // ---------------------------------------------------------------------------
  220 | 
  221 | test("@full SEC-9 scan audit records mask account_id (no raw 12-digit AWS account)", async ({
  222 |   request,
  223 | }) => {
  224 |   // Requires RECOUP_READONLY_ROLE_ARN — skip gracefully when not configured.
  225 |   const scanRes = await request.post(`${BACKEND}/api/scan/demo`);
  226 |   if (!scanRes.ok()) {
  227 |     test.skip(true, "Demo scan not configured (RECOUP_READONLY_ROLE_ARN missing) — skipping");
  228 |     return;
  229 |   }
  230 | 
  231 |   const res = await request.get(`${BACKEND}/api/scan/audit`);
  232 |   expect(res.ok()).toBeTruthy();
  233 |   const audit = (await res.json()) as Array<Record<string, string>>;
  234 |   for (const entry of audit) {
  235 |     const maskedId = entry["account_id_masked"] ?? "";
  236 |     // Raw 12-digit account IDs must not appear unmasked
  237 |     if (maskedId && maskedId !== "unknown") {
  238 |       // Must contain XXXXXXXX masking pattern
  239 |       expect(maskedId).toContain("XXXXXXXX");
  240 |     }
  241 |   }
  242 | });
  243 | 
  244 | test("@full SEC-10 scan response masks account_id (XXXXXXXX pattern or unknown)", async ({
  245 |   request,
  246 | }) => {
  247 |   // Requires RECOUP_READONLY_ROLE_ARN — skip gracefully when not configured.
  248 |   const scanRes = await request.post(`${BACKEND}/api/scan/demo`);
  249 |   if (!scanRes.ok()) {
  250 |     test.skip(true, "Demo scan not configured (RECOUP_READONLY_ROLE_ARN missing) — skipping");
  251 |     return;
  252 |   }
  253 |   const scan = await scanRes.json();
  254 |   const result = scan as unknown as { account_id: string | null };
  255 |   if (result.account_id && result.account_id !== "unknown") {
  256 |     // Must contain masking
  257 |     expect(result.account_id).toContain("XXXXXXXX");
  258 |     // Must NOT be a raw 12-digit AWS account ID
  259 |     expect(result.account_id).not.toMatch(/^\d{12}$/);
  260 |   }
  261 | });
  262 | 
  263 | // ---------------------------------------------------------------------------
  264 | // Data deletion
  265 | // ---------------------------------------------------------------------------
  266 | 
```