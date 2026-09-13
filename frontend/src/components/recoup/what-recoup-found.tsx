"use client";

import { fmtSavings } from "@/lib/recoup-ui-rules";

interface WhatRecoupFoundProps {
  headline: string;
  body: string;
  savings: number;
}

export function WhatRecoupFound({ headline, body, savings }: WhatRecoupFoundProps) {
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">
        What Recoup Found
      </h3>
      <p className="text-base font-semibold text-slate-100">{headline}</p>
      <p className="text-sm text-slate-300 leading-relaxed">{body}</p>
      {savings > 0 && (
        <p className="text-sm text-slate-400">
          Recoup estimates {fmtSavings(savings)} can be recovered.
        </p>
      )}
    </div>
  );
}
