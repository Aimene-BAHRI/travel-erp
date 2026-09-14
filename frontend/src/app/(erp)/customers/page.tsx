"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { AppShell } from "@/components/layout/app-shell";
import { CustomerList } from "@/features/customers/customer-list";
import { AuthGate } from "@/features/auth/auth-gate";

export default function CustomersPage() {
  const uiText = useUiText();
  return <AuthGate>{(user) => <AppShell user={user}><header className="mb-7"><p className="text-sm font-medium text-cyan-800">{uiText("Commercial relationships")}</p><h1 className="mt-1 text-3xl font-semibold tracking-tight">{uiText("Customers")}</h1></header><CustomerList /></AppShell>}</AuthGate>;
}
