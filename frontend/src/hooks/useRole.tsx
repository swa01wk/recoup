"use client";

import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

// Role is permanently hardcoded to "operator".
// The Viewer role has been removed from the product.
export type UserRole = "operator";

interface RoleContextValue {
  role: UserRole;
  isOperator: true;
  isViewer: false;
  principal: string;
}

const RoleContext = createContext<RoleContextValue | null>(null);

const OPERATOR_VALUE: RoleContextValue = {
  role: "operator",
  isOperator: true,
  isViewer: false,
  principal: "operator@recoup",
};

export function RoleProvider({ children }: { children: ReactNode }) {
  const value = useMemo(() => OPERATOR_VALUE, []);
  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole(): RoleContextValue {
  const ctx = useContext(RoleContext);
  if (!ctx) {
    throw new Error("useRole must be used within RoleProvider");
  }
  return ctx;
}
