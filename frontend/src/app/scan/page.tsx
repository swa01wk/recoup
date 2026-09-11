"use client";

import { useRouter } from "next/navigation";
import { useState, useCallback } from "react";
import { api, type ScanRequest } from "@/lib/api";
import { saveLastScan } from "@/lib/recovery-storage";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { STSConnectedBadge } from "@/components/ui/badge";
import { SecurityAccessSummary } from "@/components/recoup/security-access-summary";
import { TechnicalDetails } from "@/components/recoup/technical-details";
import { cn } from "@/lib/utils";

const REGIONS = [
  "us-east-1", "us-east-2", "us-west-1", "us-west-2",
  "eu-west-1", "eu-west-2", "eu-central-1",
  "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
  "ca-central-1", "sa-east-1",
];

const DEFAULT_ROLE_ARN = process.env.NEXT_PUBLIC_RECOUP_READONLY_ROLE_ARN ?? "";

const CF_TEMPLATE_YAML = (externalId: string) => `AWSTemplateFormatVersion: "2010-09-09"
Description: "Recoup read-only role — cannot create, update, or delete any resource"
# ... (ExternalId: ${externalId})`;

function ConnectWizardInline({
  onConnected,
}: {
  onConnected: (externalId: string) => void;
}) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [loading, setLoading] = useState(false);
  const [externalId, setExternalId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stsStatus, setStsStatus] = useState<"idle" | "testing" | "ok" | "fail">("idle");
  const [testRoleArn, setTestRoleArn] = useState("");

  const handleGenerateId = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.scan.initConnection();
      setExternalId(res.external_id);
      setStep(2);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate External ID");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleCopy = (text: string) => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleTestSts = async () => {
    if (!externalId || !testRoleArn) return;
    setStsStatus("testing");
    try {
      await api.scan.preview({ role_arn: testRoleArn, external_id: externalId, region: "us-east-1" });
      setStsStatus("ok");
      setStep(3);
      onConnected(externalId);
    } catch {
      setStsStatus("fail");
    }
  };

  return (
    <div className="space-y-3 pt-2">
      <div className="flex items-center gap-2">
        {([1, 2, 3] as const).map((s) => (
          <span
            key={s}
            className={cn(
              "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold",
              step === s ? "bg-blue-500 text-white" : step > s ? "bg-emerald-600 text-white" : "bg-slate-700 text-slate-400"
            )}
          >
            {step > s ? "✓" : s}
          </span>
        ))}
        <span className="text-xs text-slate-500 ml-1">
          {step === 1 ? "Generate External ID" : step === 2 ? "Deploy IAM Role" : "Connected"}
        </span>
      </div>

      {step === 1 && (
        <div className="space-y-2">
          <p className="text-xs text-slate-400">
            Generate a unique External ID for your AWS role trust policy.
          </p>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <Button variant="secondary" size="sm" loading={loading} onClick={() => void handleGenerateId()}>
            Generate External ID
          </Button>
        </div>
      )}

      {step === 2 && externalId && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <code className="text-xs font-mono text-emerald-300 flex-1 break-all">{externalId}</code>
            <button
              onClick={() => handleCopy(externalId)}
              className="text-[10px] px-2 py-1 rounded border border-slate-700 text-slate-400 hover:text-slate-200"
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <input
            type="text"
            placeholder="Role ARN from CloudFormation output"
            value={testRoleArn}
            onChange={(e) => setTestRoleArn(e.target.value)}
            className="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-blue-500 focus:outline-none font-mono"
          />
          <Button variant="secondary" size="sm" loading={stsStatus === "testing"} onClick={() => void handleTestSts()} disabled={!testRoleArn}>
            Test Connection
          </Button>
          {stsStatus === "fail" && (
            <p className="text-xs text-red-400">Connection failed — verify role ARN and External ID.</p>
          )}
        </div>
      )}

      {step === 3 && (
        <p className="text-xs text-emerald-400">✓ Account connected — credentials pre-filled below</p>
      )}
    </div>
  );
}

export default function AccountScannerPage() {
  const router = useRouter();
  const [form, setForm] = useState<ScanRequest>({
    role_arn: DEFAULT_ROLE_ARN,
    external_id: "",
    region: "us-east-1",
    regions: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consented, setConsented] = useState(false);
  const [connected, setConnected] = useState(false);

  const hasCredentials = form.role_arn.trim().length > 0 && form.external_id.trim().length > 0;
  const connectionStatus = connected || hasCredentials ? "connected" : "disconnected";

  const handleScan = async (mode: "full" | "preview" | "demo") => {
    if (mode !== "demo") {
      if (!form.role_arn.trim()) { setError("Role ARN is required."); return; }
      if (!form.external_id.trim()) { setError("External ID is required."); return; }
    }
    setLoading(true);
    setError(null);
    try {
      const res =
        mode === "demo"
          ? await api.scan.demo()
          : mode === "preview"
          ? await api.scan.preview(form)
          : await api.scan.full(form);

      saveLastScan(res);
      window.dispatchEvent(new CustomEvent("recoup:scanComplete", { detail: res.findings.length }));
      router.push("/opportunities");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen p-6 space-y-8 max-w-3xl">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Account Scanner</h1>
        <p className="text-sm text-slate-400 mt-1">
          Connect your AWS account and scan for recoverable spend.
        </p>
      </div>

      {/* A. AWS Connection */}
      <Card>
        <CardHeader>
          <CardTitle>AWS Connection</CardTitle>
          {connectionStatus === "connected" ? (
            <STSConnectedBadge roleArn={form.role_arn || undefined} />
          ) : (
            <span className="text-xs text-slate-500">Not connected</span>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4">
            <div>
              <label className="text-[10px] text-slate-500 uppercase tracking-widest block mb-1.5">
                Role ARN
              </label>
              <input
                type="text"
                placeholder="arn:aws:iam::123456789012:role/RecoupReadOnlyRole"
                value={form.role_arn}
                onChange={(e) => setForm({ ...form, role_arn: e.target.value })}
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:border-blue-500 focus:outline-none font-mono"
                autoComplete="off"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] text-slate-500 uppercase tracking-widest block mb-1.5">
                  External ID
                </label>
                <input
                  type="password"
                  placeholder="••••••••••••••••"
                  value={form.external_id}
                  onChange={(e) => setForm({ ...form, external_id: e.target.value })}
                  className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:border-blue-500 focus:outline-none font-mono"
                  autoComplete="off"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-500 uppercase tracking-widest block mb-1.5">
                  Region
                </label>
                <select
                  value={form.region}
                  onChange={(e) => setForm({ ...form, region: e.target.value })}
                  className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 focus:border-blue-500 focus:outline-none"
                >
                  {REGIONS.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <TechnicalDetails title="New customer? Connect AWS account">
            <ConnectWizardInline
              onConnected={(eid) => {
                setForm((f) => ({ ...f, external_id: eid }));
                setConnected(true);
              }}
            />
          </TechnicalDetails>
        </CardContent>
      </Card>

      {/* B. Security & Access Summary */}
      <SecurityAccessSummary consented={consented} onConsent={setConsented} />

      {/* C. Primary CTA */}
      <div className="space-y-4">
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-900/20 p-4 text-sm text-red-300">
            <p className="font-medium">Could not connect</p>
            <p className="text-red-400 font-mono text-xs mt-1">{error}</p>
          </div>
        )}

        {!consented && (
          <p className="text-xs text-amber-400">Accept the access consent above before scanning.</p>
        )}

        {loading && (
          <div className="rounded-lg border border-blue-700/30 bg-blue-950/20 p-4">
            <div className="flex items-center gap-2 text-sm text-blue-300">
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
              Scanning your AWS account — this may take 20–30 seconds
            </div>
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <Button
            variant="primary"
            size="lg"
            loading={loading}
            onClick={() => void handleScan("full")}
            disabled={!consented}
            className="flex-1 sm:flex-none"
          >
            Scan AWS Account
          </Button>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" loading={loading} onClick={() => void handleScan("preview")} disabled={!consented}>
              Quick Preview
            </Button>
            <Button variant="ghost" size="sm" loading={loading} onClick={() => void handleScan("demo")} className="text-violet-400">
              Demo Scan
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
