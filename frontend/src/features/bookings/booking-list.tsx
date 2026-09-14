"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck, LoaderCircle, Search, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";
import { statusAr } from "@/lib/i18n/ar";
import { useLocale } from "@/lib/i18n/context";

import type { BookingRecord, BookingStatus } from "./types";

const styles: Record<BookingStatus, string> = {
  DRAFT: "bg-amber-50 text-amber-700",
  CONFIRMED: "bg-emerald-50 text-emerald-700",
  CANCELLED: "bg-red-50 text-red-700",
  COMPLETED: "bg-cyan-50 text-cyan-800",
};

const text = {
  ar: {
    title: "الحجوزات المؤكدة",
    subtitle: "المبيعات المباشرة والعروض المقبولة بشروط تجارية محفوظة.",
    search: "ابحث عن حجز أو عميل أو رحلة",
    travelers: "مسافرين",
    remaining: "متبقي",
    paid: "مدفوع",
    noBookings: "لا توجد حجوزات",
    noBookingsHelp: "أنشئ حجزا مباشرا أو حول عرضا مقبولا للبدء.",
  },
  en: {
    title: "Confirmed travel bookings",
    subtitle: "Direct sales and public requests converted into booking records.",
    search: "Search booking, customer, or trip",
    travelers: "travelers",
    remaining: "remaining",
    paid: "paid",
    noBookings: "No bookings found",
    noBookingsHelp: "Create a direct booking or convert a public booking request to begin.",
  },
};

export function BookingList() {
  const { locale } = useLocale();
  const copy = text[locale];
  const [search, setSearch] = useState("");
  const bookings = useQuery({
    queryKey: ["bookings", search],
    queryFn: () =>
      apiRequest<Paginated<BookingRecord>>(`/bookings/?search=${encodeURIComponent(search)}`),
  });

  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <div className="flex flex-col gap-4 border-b p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="font-semibold">{copy.title}</h2>
          <p className="text-sm text-slate-500">{copy.subtitle}</p>
        </div>
        <label className="flex items-center gap-2 rounded-lg border px-3 py-2">
          <Search className="size-4 text-slate-400" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={copy.search}
            className="w-64 bg-transparent outline-none"
          />
        </label>
      </div>
      {bookings.isPending ? (
        <div className="grid min-h-60 place-items-center">
          <LoaderCircle className="size-7 animate-spin text-cyan-800" />
        </div>
      ) : bookings.data?.results.length ? (
        <div className="divide-y">
          {bookings.data.results.map((booking) => (
            <Link
              key={booking.id}
              href={`/bookings/${booking.id}`}
              className="grid gap-4 p-5 hover:bg-slate-50 md:grid-cols-[1fr_auto_auto]"
            >
              <div>
                <div className="flex gap-3">
                  <h3 className="font-semibold text-cyan-900">{booking.code}</h3>
                  <span className={`rounded-full px-2 py-1 text-xs ${styles[booking.status]}`}>
                    {locale === "ar" ? statusAr(booking.status) : booking.status}
                  </span>
                </div>
                <p className="text-sm text-slate-600">
                  {booking.customer_name} · {booking.trip_name}
                </p>
              </div>
              <p className="flex items-center gap-2 text-sm text-slate-500">
                <Users className="size-4" />
                {booking.traveler_count} {copy.travelers}
              </p>
              <div className={locale === "ar" ? "text-left" : "text-right"}>
                <p className="font-semibold">
                  {booking.remaining_amount} {booking.currency_code}
                </p>
                <p className="text-xs text-slate-500">
                  {copy.remaining} · {booking.paid_amount} {copy.paid}
                </p>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="grid min-h-60 place-items-center text-center">
          <div>
            <BookOpenCheck className="mx-auto size-9 text-slate-300" />
            <p className="mt-3 font-medium">{copy.noBookings}</p>
            <p className="text-sm text-slate-500">{copy.noBookingsHelp}</p>
          </div>
        </div>
      )}
    </section>
  );
}
