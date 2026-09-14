"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { TripList } from "@/features/trips/trip-list";
import { useLocale } from "@/lib/i18n/context";

export default function TripsPage() {
  const { locale } = useLocale();
  return (
    <AuthGate>
      {(user) => (
        <AppShell user={user}>
          <header className="mb-7">
            <p className="text-sm font-medium text-cyan-800">
              {locale === "ar" ? "المغادرات والعمليات" : "Departures and operations"}
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">
              {locale === "ar" ? "الرحلات" : "Trips"}
            </h1>
          </header>
          <TripList />
        </AppShell>
      )}
    </AuthGate>
  );
}
