/** Dispatched after HITL actions so Recovery Summary / Ledger refresh immediately. */
export const RECOVERY_DATA_REFRESH_EVENT = "recoup:recovery-data-refresh";

export function requestRecoveryDataRefresh(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(RECOVERY_DATA_REFRESH_EVENT));
}
