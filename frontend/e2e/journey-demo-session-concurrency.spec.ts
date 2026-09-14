/** Demo session concurrency — two isolated sessions (smoke). */

import { test, expect } from "@playwright/test";
import {
  BACKEND,
  DEMO_SESSION_HEADER,
  bindDemoSessionToPage,
  ensureDemoSession,
  getLastScan,
  promoteFinding,
  resetBackend,
  runDemoScan,
  runDemoScanFromUiOrSeed,
  sessionHeaders,
  startRecoveryFromOpportunitiesList,
  type ScanFinding,
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

  test("PSC-2 opportunity lists are isolated per session", async ({ playwright }) => {
    const ctxA = await playwright.request.newContext();
    const ctxB = await playwright.request.newContext();
    const sidA = await ensureDemoSession(ctxA);
    const sidB = await ensureDemoSession(ctxB);

    const scanA = await runDemoScan(ctxA, sidA);
    const scanB = await runDemoScan(ctxB, sidB);
    const promotedA = await promoteFinding(
      ctxA,
      scanA.findings[0] as Record<string, unknown>,
      sidA
    );
    const promotedB = await promoteFinding(
      ctxB,
      scanB.findings[0] as Record<string, unknown>,
      sidB
    );

    const listA = await ctxA.get(`${BACKEND}/api/opportunities`, {
      headers: { [DEMO_SESSION_HEADER]: sidA },
    });
    const listB = await ctxB.get(`${BACKEND}/api/opportunities`, {
      headers: { [DEMO_SESSION_HEADER]: sidB },
    });
    const idsA = ((await listA.json()) as Array<{ opportunity_id: string }>).map(
      (o) => o.opportunity_id
    );
    const idsB = ((await listB.json()) as Array<{ opportunity_id: string }>).map(
      (o) => o.opportunity_id
    );

    expect(idsA).toContain(promotedA.opportunity_id);
    expect(idsB).toContain(promotedB.opportunity_id);
    expect(new Set(idsA).intersection(new Set(idsB)).size).toBe(0);

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

test.describe("@full demo session UI isolation", () => {
  test("PSC-4 two browser contexts run independent promote flows", async ({
    browser,
    playwright,
  }) => {
    test.setTimeout(180_000);

    const reqA = await playwright.request.newContext();
    const reqB = await playwright.request.newContext();
    const sidA = await ensureDemoSession(reqA);
    const sidB = await ensureDemoSession(reqB);
    expect(sidA).not.toBe(sidB);
    await resetBackend(reqA, sidA);
    await resetBackend(reqB, sidB);

    const ctxA = await browser.newContext();
    const ctxB = await browser.newContext();
    const pageA = await ctxA.newPage();
    const pageB = await ctxB.newPage();

    await bindDemoSessionToPage(pageA, sidA);
    await bindDemoSessionToPage(pageB, sidB);

    await runDemoScanFromUiOrSeed(pageA, reqA, sidA);
    await runDemoScanFromUiOrSeed(pageB, reqB, sidB);

    const scanA = await getLastScan(reqA, sidA);
    const scanB = await getLastScan(reqB, sidB);
    const findingA = scanA.findings.find(
      (f) => f.resource_id === "i-offline-demo-session-a"
    ) as ScanFinding;
    const findingB = scanB.findings.find(
      (f) => f.resource_id === "vol-offline-demo-session-b"
    ) as ScanFinding;
    expect(findingA).toBeTruthy();
    expect(findingB).toBeTruthy();

    await startRecoveryFromOpportunitiesList(pageA, findingA);
    await startRecoveryFromOpportunitiesList(pageB, findingB);

    const oppIdA = pageA.url().match(/\/opportunities\/([^/?#]+)/)?.[1];
    const oppIdB = pageB.url().match(/\/opportunities\/([^/?#]+)/)?.[1];
    expect(oppIdA).toBeTruthy();
    expect(oppIdB).toBeTruthy();
    expect(oppIdA).not.toBe(oppIdB);

    const listA = await reqA.get(`${BACKEND}/api/opportunities`, {
      headers: sessionHeaders(sidA),
    });
    const listB = await reqB.get(`${BACKEND}/api/opportunities`, {
      headers: sessionHeaders(sidB),
    });
    const idsA = ((await listA.json()) as Array<{ opportunity_id: string }>).map(
      (o) => o.opportunity_id
    );
    const idsB = ((await listB.json()) as Array<{ opportunity_id: string }>).map(
      (o) => o.opportunity_id
    );
    expect(idsA).toContain(oppIdA);
    expect(idsB).toContain(oppIdB);
    expect(new Set(idsA).intersection(new Set(idsB)).size).toBe(0);

    await ctxA.close();
    await ctxB.close();
    await reqA.dispose();
    await reqB.dispose();
  });
});
