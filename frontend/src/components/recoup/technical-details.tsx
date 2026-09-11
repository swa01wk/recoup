"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

interface TechnicalDetailsProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  defaultOpen?: boolean;
}

export function TechnicalDetails({
  title = "View technical details",
  children,
  className,
  defaultOpen = false,
}: TechnicalDetailsProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={cn("space-y-2", className)}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1.5 transition-colors"
      >
        <span className="text-slate-600">{open ? "▾" : "▸"}</span>
        {open ? "Hide technical details" : title}
      </button>
      {open && (
        <div className="rounded-lg border border-slate-700/40 bg-slate-900/60 p-4 space-y-2 text-xs font-mono text-slate-400">
          {children}
        </div>
      )}
    </div>
  );
}
