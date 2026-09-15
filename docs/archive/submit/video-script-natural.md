# Video Script — Conversational, segment by segment (≤ 5:00)

Read **one segment at a time**. Do what’s on **Screen** first, then say the **Say** block out loud like you’re walking a teammate through it.

Shots & URLs: [video-script.md](video-script.md)

---

## Segment A — Why Recoup exists (~35 sec)

**Screen:** Empty **Opportunities** (“No recoverable opportunities yet”). Then click **Go to Account Scanner** or use the sidebar.

**Say:**

Hey — I’m going to show you **Recoup**. We built it for the **AWS Agents for Humans** hackathon, with **Strands on Bedrock**, in the **Professional Agents** track.

So — the problem. You already get waste findings from scanners and dashboards, right? Idle EC2, stray volumes… but it rarely turns into actual **recovery** with a paper trail.

This is for **FinOps and platform teams** — people who own the AWS bill and have to explain decisions to finance or security.

Why bother? Because that waste **renews every month**, and “someone should fix that” isn’t an audit story. Recoup scans read-only, builds a real case, runs policy, and makes a human approve a **specific dollar amount** — then it lands in the **Recovery Ledger** and we ping **SNS**.

Nothing’s loaded yet in this session. I’ll hit **Demo Scan** on the public demo — you don’t need AWS keys.

---

## Segment B — Scan (~30 sec)

**Screen:** **Account Scanner** — glance at the read-only / STS panel → check **consent** → **Demo Scan** → wait for **Opportunities** table.

**Say:**

Here’s the scanner. It’s **read-only** — STS, temporary credentials, no sneaky writes. You opt in with the checkbox.

**Demo Scan** fires **nine scanners** at once on our hosted account.

And we’re back on Opportunities — about **a hundred eighty bucks a month** showing up across EC2, RDS, EBS, and the rest. Everything’s still **Detected**; we haven’t committed to anything.

---

## Segment C — Open the EC2 case (~75 sec)

**Screen:** On the **EC2 · idle · ~$73/mo** row, click **Start Recovery**. Slow scroll: step bar → metric cards → **Why Recoup believes this** → **Evidence graph** → stop on **Approval Required**.

**Say:**

I’ll start with the big one — **idle EC2**, **seventy-three a month**.

**Start Recovery** runs the assessment pipeline. See the lifecycle? We’re on **step eight of eleven** — **Awaiting approval**. Detect through policy already happened; now it needs a person.

You’ve got **eight evidence signals**, **ninety-two percent** confidence, **medium** risk, rollback’s there. CPU’s been flat — about **one percent over seven days** — that’s why we call it idle.

The **evidence graph** connects the dots: scanner facts → **stop this instance** → **seventy-three a month** back.

Down here — **Approval Required**. Action, impact, risk, rollback, policy — all in one place before you click green. And that approve is tied to a **claim hash**; mess with the amount and you get a **409** — we test that.

---

## Segment D — Approve, investigate, decline (~80 sec)

**Screen:** **Approve $73.00/mo Recovery** → hold **Recovery Verified** → back to list, **Start Recovery** on **RDS** → **Investigate further** → **EBS** (or another row) → **Decline**.

**Say:**

Okay — **approve** this one.

Recoup runs the allowed stop, checks the resource, records savings, sends **SNS**. Person first, automation second.

This **Recovery Verified** screen is what you want to see — **seventy-three recovered**, action completed, checks green. Not a silent cron job.

Two more, same UI. On **RDS**, **Investigate further** — stays **pending**, no recovery blast yet. On **EBS**, **Decline** — doesn’t count as recovered, no SNS.

Three buttons, one queue — approve, dig deeper, or pass.

---

## Segment E — Ledger (~30 sec)

**Screen:** **Recovery Ledger** (sidebar or **View Recovery Ledger**).

**Say:**

**Recovery Ledger** — **Potential**, **Remaining**, **Pending**, **Recovered**.

After that approve, **seventy-three** sits in **Recovered**; the rest is still **Remaining** until someone acts. Audit history down here — timestamp, service, status — so finance can follow it.

That’s the loop most tools never finish.

---

## Segment F — Proof (~40 sec)

**Screen:** Terminal on **localhost**: `curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'` → then **`architecture/architecture.svg`**.

**Say:**

Quick sanity check — **six ship gates** in CI and local: replay through the **Strands** graph, money math, evidence, safety, traces, no unsafe actions. **419** backend tests, **127** Playwright — including this journey.

Live demo keeps promote **deterministic** so it’s fast; the full **eleven-node Strands** graph and **Cedar** policy live in the repo when you want the deep agent path.

---

## Segment G — Sign off (~10 sec)

**Screen:** Demo URL + GitHub (end slide or browser).

**Say:**

Links below — **Demo Scan** on App Runner, MIT repo on GitHub. That’s **Recoup**. Thanks.

---

## Tips while you read

- **Numbers:** Say what’s on your screen if it’s not exactly $180 / $73.
- **Pace:** These segments are ~**4–4½ min** of talk; use the extra time to scroll and let the UI breathe.
- **One take:** Reset demo → A through G in order; cut mistakes in edit.
