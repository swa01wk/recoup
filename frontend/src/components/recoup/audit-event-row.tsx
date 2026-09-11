import Link from "next/link";
import { StatusBadge } from "@/components/recoup/status-badge";
import { serviceIcon } from "@/components/recoup/service-icons";
import {
  AUDIT_TABLE_GRID,
  AUDIT_TABLE_HEADER_CELL,
  AUDIT_TABLE_ROW,
} from "@/components/recoup/audit-table-layout";
import { fmtSavings } from "@/lib/recoup-ui-rules";
import { cn } from "@/lib/utils";

export interface AuditEvent {
  /** Deterministic unique key for React lists */
  key: string;
  opportunityId: string;
  eventType: string;
  timestamp: string;
  service: string;
  event: string;
  amount: number;
  actor: string;
  state: string;
  href?: string;
}

function fmtTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function AuditTableHeader() {
  return (
    <div className={cn(AUDIT_TABLE_GRID, "py-2.5 border-b border-slate-700/40 bg-slate-800/30")}>
      <span className={AUDIT_TABLE_HEADER_CELL}>Timestamp</span>
      <span className={AUDIT_TABLE_HEADER_CELL}>Service</span>
      <span className={AUDIT_TABLE_HEADER_CELL}>Event</span>
      <span className={cn(AUDIT_TABLE_HEADER_CELL, "text-right")}>Amount</span>
      <span className={cn(AUDIT_TABLE_HEADER_CELL, "text-center")}>Actor</span>
      <span className={cn(AUDIT_TABLE_HEADER_CELL, "text-center")}>Status</span>
      <span className={cn(AUDIT_TABLE_HEADER_CELL, "text-right")}>Action</span>
    </div>
  );
}

interface AuditEventRowProps {
  event: AuditEvent;
  className?: string;
}

export function AuditEventRow({ event, className }: AuditEventRowProps) {
  const isRecovered = event.state.toUpperCase() === "RECOVERED";

  return (
    <div className={cn(AUDIT_TABLE_ROW, isRecovered && "bg-emerald-950/10", className)}>
      {/* Timestamp */}
      <span className="hidden md:block text-xs text-slate-500 tabular-nums whitespace-nowrap self-center">
        {fmtTimestamp(event.timestamp)}
      </span>

      {/* Service */}
      <span className="hidden md:flex items-center gap-1 min-w-0 self-center">
        <span className="text-sm leading-none">{serviceIcon(event.service)}</span>
        <span className="text-xs text-slate-300 truncate">{event.service}</span>
      </span>

      {/* Event (+ mobile meta) */}
      <div className="min-w-0 self-center">
        <p className="text-sm text-slate-200 truncate leading-snug" title={event.event}>
          {event.event}
        </p>
        <p className="md:hidden text-[10px] text-slate-500 mt-0.5 truncate">
          {fmtTimestamp(event.timestamp)} · {event.service} · {event.actor}
        </p>
      </div>

      {/* Amount */}
      <span
        className={cn(
          "hidden md:block font-mono text-sm font-semibold tabular-nums whitespace-nowrap text-right self-center",
          event.amount > 0 ? "text-emerald-400" : "text-slate-500"
        )}
      >
        {event.amount > 0 ? fmtSavings(event.amount) : "—"}
      </span>

      {/* Actor */}
      <span className="hidden md:block text-xs text-slate-500 text-center truncate self-center">
        {event.actor}
      </span>

      {/* Status */}
      <div className="hidden md:flex justify-center self-center">
        <StatusBadge state={event.state} className="text-[10px] whitespace-nowrap" />
      </div>

      {/* Action */}
      <div className="flex justify-end items-center self-center">
        {event.href ? (
          <Link
            href={event.href}
            className="text-[10px] text-slate-500 hover:text-blue-400 transition-colors whitespace-nowrap"
          >
            Open
          </Link>
        ) : (
          <span className="text-[10px] text-slate-700">—</span>
        )}
      </div>
    </div>
  );
}
