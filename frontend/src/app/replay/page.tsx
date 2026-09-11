"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmt } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

/**
 * SLA Replay page — runs the canonical API Gateway SLA replay scenario
 * and surfaces the credit calculation result.
 */
export default function SLAReplayPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<import("@/lib/api").ReplayResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runReplay = async () => {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await api.replay.run();
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Replay failed");
    } finally {
      setLoading(false);
    }
  };

  const creditStr = result?.potential_credit ?? null;

  return (
    <div className="flex flex-col min-h-screen p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1 flex-wrap">
            <h1 className="text-xl font-bold text-slate-100">SLA Replay</h1>
            <Badge variant="default">Verified Deterministic</Badge>
          </div>
          <p className="text-sm text-slate-400 mt-0.5">
            Replay the canonical Amazon API Gateway SLA incident scenario and
            calculate the credit eligible for recovery.
          </p>
        </div>
        <Link href="/">
          <Button variant="secondary" size="sm">
            ← Dashboard
          </Button>
        </Link>
      </div>

      {/* Scenario card */}
      <Card>
        <CardHeader>
          <CardTitle>Canonical SLA Scenario</CardTitle>
          <span className="text-xs text-slate-500">
            API Gateway · us-east-1 · August 2026 · 20/20 fixture replay
          </span>
        </CardHeader>
        <CardContent className="space-y-4 py-4">
          <p className="text-sm text-slate-400">
            Replays real CloudTrail / CloudWatch data from the API Gateway
            outage against the SLA contract, runs the full 11-node Recoup
            pipeline deterministically, and produces a credit estimate that can
            be submitted to AWS Support.
          </p>

          {error && (
            <div className="rounded border border-red-700/40 bg-red-900/20 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}

          <Button
            variant="primary"
            size="md"
            loading={loading}
            onClick={() => void runReplay()}
          >
            {loading ? "Analyzing…" : "▶ Run SLA Replay"}
          </Button>
        </CardContent>
      </Card>

      {/* Result card */}
      {result && (
        <Card className="border-emerald-700/40 bg-emerald-900/10">
          <CardHeader>
            <CardTitle>Replay Result</CardTitle>
            <span className="text-xs text-slate-500 font-mono">
              {result.opportunity_id}
            </span>
          </CardHeader>
          <CardContent className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4 text-sm lg:grid-cols-4">
              {creditStr && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide">
                    Potential Credit
                  </p>
                  <p className="font-mono font-bold text-emerald-400 text-lg">
                    {fmt(creditStr)}
                  </p>
                </div>
              )}
              {result.monthly_uptime_pct != null && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide">
                    Monthly Uptime
                  </p>
                  <p className="font-mono text-slate-200">{result.monthly_uptime_pct}%</p>
                </div>
              )}
              {result.tier_pct != null && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide">
                    SLA Tier Credit %
                  </p>
                  <p className="font-mono text-slate-200">{result.tier_pct}%</p>
                </div>
              )}
              {result.policy_decision && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide">
                    Policy Decision
                  </p>
                  <Badge
                    variant={
                      result.policy_decision === "REQUIRE_APPROVAL"
                        ? "pending"
                        : result.policy_decision === "ALLOW"
                        ? "success"
                        : "default"
                    }
                  >
                    {result.policy_decision}
                  </Badge>
                </div>
              )}
            </div>

            {result.calculation_trace && result.calculation_trace.length > 0 && (
              <div className="rounded border border-slate-700/40 bg-slate-900/40 px-3 py-3 space-y-1">
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">
                  Calculation Trace
                </p>
                {result.calculation_trace.map((line, i) => (
                  <p key={i} className="text-xs font-mono text-slate-400">
                    {line}
                  </p>
                ))}
              </div>
            )}

            <div className="flex items-center gap-2 flex-wrap">
              <Link href={`/opportunities/${result.opportunity_id}`}>
                <Button variant="secondary" size="sm">
                  View Opportunity →
                </Button>
              </Link>
              <Link href="/approvals">
                <Button variant="secondary" size="sm">
                  Decision Inbox →
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
