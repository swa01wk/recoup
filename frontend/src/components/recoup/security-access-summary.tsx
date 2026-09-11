"use client";

import { TechnicalDetails } from "@/components/recoup/technical-details";

const ACCESS_CHECKS = [
  "STS AssumeRole",
  "Temporary credentials",
  "DenyAllWrites",
  "No resource changes without approval",
] as const;

const AWS_APIS = [
  "EC2 — ec2:Describe* (instances, volumes, snapshots, IPs)",
  "CloudWatch — GetMetricStatistics, GetMetricData, ListMetrics, DescribeAlarms",
  "CloudWatch Logs — DescribeLogGroups, DescribeLogStreams, FilterLogEvents",
  "Cost Explorer — GetCostAndUsage, GetReservationUtilization, GetAnomalies",
  "CloudTrail — LookupEvents, DescribeTrails",
  "RDS — rds:Describe*, ListTagsForResource",
  "Lambda — lambda:List*, GetFunctionConfiguration",
  "Elastic Load Balancing — elasticloadbalancing:Describe*",
  "S3 — ListAllMyBuckets, GetBucketTagging, GetLifecycleConfiguration",
  "Resource Tagging — tag:GetResources, GetTagKeys, GetTagValues",
];

interface SecurityAccessSummaryProps {
  consented: boolean;
  onConsent: (value: boolean) => void;
}

export function SecurityAccessSummary({ consented, onConsent }: SecurityAccessSummaryProps) {
  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/30 p-5 space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-blue-400">🔒</span>
        <h3 className="text-sm font-semibold text-slate-200">Security & Access Summary</h3>
      </div>

      <div className="rounded-lg border border-emerald-700/30 bg-emerald-950/10 px-4 py-3 space-y-2">
        <p className="text-xs font-semibold text-emerald-300 uppercase tracking-wide">
          Read-only access
        </p>
        <ul className="space-y-1.5">
          {ACCESS_CHECKS.map((check) => (
            <li key={check} className="flex items-center gap-2 text-sm text-slate-300">
              <span className="text-emerald-500">✓</span>
              {check}
            </li>
          ))}
        </ul>
      </div>

      <TechnicalDetails title="View access details">
        <div className="space-y-3 font-sans">
          <p className="text-xs text-slate-400 leading-relaxed">
            Recoup uses <code className="text-slate-300">sts:AssumeRole</code> to obtain temporary
            credentials that expire in 1 hour. Masked finding summaries and estimated savings are
            stored; raw account IDs and ARNs are redacted. Data retained 90 days.
          </p>
          <p className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">
            AWS APIs called
          </p>
          <ul className="space-y-1">
            {AWS_APIS.map((a) => (
              <li key={a} className="flex items-start gap-2 text-[11px] text-slate-400">
                <span className="text-emerald-500 shrink-0">✓</span>
                {a}
              </li>
            ))}
          </ul>
        </div>
      </TechnicalDetails>

      <label className="flex items-start gap-3 cursor-pointer pt-2 border-t border-slate-700/40">
        <input
          type="checkbox"
          checked={consented}
          onChange={(e) => onConsent(e.target.checked)}
          className="w-4 h-4 mt-0.5 rounded border-slate-600 accent-blue-500 shrink-0"
        />
        <span className="text-sm text-slate-300 leading-relaxed">
          I understand Recoup will make read-only API calls to my AWS account.
          No resources will be created, modified, or deleted without my explicit approval.
        </span>
      </label>
    </div>
  );
}
