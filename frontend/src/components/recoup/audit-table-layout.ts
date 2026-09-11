import { cn } from "@/lib/utils";

/** Shared 7-column grid for audit history header + rows (md+). */
export const AUDIT_TABLE_GRID = cn(
  "hidden md:grid",
  "md:grid-cols-[112px_72px_minmax(0,1fr)_96px_72px_112px_52px]",
  "md:gap-x-3",
  "md:items-center",
  "px-5"
);

export const AUDIT_TABLE_HEADER_CELL =
  "text-[10px] uppercase tracking-widest text-slate-500 font-medium";

export const AUDIT_TABLE_ROW = cn(
  "grid grid-cols-[1fr_auto] gap-x-3 items-center py-3 px-5",
  "md:grid-cols-[112px_72px_minmax(0,1fr)_96px_72px_112px_52px]",
  "md:gap-x-3 md:py-2.5",
  "border-b border-slate-800/60 last:border-b-0",
  "hover:bg-slate-800/20 transition-colors"
);
