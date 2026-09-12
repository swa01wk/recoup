# Submission Record — AWS Agents for Humans Hackathon

**Competition:** Aug 10 – Sep 14, 2026  
**Internal deadline:** Sep 13, 2026  
**Last updated:** Sep 13, 2026  
**Status:** Phase 7 — AWS production live; video + devpost remaining

**Primary demo (J-FULL):** [operator-journey.md](operator-journey.md) — account scan → HITL → Recovery Ledger. Optional SLA/EC2/governance **HTTP** demos removed Sep 2026; engine/tests retain replay adapter internally.

---

## URLs

| Item | URL | Verified (incognito) |
|------|-----|---------------------|
| Public GitHub repo | https://github.com/swa01wk/recoup | ☐ |
| Live demo (frontend) | https://nvqjc7nnif.us-east-1.awsapprunner.com | ☐ |
| Backend API | https://vxndciwupy.us-east-1.awsapprunner.com | ☐ |
| Demo video (≤ 5:00) | _record following docs/video-script.md_ | ☐ |
| Devpost submission | _publish before Sep 14_ | ☐ |
| Builder.aws Post 1 | _see docs/builder-posts.md_ | ☐ |
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
- [x] 407 backend unit tests collected (live skipped as configured)
- [x] 123 Playwright tests (15 specs) — J-FULL + J2–J9 + 13 SEC adversarial
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
- [ ] Architecture diagram finalized (`architecture/architecture.svg`)
- [ ] Builder community posts live (3 posts — `docs/builder-posts.md`)
- [ ] README final polish for judge audience

---

## Phase 9 Pre-Demo Checklist (UI)

- [ ] Root-Cause Hypothesis visible in opportunity detail
- [ ] Post-Action Verification panel visible
- [ ] Intent classification badge on Eligibility card
- [ ] Agent Trace `[Strands]` vs `[Deterministic]` labels
- [ ] ALL approval cards: risk tier + action + rollback
- [ ] Dashboard tagline + positioning sentence
- [ ] 11-step pipeline on dashboard
- [ ] README FAQ (6 objections answered)
- [ ] README three-way competitive table
- [ ] README judging rubric callout
- [x] HITL on opportunity detail (`/opportunities/[id]`) with claim binding
- [ ] Operator role: full HITL access

---

## Pre-submission validation

```bash
# 1. Run smoke tests
cd frontend && npx playwright test --grep @smoke

# 2. Check quality gates
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'
# Expected: true

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
| Devpost draft started | | |
| Video recorded | | |
| Video uploaded | | |
| Devpost submitted | | |
| Builder posts live | | |
| GitHub repo made public | | |
