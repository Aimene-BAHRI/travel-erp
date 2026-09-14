"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { TransportWorkspace } from "@/features/trips/transport-workspace";

export default function TransportPage() {
  const uiText = useUiText();
  return (
    <AuthGate>
      {(user) => (
        <AppShell user={user}>
          <header className="mb-7">
            <p className="text-sm font-medium text-cyan-800">
              {uiText("Operations control")}
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">
              {uiText("Upcoming transport")}
            </h1>
            <p className="mt-2 text-slate-600">
              {uiText("Manage and monitor every scheduled transfer across your trips.")}
            </p>
          </header>
          <TransportWorkspace />
        </AppShell>
      )}
    </AuthGate>
  );
}
