# Phase 9 — Competitive UI Gaps & Polish

> **Historical implementation plan.** Targets below reflect mid-build intent. **Current product & metrics:** [docs/README.md](../docs/README.md) · [STATUS.md](../STATUS.md) · [docs/judge-demo.md](../docs/judge-demo.md).



**Timeline:** Sep 7–11, 2026 (before Sep 11 feature cutoff)
**Status:** `[x] Complete`
**Depends on:** Phases 0–8 ✅ Complete
**Source:** `Recoup_vs_ProsperOps_and_AWS_FinOps_Agent_Competitive_Positioning_and_Demo_Strategy.docx` §§ 8, 14, 15.2, 17

---

## As-built (Sep 11, 2026)

Backend approval context (`risk_tier`, `action_description`, `rollback_context`) and opportunity detail UI enhancements **shipped**. README competitive tables and FAQ **shipped**. Primary navigation is **`/opportunities`** (not a separate Decision Inbox page). Demo script: [docs/judge-demo.md](../docs/judge-demo.md).

---

## Why This Phase Exists

Cross-checking the full competitive positioning document against the live UI revealed 7 concrete gaps:

1. `trace.hypothesis_summary` is in the API (`TraceResult` type) but **never rendered** — this directly proves the agent explains WHY spend is unintended (checklist item §14.2)
2. `trace.case_outcome` is in the API but **never rendered** — post-action verification is required by §14.7
3. ALL approval cards lack risk tier, action description, and rollback context — §14.5 and §8 require the approval screen to show "WHY, evidence, risk, rollback" not just a dollar amount
4. The competitive tagline *"Investigate. Prove. Approve. Recover. Verify."* (§13) is not in the UI
5. The Agent Trace doesn't label which nodes are `[Strands Agent]` vs `[Deterministic]` — judges can't see where Bedrock reasoning is happening
6. Intent classification ("Abandoned" / "Anomalous" / "Policy-violating") is not surfaced from `eligibility.reasons` — §15.2 requires "Add intent inference"
7. The dashboard subtitle doesn't position Recoup as a spend-incident investigator (§17.4: "AWS provides the FinOps intelligence; Recoup closes the recovery loop.")

---

## Goals

- [ ] Render `hypothesis_summary` as Root-Cause Hypothesis card in opportunity detail
- [ ] Render `case_outcome` as Post-Action Verification panel in opportunity detail
- [ ] Enhance ALL approval cards (not just EC2): risk tier badge + action description + rollback note
- [ ] Add *"Investigate. Prove. Approve. Recover. Verify."* tagline to dashboard header
- [ ] Label each node in Agent Trace as `[Strands]` or `[Deterministic]`
- [ ] Add intent classification badge to Eligibility card
- [ ] Update dashboard subtitle to competitive positioning sentence
- [ ] Update pipeline from 7-step to 10-step V1.1 loop (§15.3)
- [ ] Add `risk_tier`, `action_description`, `rollback_context` to `ApprovalRecord` (backend)
- [ ] README: judge FAQ / objection-handling section (6 objections from §10)
- [ ] README: three-way competitive comparison table (§17.3)
- [ ] README: judging rubric callout table (5 criteria × how Recoup scores)

---

## Competitive Document Reference

### §8 — The "Wow Moment" (approval screen)

> "The approval screen should not merely say 'Terminate 3 instances?' It should show WHY Recoup believes they are orphaned, the estimated recovery, the operational evidence, the risk classification, and the rollback/safety plan. **That is the visible difference between an agent and a script.**"

Every approval card (SLA and EC2) must show all five elements before the Approve button.

### §13 — Messaging (use verbatim in UI and README)

Use:
- *"Autonomous cloud spend recovery."*
- *"From spend anomaly to verified recovery."*
- *"Investigate. Prove. Approve. Recover. Verify."*
- *"AWS gives you the signals; Recoup turns them into safe recovery actions."*
- *"Evidence-driven FinOps remediation for engineering and cloud operations teams."*

Avoid in all UI copy and README:
- *"AI-powered AWS cost optimizer."*
- *"Better than ProsperOps."*
- *"Automatically shuts down idle infrastructure."*
- *"Replaces AWS Compute Optimizer / Cost Explorer."*
- *"Fully autonomous cloud management."*

### §15.2 — V1.1 Loop (10 steps → pipeline visualization)

| Step | Label | Node |
|------|-------|------|
| 1 | Detect | normalize_event |
| 2 | Investigate | incident_correlation (Strands) |
| 3 | Correlate | — (CloudTrail/CW cross-ref) |
| 4 | Explain | eligibility_reasoner (Strands) |
| 5 | Prove | evidence_collector + sanitizer |
| 6 | Plan | claim_package_generator (Strands) |
| 7 | Policy | risk_policy_gate (Cedar) |
| 8 | Approve | HITL |
| 9 | Remediate | submission_adapter |
| 10 | Verify | case_monitor |
| 11 | Record | Recovery Ledger |

### §17.4 — Positioning Sentence

> "AWS provides the FinOps intelligence; Recoup closes the recovery loop."

Use as the dashboard subtitle (replaces or supplements *"Investigate. Prove. Approve. Recover. Verify."*).

### §10 — Judge Objection Handling (add as README FAQ)

| Objection | Answer |
|-----------|--------|
| "Doesn't AWS already have Compute Optimizer?" | Yes — Recoup consumes AWS optimization signals. Compute Optimizer identifies opportunities; Recoup investigates surrounding context, establishes intent, packages evidence, chooses a safe recovery workflow, executes under policy, and verifies the outcome. |
| "Isn't this just ProsperOps?" | ProsperOps is a mature autonomous FinOps optimizer, especially for commitments. Recoup is an autonomous cloud-spend investigator and recovery operator focused on cross-signal causal investigation, evidence, risk-tiered HITL remediation, and technical + financial verification. |
| "Why use an agent?" | Because deciding whether spend is truly waste often requires multi-step evidence gathering and contextual reasoning across heterogeneous signals. The agent is valuable in the investigative loop; deterministic policy still governs all sensitive actions. |
| "Why not just automate everything with rules?" | Known, repetitive optimizations should be deterministic. Recoup targets ambiguous cases where the system must determine intent and causality before applying bounded automation. |
| "How do you prevent hallucinated destructive actions?" | The model does not get unrestricted control. Evidence requirements, action allowlists, environment protections, thresholds, and approval rules are deterministic. The execution tool validates identifiers and policy before acting. |
| "How do you prove savings?" | The Recovery Ledger stores the pre-action baseline, estimated recovery, executed change, post-action resource/health checks, and subsequent cost delta. Estimated savings and realized savings remain separate metrics. |

---

## Implementation

### Backend Change (minimal — 1 file)

**`backend/src/recoup/approval/flow.py`** — add three fields to `ApprovalRecord`:

```python
risk_tier: str  # "GREEN" | "YELLOW" | "RED" — derived from Cedar policy context
action_description: str  # human-readable: "Submit real SLA credit claim to AWS Support ($0.35 from actual billing)"
rollback_context: str  # "Reversible: restart instance / withdraw claim within 24h"
```

Populate in `HITLFlow.create_request()` based on action type. No breaking changes.

---

### Frontend Changes (5 files)

#### 1. `frontend/src/app/opportunities/[id]/page.tsx` — 3 additions

**A. Root-Cause Hypothesis card** (render `trace.hypothesis_summary`):
```
┌─ Root-Cause Hypothesis ─ [Strands Agent] ────────────────────┐
│ "[hypothesis_summary text from Strands agent investigation]" │
│                                                              │
│ Intent: Abandoned  ·  Confidence: 87%  ·  Signals: 6        │
└──────────────────────────────────────────────────────────────┘
```
Position: top of Results Panel (before Availability Result). Always shown when `trace.hypothesis_summary` is not null.

**B. Post-Action Verification panel** (render `trace.case_outcome`):
```
┌─ Post-Action Verification ───────────────────────────────────┐
│ Technical:  Resource state STOPPED ✓                         │
│ Application: Health checks passing ✓                         │
│ Financial:  Estimated $7.59/mo · Savings monitoring started  │
│ Case:       SUBMITTED · Case #XXXX                           │
└──────────────────────────────────────────────────────────────┘
```
Position: bottom of Results Panel. Shown when `trace.case_outcome` is not null.

**C. Intent classification badge** on Eligibility card:
- Derive label from `eligibility.reasons[]`:
  - Contains "idle" / "abandoned" / "orphan" → `Abandoned` (amber)
  - Contains "anomal" → `Anomalous` (red)
  - Contains "policy" → `Policy-violating` (red)
  - Contains "inefficient" / "oversized" / "gp2" → `Expected-but-inefficient` (yellow)
  - Otherwise → `Recoverable` (blue)
- Show as badge next to the `Eligible / Not Eligible` badge

**D. Strands vs Deterministic labels** on NodeRow:
```typescript
const STRANDS_NODES = new Set([
  "incident_correlation",
  "eligibility_reasoner",
  "claim_package_generator",
]);
// Render [Strands] or [Det.] tag on each node row
```

#### 2. `frontend/src/app/approvals/page.tsx` — enhanced ApprovalCard

Replace bare amount/hash display with a structured context panel for ALL approval types:
```
┌─────────────────────────────────────────────────────┐
│  Risk Tier: [RED]  Action: Submit real SLA credit claim  │
│  Impact:    $0.35 recovery from real AWS billing         │
│  Rollback:  Withdraw claim within 24h               │
│  Evidence:  6 signals collected ✓                   │
└─────────────────────────────────────────────────────┘
```
For EC2 approvals: keep existing safety checklist AND add the new context panel above it.

#### 3. `frontend/src/app/page.tsx` — dashboard messaging

- Subtitle line 1: *"Investigate. Prove. Approve. Recover. Verify."*
- Subtitle line 2: *"AWS provides the FinOps intelligence; Recoup closes the recovery loop."*
- Pipeline: expand from 7 to 10-step V1.1 loop

#### 4. `frontend/src/lib/api.ts` — type updates

Add to `ApprovalRecord`:
```typescript
risk_tier?: string;
action_description?: string;
rollback_context?: string;
```

#### 5. `README.md` — three additions

- **Judge FAQ section** (6 objections from §10 with pre-written answers)
- **Three-way competitive table** (ProsperOps vs AWS FinOps Agent vs Recoup from §17.3)
- **Judging rubric callout** (5 criteria × how Recoup scores each)

---

## File Summary

| File | Change | Priority |
|------|--------|----------|
| `frontend/src/app/opportunities/[id]/page.tsx` | Hypothesis card + Verification panel + Intent badge + Strands labels | P0 |
| `frontend/src/app/approvals/page.tsx` | Risk tier + action description + rollback on ALL cards | P0 |
| `frontend/src/app/page.tsx` | Tagline + positioning sentence + 10-step pipeline | P1 |
| `frontend/src/lib/api.ts` | `ApprovalRecord` type extensions | P1 |
| `backend/src/recoup/approval/flow.py` | `risk_tier`, `action_description`, `rollback_context` fields | P1 |
| `README.md` | FAQ + three-way table + rubric callouts + live URL | P1 |

---

## Definition of Done

| Check | Criteria |
|-------|----------|
| Hypothesis rendered | `trace.hypothesis_summary` visible in opportunity detail |
| Verification rendered | `trace.case_outcome` visible as Post-Action Verification section |
| Intent badge | Eligibility card shows intent classification badge |
| Strands labels | Agent Trace labels each node as `[Strands]` or `[Det.]` |
| Approval context | ALL approval cards show risk tier + action + rollback |
| Tagline | Dashboard shows "Investigate. Prove. Approve. Recover. Verify." |
| Pipeline | 10-step V1.1 loop on dashboard |
| README FAQ | 6 objection/answer pairs in README |
| Three-way table | Competitive comparison table in README |
| Rubric callouts | 5-criteria scoring table in README |
| `npm run build` | 0 TypeScript errors |
| Pre-demo checklist | All 12 items from §14 pass |

---

## Kill Criteria (if schedule slips before Sep 11)

| Feature | Cut if | Safe? |
|---------|--------|-------|
| Intent classification badge | Sep 10 not met | Yes — minor UI |
| Strands vs Det. labels | Sep 10 not met | Yes — nice-to-have |
| 10-step pipeline | Sep 10 not met | Yes — 7-step still works |
| Backend `risk_tier` field | Risk of regression | Yes — hard-code in frontend for demo |
| Hypothesis card | DO NOT CUT | No — this is checklist item 2 |
| Verification panel | DO NOT CUT | No — this is checklist item 7 |
| Approval context panel | DO NOT CUT | No — this is checklist item 5 |
