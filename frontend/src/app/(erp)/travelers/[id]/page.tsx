"use client";

import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { TravelerProfile } from "@/features/travelers/traveler-profile";

export default function TravelerProfilePage() {
  const params = useParams<{ id: string }>();
  return <AuthGate>{(user) => <AppShell user={user}><TravelerProfile travelerId={params.id} /></AppShell>}</AuthGate>;
}

