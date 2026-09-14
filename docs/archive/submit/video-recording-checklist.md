# Video recording checklist (Phase 7)

**Script:** [video-script.md](video-script.md) · **Target:** ≤ 5:00 (aim 4:40 + buffer)

## Before record

- [ ] `./scripts/prod_journey_hitl_smoke.sh` → `PASS`
- [ ] Local: `PLAYWRIGHT_BACKEND_PORT=8015 PLAYWRIGHT_FRONTEND_PORT=3015 npx playwright test e2e/journey-full-discovery-triage-ledger.spec.ts --grep @smoke` → green
- [ ] Incognito rehearsal on production (J-FULL once)
- [ ] Pre-open tabs:
  - https://pdkeexzwxr.us-east-1.awsapprunner.com/scan
  - https://pdkeexzwxr.us-east-1.awsapprunner.com/opportunities
  - https://pdkeexzwxr.us-east-1.awsapprunner.com/recovery
- [ ] Terminal ready: `curl -s https://qawwrm7kzy.us-east-1.awsapprunner.com/api/quality/scorecard | jq '.all_gates_pass'`  
  _(If prod returns `false`, use local scorecard in Scene 6 and mention “CI + local gates”.)_

## Recording settings

- Resolution: 1080p or 1440p, full screen
- Show sidebar (3 links: Opportunities · Account Scanner · Recovery Ledger)
- Mic check; reduce notification noise
- **Warm run:** complete one Demo Scan before filming (avoid waiting on scan in take)

## Must-show moments (rubric)

1. **Problem** — waste detected, loop not closed until approval  
2. **Demo Scan** — 8+ findings, masked account  
3. **Three services** — Start Recovery on EC2 / EBS / RDS (or any three)  
4. **HITL wow moment** — risk tier + action + rollback on approval card  
5. **Triage** — Approve (SNS) · Investigate · Decline  
6. **Recovery Ledger** — Remaining / Pending / Recovered  
7. **Close** — architecture.svg + positioning sentence  

## After record

- [ ] Edit to ≤ 5:00  
- [ ] Upload **public** YouTube or Vimeo  
- [ ] Enable **captions**  
- [ ] Paste URL into [submission-record.md](submission-record.md) and Devpost  
- [ ] Description links: demo URL, GitHub, builder posts  

## Suggested YouTube title

`Recoup — AWS Agents for Humans | Investigate. Prove. Approve. Recover.`

## Suggested description (first lines)

Live demo: https://pdkeexzwxr.us-east-1.awsapprunner.com  
Repo: https://github.com/swa01wk/recoup  
Built for AWS Agents for Humans Hackathon — Professional Agents track.
