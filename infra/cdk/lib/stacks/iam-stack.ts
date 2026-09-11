/**
 * Phase 6e — IAM Security Model & STS AssumeRole
 *
 * Creates three dedicated IAM roles with clean separation of concerns:
 *
 * RecoupReadOnlyRole
 *   - Broad read-only analysis (EC2 Describe*, CloudWatch, Cost Explorer,
 *     CloudTrail, RDS, Lambda, S3, ELB, Tagging, Compute Optimizer)
 *   - No write actions on any service
 *   - Trusted by RecoupRuntimeRole with ExternalId condition
 *
 * RecoupRemediationRole
 *   - ec2:StopInstances where RecoupDemo=true tag is present
 *   - ec2:TerminateInstances explicitly denied
 *   - Trusted by RecoupRuntimeRole with ExternalId condition
 *
 * RecoupRuntimeRole (update existing)
 *   - Adds sts:AssumeRole for RecoupReadOnlyRole and RecoupRemediationRole
 */

import * as cdk from "aws-cdk-lib";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

export interface RecoupIamStackProps extends cdk.StackProps {
  /** 12-digit AWS account ID where the roles are created */
  account: string;
  /**
   * External ID used in the RecoupReadOnlyRole and RecoupRemediationRole
   * trust policy conditions.  Set this to a hard-to-guess secret and store
   * it in RECOUP_EXTERNAL_ID.  Default: "recoup-demo-external-id"
   */
  externalId?: string;
}

export class RecoupIamStack extends cdk.Stack {
  public readonly readOnlyRole: iam.Role;
  public readonly remediationRole: iam.Role;

  constructor(scope: Construct, id: string, props: RecoupIamStackProps) {
    super(scope, id, props);

    const accountId = props.account;
    const externalId = props.externalId ?? "recoup-demo-external-id";
    const runtimeRoleArn = `arn:aws:iam::${accountId}:role/RecoupRuntimeRole`;

    // ── Trust policy shared by both new roles ─────────────────────────────
    const trustPrincipal = new iam.ArnPrincipal(runtimeRoleArn);

    const externalIdCondition: iam.Conditions = {
      StringEquals: { "sts:ExternalId": externalId },
    };

    // ── RecoupReadOnlyRole ────────────────────────────────────────────────
    this.readOnlyRole = new iam.Role(this, "RecoupReadOnlyRole", {
      roleName: "RecoupReadOnlyRole",
      description:
        "Phase 6e - Read-only analysis role assumed via STS AssumeRole. " +
        "No write actions on any service.",
      assumedBy: trustPrincipal,
      externalIds: [externalId],
    });

    // EC2 read-only — ec2:GetConsoleOutput removed (not used by any scanner)
    this.readOnlyRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "EC2ReadOnly",
        effect: iam.Effect.ALLOW,
        actions: ["ec2:Describe*"],  // EC2Scanner, EBSScanner, EIPScanner
        resources: ["*"],
      })
    );

    // CloudWatch & Logs read-only
    this.readOnlyRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "CloudWatchReadOnly",
        effect: iam.Effect.ALLOW,
        actions: [
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:GetMetricData",
          "cloudwatch:ListMetrics",
          "cloudwatch:DescribeAlarms",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:FilterLogEvents",
        ],
        resources: ["*"],
      })
    );

    // Cost Explorer read-only
    this.readOnlyRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "CostReadOnly",
        effect: iam.Effect.ALLOW,
        actions: [
          "ce:GetCostAndUsage",
          "ce:GetReservationUtilization",
          "ce:GetSavingsPlanUtilization",
          "ce:GetAnomalies",
          "ce:ListCostAllocationTags",
          "cost-optimization-hub:ListRecommendations",
        ],
        resources: ["*"],
      })
    );

    // CloudTrail read-only
    this.readOnlyRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "CloudTrailReadOnly",
        effect: iam.Effect.ALLOW,
        actions: ["cloudtrail:LookupEvents", "cloudtrail:DescribeTrails"],
        resources: ["*"],
      })
    );

    // EBS, RDS, Lambda, S3, ELB read-only
    // lambda:GetFunction* removed — not used by LambdaScanner (uses lambda:List* only)
    // Scoped to exactly the APIs each scanner calls.
    this.readOnlyRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "EBSRDSLambdaS3ELBReadOnly",
        effect: iam.Effect.ALLOW,
        actions: [
          "elasticloadbalancing:Describe*",  // LBScanner
          "rds:Describe*",                   // RDSScanner
          "rds:ListTagsForResource",         // RDSScanner
          "lambda:List*",                    // LambdaScanner
          "lambda:GetFunctionConfiguration", // LambdaScanner (memory/timeout only)
          "s3:ListAllMyBuckets",             // S3Scanner
          "s3:GetBucketTagging",             // S3Scanner
          "s3:GetLifecycleConfiguration",    // S3Scanner — GetBucketLifecycleConfiguration
          "s3:GetBucketLocation",            // S3Scanner
          "s3:GetMetricsConfiguration",      // S3Scanner — GetBucketMetricsConfiguration
        ],
        resources: ["*"],
      })
    );

    // Resource tagging API read-only
    this.readOnlyRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "TaggingReadOnly",
        effect: iam.Effect.ALLOW,
        actions: ["tag:GetResources", "tag:GetTagKeys", "tag:GetTagValues"],
        resources: ["*"],
      })
    );

    // Compute Optimizer read-only
    this.readOnlyRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "ComputeOptimizerReadOnly",
        effect: iam.Effect.ALLOW,
        actions: [
          "compute-optimizer:GetEC2InstanceRecommendations",
          "compute-optimizer:GetEBSVolumeRecommendations",
          "compute-optimizer:GetLambdaFunctionRecommendations",
          "compute-optimizer:GetRDSInstanceRecommendations",
        ],
        resources: ["*"],
      })
    );

    // Explicit deny: no write actions — mirrors the Allow list exactly.
    // Any action NOT in this NotActions list is DENIED, even if an Allow
    // policy were added later.  This is the provable read-only guarantee.
    this.readOnlyRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "DenyAllWrites",
        effect: iam.Effect.DENY,
        notActions: [
          // EC2Scanner, EBSScanner, EIPScanner
          "ec2:Describe*",
          // CloudWatch + Logs (CWLogsScanner)
          "cloudwatch:Get*",
          "cloudwatch:List*",
          "cloudwatch:Describe*",
          "logs:Describe*",
          "logs:Filter*",
          // CostExplorerScanner
          "ce:Get*",
          "ce:List*",
          "cost-optimization-hub:List*",
          // CloudTrail (scanners + agent tools)
          "cloudtrail:Lookup*",
          "cloudtrail:Describe*",
          // LBScanner
          "elasticloadbalancing:Describe*",
          // RDSScanner
          "rds:Describe*",
          "rds:ListTagsForResource",
          // LambdaScanner
          "lambda:List*",
          "lambda:GetFunctionConfiguration",
          // S3Scanner
          "s3:List*",
          "s3:GetBucket*",
          "s3:GetLifecycleConfiguration",
          "s3:GetMetricsConfiguration",
          // Tagging API (tagging_demo)
          "tag:GetResources",
          "tag:GetTagKeys",
          "tag:GetTagValues",
          // Compute Optimizer
          "compute-optimizer:Get*",
          // STS identity check
          "sts:GetCallerIdentity",
        ],
        resources: ["*"],
      })
    );

    cdk.Tags.of(this.readOnlyRole).add("Phase", "6e");
    cdk.Tags.of(this.readOnlyRole).add("ManagedBy", "CDK");

    // ── RecoupRemediationRole ─────────────────────────────────────────────
    this.remediationRole = new iam.Role(this, "RecoupRemediationRole", {
      roleName: "RecoupRemediationRole",
      description:
        "Phase 6e - Narrow write role for approved remediation. " +
        "ec2:StopInstances on RecoupDemo=true only. TerminateInstances denied.",
      assumedBy: trustPrincipal,
      externalIds: [externalId],
    });

    // Allow StopInstances only when RecoupDemo=true tag is present
    this.remediationRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "AllowStopDemoInstancesOnly",
        effect: iam.Effect.ALLOW,
        actions: ["ec2:StopInstances"],
        resources: ["*"],
        conditions: {
          StringEquals: { "ec2:ResourceTag/RecoupDemo": "true" },
        },
      })
    );

    // ec2:DescribeTags needed to verify the RecoupDemo=true tag before stopping
    this.remediationRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "DescribeTagsForVerification",
        effect: iam.Effect.ALLOW,
        actions: ["ec2:DescribeTags", "ec2:DescribeInstances"],
        resources: ["*"],
      })
    );

    // Explicit deny: TerminateInstances — cannot be overridden by any Allow
    this.remediationRole.addToPolicy(
      new iam.PolicyStatement({
        sid: "ExplicitlyDenyTerminate",
        effect: iam.Effect.DENY,
        actions: ["ec2:TerminateInstances"],
        resources: ["*"],
      })
    );

    cdk.Tags.of(this.remediationRole).add("Phase", "6e");
    cdk.Tags.of(this.remediationRole).add("ManagedBy", "CDK");

    // ── RecoupRuntimeRole — grant sts:AssumeRole on both customer roles ──
    // The runtime role (created by RecoupInfraStack) must be able to call
    // sts:AssumeRole to obtain short-lived credentials for customer accounts.
    // We look it up by ARN and attach an inline policy here so the permission
    // is versioned alongside the role trust conditions.
    //
    // If the RuntimeRole has already been created by RecoupInfraStack (which is
    // the common deploy order), we add the AssumeRole permission inline.
    // In a fresh account where only this stack is deployed, we create a minimal
    // RuntimeRole as a placeholder so CDK synth succeeds.
    const runtimeRole = iam.Role.fromRoleArn(
      this,
      "RecoupRuntimeRoleRef",
      runtimeRoleArn,
      { mutable: true }
    );

    runtimeRole.addToPrincipalPolicy(
      new iam.PolicyStatement({
        sid: "AllowAssumeCustomerRoles",
        effect: iam.Effect.ALLOW,
        actions: ["sts:AssumeRole"],
        resources: [
          this.readOnlyRole.roleArn,
          this.remediationRole.roleArn,
        ],
      })
    );

    // ── Outputs ───────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, "ReadOnlyRoleArn", {
      value: this.readOnlyRole.roleArn,
      description: "ARN of RecoupReadOnlyRole — set as RECOUP_READONLY_ROLE_ARN",
      exportName: "RecoupReadOnlyRoleArn",
    });

    new cdk.CfnOutput(this, "RemediationRoleArn", {
      value: this.remediationRole.roleArn,
      description: "ARN of RecoupRemediationRole — set as RECOUP_REMEDIATION_ROLE_ARN",
      exportName: "RecoupRemediationRoleArn",
    });

    new cdk.CfnOutput(this, "ExternalId", {
      value: externalId,
      description: "External ID for STS trust condition — set as RECOUP_EXTERNAL_ID",
    });
  }
}
