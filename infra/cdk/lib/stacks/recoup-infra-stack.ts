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
import * as sns from "aws-cdk-lib/aws-sns";
import { Construct } from "constructs";

export class RecoupInfraStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;

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
      ],
    });

    const slaCatalogBucket = new s3.Bucket(this, "RecoupSLACatalogBucket", {
      bucketName: `recoup-sla-catalog-${this.account}-${this.region}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const evalFixturesBucket = new s3.Bucket(this, "RecoupEvalFixturesBucket", {
      bucketName: `recoup-eval-fixtures-${this.account}-${this.region}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
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
      timeToLiveAttribute: "expires_at",
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const toolAuditsTable = new dynamodb.Table(this, "RecoupToolAuditsTable", {
      tableName: "recoup-tool-audits",
      partitionKey: { name: "trace_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const outcomeMetadataTable = new dynamodb.Table(this, "RecoupOutcomeMetadataTable", {
      tableName: "recoup-outcome-metadata",
      partitionKey: { name: "pk", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ── SQS ─────────────────────────────────────────────────────────────────
    const dlq = new sqs.Queue(this, "RecoupRecoveryEventsDLQ", {
      queueName: "recoup-recovery-events-dlq",
      retentionPeriod: cdk.Duration.days(14),
    });

    const recoveryEventsQueue = new sqs.Queue(this, "RecoupRecoveryEventsQueue", {
      queueName: "recoup-recovery-events",
      visibilityTimeout: cdk.Duration.seconds(300),
      retentionPeriod: cdk.Duration.days(14),
      deadLetterQueue: { queue: dlq, maxReceiveCount: 3 },
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
      maxAzs: 1,
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

    // ── Stack outputs ─────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, "OpportunitiesTableName", { value: opportunitiesTable.tableName });
    new cdk.CfnOutput(this, "ApprovalsTableName", { value: approvalsTable.tableName });
    new cdk.CfnOutput(this, "ToolAuditsTableName", { value: toolAuditsTable.tableName });
    new cdk.CfnOutput(this, "EvidenceBucketName", { value: evidenceBucket.bucketName });
    new cdk.CfnOutput(this, "SLACatalogBucketName", { value: slaCatalogBucket.bucketName });
    new cdk.CfnOutput(this, "EvalFixturesBucketName", { value: evalFixturesBucket.bucketName });
    new cdk.CfnOutput(this, "EvidenceKMSKeyArn", { value: evidenceKey.keyArn });
    new cdk.CfnOutput(this, "RecoveryEventsQueueUrl", { value: recoveryEventsQueue.queueUrl });
  }
}
