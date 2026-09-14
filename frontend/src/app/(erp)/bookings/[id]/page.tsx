"use client";

import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { BookingProfile } from "@/features/bookings/booking-profile";

export default function BookingPage() {
  const params = useParams<{ id: string }>();
  return <AuthGate>{(user) => <AppShell user={user}><BookingProfile bookingId={params.id} /></AppShell>}</AuthGate>;
}
