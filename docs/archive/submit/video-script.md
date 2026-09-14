# Video Script — Recoup (≤ 5:00)

**Hackathon:** AWS Agents for Humans · **Track:** Professional Agents  
**Target runtime:** **4:50** (10s buffer under 5:00)  
**Format:** Screen recording + voiceover (no on-camera required)  
**Last updated:** Sep 15, 2026 (aligned to production screenshot walkthrough)

**Devpost pitch must cover:** (1) problem · (2) audience · (3) why it matters — **Segment A**; working project — **Segments B–E** (your UI capture).

**Canonical flow:** [operator-journey.md](../../operator-journey.md) · [judge-demo.md](../../judge-demo.md)

---

## Production demo (record this)

| Tab | URL |
|-----|-----|
| Scanner | https://pdkeexzwxr.us-east-1.awsapprunner.com/scan |
| Opportunities | https://pdkeexzwxr.us-east-1.awsapprunner.com/opportunities |
| Recovery Ledger | https://pdkeexzwxr.us-east-1.awsapprunner.com/recovery |

**Before record:** Sidebar → **Reset Demo Data** → confirm **Opportunities** empty (*"No recoverable opportunities yet"*). Warm one **Demo Scan** off-camera if the spinner is slow.

**Numbers from your Sep 15 capture (say what’s on screen — totals can shift slightly):**

| UI element | Example value |
|------------|----------------|
| Summary bar (post-scan) | **Potential savings ~$180.33/mo** · Remaining matches until you act |
| Hero row | **EC2 · Idle EC2 resource · $73.00/mo · High · DETECTED** |
| Other services in table | RDS stopped instance, EBS unattached, S3 lifecycle, Lambda oversized, etc. |
| EC2 case (detail) | **$73.00/mo recoverable** · **$876.00/yr projected** · **Step 8 of 11 — Awaiting Approval** |
| Confidence cards | **8 signals** · Discovery **92%** · Action **80%** · Risk **Medium (45)** · Rollback **Available** |
| After EC2 approve | **Recovery Verified · $73.00/mo recovered** · action **Stopped EC2 instance** |
| Ledger (one approve) | Potential **$180.33** · Remaining **$107.33** · Pending **$0** · Recovered **$73.00** |

**J-FULL triage (required for rubric):** After the **EC2 approve** hero beat, promote **two other services** (e.g. **RDS** + **EBS**) and show **Investigate further** and **Decline** so Pending / Recovered / Remaining tell a story. Your screenshots cover the **EC2 approve path** end-to-end; record the other two actions in the same session (quick cuts OK).

---

## Screenshot-aligned shot list (editor order)

Use this as the **picture lock**; VO below matches these frames.

| # | Screen | What to show / click |
|---|--------|----------------------|
| 1 | **Opportunities (empty)** | *"No recoverable opportunities yet"* → click **Go to Account Scanner** (or sidebar **Account Scanner**) |
| 2 | **Account Scanner** | Read-only checklist (STS, temporary creds, DenyAllWrites). Check **consent** → **Demo Scan** (not “Scan AWS Account” unless you’re showing real role connect) |
| 3 | **Opportunities (populated)** | Summary: **Potential savings** banner. Table: **EC2 $73**, multiple services, all **DETECTED**, blue **Start Recovery** |
| 4 | **EC2 opportunity detail (top)** | Title **EC2 Opportunity · Awaiting Approval**. Green **$73.00/mo recoverable**. **11-step** pipeline — highlight **Step 8 of 11 — Awaiting Approval** (Detect → … → Policy ✓ → **Approve** highlighted) |
| 5 | **EC2 detail (middle)** | Six cards: **Evidence 8 signals**, **Impact $73/mo**, **Risk Medium**, **Discovery 92%**, **Action 80%**, **Rollback Available**. Scroll **Why Recoup believes this** — *1.2% CPU over 7 days*, idle instance |
| 6 | **EC2 detail (bottom)** | **Evidence Graph** → **Stop EC2 instance** → **$73.00/mo recovery**. Right rail: **Recommended action**, **Safety checks**, **Recovery plan** (8 steps) |
| 7 | **Approval Required card** | **Action: Stop EC2 instance** · **Impact: $73.00/mo** · **Risk: Medium** · **Policy: Default human approval…** Buttons: **Investigate Further** · **Decline** · **Approve $73.00/mo Recovery** |
| 8 | **Recovery Verified** | Green check · **$73.00/mo recovered** · **Stopped EC2 instance** · three checks (AWS action, state verified, savings in ledger) → **View Recovery Ledger** |
| 9 | **Recovery Ledger** | Four buckets + **Audit history** row (*Recovery verified · EC2 · $73.00/mo · RECOVERED*) |
| 10 | *(optional cuts)* | **RDS** → Investigate · **EBS** → Decline → refresh **Opportunities** summary / **Ledger** |
| 11 | **Trust close** | Local scorecard terminal + `architecture/architecture.svg` |
| 12 | **End** | Demo + GitHub URLs |

---

## Segment map

| Time | Segment | On screen (your flow) |
|------|---------|------------------------|
| 0:00–0:45 | **A — Pitch** | Shot 1 empty **Opportunities** OR title card → empty hub |
| 0:45–1:20 | **B — Detect** | Shots 2–3 **Account Scanner** → **Demo Scan** → table |
| 1:20–2:15 | **C — Prove & assess** | Shots 4–7 **Start Recovery** on EC2 → scroll to **Approval Required** |
| 2:15–3:30 | **D — Triage** | Shot 7 **Approve $73.00/mo** → Shot 8 **Recovery Verified** → shots 10 RDS/EBS |
| 3:30–4:05 | **E — Ledger** | Shot 9 (+ summary bar on **Opportunities** if Pending ≠ $0) |
| 4:05–4:50 | **F — Trust & stack** | Scorecard + architecture |
| 4:50–5:00 | **G — Close** | Links |

---

## Segment A — Pitch (0:00–0:45)

**On screen:** Shot **1** — **Opportunities** empty state (*"Scan your AWS account to discover idle resources…"*).

**VO (~128 words):**

> I'm demoing **Recoup** for the AWS Agents for Humans hackathon — **Strands Agents on Amazon Bedrock**, Professional Agents track.
>
> **(1) The problem:** Teams already see waste in scanners and dashboards, but findings rarely become **governed recovery**. Dollars stay on the bill; nobody has a **bound record** of who approved what.
>
> **(2) Who it's for:** **FinOps leads, cloud platform engineers, and engineering managers** accountable for AWS spend — people who need approval trails finance and security will accept.
>
> **(3) Why it matters:** Unclosed waste repeats every month. Recoup runs **real read-only scans**, builds **evidence-backed cases**, enforces **policy before action**, and requires **human approval** tied to **claim hash, amount, and state version** — then **Recovery Ledger** and **SNS** on approve.
>
> Right now there are **no opportunities** until we scan — I'll use **Demo Scan** on our public App Runner site. No AWS keys required.

**Transition:** Click **Go to Account Scanner**.

---

## Segment B — Detect (0:45–1:20)

**On screen:** Shots **2–3**.

1. **Account Scanner** — pan the green **Read-only access** panel (STS AssumeRole, temporary credentials, DenyAllWrites, *no resource changes without approval*).
2. Check **consent** → **Demo Scan**.
3. Land on **Opportunities** — hold on summary **Potential savings ~$180/mo** and the table (EC2, RDS, EBS, S3, Lambda…).

**VO (~88 words):**

> **Account Scanner** uses **STS AssumeRole** with **read-only** permissions — no writes without explicit approval.
>
> **Demo Scan** hits our hosted demo account with **nine parallel scanners** across EC2, EBS, RDS, S3, Lambda, and more.
>
> Findings land in **Opportunities** — here about **a hundred eighty dollars per month** in **potential savings**, ranked by service and risk. Every row is still **DETECTED** until an operator starts recovery.

---

## Segment C — Prove & assess (1:20–2:15)

**On screen:** Shots **4–7**. On **EC2 · Idle EC2 resource · $73.00/mo**, click **Start Recovery**.

Scroll in one continuous take (or two tight cuts):

1. **Step 8 of 11 — Awaiting Approval** on the lifecycle bar (mention steps 1–7 already ran: detect, investigate, correlate, explain, prove, plan, policy).
2. **Why Recoup believes this** — idle **t2.micro**, **~1.2% CPU over seven days**, high severity.
3. **Evidence Graph** linking scanner nodes to **Stop EC2 instance** and **$73.00/mo recovery**.
4. Pause on **Approval Required** — read the card fields on screen.

**VO (~105 words):**

> I'll **Start Recovery** on the top **EC2 idle instance** — **seventy-three dollars a month**.
>
> That promotes the case through our **eleven-step lifecycle**. We're at **step eight: awaiting approval** — detect through **policy** already passed; the operator owns the decision.
>
> **Eight evidence signals**, **ninety-two percent discovery confidence**, **medium risk** with **rollback available**. The **evidence graph** ties scanner facts to a recommended **stop EC2 instance** action — not a black-box score.
>
> **Approval Required** summarizes **action, impact, risk, rollback, and policy** before any button turns green. Claim hash and state version bind this **exact seventy-three dollar** approval — tamper attempts return **409** in our tests.

---

## Segment D — Human triage (2:15–3:30)

**On screen:** Shot **7 → 8**, then **10** (two quick triage actions).

### Hero: EC2 approve (shots 7–8)

**Click:** **Approve $73.00/mo Recovery**

**Hold on Recovery Verified:**

- **$73.00/mo recovered** / **$876.00/year**
- **Action completed: Stopped EC2 instance**
- Checks: **AWS action executed** · **Resource state verified** · **Savings recorded in Recovery Ledger**

**VO (~75 words):**

> I **approve** the bound **seventy-three dollar** recovery. Recoup runs the **allow-listed action**, **verifies post-action state**, records savings, and notifies via **SNS** — human authorization first, automation second.
>
> This is the **Recovery Verified** screen judges should see: explicit **action completed**, not a silent background job.

### Complete J-FULL (shots 10 — ~40s each, can be faster)

| Row | Button | Say |
|-----|--------|-----|
| **RDS** (or next service) | **Investigate further** | Stays **pending** — no recovery notification until follow-up |
| **EBS** (or third service) | **Decline** | Excluded from **Recovered** totals |

**VO (~85 words):**

> Same page for other findings: **Investigate further** keeps the case in **pending approval** without closing it. **Decline** rejects the bound action — **no SNS**, not counted as recovered.
>
> Approve, investigate, and decline all live on **opportunity detail** — one operator queue, not a separate inbox.

**If short on time:** Keep EC2 approve on camera; do RDS/EBS with voiceover only and a one-second button flash each.

---

## Segment E — Recovery Ledger (3:30–4:05)

**On screen:** Shot **9** — click **View Recovery Ledger** or sidebar **Recovery Ledger**.

Point to:

- **Potential savings** (original scan total)
- **Remaining** (not yet actioned)
- **Pending approval** (after *Investigate* — may be **$0** if you only filmed EC2 approve)
- **Recovered** (**$73.00/mo** after EC2 approve)
- **Audit history** — *Recovery verified · EC2 · RECOVERED*

**VO (~72 words):**

> **Recovery Ledger** is the immutable audit view: **potential** from the scan, **remaining** still on the table, **pending** awaiting humans, **recovered** after verified approve.
>
> After one approval, **seventy-three dollars** moves to **Recovered**; the rest stays in **remaining** until operators act. Every event is **timestamped** with service and status — the loop scanners usually don't close.

**Director note:** If you recorded all three triage outcomes, narrate how **Pending** and **Recovered** shifted; match **your** summary bar numbers, not a script default.

---

## Segment F — Trust & stack (4:05–4:50)

**On screen:** Terminal (**localhost only**):

```bash
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
```

Then **`architecture/architecture.svg`** — Strands agent nodes vs deterministic / policy nodes.

**VO (~100 words):**

> Trust is testable: **six ship gates** — golden **SLA replay through the full Strands graph**, financial correctness, evidence recall, autonomy classes, trace completeness, **zero unsafe external actions**. **419** backend tests, **127** Playwright tests including this journey.
>
> Production demo prioritizes **deterministic assessment and policy on promote** for latency; the **eleven-node Strands graph on Bedrock Nova Pro** and Cedar rules live in repo and CI. **AgentCore-oriented CDK**, per-guest **demo sessions**, masked account IDs.

---

## Segment G — Close (4:50–5:00)

**On screen:** Demo + repo URLs.

**VO (~32 words):**

> Try it: **Demo Scan** at the link below, MIT repo in the description. **Recoup** — detect, prove, approve, recover. Thanks for watching.

---

## VO-only block (teleprompter)

Paste into your teleprompter app; perform actions during the `[ACTION]` lines.

```
[ACTION: Empty Opportunities → Account Scanner]

I'm demoing Recoup for AWS Agents for Humans — Strands on Bedrock, Professional Agents.

One — the problem: scanners find waste, but teams rarely close governed recovery.
Two — who it's for: FinOps, platform engineers, and engineering leaders on AWS spend.
Three — why it matters: recurring dollars and audit risk. Recoup scans read-only, builds evidence-backed cases, policy-gates actions, and binds human approval to claim hash, amount, and state version — then Recovery Ledger and SNS on approve.

[ACTION: Consent → Demo Scan → Opportunities table ~$180/mo]

Account Scanner uses STS read-only access. Demo Scan runs nine parallel scanners. Findings appear here — about one hundred eighty dollars per month potential, all DETECTED.

[ACTION: Start Recovery on EC2 $73 → scroll Step 8/11, evidence graph, Approval Required]

Start Recovery on the idle EC2 case — seventy-three dollars a month. Eleven-step lifecycle — we're at step eight, awaiting approval. Eight signals, ninety-two percent discovery confidence, evidence graph to stop instance. Approval Required shows action, impact, risk, rollback, policy.

[ACTION: Approve $73.00/mo → Recovery Verified]

Approve — allow-listed stop, verify state, record savings, SNS. Recovery Verified: seventy-three dollars recovered, action completed.

[ACTION: RDS Investigate · EBS Decline — if time]

Investigate further — pending, no close. Decline — not recovered, no SNS.

[ACTION: Recovery Ledger audit row]

Ledger: potential, remaining, pending, recovered — audit history for every decision.

[ACTION: Local scorecard true + architecture.svg]

Six ship gates, four nineteen plus one twenty-seven tests, Strands graph in CI, Cedar in repo.

Demo and GitHub in the description. Thanks.
```

---

## Pre-recording setup

```bash
./scripts/prod_journey_hitl_smoke.sh
curl -X POST http://localhost:8000/api/test/reset   # local only
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
```

**Recording checklist:** [video-recording-checklist.md](video-recording-checklist.md)

**Speaking pace:** ~140–150 wpm · total VO ≈ **720 words** → ~**4:50**.
