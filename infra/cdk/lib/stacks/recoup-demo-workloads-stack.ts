/**
 * Phase 6f — RecoupDemoWorkloadsStack
 *
 * Deploys 8 controlled waste scenarios for the Recoup hackathon demo.
 * All resources are tagged so that Recoup scanners can identify them via
 * RecoupReadOnlyRole (Phase 6e) and display them in the Account Scanner UI.
 *
 * Scenario map:
 *  1. oversized-ec2      — t3.medium with near-zero CPU (inject via script)
 *  2. unattached-ebs     — gp3 100 GiB volume, no instance attached
 *  3. gp2-migration      — gp2 50 GiB volume (cheaper to run as gp3)
 *  4. idle-eip           — Elastic IP allocated but not associated
 *  5. idle-rds           — db.t3.micro MySQL with zero connections
 *  6. s3-no-lifecycle    — S3 bucket with no lifecycle policy
 *  7. oversized-lambda   — 1024 MB function with near-zero invocations
 *  8. stale-snapshot     — created via scripts/create_stale_snapshot.py
 *
 * Budget constraint: EC2 + RDS are the two largest cost drivers (~$45/mo).
 * Stop both between demo sessions to stay within the $30–$50 target spend.
 *
 * Destroy: cdk destroy RecoupDemoWorkloadsStack
 */

import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as rds from "aws-cdk-lib/aws-rds";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as lambda_ from "aws-cdk-lib/aws-lambda";
import { Construct } from "constructs";

const DEMO_TAGS: Record<string, string> = {
  Project: "Recoup",
  Environment: "hackathon-demo",
  RecoupDemo: "true",
  RecoupLayer: "demo-scanner-target",
  ManagedBy: "CDK",
};

/** Apply standard demo tags to any CDK construct. */
function applyDemoTags(scope: Construct, scenarioTag: string): void {
  for (const [k, v] of Object.entries(DEMO_TAGS)) {
    cdk.Tags.of(scope).add(k, v);
  }
  cdk.Tags.of(scope).add("RecoupScenario", scenarioTag);
}

export interface RecoupDemoWorkloadsStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
}

export class RecoupDemoWorkloadsStack extends cdk.Stack {
  /** The oversized EC2 instance — stop between sessions to save ~$30/month */
  public readonly oversizedInstance: ec2.Instance;
  /** The idle RDS instance — stop between sessions to save ~$15/month */
  public readonly idleRdsInstance: rds.DatabaseInstance;

  constructor(
    scope: Construct,
    id: string,
    props: RecoupDemoWorkloadsStackProps
  ) {
    super(scope, id, props);

    // ── Security group shared by demo EC2 ──────────────────────────────────
    const demoSg = new ec2.SecurityGroup(this, "DemoWorkloadSG", {
      vpc: props.vpc,
      description: "Phase 6f demo workloads - no inbound traffic required",
      allowAllOutbound: false,
    });

    // ══ Scenario 1 — Oversized EC2 (t3.medium, CPU < 5%) ══════════════════
    this.oversizedInstance = new ec2.Instance(this, "OversizedEC2", {
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T3,
        ec2.InstanceSize.MEDIUM
      ),
      machineImage: ec2.MachineImage.latestAmazonLinux2023(),
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      securityGroup: demoSg,
    });
    applyDemoTags(this.oversizedInstance, "oversized-ec2");
    // Extra tag for human readability
    cdk.Tags.of(this.oversizedInstance).add("Name", "recoup-demo-oversized-ec2");

    new cdk.CfnOutput(this, "OversizedEC2InstanceId", {
      value: this.oversizedInstance.instanceId,
      description: "Scenario 1 — Oversized EC2 (RecoupScenario=oversized-ec2)",
      exportName: "RecoupDemoOversizedEC2Id",
    });

    // ══ Scenario 2 — Unattached EBS (gp3, 100 GiB) ═══════════════════════
    const unattachedVol = new ec2.Volume(this, "UnattachedEBS", {
      availabilityZone: `${this.region}a`,
      size: cdk.Size.gibibytes(100),
      volumeType: ec2.EbsDeviceVolumeType.GP3,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      encrypted: false,
    });
    applyDemoTags(unattachedVol, "unattached-ebs");
    cdk.Tags.of(unattachedVol).add("Name", "recoup-demo-unattached-ebs");

    new cdk.CfnOutput(this, "UnattachedEBSVolumeId", {
      value: unattachedVol.volumeId,
      description: "Scenario 2 — Unattached EBS gp3 100 GiB (RecoupScenario=unattached-ebs)",
      exportName: "RecoupDemoUnattachedEBSId",
    });

    // ══ Scenario 3 — gp2 Migration Candidate (gp2, 50 GiB) ══════════════
    const gp2Vol = new ec2.Volume(this, "GP2MigrationVolume", {
      availabilityZone: `${this.region}a`,
      size: cdk.Size.gibibytes(50),
      volumeType: ec2.EbsDeviceVolumeType.GP2,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      encrypted: false,
    });
    applyDemoTags(gp2Vol, "gp2-migration");
    cdk.Tags.of(gp2Vol).add("Name", "recoup-demo-gp2-migration");

    new cdk.CfnOutput(this, "GP2VolumeId", {
      value: gp2Vol.volumeId,
      description: "Scenario 3 — gp2 migration candidate 50 GiB (RecoupScenario=gp2-migration)",
      exportName: "RecoupDemoGP2VolumeId",
    });

    // ══ Scenario 4 — Idle EIP (allocated, not associated) ════════════════
    const idleEip = new ec2.CfnEIP(this, "IdleEIP", {
      domain: "vpc",
      tags: [
        ...Object.entries(DEMO_TAGS).map(([k, v]) => ({ key: k, value: v })),
        { key: "RecoupScenario", value: "idle-eip" },
        { key: "Name", value: "recoup-demo-idle-eip" },
      ],
    });

    new cdk.CfnOutput(this, "IdleEIPAllocationId", {
      value: idleEip.attrAllocationId,
      description: "Scenario 4 — Idle EIP (RecoupScenario=idle-eip)",
      exportName: "RecoupDemoIdleEIPAllocationId",
    });

    // ══ Scenario 5 — Idle RDS (db.t3.micro MySQL, 0 connections) ═════════
    // Use smallest practical config; deletion protection off for easy teardown
    const rdsSubnetGroup = new rds.SubnetGroup(this, "DemoRDSSubnetGroup", {
      description: "Phase 6f demo RDS subnet group",
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.idleRdsInstance = new rds.DatabaseInstance(this, "IdleRDS", {
      engine: rds.DatabaseInstanceEngine.mysql({
        version: rds.MysqlEngineVersion.VER_8_0_42,
      }),
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T3,
        ec2.InstanceSize.MICRO
      ),
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      subnetGroup: rdsSubnetGroup,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      deletionProtection: false,
      backupRetention: cdk.Duration.days(0),
      multiAz: false,
      publiclyAccessible: false,
      // Smallest storage — cost driven by instance hours, not storage
      allocatedStorage: 20,
      storageType: rds.StorageType.GP2,
      databaseName: "recoupdemo",
    });
    applyDemoTags(this.idleRdsInstance, "idle-rds");
    cdk.Tags.of(this.idleRdsInstance).add("Name", "recoup-demo-idle-rds");

    new cdk.CfnOutput(this, "IdleRDSInstanceIdentifier", {
      value: this.idleRdsInstance.instanceIdentifier,
      description: "Scenario 5 — Idle RDS db.t3.micro MySQL (RecoupScenario=idle-rds)",
      exportName: "RecoupDemoIdleRDSId",
    });

    // ══ Scenario 6 — S3 Bucket with No Lifecycle Policy ══════════════════
    const noLifecycleBucket = new s3.Bucket(this, "NoLifecycleBucket", {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: false,
      // Intentionally no lifecycleRules — this is the waste signal
    });
    applyDemoTags(noLifecycleBucket, "s3-no-lifecycle");
    cdk.Tags.of(noLifecycleBucket).add("Name", "recoup-demo-s3-no-lifecycle");

    new cdk.CfnOutput(this, "NoLifecycleBucketName", {
      value: noLifecycleBucket.bucketName,
      description: "Scenario 6 — S3 bucket without lifecycle policy (RecoupScenario=s3-no-lifecycle)",
      exportName: "RecoupDemoNoLifecycleBucket",
    });

    // ══ Scenario 7 — Oversized Lambda (1024 MB, near-zero invocations) ════
    const oversizedLambda = new lambda_.Function(this, "OversizedLambda", {
      runtime: lambda_.Runtime.PYTHON_3_12,
      handler: "index.handler",
      code: lambda_.Code.fromInline(
        "def handler(event, context):\n    return {'statusCode': 200, 'body': 'recoup-demo'}\n"
      ),
      memorySize: 1024, // deliberately oversized — waste signal for scanner
      timeout: cdk.Duration.seconds(3),
      description: "Recoup Phase 6f demo — oversized Lambda memory (1024 MB vs needed ~128 MB)",
    });
    applyDemoTags(oversizedLambda, "oversized-lambda");
    cdk.Tags.of(oversizedLambda).add("Name", "recoup-demo-oversized-lambda");

    new cdk.CfnOutput(this, "OversizedLambdaName", {
      value: oversizedLambda.functionName,
      description: "Scenario 7 — Oversized Lambda 1024 MB (RecoupScenario=oversized-lambda)",
      exportName: "RecoupDemoOversizedLambda",
    });

    // ══ Scenario 8 — Stale EBS Snapshot ══════════════════════════════════
    // CDK cannot create standalone EBS snapshots natively.
    // Run scripts/create_stale_snapshot.py after stack deploy to create
    // a snapshot of the unattached-ebs volume and tag it RecoupScenario=stale-snapshot.
    new cdk.CfnOutput(this, "StaleSnapshotNote", {
      value: "Run scripts/create_stale_snapshot.py to create scenario 8",
      description: "Scenario 8 — Stale EBS snapshot (created via script post-deploy)",
    });

    // ── Stack-level summary output ─────────────────────────────────────────
    new cdk.CfnOutput(this, "DemoWorkloadsReadme", {
      value: [
        "RecoupDemoWorkloadsStack deployed.",
        "Next steps:",
        "1. Run scripts/inject_demo_activity.py to seed CloudWatch metrics",
        "2. Run scripts/create_stale_snapshot.py for scenario 8",
        "3. Wait 15-30 min for metrics to appear in CloudWatch",
        "4. Open /scan in the Recoup UI and click 'Demo Scan'",
      ].join(" | "),
      description: "Phase 6f post-deploy instructions",
    });
  }
}
