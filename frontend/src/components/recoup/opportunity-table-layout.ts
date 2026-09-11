import { cn } from "@/lib/utils";

/** Shared 7-column grid for opportunities table header + rows (md+). */
export const OPPORTUNITY_TABLE_GRID = cn(
  "hidden md:grid",
  "md:grid-cols-[88px_128px_minmax(0,1fr)_96px_80px_116px_136px]",
  "md:gap-x-3",
  "md:items-center",
  "px-4"
);

export const OPPORTUNITY_TABLE_HEADER_CELL = "text-[10px] uppercase tracking-widest text-slate-500 font-medium";

export const OPPORTUNITY_TABLE_ROW = cn(
  "grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 items-center py-3 px-4",
  "md:grid-cols-[88px_128px_minmax(0,1fr)_96px_80px_116px_136px]",
  "md:gap-x-3 md:gap-y-0 md:items-center md:py-2.5",
  "border-b border-slate-800/60 last:border-b-0",
  "hover:bg-slate-800/20 transition-colors"
);
