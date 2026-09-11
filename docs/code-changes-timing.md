# Code Changes — Now vs Later

**Status:** Decision record (adopted Sep 11, 2026)  
**Product source of truth:** [operator-journey.md](operator-journey.md) (J-FULL)  
**Cleanup plan (when ready):** [stale-code-removal-plan.md](stale-code-removal-plan.md)  
**Context:** Feature cutoff Sep 11, 2026 · Hackathon deadline Sep 14, 2026 · Phase 7 (video/submission) in progress

---

## Summary

| When | What |
|------|------|
| **Now** | Demo, docs, smoke tests, optional copy fixes — **no broad code deletion** |
| **Later** | Stale UI/API/test removal per [stale-code-removal-plan.md](stale-code-removal-plan.md), ideally **after Devpost submit** |

Documentation was aligned to J-FULL (Sep 11, 2026). The **product UI already matches** (sidebar: Opportunities · Account Scanner · Recovery Ledger). Removing replay APIs, graph-heavy tests, or demo routes before submission is **unnecessary risk** with little judge-facing benefit.

---

## Do now (low risk)

| Action | Why |
|--------|-----|
| **Record the demo from J-FULL only** | Matches [judge-demo.md](judge-demo.md) and [operator-journey.md](operator-journey.md). |
| **Pre-flight E2E** | `cd frontend && npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts` |
| **Smoke before recording** | `cd frontend && npx playwright test --grep @smoke` |
| **Optional copy pass** | Grep UI for stale “SLA replay” / dashboard tiles; fix strings only — no route deletes. |
| **Scope freeze** | No refactors or cleanup PRs until after submit unless CI is failing. |

**Judge path (no code required):**

1. Sidebar **↺ Reset Demo Data** (optional)  
2. **`/scan`** → Demo Scan  
3. **`/opportunities`** → three **different services** → **Start Recovery**  
4. **`/opportunities/{id}`** → Approve / Investigate / Decline  
5. **`/recovery`** → ledger buckets  

Optional depth (not in sidebar): `POST /api/replay/api-gateway-sla`, `POST /api/ec2-demo/trigger` — mention in Q&A only if needed.

---

## Do later (after submission or when CI is stable)

Execute [stale-code-removal-plan.md](stale-code-removal-plan.md) in this order:

| Phase | Focus | Risk |
|-------|--------|------|
| **1** | Remove `/replay` page; trim legacy UI tests (`journey-ui-browser`) | Low–medium |
| **5** | Governance demo APIs if unused | Medium |
| **2** | `/api/replay/*`, `/api/ec2-demo/*` if video/rubric no longer need them | High |
| **3** | Collapse Strands/replay-centric Playwright suites | High |
| **4** | EC2 `stop_demo_instance` on promote | Medium |
| **6** | Infra / AgentCore trim | Very high |

**Verification after each phase:**

```bash
cd backend && pytest tests/ -q -W error::DeprecationWarning
cd frontend && npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts
cd frontend && npx playwright test --grep @smoke
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
```

---

## Do not do now (unless accepting slip risk)

- Delete `/api/replay/*`, `eval_fixtures/`, or golden replay unit/e2e tests.  
- Remove `journey-strands-all-lifecycles.spec.ts` or other large suites while CI still expects full coverage.  
- Single “mega cleanup” PR touching backend + frontend before the video is finished.  
- Change AgentCore / CDK / IAM unless a judge blocker or security issue.

---

## Decision checklist

Answer before starting **Phase 1+** code removal:

| Question | If **yes** | If **no** |
|----------|------------|-----------|
| Will the **≤5 min video** show SLA replay or live EC2? | Keep those **APIs**; UI already hides them. | Plan frontend Phase 1 **after** submit. |
| CI green and **>1 day** before submit? | Optional: Phase 1 on a **branch**; merge only if smoke stays green. | **No removal** until post-submit. |
| Maintaining the repo after hackathon? | Schedule post-submit cleanup PR (Phase 1 → 2). | Defer all phases. |

---

## Related documents

| Document | Role |
|----------|------|
| [operator-journey.md](operator-journey.md) | What must keep working |
| [judge-demo.md](judge-demo.md) | What to show judges |
| [stale-code-removal-plan.md](stale-code-removal-plan.md) | What to delete and how |
| [stale-documents.md](stale-documents.md) | Misleading / historical markdown inventory |
| [USER_JOURNEY_CHECKLIST.md](../USER_JOURNEY_CHECKLIST.md) | Test map after pruning |
| [README.md](../README.md) | Quick start (J-FULL) |
