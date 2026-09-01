# Phase 7 — Polish, Submission & Video

**Timeline:** Day 12–14 (Target: Sep 13 internal deadline; Sep 14 official deadline)  
**Status:** `[ ] Not Started`  
**Depends on:** All previous phases complete

---

## Objective

Final polish, competition submission preparation, video production, and three builder.aws posts. Everything in this phase exists to maximize the judge score. A smaller, flawless submission beats an impressive but brittle one.

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

## Workstreams

### 7.1 Sep 11 Feature Cutoff

After Sep 11:
- No new features
- No changes to the SLA calculation or policy logic
- Only bug fixes, UI polish, documentation
- Re-read official Devpost rules on Sep 13–14 before final submission

### 7.2 Architecture Diagram

**Update `architecture/architecture.png`** to show deployed reality:

```
┌─────────────────────────────────────────────────────────────────┐
│                    RECOUP ARCHITECTURE                          │
├────────────┬────────────────────────┬───────────────────────────┤
│  FRONTEND  │       API LAYER        │     AGENT RUNTIME         │
│            │                        │                           │
│  Next.js   │    FastAPI             │  AgentCore Runtime        │
│  Command   │    /api/*              │  ┌─────────────────────┐  │
│  Center    │    Auth + Session      │  │   Strands Graph     │  │
│            │    SSE Streaming       │  │                     │  │
│  Evidence  │                        │  │  normalize_event    │  │
│  Room      │                        │  │  incident_correl.   │  │
│            │                        │  │  sla_resolver       │  │
│  Decision  │                        │  │  calculator         │  │
│  Inbox     │                        │  │  evidence_collect.  │  │
│            │                        │  │  sanitizer          │  │
│  Trace     │                        │  │  eligibility        │  │
│  View      │                        │  │  risk_gate          │  │
│            │                        │  │  claim_generator    │  │
│  Quality   │                        │  │  submission_adapter │  │
│            │                        │  │  case_monitor       │  │
└────────────┴────────────────────────┴─┬─────────────────────┘  │
                                        │                          │
         ┌──────────────────────────────┴──────────────────────┐  │
         │              AWS SERVICES                            │  │
         │                                                      │  │
         │  AgentCore    AgentCore    AgentCore                 │  │
         │  Gateway      Policy       Observability             │  │
         │  (MCP tools)  (Cedar)      (CloudWatch)              │  │
         │                                                      │  │
         │  EventBridge  SQS          DynamoDB    S3            │  │
         │  (Health)     (Queue)      (State)     (Evidence)    │  │
         │                                                      │  │
         │  CloudWatch   Cost         CloudTrail  Bedrock       │  │
         │  (Metrics)    Explorer     (Audit)     (Model)       │  │
         │                                                      │  │
         │  EC2          AWS Support                            │  │
         │  (Demo)       (Adapter)                              │  │
         └──────────────────────────────────────────────────────┘
```

### 7.3 README

**`README.md` must include:**

```markdown
# Recoup — AWS Autonomous Cloud Spend Recovery Agent

> Recoup is a background Strands agent that finds recoverable or preventable AWS spend, 
> investigates the cause, assembles the evidence, and safely handles the operational 
> work — involving humans only when a real approval or judgment is required.

## Quick Start (Judge Demo)
1. Visit [https://recoup.example.com] — no AWS credentials required
2. Click "▶ Run Canonical Replay" 
3. Watch the agent investigate a synthetic API Gateway SLA breach
4. Approve the $1,840 claim in the Decision Inbox
5. View the complete agent trace with policy decisions and evidence

## What Recoup Proves
- One real, reversible AWS action (EC2 stop with governed approval)
- Complex SLA recovery workflow via Verified Replay
- 0 unsafe external actions across 50+ test scenarios

## Architecture
[architecture diagram]

## Built With
- Amazon Bedrock Strands Agents (graph orchestration)
- Amazon Bedrock AgentCore (Runtime, Gateway, Policy, Observability)
- Amazon Bedrock (model reasoning)
- AWS EventBridge, SQS, DynamoDB, S3, CloudWatch, Cost Explorer
- Next.js + FastAPI

## Repository Structure
- `backend/` — FastAPI API + Strands graph + deterministic engines
- `frontend/` — Next.js Command Center UI
- `infra/` — CDK infrastructure-as-code
- `sla_catalog/` — Human-verified SLA contract catalog
- `eval_fixtures/` — Immutable replay seed artifacts
- `plans/` — Implementation phase plans

## Evaluation Results
[Link to /quality view screenshot or live URL]

## License
MIT
```

### 7.4 Video Script (4:40 target + 20s buffer)

**Timing breakdown:**

| Timestamp | Content | Proof point |
|-----------|---------|-------------|
| 0:00–0:15 | Title card: "Recoup — Every cloud dollar accounted for" | Memorable hook |
| 0:15–0:40 | Problem: Show real scenario. "Your API Gateway was down for 30 minutes. AWS owes you credit. Finding it, proving it, and claiming it takes hours." | Audience pain |
| 0:40–1:00 | Solution in one sentence: "Recoup is a background agent that does that work — investigating, assembling evidence, and asking you only for the decisions that require a human." | Clear pitch |
| 1:00–1:20 | Architecture (35 seconds max): Strands Graph + AgentCore Runtime/Gateway/Policy | Technical depth |
| 1:20–1:40 | Live EC2 demo: Show Command Center → OPTIMIZATION opportunity → LIVE badge → approve → instance stops → trace confirms | Real execution |
| 1:40–2:10 | Trigger canonical replay: watch nodes execute in real time via SSE | Agentic workflow |
| 2:10–2:40 | Calculation view: "99.9306% → 10% tier. $18,400 × 10% = $1,840. Every step in the formula is shown." | Deterministic math |
| 2:40–3:10 | Evidence Room: required fields, sanitized logs, redaction count, hashes | Completeness + safety |
| 3:10–3:35 | Decision Inbox: "Creating an external financial case is a human boundary. Approving triggers Simulate Submission — REPLAY case id only." | Agents for Humans |
| 3:35–4:00 | Agent Trace: Strands nodes, Gateway calls, policy decisions, durations | Technical depth |
| 4:00–4:20 | Quality view: "50 scenarios. Financial math 100% deterministic. 0 unsafe actions." | Engineering rigor |
| 4:20–4:43 | Closing: same architecture supports anomaly investigation and optimization | Platform credibility |
| 4:43–4:55 | End card: "Recoup: every cloud dollar accounted for." | Memorable finish |

**Recording rules:**
- Record at 1440p or 1080p
- No terminal scrolling unless it proves one technical point
- Warm replay before filming; never wait on model during recording
- Architecture explanation ≤ 35 seconds
- Use captions; keep text away from YouTube controls
- Record 3 clean takes; edit the best
- Show mode badges clearly: LIVE AWS ACTION for EC2 demo, VERIFIED REPLAY for SLA

### 7.5 Builder.aws Posts

Three posts required for +0.6 bonus (0.2 each). Use "Agents for Humans" in each title.

**Post 1 — Architecture (publish by Sep 8):**  
*"Building Recoup: Agents for Humans — How We Designed a Safe AWS Recovery Workflow with Strands Graph"*
- Strands Graph design decisions
- Why we chose deterministic nodes for financial logic
- Agent/deterministic boundary diagram
- Code snippets from node definitions

**Post 2 — Safety (publish by Sep 10):**  
*"Agents for Humans — Making AI Financial Decisions Trustworthy: Cedar Policies, Evidence Redaction, and HITL Approvals in Recoup"*
- AgentCore Policy design
- Evidence sanitization pipeline
- Autonomy class system
- Example Cedar policy

**Post 3 — Evaluation (publish by Sep 12):**  
*"Agents for Humans — How We Proved Recoup Works: 50 Scenarios, Deterministic Math, and Zero Unsafe Actions"*
- Evaluation architecture
- Golden acceptance tests
- Ship gate CI pipeline
- Adversarial testing lessons

### 7.6 Submission Checklist

**Final check — run from a different device/account:**

```
Repository
[ ] Public GitHub repo accessible without authentication
[ ] MIT or Apache-2.0 license visible from repo root page
[ ] README present with problem, solution, quick start, architecture diagram
[ ] architecture/architecture.png matches deployed reality
[ ] DISCLOSURE.md present (fresh project disclosure)
[ ] All source, assets, and instructions included
[ ] First commit dated after Aug 10, 2026

Evaluation & Safety
[ ] 20/20 consecutive golden replay passes in CI
[ ] 0 unsafe external actions across full test suite
[ ] /quality page shows current scorecard
[ ] All ship gates green in last CI run

Demo
[ ] Live URL accessible in incognito (no AWS credentials)
[ ] Replay can be triggered and completes < 60s
[ ] Decision Inbox shows approval card correctly
[ ] EC2 demo path works (or reset script ready)
[ ] VERIFIED REPLAY badge visible on SLA opportunity
[ ] LIVE AWS ACTION badge visible on EC2 opportunity
[ ] Demo URL budgeted to remain available through Oct 8, 2026

Video
[ ] Video is ≤ 5:00 (not 5:01)
[ ] Public on YouTube or Vimeo
[ ] Covers: problem, audience, why it matters, working end-to-end demo
[ ] No dead air; replay warmed before recording
[ ] Captions enabled

Builder.aws
[ ] Post 1 published with "Agents for Humans" in title
[ ] Post 2 published with "Agents for Humans" in title
[ ] Post 3 published with "Agents for Humans" in title

Devpost
[ ] AWS Builder ID verified and accessible
[ ] All Devpost fields completed in English
[ ] Video URL entered
[ ] Repository URL entered (public)
[ ] Demo URL entered
[ ] Builder.aws post URLs entered (3)
[ ] Professional Agents track selected
[ ] Submitted before Sep 13 internal deadline (not Sep 14)

Final verification
[ ] Test all links from incognito on a different device
[ ] Re-read official Devpost rules on Sep 13–14 for any changes
[ ] Check that repository is still public
[ ] Confirm demo URL still works
[ ] Confirm builder.aws posts are still published
```

### 7.7 Kill Criteria (Features to Cut if Behind Schedule)

Per the plan: "A smaller flawless agent will score better than an impressive but brittle platform."

| Feature | Cut if | Safe to cut? |
|---------|--------|-------------|
| Cost anomaly module | Golden SLA replay not 20/20 | Yes — supporting proof only |
| Cost Optimization Hub integration | Sep 11 feature cutoff not met | Yes — enhances but not core |
| Case Monitor (live status) | Demo route works | Yes — replace with static SUBMITTED state |
| Multi-region SLA contracts | Time risk | Yes — API Gateway only is sufficient |
| CloudTrail in EC2 demo | EC2 path adds complexity | Yes — simplify to just CW utilization |
| EC2 demo path entirely | Replay alone proves agentic workflow | Acceptable if safety concern arises |

---

## Definition of Done

| Check | Criteria |
|-------|----------|
| Video | ≤ 5:00; public; covers all required content |
| Live URL | Works in incognito; replay functional; no AWS credentials |
| Repository | Public; license visible; README + architecture; disclosure |
| Builder.aws | 3 posts published with "Agents for Humans" in title |
| Devpost | All fields complete; submitted before Sep 13 |
| Cross-device | All links verified from different device/account |
| Rules re-check | Official rules re-read on Sep 13–14 |

---

## Post-Implementation Documentation

> Created in `plans/docs/` after phase completion.

- `docs/submission-record.md` — Record of submission: timestamp, URLs, field values, final checklist
- `docs/builder-posts.md` — Links to all three builder.aws posts
- `docs/video-script.md` — Final video script used in recording

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Video runs over 5:00 | Practice run timed to 4:40; leave 20s buffer |
| Demo URL goes down | Monitor with uptime service; keep cost under free tier; have backup screenshots |
| Builder.aws posts not indexed | Publish by Sep 12; confirm visible to public before submission |
| Devpost submission fails | Submit by Sep 13; not Sep 14 last minute |
| Rules changed | Re-read official rules page on Sep 13–14 before final submission |
| Judge cannot access replay | Test in incognito; no AWS credentials; test from mobile |
