/**
 * RecoupSLADemoStack — Option C: real API Gateway + Lambda for SLA replay scenario.
 *
 * Deploys:
 *   - Python 3.12 Lambda `recoup-sla-health` — returns 200 normally,
 *     503 when env var OUTAGE_MODE=true (set by inject_sla_traffic.py)
 *   - API Gateway REST API `recoup-sla-demo` — /health GET endpoint
 *   - CloudWatch Log Group `/recoup/sla-demo-access` — 30-day retention
 *
 * After deploy, run:
 *   python scripts/inject_sla_traffic.py \
 *     --api-url <SLADemoApiUrl output> \
 *     --lambda-name recoup-sla-health
 *
 * Cost: ~$0.70 one-time (200K API calls). Ongoing idle cost: $0.
 */

import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigw from "aws-cdk-lib/aws-apigateway";
import * as logs from "aws-cdk-lib/aws-logs";
import { Construct } from "constructs";

export class RecoupSLADemoStack extends cdk.Stack {
  public readonly apiUrl: string;
  public readonly apiId: string;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ── Lambda: health endpoint with on-demand outage mode ──────────────────
    const healthFn = new lambda.Function(this, "SLAHealthFn", {
      functionName: "recoup-sla-health",
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "index.handler",
      timeout: cdk.Duration.seconds(5),
      memorySize: 128,
      code: lambda.Code.fromInline(`
import json
import os

def handler(event, context):
    if os.environ.get("OUTAGE_MODE") == "true":
        return {
            "statusCode": 503,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "status": "error",
                "message": "Service temporarily unavailable",
                "service": "recoup-sla-demo"
            })
        }
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "status": "ok",
            "service": "recoup-sla-demo",
            "account": "${this.account}"
        })
    }
`),
      environment: {
        OUTAGE_MODE: "false",
      },
    });

    // ── CloudWatch log group for access logs ────────────────────────────────
    const accessLogGroup = new logs.LogGroup(this, "SLADemoAccessLogs", {
      logGroupName: "/recoup/sla-demo-access",
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ── API Gateway REST API ────────────────────────────────────────────────
    const api = new apigw.RestApi(this, "SLADemoApi", {
      restApiName: "recoup-sla-demo",
      description: "Recoup SLA demo API — real CloudWatch + CloudTrail evidence for SLA replay scenario",
      deployOptions: {
        stageName: "prod",
        accessLogDestination: new apigw.LogGroupLogDestination(accessLogGroup),
        accessLogFormat: apigw.AccessLogFormat.jsonWithStandardFields(),
        metricsEnabled: true,
        dataTraceEnabled: false,
        loggingLevel: apigw.MethodLoggingLevel.ERROR,
      },
      defaultCorsPreflightOptions: undefined,
    });

    // GET /health
    const health = api.root.addResource("health");
    health.addMethod(
      "GET",
      new apigw.LambdaIntegration(healthFn, { proxy: true }),
      { apiKeyRequired: false },
    );

    // ── Outputs ─────────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, "SLADemoApiUrl", {
      value: `${api.url}health`,
      description: "Health endpoint URL — pass to inject_sla_traffic.py --api-url",
    });

    new cdk.CfnOutput(this, "SLADemoApiId", {
      value: api.restApiId,
      description: "API Gateway REST API ID — set as RECOUP_SLA_DEMO_API_ID in .env",
    });

    new cdk.CfnOutput(this, "SLADemoLambdaName", {
      value: healthFn.functionName,
      description: "Lambda function name — pass to inject_sla_traffic.py --lambda-name",
    });

    cdk.Tags.of(this).add("ManagedBy", "recoup");
    cdk.Tags.of(this).add("Purpose", "sla-demo-evidence");
    cdk.Tags.of(this).add("RecoupDemo", "true");

    this.apiUrl = `${api.url}health`;
    this.apiId = api.restApiId;
  }
}
