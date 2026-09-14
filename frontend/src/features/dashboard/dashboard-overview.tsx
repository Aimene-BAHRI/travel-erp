"use client";
import { OperationalSummary } from "@/features/trips/operational-summary";

import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck, CalendarDays, CreditCard, Inbox, LoaderCircle, Plus } from "lucide-react";
import Link from "next/link";

import { apiRequest } from "@/lib/api/client";
import { statusAr } from "@/lib/i18n/ar";
import { useLocale } from "@/lib/i18n/context";

import type { DashboardData } from "./types";

const metrics = [
  { key: "open_trips", label: { ar: "رحلات مفتوحة", en: "Open trips" }, icon: CalendarDays, href: "/trips" },
  { key: "confirmed_bookings", label: { ar: "حجوزات مؤكدة", en: "Confirmed bookings" }, icon: BookOpenCheck, href: "/bookings" },
  { key: "booking_requests", label: { ar: "طلبات تحتاج متابعة", en: "Requests to follow" }, icon: Inbox, href: "/booking-requests" },
  { key: "payment_entries", label: { ar: "قيود مدفوعات", en: "Payment entries" }, icon: CreditCard, href: "/payments" },
] as const;

function formatDate(value: string, locale: "ar" | "en") {
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-DZ" : "en", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

export function DashboardOverview() {
  const { locale } = useLocale();
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiRequest<DashboardData>("/dashboard/"),
  });

  if (dashboard.isPending) {
    return (
      <div className="grid min-h-80 place-items-center">
        <LoaderCircle className="size-8 animate-spin text-cyan-800" />
      </div>
    );
  }
  if (dashboard.isError || !dashboard.data) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
        {locale === "ar"
          ? "تعذر تحميل لوحة التحكم. يرجى تحديث الصفحة والمحاولة مرة أخرى."
          : "The dashboard could not be loaded. Please refresh and try again."}
      </div>
    );
  }

  const data = dashboard.data;

  return (
    <div className="space-y-6">
      {dashboard.data.operational?.map((item) => <div key={item.trip}><Link href={`/trips/${item.trip}`} className="font-medium">{item.name}</Link><OperationalSummary report={item.readiness} /></div>)}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-medium text-cyan-800">
            {locale === "ar" ? "نظرة عامة على العمليات" : "Operations overview"}
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            {locale === "ar" ? "لوحة التحكم" : "Dashboard"}
          </h1>
          <p className="mt-2 text-slate-600">
            {locale === "ar"
              ? "متابعة الرحلات، الطلبات، الحجوزات، والمدفوعات."
              : "Follow trips, requests, bookings, and payments."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/trips" className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50">
            <Plus className="size-4" />
            {locale === "ar" ? "رحلة جديدة" : "New trip"}
          </Link>
          <Link href="/booking-requests" className="inline-flex items-center gap-2 rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-900">
            <Inbox className="size-4" />
            {locale === "ar" ? "طلبات الحجز" : "Booking requests"}
          </Link>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(({ key, label, icon: Icon, href }) => (
          <Link key={key} href={href} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-cyan-300">
            <div className="flex items-center justify-between">
              <span className="rounded-lg bg-cyan-50 p-2 text-cyan-800">
                <Icon className="size-5" />
              </span>
              <span className="text-xs font-medium text-slate-400">
                {locale === "ar" ? "عرض الكل" : "View all"}
              </span>
            </div>
            <p className="mt-5 text-3xl font-semibold">{data.counts[key]}</p>
            <p className="mt-1 text-sm text-slate-500">{label[locale]}</p>
          </Link>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 p-5">
            <div>
              <h2 className="font-semibold">
                {locale === "ar" ? "المغادرات القادمة" : "Upcoming departures"}
              </h2>
              <p className="text-sm text-slate-500">
                {locale === "ar" ? "أقرب الرحلات في الرزنامة." : "The next trips on the calendar."}
              </p>
            </div>
            <Link href="/trips" className="text-sm font-medium text-cyan-800">
              {locale === "ar" ? "كل الرحلات" : "All trips"}
            </Link>
          </div>
          {data.upcoming_trips.length ? (
            <div className="divide-y divide-slate-100">
              {data.upcoming_trips.map((trip) => (
                <Link key={trip.id} href={`/trips/${trip.id}`} className="flex items-center justify-between gap-4 p-5 hover:bg-slate-50">
                  <div>
                    <p className="font-medium text-cyan-900">{trip.code} · {trip.name}</p>
                    <p className="mt-1 text-sm text-slate-500">{formatDate(trip.departure_date, locale)}</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                    {locale === "ar" ? statusAr(trip.status) : trip.status}
                  </span>
                </Link>
              ))}
            </div>
          ) : (
            <p className="p-8 text-center text-sm text-slate-500">
              {locale === "ar" ? "لا توجد رحلات قادمة بعد." : "No upcoming trips yet."}
            </p>
          )}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 p-5">
            <div>
              <h2 className="font-semibold">
                {locale === "ar" ? "أحدث الحجوزات" : "Recent bookings"}
              </h2>
              <p className="text-sm text-slate-500">
                {locale === "ar"
                  ? "آخر السجلات التجارية المؤكدة."
                  : "The latest confirmed commercial records."}
              </p>
            </div>
            <Link href="/bookings" className="text-sm font-medium text-cyan-800">
              {locale === "ar" ? "كل الحجوزات" : "All bookings"}
            </Link>
          </div>
          {data.recent_bookings.length ? (
            <div className="divide-y divide-slate-100">
              {data.recent_bookings.map((booking) => (
                <Link key={booking.id} href={`/bookings/${booking.id}`} className="grid gap-2 p-5 hover:bg-slate-50 md:grid-cols-[1fr_1fr_auto] md:items-center">
                  <p className="font-medium text-cyan-900">{booking.code}</p>
                  <p className="text-sm text-slate-600">{booking.customer_name} · {booking.trip_name}</p>
                  <span className="text-xs font-medium text-slate-500">
                    {locale === "ar" ? statusAr(booking.status) : booking.status}
                  </span>
                </Link>
              ))}
            </div>
          ) : (
            <p className="p-8 text-center text-sm text-slate-500">
              {locale === "ar" ? "لم يتم إنشاء أي حجوزات بعد." : "No bookings have been created yet."}
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
