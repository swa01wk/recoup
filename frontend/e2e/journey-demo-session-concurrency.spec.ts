/** Demo session concurrency — two isolated sessions (smoke). */

import { test, expect } from "@playwright/test";
import {
  BACKEND,
  DEMO_SESSION_HEADER,
  ensureDemoSession,
  promoteFinding,
  resetBackend,
  runDemoScan,
} from "./helpers";

test.describe("@smoke demo session concurrency", () => {
  test("PSC-1 two sessions can each run demo scan", async ({ playwright }) => {
    const ctxA = await playwright.request.newContext();
    const ctxB = await playwright.request.newContext();
    const sidA = await ensureDemoSession(ctxA);
    const sidB = await ensureDemoSession(ctxB);
    expect(sidA).not.toBe(sidB);

    const scanA = await runDemoScan(ctxA, sidA);
    const scanB = await runDemoScan(ctxB, sidB);
    expect(scanA.findings.length).toBeGreaterThan(0);
    expect(scanB.findings.length).toBeGreaterThan(0);

    await ctxA.dispose();
    await ctxB.dispose();
  });

  test("PSC-3 session reset does not clear other session opps", async ({ playwright }) => {
    const ctxA = await playwright.request.newContext();
    const ctxB = await playwright.request.newContext();
    const sidA = await ensureDemoSession(ctxA);
    const sidB = await ensureDemoSession(ctxB);

    const scanB = await runDemoScan(ctxB, sidB);
    await runDemoScan(ctxA, sidA);
    const finding = scanB.findings[0] as Record<string, unknown>;
    await promoteFinding(ctxB, finding, sidB);

    await resetBackend(ctxA, sidA);

    const listA = await ctxA.get(`${BACKEND}/api/opportunities`, {
      headers: { [DEMO_SESSION_HEADER]: sidA },
    });
    const listB = await ctxB.get(`${BACKEND}/api/opportunities`, {
      headers: { [DEMO_SESSION_HEADER]: sidB },
    });
    expect(listA.ok()).toBeTruthy();
    expect(listB.ok()).toBeTruthy();
    const oppsA = (await listA.json()) as unknown[];
    const oppsB = (await listB.json()) as unknown[];
    expect(oppsA).toHaveLength(0);
    expect(oppsB.length).toBeGreaterThan(0);

    await ctxA.dispose();
    await ctxB.dispose();
  });
});
