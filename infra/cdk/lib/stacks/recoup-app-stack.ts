/**
 * Plane A — Recoup public API hosting (App Runner + ECR + RecoupAppRunnerRole).
 *
 * Deploy after RecoupInfraStack + RecoupIamStack (ReadOnlyRole trusts App Runner role).
 * Push image: ../../scripts/deploy_app_hosting.sh
 */

import * as cdk from "aws-cdk-lib";
import * as apprunner from "aws-cdk-lib/aws-apprunner";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

export interface RecoupAppStackProps extends cdk.StackProps {
  /** Plane A — from RecoupIamStack (RecoupAppRunnerRole). */
  appRunnerInstanceRoleArn: string;
  /** Amplify / frontend origin for CORS (FRONTEND_URL). Update after Amplify first deploy. */
  frontendUrl: string;
  opportunitiesTableName: string;
  approvalsTableName: string;
  toolAuditsTableName: string;
  outcomeMetadataTableName: string;
  evidenceBucketName: string;
  slaCatalogBucketName: string;
  evalFixturesBucketName: string;
  evidenceKmsKeyArn: string;
  recoveryEventsQueueUrl: string;
  snsAlertTopicArn: string;
  readOnlyRoleArn: string;
  externalId: string;
  bedrockRegion?: string;
  /** Set true after ECR image push (see scripts/deploy_app_hosting.sh). */
  createAppRunnerService?: boolean;
}

export class RecoupAppStack extends cdk.Stack {
  public readonly repository: ecr.Repository;
  public readonly serviceUrl: string;

  constructor(scope: Construct, id: string, props: RecoupAppStackProps) {
    super(scope, id, props);

    const region = props.bedrockRegion ?? this.region;

    this.repository = new ecr.Repository(this, "RecoupApiRepository", {
      repositoryName: "recoup-api",
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [{ maxImageCount: 5 }],
    });
    cdk.Tags.of(this.repository).add("RecoupLayer", "hosting");

    const ecrAccessRole = new iam.Role(this, "AppRunnerEcrAccessRole", {
      assumedBy: new iam.ServicePrincipal("build.apprunner.amazonaws.com"),
    });
    this.repository.grantPull(ecrAccessRole);

    const autoScaling = new apprunner.CfnAutoScalingConfiguration(this, "RecoupApiAutoScaling", {
      autoScalingConfigurationName: "recoup-api-scaling",
      maxConcurrency: 50,
      maxSize: 1,
      minSize: 1,
    });

    const imageTag = process.env.RECOUP_API_IMAGE_TAG ?? "latest";
    const deployService = props.createAppRunnerService ?? false;

    if (!deployService) {
      new cdk.CfnOutput(this, "AppRunnerServiceUrl", {
        value: "(deploy with -c createAppRunnerService=true after docker push)",
        description: "Run scripts/deploy_app_hosting.sh",
      });
      new cdk.CfnOutput(this, "EcrRepositoryUri", {
        value: this.repository.repositoryUri,
        exportName: "RecoupApiEcrUri",
      });
      this.serviceUrl = "";
      return;
    }

    const service = new apprunner.CfnService(this, "RecoupApiService", {
      serviceName: "recoup-api",
      autoScalingConfigurationArn: autoScaling.attrAutoScalingConfigurationArn,
      healthCheckConfiguration: {
        // HTTP /health failed stabilization at 512/1024; TCP matches proven App Runner create path.
        protocol: "TCP",
        path: "/",
        interval: 10,
        timeout: 5,
        healthyThreshold: 1,
        unhealthyThreshold: 10,
      },
      instanceConfiguration: {
        // 512/1024 cold-starts often fail HTTP health before uvicorn listens; 1 vCPU / 2 GiB stabilizes.
        cpu: "1024",
        memory: "2048",
        instanceRoleArn: props.appRunnerInstanceRoleArn,
      },
      sourceConfiguration: {
        authenticationConfiguration: {
          accessRoleArn: ecrAccessRole.roleArn,
        },
        autoDeploymentsEnabled: false,
        imageRepository: {
          imageIdentifier: `${this.repository.repositoryUri}:${imageTag}`,
          imageRepositoryType: "ECR",
          imageConfiguration: {
            port: "8080",
            runtimeEnvironmentVariables: [
              { name: "PORT", value: "8080" },
              { name: "RECOUP_ENV", value: "production" },
              { name: "RECOUP_ENABLE_ADMIN_RESET", value: "true" },
              { name: "FRONTEND_URL", value: props.frontendUrl },
              { name: "OPPORTUNITIES_TABLE", value: props.opportunitiesTableName },
              { name: "APPROVALS_TABLE", value: props.approvalsTableName },
              { name: "TOOL_AUDITS_TABLE", value: props.toolAuditsTableName },
              { name: "OUTCOME_METADATA_TABLE", value: props.outcomeMetadataTableName },
              { name: "DEMO_CONTROL_TABLE", value: "recoup-demo-control" },
              { name: "EVIDENCE_BUCKET", value: props.evidenceBucketName },
              { name: "SLA_CATALOG_BUCKET", value: props.slaCatalogBucketName },
              { name: "EVAL_FIXTURES_BUCKET", value: props.evalFixturesBucketName },
              { name: "EVIDENCE_KMS_KEY_ID", value: props.evidenceKmsKeyArn },
              { name: "RECOVERY_EVENTS_QUEUE_URL", value: props.recoveryEventsQueueUrl },
              { name: "RECOUP_SNS_TOPIC_ARN", value: props.snsAlertTopicArn },
              { name: "RECOUP_READONLY_ROLE_ARN", value: props.readOnlyRoleArn },
              { name: "RECOUP_EXTERNAL_ID", value: props.externalId },
              { name: "RECOVERY_LLM_ON_PROMOTE", value: "false" },
              { name: "BEDROCK_REGION", value: region },
              { name: "LLM_PROVIDER", value: "bedrock" },
            ],
          },
        },
      },
    });

    cdk.Tags.of(service).add("RecoupLayer", "hosting");
    cdk.Tags.of(service).add("RecoupDemo", "false");

    this.serviceUrl = `https://${service.attrServiceUrl}`;

    new cdk.CfnOutput(this, "AppRunnerServiceUrl", {
      value: this.serviceUrl,
      description: "Public HTTPS URL for FastAPI — set NEXT_PUBLIC_API_URL on Amplify",
      exportName: "RecoupAppRunnerServiceUrl",
    });

    new cdk.CfnOutput(this, "EcrRepositoryUri", {
      value: this.repository.repositoryUri,
      exportName: "RecoupApiEcrUri",
    });
  }
}
