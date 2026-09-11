#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { RecoupInfraStack } from "../lib/stacks/recoup-infra-stack";
import { RecoupDemoStack } from "../lib/stacks/recoup-demo-stack";
import { RecoupIamStack } from "../lib/stacks/iam-stack";
import { RecoupDemoWorkloadsStack } from "../lib/stacks/recoup-demo-workloads-stack";
import { RecoupSLADemoStack } from "../lib/stacks/recoup-sla-demo-stack";

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? "us-east-1",
};

const infra = new RecoupInfraStack(app, "RecoupInfraStack", {
  env,
  description: "Recoup core infrastructure — DynamoDB, S3, SQS, KMS, EventBridge",
});

new RecoupDemoStack(app, "RecoupDemoStack", {
  env,
  vpc: infra.vpc,
  description: "Recoup demo EC2 instance (RecoupDemo=true tag; reversible stop only)",
});

new RecoupIamStack(app, "RecoupIamStack", {
  env,
  account: process.env.CDK_DEFAULT_ACCOUNT ?? "",
  externalId: process.env.RECOUP_EXTERNAL_ID ?? "recoup-demo-external-id",
  description:
    "Phase 6e — RecoupReadOnlyRole + RecoupRemediationRole with STS AssumeRole trust",
});

// Phase 6f — 8 controlled waste scenarios for the demo story
new RecoupDemoWorkloadsStack(app, "RecoupDemoWorkloadsStack", {
  env,
  vpc: infra.vpc,
  description:
    "Phase 6f — RecoupDemoWorkloadsStack: 8 demo waste scenarios " +
    "(oversized-ec2, unattached-ebs, gp2-migration, idle-eip, idle-rds, " +
    "s3-no-lifecycle, oversized-lambda, stale-snapshot). " +
    "Destroy after hackathon: cdk destroy RecoupDemoWorkloadsStack",
});

// Option C — Real API Gateway + Lambda for SLA replay evidence
new RecoupSLADemoStack(app, "RecoupSLADemoStack", {
  env,
  description:
    "Option C — Real API Gateway (recoup-sla-demo) + Lambda (recoup-sla-health) " +
    "for SLA replay evidence. Run scripts/inject_sla_traffic.py after deploy. " +
    "Cost: ~$0.70 one-time. Destroy after hackathon: cdk destroy RecoupSLADemoStack",
});
