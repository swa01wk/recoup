# Stale & Obsolete Documents

**Last updated:** Sep 11, 2026  
**Canonical operator story:** [operator-journey.md](operator-journey.md) (J-FULL)  
**Doc index (current):** [README.md](README.md)  
**When to edit vs delete docs:** [code-changes-timing.md](code-changes-timing.md) (same timing as code — prefer banners over deletes before submit)

---

## Where to start (not stale)

Use these for judges, demo, and day-to-day work:

| Document | Purpose |
|----------|---------|
| [operator-journey.md](operator-journey.md) | Primary lifecycle — scan → HITL → ledger |
| [judge-demo.md](judge-demo.md) | ≤5 min walkthrough (J-FULL) |
| [demo-playbook.md](demo-playbook.md) | S5/J-FULL first; S1–S4 optional |
| [code-changes-timing.md](code-changes-timing.md) | Freeze / cleanup timing |
| [stale-code-removal-plan.md](stale-code-removal-plan.md) | Code removal phases |
| [local-dev-and-testing.md](local-dev-and-testing.md) | Ports, Playwright |
| [frontend-guide.md](frontend-guide.md) | Routes & components |
| [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) | Test ↔ journey map (J-FULL at top) |
| [README.md](../README.md) | Repo overview & quick start |

---

## Category A — Misleading unless read with caution

These files exist and are linked from the repo but describe **old IA** (replay-first nav, Decision Inbox, Viewer role, dashboard tiles) or **mixed** old + new content.

| Document | What’s stale | Suggested action |
|----------|----------------|------------------|
| [plans/phase-7-polish-submission-video.md](../plans/phase-7-polish-submission-video.md) | “As-built” block still lists **`/replay`** as step 5 before ledger; body has legacy Command Center / Viewer checklist | Add banner pointing to J-FULL; fix steps 1–6 to match [judge-demo.md](judge-demo.md) **or** mark entire file historical-only |
| [STATUS.md](../STATUS.md) | Phase snapshots (Sep 8) with old test counts; lines like “Replay Engine (`/replay`)” as shipped UI; “Operator/Viewer switcher”, “6 routes” | Keep as **internal history**; do not use for metrics — use [docs/README.md](README.md) key numbers |
| [docs/api-reference.md](api-reference.md) | Replay endpoints documented equally with scan/HITL; no **J-FULL vs optional** grouping | Add section headers: “J-FULL APIs” vs “Optional / legacy demos” |
| [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) | UI table still lists **UI-7 `/replay`** as smoke; notes `journey-ui-browser` legacy | Mark UI-7 optional; point UI smoke to J-FULL + `live-ec2-demo-removed` |
| [docs/frontend-guide.md](frontend-guide.md) | Quick-start curl still starts with replay API | Move replay curls to “Optional depth” appendix |
| [docs/submission-record.md](submission-record.md) | Feature list emphasizes SLA replay + EC2 + S7–S9 as peer to scanners; Phase 9 UI checklist may not match trimmed UI | Reframe “primary demo = J-FULL”; mark optional proofs separately |
| [docs/builder-posts.md](builder-posts.md) | Posts 1–3 center **11-node graph / SLA** more than scanner loop | OK for AWS depth bonus; add one paragraph tying posts to J-FULL ledger story |
| [architecture/architecture.svg](../architecture/architecture.svg) | May still imply replay-centric flow (verify before video) | Visual pass after submit if diagram doesn’t show scanner-first |

---

## Category B — Historical implementation plans (entire `plans/` folder)

**Status:** Completed sprint records — **not** operator runbooks.

| Pattern | Examples | Notes |
|---------|----------|--------|
| Replay as **primary judge path** | [phase-2-verified-replay-sla-engine.md](../plans/phase-2-verified-replay-sla-engine.md) | Says “Verified Replay is the primary judge demo path” |
| Old frontend IA | [phase-4-frontend-command-center.md](../plans/phase-4-frontend-command-center.md), [phase-8-frontend-redesign.md](../plans/phase-8-frontend-redesign.md), [phase-9-competitive-ui-gaps.md](../plans/phase-9-competitive-ui-gaps.md) | Decision Inbox, dashboard tiles, 8-scenario grid |
| Replay-first principles | [plans/README.md](../plans/README.md) | “Replay-first” row in principles table |
| Demo scene scripts | [phase-6b-demo-realism-aws-integration.md](../plans/phase-6b-demo-realism-aws-integration.md), [phase-6c-strands-bedrock-integration.md](../plans/phase-6c-strands-bedrock-integration.md) | Scene 1 = SLA replay |
| AWS cost / scenario math | [aws-requirements.md](../plans/aws-requirements.md) | Still useful for infra; demo **narrative** is stale |

[plans/README.md](../plans/README.md) already warns these are historical. **Do not delete** before hackathon — judges rarely open `plans/`; optional: one-line superseded banner on phase-2 and phase-7 only.

**Missing doc referenced from plans:** `docs/replay-api.md` ( cited in phase-2 ) — **never created**; use [api-reference.md](api-reference.md) replay section instead.

---

## Category C — Root stubs (superseded pointers)

Not wrong — they only redirect. Safe to keep for old links.

| File | Points to |
|------|-----------|
| [DEMO_SCENARIOS.md](../DEMO_SCENARIOS.md) | [demo-playbook.md](demo-playbook.md) |
| [FRONTEND_GUIDE.md](../FRONTEND_GUIDE.md) | [frontend-guide.md](frontend-guide.md) |
| [HACKATHON_DEMO.md](../HACKATHON_DEMO.md) | [judge-demo.md](judge-demo.md) |
| [LIVE_TESTING_GUIDE.md](../LIVE_TESTING_GUIDE.md) | [local-dev-and-testing.md](local-dev-and-testing.md) |
| [LIVE_SCENARIOS_TODO.md](../LIVE_SCENARIOS_TODO.md) | [docs/archive/LIVE_SCENARIOS_TODO.md](archive/LIVE_SCENARIOS_TODO.md) |

---

## Category D — Archive (explicitly not maintained)

| Path | Notes |
|------|--------|
| [docs/archive/](archive/) | [archive/README.md](archive/README.md) — completed checklists |
| [docs/archive/LIVE_SCENARIOS_TODO.md](archive/LIVE_SCENARIOS_TODO.md) | Scenario tracker snapshot |

---

## Category E — Secondary technical reference (still accurate, not the product story)

Keep for engineers and optional demos; **do not** use as the judge walkthrough.

| Document | Role |
|----------|------|
| [replay-system.md](replay-system.md) | SLA verified replay engine (code still present) |
| [sla-calculator.md](sla-calculator.md) | Deterministic credit math |
| [agent-graph.md](agent-graph.md) | 11 nodes — central to replay, optional on promote |
| [agentcore-integration.md](agentcore-integration.md) | Bedrock / Gateway |
| [tool-registry.md](tool-registry.md) | 13 tools |
| [scanner-coverage.md](scanner-coverage.md) | 9 scanners (**J-FULL**) |
| [state-machine.md](state-machine.md) | Opportunity states (shared by scan + replay) |
| [cross-account-onboarding.md](cross-account-onboarding.md) | J3 / S2 |
| [demo-workloads.md](demo-workloads.md) | 8 tagged resources |
| [iam-roles.md](iam-roles.md), [iam-architecture.md](iam-architecture.md) | Security |
| [infrastructure-runbook.md](infrastructure-runbook.md), [deployment.md](deployment.md) | Ops |

---

## Category F — Binary / offline docs (likely stale narrative)

Word docs at repo root — not synced with J-FULL (Sep 11 docs pass):

| File | Risk |
|------|------|
| `Recoup_AWS_Master_Hackathon_Plan.docx` | Pre-IA-trim positioning |
| `Recoup_AWS_Target_Account_Demo_Plan.docx` | May include replay-first scenes |
| `Recoup_vs_ProsperOps_and_AWS_FinOps_Agent_Competitive_Positioning_and_Demo_Strategy (1).docx` | Competitive framing OK; demo steps may be old |

**Suggestion:** Treat as **historical**; do not cite in Devpost without cross-checking [judge-demo.md](judge-demo.md).

---

## Category G — Not documentation (ignore for “stale docs” cleanup)

| Path | Notes |
|------|--------|
| `frontend/playwright-report/**` | Generated HTML/markdown from test runs |
| `frontend/test-results/**` | Failure snapshots — ephemeral |
| `frontend/AGENTS.md`, `frontend/CLAUDE.md` | Next.js agent rules |

---

## Recommended doc hygiene (post-submit)

Priority order — align with [code-changes-timing.md](code-changes-timing.md):

1. **Fix** [plans/phase-7-polish-submission-video.md](../plans/phase-7-polish-submission-video.md) as-built block (remove `/replay` as required step).  
2. **Group** [api-reference.md](api-reference.md) endpoints: J-FULL vs optional.  
3. **Trim** [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) UI-7 / legacy `journey-ui-browser` notes after test cleanup.  
4. **Archive or banner** entire `plans/` with single [plans/SUPERSEDED.md](../plans/SUPERSEDED.md) pointer to [operator-journey.md](operator-journey.md).  
5. **Move** root `.docx` to `docs/archive/offline/` or add README note — optional.

**Do not delete** [replay-system.md](replay-system.md) or SLA docs until replay **code** is removed ([stale-code-removal-plan.md](stale-code-removal-plan.md) Phase 2).

---

## Related

| Doc | Link |
|-----|------|
| Stale **code** | [stale-code-removal-plan.md](stale-code-removal-plan.md) |
| Now vs later | [code-changes-timing.md](code-changes-timing.md) |
