#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { RecoupInfraStack } from "../lib/stacks/recoup-infra-stack";
import { RecoupIamStack } from "../lib/stacks/iam-stack";
import { RecoupDemoWorkloadsStack } from "../lib/stacks/recoup-demo-workloads-stack";
import { RecoupAppStack } from "../lib/stacks/recoup-app-stack";
import { RecoupUiStack } from "../lib/stacks/recoup-ui-stack";

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? "us-east-1",
};

const account = process.env.CDK_DEFAULT_ACCOUNT ?? "";
const externalId = process.env.RECOUP_EXTERNAL_ID ?? "recoup-demo-external-id";
const frontendUrl =
  process.env.RECOUP_FRONTEND_URL ?? "https://main.d11111111111.amplifyapp.com";

const infra = new RecoupInfraStack(app, "RecoupInfraStack", {
  env,
  description: "Recoup core infrastructure — DynamoDB, S3, SQS, KMS, EventBridge",
});

const iam = new RecoupIamStack(app, "RecoupIamStack", {
  env,
  account,
  externalId,
  platform: {
    snsAlertTopicArn: infra.alertTopic.topicArn,
    evidenceBucketName: infra.evidenceBucket.bucketName,
    slaCatalogBucketName: infra.slaCatalogBucket.bucketName,
    evalFixturesBucketName: infra.evalFixturesBucket.bucketName,
    evidenceKmsKeyArn: infra.evidenceKey.keyArn,
  },
  description:
    "RecoupReadOnlyRole + RecoupRemediationRole + RecoupAppRunnerRole (Plane A/C)",
});
iam.addDependency(infra);

new RecoupDemoWorkloadsStack(app, "RecoupDemoWorkloadsStack", {
  env,
  vpc: infra.vpc,
  description:
    "RecoupDemoWorkloadsStack: 8 demo waste scenarios for Account Scanner (Plane D)",
});

if (!iam.appRunnerRole) {
  throw new Error("RecoupIamStack must create appRunnerRole when platform is set");
}

const appHost = new RecoupAppStack(app, "RecoupAppStack", {
  env,
  appRunnerInstanceRoleArn: iam.appRunnerRole.roleArn,
  frontendUrl,
  opportunitiesTableName: "recoup-opportunities",
  approvalsTableName: "recoup-approvals",
  toolAuditsTableName: "recoup-tool-audits",
  outcomeMetadataTableName: "recoup-outcome-metadata",
  evidenceBucketName: infra.evidenceBucket.bucketName,
  slaCatalogBucketName: infra.slaCatalogBucket.bucketName,
  evalFixturesBucketName: infra.evalFixturesBucket.bucketName,
  evidenceKmsKeyArn: infra.evidenceKey.keyArn,
  recoveryEventsQueueUrl: infra.recoveryEventsQueue.queueUrl,
  snsAlertTopicArn: infra.alertTopic.topicArn,
  readOnlyRoleArn: iam.readOnlyRole.roleArn,
  externalId,
  createAppRunnerService: app.node.tryGetContext("createAppRunnerService") === "true",
  description: "Recoup API on App Runner (Plane A hosting)",
});
appHost.addDependency(iam);

new RecoupUiStack(app, "RecoupUiStack", {
  env,
  createUiService: app.node.tryGetContext("createUiService") === "true",
  description: "Recoup Next.js UI on App Runner (Plane A; use Amplify when GitHub connected)",
});
