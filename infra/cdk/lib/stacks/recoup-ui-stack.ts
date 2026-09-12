/**
 * Plane A — Next.js UI on App Runner (fallback when Amplify GitHub is not connected).
 * Prefer Amplify via scripts/deploy_amplify_frontend.sh when GITHUB_OAUTH_TOKEN is set.
 */

import * as cdk from "aws-cdk-lib";
import * as apprunner from "aws-cdk-lib/aws-apprunner";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

export interface RecoupUiStackProps extends cdk.StackProps {
  createUiService?: boolean;
}

export class RecoupUiStack extends cdk.Stack {
  public readonly repository: ecr.Repository;
  public readonly serviceUrl: string;

  constructor(scope: Construct, id: string, props: RecoupUiStackProps) {
    super(scope, id, props);

    this.repository = new ecr.Repository(this, "RecoupUiRepository", {
      repositoryName: "recoup-ui",
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [{ maxImageCount: 5 }],
    });
    cdk.Tags.of(this.repository).add("RecoupLayer", "hosting");
    cdk.Tags.of(this.repository).add("RecoupDemo", "false");

    const ecrAccessRole = new iam.Role(this, "UiAppRunnerEcrAccessRole", {
      assumedBy: new iam.ServicePrincipal("build.apprunner.amazonaws.com"),
    });
    this.repository.grantPull(ecrAccessRole);

    const autoScaling = new apprunner.CfnAutoScalingConfiguration(this, "RecoupUiAutoScaling", {
      autoScalingConfigurationName: "recoup-ui-scaling",
      maxConcurrency: 50,
      maxSize: 1,
      minSize: 1,
    });

    const observability = new apprunner.CfnObservabilityConfiguration(this, "RecoupUiObservability", {
      observabilityConfigurationName: "recoup-ui-obs",
      traceConfiguration: { vendor: "AWSXRAY" },
    });

    const imageTag = process.env.RECOUP_UI_IMAGE_TAG ?? "latest";
    const deployService = props.createUiService ?? false;

    if (!deployService) {
      new cdk.CfnOutput(this, "UiAppRunnerServiceUrl", {
        value: "(deploy with scripts/deploy_ui_hosting.sh)",
      });
      new cdk.CfnOutput(this, "UiEcrRepositoryUri", {
        value: this.repository.repositoryUri,
        exportName: "RecoupUiEcrUri",
      });
      this.serviceUrl = "";
      return;
    }

    const service = new apprunner.CfnService(this, "RecoupUiService", {
      serviceName: "recoup-ui",
      autoScalingConfigurationArn: autoScaling.attrAutoScalingConfigurationArn,
      observabilityConfiguration: {
        observabilityConfigurationArn: observability.attrObservabilityConfigurationArn,
        observabilityEnabled: true,
      },
      healthCheckConfiguration: {
        protocol: "HTTP",
        path: "/api/health",
        interval: 10,
        timeout: 5,
        healthyThreshold: 1,
        unhealthyThreshold: 5,
      },
      instanceConfiguration: {
        // 512/1024 leaves headroom with recoup-api on 1024/2048 (account App Runner limits).
        cpu: "512",
        memory: "1024",
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
            port: "3000",
            runtimeEnvironmentVariables: [
              { name: "PORT", value: "3000" },
              { name: "HOSTNAME", value: "0.0.0.0" },
              { name: "NODE_ENV", value: "production" },
            ],
          },
        },
      },
    });

    cdk.Tags.of(service).add("RecoupLayer", "hosting");
    cdk.Tags.of(service).add("RecoupDemo", "false");

    this.serviceUrl = `https://${service.attrServiceUrl}`;

    new cdk.CfnOutput(this, "UiAppRunnerServiceUrl", {
      value: this.serviceUrl,
      exportName: "RecoupUiAppRunnerServiceUrl",
    });
    new cdk.CfnOutput(this, "UiEcrRepositoryUri", {
      value: this.repository.repositoryUri,
      exportName: "RecoupUiEcrUri",
    });
  }
}
