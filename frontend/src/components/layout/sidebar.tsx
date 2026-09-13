"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { SCAN_COUNT_KEY, clearLocalScanData } from "@/lib/recovery-storage";
import { api } from "@/lib/api";

const NAV = [
  { href: "/opportunities", label: "Opportunities", icon: "◈" },
  { href: "/scan", label: "Account Scanner", icon: "⊕" },
  { href: "/recovery", label: "Recovery Ledger", icon: "◉" },
];

export function Sidebar() {
  const path = usePathname();
  const [scanFindingCount, setScanFindingCount] = useState<number | null>(null);
  const [resetting, setResetting] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);

  const handleReset = async () => {
    if (!confirm("Reset your demo data?\n\nClears your scan, opportunities, and approvals only — other visitors are unaffected.")) return;
    setResetting(true);
    setResetMsg(null);
    try {
      await api.scan.adminReset(true); // clear_scan_cache=true
      // Clear ALL scan-related keys from localStorage so the UI starts fresh
      clearLocalScanData();
      setScanFindingCount(null);
      setResetMsg("✓ Reset");
      setTimeout(() => setResetMsg(null), 3000);
      // Reload the page so all React state is fresh
      window.location.reload();
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      const detail = (() => {
        try {
          const json = raw.match(/\{[\s\S]*\}/)?.[0];
          if (json) return (JSON.parse(json) as { detail?: string }).detail;
        } catch {
          /* ignore */
        }
        return null;
      })();
      if (raw.startsWith("403") || detail?.includes("disabled")) {
        setResetMsg("Reset disabled — redeploy API with RECOUP_ENABLE_ADMIN_RESET");
      } else {
        setResetMsg("Error — is backend running?");
      }
      setTimeout(() => setResetMsg(null), 5000);
    } finally {
      setResetting(false);
    }
  };

  useEffect(() => {
    const stored = localStorage.getItem(SCAN_COUNT_KEY);
    if (stored !== null) setScanFindingCount(Number(stored));

    const handler = (e: Event) => {
      const count = (e as CustomEvent<number>).detail;
      setScanFindingCount(count);
      localStorage.setItem(SCAN_COUNT_KEY, String(count));
    };
    window.addEventListener("recoup:scanComplete", handler);
    return () => window.removeEventListener("recoup:scanComplete", handler);
  }, []);

  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-56 flex-col border-r border-slate-700/60 bg-slate-900">
      <div className="flex h-14 items-center border-b border-slate-700/60 px-4 gap-2">
        <span className="text-blue-400 text-lg">⬡</span>
        <div>
          <span className="font-bold text-slate-100 text-sm tracking-tight block">
            Recoup
          </span>
          <span className="text-[10px] text-slate-500">Cloud Spend Recovery</span>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-2 py-3">
        {NAV.map(({ href, label, icon }) => {
          const active = path.startsWith(href);
          const isScan = href === "/scan";

          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-blue-600/20 text-blue-300 border border-blue-700/40"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-transparent"
              )}
            >
              <span className="text-[10px] w-3 text-center opacity-70">{icon}</span>
              <span className="flex-1">{label}</span>
              {isScan && scanFindingCount !== null && scanFindingCount > 0 && (
                <span className="inline-flex items-center rounded-full bg-emerald-900/50 border border-emerald-700/40 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-300 tabular-nums">
                  {scanFindingCount}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-700/60 px-3 py-3 space-y-3">
        <div className="px-1">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-slate-400">Backend connected</span>
          </div>
          <p className="mt-1 text-[10px] text-slate-600">
            {process.env.NEXT_PUBLIC_API_URL?.replace(/^https?:\/\//, "") ?? "localhost:8000"}
          </p>
        </div>

        {/* Reset Demo Data — clears all in-memory state + scan cache */}
        <div className="px-1">
          <button
            onClick={() => void handleReset()}
            disabled={resetting}
            className={cn(
              "w-full flex items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 text-[10px] transition-colors",
              resetting
                ? "border-slate-700 text-slate-600 cursor-not-allowed"
                : "border-red-900/50 text-red-400 hover:border-red-700/60 hover:bg-red-950/30"
            )}
            title="Clear all demo data: opportunities, approvals, scan cache"
          >
            {resetting ? (
              <span className="inline-block h-2.5 w-2.5 animate-spin rounded-full border border-slate-600 border-t-slate-400" />
            ) : (
              <span>↺</span>
            )}
            {resetMsg ?? (resetting ? "Resetting…" : "Reset Demo Data")}
          </button>
        </div>
      </div>
    </aside>
  );
}
