"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { TravelerList } from "@/features/travelers/traveler-list";

export default function TravelersPage() {
  const uiText = useUiText();
  return <AuthGate>{(user) => <AppShell user={user}><header className="mb-7"><p className="text-sm font-medium text-cyan-800">{uiText("Reusable travel profiles")}</p><h1 className="mt-1 text-3xl font-semibold tracking-tight">{uiText("Travelers")}</h1></header><TravelerList /></AppShell>}</AuthGate>;
}
