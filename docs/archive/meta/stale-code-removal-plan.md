# Stale & Obsolete Code Removal Plan

**Status:** Phases **0–5 executed** Sep 11, 2026 · Phase **6 deferred**  
**Last updated:** Sep 12, 2026  
**Product source of truth:** [operator-journey.md](operator-journey.md) (J-FULL)  
**When to execute:** See **[code-changes-timing.md](code-changes-timing.md)** — defer phases until after Devpost unless CI forces a fix.  
**Goal:** Remove or quarantine surfaces that are **not** part of the three-link operator UI, without breaking CI or hackathon proofs you still want to keep.

---

## Phase execution summary

| Phase | Description | Status |
|-------|-------------|--------|
| **0** | J-FULL doc alignment | **Done** — README, judge-demo, api-reference J-FULL table, STATUS banner, submission-record, `plans/SUPERSEDED.md` |
| **1** | Frontend dead surfaces | **Done** — `/replay` page, demo API client, redirects via `next.config.ts`, `journey-ui-browser` |
| **2** | Optional demo API routes | **Done** — removed `replay`, `ec2-demo`, `cloudtrail`, `tagging`, `cost` routers + route modules |
| **3** | Replay-centric Playwright | **Done** — deleted 9 specs; retargeted J7/J9/quality-dashboard/helpers |
| **4** | EC2 promote mapping | **Done** — `apply_cost_recovery` only; `adapters/ec2_demo.py` + unit tests removed |
| **5** | Governance demo APIs | **Done** (with Phase 2 route deletion) |
| **6** | Infra / AgentCore trim | **Deferred** — CDK/AgentCore/Gateway unchanged (hackathon rubric); replay **adapter** kept for pytest/scorecard |

---

## Principles

1. **J-FULL stays** — `/scan`, `/opportunities`, `/opportunities/[id]`, `/recovery`, promote + approvals + outcomes + SNS + 9 scanners.  
2. **Delete vs archive** — Prefer delete when unused; move to `docs/archive/` or `backend/tests/fixtures` only for historical reference.  
3. **Test migration** — Before removing a route, retarget or delete Playwright/specs that depend on it; keep **one** mega journey: `journey-full-discovery-triage-ledger.spec.ts`.  
4. **Phased** — Each phase should leave `pytest` + `npx playwright test --grep @smoke` green.

---

## Divergence matrix (code vs J-FULL reference)

**Reference:** [operator-journey.md](operator-journey.md) — steps, APIs (§ Quick reference), agent pipeline table (§ Agent pipeline vs this journey).  
**Verified in code:** `sidebar.tsx`, `frontend/src/app/**/page.tsx`, `backend/src/recoup/api/main.py`, `scan.py`, `useRole.tsx`, `live-ec2-demo-removed.spec.ts`.

| Layer | J-FULL reference | Codebase today | Δ | Cleanup phase |
|-------|------------------|----------------|----|----------------|
| **Nav** | 3 sidebar links | `NAV`: `/opportunities`, `/scan`, `/recovery` | OK | — |
| **Routes (product)** | `/`, scan, opportunities, `[id]`, recovery | All present; `/` → opportunities | OK | — |
| **Routes (extra UI)** | Not required; J4 optional | `/replay` **removed**; `/approvals`, `/quality` redirects remain | OK / partial | **Phase 1** ✅ replay page; redirects optional keep |
| **HITL** | Detail + approvals API | `opportunities/[id]/page.tsx`, `routes/approvals.py` | OK | — |
| **Scan** | 9 scanners, `POST /api/scan/demo` | `_ALL_SCANNERS` in `scan.py` (9) | OK | — |
| **Promote** | `POST /api/scan/findings/promote` → `AWAITING_APPROVAL` | `promote_finding`; idempotent by `resource_id` | OK | — |
| **Graph on promote** | Runs through `risk_policy_gate` + `recovery/` pipeline; no SSE | Matches `operator-journey` + `scan.py` | OK | Do not SSE-stream promote or run past gate without HITL |
| **Graph optional** | `POST /api/opportunities/{id}/run` | `opportunities.py` | OK | Keep |
| **Graph replay path** | J4 engine only | `adapters/replay.py`, `recoup_graph.py`; **no** `routes/replay.py` | OK (adapter) | Keep for pytest/scorecard |
| **SNS** | Approve only | `HITLFlow.approve` → `notifications.py` | OK | — |
| **Ledger** | `/recovery` + summary on opportunities | `recovery/page.tsx`, `recovery-ledger.tsx`, `useRecoveryData.ts` | OK | — |
| **Role** | Operator only | `useRole.tsx` hardcoded | OK | — |
| **Removed UI (expected absent)** | No EC2 card, governance grid, SLA nav, Viewer | Asserted in `live-ec2-demo-removed.spec.ts` | OK | Keep spec |
| **Backend J-FULL APIs** | scan, approvals, opportunities, admin/test reset | Mounted | OK | **Never remove** in cleanup |
| **Backend extra APIs** | Not in J-FULL § API map | Demo routers **removed**; `quality` scorecard **kept** | OK | **Done** Phase 2/5 |
| **SQS poller** | Not in operator loop | Health ack only (no auto replay) | OK | **Done** Phase 2 |
| **Promote → EC2 action** | `apply_cost_recovery` | `_recovery_action_for_finding()` always cost recovery | OK | **Done** Phase 4 |
| **EC2 demo module** | Removed from promote path | `adapters/ec2_demo.py` deleted; core `ec2_tools` may remain for AgentCore | Partial | **Done** Phase 2/4 |
| **Eval fixtures / scripts** | Not used in J-FULL UI | `eval_fixtures/`, `replay_run.py`, `inject_sla_metrics.py` | Δ | **Phase 2** (keep unit fixtures if API removed) |
| **Tests authoritative** | `journey-full-discovery-triage-ledger.spec.ts` | Present (`@smoke @e2e`) | OK | **Protect** |
| **Tests overlapping J-FULL** | J2, J6, J9, scan, decision-inbox | Present | OK | Keep |
| **Tests divergent IA** | 3-link product | `journey-ui-browser.spec.ts` rewritten for J-FULL | OK | **Phase 1** ✅ |
| **Tests optional journeys** | J4, J5, J10–J12 e2e removed | Golden replay **pytest** + WF-11 smoke | OK | **Done** Phase 3 |
| **Docs product** | J-FULL canonical | Sep 11 alignment (Phase 0 ✅) | OK | **Phase 0** tail in checklist below |

**Interpretation:** **Δ** rows are *intentional coexistence* until phases run — not bugs. J-FULL path is **OK** across UI + core backend; divergence is **extra** routes, pages, poller, and test suites.

---

## Current product vs leftover inventory

| Area | J-FULL (keep) | Stale / optional (candidate removal) |
|------|----------------|--------------------------------------|
| **Nav** | 3 links in `sidebar.tsx` | SLA Replay nav, EC2 demo card, governance tiles, 8-scenario grid, Viewer role (already removed from UI) |
| **Frontend routes** | `/`, `/opportunities`, `/scan`, `/recovery`, `/opportunities/[id]` | `/replay` **removed**; redirect-only `/approvals`, `/quality` (optional delete) |
| **Backend API** | `/api/scan/*`, `/api/approvals/*`, `/api/opportunities/*`, `/api/quality/scorecard`, health, admin reset | Demo HTTP prefixes **removed** Sep 2026 |
| **Graph** | Promote path in `scan.py`, optional `POST .../run` | Full replay adapter path if replay API removed |
| **Infra / jobs** | Scanner IAM, approvals DynamoDB, SNS | SQS poller → auto canonical replay (`sqs_poller.py`) |
| **Tests** | J-FULL, J2, J6, J9, SEC, scan specs | J4, J5, J10–J12, `journey-sla-replay*`, `journey-ec2-stop*`, `governance.spec`, large Strands lifecycle suites tied to replay |
| **Docs** | operator-journey, judge-demo (updated), demo-playbook S5 | Old “replay-first” copy in `plans/`, phase docs, `video-script` appendix only |

---

## Phase 0 — Documentation & test labels (done / low risk)

**Completed (Sep 11, 2026):** README, docs index, judge-demo, demo-playbook, USER_JOURNEY_CHECKLIST, architecture-overview, frontend-guide, video-script, `plans/phase-7` as-built aligned to J-FULL.

**Remaining doc hygiene:**

- [x] Replay UI removed — document in `frontend-guide.md`, matrices updated  
- [ ] `STATUS.md` — mark replay UI removed; point primary story to J-FULL  
- [ ] `docs/api-reference.md` — group endpoints into **J-FULL** vs **Legacy / optional**  
- [ ] Root stubs (`DEMO_SCENARIOS.md`) — one line “primary path = operator-journey.md”  
- [ ] `plans/phase-*.md` — bulk banner “superseded by operator-journey.md” (optional)

---

## Phase 1 — Frontend dead surfaces

**Status (Sep 11, 2026):** ✅ `/replay` page deleted · `api.replay` client removed · `journey-ui-browser.spec.ts` rewritten for J-FULL · `/quality` redirect test kept.

**Remove or gate behind `NEXT_PUBLIC_ENABLE_LEGACY_DEMOS=1`:**

| Item | Path | Depends on |
|------|------|------------|
| SLA Replay page | `frontend/src/app/replay/page.tsx` | `api.replay` in `lib/api.ts` |
| Redirect pages | `frontend/src/app/approvals/page.tsx`, `quality/page.tsx` | Can stay as redirects (cheap) or delete routes and rely on middleware |
| Legacy API client methods | `api.ts` — `replay`, unused demo helpers | Backend routes |

**Tests to update/remove:**

- `live-ec2-demo-removed.spec.ts` — **keep** (documents absence of stale UI)  
- `journey-ui-browser.spec.ts` — remove or rewrite tests expecting 6 routes, `/quality` page, Viewer role  
- `sla-replay.spec.ts`, UI steps in `journey-sla-replay-full.spec.ts` that open `/replay`

**Exit criteria:** Smoke = J-FULL + scan + decision paths; no test navigates to `/replay` unless legacy flag on.

---

## Phase 2 — Optional demo API routes (backend)

Remove routers from `main.py` and delete route modules if product no longer needs depth proofs:

| Router | Module | Still useful for |
|--------|--------|------------------|
| `replay` | `api/routes/replay.py` | Golden SLA math, AgentCore graph demo |
| `ec2-demo` | `api/routes/ec2_demo.py` | Live StopInstances proof |
| `cloudtrail-demo` | `api/routes/cloudtrail_demo.py` | J10 governance |
| `tagging-demo` | `api/routes/tagging_demo.py` | J11 |
| `cost-demo` | `api/routes/cost_demo.py` | J12 |

**Recommendation:** If hackathon video mentions “11-node graph” or live EC2, **keep replay + ec2-demo as API-only** and delete only **frontend** pages. If pitch is **J-FULL only**, delete replay + ec2-demo last after migrating quality gates off replay metrics.

**Coupled code if replay removed entirely:**

- `backend/src/recoup/adapters/replay.py`  
- `backend/src/recoup/sqs_poller.py` (replay auto-trigger)  
- `eval_fixtures/sla/**` (keep for **unit** tests even if API gone — or move to `tests/fixtures`)  
- `scripts/replay_run.py`, `inject_sla_metrics.py`, parts of `quality.py` scorecard that assume replay P95  

**Exit criteria:** `pytest tests/e2e/test_golden_replay.py` either kept (unit) or replaced with calculator-only tests.

---

## Phase 3 — Graph & Strands lifecycle tests

Large E2E surface exists for **replay-centric** agent streaming:

| Spec | Tests | Action |
|------|------:|--------|
| `journey-strands-all-lifecycles.spec.ts` | 64 | Trim to J-FULL + scan promote + optional `run` |
| `journey-sse-stream-nodes.spec.ts` | 10 | Keep only if replay API kept |
| `journey-bedrock-strands-e2e.spec.ts` | 11 | Same |
| `journey-sla-replay-full.spec.ts` | 10 | Delete if J4 removed |

**Keep minimum agent proof without replay UI:**

- `POST /api/opportunities/{id}/run` with `use_strands=true` on a **promoted** scan opportunity (add one smoke test if missing).

---

## Phase 4 — EC2 demo & promote action mapping

Promote still maps idle EC2 to `stop_demo_instance` (`scan.py` `_recovery_action_for_finding`). For pure “cost recovery” narrative:

- [ ] Decide: approve path records **RECOVERED** without calling `ec2-demo/execute` (current behavior for non-stop actions)  
- [ ] Remove `stop_demo_instance` from promote if EC2 demo deleted  
- [ ] Remove `backend/src/recoup/adapters/ec2_demo.py`, `tools/ec2_tools.py` **only** if live stop proof abandoned  

**Risk:** Demo workload `oversized-ec2` finding may still reference stop action in approval payload — align copy on opportunity detail.

---

## Phase 5 — Governance demo APIs

If dashboard cards are gone and judges never curl these:

- Delete `cloudtrail_demo.py`, `tagging_demo.py`, `cost_demo.py`  
- Delete `governance.spec.ts`, `journey-governance.spec.ts`  
- Remove any orphaned frontend components (search `GovernanceInsights`, `cloudtrail-demo`)

**Alternative:** Fold governance into **scanner findings** only (CW Logs / Cost Explorer scanners already in J-FULL).

---

## Phase 6 — Infra & AgentCore (only if de-scoping hackathon AWS story)

**Do not remove lightly** — competition rubric may expect Bedrock AgentCore:

- `infra/agentcore-config.yaml`, `scripts/register_agentcore.py`  
- Gateway tool Lambdas  

If replay goes away but AgentCore must stay: register fewer tools; document “AgentCore used for optional investigation run.”

---

## Suggested execution order (recommended)

```text
Phase 0  Docs ✅
Phase 1  Remove /replay page + trim journey-ui-browser
Phase 5  Governance demo APIs (if unused in pitch)
Phase 2  replay + ec2-demo API (only after deciding video/rubric need)
Phase 3  Collapse Strands lifecycle specs
Phase 4  EC2 action mapping cleanup
Phase 6  Infra (last resort)
```

---

## Verification commands (after each phase)

```bash
cd backend && pytest tests/ -q -W error::DeprecationWarning
cd frontend && npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts
cd frontend && npx playwright test --grep @smoke
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
```

---

## Decision checklist (product owner)

Answer before Phase 2+:

1. **Video / Devpost:** Is SLA replay or live EC2 stop still shown? (If no → stronger deletion.)  
2. **Quality scorecard:** Can gates pass without `replay_p95_seconds`?  
3. **AgentCore rubric:** Is “11-node graph” required verbally only (API curl) or must it be UI?  
4. **CI time:** Is reducing 279 tests acceptable by dropping J4/J5/J10–J12/LC suites?

---

## Tier B — Keep for J-FULL optional depth (Sep 11 audit decision)

**Decision:** Retain until post-hackathon unless you explicitly drop scorecard / AgentCore rubric proofs.

| Area | Not on J-FULL promote? | Action |
|------|------------------------|--------|
| `graph/recoup_graph.py`, `adapters/replay.py` | Yes | **Keep** — pytest golden replay + optional `POST .../run` |
| `agents/strands_agents.py`, `adapters/agentcore.py` | Yes | **Keep** — optional investigation + competition narrative |
| `api/routes/quality.py` | Yes (no UI page) | **Keep** — ship gates; curl in judge appendix |
| `tools/ec2_tools.py`, Cedar `stop_demo_instance` | Yes for scan promote | **Keep** — tool contracts; not wired from promote |
| `infra/cdk/**`, `infra/agentcore-config.yaml` | Yes | **Keep** — Phase 6 deferred |
| Eval scripts (`run_eval_suite.py`, `replay_run.py`, …) | Yes | **Keep** — CI / ops |
| Detail page SSE + Re-run | Optional UX | **Keep** — documented in operator-journey |

**Playwright consolidation (Sep 11):** Removed duplicate specs → **15** files; **123** tests as of Sep 12 (`journey-ui-browser` expanded).

---

## Related documents

| Doc | Role |
|-----|------|
| [code-changes-timing.md](code-changes-timing.md#divergence-matrix-reference-vs-today) | Same reference, **when** to close gaps |
| [stale-documents.md](stale-documents.md#divergence-matrix-documentation-vs-j-full) | Same reference, **markdown** Δ |
| [operator-journey.md](operator-journey.md) | What must never break |
| [judge-demo.md](judge-demo.md) | What judges see |
| [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) | Test map after pruning |
| [demo-playbook.md](demo-playbook.md) | Which scenarios stay “optional” |
