#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { RecoupInfraStack } from "../lib/stacks/recoup-infra-stack";
import { RecoupDemoStack } from "../lib/stacks/recoup-demo-stack";

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
