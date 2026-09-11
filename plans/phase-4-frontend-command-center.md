# Phase 4 — Frontend Command Center

> **Historical implementation plan.** Targets below reflect mid-build intent. **Current product & metrics:** [docs/README.md](../docs/README.md) · [STATUS.md](../STATUS.md) · [docs/judge-demo.md](../docs/judge-demo.md).



**Timeline:** Day 8–11 (Target: by Sep 11, 2026)  
**Status:** `[✅] Complete — Sep 1, 2026`  
**Superseded by:** `plans/phase-8-frontend-redesign.md` (Sep 3, 2026)  
**Depends on:** Phase 1 (API contracts); Phases 2 & 3 can be partially parallel

> **Note (Sep 3, 2026):** Phase 4 was completed as planned. The resulting UI (dark "SLA Recovery Command Center") is being replaced by Phase 8 — a full redesign aligned with the hackathon winning strategy: Recovery Dashboard, Recovery Ledger hero metric, role system (Operator / Viewer), IAM security boundary visualization, and a Finding → Opportunity promotion bridge. See `plans/phase-8-frontend-redesign.md`.

> **As-built (Sep 11):** Phase 8/9 delivered ledger + promote + detail HITL; current IA is **opportunities-first** — see Phase 8 as-built and [docs/frontend-guide.md](../docs/frontend-guide.md). This document describes the **original** six-view Command Center spec (superseded).

---

## Objective

Build the Recoup Command Center — a polished, professional Next.js UI with six distinct views: Command Center (dashboard), Opportunity Detail, Evidence Room, Decision Inbox, Agent Trace, and Evaluation/Quality view. The UI must be judge-ready: clear at a glance, trustworthy language, correct empty/loading/error states, and obvious simulation badges.

---

## Goals

- [ ] Next.js 14+ app with TypeScript, Tailwind CSS, and shadcn/ui component library
- [ ] Command Center dashboard: opportunity list, recovered value, prevented value, system status
- [ ] Opportunity Detail: status timeline, financial summary, confidence indicators
- [ ] Evidence Room: required fields checklist, sanitized preview, redaction count, provenance hashes
- [ ] Decision Inbox: approval card with full financial detail; approve/decline actions; expiry countdown
- [ ] Agent Trace: node-by-node visualization, tool calls, policy decisions, durations
- [ ] Evaluation/Quality view: scorecard with scenario count, success rate, unsafe action rate
- [ ] All views have intentional loading, empty, error, and simulation states
- [ ] LIVE AWS ACTION and VERIFIED REPLAY badges clearly visible where relevant
- [ ] Live URL deployed and accessible without judge AWS credentials

---

## Workstreams

### 4.1 Project Setup

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --app
npm install @shadcn/ui lucide-react recharts
npx shadcn-ui@latest init
```

**Folder structure:**
```
frontend/src/
├── app/
│   ├── layout.tsx              # Root layout with nav sidebar
│   ├── page.tsx                # Redirect → /opportunities
│   ├── opportunities/
│   │   ├── page.tsx            # Command Center
│   │   └── [id]/
│   │       ├── page.tsx        # Opportunity Detail
│   │       ├── evidence/page.tsx
│   │       ├── trace/page.tsx
│   │       └── approve/page.tsx
│   ├── inbox/page.tsx          # Decision Inbox
│   └── quality/page.tsx        # Evaluation scorecard
├── components/
│   ├── command-center/
│   ├── evidence-room/
│   ├── decision-inbox/
│   ├── agent-trace/
│   └── shared/
│       ├── SimulationBadge.tsx
│       ├── LiveActionBadge.tsx
│       ├── OpportunityStateBadge.tsx
│       ├── ConfidenceIndicator.tsx
│       └── MoneyDisplay.tsx    # Always shows "Potential" vs "Confirmed"
├── lib/
│   ├── api.ts                  # Typed API client
│   └── sse.ts                  # SSE hook for live streaming
└── types/
    └── recoup.ts               # TypeScript mirror of Python domain models
```

### 4.2 Command Center (Dashboard)

**Route:** `/opportunities`

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  RECOUP                           [System Status: Live]  │
├────────────────┬────────────────┬────────────────────────┤
│ Potential      │ Recovered      │ Active                  │
│ Recovery       │ (Confirmed)    │ Investigations          │
│ $0.35          │ $0             │ 1                       │
│ [Real billing] │                │                         │
├─────────────────────────────────────────────────────────┤
│ OPPORTUNITIES                    [▶ Run Canonical Replay] │
├────────┬────────────┬───────────┬───────────┬────────────┤
│ ID     │ Service    │ State     │ Value     │ Mode        │
├────────┼────────────┼───────────┼───────────┼────────────┤
│ op-... │ API GW     │ AWAITING  │ $0.35     │ [REPLAY]   │
│        │ us-east-1  │ APPROVAL  │ Potential │            │
└────────┴────────────┴───────────┴───────────┴────────────┘
```

**Components:**
```tsx
// components/command-center/MetricCard.tsx
export function MetricCard({ label, value, sublabel, badge }: MetricCardProps) {
  return (
    <div className="rounded-xl border bg-card p-6">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {sublabel && <p className="text-xs text-muted-foreground mt-1">{sublabel}</p>}
      {badge && <span className="ml-2 text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded">{badge}</span>}
    </div>
  );
}
```

### 4.3 Opportunity Detail

**Route:** `/opportunities/[id]`

Shows the full recovery story timeline:
1. Signal detected (event source, timestamp)
2. Correlation complete (incident hypothesis)
3. SLA contract resolved (version, commitment)
4. Availability calculated (uptime %, tier, credit formula)
5. Evidence collected (X/Y fields)
6. Eligibility assessed (confident/uncertain)
7. Human approval required / approved
8. Claim submitted / case monitoring

**Key component: Financial Summary**
```tsx
// Always shows "Potential recovery" until AWS confirms
// Never displays "Credit confirmed" without AWS case resolution
function FinancialSummary({ result }: { result: AvailabilityResult }) {
  return (
    <div className="border rounded-lg p-4 space-y-2">
      <div className="flex justify-between">
        <span className="text-sm text-muted-foreground">Monthly Uptime</span>
        <span className="font-mono">{result.monthly_uptime_pct}%</span>
      </div>
      <div className="flex justify-between">
        <span className="text-sm text-muted-foreground">SLA Commitment</span>
        <span className="font-mono">99.95%</span>
      </div>
      <div className="flex justify-between text-amber-700">
        <span className="text-sm font-medium">Credit Tier</span>
        <span className="font-mono font-bold">{result.tier_pct}%</span>
      </div>
      <Separator />
      <div className="flex justify-between">
        <span className="text-sm text-muted-foreground">Billed Charges</span>
        <span className="font-mono">${result.billed_charges.toLocaleString()}</span>
      </div>
      <div className="flex justify-between text-green-700">
        <span className="font-medium">Potential Recovery</span>
        <span className="font-mono font-bold text-lg">${result.potential_credit.toLocaleString()}</span>
      </div>
      <CollapsibleTrace steps={result.calculation_trace} />
    </div>
  );
}
```

### 4.4 Evidence Room

**Route:** `/opportunities/[id]/evidence`

```
┌──────────────────────────────────────────────────────────┐
│ EVIDENCE ROOM                        [VERIFIED REPLAY]   │
├──────────────────────────────────────────────────────────┤
│ Required Fields (4/4 present)                            │
│                                                          │
│ ✓ API ID          ev-a1b2  sha256:abc... [sanitized]     │
│ ✓ Request Logs    ev-c3d4  sha256:def... [sanitized]     │
│   ⚠  2 values redacted — Auth headers masked            │
│ ✓ Billing Record  ev-e5f6  sha256:ghi... [source: CE]    │
│ ✓ SLA Contract    ev-g7h8  sha256:2022-05-05.yaml        │
│                                                          │
│ Missing Fields   (0 missing)                             │
│ Possible Exclusions                                      │
│   None identified                                        │
│                                                          │
│ Redaction Report                                         │
│   Total values redacted: 2                               │
│   Patterns applied: Authorization, Cookie, API Key       │
│   Raw evidence: encrypted at rest, never shown here      │
└──────────────────────────────────────────────────────────┘
```

**Sanitized preview component:**
```tsx
function EvidenceItemRow({ item }: { item: EvidenceItem }) {
  return (
    <div className="flex items-start gap-3 py-2">
      <StatusIcon status={item.status} />
      <div className="flex-1">
        <div className="flex gap-2 items-center">
          <span className="font-medium text-sm">{item.type}</span>
          <code className="text-xs text-muted-foreground">{item.id}</code>
          {item.sanitized_uri && (
            <Badge variant="outline" className="text-xs">sanitized</Badge>
          )}
        </div>
        <div className="text-xs text-muted-foreground font-mono mt-0.5">
          {item.hash}
        </div>
        {/* Never show raw content; only show sanitized preview or redaction count */}
        {item.sensitivity === "HIGH" && (
          <p className="text-xs text-amber-600 mt-1">
            ⚠ Sensitive field — raw value encrypted, not shown
          </p>
        )}
      </div>
    </div>
  );
}
```

### 4.5 Decision Inbox

**Route:** `/inbox` and `/opportunities/[id]/approve`

```
┌──────────────────────────────────────────────────────────┐
│ DECISION INBOX                                           │
├──────────────────────────────────────────────────────────┤
│ AWAITING YOUR APPROVAL                    ⏱ 23:47:12    │
│                                                          │
│ ACTION                                                   │
│ Submit SLA Credit Claim to AWS Support                   │
│                                                          │
│ AMOUNT         $0.35 (real AWS billing)                  │
│ BASIS          10% of $3.51 billed charges               │
│ SERVICE        Amazon API Gateway — us-east-1            │
│ BILLING CYCLE  Sep 2026                                  │
│ EVIDENCE       4 of 4 required fields present            │
│                                                          │
│ CALCULATION                                              │
│ (8,634 / 8,640) × 100 = 99.9306% → 10% tier             │
│ $3.51 × 10% = $0.35                                      │
│                                                          │
│ SLA BASIS      API Gateway SLA 2022-05-05                │
│                sha256:abc123...                          │
│                                                          │
│ ⚠ VERIFIED REPLAY MODE                                  │
│ Real AWS Support submission is DISABLED.                 │
│ Approving will trigger: Simulate Submission              │
│ → REPLAY case id only. No real case will be created.    │
│                                                          │
│         [Decline]              [Approve →]               │
└──────────────────────────────────────────────────────────┘
```

**Approval expiry countdown:**
```tsx
function ApprovalExpiryCountdown({ expiresAt }: { expiresAt: string }) {
  const [remaining, setRemaining] = useState(getRemaining(expiresAt));
  useEffect(() => {
    const interval = setInterval(() => setRemaining(getRemaining(expiresAt)), 1000);
    return () => clearInterval(interval);
  }, [expiresAt]);

  const isUrgent = remaining.totalSeconds < 3600;
  return (
    <span className={cn("font-mono text-sm", isUrgent && "text-red-600 font-bold")}>
      ⏱ {remaining.display}
    </span>
  );
}
```

### 4.6 Agent Trace View

**Route:** `/opportunities/[id]/trace`

Visualizes the Strands Graph execution:

```
normalize_event        ✓  48ms    [Deterministic]
incident_correlation   ✓  4.2s    [Agent]  3 tool calls
sla_contract_resolver  ✓  12ms    [Deterministic]
availability_calculator✓  8ms     [Deterministic]
evidence_collector     ✓  6.1s    [Agent]  4 tool calls
evidence_sanitizer     ✓  34ms    [Deterministic]  2 values redacted
eligibility_reasoner   ✓  3.8s    [Agent]
risk_policy_gate       ✓  89ms    [Deterministic]  REQUIRE_APPROVAL
claim_package_generator✓  2.9s    [Agent]
  [⏸ AWAITING HUMAN APPROVAL]
submission_adapter     —  pending
case_monitor           —  pending

Tool calls:
  get_cloudwatch_metrics   ALLOW  2.1s  ev-a1b2
  get_health_event         ALLOW  1.8s  ev-c3d4
  store_evidence           ALLOW  0.3s  ev-e5f6
  submit_support_case      DENY   0ms   (no approval)
```

```tsx
function TraceNodeRow({ node }: { node: TraceNode }) {
  return (
    <div className="flex items-center gap-4 py-2 border-b">
      <NodeStatusIcon status={node.status} />
      <span className="font-mono text-sm w-48">{node.name}</span>
      <NodeTypeBadge type={node.type} />
      {node.duration_ms && (
        <span className="text-xs text-muted-foreground">{node.duration_ms}ms</span>
      )}
      {node.tool_calls?.length > 0 && (
        <span className="text-xs text-muted-foreground">
          {node.tool_calls.length} tool calls
        </span>
      )}
      {node.policy_decision && (
        <PolicyDecisionBadge decision={node.policy_decision} />
      )}
    </div>
  );
}
```

### 4.7 Evaluation / Quality View

**Route:** `/quality`

```
RECOUP QUALITY — build 2026.09.xx
──────────────────────────────────────────────────────
Golden-path success (20 runs)     20 / 20    100%  ✓
Overall scenario success           46 / 50    92%   ✓
Evidence recall                   49 / 50    98%   ✓
Tool selection accuracy            48 / 50    96%   ✓
Financial math correctness        100%              ✓
Unsafe external actions            0                ✓
Unsupported claim rate             0 / 50    0%    ✓
Replay P95 completion time         < 60s            ✓
Trace completeness                 100%             ✓
```

### 4.8 Shared Components

```tsx
// Simulation badge — always visible on replay opportunities
function SimulationBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
      VERIFIED REPLAY
    </span>
  );
}

// Live action badge — for Phase 6 EC2 demo
function LiveActionBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800 animate-pulse">
      <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
      LIVE AWS ACTION
    </span>
  );
}

// Money display — always shows "potential" until confirmed
function MoneyDisplay({ amount, confirmed }: { amount: Decimal; confirmed: boolean }) {
  return (
    <div>
      <span className="text-2xl font-bold text-green-700">
        ${amount.toLocaleString()}
      </span>
      <span className="ml-2 text-xs text-muted-foreground">
        {confirmed ? "Confirmed Recovery" : "Potential Recovery"}
      </span>
    </div>
  );
}
```

### 4.9 FastAPI Backend (UI-facing)

**Location:** `backend/src/recoup/api/`

```python
# Endpoints required by frontend
GET  /api/opportunities              → list[OpportunityListItem]
GET  /api/opportunities/{id}         → OpportunityDetail
GET  /api/opportunities/{id}/evidence → EvidenceManifest
GET  /api/opportunities/{id}/trace   → TraceView
GET  /api/opportunities/{id}/stream  → SSE stream
POST /api/opportunities/{id}/approve → ApprovalRecord
POST /api/opportunities/{id}/decline → dict
POST /api/replay/api-gateway-sla     → ReplayResponse
GET  /api/evaluations/latest         → EvaluationScorecard
GET  /healthz                        → {"status": "ok"}
```

**No AWS credentials in frontend:** All API calls go through FastAPI, which uses the Recoup runtime IAM role. Frontend receives only sanitized, typed responses.

### 4.10 Deployment

- **Frontend:** Vercel (free tier) or AWS Amplify
- **Backend:** AWS App Runner or EC2 with auto-start script
- **URL:** Must be reachable in incognito without AWS credentials
- **Uptime:** Must remain available through Oct 8, 2026

---

## Definition of Done

| Check | Criteria |
|-------|----------|
| All 6 views | Render correctly with real API data from replay run |
| Simulation badge | Visible on every replay opportunity; correct on live action path |
| Financial language | "Potential recovery" everywhere; no "confirmed" without real AWS resolution |
| Evidence Room | Shows sanitized preview; never raw content; redaction count visible |
| Decision Inbox | Approval card shows full detail; countdown works; approve/decline functional |
| Trace view | All 11 nodes shown with status, duration, and tool call summary |
| Evaluation view | Scorecard renders with current metrics from CI |
| Empty/loading/error | All 3 states implemented for every view |
| Live URL | Accessible in incognito; replay can be triggered; no AWS credentials required |

---

## Post-Implementation Documentation

> Created in `plans/docs/` after phase completion.

- `docs/frontend-architecture.md` — Component hierarchy, routing, and data flow
- `docs/api-reference.md` — Complete UI-facing API reference with request/response schemas
- `docs/ux-decisions.md` — Key UX decisions: simulation badges, money language, evidence redaction display
- `docs/deployment-guide.md` — How to deploy frontend and backend; environment variables; uptime strategy

---

## Risks

| Risk | Mitigation |
|------|-----------|
| UI looks like a prototype | Use shadcn/ui components; spend time on typography, spacing, and color |
| Demo URL goes down during judging | Monitor with uptime service; keep cost under free tier |
| Raw evidence leaks into UI | API response types exclude raw fields; TypeScript enforces this |
| Approval card misleads judge | Explicit VERIFIED REPLAY warning with "no real case" explanation |
