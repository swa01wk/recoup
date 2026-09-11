# Phase 7 — Polish, Submission & Video

> **Historical implementation plan.** Targets below reflect mid-build intent. **Current product & metrics:** [docs/README.md](../docs/README.md) · [STATUS.md](../STATUS.md) · [docs/judge-demo.md](../docs/judge-demo.md).



**Timeline:** Day 12–14 (Target: Sep 13 internal deadline; Sep 14 official deadline)
**Status:** `[~] In progress` — docs/playbooks synced Sep 11; video + Devpost remain
**Depends on:** Phases 0–9 ✅ Complete

---

## As-built demo path (use for video — Sep 11, 2026)

Do **not** follow the legacy Command Center / Decision Inbox / Viewer checklist below without reading this block.

1. `docker compose up` or local backend **8000** / frontend **3000**
2. **`/scan`** — consent → Demo Scan → **`/opportunities`**
3. Three findings, **three services** → **Start Recovery** on each
4. **`/opportunities/{id}`** — Approve / Investigate / Decline (claim-bound)
5. **`/recovery`** — ledger buckets (+ SNS on approve)
6. Quality: `curl /api/quality/scorecard` → `all_gates_pass` (**6 gates**)
7. Canonical doc: [docs/operator-journey.md](../docs/operator-journey.md) · [docs/judge-demo.md](../docs/judge-demo.md) · [docs/video-script.md](../docs/video-script.md)
8. Optional depth: `curl /api/quality/scorecard`; pytest golden replay; `POST /api/opportunities/{id}/run` (no `/api/replay/*`)

**Tests:** 393 backend collected · 118 Playwright (15 specs) — see [docs/README.md](../docs/README.md).

---

## Objective

Final polish, competition submission preparation, video production, and three builder.aws posts. Everything in this phase exists to maximize the judge score. A smaller, flawless submission beats an impressive but brittle one.

**Competitive positioning:** Recoup is an *Autonomous Cloud Spend Recovery Agent* — a spend-incident investigator and recovery operator. It is not a FinOps dashboard, not a rightsizer, not a commitment optimizer.

---

## Goals

- [ ] Video ≤ 5:00, public on YouTube/Vimeo, covers problem/audience/why/demo
- [ ] Live URL accessible in incognito; replay works without AWS credentials
- [ ] Public repo: README, architecture diagram, license visible from repo root
- [ ] Three builder.aws posts published (0.2 each → +0.6 bonus)
- [ ] All Devpost fields completed in English; AWS Builder ID verified
- [ ] All links tested from a different device/account
- [ ] Architecture diagram matches deployed reality
- [ ] Sep 11 feature cutoff respected; only bug fixes and polish after Sep 11
- [ ] Internal deadline submission by Sep 13 (not Sep 14 last minute)

---

## Competitive Positioning (from positioning document)

### The positioning sentence

> "AWS provides the FinOps intelligence; Recoup closes the recovery loop."

### One-liner answers (must be deliverable in under 30 seconds)

**"Why not ProsperOps?"**
> ProsperOps is a mature autonomous FinOps optimizer, especially for commitments and workload scheduling. Recoup is an autonomous cloud-spend investigator and recovery operator focused on cross-signal causal investigation, evidence, risk-tiered HITL remediation, and technical + financial verification.

**"Why not AWS FinOps Agent?"**
> AWS FinOps Agent investigates anomalies and surfaces recommendations. Recoup goes further: it assembles an evidence-backed Recovery Case, runs the proposed action through deterministic Cedar policy, obtains explicit human approval with rollback context, executes a bounded AWS action, verifies technical health and financial outcome, and closes the case in the Recovery Ledger.

**"Why not AWS Compute Optimizer?"**
> Compute Optimizer identifies opportunities. Recoup investigates surrounding context, establishes intent, packages evidence, chooses a safe recovery workflow, executes under policy, and verifies the outcome.

### Three-way competitive boundary (§17.3)

| Dimension | ProsperOps | AWS FinOps Agent | Recoup |
|-----------|-----------|-----------------|--------|
| Primary job | Autonomous cloud economics optimization | FinOps investigation, cost answers, recommendation routing | Agentic spend-incident remediation and recovery |
| Strongest domain | Commitments, rates, workload optimization | AWS cost anomalies, cost Q&A, AWS-native recommendations | Ambiguous spend incidents requiring evidence, governance, action |
| Investigation | Not central public model | Core capability | Core capability |
| Root-cause / change attribution | Not central positioning | Core capability using CloudTrail | Core + intent + dependency reasoning |
| Recommendation source | Own optimization engines | Cost Optimization Hub / Compute Optimizer + agent | Agent-created recovery plan informed by AWS signals |
| Execution model | Autonomous optimization within configured domains | Primarily investigates, reports, routes | Policy-governed bounded remediation |
| HITL | Not central to core autonomous story | Engineering decision after findings routed | Explicit approval state inside recovery workflow |
| Post-action technical verification | Not primary | Not primary documented workflow | Core requirement |
| Recovery accounting | Savings / optimization outcomes | Cost reports and recommendation estimates | Projected vs realized recovery ledger |

### What Recoup should NOT lead with (§9)

| Avoid as headline | Reason |
|-------------------|--------|
| Savings Plan / RI recommendations | ProsperOps territory — unfavorable comparison |
| Generic cost dashboard | Low originality; AWS tools already cover it |
| Idle-resource list alone | Make investigation + evidence + action the center |
| Scheduling by itself | ProsperOps Scheduler already automates schedules |
| LLM chatbot over Cost Explorer | Thin wrapper; underuses Strands |
| Fully autonomous destructive actions | Weakens safety story; use HITL visibly |
| Too many scenarios in video | One flagship + one fast secondary is stronger than six shallow examples |

### Judge objection-handling (§10)

Add verbatim as FAQ in README:

| Objection | Answer |
|-----------|--------|
| "Doesn't AWS already have Compute Optimizer?" | Yes — Recoup consumes AWS signals. Compute Optimizer identifies opportunities; Recoup investigates surrounding context, establishes intent, packages evidence, chooses a safe recovery workflow, executes under policy, and verifies the outcome. |
| "Isn't this just ProsperOps?" | ProsperOps is a mature autonomous FinOps optimizer, especially for commitments. Recoup is an autonomous cloud-spend investigator and recovery operator focused on cross-signal causal investigation, evidence, risk-tiered HITL remediation, and technical + financial verification. |
| "Why use an agent?" | Because deciding whether spend is truly waste often requires multi-step evidence gathering and contextual reasoning across heterogeneous signals. The agent is valuable in the investigative loop; deterministic policy governs sensitive actions. |
| "Why not automate everything with rules?" | Known, repetitive optimizations should be deterministic. Recoup targets ambiguous cases where the system must determine intent and causality before applying bounded automation. |
| "How do you prevent hallucinated destructive actions?" | The model does not get unrestricted control. Evidence requirements, action allowlists, environment protections, thresholds, and approval rules are deterministic. The execution tool validates identifiers and policy before acting. |
| "How do you prove savings?" | The Recovery Ledger stores the pre-action baseline, estimated recovery, executed change, post-action resource/health checks, and subsequent cost delta. Estimated savings and realized savings remain separate metrics. |

---

## Workstreams

### 7.1 Sep 11 Feature Cutoff

After Sep 11:
- No new features
- No changes to the SLA calculation or policy logic
- Only bug fixes, UI polish, documentation
- Re-read official Devpost rules on Sep 13–14 before final submission

### 7.2 Architecture Diagram

**Update `architecture/architecture.svg`** to show:
- Strands Graph (11 nodes: 3 Strands Agent + 8 Deterministic)
- AgentCore Runtime / Gateway / Policy
- 17 AWS services
- STS role chain: RecoupRuntimeRole → STS AssumeRole → RecoupReadOnlyRole / RecoupRemediationRole
- Recovery Ledger as the closing artifact

### 7.3 README

**`README.md` must include:**

```markdown
# Recoup — AWS Autonomous Cloud Spend Recovery Agent

> "AWS provides the FinOps intelligence; Recoup closes the recovery loop."
> Investigate. Prove. Approve. Recover. Verify.

Recoup is a background Strands Agents graph that detects unintended AWS spend,
investigates surrounding evidence, applies deterministic Cedar policy, involves
humans at real approval boundaries, executes bounded AWS actions, and records
verified recovery — closing the complete loop from anomaly to auditable outcome.

## Quick Start (Judge Demo)
1. Visit [LIVE_URL] or `http://localhost:3000/opportunities` — no AWS credentials required for replay/scan demo paths
2. **`/recovery`** — ledger buckets (Remaining / Pending Approval / Recovered)
3. **`/scan`** — Run Demo Scan → 8+ findings
4. **Start Recovery** → open **`/opportunities/{id}`**
5. Root-Cause Hypothesis / trace on opportunity detail (Strands where enabled)
6. **Approve** on opportunity detail (evidence + risk + rollback on card)
7. Ledger updates after approval

## How It Works (V1.1 Execution Loop)
1. Detect — cost anomaly or waste pattern opens a spend incident
2. Investigate — Strands agent collects cost, utilization, CloudTrail, tag, dependency evidence
3. Correlate — connect spend to underlying resource graph and recent changes
4. Explain — generate root-cause hypothesis; classify spend intent
5. Prove — assemble Recovery Case with confidence and supporting evidence
6. Plan — bounded remediation sequence with preconditions and rollback
7. Policy — Cedar policy gate (deterministic, not LLM) evaluates action risk
8. Approve — HITL approval: evidence + impact + risk + exact action + rollback
9. Remediate — execute only approved/bounded AWS actions via scoped IAM role
10. Verify — validate resource state, application health, financial impact
11. Record — close case in Recovery Ledger (estimated vs realized recovery)

## What Recoup Proves
- Closed-loop: anomaly → investigation → evidence → policy → approve → action → verify → ledger
- The LLM proposes. Cedar policy decides. Humans approve destructive changes.
- 0 unsafe external actions (quality gate); 420 backend tests collected
- Real AWS action (EC2 stop) executed through 5 safety gates
- 20/20 deterministic golden replay — financial math is never LLM-generated
- STS AssumeRole: no long-lived credentials, read-only analysis role, separate remediation role

## Why Not [X]?
- **Why not ProsperOps?** ProsperOps autonomously optimizes cloud economics (commitments, rates, workload scheduling). Recoup investigates *ambiguous* spend incidents: causal evidence, intent inference, staged remediation, HITL approval, technical + financial verification. Different jobs.
- **Why not AWS FinOps Agent?** AWS FinOps Agent investigates anomalies and routes recommendations. Recoup goes further: it closes the loop — Recovery Case with evidence, Cedar policy gate, explicit HITL, bounded execution, post-action health check, and a Recovery Ledger distinguishing estimated from realized savings.
- **Why not Compute Optimizer?** Compute Optimizer identifies opportunities. Recoup investigates surrounding context, establishes intent, runs the proposed action through policy, executes with a bounded role, and verifies both technical health and financial outcome.

## Frequently Asked Questions
[6 Q&A pairs from §10 — see phase-9 plan for exact text]

## Judging Criteria — How Recoup Scores
| Criterion | Evidence |
|-----------|----------|
| Technological Implementation | Strands graph (11 nodes), Bedrock reasoning, real multi-step tool calls, Cedar policy, STS AssumeRole |
| Design | Recovery Dashboard → Pipeline → Evidence → Approval → Verified Ledger: coherent operator experience |
| Potential Impact | $87.82/mo detected across 8 live scenarios; $0.35 real SLA credit recovery from actual AWS billing demonstrated |
| Creativity & Originality | Spend incident investigator, not a cost dashboard. LLMs propose; policy decides; humans approve |
| Presentation | One end-to-end story: anomaly → evidence → approval → live EC2 stop → Recovery Ledger |
```

### 7.4 Video Script (4:40 target + 20s buffer)

**Core narrative:** One excellent end-to-end recovery story (configuration-/deployment-driven spend incident) plus one short secondary scenario (EC2 live action). This is the §18 "safest high-scoring strategy."

**Opening frame must establish:** "This is a spend incident investigator, not a cost optimizer." The approval screen is the demo's "wow moment" (§8): it shows WHY Recoup believes the spend is unintended, the evidence, the risk classification, and the rollback plan.

**Closing frame must be:** the Recovery Ledger entry — "money safely recovered" not "opportunity identified."

| Timestamp | Content | Competitive doc proof point |
|-----------|---------|----------------------------|
| 0:00–0:15 | Title: "Recoup — Investigate. Prove. Approve. Recover. Verify." | Tagline from §13 |
| 0:15–0:40 | Problem: "AWS is wasting money. Finding it, proving it, and fixing it safely takes hours — or just never happens." | Pain statement |
| 0:40–1:00 | Solution: "Recoup is a spend-incident investigator. AWS provides the FinOps intelligence; Recoup closes the recovery loop." | §17.4 positioning sentence |
| 1:00–1:20 | Recovery Dashboard: Ledger (Detected → Approved → Recovered → Pending) + 10-step pipeline + 8 scenario tiles | Closed-loop story |
| 1:20–1:45 | Account Scanner: Role ARN pre-filled (no raw keys) → scan → 6+ findings → "Start Recovery" on EBS/EC2 finding | STS security + breadth |
| 1:45–2:05 | **"Wow moment" #1** — Opportunity detail: Root-Cause Hypothesis card streams in with Strands agent reasoning | §8 + §14.2 — WHY spend is unintended |
| 2:05–2:25 | Agent Trace: 11 nodes, `[Strands]` labels on 3 nodes, Cedar policy card shows `REQUIRE_APPROVAL` | §14.3, 4, 11 |
| 2:25–2:50 | **"Wow moment" #2** — Opportunity detail: full approval card (risk, action description, rollback) → Approve | §8 + §14.5 |
| 2:50–3:05 | Post-Action Verification panel: resource state STOPPED ✓, health checks ✓, savings monitoring started | §14.7 — technical + financial verification |
| 3:05–3:20 | Recovery Ledger updates: Pending → Recovered; dollar amounts update | §14.8 — estimated vs realized separated |
| 3:20–3:35 | (Optional) API-only judge mode: no AWS keys; replay + scorecard curl | Judge-safe experience |
| 3:35–3:55 | EC2 Demo: CloudWatch 0.17% CPU → LIVE AWS ACTION badge → StopInstances confirmed | Real bounded AWS action |
| 3:55–4:15 | `GET /api/quality/scorecard`: 6 gates, `all_gates_pass`, 0 unsafe actions | Engineering rigor |
| 4:15–4:40 | "Why not ProsperOps / AWS FinOps Agent / Compute Optimizer?" (25s total, 3 one-liners) | Competitive clarity |
| 4:40–4:55 | Architecture overlay (17 services, STS chain) + closing: "Every cloud dollar accounted for." | Technical depth |

**Recording rules:**
- Record at 1440p or 1080p
- Warm the replay before filming — never wait on a network call during recording
- Architecture explanation ≤ 35 seconds total
- Use [docs/judge-demo.md](../docs/judge-demo.md) for current UI paths (no Viewer switch in sidebar)
- Show the Recovery Ledger updating after each recovery step (the closing visual)
- Record 3 clean takes; edit the best

### 7.5 Builder.aws Posts

Three posts required for +0.6 bonus. All must have "Agents for Humans" in the title.

**Post 1 — Architecture (publish by Sep 8):**
*"Building Recoup: Agents for Humans — How We Designed a Safe AWS Recovery Workflow with Strands Graph"*
- The 11-node graph: 5 Strands Agent nodes + 6 deterministic
- Why LLMs propose but deterministic policy decides (§5 architectural rule)
- Cedar policy file walkthrough
- Node-level code snippets from `backend/src/recoup/graph/nodes.py`
- Key diagram: `normalize_event → incident_correlation [Strands] → … → risk_policy_gate [Cedar] → HITL → submission_adapter → case_monitor`

**Post 2 — Safety (publish by Sep 10):**
*"Agents for Humans — Making AI Financial Decisions Trustworthy: Cedar Policies, Evidence Redaction, and HITL Approvals in Recoup"*
- 8-pattern evidence sanitizer (`evidence/sanitizer.py`): auth tokens, JWT, API keys, cookies, emails, AWS account IDs, private IPs, AWS secrets
- Autonomy class system (GREEN/YELLOW/RED/BLACK) and tool allowlists
- HITL binding assertions: claim_hash + amount + state_version tamper-proofing
- Cedar policy permit rules and hard-forbid on `terminate_ec2_instance`
- Approval card "wow moment": WHY, evidence, risk, rollback shown before Approve button

**Post 3 — Evaluation (publish by Sep 12):**
*"Agents for Humans — How We Proved Recoup Works: 420 Backend + 279 E2E Tests, Deterministic Math, and Zero Unsafe Actions"*
- 47 YAML scenario categories: sla/, evidence/, exclusions/, policy/, resilience/, sanitization/, anomaly/
- Golden acceptance tests: 20/20 consecutive deterministic runs at 23ms P95
- Adversarial suite: prompt injection, evidence hallucination, binding tamper, BLACK tool enforcement
- Ship gate CI pipeline (`assert_ship_gates.py` + `/api/quality/scorecard` → 6 gates)
- Key insight: financial math is never LLM-generated — Decimal arithmetic, deterministic

### 7.6 Submission Checklist

**Run from a different device/account in incognito:**

```
Repository
[ ] Public GitHub repo accessible without authentication
[ ] MIT license visible from repo root
[ ] README has problem, solution, quick start, architecture diagram
[ ] README has Why-not-ProsperOps, Why-not-AWS-FinOps-Agent, Why-not-Compute-Optimizer
[ ] README has judge FAQ (6 objection/answer pairs)
[ ] README has three-way competitive comparison table
[ ] README has judging rubric callout (5 criteria)
[ ] DISCLOSURE.md present
[ ] First commit dated after Aug 10, 2026

Phase 9 UI Gaps (pre-demo checklist §14)
[ ] Opportunity detail shows Root-Cause Hypothesis (trace.hypothesis_summary)
[ ] Opportunity detail shows Post-Action Verification (trace.case_outcome)
[ ] Opportunity detail shows intent classification badge (Abandoned/Anomalous/etc.)
[ ] Agent Trace labels [Strands] vs [Det.] on each node
[ ] ALL approval cards show: risk tier + action description + rollback note
[ ] Dashboard shows "Investigate. Prove. Approve. Recover. Verify." tagline
[ ] Dashboard shows 10-step V1.1 pipeline

Demo URL (current IA — Sep 11)
[ ] `/opportunities` loads (`/` redirects)
[ ] `/scan` — demo scan + Start Recovery → opportunity
[ ] `/opportunities/[id]` — HITL approve/decline/investigate
[ ] `/recovery` — ledger + chart
[ ] `/replay` — SLA replay (optional deep link)
[ ] `GET /api/quality/scorecard` → `all_gates_pass`
[ ] Demo URL budgeted to remain available through Oct 8, 2026

IAM & Multi-Scenario (Phase 6e + 6f)
[ ] RecoupDemoWorkloadsStack deployed; all 8 scenarios tagged
[ ] Account Scanner shows ≥ 6 findings via RecoupReadOnlyRole
[ ] Role ARN form pre-filled; no raw access key visible
[ ] Analysis role confirmed cannot StopInstances
[ ] Remediation role used for EC2 stop
[ ] Cross-account narrative deliverable verbally (30 seconds)

Video
[ ] Video is ≤ 5:00 (not 5:01)
[ ] Public on YouTube or Vimeo
[ ] Root-Cause Hypothesis card visible in video
[ ] Approval "wow moment" shown (evidence + risk + rollback before Approve)
[ ] Post-Action Verification panel shown
[ ] Recovery Ledger updating shown (closing visual)
[ ] Opportunities-first navigation shown (not legacy Command Center)
[ ] Competitive positioning answered (≤ 25s for each "Why not X?" question)
[ ] No dead air; replay warmed before recording
[ ] Captions enabled

Builder.aws
[ ] Post 1 published with "Agents for Humans" in title (by Sep 8)
[ ] Post 2 published with "Agents for Humans" in title (by Sep 10)
[ ] Post 3 published with "Agents for Humans" in title (by Sep 12)

Devpost
[ ] AWS Builder ID verified
[ ] All fields completed in English
[ ] Video URL entered
[ ] Repository URL entered (public)
[ ] Demo URL entered
[ ] Builder.aws post URLs entered (3)
[ ] Professional Agents track selected
[ ] Submitted before Sep 13 internal deadline

Final verification
[ ] All links from incognito on different device
[ ] Re-read official Devpost rules Sep 13–14
[ ] Repository still public
[ ] Demo URL still works
[ ] Builder.aws posts still published
```

### 7.7 Kill Criteria (Features to Cut if Behind Schedule)

Per the competitive doc §9: "One flagship + one fast secondary scenario is stronger than six shallow examples."

| Feature | Cut if | Safe? |
|---------|--------|-------|
| Intent classification badge (Phase 9 A7) | Sep 10 not met | Yes — minor UI |
| 10-step pipeline visualization | Time risk | Yes — 7-step still tells the story |
| "Investigate Further" as third HITL state | Sep 10 not met | Yes — Approve/Decline sufficient |
| Cost anomaly module | Golden SLA replay not 20/20 | Yes — supporting proof only |
| CloudTrail standalone scenario in video | Adds complexity | Yes — EC2 + SLA proves the story |
| EC2 demo path in video | Demo instability | Yes — SLA replay alone proves agentic workflow |
| 3rd builder.aws post | Sep 11 feature cutoff reached | Yes — 2 posts earns +0.4 |
| Multi-region SLA contracts | Time risk | Yes — API Gateway only is sufficient |
| RecoupDemoWorkloadsStack (6f) in video | Time risk | Yes — show 1–2 findings instead of all 8 |

---

## Definition of Done

| Check | Criteria |
|-------|----------|
| Phase 9 UI gaps | All 12 pre-demo checklist items pass |
| Video | ≤ 5:00; public; "wow moment" approval screen shown; closing on Recovery Ledger |
| Live URL | Works in incognito; replay functional; no AWS credentials |
| Repository | Public; license; README with Why-not sections + FAQ + rubric table |
| Builder.aws | 3 posts with "Agents for Humans" in title |
| Devpost | All fields complete; submitted before Sep 13 |
| Cross-device | All links verified from different device/account |
| Rules re-check | Official rules re-read Sep 13–14 |

---

## Post-Implementation Documentation

- `docs/submission-record.md` — timestamp, URLs, field values, final checklist
- `docs/builder-posts.md` — links to all three builder.aws posts
- `docs/video-script.md` — final video script used in recording

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Video runs over 5:00 | Practice run timed to 4:40; leave 20s buffer |
| Demo URL goes down | Monitor with uptime service; keep cost under demo budget |
| Builder.aws posts not indexed | Publish by Sep 12; confirm visible to public before submission |
| Devpost submission fails | Submit by Sep 13; not Sep 14 last minute |
| Rules changed | Re-read official rules Sep 13–14 before final submission |
| Judge cannot access replay | Test in incognito; no AWS credentials; test from mobile |
| Competitive objection in judging | FAQ in README pre-answers all 6 common objections |
