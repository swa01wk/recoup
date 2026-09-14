# Submission Record — AWS Agents for Humans Hackathon

**Competition:** Aug 10 – Sep 14, 2026  
**Internal deadline:** Sep 13, 2026  
**Last updated:** Sep 13, 2026 (PM)  
**Status:** Phase 7 — production J-FULL verified (`prod_journey_hitl_smoke.sh` PASS); video upload + Devpost + builder.aws publish remain (human steps)

**Primary demo (J-FULL):** [operator-journey.md](operator-journey.md) — account scan → HITL → Recovery Ledger. Optional SLA/EC2/governance **HTTP** demos removed Sep 2026; engine/tests retain replay adapter internally.

---

## URLs

| Item | URL | Verified (incognito) |
|------|-----|---------------------|
| Public GitHub repo | https://github.com/swa01wk/recoup | ☐ confirm public + MIT |
| Live demo (frontend) | https://pdkeexzwxr.us-east-1.awsapprunner.com | ☑ loads (308→200) |
| Backend API | https://qawwrm7kzy.us-east-1.awsapprunner.com | ☑ J-FULL smoke PASS |
| Demo video (≤ 5:00) | _see [video-recording-checklist.md](video-recording-checklist.md)_ | ☐ |
| Devpost submission | _paste from [devpost-project-description.md](devpost-project-description.md)_ | ☐ |
| Builder.aws Post 1 | _[builder-post-drafts.md](builder-post-drafts.md)_ | ☐ publish + URL |
| Builder.aws Post 2 | | ☐ |
| Builder.aws Post 3 | | ☐ |

---

## Devpost Fields

| Field | Value |
|-------|-------|
| Project name | Recoup |
| Tagline | Autonomous AWS cloud spend recovery — detect, prove, approve, recover |
| Track | Professional Agents |
| AWS Builder ID | Verified ☐ |
| Language | English |

---

## Technical Completeness Checklist

### Core features (all ✅)
- [x] 9 AWS waste scanners (EC2, EBS, EIP, RDS, S3, Lambda, LB, CW Logs, Cost Explorer)
- [x] 11-node Strands Agents graph on Bedrock Nova Pro
- [x] AgentCore Runtime + Gateway integration
- [x] Cedar policy (default-deny all writes)
- [x] HITL claim binding (claim_hash + amount + state_version)
- [x] SLA verified replay with real credit math
- [x] EC2 demo with real StopInstances
- [x] Evidence sanitizer (zero PII in agent context)
- [x] Recovery Ledger (3-bucket pipeline)
- [x] Quality scorecard (6 gates via `/api/quality/scorecard`)
- [x] Cross-account ExternalId onboarding
- [x] CloudTrail no-actor detection (S7)
- [x] Missing tags scan (S8)
- [x] Cost Explorer billing data (S9)

### Testing (all ✅)
- [x] 416 backend unit tests collected (live skipped as configured)
- [x] 125 Playwright tests (16 specs) — J-FULL + J2–J9 + SEC adversarial
- [x] 0 DeprecationWarnings
- [x] mypy strict + ruff clean
- [x] CDK synth passes

### Security (all ✅)
- [x] Tampered claim_hash → 409
- [x] Wrong amount → 409
- [x] Stale state_version → 409
- [x] Double-approve → 404
- [x] X-Request-ID on all responses
- [x] account_id masked (XXXXXXXX)
- [x] /api/config exposes no secrets

### Remaining (Phase 7)
- [ ] Demo video recorded (≤ 5:00) — follow `docs/video-script.md`
- [ ] Devpost submission published
- [x] Architecture diagram finalized (`architecture/architecture.svg`)
- [ ] Builder community posts live (3 posts — drafts in `builder-post-drafts.md`)
- [x] README final polish for judge audience

---

## Phase 9 Pre-Demo Checklist (UI)

- [x] Root-Cause Hypothesis visible in opportunity detail
- [x] Post-Action Verification panel visible
- [x] Intent classification badge on Eligibility card
- [x] Agent Trace `[Strands]` vs `[Deterministic]` labels
- [x] ALL approval cards: risk tier + action + rollback
- [x] Dashboard tagline + positioning sentence
- [x] 11-step pipeline on dashboard
- [x] README FAQ (6 objections answered)
- [x] README three-way competitive table
- [x] README judging rubric callout
- [x] HITL on opportunity detail (`/opportunities/[id]`) with claim binding
- [ ] Operator role: full HITL access

---

## Pre-submission validation

```bash
# 1. Run smoke tests (use free ports if Docker holds 8000)
cd frontend && PLAYWRIGHT_BACKEND_PORT=8015 PLAYWRIGHT_FRONTEND_PORT=3015 npx playwright test --grep @smoke

# 1b. Production API journey (no browser)
./scripts/prod_journey_hitl_smoke.sh

# 2. Check quality gates
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
# Expected: true (prod may show false if DynamoDB degraded — use local for video Scene 6)

# 3. Verify 8 scenario tags
curl -s -X POST http://localhost:8000/api/scan/demo | jq '[.findings[].scenario_tag] | unique | length'
# Expected: 8

# 4. Check health
curl -s http://localhost:8000/health/ready | jq '.status'
# Expected: "ready"

# 5. Verify no secrets in config
curl -s http://localhost:8000/api/config | jq 'keys'
# Expected: ["bedrock_model","bedrock_region","real_submission_enabled"]
```

---

## Final Verification (Sep 13–14)

- [ ] All links work from different device/account (incognito)
- [ ] Video ≤ 5:00 with captions
- [ ] Repository still public; MIT license visible
- [ ] Demo URL budgeted through Oct 8, 2026
- [ ] Re-read official Devpost rules before submit
- [ ] `git log --oneline -10` shows recent meaningful commits

---

## Submission Timestamps

| Event | Date (IST) | Notes |
|-------|------------|-------|
| Devpost draft started | Sep 13 PM | devpost-project-description.md |
| Video recorded | | video-recording-checklist.md |
| Prod J-FULL API smoke | Sep 13 PM | prod_journey_hitl_smoke.sh PASS |
| Playwright J-FULL @smoke | Sep 13 PM | journey-full-discovery-triage-ledger.spec.ts |
| Video uploaded | | |
| Devpost submitted | | |
| Builder posts live | | |
| GitHub repo made public | | |
