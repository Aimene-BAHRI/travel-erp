"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck, LoaderCircle, Plus, Users } from "lucide-react";
import Link from "next/link";

import type { BookingRecord, BookingStatus } from "@/features/bookings/types";
import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";
import { statusAr } from "@/lib/i18n/ar";

const statusStyles: Record<BookingStatus, string> = {
  DRAFT: "bg-amber-50 text-amber-800",
  CONFIRMED: "bg-emerald-50 text-emerald-800",
  CANCELLED: "bg-red-50 text-red-800",
  COMPLETED: "bg-cyan-50 text-cyan-800",
};

export function TripBookings({ tripId }: Readonly<{ tripId: string }>) {
  const { locale } = useLocale();
  const bookings = useQuery({
    queryKey: ["trip-bookings", tripId],
    queryFn: () =>
      apiRequest<Paginated<BookingRecord>>(
        `/bookings/?trip=${tripId}&ordering=-created_at`,
      ),
  });
  const t = (en: string, ar: string) => (locale === "ar" ? ar : en);

  if (bookings.isPending) {
    return (
      <div className="grid min-h-48 place-items-center">
        <LoaderCircle className="size-7 animate-spin text-cyan-800" />
      </div>
    );
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <header className="flex flex-col gap-4 border-b p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="font-semibold">
            {t("Bookings for this trip", "حجوزات هذه الرحلة")}
          </h2>
          <p className="text-sm text-slate-500">
            {t(
              "Review existing bookings or start a new one already linked to this trip.",
              "راجع الحجوزات الحالية أو ابدأ حجزا مرتبطا بهذه الرحلة مباشرة.",
            )}
          </p>
        </div>
        <Link
          href={`/bookings?trip=${tripId}`}
          className="inline-flex items-center gap-2 rounded-lg bg-cyan-800 px-3 py-2 text-sm font-medium text-white"
        >
          <Plus className="size-4" />
          {t("New booking for this trip", "حجز جديد لهذه الرحلة")}
        </Link>
      </header>
      {bookings.data?.results.length ? (
        <div className="divide-y">
          {bookings.data.results.map((booking) => (
            <Link
              key={booking.id}
              href={`/bookings/${booking.id}`}
              className="grid gap-3 p-5 hover:bg-slate-50 md:grid-cols-[1fr_auto_auto] md:items-center"
            >
              <div>
                <div className="flex items-center gap-3">
                  <p className="font-semibold text-cyan-900">{booking.code}</p>
                  <span
                    className={`rounded-full px-2 py-1 text-xs ${statusStyles[booking.status]}`}
                  >
                    {locale === "ar"
                      ? statusAr(booking.status)
                      : booking.status}
                  </span>
                </div>
                <p className="text-sm text-slate-600">
                  {booking.customer_name}
                  {booking.partner_name ? ` · ${booking.partner_name}` : ""}
                </p>
              </div>
              <p className="flex items-center gap-2 text-sm text-slate-500">
                <Users className="size-4" />
                {booking.traveler_count} {t("travelers", "مسافرين")}
              </p>
              <div className="text-right">
                <p className="font-semibold">
                  {booking.total_amount} {booking.currency_code}
                </p>
                <p className="text-xs text-slate-500">
                  {t("paid", "مدفوع")} {booking.paid_amount} ·{" "}
                  {t("remaining", "متبقي")} {booking.remaining_amount}
                </p>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="grid min-h-48 place-items-center text-center">
          <div>
            <BookOpenCheck className="mx-auto size-9 text-slate-300" />
            <p className="mt-3 font-medium">
              {t("No bookings for this trip", "لا توجد حجوزات لهذه الرحلة")}
            </p>
            <p className="text-sm text-slate-500">
              {t(
                "Create the first booking from this tab.",
                "أنشئ أول حجز من هذه الصفحة.",
              )}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
