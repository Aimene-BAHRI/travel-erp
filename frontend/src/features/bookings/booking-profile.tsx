"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BedDouble,
  Fingerprint,
  LoaderCircle,
  Plane,
  Printer,
  Users,
} from "lucide-react";
import Link from "next/link";
import { Fragment } from "react";

import { AgencyDocumentHeader } from "@/components/documents/agency-document-header";
import type { FinancialSummary } from "@/features/finance/types";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";
import { statusAr } from "@/lib/i18n/ar";

function useBookingText() {
  const { locale } = useLocale();
  return (en: string, ar: string) => locale === "ar" ? ar : en;
}

import { BookingTravelerProgress } from "./booking-traveler-progress";
import { BookingDraftWorkspace } from "./booking-draft-workspace";
import type { BookingRecord, BookingStatus } from "./types";

export function BookingProfile({ bookingId }: Readonly<{ bookingId: string }>) {
  const t = useBookingText();
  const cache = useQueryClient();
  const booking = useQuery({
    queryKey: ["booking", bookingId],
    queryFn: () => apiRequest<BookingRecord>(`/bookings/${bookingId}/`),
  });
  const refresh = (record: BookingRecord) => {
    cache.setQueryData(["booking", bookingId], record);
    cache.invalidateQueries({ queryKey: ["bookings"] });
  };
  const transition = useMutation({
    mutationFn: ({
      status,
      cancellation_reason = "",
    }: {
      status: BookingStatus;
      cancellation_reason?: string;
    }) =>
      apiRequest<BookingRecord>(`/bookings/${bookingId}/transition/`, {
        method: "POST",
        body: JSON.stringify({ status, cancellation_reason }),
      }),
    onSuccess: refresh,
  });
  if (booking.isPending)
    return (
      <div className="grid min-h-72 place-items-center">
        <LoaderCircle className="size-8 animate-spin text-cyan-800" />
      </div>
    );
  if (!booking.data)
    return (
      <p className="rounded-lg bg-red-50 p-4 text-red-700">
        {t("Booking is unavailable.", "الحجز غير متاح.")}
      </p>
    );
  const record = booking.data;
  const cancel = () => {
    const reason = window.prompt(t("Why is this booking being cancelled?", "ما سبب إلغاء هذا الحجز؟"));
    if (reason)
      transition.mutate({ status: "CANCELLED", cancellation_reason: reason });
  };
  return (
    <>
      <div className="no-print space-y-6">
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="flex flex-col justify-between gap-5 lg:flex-row">
            <div>
              <div className="flex items-center gap-3">
                <p className="text-sm uppercase tracking-wide text-slate-500">
                  {record.code}
                </p>
                <Status status={record.status} />
              </div>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">
                {record.customer_name}
              </h1>
              <p className="mt-2 text-sm text-slate-600">
                {record.trip_name}
                {record.source_quote_code
                  ? ` · ${t("source quote", "عرض السعر الأصلي")} ${record.source_quote_code}`
                  : t(" · direct booking", " · حجز مباشر")}
              </p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-semibold">
                {record.total_amount} {record.currency_code}
              </p>
              {record.status === "CONFIRMED" && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link
                    href={`/bookings/${record.id}/invoice`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium"
                  >
                    <Printer className="size-4" />
                    {t("Print invoice", "طباعة الفاتورة")}
                  </Link>
                  <button
                    onClick={() => transition.mutate({ status: "COMPLETED" })}
                    className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-medium text-white"
                  >
                    {t("Complete", "إكمال الحجز")}
                  </button>
                  <button
                    onClick={cancel}
                    className="rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-700"
                  >
                    {t("Cancel", "إلغاء")}
                  </button>
                </div>
              )}
            </div>
          </div>
        </section>
        <BookingTravelerProgress key={record.id} booking={record} onChange={refresh} />
        {record.status === "DRAFT" ? (
          <BookingDraftWorkspace booking={record} onChange={refresh} />
        ) : (
          <ConfirmedBooking booking={record} />
        )}
        {transition.isError && (
          <p className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
            {t("The status change was rejected.", "تعذر تغيير حالة الحجز.")}
          </p>
        )}
      </div>
      {record.status !== "DRAFT" && <BookingInvoice booking={record} />}
    </>
  );
}

function Status({ status }: Readonly<{ status: BookingStatus }>) {
  const t = useBookingText();
  const color =
    status === "DRAFT"
      ? "bg-amber-50 text-amber-800"
      : status === "CANCELLED"
        ? "bg-red-50 text-red-800"
        : "bg-cyan-50 text-cyan-800";
  return (
    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${color}`}>
      {t(status.replaceAll("_", " "), statusAr(status))}
    </span>
  );
}

function ConfirmedBooking({ booking }: Readonly<{ booking: BookingRecord }>) {
  const t = useBookingText();
  return (
    <>
      <section className="rounded-xl border border-slate-200 bg-white">
        <header className="border-b p-5">
          <h2 className="flex items-center gap-2 font-semibold">
            <Users className="size-5 text-cyan-700" />
            {t("Travelers and final prices", "المسافرون والأسعار النهائية")}
          </h2>
        </header>
        <div className="divide-y">
          {booking.travelers.map((traveler) => (
            <div key={traveler.id} className="p-5">
              <div className="flex justify-between">
                <div>
                  <p className="font-medium">{traveler.traveler_name}</p>
                  <p className="text-xs text-slate-500">
                    {traveler.passenger_category_name}
                  </p>
                </div>
                <p className="font-semibold">
                  {traveler.charges
                    .reduce(
                      (sum, charge) => sum + Number(charge.final_amount),
                      0,
                    )
                    .toFixed(2)}{" "}
                  {booking.currency_code}
                </p>
              </div>
              <div className="mt-3 space-y-1">
                {traveler.charges.map((charge) => (
                  <p
                    key={charge.id}
                    className="flex justify-between text-sm text-slate-600"
                  >
                    <span>{charge.description}</span>
                    <span>
                      {charge.final_amount} {charge.currency_code}
                    </span>
                  </p>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
      <div className="grid gap-6 xl:grid-cols-2">
        <Summary
          title={t("Sold accommodation", "الإقامة المحجوزة")}
          icon={<BedDouble className="size-5 text-cyan-700" />}
        >
          {booking.accommodations.map((item) => (
            <div key={item.id} className="flex justify-between p-4">
              <span>
                {item.hotel_name} · {item.room_type_name}
              </span>
              <b>
                {item.total_amount} {item.currency_code}
              </b>
            </div>
          ))}
        </Summary>
        <Summary
          title={t("Selected flights", "رحلات الطيران المختارة")}
          icon={<Plane className="size-5 text-cyan-700" />}
        >
          {booking.flights.map((item) => (
            <div key={item.id} className="p-4">
              <b>{item.flight_number}</b>
              <p className="text-sm text-slate-500">
                {item.origin_airport_code} → {item.destination_airport_code}
              </p>
            </div>
          ))}
        </Summary>
      </div>
      {booking.snapshot && (
        <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
          <p className="flex items-center gap-2 font-semibold text-emerald-950">
            <Fingerprint className="size-5" />
            {t("Immutable commercial snapshot", "نسخة محفوظة من بيانات الحجز المؤكد")}
          </p>
          <p className="mt-2 break-all font-mono text-xs text-emerald-700">
            {booking.snapshot.sha256}
          </p>
        </section>
      )}
    </>
  );
}

function Summary({
  title,
  icon,
  children,
}: Readonly<{
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}>) {
  return (
    <section className="rounded-xl border bg-white">
      <header className="flex items-center gap-2 border-b p-5 font-semibold">
        {icon}
        {title}
      </header>
      <div className="divide-y">{children}</div>
    </section>
  );
}

export function BookingInvoice({
  booking,
  preview = false,
}: Readonly<{ booking: BookingRecord; preview?: boolean }>) {
  const t = useBookingText();
  const summary = useQuery({
    queryKey: ["financial-summary", booking.id],
    queryFn: () =>
      apiRequest<FinancialSummary>(
        `/finance/transactions/booking-summary/?booking=${booking.id}`,
      ),
  });
  const allocatedPaid = (summary.data?.traveler_balances ?? []).reduce(
    (total, traveler) => total + Number(traveler.paid_amount),
    0,
  );
  const unallocatedPaid =
    Number(summary.data?.paid_amount ?? 0) - allocatedPaid;
  return (
    <>
      {preview && (
        <div className="no-print sticky top-0 z-10 flex items-center justify-between border-b bg-white/95 px-6 py-4 shadow-sm backdrop-blur">
          <Link
            href={`/bookings/${booking.id}`}
            className="rounded-lg border px-4 py-2 text-sm font-medium"
          >
            {t("Back to booking", "العودة إلى الحجز")}
          </Link>
          <button
            type="button"
            disabled={summary.isPending}
            onClick={async () => {
              await Promise.allSettled([
                document.fonts.ready,
                ...Array.from(document.querySelectorAll<HTMLImageElement>(".receipt-sheet img"))
                  .map((logo) => logo.decode()),
              ]);
              window.print();
            }}
            className="inline-flex items-center gap-2 rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            <Printer className="size-4" />
            {summary.isPending ? t("Loading totals…", "جارٍ تحميل المبالغ…") : t("Print / Save PDF", "طباعة / حفظ PDF")}
          </button>
        </div>
      )}
      <div className={`receipt-sheet ${preview ? "mx-auto max-w-3xl space-y-4 p-4 sm:p-6" : "print-only hidden space-y-4"}`}>
      {([t("Client copy", "نسخة العميل"), t("Accountant copy", "نسخة المحاسب")] as const).map((copy, index) => (
        <Fragment key={copy}>
        {index > 0 && <div className="border-t border-dashed border-slate-400" />}
        <article
          className={`receipt-slip booking-invoice-slip rounded-xl border border-slate-900 p-3 text-slate-950 print:break-inside-avoid ${index === 0 ? "bg-cyan-50" : "bg-amber-50"}`}
          dir={t("ltr", "rtl") as "ltr" | "rtl"}
        >
          <div className="flex items-start justify-between gap-3 border-b pb-3">
          <AgencyDocumentHeader
            compact
            agencyName={booking.agency_name}
            agencyLogo={booking.agency_logo}
            title={t("Booking confirmation / Invoice", "تأكيد الحجز / الفاتورة")}
          />
          <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${index === 0 ? "bg-cyan-100 text-cyan-800" : "bg-amber-100 text-amber-800"}`}>{copy}</span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <p>
              <b>{t("Booking number:", "رقم الحجز:")}</b> {booking.code}
            </p>
            <p>
              <b>{t("Date:", "التاريخ:")}</b>{" "}
              {new Date(booking.created_at).toLocaleDateString(t("en-GB", "ar-DZ"))}
            </p>
            <p>
              <b>{t("Customer:", "الزبون:")}</b> {booking.customer_name}
            </p>
            <p>
              <b>{t("Phone:", "الهاتف:")}</b> {booking.customer_phone}
            </p>
            <p>
              <b>{t("Program:", "البرنامج:")}</b> {booking.trip_name}
            </p>
            <p>
              <b>{t("Return date:", "تاريخ العودة:")}</b> {booking.return_date}
            </p>
          </div>
          <table className="mt-3 w-full border-collapse text-xs">
            <thead>
              <tr className="bg-slate-100">
                <th className="border p-2">{t("Traveler", "المسافر")}</th>
                <th className="border p-2">{t("Category", "الفئة")}</th>
                <th className="border p-2">{t("Accommodation", "السكن")}</th>
                <th className="border p-2">{t("Price", "السعر")}</th>
                <th className="border p-2">{t("Discount", "التخفيض")}</th>
                <th className="border p-2">{t("Final price", "النهائي")}</th>
              </tr>
            </thead>
            <tbody>
              {booking.travelers.map((traveler) => (
                <tr key={traveler.id}>
                  <td className="border p-2">{traveler.traveler_name}</td>
                  <td className="border p-2">
                    {t(traveler.derived_passenger_category ?? "Unspecified", ({ ADULT: "بالغ", CHILD: "طفل", INFANT: "رضيع" } as Record<string, string>)[traveler.derived_passenger_category ?? ""] ?? traveler.derived_passenger_category ?? "غير محدد")}
                  </td>
                  <td className="border p-2">
                    {traveler.room_assignments
                      .map(
                        (room) =>
                          `${room.city}: ${room.hotel} (${room.room_type})`,
                      )
                      .join("، ")}
                  </td>
                  <td className="border p-2">
                    {traveler.charges
                      .reduce((sum, item) => sum + Number(item.base_amount), 0)
                      .toFixed(2)}
                  </td>
                  <td className="border p-2">
                    {traveler.charges
                      .reduce(
                        (sum, item) => sum + Number(item.discount_amount),
                        0,
                      )
                      .toFixed(2)}
                  </td>
                  <td className="border p-2 font-bold">
                    {traveler.final_amount}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {summary.data && (
            <section className="mt-3 break-inside-avoid">
              <h2 className="mb-1 text-sm font-bold">
                {t("Payments by traveler", "تفاصيل الدفعات حسب المسافر")}
              </h2>
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-100">
                    <th className="border p-2">{t("Traveler", "المسافر")}</th>
                    <th className="border p-2">{t("Paid so far", "المدفوع حتى الآن")}</th>
                    <th className="border p-2">{t("Remaining balance", "المبلغ المتبقي")}</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.data.traveler_balances.map((traveler) => (
                    <tr key={traveler.booking_traveler}>
                      <td className="border p-2">{traveler.traveler_name}</td>
                      <td className="border p-2">
                        {traveler.paid_amount} {summary.data.currency}
                      </td>
                      <td className="border p-2">
                        {traveler.remaining_amount} {summary.data.currency}
                      </td>
                    </tr>
                  ))}
                  {unallocatedPaid > 0.00005 && (
                    <tr className="bg-amber-50">
                      <td className="border p-2 font-bold">
                        {t("Payments not allocated to a traveler", "دفعات غير مخصصة لمسافر")}
                      </td>
                      <td className="border p-2 font-bold">
                        {unallocatedPaid.toFixed(4)} {summary.data.currency}
                      </td>
                      <td className="border p-2">—</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>
          )}
          <div className="mt-3 grid grid-cols-3 gap-3 rounded-lg border border-slate-900 p-2 text-xs">
            <p className="flex flex-col gap-1 text-center">
              <span>{t("Total:", "المجموع:")}</span>
              <b>
                {booking.total_amount} {booking.currency_code}
              </b>
            </p>
            <p className="flex flex-col gap-1 text-center">
              <span>{t("Paid:", "المدفوع:")}</span>
              <b>
                {summary.data?.paid_amount ?? "0"} {booking.currency_code}
              </b>
            </p>
            <p className="flex flex-col gap-1 text-center">
              <span>{t("Remaining:", "المتبقي:")}</span>
              <b>
                {summary.data?.remaining_amount ?? booking.total_amount}{" "}
                {booking.currency_code}
              </b>
            </p>
          </div>
          <footer className="mt-4 grid break-inside-avoid grid-cols-3 gap-4 pb-[15mm] text-center text-xs">
            <span>{t("Customer signature", "توقيع الزبون")}</span>
            <span>{t("Employee signature", "توقيع الموظف")}</span>
            <span>{t("Agency stamp", "ختم الوكالة")}</span>
          </footer>
        </article>
        </Fragment>
      ))}
      </div>
    </>
  );
}
