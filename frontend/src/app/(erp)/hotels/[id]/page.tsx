"use client";

import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { HotelProfile } from "@/features/catalog/hotel-profile";

export default function HotelProfilePage() {
  const params = useParams<{ id: string }>();
  return <AuthGate>{(user) => <AppShell user={user}><HotelProfile hotelId={params.id} /></AppShell>}</AuthGate>;
}

