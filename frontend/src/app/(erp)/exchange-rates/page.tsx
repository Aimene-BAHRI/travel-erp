"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { ExchangeRateWorkspace } from "@/features/finance/exchange-rate-workspace";

export default function ExchangeRatesPage() {
  const uiText = useUiText();
  return (
    <AuthGate>
      {(user) => (
        <AppShell user={user}>
          <header className="mb-7">
            <p className="text-sm font-medium text-cyan-800">{uiText("مرجع الأسعار المالية")}</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">{uiText("أسعار الصرف")}</h1>
          </header>
          <ExchangeRateWorkspace />
        </AppShell>
      )}
    </AuthGate>
  );
}
