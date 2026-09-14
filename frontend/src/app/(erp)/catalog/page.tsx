"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { CatalogOverview } from "@/features/catalog/catalog-overview";
import { SupplierManager } from "@/features/catalog/supplier-manager";

export default function CatalogPage() {
  const uiText = useUiText();
  return <AuthGate>{(user) => <AppShell user={user}><header className="mb-7"><p className="text-sm font-medium text-cyan-800">{uiText("Commercial reference data")}</p><h1 className="mt-1 text-3xl font-semibold tracking-tight">{uiText("Catalog")}</h1><p className="mt-2 text-slate-600">{uiText("Suppliers, airlines, and configurable accommodation categories.")}</p></header><div className="mb-6"><SupplierManager /></div><CatalogOverview /></AppShell>}</AuthGate>;
}
