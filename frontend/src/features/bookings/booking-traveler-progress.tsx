"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { MutationMessage } from "@/components/forms/mutation-message";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";
import { OperationalSummary } from "@/features/trips/operational-summary";
import { BookingTravelerFlow } from "./booking-traveler-flow";
import type { BookingRecord } from "./types";

export function BookingTravelerProgress({ booking, onChange }: { booking: BookingRecord; onChange: (record: BookingRecord) => void }) {
  const { locale } = useLocale();
  const t = (en: string, ar: string) => locale === "ar" ? ar : en;
  const [count, setCount] = useState(String(booking.expected_travelers));
  const save = useMutation({
    mutationFn: () => apiRequest<BookingRecord>(`/bookings/${booking.id}/size/`, {
      method: "PATCH", body: JSON.stringify({ expected_travelers: Number(count) }),
    }),
    onSuccess: onChange,
  });
  const r = booking.readiness;
  const c = booking.capacity;
  const stats = [
    [t("Trip capacity", "سعة الرحلة"), c.maximum ?? t("Not set", "غير محددة")],
    [t("Booked places", "الأماكن المحجوزة"), c.booked],
    [t("Trip places remaining", "الأماكن المتبقية بالرحلة"), c.remaining ?? t("Not limited", "غير محدودة")],
    [t("Expected travelers", "المسافرون المطلوبون"), booking.expected_travelers],
    [t("Travelers added", "المسافرون المضافون"), r.traveler_count],
    [t("Still to add", "المتبقي إضافتهم"), r.remaining_travelers],
  ];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="font-semibold">{t("Travelers and availability", "المسافرون والأماكن المتاحة")}</h2>
      <dl className="my-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map(([label, value]) => <div key={label} className="rounded-lg bg-slate-50 p-3"><dt className="text-xs text-slate-600">{label}</dt><dd className="mt-1 text-xl font-semibold">{value}</dd></div>)}
      </dl>
      {booking.status === "DRAFT" && <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="mb-4 flex flex-wrap items-end gap-2">
        <label className="text-sm">{t("Number of travelers to book", "عدد المسافرين للحجز")}<input type="number" min={Math.max(1, r.traveler_count)} max={32767} required value={count} onChange={(e) => setCount(e.target.value)} className="mt-1 block w-32 rounded-lg border px-3 py-2" /></label>
        <button disabled={save.isPending || Number(count) === booking.expected_travelers} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">{t("Update booking size", "تحديث عدد المسافرين")}</button>
        <MutationMessage error={save.error} />
      </form>}
      <OperationalSummary report={booking.readiness.structured} />
      <BookingTravelerFlow booking={booking} onChange={onChange} />
      <p className={`text-sm font-medium ${r.validated_travelers === booking.expected_travelers ? "text-emerald-700" : "text-amber-800"}`}>
        {t("Travelers validated", "المسافرون المستوفون للشروط")}: {r.validated_travelers} / {booking.expected_travelers}
      </p>
      {booking.readiness.payment_blockers.length > 0 && <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{t("Payments blocked: every requested traveler needs a valid passport.", "الدفعات محظورة: يحتاج كل مسافر مطلوب إلى جواز صالح.")}</p>}
      {booking.status === "DRAFT" && <>
        <p className="mt-1 text-xs text-slate-500">{t("Every traveler needs a first and last name, birth date, and individual price. Drafts do not reserve places; availability is checked again on confirmation.", "يحتاج كل مسافر إلى الاسم واللقب وتاريخ الميلاد وسعر فردي. المسودات لا تحجز أماكن؛ يُعاد التحقق من التوفر عند التأكيد.")}</p>
        {!c.has_capacity && <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-800">{t("Not enough trip places for this booking. Available for this booking:", "الأماكن غير كافية لهذا الحجز. المتاح لهذا الحجز:")} {c.available_for_booking}</p>}
        <ul className="mt-3 space-y-1 text-sm">
          {r.traveler_validation.map((item) => <li key={item.id} className={item.issues.length ? "text-amber-800" : "text-emerald-700"}>{item.name} · {item.issues.length ? item.issues.map((issue) => ({ "First and last name are required": t(issue, "الاسم واللقب مطلوبان"), "Birth date is required": t(issue, "تاريخ الميلاد مطلوب"), "Individual price is required": t(issue, "السعر الفردي مطلوب"), "Price category does not match traveler": t(issue, "فئة السعر لا تطابق المسافر") }[issue] ?? issue)).join(" · ") : t("Validated", "مستوفٍ للشروط")}</li>)}
        </ul>
      </>}
    </section>
  );
}
