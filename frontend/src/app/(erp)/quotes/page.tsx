"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { QuoteList } from "@/features/pricing/quote-list";

export default function QuotesPage() {
  return <AuthGate>{(user) => <AppShell user={user}><header className="mb-7"><p className="text-sm font-medium text-cyan-800">Pricing and sales</p><h1 className="mt-1 text-3xl font-semibold tracking-tight">Quotes</h1></header><QuoteList /></AppShell>}</AuthGate>;
}
