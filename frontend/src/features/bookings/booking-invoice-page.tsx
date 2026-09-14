"use client";

import { useQuery } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";

import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";

import { BookingInvoice } from "./booking-profile";
import type { BookingRecord } from "./types";

export function BookingInvoicePage({
  bookingId,
}: Readonly<{ bookingId: string }>) {
  const { locale } = useLocale();
  const booking = useQuery({
    queryKey: ["booking-invoice", bookingId],
    queryFn: () => apiRequest<BookingRecord>(`/bookings/${bookingId}/`),
  });

  if (booking.isPending)
    return (
      <div className="grid min-h-screen place-items-center bg-slate-100">
        <LoaderCircle className="size-8 animate-spin text-cyan-800" />
      </div>
    );

  if (!booking.data)
    return (
      <p className="m-6 rounded-lg bg-red-50 p-4 text-red-700">
        {locale === "ar" ? "الفاتورة غير متاحة." : "Invoice is unavailable."}
      </p>
    );

  if (booking.data.status === "DRAFT")
    return (
      <p className="m-6 rounded-lg bg-amber-50 p-4 text-amber-800">
        {locale === "ar" ? "يرجى تأكيد الحجز قبل طباعة الفاتورة." : "Confirm the booking before printing its commercial invoice."}
      </p>
    );

  return (
    <main className="min-h-screen bg-slate-100 pb-10 print:min-h-0 print:bg-white print:pb-0">
      <BookingInvoice booking={booking.data} preview />
    </main>
  );
}
