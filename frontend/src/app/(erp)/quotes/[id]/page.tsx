"use client";

import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { QuoteProfile } from "@/features/pricing/quote-profile";

export default function QuotePage() {
  const params = useParams<{ id: string }>();
  return <AuthGate>{(user) => <AppShell user={user}><QuoteProfile quoteId={params.id} /></AppShell>}</AuthGate>;
}
