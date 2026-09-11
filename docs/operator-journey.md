# Recoup — Primary Operator Journey (J-FULL)

**Status:** This is the **main cost-recovery lifecycle Recoup ships today**, polished for the AWS Agents for Humans hackathon demo.  
**Last updated:** Sep 11, 2026  
**Checklist entry:** [USER_JOURNEY_CHECKLIST.md — J-FULL](../USER_JOURNEY_CHECKLIST.md#j-full--full-operator-journey-scan--3-hitl-paths--ledger--sns)  
**Playwright:** `frontend/e2e/journey-full-discovery-triage-ledger.spec.ts`

---

## Executive summary

Recoup’s **operator loop** is:

1. **Reset** demo state (optional in UI; required in automated tests).  
2. **Scan** the AWS account for recoverable spend (Account Scanner).  
3. **Choose findings** — in the canonical demo, **three different services**, one after another.  
4. **Start Recovery** on each (promote finding → opportunity).  
5. **Human triage:** **Approve** (SNS recovery report), **Investigate Further**, or **Decline**.  
6. **Recovery Ledger** reflects remaining, pending, and recovered dollars.

This path is **implemented end-to-end** in frontend + backend, covered by **Playwright J-FULL** and overlapping journeys (J2, J6, inbox, UI), and **manually verified** (including live SNS to `recoup-alerts`).

It is **not** the same as the **SLA verified replay** journey (`/replay`, J4), which runs the full 11-node graph for API Gateway credits. Both coexist in Recoup; **J-FULL is the account-scanner operator story**.

---

## Lifecycle diagram

```text
┌─────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│ 1. Reset    │───▶│ 2. Account Scan  │───▶│ 3. Pick 3 services  │
│ (test/admin)│    │ 9 AWS scanners   │    │ on /opportunities   │
└─────────────┘    └──────────────────┘    └──────────┬──────────┘
                                                      │
                        ┌─────────────────────────────┼─────────────────────────────┐
                        ▼                             ▼                             ▼
               ┌────────────────┐           ┌────────────────┐           ┌────────────────┐
               │ 4–5a Approve   │           │ 4–5b Investigate│           │ 4–5c Decline   │
               │ SNS + RECOVERED│           │ NEEDS_FOLLOWUP  │           │ DENIED         │
               └────────┬───────┘           └────────┬───────┘           └────────┬───────┘
                        └─────────────────────────────┼─────────────────────────────┘
                                                      ▼
                                            ┌──────────────────┐
                                            │ 6. Recovery      │
                                            │ Ledger buckets   │
                                            └──────────────────┘
```

**Pipeline semantics (cost recovery):**

- **Backend:** Detect (scanners) → Package (`promote`) → Policy (`REQUIRE_APPROVAL` at promote) → HITL → Record (outcomes + SNS on approve).  
- **UI (detail page):** 6 stages — `Detect → Investigate → Plan → Policy → Approve → Record` — see `COST_RECOVERY_STAGES` in `frontend/src/lib/recovery-storage.ts`.  
- **UI (dashboard):** 11-step V1.1 strip — see `pipelineStageForOpportunity()` in the same file.

**Agent graph (11 nodes):** **Not streamed on promote.** Promote builds a ready-to-approve `GraphState` from scanner output. Optional **Re-run agent investigation** on opportunity detail calls `POST /api/opportunities/{id}/run` with Strands/Bedrock. Full graph execution is central to **SLA replay**, not this loop.

---

## Step 1 — Reset demo data

### Operator intent

Start from a clean slate: no stale opportunities, approvals, promoted findings, or ledger outcomes bleeding between demos or tests.

### Frontend

- Sidebar **↺ Reset Demo Data** (calls admin reset when configured).  
- Playwright uses API reset only (`helpers.resetBackend`).

### Backend

| Endpoint | Role |
|----------|------|
| `POST /api/test/reset` | Playwright / dev — clears in-memory state; **does not** clear demo scan cache (performance) |
| `POST /api/admin/reset?clear_scan_cache=true` | Stronger demo reset — optional scan cache clear |

Shared implementation clears graph states, promoted findings, scan audit/history, EC2 demo cache, approvals (DynamoDB + memory), and outcome records:

```281:317:backend/src/recoup/api/main.py
def _do_full_reset(*, clear_scan_cache: bool = False) -> dict[str, str]:
    """Shared implementation for full in-memory state reset."""
    from .routes.opportunities import _graph_states
    from .routes.scan import _promoted_findings, _scan_audit_log, _last_scan_result, _scan_history

    _graph_states.clear()
    _promoted_findings.clear()
    _scan_audit_log.clear()
    _scan_history.clear()
    if clear_scan_cache:
        _last_scan_result.clear()
    # ... ec2_demo, clear_all_approvals, outcome_repo.clear_all()
```

Test entry point:

```339:358:backend/src/recoup/api/main.py
@app.post("/api/test/reset", tags=["meta"])
def test_reset() -> dict[str, str]:
    """
    Reset all in-memory state for Playwright test isolation.
    ...
    """
    return _do_full_reset(clear_scan_cache=False)
```

### Playwright

```9:11:frontend/e2e/helpers.ts
export async function resetBackend(request: APIRequestContext): Promise<void> {
  await request.post(`${BACKEND}/api/test/reset`);
}
```

---

## Step 2 — AWS Account Scanner

### Operator intent

Discover recoverable spend across the connected account (demo: one-click **Demo Scan** using env-configured read role).

### Frontend

Route: **`/scan`** (`frontend/src/app/scan/page.tsx`).

- Security consent checkbox (`SecurityAccessSummary`).  
- **Demo Scan** → `api.scan.demo()` → `saveLastScan(res)` → navigate to **`/opportunities`**.

```155:172:frontend/src/app/scan/page.tsx
  const handleScan = async (mode: "full" | "preview" | "demo") => {
    ...
      const res =
        mode === "demo"
          ? await api.scan.demo()
          : mode === "preview"
          ? await api.scan.preview(form)
          : await api.scan.full(form);

      saveLastScan(res);
      window.dispatchEvent(new CustomEvent("recoup:scanComplete", { detail: res.findings.length }));
      router.push("/opportunities");
```

Findings persist in **localStorage** (`recoup:lastScanResult`) via `saveLastScan` in `frontend/src/lib/recovery-storage.ts`.

### Backend

**Demo scan endpoint:**

```398:410:backend/src/recoup/api/routes/scan.py
@router.post("/demo")
def scan_demo() -> ScanResult:
    """
    Phase 6f — One-click demo scan using the pre-configured RecoupReadOnlyRole.
    ...
    """
```

**Nine parallel scanners** (real AWS read APIs via STS `CustomerConnection`):

```225:235:backend/src/recoup/api/routes/scan.py
_ALL_SCANNERS = [
    EC2Scanner(),
    EBSScanner(),
    EIPScanner(),
    RDSScanner(),
    S3Scanner(),
    LambdaScanner(),
    LBScanner(),
    CWLogsScanner(),
    CostExplorerScanner(),
]
```

Supporting APIs:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/scan/last` | Last scan payload (Playwright + UI refresh) |
| GET | `/api/scan/audit` | Scan audit trail |
| POST | `/api/scan/full` | Full scan with Role ARN + External ID |
| POST | `/api/scan/preview` | Cost Explorer + EC2 only |

Demo workloads target **8 scenario tags** (~$87.82/mo aggregate) — see `docs/demo-workloads.md`.

---

## Step 3 — Three distinct services

### Operator intent

Work **three findings from different services** (e.g. EC2, EBS, RDS) so the demo shows breadth, not three rows of the same service.

### Frontend

**`/opportunities`** — table built from `findings` (localStorage) + promoted map + opportunity states (`useRecoveryData`, `buildOpportunityRows` in `frontend/src/app/opportunities/page.tsx`).

Service filter dropdown uses distinct `finding.service` values.

### Backend / tests

No separate API — selection is operator or test logic. Playwright helper `pickFindingsByDistinctServices` in `frontend/e2e/helpers.ts` (picks up to N findings with unique `service` from `GET /api/scan/last`).

---

## Step 4 — Start Recovery (discovery / promote)

### Operator intent

Move a finding from **detected** to **actionable opportunity** awaiting human approval.

### Frontend

**Start Recovery** on an opportunity row → `handleStartRecovery` → `api.scan.promote(finding)` → redirect to detail:

```199:204:frontend/src/app/opportunities/page.tsx
  const handleStartRecovery = async (finding: Finding) => {
    ...
      const res = await api.scan.promote(finding);
      router.push(`/opportunities/${res.opportunity_id}`);
```

Row action labels: `frontend/src/components/recoup/opportunity-row.tsx` (`primaryAction`).

### Backend

**Promote** creates `recovery-{uuid}` opportunity, synthetic graph artifacts from the finding, and HITL request:

```581:588:backend/src/recoup/api/routes/scan.py
@router.post("/findings/promote", response_model=PromoteResponse)
def promote_finding(finding: Finding) -> PromoteResponse:
    """
    Promote a scan Finding into an Opportunity in the recovery pipeline.
    Creates an in-memory GraphState, registers it with the opportunities store,
    and opens an HITL approval request for operator review.
    """
```

Key effects (same handler):

- `GraphState` with `current_state=AWAITING_APPROVAL`, `policy_decision=REQUIRE_APPROVAL`.  
- `HITLFlow.create_request` with **claim_hash**, **amount**, **state_version**.  
- Action: `apply_cost_recovery` or `stop_demo_instance` for idle EC2 — `_recovery_action_for_finding()`.

```575:578:backend/src/recoup/api/routes/scan.py
def _recovery_action_for_finding(finding: Finding) -> str:
    if finding.finding_type == "IDLE_INSTANCE" or finding.service == "EC2":
        return "stop_demo_instance"
    return "apply_cost_recovery"
```

Idempotent re-promote of same `resource_id` returns `status: "existing"` when content unchanged.

**Promoted registry:** `GET /api/scan/findings/promoted`.

### Opportunity detail UI

**`/opportunities/[id]`** — Cost Recovery Analysis, pipeline strip, **Approval Required** `DecisionCard` when approval is PENDING (`frontend/src/app/opportunities/[id]/page.tsx`, `frontend/src/components/recoup/decision-card.tsx`).

---

## Step 5 — Human triage (three paths)

HITL buttons are always enabled for the single product role (**operator**); the Viewer role switcher was removed (`frontend/src/hooks/useRole.tsx`).

### 5a — Approve (+ SNS recovery report)

**Frontend** — claim-bound approve, redirect to ledger:

```184:197:frontend/src/app/opportunities/[id]/page.tsx
  const handleApprove = async () => {
    ...
      await api.approvals.approve(id, {
        principal,
        claim_hash: approval.claim_hash,
        amount: approval.amount,
        state_version: approval.state_version,
        notes: "Approved via Recoup",
      });
      setApprovalMsg("Approved — redirecting to ledger…");
      ...
      setTimeout(() => router.push("/recovery"), 1200);
```

**Backend** — validate binding, approve, SNS flag, state → APPROVED → RECOVERED (cost recovery):

```210:270:backend/src/recoup/api/routes/approvals.py
@router.post("/opportunity/{opportunity_id}/approve")
def approve_opportunity(...):
    ...
    result["sns_notification_sent"] = flow.last_sns_notification_sent
    _transition_opportunity_state(..., new_state=OpportunityState.APPROVED, ...)
    if updated.action != "stop_demo_instance":
        _transition_opportunity_state(..., new_state=OpportunityState.RECOVERED, ...)
```

**HITL + SNS + ledger write** inside `HITLFlow.approve()`:

```288:315:backend/src/recoup/approval/flow.py
        sns_sent = self._send_sns_recovery_report(updated)
        self._last_sns_notification_sent = sns_sent
        ...
            outcome_repo.record_sns_notification(self._opportunity_id, sns_sent)
        ...
            outcome_repo.mark_recovered(
                opportunity_id=self._opportunity_id,
                credit_amount=updated.amount,
            )
```

**Email body** for SNS:

```28:72:backend/src/recoup/notifications.py
def format_recovery_report_email(...) -> tuple[str, str]:
    ...
    subject = f"[Recoup] Recovery Report — {service} · ${savings_per_month}/mo · {severity.upper()}"
```

**Publish:**

```75:108:backend/src/recoup/notifications.py
def notify_sns(subject: str, message: str) -> bool:
    ...
        sns.publish(TopicArn=topic_arn, Subject=subject[:100], Message=message)
```

Config: `RECOUP_SNS_TOPIC_ARN` (e.g. `recoup-alerts`). Playwright uses `RECOUP_SNS_DRY_RUN=1` in `playwright.config.ts` webServer.

**Manual confirmation:** Live SNS subscription received full JSON notification (Sep 2026 session).

---

### 5b — Investigate Further (no SNS)

**Frontend:**

```220:228:frontend/src/app/opportunities/[id]/page.tsx
  const handleInvestigate = async () => {
    ...
      await api.approvals.investigate(id, { principal, notes: "Investigate Further" });
```

**Backend** — approval record declined with `[INVESTIGATE]` prefix; opportunity **NEEDS_FOLLOWUP**:

```273:315:backend/src/recoup/api/routes/approvals.py
@router.post("/opportunity/{opportunity_id}/investigate")
def investigate_opportunity(...):
    ...
    _transition_opportunity_state(..., new_state=OpportunityState.NEEDS_FOLLOWUP, ...)
```

**Ledger bucket:** `NEEDS_FOLLOWUP` → **Pending** (`toCanonicalLifecycle`):

```125:131:frontend/src/lib/recovery-storage.ts
  if (["AWAITING_APPROVAL", "NEEDS_FOLLOWUP"].includes(s)) {
    return "PENDING";
  }
```

No SNS in investigate path.

---

### 5c — Decline (no SNS)

**Frontend:** `handleDecline` → `api.approvals.decline`.

**Backend** — opportunity **DENIED**:

```318:343:backend/src/recoup/api/routes/approvals.py
@router.post("/opportunity/{opportunity_id}/decline")
def decline_opportunity(...):
    ...
    _transition_opportunity_state(..., new_state=OpportunityState.DENIED, ...)
```

Terminal negatives return to **Detected/remaining** bucket for ledger math (`toCanonicalLifecycle` default).

No SNS.

---

## Step 6 — Recovery Ledger

### Operator intent

See **Potential Savings → Remaining → Pending Approval → Recovered** aligned with decisions on the three opportunities.

### Frontend

| Surface | File |
|---------|------|
| Summary banner | `/opportunities` — `RecoveryLedger` `variant="summary"` |
| Full ledger + chart | `/recovery` — `frontend/src/app/recovery/page.tsx` |
| Data hook | `frontend/src/hooks/useRecoveryData.ts` — merges API opportunities + `GET /api/approvals/outcomes` |

Bucket math:

```281:316:frontend/src/components/ui/recovery-ledger.tsx
export function computeLedgerData(
  scanTotal: number,
  opportunities: Array<{ state: string; potential_value: string | null }>,
  pendingApprovalAmount: number
): RecoveryLedgerData {
  ...
  // remaining (detected) + pending + recovered ≈ totalDetected (scan scope)
```

### Backend

| Source | Role |
|--------|------|
| `GET /api/opportunities` | Opportunity states + `potential_value` |
| `GET /api/approvals/outcomes` | `sns_sent`, `credit_amount`, `outcome_state` |
| `outcome_repo` | Persists recovered credits; `record_sns_notification` |

List outcomes: `backend/src/recoup/api/routes/approvals.py` (`GET /outcomes`).

---

## Agent pipeline vs this journey

| Component | In J-FULL? | Code anchor |
|-----------|------------|-------------|
| 9 AWS scanners | Yes | `scan.py` `_ALL_SCANNERS` |
| STS read role | Yes | `CustomerConnection` — `backend/src/recoup/models/connection.py` |
| Promote → GraphState + HITL | Yes | `scan.py` `promote_finding` |
| Cedar policy gate | Yes (at promote: `REQUIRE_APPROVAL`) | `GraphState.policy_decision` |
| 11-node Strands graph (streaming) | No (on promote) | `backend/src/recoup/graph/recoup_graph.py` — used heavily in **replay** |
| Strands/Bedrock optional re-run | Optional on detail | `POST /api/opportunities/{id}/run` |
| SNS on approve | Yes | `approval/flow.py`, `notifications.py` |
| Live EC2 stop | Separate J5 path | `backend/src/recoup/tools/ec2_tools.py`, `api/routes/ec2_demo.py` |

**Hackathon pitch alignment:** *Detect waste with real scanners → human approves with claim binding → ledger shows recovered savings → SNS emails the recovery report.*

---

## Testing confirmation

### Playwright — this journey (authoritative E2E)

| Artifact | Coverage |
|----------|----------|
| `frontend/e2e/journey-full-discovery-triage-ledger.spec.ts` | Single `@smoke @e2e` test: steps 1–6 in **one browser session**; SNS on approve; investigate/decline guards |
| `frontend/e2e/helpers.ts` | `resetBackend`, `runDemoScanFromUiOrSeed`, `startRecoveryFromOpportunitiesList`, `fetchLedgerBuckets`, `listOutcomes` |
| `frontend/playwright.config.ts` | Starts backend + frontend; `RECOUP_SNS_DRY_RUN=1` |

Run:

```bash
cd frontend
npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts
```

### Playwright — related (same product, partial overlap)

| Spec | Overlap |
|------|---------|
| `journey-operator-primary.spec.ts` (J2) | Scan → promote → approve (one finding) |
| `decision-inbox.spec.ts` | Approve / investigate / decline (API) |
| `journey-recovery-ledger.spec.ts` (J9) | Ledger after approve |
| `scan.spec.ts` | Demo scan + promote |
| `journey-ui-browser.spec.ts` | `/scan`, Start Recovery, Approve click |

### Manual

- Account Scanner demo scan → opportunities table → opportunity detail HITL.  
- **Live SNS** to `recoup-alerts` with `[Recoup] Recovery Report — …` subject (verified).  
- Broader demo script: `HACKATHON_DEMO.md` (adds SLA replay + EC2 live stop scenes).

---

## Related journeys (not J-FULL)

| Journey | Route / ID | Purpose |
|---------|------------|---------|
| SLA verified replay | `/replay`, J4 | $0.35 API Gateway credit; full graph + SSE |
| EC2 idle stop | EC2 demo API, J5 | Live `StopInstances` after approve |
| Governance | Dashboard tiles, J10–J12 | CloudTrail, tags, Cost Explorer |

Recoup is **hackathon-complete** when you present **J-FULL as the primary operator lifecycle** and optionally deep-link SLA or EC2 as proof of agent depth and live AWS.

---

## Quick reference — API map (J-FULL)

| Step | HTTP |
|------|------|
| Reset | `POST /api/test/reset` |
| Scan | `POST /api/scan/demo` |
| Promote | `POST /api/scan/findings/promote` |
| Approve | `POST /api/approvals/opportunity/{id}/approve` |
| Investigate | `POST /api/approvals/opportunity/{id}/investigate` |
| Decline | `POST /api/approvals/opportunity/{id}/decline` |
| Ledger data | `GET /api/opportunities`, `GET /api/approvals/outcomes`, `GET /api/scan/findings/promoted` |

Full API docs: [api-reference.md](api-reference.md).

---

## Documentation & cleanup

- **Docs aligned to this journey (Sep 11, 2026):** [README.md](../README.md), [judge-demo.md](judge-demo.md), [demo-playbook.md](demo-playbook.md), [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md), [architecture-overview.md](architecture-overview.md).  
- **When to change code vs docs-only:** [code-changes-timing.md](code-changes-timing.md).  
- **Stale or superseded markdown:** [stale-documents.md](stale-documents.md).  
- **Plan to remove stale code** (replay UI, demo APIs, legacy tests): [stale-code-removal-plan.md](stale-code-removal-plan.md).
