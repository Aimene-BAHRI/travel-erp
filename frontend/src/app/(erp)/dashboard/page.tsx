"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { DashboardOverview } from "@/features/dashboard/dashboard-overview";

export default function DashboardPage() {
  return (
    <AuthGate>{(user) => <AppShell user={user}><DashboardOverview /></AppShell>}</AuthGate>
  );
}
