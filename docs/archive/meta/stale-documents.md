# Stale & Obsolete Documents

**Last updated:** Sep 13, 2026  
**Canonical operator story:** [operator-journey.md](operator-journey.md) (J-FULL)  
**Doc index (current):** [README.md](README.md)  
**When to edit vs delete docs:** [code-changes-timing.md](code-changes-timing.md) (same timing as code — prefer banners over deletes before submit)

---

## Plan execution status (documentation track)

| Item | Status |
|------|--------|
| Canonical J-FULL docs (operator-journey, judge-demo, playbook, video-script) | ✅ Updated Sep 11 |
| `api-reference.md` J-FULL table + removed routes + archived replay section | ✅ |
| `demo-playbook.md` S5 primary; S1/S3/S7–S9 marked removed | ✅ |
| `replay-system.md`, `judge-demo.md`, `USER_JOURNEY_CHECKLIST.md` | ✅ Post-cleanup counts & removed journeys |
| `code-changes-timing.md` execution + matrix | ✅ Phases 0–5 done |
| `STATUS.md`, `submission-record.md`, test count lines in README | ✅ Use **123** Playwright (15 specs) · **407** pytest (Sep 13) |
| Production App Runner URLs (API `vxndciwupy…`, UI `nvqjc7nnif…`) | ✅ Synced across root README, judge/operator guides, scripts, [production-hosting.md](../ops/production-hosting.md) (Sep 13) |
| Recovery pipeline + detail UI docs | ✅ `backend-code-architecture`, `frontend-code-architecture`, `agent-code-architecture`, `operator-journey` (Sep 11–13) |
| `plans/SUPERSEDED.md` pointer | ✅ |
| Historical `plans/phase-*` bodies | ☐ Intentionally unchanged (Category B) |
| **Code track (Phase 6)** | ☐ AgentCore/CDK deferred |

---

## Divergence matrix (documentation vs J-FULL)

**Reference:** [operator-journey.md](operator-journey.md) + codebase verification (same rows as [code-changes-timing.md](code-changes-timing.md) / [stale-code-removal-plan.md](stale-code-removal-plan.md)).  
**Legend:** **Δ** = doc(s) mislead or lag reference · **OK** = aligned · **Doc action** = how to fix in markdown (not code).

| Area | J-FULL reference | What docs say / imply | Δ | Doc action |
|------|------------------|------------------------|---|------------|
| Primary operator story | Scan → 3 services → 3 HITL paths → ledger + SNS | **Aligned:** `operator-journey.md`, `judge-demo.md`, `demo-playbook.md` (S5 first), `README.md` | OK | Canonical — maintain here |
| Recovery pipeline on promote | `recovery/` + detail UI (evidence graph, safety, plan) | **Aligned:** `operator-journey.md`, `backend-code-architecture.md`, `frontend-code-architecture.md`, `agent-code-architecture.md` | OK | — |
| Production URLs | API `vxndciwupy…`, UI `nvqjc7nnif…` | **Aligned:** [production-hosting.md](../ops/production-hosting.md), root README, judge/operator guides, smoke scripts (Sep 13) | OK | Re-sync after App Runner recreate |
| Sidebar / nav | 3 links only | **Aligned:** `frontend-guide.md`, `docs/README.md` key numbers | OK | — |
| HITL / Decision Inbox | Detail page only; no `/approvals` inbox | **Aligned:** `judge-demo.md`, `frontend-guide.md` | OK | — |
| SLA replay as main demo | Related journey J4; optional | **Mixed:** `replay-system.md`, `sla-calculator.md` (correct as **technical**); `plans/phase-2` (“primary judge path”) | Δ | Category B — historical banner; do not use for pitch |
| `/replay` in judge steps | Optional appendix (API only) | **Aligned:** `phase-7` as-built, `judge-demo.md`, `frontend-guide.md` (page removed) | OK | — |
| Video script | J-FULL scenes 1–6 | **Aligned:** `video-script.md` (Sep 11 rewrite); appendix for SLA | OK | — |
| Test checklist UI smoke | J-FULL + 3-link nav | **Aligned:** J1-6 = 3 links; UI-7 = `/replay` 404 | OK | — |
| Legacy UI tests doc | `journey-ui-browser` = J-FULL | **Aligned:** spec rewritten Sep 11 | OK | — |
| Viewer role | Removed; operator only | **Δ:** `plans/phase-4/8/9`, old `STATUS.md` lines; **OK:** `operator-journey.md` | Partial | Category B; ignore for judges |
| 8 Demo Scenarios grid | Not on dashboard | **OK:** removed from UI; still documented in `demo-workloads.md`, S6 playbook | OK | S6 = scan tags, not dashboard grid |
| Governance dashboard | J10–J12 API-only | **Δ:** old phase plans describe tiles; playbook S7–S9 API-first | Partial | Category B plans; playbook OK |
| API reference layout | J-FULL endpoints primary | **OK:** J-FULL table + “Removed HTTP routes”; replay section archived | OK | — |
| STATUS.md | Internal history | **Partial:** Sep 8 sprint snapshots; banner points to J-FULL | Partial | Category A — metrics from `docs/README.md` |
| submission-record | J-FULL as primary demo | **OK:** primary demo reframed Sep 11 | OK | — |
| Root `.docx` plans | J-FULL | Unknown / likely replay-first scenes | Δ | Category F — do not cite without cross-check |
| Missing `replay-api.md` | N/A | **Δ:** `plans/phase-2` links to non-existent file | Δ | Point to `api-reference.md` replay section |
| `HACKATHON_DEMO.md` stub | → `judge-demo.md` | Stub OK; `operator-journey.md` points to judge-demo appendix | OK | — |
| Archive | Not maintained | `docs/archive/`, `LIVE_SCENARIOS_TODO.md` stub | OK | Category D |

**Summary:** Judge-facing docs aligned to J-FULL post-cleanup. Remaining **doc Δ:** historical `plans/*`, root `.docx`, optional diagram pass on `architecture.svg`.

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
| architecture.svg (not in repo) | Referenced historically; use [architecture-overview.md](architecture-overview.md) ASCII | No checked-in SVG — diagram lives in architecture-overview |

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
| Divergence matrix (timing) | [code-changes-timing.md](code-changes-timing.md#divergence-matrix-reference-vs-today) |
| Divergence matrix (code) | [stale-code-removal-plan.md](stale-code-removal-plan.md#divergence-matrix-code-vs-j-full-reference) |
| Stale **code** | [stale-code-removal-plan.md](stale-code-removal-plan.md) |
| Now vs later | [code-changes-timing.md](code-changes-timing.md) |
