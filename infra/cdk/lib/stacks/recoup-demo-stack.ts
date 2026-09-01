import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import { Construct } from "constructs";

interface RecoupDemoStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
}

export class RecoupDemoStack extends cdk.Stack {
  public readonly demoInstance: ec2.Instance;

  constructor(scope: Construct, id: string, props: RecoupDemoStackProps) {
    super(scope, id, props);

    const sg = new ec2.SecurityGroup(this, "RecoupDemoSG", {
      vpc: props.vpc,
      description: "Security group for Recoup demo EC2 instance",
      allowAllOutbound: false, // demo instance needs no outbound
    });

    this.demoInstance = new ec2.Instance(this, "RecoupDemoInstance", {
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
      machineImage: ec2.MachineImage.latestAmazonLinux2023(),
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      securityGroup: sg,
    });

    // Tags checked at runtime before any stop action
    cdk.Tags.of(this.demoInstance).add("RecoupDemo", "true");
    cdk.Tags.of(this.demoInstance).add("ManagedBy", "recoup");
    cdk.Tags.of(this.demoInstance).add("Purpose", "hackathon-demo-reversible");
    cdk.Tags.of(this.demoInstance).add("Environment", "sandbox");

    new cdk.CfnOutput(this, "DemoInstanceId", {
      value: this.demoInstance.instanceId,
      description: "Add this value to RECOUP_DEMO_INSTANCE_ALLOWLIST",
    });
  }
}
