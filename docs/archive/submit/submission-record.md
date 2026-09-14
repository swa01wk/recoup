# Submission Record — AWS Agents for Humans Hackathon

**Competition:** Aug 10 – Sep 14, 2026  
**Internal deadline:** Sep 13, 2026  
**Last updated:** Sep 15, 2026  
**Status:** Phase 7 — production J-FULL verified; **builder.aws 3/3** + **Devpost submitted** (Sep 15). Remaining: demo video URL on Devpost (if not already added) + final incognito link pass.

**Primary demo (J-FULL):** [operator-journey.md](operator-journey.md) — account scan → HITL → Recovery Ledger. Optional SLA/EC2/governance **HTTP** demos removed Sep 2026; engine/tests retain replay adapter internally.

---

## URLs

| Item | URL | Verified (incognito) |
|------|-----|---------------------|
| Public GitHub repo | https://github.com/swa01wk/recoup | ☐ confirm public + MIT |
| Live demo (frontend) | https://pdkeexzwxr.us-east-1.awsapprunner.com | ☑ loads (308→200) |
| Backend API | https://qawwrm7kzy.us-east-1.awsapprunner.com | ☑ J-FULL smoke PASS |
| Demo video (≤ 5:00) | _see [video-recording-checklist.md](video-recording-checklist.md)_ | ☐ |
| Devpost submission | _paste public project URL here_ | ☑ submitted Sep 15 · ☐ incognito |
| Builder.aws Post 1 — architecture | https://builder.aws.com/content/3JKKaMeu6Cbc2HQQjmAiOosEVOH/building-recoup-agents-for-humans-and-how-we-designed-a-safe-aws-recovery-workflow-with-strands-graph | ☑ |
| Builder.aws Post 2 — trust (Cedar, redaction, HITL) | https://builder.aws.com/content/3JKron5aTHK1KpAaoIbxNdSd9IH/agents-for-humans-and-making-ai-financial-decisions-trustworthy-cedar-evidence-redaction-and-hitl-in-recoup | ☑ · ☐ incognito |
| Builder.aws Post 3 — proof (419+127, scorecard) | https://builder.aws.com/content/3JKtrHzpq4RFxt6kXlNYT5uY1uJ/agents-for-humans-and-how-we-proved-recoup-works-419-backend-127-e2e-tests-and-zero-unsafe-actions | ☑ · ☐ incognito |

---

## Devpost Fields

| Field | Value |
|-------|-------|
| Project name | Recoup |
| Tagline | Autonomous AWS cloud spend recovery — detect, prove, approve, recover |
| Track | Professional Agents |
| AWS Builder ID | Verified ☑ (on Devpost submit) |
| Language | English |

---

## Technical Completeness Checklist

### Core features (all ✅)
- [x] 9 AWS waste scanners (EC2, EBS, EIP, RDS, S3, Lambda, LB, CW Logs, Cost Explorer)
- [x] 11-node Strands Agents graph on Bedrock Nova Pro (SLA path; J-FULL uses recovery pipeline on promote — see judge-demo.md)
- [x] AgentCore-oriented CDK/IAM + tool registry (demo Cedar eval deterministic on App Runner)
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
- [x] 419 backend unit tests collected (live skipped as configured)
- [x] 127 Playwright tests (16 specs) — J-FULL + PSC + J2–J9 + SEC adversarial
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
- [ ] Demo video recorded (≤ 5:00) — follow `docs/video-script.md`; add URL on Devpost if empty
- [x] Devpost submission published (Sep 15)
- [x] Architecture diagram finalized (`architecture/architecture.svg`)
- [x] Builder community posts live (3 posts — [builder-post-drafts.md](builder-post-drafts.md))
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
- [x] README FAQ (safety + savings proof; no third-party product comparisons)
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
- [x] Re-read official Devpost rules before submit
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
| Devpost submitted | Sep 15 AM | Builder ID verified on form; add project URL to URLs table |
| Builder posts live | Sep 15 | 3/3 URLs in devpost-project-description.md |
| GitHub repo made public | | |
