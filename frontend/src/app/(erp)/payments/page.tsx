"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { PaymentWorkspace } from "@/features/finance/payment-workspace";
import { useLocale } from "@/lib/i18n/context";

export default function PaymentsPage() {
  const { locale } = useLocale();
  return (
    <AuthGate>
      {(user) => (
        <AppShell user={user}>
          <header className="no-print mb-7">
            <p className="text-sm font-medium text-cyan-800">
              {locale === "ar" ? "العمليات المالية" : "Financial operations"}
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">
              {locale === "ar" ? "المدفوعات" : "Payments"}
            </h1>
          </header>
          <PaymentWorkspace />
        </AppShell>
      )}
    </AuthGate>
  );
}
