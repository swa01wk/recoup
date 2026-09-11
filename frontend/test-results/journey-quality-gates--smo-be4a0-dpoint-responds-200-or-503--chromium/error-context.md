# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey-quality-gates.spec.ts >> @smoke J8-1 quality scorecard endpoint responds (200 or 503)
- Location: e2e/journey-quality-gates.spec.ts:32:5

# Error details

```
Error: expect(received).toContain(expected) // indexOf

Expected value: 404
Received array: [200, 503]
```

# Test source

```ts
  1   | /**
  2   |  * J8 — Quality Scorecard: Real Data, No Hardcoded Fallback (Sprint 5)
  3   |  *
  4   |  * Tests:
  5   |  *   GET /api/quality/scorecard — returns valid structure (or 503 when Bedrock absent)
  6   |  *   Scorecard fields are numeric, within valid ranges
  7   |  *   unsafe_external_actions is always 0
  8   |  *   Scan/promote path feeds scorecard gates (no /api/replay HTTP)
  9   |  *   Scorecard is NOT the hardcoded DEMO_SCORECARD when API is reachable
  10  |  *
  11  |  * Tags:
  12  |  *   @smoke  — scorecard endpoint + structure
  13  |  *   @full   — field validation, replay integration, threshold checks
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
  29  | // J8 — @smoke: happy paths
  30  | // ---------------------------------------------------------------------------
  31  | 
  32  | test("@smoke J8-1 quality scorecard endpoint responds (200 or 503)", async ({
  33  |   request,
  34  | }) => {
  35  |   const res = await request.get(`${BACKEND}/api/quality/scorecard`);
  36  |   // 200 = live scorecard; 503 = Bedrock not configured (acceptable in local)
> 37  |   expect([200, 503]).toContain(res.status());
      |                      ^ Error: expect(received).toContain(expected) // indexOf
  38  | });
  39  | 
  40  | test("@smoke J8-2 scorecard structure is valid when API responds 200", async ({
  41  |   request,
  42  | }) => {
  43  |   const res = await request.get(`${BACKEND}/api/quality/scorecard`);
  44  |   if (res.status() !== 200) {
  45  |     return; // Skip structural check when backend returns 503
  46  |   }
  47  |   const card = (await res.json()) as Record<string, unknown>;
  48  |   expect(typeof card["build"]).toBe("string");
  49  |   expect(typeof card["unsafe_external_actions"]).toBe("number");
  50  |   expect(card["golden_path_success"]).toBeTruthy();
  51  |   expect(card["overall_scenario_success"]).toBeTruthy();
  52  |   expect(card["evidence_recall"]).toBeTruthy();
  53  |   expect(card["tool_selection_accuracy"]).toBeTruthy();
  54  |   expect(card["financial_math_correctness"]).toBeTruthy();
  55  |   expect(card["trace_completeness"]).toBeTruthy();
  56  | });
  57  | 
  58  | test("@smoke J8-3 unsafe_external_actions is always 0", async ({ request }) => {
  59  |   const res = await request.get(`${BACKEND}/api/quality/scorecard`);
  60  |   if (res.status() !== 200) return;
  61  |   const card = (await res.json()) as { unsafe_external_actions: number };
  62  |   expect(card.unsafe_external_actions).toBe(0);
  63  | });
  64  | 
  65  | test("@smoke J8-4 scorecard metric rates are between 0 and 1", async ({ request }) => {
  66  |   const res = await request.get(`${BACKEND}/api/quality/scorecard`);
  67  |   if (res.status() !== 200) return;
  68  |   const card = (await res.json()) as Record<
  69  |     string,
  70  |     { rate?: number; passed?: number; total?: number } | unknown
  71  |   >;
  72  | 
  73  |   const rateFields = [
  74  |     "golden_path_success",
  75  |     "overall_scenario_success",
  76  |     "evidence_recall",
  77  |     "tool_selection_accuracy",
  78  |     "financial_math_correctness",
  79  |     "trace_completeness",
  80  |   ];
  81  |   for (const field of rateFields) {
  82  |     const metric = card[field] as { rate: number } | undefined;
  83  |     if (metric?.rate !== undefined) {
  84  |       expect(metric.rate).toBeGreaterThanOrEqual(0);
  85  |       expect(metric.rate).toBeLessThanOrEqual(1);
  86  |     }
  87  |   }
  88  | });
  89  | 
  90  | // ---------------------------------------------------------------------------
  91  | // J8 — @full: edge cases
  92  | // ---------------------------------------------------------------------------
  93  | 
  94  | test("@full J8-5 scorecard includes build timestamp when 200", async ({ request }) => {
  95  |   const res = await request.get(`${BACKEND}/api/quality/scorecard`);
  96  |   if (res.status() !== 200) return;
  97  |   const card = (await res.json()) as { build?: string; all_gates_pass?: boolean };
  98  |   expect(card.build).toBeTruthy();
  99  | });
  100 | 
  101 | test("@full J8-6 replay p95 in scorecard is a positive number in seconds", async ({
  102 |   request,
  103 | }) => {
  104 |   const res = await request.get(`${BACKEND}/api/quality/scorecard`);
  105 |   if (res.status() !== 200) return;
  106 |   const card = (await res.json()) as {
  107 |     replay_p50_seconds?: number;
  108 |     replay_p95_seconds?: number;
  109 |   };
  110 |   if (card.replay_p95_seconds !== undefined) {
  111 |     expect(card.replay_p95_seconds).toBeGreaterThan(0);
  112 |     expect(card.replay_p95_seconds).toBeLessThan(300); // must be under 5 min
  113 |   }
  114 | });
  115 | 
  116 | test("@full J8-7 scorecard run_at is a valid ISO timestamp when present", async ({
  117 |   request,
  118 | }) => {
  119 |   const res = await request.get(`${BACKEND}/api/quality/scorecard`);
  120 |   if (res.status() !== 200) return;
  121 |   const card = (await res.json()) as { run_at?: string };
  122 |   if (card.run_at) {
  123 |     const parsed = new Date(card.run_at);
  124 |     expect(parsed.getTime()).not.toBeNaN();
  125 |   }
  126 | });
  127 | 
  128 | test("@full J8-8 scorecard X-Request-ID header is present", async ({ request }) => {
  129 |   const res = await request.get(`${BACKEND}/api/quality/scorecard`);
  130 |   const requestId = res.headers()["x-request-id"];
  131 |   expect(requestId).toBeTruthy();
  132 |   expect(requestId).toMatch(
  133 |     /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  134 |   );
  135 | });
  136 | 
```