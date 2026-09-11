# Code Changes — Now vs Later

**Status:** J-FULL cleanup **Phases 0–5 executed** (Sep 11, 2026) · Phase 6 deferred  
**Product source of truth:** [operator-journey.md](operator-journey.md) (J-FULL)  
**Cleanup plan:** [stale-code-removal-plan.md](stale-code-removal-plan.md)  
**Context:** Feature cutoff Sep 11, 2026 · Hackathon deadline Sep 14, 2026

---

## Plan execution status

| Track | Scope | Status |
|-------|--------|--------|
| **Phase 0** | J-FULL doc alignment | **Done** — README, judge-demo, playbook, api-reference J-FULL table, STATUS, submission-record, `plans/SUPERSEDED.md` |
| **Phase 1** | Frontend stale UI | **Done** — `/replay` page removed; demo client trimmed; `/approvals` + `/quality` redirect via `next.config.ts`; `journey-ui-browser` rewritten |
| **Phase 2** | Optional demo HTTP APIs | **Done** — `/api/replay/*`, ec2/cloudtrail/tagging/cost demo routers removed |
| **Phase 3** | Replay-centric Playwright | **Done** — 9 specs deleted; J7/J8/J9 retargeted to scan/promote |
| **Phase 4** | EC2 promote path | **Done** — `apply_cost_recovery` only; `ec2_demo` adapter removed |
| **Phase 5** | Governance demo APIs | **Done** (with Phase 2) |
| **Phase 6** | Infra / AgentCore trim | **Deferred** — CDK/AgentCore unchanged |

**Verify locally:**

```bash
cd backend && pytest tests/ -q -W error::DeprecationWarning
cd frontend && npm run build
cd frontend && PLAYWRIGHT_REUSE_SERVERS=1 npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts
cd frontend && PLAYWRIGHT_REUSE_SERVERS=1 npx playwright test --grep @smoke
```

---

## Summary

| When | What |
|------|------|
| **Now** | Demo from J-FULL only; optional Q&A cites **adapter-level** SLA replay (pytest/scorecard), not removed HTTP routes |
| **Later** | Phase 6 infra trim only if you accept AgentCore/CDK risk post-submit |

The **product UI** matches J-FULL (sidebar: Opportunities · Account Scanner · Recovery Ledger). Removed surfaces were optional judge depth paths, not the scanner loop.

---

## Divergence matrix (reference vs today)

**Reference:** [operator-journey.md](operator-journey.md) (J-FULL) · verified Sep 11, 2026 post-cleanup.  
**Legend:** **Δ** = diverges · **OK** = aligned.

| Area | J-FULL reference | Actual (code + docs) | Δ | Notes |
|------|------------------|----------------------|---|--------|
| Sidebar nav | 3 links | `sidebar.tsx` `NAV` | OK | — |
| HITL location | `/opportunities/[id]` | Detail + approvals API; `/approvals` → redirect | OK | — |
| Operator loop | Reset → scan → 3 services → HITL → ledger | `journey-full-discovery-triage-ledger.spec.ts` | OK | Primary demo |
| Graph on promote | Not streamed | `scan.py` promote → synthetic state | OK | Freeze |
| Optional Strands re-run | `POST .../run` | `opportunities.py` | OK | WF-11 smoke |
| `/replay` page | Not in product | Removed (404) | OK | Phase 1 |
| Extra demo HTTP APIs | Not in J-FULL | **Removed** (replay, ec2-demo, gov demos) | OK | Phase 2/5 |
| Replay **adapter** | Optional depth / scorecard | `adapters/replay.py` + pytest golden tests | OK | Not HTTP |
| SQS poller | Not auto-replay in loop | Health ack only | OK | Phase 2 |
| Quality scorecard | `GET /api/quality/scorecard` | Mounted; `/quality` UI redirects | OK | curl in demo |
| SNS on approve | Yes | `approval/flow.py` | OK | — |
| Viewer role | Operator only | `useRole.tsx` | OK | Phase 1 |
| AgentCore / CDK | Unchanged for rubric | Full stack still in repo | Δ | **Phase 6 deferred** |

---

## Do now (demo & submit)

| Action | Why |
|--------|-----|
| Record from **J-FULL** only | [judge-demo.md](judge-demo.md) |
| Pre-flight E2E | `journey-full-discovery-triage-ledger.spec.ts` |
| Smoke | `npx playwright test --grep @smoke` |
| Quality curl | `GET /api/quality/scorecard` |

**Do not cite in demo:** `POST /api/replay/*`, `POST /api/ec2-demo/*`, governance demo URLs — **removed**.

**Optional Q&A (no HTTP):** SLA math proven in `pytest tests/e2e/test_golden_replay.py`; scorecard gates include replay-derived metrics.

---

## Do later

| Phase | Focus |
|-------|--------|
| **6** | AgentCore/CDK/IAM trim — only if maintaining repo long-term |

---

## Related documents

| Document | Role |
|----------|------|
| [stale-documents.md](stale-documents.md) | Doc inventory + execution status |
| [stale-code-removal-plan.md](stale-code-removal-plan.md) | Phase detail + code matrix |
| [operator-journey.md](operator-journey.md) | What must keep working |
| [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) | Test map (J-FULL primary) |
