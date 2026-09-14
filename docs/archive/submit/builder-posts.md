# Builder.aws Posts — Agents for Humans Hackathon

Three posts required for +0.6 bonus. Each title must include **"Agents for Humans"**.

| # | Target date | Status | URL |
|---|-------------|--------|-----|
| 1 | Sep 8 | ✅ Published (keep as-is) | https://builder.aws.com/content/3JKKaMeu6Cbc2HQQjmAiOosEVOH/building-recoup-agents-for-humans-and-how-we-designed-a-safe-aws-recovery-workflow-with-strands-graph |
| 2 | Sep 15 | ✅ Published — trust / J-FULL | https://builder.aws.com/content/3JKron5aTHK1KpAaoIbxNdSd9IH/agents-for-humans-and-making-ai-financial-decisions-trustworthy-cedar-evidence-redaction-and-hitl-in-recoup |
| 3 | Sep 15 | ✅ Published — proof / scorecard | https://builder.aws.com/content/3JKtrHzpq4RFxt6kXlNYT5uY1uJ/agents-for-humans-and-how-we-proved-recoup-works-419-backend-127-e2e-tests-and-zero-unsafe-actions |

**Full copy-paste bodies:** [builder-post-drafts.md](builder-post-drafts.md)

---

## Post 1 — Architecture (publish by Sep 8)

**Title:** *Building Recoup: Agents for Humans — How We Designed a Safe AWS Recovery Workflow with Strands Graph*

**Outline:**
- 11-node graph: 5 agent nodes + 6 deterministic
- Why LLMs propose but Cedar policy decides
- Cedar policy file walkthrough (`infra/policy/recoup-policy.cedar`)
- Node snippets from `backend/src/recoup/graph/nodes.py`
- Diagram: `normalize_event → incident_correlation [Strands] → … → risk_policy_gate [Cedar] → HITL → submission_adapter → case_monitor`

**Assets:** `architecture/architecture.svg`, screenshot of Agent Trace with [Strands] labels

---

## Post 2 — Safety (publish by Sep 10)

**Title:** *Agents for Humans — Making AI Financial Decisions Trustworthy: Cedar Policies, Evidence Redaction, and HITL Approvals in Recoup*

**Outline:**
- 8-pattern evidence sanitizer (`evidence/sanitizer.py`)
- Autonomy classes (GREEN/YELLOW/RED/BLACK)
- HITL binding: claim_hash + amount + state_version
- Cedar hard-forbid on `terminate_ec2_instance`
- Approval card "wow moment": risk tier + action + rollback before Approve

**Assets:** Opportunity detail HITL screenshot, Cedar policy excerpt

---

## Post 3 — Evaluation (publish by Sep 12)

**Title:** *Agents for Humans — How We Proved Recoup Works: 419 Backend + 127 E2E Tests, Deterministic Math, and Zero Unsafe Actions*

**Outline:**
- 47 YAML scenario categories
- Golden path: 20/20 consecutive runs at ~23ms P95
- Adversarial suite: prompt injection, binding tamper, BLACK tool enforcement
- Ship gate CI (`scripts/assert_ship_gates.py`)
- Financial math is never LLM-generated — Decimal arithmetic only

**Assets:** Terminal or API screenshot of `GET /api/quality/scorecard` JSON (`all_gates_pass`)

---

## After Publishing

1. Paste URLs into Devpost submission form
2. Update the table above with live links
3. Verify posts are publicly visible (incognito)
