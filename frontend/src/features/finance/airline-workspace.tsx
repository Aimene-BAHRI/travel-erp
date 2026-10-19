"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "@/lib/i18n/context";
import { apiRequest } from "@/lib/api/client";
import { MutationMessage } from "@/components/forms/mutation-message";
import { FormDialog } from "@/components/forms/form-dialog";
import { CashFlowWorkspace } from "./cash-flow-workspace";
import type { Paginated, PaymentMethod } from "@/features/reference/types";
import type { TripRecord, TripFlightRecord } from "@/features/trips/types";

type Row = { category: string; seats: number; price: string | null };
type Pricing = {
  rows: Row[];
  visa_price: string;
  active: boolean;
  quantities_from_bookings: boolean;
  unbooked_seats: number;
  confirmed_counts: Record<string, number>;
  pricing_error: string | null;
  total: string | null;
  paid: string;
  remaining: string | null;
  scheduled: string;
  unscheduled: string | null;
  progress: string;
  installments: {
    id: string;
    date: string | null;
    due_date: string | null;
    is_paid: boolean;
    reference: string;
    amount: string;
    notes: string;
    payment_method: string;
    attachment: string | null;
  }[];
};
const categories = [
  ["ADULT", "Adult", "بالغ"],
  ["CHD", "Child (CHD)", "طفل (CHD)"],
  ["INF", "Infant (INF)", "رضيع (INF)"],
  ["FREE", "Free Ticket", "تذكرة مجانية"],
  ["DISCOUNT_50", "50% Discount", "تخفيض 50%"],
  ["DISCOUNT_60", "60% Discount", "تخفيض 60%"],
  ["DISCOUNT_100", "100% Discount", "تخفيض 100%"],
  ["REV", "REV", "REV"],
  ["SHENTOS", "Shentos", "شنتوس"],
  ["REVALIDATION", "Revalidation", "إعادة المصادقة"],
  ["LESS_10", "Less than 10 days", "أقل من 10 أيام"],
  ["MORE_10", "More than 10 days", "أكثر من 10 أيام"],
  ["INF_SEAT", "Infant with seat", "رضيع بمقعد"],
];
const seatCategories = ["ADULT", "CHD", "INF_SEAT", "FREE", "DISCOUNT_50", "DISCOUNT_60", "DISCOUNT_100"];
const passengerCategories = ["ADULT", "CHD", "INF", "INF_SEAT"];
const input = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2";
const button =
  "rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50";
const money = (value: string | number | null) => value === null ? "—" :
  `${Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Da`;

export function MoneyFlowWorkspace() {
  const { locale } = useLocale();
  const t = (en: string, ar: string) => (locale === "ar" ? ar : en);
  const [tab, setTab] = useState(() => typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("tab") || "cash" : "cash");
  return (
    <div className="space-y-6">
      <nav
        aria-label={t("Money flow sections", "أقسام التدفقات المالية")}
        className="flex flex-wrap gap-2 print:hidden"
      >
        {[
          ["cash", "Cash flow", "حركة الصندوق"],
          ["pricing", "Airline pricings", "أسعار الطيران"],
          ["installments", "Airline installments", "أقساط الطيران"],
        ].map(([key, en, ar]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            aria-pressed={tab === key}
            className={
              tab === key
                ? button
                : "rounded-lg border bg-white px-4 py-2 text-sm"
            }
          >
            {t(en, ar)}
          </button>
        ))}
      </nav>
      {tab === "cash" ? <CashFlowWorkspace /> : <AirlineWorkspace mode={tab} />}
    </div>
  );
}

function AirlineWorkspace({ mode }: { mode: string }) {
  const { locale } = useLocale();
  const t = (en: string, ar: string) => (locale === "ar" ? ar : en);
  const [tripId, setTripId] = useState(() => typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("trip") || "" : "");
  const [page, setPage] = useState(1);
  const trips = useQuery({
    queryKey: ["airline-trips", page],
    queryFn: () =>
      apiRequest<Paginated<TripRecord>>(
        `/trips/?ordering=-departure_date&page=${page}`,
      ),
  });
  const selectedTrip = useQuery({
    queryKey: ["airline-selected-trip", tripId],
    queryFn: () => apiRequest<TripRecord>(`/trips/${tripId}/`),
    enabled: !!tripId,
  });
  const trip = selectedTrip.data ?? trips.data?.results.find((item) => item.id === tripId);
  return (
    <div className="space-y-5">
      <div className="flex items-end gap-3 print:hidden">
        <label className="block flex-1 text-sm font-medium">
          {t("Trip", "الرحلة")}
          <select
            className={`${input} mt-2`}
            value={tripId}
            onChange={(e) => setTripId(e.target.value)}
          >
            <option value="">{t("Select a trip", "اختر رحلة")}</option>
            {trip && !trips.data?.results.some((item) => item.id === trip.id) && <option value={trip.id}>{trip.name}</option>}
            {trips.data?.results.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.departure_date}
              </option>
            ))}
          </select>
        </label>
        <button
          disabled={page === 1}
          className={button}
          onClick={() => {
            setPage(page - 1);
            setTripId("");
          }}
        >
          ←
        </button>
        <button
          disabled={!trips.data?.next}
          className={button}
          onClick={() => {
            setPage(page + 1);
            setTripId("");
          }}
        >
          →
        </button>
      </div>
      <MutationMessage error={trips.error} />
      {trips.isPending && <p>{t("Loading…", "جار التحميل…")}</p>}
      {trip ? (
        <TripAirline key={trip.id} trip={trip} mode={mode} />
      ) : (
        <p className="rounded-xl border bg-white p-8 text-slate-500">
          {t(
            "Select a trip to manage airline pricing and payments.",
            "اختر رحلة لإدارة أسعار وأقساط الطيران.",
          )}
        </p>
      )}
    </div>
  );
}

function TripAirline({ trip, mode }: { trip: TripRecord; mode: string }) {
  const { locale } = useLocale();
  const t = (en: string, ar: string) => (locale === "ar" ? ar : en);
  const cache = useQueryClient();
  const [draft, setDraft] = useState<{
    rows: Row[];
    visa_price: string;
  } | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<
    Pricing["installments"][number] | null
  >(null);
  const [markingPaid, setMarkingPaid] = useState(false);
  const [saved, setSaved] = useState(false);
  const [payment, setPayment] = useState({
    due_date: "",
    entry_date: new Date().toLocaleDateString("en-CA"),
    reference: "",
    amount: "",
    notes: "",
    payment_method: "",
  });
  const [attachment, setAttachment] = useState<File | null>(null);
  const query = useQuery({
    queryKey: ["airline-finance", trip.id],
    queryFn: () => apiRequest<Pricing>(`/finance/airlines/${trip.id}/`),
  });
  const flights = useQuery({
    queryKey: ["trip-flights", trip.id],
    queryFn: () =>
      apiRequest<Paginated<TripFlightRecord>>(
        `/trips/flights/?trip=${trip.id}`,
      ),
  });
  const methods = useQuery({
    queryKey: ["payment-methods"],
    queryFn: () =>
      apiRequest<Paginated<PaymentMethod>>("/reference/payment-methods/"),
  });
  const refresh = (data: Pricing) => {
    cache.setQueryData(["airline-finance", trip.id], data);
    cache.invalidateQueries({ queryKey: ["cash-flow-report"] });
    cache.invalidateQueries({ queryKey: ["notifications"] });
    cache.invalidateQueries({ queryKey: ["occupancy-packages", trip.id] });
  };
  const save = useMutation({
    mutationFn: () =>
      apiRequest<Pricing>(`/finance/airlines/${trip.id}/`, {
        method: "PUT",
        body: JSON.stringify(draft ?? query.data),
      }),
    onSuccess: (data) => {
      refresh(data);
      setDraft(null);
      setSaved(true);
    },
  });
  const pay = useMutation({
    mutationFn: () => {
      const body = new FormData();
      Object.entries(payment).forEach(([key, value]) =>
        body.append(key, value),
      );
      if (attachment) body.append("attachment", attachment);
      return apiRequest<Pricing>(`/finance/airlines/${trip.id}/schedule-installment/`, {
        method: "POST",
        body,
      });
    },
    onSuccess: (data) => {
      refresh(data);
      setOpen(false);
    },
  });
  const updateInstallment = useMutation({
    mutationFn: () => {
      const body = new FormData();
      Object.entries(payment).forEach(([key, value]) =>
        body.append(key, value),
      );
      if (attachment) body.append("attachment", attachment);
      return apiRequest<Pricing>(
        `/finance/airlines/${trip.id}/installments/${editing?.id}/${markingPaid ? "pay/" : ""}`,
        { method: markingPaid ? "POST" : "PATCH", body },
      );
    },
    onSuccess: (data) => {
      refresh(data);
      setEditing(null);
      setOpen(false);
    },
  });
  const removeInstallment = useMutation({
    mutationFn: (id: string) =>
      apiRequest<Pricing>(`/finance/airlines/${trip.id}/installments/${id}/`, {
        method: "DELETE",
      }),
    onSuccess: refresh,
  });
  if (query.isPending) return <p>{t("Loading…", "جار التحميل…")}</p>;
  if (!query.data) return <MutationMessage error={query.error} />;
  const data = query.data;
  const current = draft ?? data;
  const seats = current.rows
    .filter(
      (row) =>
        seatCategories.includes(row.category),
    )
    .reduce((sum, row) => sum + row.seats, 0);
  const totalCents = current.rows.reduce(
    (sum, row) => sum + row.seats * Math.round(Number(row.price) * 100),
    0,
  );
  const missingFare = current.rows.some(row => row.seats > 0 && (row.price === null || row.price === ""));
  const unbookedSeats = Math.max(0, (current.rows.find(row => row.category === "ADULT")?.seats ?? 0) - (data.confirmed_counts.ADULT ?? 0));
  const flight = flights.data?.results[0];
  const edit = (index: number, field: "seats" | "price", value: string) => {
    setSaved(false);
    const rows = current.rows.map((row, i) => i === index
      ? { ...row, [field]: field === "seats" ? Number(value) : value === "" ? null : value }
      : { ...row });
    if (trip.max_travelers !== null) {
      const otherSeats = rows.filter(row => seatCategories.includes(row.category) && row.category !== "ADULT")
        .reduce((sum, row) => sum + row.seats, 0);
      const adult = rows.find(row => row.category === "ADULT");
      if (adult) adult.seats = Math.max(data.confirmed_counts.ADULT ?? 0, trip.max_travelers - otherSeats);
    }
    setDraft({
      ...current,
      rows,
    });
  };
  return (
    <section
      id="airline-print"
      className="rounded-xl border bg-white p-5 sm:p-6"
    >
      <style>{`@media print { body * { visibility: hidden; } #airline-print, #airline-print * { visibility: visible; } #airline-print { position: absolute; inset: 0; border: 0; } #airline-print .print\\:hidden { display: none; } }`}</style>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">
            {mode === "pricing"
              ? t("Default Pricing", "التسعير الافتراضي")
              : t("Airline installments", "أقساط الطيران")}
          </h2>
          <p className="mt-2 font-medium">
            {flight?.flight_number || trip.code}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            {flight?.origin_airport_code || "—"} · {trip.departure_date} ·{" "}
            {trip.max_travelers ?? "—"} {t("seats", "مقعد")} · {trip.name}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs text-cyan-900">
            {data.active
              ? t("Defaults active", "الأسعار الافتراضية مفعلة")
              : t("Not configured", "غير محدد")}
          </span>
          <button
            className="rounded-lg border px-3 py-2 text-sm print:hidden"
            onClick={() => window.print()}
          >
            {t("Export PDF", "تصدير PDF")}
          </button>
        </div>
      </header>
      {data.pricing_error && <p role="alert" className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{data.pricing_error}</p>}
      {trip.max_travelers === null && <p role="status" className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{t("Set trip seats in the trip profile to include unbooked seats in the flight estimate.", "حدد عدد المقاعد في بيانات الرحلة لاحتساب المقاعد غير المحجوزة ضمن تكلفة الطيران.")}</p>}
      {mode === "pricing" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
          className="space-y-6"
        >
          <div className="overflow-x-auto">
            <table className="w-full text-start text-sm">
              <thead>
                <tr className="border-b text-slate-500">
                  {[
                    t("Category", "الفئة"),
                    t("Seats / quantity", "المقاعد / العدد"),
                    t("Price per passenger", "السعر للفرد"),
                  ].map((label) => (
                    <th key={label} className="p-3 text-start">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {current.rows.map((row, index) => {
                  const category = categories.find(
                    (item) => item[0] === row.category,
                  )!;
                  return (
                    <tr
                      key={row.category}
                      className="border-b border-slate-100"
                    >
                      <td className="p-3">
                        {t(category[1], category[2])}
                        {row.category === "ADULT" && trip.max_travelers !== null && <p className="mt-1 text-xs text-slate-500">{t("Confirmed adults + unbooked seats", "البالغون المؤكدون + المقاعد غير المحجوزة")}</p>}
                        {categories.indexOf(category) >= 7 && row.category !== "INF_SEAT" && (
                          <span className="ms-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">
                            {t("Penalty", "غرامة")}
                          </span>
                        )}
                      </td>
                      <td className="p-3">
                        <input
                          aria-label={`${category[1]} quantity`}
                          className={`${input} max-w-32`}
                          required
                          type="number"
                          min="0"
                          max="65535"
                          step="1"
                          disabled={data.quantities_from_bookings && passengerCategories.includes(row.category)}
                          value={row.seats}
                          onChange={(e) => edit(index, "seats", e.target.value)}
                        />
                      </td>
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          <input
                            aria-label={`${category[1]} price`}
                            className={`${input} max-w-48`}
                            required={!["CHD", "INF", "INF_SEAT"].includes(row.category) || row.seats > 0}
                            type="number"
                            min="0"
                            step="0.01"
                            value={row.price ?? ""}
                            onChange={(e) =>
                              edit(index, "price", e.target.value)
                            }
                          />
                          <span>Da</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="grid gap-4 rounded-xl bg-slate-50 p-4 sm:grid-cols-2">
            <div>
              {t("Seats allocated", "المقاعد المخصصة")}
              <p className="mt-1 text-xl font-semibold">
                {seats} / {trip.max_travelers ?? "—"}
              </p>
              <p className="text-xs text-slate-500">
                {t(
                  "Infants with seats count toward capacity. Infants without seats and penalties do not.",
                  "الرضع بمقاعد يحتسبون ضمن السعة. الرضع دون مقاعد والغرامات لا تستهلك مقاعد.",
                )}
              </p>
            </div>
            <div>
              {t("Total flight price", "تكلفة الطيران")}
              <p className="mt-1 text-xl font-semibold">
                {missingFare ? t("Fare required", "التسعيرة مطلوبة") : money(totalCents / 100)}
              </p>
            </div>
          </div>
          <p className="text-sm text-slate-500">
            {t(
              "Only confirmed and completed bookings update passenger quantities. Adult quantity includes unbooked seats at the adult fare. Drafts, cancellations and visa-only travelers are excluded. Free and discounted tickets reserve separate seats; do not also include those passengers as full-fare bookings.",
              "تحدث الحجوزات المؤكدة والمكتملة فقط أعداد المسافرين. يشمل عدد البالغين المقاعد غير المحجوزة بسعر البالغ. تستثنى المسودات والإلغاءات وخدمة التأشيرة فقط. التذاكر المجانية والمخفضة تحجز مقاعد مستقلة ولا يجب احتساب أصحابها مرة أخرى بالسعر الكامل.",
            )}
          </p>
          <p className="text-sm text-slate-600">{t("Unbooked seats priced as adults", "مقاعد غير محجوزة بسعر البالغ")}: {trip.max_travelers === null ? "—" : unbookedSeats}</p>
          <div className="border-t pt-5">
            <label className="block font-medium">
              {t("Visa price", "سعر التأشيرة")}
              <input
                className={`${input} mt-2 max-w-xs`}
                type="number"
                required
                min="0"
                step="0.01"
                value={current.visa_price}
                onChange={(e) => {
                  setSaved(false);
                  setDraft({ ...current, visa_price: e.target.value });
                }}
              />
            </label>
            <p className="mt-2 text-sm text-slate-500">
              {t(
                "Applies to Adult, CHD and INF in component-based package calculations.",
                "يطبق على البالغين والأطفال والرضع في حساب الباقات المعتمدة على مكونات التكلفة.",
              )}
            </p>
          </div>
          <MutationMessage error={save.error} />
          {saved && (
            <p role="status" className="text-green-700">
              {t("Defaults saved.", "تم حفظ الأسعار.")}
            </p>
          )}
          <button
            disabled={
              save.isPending ||
              (trip.max_travelers !== null && seats > trip.max_travelers)
            }
            className={`${button} print:hidden`}
          >
            {t("Save defaults", "حفظ الأسعار الافتراضية")}
          </button>
        </form>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              [t("Total flight cost", "التكلفة الإجمالية"), data.total],
              [t("Paid", "المدفوع"), data.paid],
              [t("Remaining", "المتبقي"), data.remaining],
              [t("Scheduled unpaid", "أقساط مجدولة غير مدفوعة"), data.scheduled],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl bg-slate-50 p-5">
                <p className="text-sm text-slate-500">{label}</p>
                <p className="mt-2 text-xl font-semibold">{money(value)}</p>
              </div>
            ))}
          </div>
          <div>
            <div className="mb-2 flex justify-between text-sm">
              <span>{t("Progress", "التقدم")}</span>
              <span>{Number(data.progress).toFixed(2)}%</span>
            </div>
            <progress
              className="h-3 w-full accent-cyan-800"
              value={Math.min(100, Number(data.progress))}
              max="100"
            />
          </div>
          <MutationMessage error={removeInstallment.error} />
          {Number(data.remaining) < 0 && (
            <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
              {t(
                "Recorded payments exceed the current flight total. Review booking quantities and prices. You can still edit existing installments without increasing their amounts.",
                "المدفوعات المسجلة تتجاوز تكلفة الطيران الحالية. راجع أعداد المسافرين والأسعار. يمكنك تعديل الأقساط الحالية دون زيادة مبالغها.",
              )}
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  {[
                    "#",
                    t("Payment date", "التاريخ"),
                    t("Due date", "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0627\u0633\u062a\u062d\u0642\u0627\u0642"),
                    t("Status", "\u0627\u0644\u062d\u0627\u0644\u0629"),
                    t("Reference", "المرجع"),
                    t("Amount (DZD)", "المبلغ (د.ج)"),
                    t("Note", "ملاحظة"),
                    t("Attachment", "مرفق"),
                    t("Actions", "إجراءات"),
                  ].map((label) => (
                    <th key={label} className="p-3 text-start">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.installments.map((item, index) => (
                  <tr key={item.id} className="border-b">
                    <td className="p-3">{index + 1}</td>
                    <td className="p-3">{item.date || "?"}</td>
                    <td className="p-3">{item.due_date || "?"}</td>
                    <td className="p-3">{item.is_paid ? t("Paid", "\u0645\u062f\u0641\u0648\u0639") : t("Unpaid", "\u063a\u064a\u0631 \u0645\u062f\u0641\u0648\u0639")}</td>
                    <td className="p-3">{item.reference || "—"}</td>
                    <td className="p-3 whitespace-nowrap">
                      {money(item.amount)}
                    </td>
                    <td className="p-3">{item.notes || "—"}</td>
                    <td className="p-3">
                      {item.attachment ? (
                        <a
                          className="text-cyan-800 underline"
                          href={item.attachment}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {t("View", "عرض")}
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="p-3 whitespace-nowrap print:hidden">
                      {!item.is_paid && <button className="me-2 text-green-700 underline" onClick={() => {
                        setEditing(item); setMarkingPaid(true);
                        setPayment({ due_date: item.due_date || "", entry_date: new Date().toLocaleDateString("en-CA"), amount: item.amount, reference: item.reference, notes: item.notes, payment_method: methods.data?.results[0]?.id ?? "" });
                        setAttachment(null); updateInstallment.reset(); setOpen(true);
                      }}>{t("Mark paid", "\u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u0641\u0639")}</button>}
                      <button
                        className="me-2 text-cyan-800 underline"
                        onClick={() => {
                          setMarkingPaid(false);
                          setEditing(item);
                          setPayment({
                            due_date: item.due_date || "",
                            entry_date: item.date || new Date().toLocaleDateString("en-CA"),
                            reference: item.reference,
                            amount: item.amount,
                            notes: item.notes,
                            payment_method:
                              item.payment_method ??
                              methods.data?.results[0]?.id ??
                              "",
                          });
                          setAttachment(null);
                          updateInstallment.reset();
                          setOpen(true);
                        }}
                      >
                        {t("Edit", "تعديل")}
                      </button>
                      <button
                        className="text-red-700 underline disabled:opacity-50"
                        disabled={removeInstallment.isPending}
                        onClick={() => {
                          if (
                            window.confirm(
                              t("Delete this installment?", "حذف هذا القسط؟"),
                            )
                          ) {
                            removeInstallment.mutate(item.id);
                          }
                        }}
                      >
                        {t("Delete", "حذف")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!data.installments.length && (
              <p className="p-6 text-center text-slate-500">
                {t("No installments recorded.", "لم تسجل أقساط بعد.")}
              </p>
            )}
          </div>
          <button
            className={`${button} print:hidden`}
            disabled={!data.active || Number(data.unscheduled) <= 0}
            onClick={() => {
              setPayment({
                due_date: "",
                entry_date: new Date().toLocaleDateString("en-CA"),
                reference: "",
                amount: "",
                notes: "",
                payment_method: methods.data?.results[0]?.id ?? "",
              });
              setAttachment(null);
              setEditing(null);
              setMarkingPaid(false);
              pay.reset();
              setOpen(true);
            }}
          >
            {t("Schedule installment", "جدولة قسط")}
          </button>
          {!data.active && (
            <p className="text-sm text-amber-800">
              {t(
                "Save airline pricing before recording payments.",
                "احفظ أسعار الطيران قبل تسجيل الأقساط.",
              )}
            </p>
          )}
        </div>
      )}
      <FormDialog
        open={open}
        onClose={() => setOpen(false)}
        title={markingPaid ? t("Mark installment paid", "\u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u0641\u0639") :
          editing
            ? t("Edit installment", "تعديل القسط")
            : t("Add installment", "إضافة قسط")
        }
      >
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (editing) updateInstallment.mutate();
            else pay.mutate();
          }}
        >
          {(
            [
              ["due_date", "Due date", "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0627\u0633\u062a\u062d\u0642\u0627\u0642", "date"],
              ["entry_date", "Date", "التاريخ", "date"],
              ["reference", "Reference", "المرجع", "text"],
              ["amount", "Amount (DZD)", "المبلغ (د.ج)", "number"],
              ["notes", "Note", "ملاحظة", "text"],
            ] as const
          ).filter(([key]) => markingPaid ? key === "entry_date" : key !== "entry_date" || editing?.is_paid).map(([key, en, ar, type]) => (
            <label key={key} className="block text-sm">
              {t(en, ar)}
              <input
                className={`${input} mt-1`}
                type={type}
                required={key === "entry_date" || key === "amount" || (key === "due_date" && !editing?.is_paid)}
                min={key === "amount" ? "0.01" : undefined}
                max={
                  key === "amount"
                    ? String(
                        Math.max(
                          0.01,
                          Number(editing?.amount ?? 0),
                          Number(data.remaining) - (editing?.is_paid ? 0 : Number(data.scheduled)) + Number(editing?.amount ?? 0),
                        ),
                      )
                    : undefined
                }
                step={key === "amount" ? "0.01" : undefined}
                value={payment[key]}
                onChange={(e) =>
                  setPayment({ ...payment, [key]: e.target.value })
                }
              />
            </label>
          ))}
          {(markingPaid || editing?.is_paid) && <label className="block text-sm">
            {t("Payment method", "طريقة الدفع")}
            <select
              required
              className={`${input} mt-1`}
              value={payment.payment_method}
              onChange={(e) =>
                setPayment({ ...payment, payment_method: e.target.value })
              }
            >
              <option value="">{t("Select", "اختر")}</option>
              {methods.data?.results.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>}
          <label className="block text-sm">
            {t(
              "Attachment (PDF, JPG, PNG; max 10 MB)",
              "مرفق (PDF، JPG، PNG؛ حتى 10 ميغابايت)",
            )}
            <input
              className={`${input} mt-1`}
              type="file"
              accept="application/pdf,image/jpeg,image/png"
              onChange={(e) => setAttachment(e.target.files?.[0] ?? null)}
            />
          </label>
          <MutationMessage
            error={
              pay.error ||
              updateInstallment.error ||
              removeInstallment.error ||
              methods.error
            }
          />
          <button
            disabled={pay.isPending || updateInstallment.isPending}
            className={button}
          >
            {markingPaid ? t("Confirm payment", "\u062a\u0623\u0643\u064a\u062f \u0627\u0644\u062f\u0641\u0639") : editing
              ? t("Save changes", "حفظ التعديلات")
              : t("Save installment", "حفظ القسط")}
          </button>
        </form>
      </FormDialog>
    </section>
  );
}
