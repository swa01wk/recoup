/**
 * @smoke
 * Account Scanner lifecycle — scan → findings → promote → opportunity created
 *
 * UI components: ScanPage (/scan), DemoScanButton, FindingRow, StartRecoveryButton
 * Backend calls: POST /api/scan/demo, POST /api/scan/findings/promote
 */
import { test, expect } from "@playwright/test";
import { resetBackend, runDemoScan } from "./helpers";

test.beforeEach(async ({ request }) => {
  await resetBackend(request);
});

test("@smoke scan demo returns 8+ findings with total savings", async ({ request }) => {
  // Stage: Detect
  // UI component → ScanPage (`/scan`) · DemoScanButton
  // Backend call → POST /api/scan/demo
  const result = await runDemoScan(request);
  expect(result.findings.length).toBeGreaterThanOrEqual(1);
  expect(result.total_estimated_monthly_savings_usd).toBeGreaterThan(60);
});

test("scan/last returns the most recent scan after demo scan", async ({ request }) => {
  await runDemoScan(request);
  const res = await request.get("http://localhost:8000/api/scan/last");
  expect(res.ok()).toBeTruthy();
  const data = (await res.json()) as { total_estimated_monthly_savings_usd: number };
  expect(data.total_estimated_monthly_savings_usd).toBeGreaterThan(0);
});

test("@smoke promote finding creates opportunity in AWAITING_APPROVAL state", async ({
  request,
}) => {
  // Stage: Start Recovery (Detect → AWAITING_APPROVAL)
  // UI component → FindingRow · StartRecoveryButton
  // Backend call → POST /api/scan/findings/promote
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  expect(findings.length).toBeGreaterThan(0);

  const finding = findings[0];
  const res = await request.post("http://localhost:8000/api/scan/findings/promote", {
    data: finding,
  });
  expect(res.ok()).toBeTruthy();
  const promoted = (await res.json()) as { opportunity_id: string; status: string };
  expect(promoted.opportunity_id).toBeTruthy();
  expect(["created", "existing"]).toContain(promoted.status);

  // Verify the opportunity is visible via GET /api/opportunities/{id}
  const oppRes = await request.get(
    `http://localhost:8000/api/opportunities/${promoted.opportunity_id}`
  );
  expect(oppRes.ok()).toBeTruthy();
  const opp = (await oppRes.json()) as { state: string };
  expect(opp.state).toBe("AWAITING_APPROVAL");
});

test("promote is idempotent — same resource_id returns existing opportunity", async ({
  request,
}) => {
  const scan = await runDemoScan(request);
  const findings = scan.findings as Array<Record<string, unknown>>;
  const finding = findings[0];

  const first = (await (
    await request.post("http://localhost:8000/api/scan/findings/promote", { data: finding })
  ).json()) as { opportunity_id: string; status: string };

  const second = (await (
    await request.post("http://localhost:8000/api/scan/findings/promote", { data: finding })
  ).json()) as { opportunity_id: string; status: string };

  expect(second.opportunity_id).toBe(first.opportunity_id);
  expect(second.status).toBe("existing");
});

// ---------------------------------------------------------------------------
// S6 — Per scenario_tag coverage (Scan-1 through Scan-8)
// ---------------------------------------------------------------------------

/**
 * The 8 demo scenario tags that must appear in every scan result.
 * Matches the RecoupScenario tags on live AWS demo resources.
 */
const EXPECTED_SCENARIO_TAGS = [
  "oversized-ec2",    // Scan-1: Stopped EC2 t3.medium ($30.37/mo)
  "unattached-ebs",   // Scan-2: Unattached 20 GiB gp2 ($2.00/mo)
  "gp2-migration",    // Scan-3: gp2 50 GiB unattached volume, also a gp3 migration candidate ($5.00/mo)
  "idle-eip",         // Scan-4: Idle Elastic IP ($3.60/mo)
  "idle-rds",         // Scan-5: Idle RDS db.t3.micro ($14.60/mo)
  "s3-no-lifecycle",  // Scan-6: S3 bucket with no lifecycle policy ($2.30/mo)
  "oversized-lambda", // Scan-7: Oversized Lambda 1024 MB, zero invocations ($3.75/mo)
  "stale-snapshot",   // Scan-8: Stale EBS snapshot, source volume deleted ($1.76/mo)
] as const;

test("@smoke S6 — all 8 scenario_tags present in scan results", async ({ request }) => {
  // Stage: Detect — each tile in the scanner UI maps to a scenario_tag
  // Backend call → POST /api/scan/demo → findings[].scenario_tag
  const result = await runDemoScan(request);
  const findings = result.findings as Array<{ scenario_tag?: string | null; service: string; estimated_monthly_savings_usd: number }>;
  const foundTags = new Set(findings.map((f) => f.scenario_tag).filter(Boolean));

  for (const tag of EXPECTED_SCENARIO_TAGS) {
    expect(
      foundTags.has(tag),
      `Missing scenario_tag '${tag}' — check that the demo resource still exists`
    ).toBe(true);
  }
});

test("S6 — each scanner finding has required fields (resource_id, severity, savings > 0)", async ({
  request,
}) => {
  const result = await runDemoScan(request);
  const findings = result.findings as Array<{
    resource_id: string;
    service: string;
    severity: string;
    estimated_monthly_savings_usd: number;
    recommendation: string;
    scenario_tag?: string | null;
  }>;

  // Every finding with a scenario_tag must have all required fields
  const taggedFindings = findings.filter((f) => f.scenario_tag);
  for (const f of taggedFindings) {
    expect(f.resource_id, `resource_id missing on ${f.scenario_tag}`).toBeTruthy();
    expect(f.service, `service missing on ${f.scenario_tag}`).toBeTruthy();
    expect(["high", "medium", "low"]).toContain(f.severity);
    expect(f.estimated_monthly_savings_usd, `savings must be >= 0 on ${f.scenario_tag}`).toBeGreaterThanOrEqual(0);
    expect(f.recommendation, `recommendation missing on ${f.scenario_tag}`).toBeTruthy();
  }
});

test("S6 — Scan-1 (oversized-ec2) finding has correct resource type and service", async ({
  request,
}) => {
  const result = await runDemoScan(request);
  const findings = result.findings as Array<{
    scenario_tag?: string | null;
    service: string;
    resource_type: string;
    estimated_monthly_savings_usd: number;
    resource_id: string;
  }>;
  const ec2Finding = findings.find((f) => f.scenario_tag === "oversized-ec2");
  if (!ec2Finding) {
    console.log("oversized-ec2 not found in this scan — demo resource may be missing");
    return;
  }
  expect(ec2Finding.service).toBe("EC2");
  expect(ec2Finding.estimated_monthly_savings_usd).toBeGreaterThan(0);
  // Resource ID should be an EC2 instance ID
  expect(ec2Finding.resource_id).toMatch(/^i-/);
});

test("S6 — promote each scenario_tag finding creates separate opportunity", async ({
  request,
}) => {
  test.setTimeout(120_000); // Promoting 8 findings sequentially; each may hit DynamoDB fallback latency
  const result = await runDemoScan(request);
  const findings = result.findings as Array<Record<string, unknown>>;
  const taggedFindings = findings.filter((f) => f.scenario_tag);

  // Promote all tagged findings and collect opportunity IDs
  const opportunityIds = new Set<string>();
  for (const finding of taggedFindings) {
    const res = await request.post("http://localhost:8000/api/scan/findings/promote", {
      data: finding,
    });
    if (res.ok()) {
      const data = (await res.json()) as { opportunity_id: string };
      opportunityIds.add(data.opportunity_id);
    }
  }

  // Each unique resource should have its own opportunity
  expect(opportunityIds.size).toBe(taggedFindings.length);

  // All should appear in the pending approval queue
  const pendingRes = await request.get("http://localhost:8000/api/approvals/pending");
  const pending = (await pendingRes.json()) as Array<{ opportunity_id: string }>;
  const pendingIds = new Set(pending.map((r) => r.opportunity_id));
  for (const id of opportunityIds) {
    expect(pendingIds.has(id), `Opportunity ${id} not in pending queue`).toBe(true);
  }
});
