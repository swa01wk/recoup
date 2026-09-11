"use client";

import { RoleProvider } from "@/hooks/useRole";
import { Sidebar } from "@/components/layout/sidebar";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <RoleProvider>
      <Sidebar />
      <div className="flex-1 ml-56 min-h-screen flex flex-col">{children}</div>
    </RoleProvider>
  );
}
