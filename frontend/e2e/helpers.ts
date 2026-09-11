/**
 * Shared helpers for Recoup Playwright tests.
 */
import { type Page, type APIRequestContext, expect } from "@playwright/test";

/** Backend base URL — override with PLAYWRIGHT_BACKEND_URL or PLAYWRIGHT_BACKEND_PORT. */
export const BACKEND =
  process.env.PLAYWRIGHT_BACKEND_URL ??
  `http://127.0.0.1:${process.env.PLAYWRIGHT_BACKEND_PORT ?? "8000"}`;

/** Reset all in-memory backend state between tests. */
export async function resetBackend(request: APIRequestContext): Promise<void> {
  await request.post(`${BACKEND}/api/test/reset`);
}

/** Call POST /api/scan/demo and return the scan result. */
export async function runDemoScan(
  request: APIRequestContext
): Promise<{ total_estimated_monthly_savings_usd: number; findings: unknown[] }> {
  const res = await request.post(`${BACKEND}/api/scan/demo`);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

/** Promote a finding by resource_id from the last scan. */
export async function promoteFinding(
  request: APIRequestContext,
  finding: Record<string, unknown>
): Promise<{ opportunity_id: string }> {
  const res = await request.post(`${BACKEND}/api/scan/findings/promote`, {
    data: finding,
  });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

/** Approve an opportunity and return the updated record. */
export async function approveOpportunity(
  request: APIRequestContext,
  opportunityId: string
): Promise<Record<string, unknown>> {
  // Fetch the pending approval first
  const pendingRes = await request.get(
    `${BACKEND}/api/approvals/opportunity/${opportunityId}`
  );
  expect(pendingRes.ok()).toBeTruthy();
  const pending = (await pendingRes.json()) as {
    approval_id: string;
    claim_hash: string;
    amount: string;
    state_version: number;
  };

  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunityId}/approve`,
    {
      data: {
        principal: "playwright-test",
        claim_hash: pending.claim_hash,
        amount: pending.amount,
        state_version: pending.state_version,
        notes: "Approved by Playwright test",
      },
    }
  );
  expect(res.ok()).toBeTruthy();
  return res.json();
}

/** Mark an opportunity for further investigation (NEEDS_FOLLOWUP). */
export async function investigateOpportunity(
  request: APIRequestContext,
  opportunityId: string,
  notes = "Investigate Further — Playwright test"
): Promise<Record<string, unknown>> {
  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunityId}/investigate`,
    { data: { principal: "playwright-test", notes } }
  );
  expect(res.ok()).toBeTruthy();
  return res.json();
}

/** Decline an opportunity. */
export async function declineOpportunity(
  request: APIRequestContext,
  opportunityId: string,
  notes = "Declined by Playwright test"
): Promise<Record<string, unknown>> {
  const res = await request.post(
    `${BACKEND}/api/approvals/opportunity/${opportunityId}/decline`,
    { data: { principal: "playwright-test", notes } }
  );
  expect(res.ok()).toBeTruthy();
  return res.json();
}

/** Wait for a page element containing text to appear. */
export async function waitForText(page: Page, text: string, timeout = 10_000): Promise<void> {
  await expect(page.getByText(text)).toBeVisible({ timeout });
}

export type ScanFinding = Record<string, unknown> & {
  service?: string;
  resource_id?: string;
  estimated_monthly_savings_usd?: number;
  scenario_tag?: string;
};

/** Pick up to `count` findings from distinct AWS services (EC2, EBS, …). */
export function pickFindingsByDistinctServices(
  findings: ScanFinding[],
  count = 3
): ScanFinding[] {
  const picked: ScanFinding[] = [];
  const seenServices = new Set<string>();
  for (const f of findings) {
    const svc = String(f.service ?? "").trim();
    if (!svc || seenServices.has(svc)) continue;
    if (!f.resource_id) continue;
    seenServices.add(svc);
    picked.push(f);
    if (picked.length >= count) break;
  }
  return picked;
}

/** Latest scan payload from the backend (after demo or live scan). */
export async function getLastScan(
  request: APIRequestContext
): Promise<{
  total_estimated_monthly_savings_usd: number;
  findings: ScanFinding[];
  scan_id?: string;
}> {
  const res = await request.get(`${BACKEND}/api/scan/last`);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

export type OutcomeRecord = {
  opportunity_id?: string;
  pk?: string;
  credit_amount?: string;
  outcome_state?: string;
  sns_sent?: boolean;
  sns_sent_at?: string | null;
};

export async function listOutcomes(request: APIRequestContext): Promise<OutcomeRecord[]> {
  const res = await request.get(`${BACKEND}/api/approvals/outcomes`);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

export function outcomeForOpportunity(
  outcomes: OutcomeRecord[],
  opportunityId: string
): OutcomeRecord | undefined {
  return outcomes.find((o) => {
    if (o.opportunity_id === opportunityId) return true;
    const pk = o.pk ?? "";
    return pk === `outcome#${opportunityId}`;
  });
}

export async function getOpportunity(
  request: APIRequestContext,
  opportunityId: string
): Promise<{ id: string; state: string; potential_value: string | null }> {
  const res = await request.get(`${BACKEND}/api/opportunities/${opportunityId}`);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

/** Ledger buckets derived from opportunities + scan total (matches frontend computeLedgerData). */
export async function fetchLedgerBuckets(
  request: APIRequestContext
): Promise<{
  scanTotal: number;
  detected: number;
  pending: number;
  recovered: number;
  totalDetected: number;
}> {
  const [scan, oppsRes, pendingRes] = await Promise.all([
    getLastScan(request).catch(() => ({
      total_estimated_monthly_savings_usd: 0,
      findings: [],
    })),
    request.get(`${BACKEND}/api/opportunities`),
    request.get(`${BACKEND}/api/approvals/pending`),
  ]);
  expect(oppsRes.ok()).toBeTruthy();
  expect(pendingRes.ok()).toBeTruthy();

  const opportunities = (await oppsRes.json()) as Array<{
    id: string;
    state: string;
    potential_value: string | null;
  }>;
  const pendingApprovals = (await pendingRes.json()) as Array<{ amount: string }>;

  const pendingApprovalAmount = pendingApprovals.reduce((sum, r) => {
    const v = parseFloat(r.amount);
    return sum + (isNaN(v) ? 0 : v);
  }, 0);

  const scanTotal = scan.total_estimated_monthly_savings_usd ?? 0;
  let recovered = 0;
  let pendingFromOpps = 0;

  const canonical = (state: string): "RECOVERED" | "PENDING" | "DETECTED" => {
    const s = state.toUpperCase();
    if (["AWAITING_APPROVAL", "NEEDS_FOLLOWUP"].includes(s)) return "PENDING";
    if (["APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING", "RECOVERED"].includes(s)) {
      return "RECOVERED";
    }
    return "DETECTED";
  };

  for (const opp of opportunities) {
    const raw = parseFloat(opp.potential_value ?? "0");
    if (isNaN(raw) || raw <= 0) continue;
    const value = Math.round((raw + Number.EPSILON) * 100) / 100;
    const bucket = canonical(opp.state);
    if (bucket === "RECOVERED") recovered += value;
    else if (bucket === "PENDING") pendingFromOpps += value;
  }

  recovered = Math.round((recovered + Number.EPSILON) * 100) / 100;
  pendingFromOpps = Math.round((pendingFromOpps + Number.EPSILON) * 100) / 100;
  const pending = pendingFromOpps > 0 ? pendingFromOpps : pendingApprovalAmount;
  const totalDetected = Math.max(
    Math.round((scanTotal + Number.EPSILON) * 100) / 100,
    Math.round((recovered + pending + Number.EPSILON) * 100) / 100
  );
  const detected = Math.max(
    0,
    Math.round((totalDetected - recovered - pending + Number.EPSILON) * 100) / 100
  );

  return { scanTotal, detected, pending, recovered, totalDetected };
}

/** Operator role for UI actions that require approve/decline. */
export async function setOperatorRole(page: Page): Promise<void> {
  await page.evaluate(() => localStorage.setItem("recoup:userRole", "operator"));
}

/** Consent + Demo Scan on /scan, wait until Opportunities list is ready. */
export async function runDemoScanFromUi(page: Page): Promise<void> {
  await page.goto("/");
  await setOperatorRole(page);
  await page.goto("/scan");
  await expect(page.getByText("Account Scanner").first()).toBeVisible({ timeout: 15_000 });
  await page.getByRole("checkbox").check();
  const demoBtn = page.getByRole("button", { name: /demo scan/i });
  await expect(demoBtn).toBeEnabled({ timeout: 5_000 });
  await demoBtn.click();
  await page.waitForURL(/\/opportunities\/?$/, { timeout: 60_000 });
  await expect(page.getByText(/recovery summary|opportunities/i).first()).toBeVisible({
    timeout: 30_000,
  });
}

/** Mirror backend scan into browser localStorage (same as saveLastScan after a real UI scan). */
export async function seedBrowserScanResult(
  page: Page,
  scan: Record<string, unknown>
): Promise<void> {
  await page.goto("/");
  await page.evaluate((result) => {
    localStorage.setItem("recoup:lastScanResult", JSON.stringify(result));
    localStorage.setItem(
      "recoup:lastScanFindingCount",
      String((result.findings as unknown[])?.length ?? 0)
    );
  }, scan);
}

/**
 * Prefer real Account Scanner UI; if /scan is unavailable (stale dev server), fall back to
 * API demo scan + localStorage seed — identical post-scan state on /opportunities.
 */
export async function runDemoScanFromUiOrSeed(
  page: Page,
  request: APIRequestContext
): Promise<void> {
  await page.goto("/");
  await setOperatorRole(page);
  await page.goto("/scan");
  const scannerVisible = await page
    .getByText("Account Scanner")
    .first()
    .isVisible()
    .catch(() => false);
  if (scannerVisible) {
    await runDemoScanFromUi(page);
    return;
  }

  const scan = await runDemoScan(request);
  await seedBrowserScanResult(page, scan as Record<string, unknown>);
  await page.goto("/opportunities");
  await expect(page.getByText(/recovery summary|opportunities/i).first()).toBeVisible({
    timeout: 30_000,
  });
}

/** Reload scan findings from the backend into browser localStorage. */
export async function syncScanToBrowser(
  page: Page,
  request: APIRequestContext
): Promise<void> {
  const scan = await getLastScan(request);
  await seedBrowserScanResult(page, scan as Record<string, unknown>);
}

/** Click Start Recovery for a finding row on /opportunities. */
export async function startRecoveryFromOpportunitiesList(
  page: Page,
  finding: ScanFinding
): Promise<void> {
  const resourceId = String(finding.resource_id ?? "");
  await page.goto("/opportunities");
  await page.getByRole("button", { name: /^refresh$/i }).click();
  await expect(page.getByText("Opportunities").first()).toBeVisible({ timeout: 15_000 });

  const startBtn = page
    .locator(`span[title="${resourceId}"]`)
    .locator("xpath=ancestor::div[contains(@class,'border-b')][1]")
    .getByRole("button", { name: /start recovery/i });
  await expect(startBtn).toBeVisible({ timeout: 60_000 });
  await startBtn.click();
  await page.waitForURL(/\/opportunities\/recovery-/, { timeout: 30_000 });
}

// ---------------------------------------------------------------------------
// SSE helpers (shared by journey-sse-stream-nodes and lifecycle specs)
// ---------------------------------------------------------------------------

export interface SSEEvent {
  type: string;
  node?: string;
  duration_ms?: number;
  potential_credit?: string;
  amount?: string;
  opportunity_id?: string;
  state?: string;
  errors?: string[];
  [key: string]: unknown;
}

/**
 * Consume a text/event-stream response and return all parsed events.
 * Stops as soon as the `opportunity_done` sentinel is received.
 *
 * Uses the global `fetch` (Node 18+) available in the Playwright worker
 * process — Playwright's `APIRequestContext` does not expose the raw stream
 * body, so we call fetch directly.
 */
export async function collectSSEEvents(
  url: string,
  timeoutMs = 30_000
): Promise<SSEEvent[]> {
  const events: SSEEvent[] = [];

  const res = await fetch(url, {
    headers: { Accept: "text/event-stream" },
    signal: AbortSignal.timeout(timeoutMs),
  });

  if (!res.ok || !res.body) {
    throw new Error(`SSE fetch failed: ${res.status} ${url}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  outer: while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const dataLine = part.split("\n").find((l) => l.startsWith("data: "));
      if (!dataLine) continue;
      const jsonStr = dataLine.slice("data: ".length).trim();
      if (!jsonStr) continue;
      try {
        const ev = JSON.parse(jsonStr) as SSEEvent;
        events.push(ev);
        if (ev.type === "opportunity_done") {
          reader.cancel();
          break outer;
        }
      } catch {
        // ignore malformed SSE lines
      }
    }
  }

  return events;
}

/** Canonical 8-node pre-approval pipeline (always streamed). */
export const CANONICAL_NODES = [
  "normalize_event",
  "incident_correlation",
  "sla_contract_resolver",
  "availability_calculator",
  "evidence_collector",
  "evidence_sanitizer",
  "eligibility_reasoner",
  "risk_policy_gate",
] as const;

/** Post-approval nodes — only streamed after HITL gate is cleared. */
export const POST_APPROVAL_NODES = [
  "claim_package_generator",
  "submission_adapter",
  "case_monitor",
] as const;

/**
 * Run an opportunity with `use_strands: true`, then stream it and return
 * the run response body AND the collected SSE events.
 *
 * This is the central "Strands stream lifecycle" helper used by all LC-* tests.
 */
export async function strandsRunAndStream(
  request: APIRequestContext,
  opportunityId: string,
  { streamTimeoutMs = 30_000 }: { streamTimeoutMs?: number } = {}
): Promise<{
  runBody: {
    opportunity_id: string;
    final_state: string;
    use_strands: boolean;
    potential_credit: string | null;
    errors: string[];
  };
  events: SSEEvent[];
}> {
  const runRes = await request.post(
    `${BACKEND}/api/opportunities/${opportunityId}/run`,
    { data: { use_strands: true } }
  );
  expect(runRes.ok()).toBeTruthy();
  const runBody = (await runRes.json()) as {
    opportunity_id: string;
    final_state: string;
    use_strands: boolean;
    potential_credit: string | null;
    errors: string[];
  };

  const events = await collectSSEEvents(
    `${BACKEND}/api/opportunities/${opportunityId}/stream`,
    streamTimeoutMs
  );

  return { runBody, events };
}

/**
 * Poll GET /api/opportunities/:id until `state` matches `expected` or timeout.
 *
 * Returns the final opportunity record (whether or not it matched).
 * Throws if the backend returns a non-200 response on the first call.
 */
export async function pollUntilState(
  request: APIRequestContext,
  opportunityId: string,
  expected: string | string[],
  { intervalMs = 500, timeoutMs = 15_000 }: { intervalMs?: number; timeoutMs?: number } = {}
): Promise<{ id: string; state: string; potential_value: string | null; state_version: number }> {
  const targets = Array.isArray(expected)
    ? expected.map((s) => s.toUpperCase())
    : [expected.toUpperCase()];

  const deadline = Date.now() + timeoutMs;
  let last: { id: string; state: string; potential_value: string | null; state_version: number } | null = null;

  while (Date.now() < deadline) {
    const res = await request.get(`${BACKEND}/api/opportunities/${opportunityId}`);
    if (!res.ok()) throw new Error(`GET /api/opportunities/${opportunityId} returned ${res.status()}`);
    last = await res.json();
    if (targets.includes(last!.state.toUpperCase())) return last!;
    await new Promise((r) => setTimeout(r, intervalMs));
  }

  throw new Error(
    `Timed out waiting for opportunity ${opportunityId} to reach state(s) ${targets.join("|")}. ` +
      `Last observed: ${last?.state ?? "unknown"}`
  );
}
