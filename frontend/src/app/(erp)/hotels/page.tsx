"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { HotelList } from "@/features/catalog/hotel-list";

export default function HotelsPage() {
  const uiText = useUiText();
  return <AuthGate>{(user) => <AppShell user={user}><header className="mb-7"><p className="text-sm font-medium text-cyan-800">{uiText("Accommodation catalog")}</p><h1 className="mt-1 text-3xl font-semibold tracking-tight">{uiText("Hotels")}</h1></header><HotelList /></AppShell>}</AuthGate>;
}
