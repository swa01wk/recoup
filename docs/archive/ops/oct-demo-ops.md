# Operations through Oct 31 ($150 plan)

**Production URLs:** UI https://pdkeexzwxr.us-east-1.awsapprunner.com · API https://qawwrm7kzy.us-east-1.awsapprunner.com  
**Hosting:** [production-hosting.md](./production-hosting.md) · **Segregation:** [demo-vs-platform-segregation.md](./demo-vs-platform-segregation.md)

## Weekly (5 min)

1. Billing → Cost Explorer → by service (API Gateway ≈ $0, RDS/EC2 compute minimal).
2. `./scripts/stop_demo_scanner_compute.sh` if EC2/RDS were started for filming.
3. App Runner **max instances = 1** per service (`recoup-api`, `recoup-ui`); account may cap at **2** App Runner services in `us-east-1`.

## Budget alerts

```bash
./scripts/create_plan_budget_alerts.sh
```

| Threshold | Meaning |
|-----------|---------|
| $100/mo | Warning |
| $150/mo | Plan ceiling — no hosting upgrades |
| $180/mo | Stretch — document why |

Credits backstop ~$204; plan discipline is **$150 total** through Oct 31.

## Stretch triggers (before spending past $150)

- Judge window + need EC2+RDS up for richer scans
- Demo scan timeouts → larger App Runner CPU (stretch)
- **Not:** AgentCore, SLA stack, 24/7 demo compute without reason

## Start demo compute (Plane D only)

See [stopped-services.md](./stopped-services.md). Does **not** stop App Runner or DynamoDB.

## After Oct 31

1. `cdk destroy RecoupDemoWorkloadsStack` (Plane D)
2. Remove App Runner + Amplify when URL no longer needed
3. Optional `cdk destroy RecoupInfraStack` after export
