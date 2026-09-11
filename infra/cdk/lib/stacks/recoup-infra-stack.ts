import * as cdk from "aws-cdk-lib";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as kms from "aws-cdk-lib/aws-kms";
import * as events from "aws-cdk-lib/aws-events";
import * as targets from "aws-cdk-lib/aws-events-targets";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import * as cloudwatchActions from "aws-cdk-lib/aws-cloudwatch-actions";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as sns from "aws-cdk-lib/aws-sns";
import { Construct } from "constructs";

export class RecoupInfraStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly runtimeRole: iam.Role;
  public readonly gatewayExecutionRole: iam.Role;
  public readonly readConnectorRole: iam.Role;

  constructor(scope: Construct, id: string, props: cdk.StackProps) {
    super(scope, id, props);

    // ── KMS ─────────────────────────────────────────────────────────────────
    const evidenceKey = new kms.Key(this, "RecoupEvidenceKey", {
      alias: "alias/recoup-evidence",
      description: "Encrypts raw evidence in S3 and DynamoDB",
      enableKeyRotation: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ── S3 Buckets ───────────────────────────────────────────────────────────
    const evidenceBucket = new s3.Bucket(this, "RecoupEvidenceBucket", {
      bucketName: `recoup-evidence-${this.account}-${this.region}`,
      versioned: true,
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: evidenceKey,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,  // Sprint 2: require TLS for all S3 operations
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: "archive-raw-evidence",
          prefix: "evidence/raw/",
          transitions: [
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(90),
            },
          ],
        },
        {
          // Sprint 2: purge sanitized judge evidence after 90 days
          id: "expire-sanitized-evidence",
          prefix: "evidence/sanitized/",
          expiration: cdk.Duration.days(90),
        },
      ],
    });

    const slaCatalogBucket = new s3.Bucket(this, "RecoupSLACatalogBucket", {
      bucketName: `recoup-sla-catalog-${this.account}-${this.region}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const evalFixturesBucket = new s3.Bucket(this, "RecoupEvalFixturesBucket", {
      bucketName: `recoup-eval-fixtures-${this.account}-${this.region}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ── DynamoDB Tables ──────────────────────────────────────────────────────
    const opportunitiesTable = new dynamodb.Table(this, "RecoupOpportunitiesTable", {
      tableName: "recoup-opportunities",
      partitionKey: { name: "id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: evidenceKey,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    opportunitiesTable.addGlobalSecondaryIndex({
      indexName: "account-state-index",
      partitionKey: { name: "account_id_masked", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "state", type: dynamodb.AttributeType.STRING },
    });

    opportunitiesTable.addGlobalSecondaryIndex({
      indexName: "state-discovered-index",
      partitionKey: { name: "state", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "discovered_at", type: dynamodb.AttributeType.STRING },
    });

    const approvalsTable = new dynamodb.Table(this, "RecoupApprovalsTable", {
      tableName: "recoup-approvals",
      partitionKey: { name: "approval_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      // Sprint 2: Fix TTL attribute name — code writes "expires_at_epoch" (Unix int);
      // CDK was incorrectly using "expires_at" (ISO string) which silently broke TTL.
      timeToLiveAttribute: "expires_at_epoch",
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: evidenceKey,  // Sprint 2: extend CMK to approvals
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const toolAuditsTable = new dynamodb.Table(this, "RecoupToolAuditsTable", {
      tableName: "recoup-tool-audits",
      partitionKey: { name: "trace_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: evidenceKey,  // Sprint 2: extend CMK to tool-audits
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const outcomeMetadataTable = new dynamodb.Table(this, "RecoupOutcomeMetadataTable", {
      tableName: "recoup-outcome-metadata",
      partitionKey: { name: "pk", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: evidenceKey,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ── SQS ─────────────────────────────────────────────────────────────────
    // Sprint 2: extend CMK encryption to SQS queues
    const dlq = new sqs.Queue(this, "RecoupRecoveryEventsDLQ", {
      queueName: "recoup-recovery-events-dlq",
      retentionPeriod: cdk.Duration.days(14),
      encryptionMasterKey: evidenceKey,
    });

    const recoveryEventsQueue = new sqs.Queue(this, "RecoupRecoveryEventsQueue", {
      queueName: "recoup-recovery-events",
      visibilityTimeout: cdk.Duration.seconds(300),
      retentionPeriod: cdk.Duration.days(14),
      deadLetterQueue: { queue: dlq, maxReceiveCount: 3 },
      encryptionMasterKey: evidenceKey,
    });

    // ── EventBridge — AWS Health events ─────────────────────────────────────
    new events.Rule(this, "RecoupHealthEventRule", {
      ruleName: "RecoupHealthEventRule",
      description: "Route all aws.health events to Recoup SQS queue",
      eventPattern: { source: ["aws.health"] },
      targets: [new targets.SqsQueue(recoveryEventsQueue)],
    });

    // ── VPC (minimal; for EC2 demo instance) ────────────────────────────────
    this.vpc = new ec2.Vpc(this, "RecoupVpc", {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        { name: "Public", subnetType: ec2.SubnetType.PUBLIC, cidrMask: 24 },
      ],
    });

    // ── CloudWatch alarms ────────────────────────────────────────────────────
    const alertTopic = new sns.Topic(this, "RecoupAlertTopic", {
      topicName: "recoup-alerts",
    });

    new cloudwatch.Alarm(this, "RecoupSpendAlarm", {
      alarmName: "RecoupEstimatedChargesAlarm",
      alarmDescription: "Alert when estimated charges exceed $10",
      metric: new cloudwatch.Metric({
        namespace: "AWS/Billing",
        metricName: "EstimatedCharges",
        dimensionsMap: { Currency: "USD" },
        statistic: "Maximum",
        period: cdk.Duration.hours(6),
      }),
      threshold: 10,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // ── CloudWatch Log Groups ────────────────────────────────────────────────
    const runtimeLogGroup = new logs.LogGroup(this, "RecoupRuntimeLogGroup", {
      logGroupName: "/recoup/runtime",
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const gatewayLogGroup = new logs.LogGroup(this, "RecoupGatewayLogGroup", {
      logGroupName: "/recoup/gateway",
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const apiLogGroup = new logs.LogGroup(this, "RecoupApiLogGroup", {
      logGroupName: "/recoup/api",
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ── IAM Roles ─────────────────────────────────────────────────────────────
    // RecoupRuntimeRole — used by Amazon Bedrock AgentCore Harness/Runtime
    // Trust principal is bedrock-agentcore.amazonaws.com (new service) with
    // confused-deputy conditions to prevent cross-account abuse.
    this.runtimeRole = new iam.Role(this, "RecoupRuntimeRole", {
      roleName: "RecoupRuntimeRole",
      assumedBy: new iam.ServicePrincipal("bedrock-agentcore.amazonaws.com", {
        conditions: {
          StringEquals: { "aws:SourceAccount": this.account },
          ArnLike: {
            "aws:SourceArn": `arn:aws:bedrock-agentcore:${this.region}:${this.account}:*`,
          },
        },
      }),
      description: "AgentCore Harness/Runtime: invokes Bedrock, reads/writes Recoup DynamoDB/S3",
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonBedrockFullAccess"),
      ],
    });
    opportunitiesTable.grantReadWriteData(this.runtimeRole);
    approvalsTable.grantReadWriteData(this.runtimeRole);
    toolAuditsTable.grantReadWriteData(this.runtimeRole);
    outcomeMetadataTable.grantReadWriteData(this.runtimeRole);
    evidenceBucket.grantReadWrite(this.runtimeRole);
    slaCatalogBucket.grantRead(this.runtimeRole);
    evalFixturesBucket.grantRead(this.runtimeRole);
    evidenceKey.grantEncryptDecrypt(this.runtimeRole);
    runtimeLogGroup.grantWrite(this.runtimeRole);

    // Sprint 1: grant sts:AssumeRole so the runtime can obtain short-lived
    // credentials for customer accounts via RecoupReadOnlyRole /
    // RecoupRemediationRole (which are created by RecoupIamStack).
    // The exact role ARNs are added by RecoupIamStack; here we grant a
    // pattern-based allow so the infra stack doesn't need to import IAM stack.
    this.runtimeRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "AllowAssumeCustomerRolesPattern",
        effect: iam.Effect.ALLOW,
        actions: ["sts:AssumeRole"],
        resources: [
          `arn:aws:iam::*:role/RecoupReadOnlyRole`,
          `arn:aws:iam::*:role/RecoupRemediationRole`,
        ],
      })
    );

    // RecoupGatewayExecutionRole — used by AgentCore Gateway to invoke Lambda tools
    this.gatewayExecutionRole = new iam.Role(this, "RecoupGatewayExecutionRole", {
      roleName: "RecoupGatewayExecutionRole",
      assumedBy: new iam.ServicePrincipal("bedrock-agentcore.amazonaws.com", {
        conditions: {
          StringEquals: { "aws:SourceAccount": this.account },
          ArnLike: {
            "aws:SourceArn": `arn:aws:bedrock-agentcore:${this.region}:${this.account}:*`,
          },
        },
      }),
      description: "AgentCore Gateway: invokes Lambda tool targets, emits logs/traces",
    });
    this.gatewayExecutionRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "InvokeLambdaTools",
        actions: ["lambda:InvokeFunction"],
        resources: [`arn:aws:lambda:${this.region}:${this.account}:function:recoup-*`],
      })
    );
    gatewayLogGroup.grantWrite(this.gatewayExecutionRole);

    // RecoupReadConnectorRole — read-only AWS data access for tools
    this.readConnectorRole = new iam.Role(this, "RecoupReadConnectorRole", {
      roleName: "RecoupReadConnectorRole",
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      description: "Read-only: CloudWatch, Health, Cost Explorer, CloudTrail; no mutations",
    });
    this.readConnectorRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "RecoupReadAccess",
        actions: [
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:GetMetricData",
          "cloudwatch:DescribeAlarms",
          "logs:FilterLogEvents",
          "logs:GetLogEvents",
          "health:DescribeEvents",
          "health:DescribeEventDetails",
          "health:DescribeAffectedEntities",
          "ce:GetCostAndUsage",
          "ce:GetCostForecast",
          "ce:GetAnomalies",
          "ce:GetRecommendations",
          "cloudtrail:LookupEvents",
          "ec2:DescribeInstances",
          "support:DescribeCases",
        ],
        resources: ["*"],
      })
    );
    this.readConnectorRole.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaBasicExecutionRole")
    );

    // ── Stack outputs ─────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, "OpportunitiesTableName", { value: opportunitiesTable.tableName });
    new cdk.CfnOutput(this, "ApprovalsTableName", { value: approvalsTable.tableName });
    new cdk.CfnOutput(this, "ToolAuditsTableName", { value: toolAuditsTable.tableName });
    new cdk.CfnOutput(this, "EvidenceBucketName", { value: evidenceBucket.bucketName });
    new cdk.CfnOutput(this, "SLACatalogBucketName", { value: slaCatalogBucket.bucketName });
    new cdk.CfnOutput(this, "EvalFixturesBucketName", { value: evalFixturesBucket.bucketName });
    new cdk.CfnOutput(this, "EvidenceKMSKeyArn", { value: evidenceKey.keyArn });
    new cdk.CfnOutput(this, "RecoveryEventsQueueUrl", { value: recoveryEventsQueue.queueUrl });
    new cdk.CfnOutput(this, "RuntimeRoleArn", { value: this.runtimeRole.roleArn });
    new cdk.CfnOutput(this, "GatewayExecutionRoleArn", { value: this.gatewayExecutionRole.roleArn });
    new cdk.CfnOutput(this, "ReadConnectorRoleArn", { value: this.readConnectorRole.roleArn });
    new cdk.CfnOutput(this, "RuntimeLogGroup", { value: runtimeLogGroup.logGroupName });
    new cdk.CfnOutput(this, "GatewayLogGroup", { value: gatewayLogGroup.logGroupName });
    new cdk.CfnOutput(this, "ApiLogGroup", { value: apiLogGroup.logGroupName });
  }
}
