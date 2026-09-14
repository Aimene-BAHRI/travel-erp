"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { BookingCreator } from "@/features/bookings/booking-creator";
import { BookingList } from "@/features/bookings/booking-list";
import { useLocale } from "@/lib/i18n/context";

export default function BookingsPage() {
  const { locale } = useLocale();
  return (
    <AuthGate>
      {(user) => (
        <AppShell user={user}>
          <header className="mb-7">
            <p className="text-sm font-medium text-cyan-800">
              {locale === "ar" ? "المبيعات المؤكدة" : "Confirmed travel sales"}
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">
              {locale === "ar" ? "الحجوزات" : "Bookings"}
            </h1>
          </header>
          <BookingCreator />
          <BookingList />
        </AppShell>
      )}
    </AuthGate>
  );
}
