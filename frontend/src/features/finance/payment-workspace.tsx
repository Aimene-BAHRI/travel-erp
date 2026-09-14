"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Clock3,
  CreditCard,
  LoaderCircle,
  Printer,
  ReceiptText,
  RotateCcw,
  X,
} from "lucide-react";
import { useState } from "react";

import { AgencyDocumentHeader } from "@/components/documents/agency-document-header";
import type { BookingRecord } from "@/features/bookings/types";
import type { AgencyCurrency, Paginated, PaymentMethod } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";

import type { FinancialSummary, FinancialTransactionRecord, PaymentReceipt } from "./types";

const text = {
  ar: {
    booking: "الحجز",
    selectBooking: "اختر حجزا مؤكدا",
    bookingTotal: "إجمالي الحجز",
    netPaid: "صافي المدفوع",
    remainingBalance: "الرصيد المتبقي",
    postTitle: "تسجيل دفعة أو استرجاع",
    postHelp: "سجل المبلغ، ثم يمكنك ربطه بكل مسافر على حدة.",
    amount: "المبلغ المستلم",
    rate: "الصرف إلى عملة الحجز",
    method: "طريقة الدفع",
    reference: "رقم المرجع",
    allocate: "ربط المبلغ بالمسافرين",
    allocateHelp: "اترك الحقول فارغة إذا كانت الدفعة جماعية بدون تخصيص.",
    allocated: "مخصص",
    due: "المتبقي",
    travelerAmount: "المبلغ المدفوع من هذا المسافر",
    postPayment: "تسجيل دفعة",
    postRefund: "تسجيل استرجاع",
    ledger: "السجل المالي غير القابل للتعديل",
    receipt: "وصل",
    reverse: "عكس القيد",
    rejected: "تم رفض العملية. تحقق من المبالغ، التخصيصات، العملة، وسجل العمليات.",
    allocationTitle: "تخصيص المدفوعات",
    allocationHelp: "إلى من تم ربط المبلغ المدفوع حتى الآن.",
    paid: "مدفوع",
    remaining: "متبقي",
    unallocated: "دفعة غير مخصصة",
  },
  en: {
    booking: "Booking",
    selectBooking: "Select a confirmed booking",
    bookingTotal: "Booking total",
    netPaid: "Net paid",
    remainingBalance: "Remaining balance",
    postTitle: "Post payment or refund",
    postHelp: "Record the receipt, then optionally split it between individual travelers.",
    amount: "Amount received",
    rate: "Rate to booking currency",
    method: "Payment method",
    reference: "Reference number",
    allocate: "Allocate to travelers",
    allocateHelp: "Leave every field empty for an unallocated group payment.",
    allocated: "Allocated",
    due: "Due",
    travelerAmount: "Amount paid by this traveler",
    postPayment: "Post payment",
    postRefund: "Post refund",
    ledger: "Immutable ledger",
    receipt: "Receipt",
    reverse: "Reverse",
    rejected: "The operation was rejected. Check the amounts, allocations, currency rate, and history.",
    allocationTitle: "Payment allocation",
    allocationHelp: "Who the amount paid so far is linked to.",
    paid: "paid",
    remaining: "remaining",
    unallocated: "Unallocated payment",
  },
};

export function PaymentWorkspace() {
  const { locale } = useLocale();
  const copy = text[locale];
  const paymentUi = {
    allocationWarning:
      locale === "ar"
        ? "تنبيه: المبلغ غير موزع بالكامل على المسافرين."
        : "Warning: this payment is not fully allocated to travelers.",
    close: locale === "ar" ? "إغلاق" : "Close",
    createdAt: locale === "ar" ? "وقت التسجيل" : "Posted",
    printReceipt: locale === "ar" ? "طباعة الوصل" : "Print receipt",
    receiptPreview: locale === "ar" ? "معاينة الوصل" : "Receipt preview",
  };
  const cache = useQueryClient();
  const [bookingId, setBookingId] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("");
  const [rate, setRate] = useState("1");
  const [method, setMethod] = useState("");
  const [reference, setReference] = useState("");
  const [allocations, setAllocations] = useState<Record<string, string>>({});
  const [receipt, setReceipt] = useState<PaymentReceipt | null>(null);
  const bookings = useQuery({
    queryKey: ["payment-bookings"],
    queryFn: () => apiRequest<Paginated<BookingRecord>>("/bookings/?status=CONFIRMED"),
  });
  const currencies = useQuery({
    queryKey: ["agency-currencies"],
    queryFn: () => apiRequest<Paginated<AgencyCurrency>>("/reference/agency-currencies/"),
  });
  const methods = useQuery({
    queryKey: ["payment-methods"],
    queryFn: () => apiRequest<Paginated<PaymentMethod>>("/reference/payment-methods/"),
  });
  const summary = useQuery({
    queryKey: ["financial-summary", bookingId],
    enabled: Boolean(bookingId),
    queryFn: () =>
      apiRequest<FinancialSummary>(`/finance/transactions/booking-summary/?booking=${bookingId}`),
  });
  const ledger = useQuery({
    queryKey: ["financial-ledger", bookingId],
    enabled: Boolean(bookingId),
    queryFn: () =>
      apiRequest<Paginated<FinancialTransactionRecord>>(
        `/finance/transactions/?booking=${bookingId}&ordering=-transaction_date`,
      ),
  });
  const refresh = () => {
    cache.invalidateQueries({ queryKey: ["financial-summary", bookingId] });
    cache.invalidateQueries({ queryKey: ["financial-ledger", bookingId] });
    setAmount("");
    setReference("");
    setAllocations({});
  };
  const allocationPayload = Object.entries(allocations)
    .filter(([, value]) => Number(value) > 0)
    .map(([booking_traveler, value]) => ({ booking_traveler, amount: value }));
  const post = useMutation({
    mutationFn: (kind: "payments" | "refunds") =>
      apiRequest<FinancialTransactionRecord>(`/finance/transactions/${kind}/`, {
        method: "POST",
        body: JSON.stringify({
          booking: bookingId,
          amount,
          currency,
          booking_exchange_rate: rate,
          payment_method: method,
          transaction_date: new Date().toISOString().slice(0, 10),
          reference,
          allocations: allocationPayload,
        }),
      }),
    onSuccess: refresh,
  });
  const reverse = useMutation({
    mutationFn: (id: string) =>
      apiRequest<FinancialTransactionRecord>(`/finance/transactions/${id}/reverse/`, {
        method: "POST",
        body: JSON.stringify({
          transaction_date: new Date().toISOString().slice(0, 10),
          reason: "Operator correction",
        }),
      }),
    onSuccess: refresh,
  });
  const printReceipt = useMutation({
    mutationFn: (id: string) => apiRequest<PaymentReceipt>(`/finance/transactions/${id}/receipt/`),
    onSuccess: setReceipt,
  });
  const selected = bookings.data?.results.find((item) => item.id === bookingId);
  const chooseBooking = (id: string) => {
    setBookingId(id);
    setAllocations({});
    const booking = bookings.data?.results.find((item) => item.id === id);
    if (booking) {
      setCurrency(booking.currency_code);
      setRate("1");
    }
  };
  const allocationTotal = allocationPayload.reduce((sum, item) => sum + Number(item.amount), 0);
  const bookingAmount = Number(amount || 0) * Number(rate || 0);
  const allocationsValid =
    !allocationPayload.length || Math.abs(allocationTotal - bookingAmount) < 0.0001;
  const dateTimeLocale = locale === "ar" ? "ar-DZ" : "en";

  if (bookings.isPending) {
    return (
      <div className="grid min-h-72 place-items-center">
        <LoaderCircle className="size-8 animate-spin text-cyan-800" />
      </div>
    );
  }

  return (
    <>
      <div className="no-print space-y-6">
        <section className="rounded-xl border bg-white p-5">
          <label className="text-sm font-medium">{copy.booking}</label>
          <select
            value={bookingId}
            onChange={(event) => chooseBooking(event.target.value)}
            className="mt-2 w-full rounded-lg border px-3 py-2"
          >
            <option value="">{copy.selectBooking}</option>
            {bookings.data?.results.map((booking) => (
              <option key={booking.id} value={booking.id}>
                {booking.code} · {booking.customer_name} · {booking.trip_name}
              </option>
            ))}
          </select>
        </section>
        {bookingId && (
          <>
            <section className="grid gap-4 md:grid-cols-3">
              <Metric label={copy.bookingTotal} value={summary.data?.booking_total} currency={summary.data?.currency} />
              <Metric label={copy.netPaid} value={summary.data?.paid_amount} currency={summary.data?.currency} tone="emerald" />
              <Metric label={copy.remainingBalance} value={summary.data?.remaining_amount} currency={summary.data?.currency} tone="amber" />
            </section>
            {summary.data && <PaymentAllocationBreakdown summary={summary.data} copy={copy} />}
            <section className="rounded-xl border bg-white">
              <header className="border-b p-5">
                <h2 className="flex items-center gap-2 font-semibold">
                  <CreditCard className="size-5 text-cyan-700" />
                  {copy.postTitle}
                </h2>
                <p className="text-sm text-slate-500">{copy.postHelp}</p>
              </header>
              <div className="grid gap-3 p-5 md:grid-cols-5">
                <Input value={amount} setValue={setAmount} placeholder={copy.amount} type="number" />
                <select
                  value={currency}
                  onChange={(event) => {
                    setCurrency(event.target.value);
                    if (event.target.value === selected?.currency_code) setRate("1");
                  }}
                  className="rounded-lg border px-3 py-2 text-sm"
                >
                  {currencies.data?.results
                    .filter((item) => item.is_enabled)
                    .map((item) => (
                      <option key={item.id} value={item.currency}>{item.currency}</option>
                    ))}
                </select>
                <Input value={rate} setValue={setRate} placeholder={copy.rate} type="number" />
                <select value={method} onChange={(event) => setMethod(event.target.value)} className="rounded-lg border px-3 py-2 text-sm">
                  <option value="">{copy.method}</option>
                  {methods.data?.results.map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </select>
                <Input value={reference} setValue={setReference} placeholder={copy.reference} />
              </div>
              {!!summary.data?.traveler_balances.length && (
                <div className="border-t p-5">
                  <div className="mb-3 flex justify-between">
                    <div>
                      <h3 className="font-medium">{copy.allocate}</h3>
                      <p className="text-xs text-slate-500">{copy.allocateHelp}</p>
                    </div>
                    <div className="text-sm">
                      <p className={allocationsValid ? "text-emerald-700" : "text-red-700"}>
                        {copy.allocated} {allocationTotal.toFixed(2)} / {bookingAmount.toFixed(2)}{" "}
                        {selected?.currency_code}
                      </p>
                      {!allocationsValid && (
                        <p className="mt-1 text-xs text-red-700">{paymentUi.allocationWarning}</p>
                      )}
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    {summary.data.traveler_balances.map((traveler) => (
                      <label key={traveler.booking_traveler} className="rounded-lg border p-3 text-sm">
                        <span className="flex justify-between">
                          <b>{traveler.traveler_name}</b>
                          <span>{copy.due} {traveler.remaining_amount}</span>
                        </span>
                        <input
                          type="number"
                          min="0"
                          step="0.0001"
                          value={allocations[traveler.booking_traveler] ?? ""}
                          onChange={(event) =>
                            setAllocations({
                              ...allocations,
                              [traveler.booking_traveler]: event.target.value,
                            })
                          }
                          placeholder={copy.travelerAmount}
                          className="mt-2 w-full rounded-lg border px-3 py-2"
                        />
                      </label>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex gap-2 px-5 pb-5">
                {Boolean(selected?.readiness.payment_blockers.length) && <p className="text-sm text-amber-800">{locale === "ar" ? "???? ?????? ???? ????????? ??? ????? ????." : "Complete valid passports for all requested travelers before recording payment."}</p>}
                <Action onClick={() => post.mutate("payments")} disabled={!amount || !currency || !method || !allocationsValid || post.isPending || Boolean(selected?.readiness.payment_blockers.length)}>
                  <ArrowDownLeft className="size-4" />
                  {copy.postPayment}
                </Action>
                <button
                  onClick={() => post.mutate("refunds")}
                  disabled={!amount || !currency || !method || !allocationsValid || post.isPending}
                  className="flex items-center gap-2 rounded-lg border border-amber-300 px-4 py-2 text-sm font-medium text-amber-800 disabled:opacity-50"
                >
                  <ArrowUpRight className="size-4" />
                  {copy.postRefund}
                </button>
              </div>
            </section>
            <section className="rounded-xl border bg-white">
              <header className="border-b p-5">
                <h2 className="flex items-center gap-2 font-semibold">
                  <ReceiptText className="size-5 text-cyan-700" />
                  {copy.ledger}
                </h2>
              </header>
              <div className="divide-y">
                {ledger.data?.results.map((item) => (
                  <div key={item.id} className="grid gap-3 p-5 md:grid-cols-[1fr_auto_auto]">
                    <div>
                      <p className="font-medium">{item.number}</p>
                      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                        <span>{item.transaction_date}</span>
                        <span>{item.payment_method_name}</span>
                        <span>
                          {item.amount} {item.currency_code}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <Clock3 className="size-3" />
                          {paymentUi.createdAt}:{" "}
                          {new Intl.DateTimeFormat(dateTimeLocale, {
                            dateStyle: "medium",
                            timeStyle: "short",
                          }).format(new Date(item.created_at))}
                        </span>
                      </div>
                      {item.allocations.map((allocation) => (
                        <p key={allocation.id} className="text-xs text-cyan-800">
                          {allocation.traveler_name}: {allocation.amount} {item.booking_currency_code}
                        </p>
                      ))}
                    </div>
                    <p className="font-semibold">
                      {item.signed_booking_amount} {item.booking_currency_code}
                    </p>
                    <div className="flex flex-wrap gap-3">
                      {item.kind === "PAYMENT" && (
                        <button onClick={() => printReceipt.mutate(item.id)} className="flex items-center gap-1 text-sm text-cyan-800">
                          <Printer className="size-4" />
                          {copy.receipt}
                        </button>
                      )}
                      {item.kind !== "REVERSAL" && (
                        <button onClick={() => reverse.mutate(item.id)} className="flex items-center gap-1 text-sm">
                          <RotateCcw className="size-4" />
                          {copy.reverse}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
        {(post.isError || reverse.isError || printReceipt.isError) && (
          <p className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{copy.rejected}</p>
        )}
      </div>
      {receipt && (
        <>
          <PaymentReceiptPreview
            copy={paymentUi}
            onClose={() => setReceipt(null)}
            receipt={receipt}
          />
          <PaymentReceiptPrint receipt={receipt} />
        </>
      )}
    </>
  );
}

function PaymentReceiptPreview({
  copy,
  onClose,
  receipt,
}: Readonly<{
  copy: {
    close: string;
    printReceipt: string;
    receiptPreview: string;
  };
  onClose: () => void;
  receipt: PaymentReceipt;
}>) {
  const print = () => {
    window.setTimeout(() => {
      const logo = document.querySelector<HTMLImageElement>(".print-only img");
      if (logo && !logo.complete) {
        const trigger = () => window.print();
        logo.addEventListener("load", trigger, { once: true });
        logo.addEventListener("error", trigger, { once: true });
      } else {
        window.print();
      }
    }, 100);
  };

  return (
    <div className="no-print fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 p-3 sm:p-6">
      <div className="mx-auto max-w-4xl rounded-2xl bg-white shadow-2xl">
        <header className="sticky top-0 z-10 flex flex-col gap-3 border-b bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <h2 className="font-semibold">{copy.receiptPreview}</h2>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={print}
              className="inline-flex items-center gap-2 rounded-lg bg-cyan-800 px-3 py-2 text-sm font-medium text-white"
            >
              <Printer className="size-4" />
              {copy.printReceipt}
            </button>
            <button
              onClick={onClose}
              className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"
            >
              <X className="size-4" />
              {copy.close}
            </button>
          </div>
        </header>
        <PaymentReceiptPrint preview receipt={receipt} />
      </div>
    </div>
  );
}

function PaymentReceiptPrint({
  preview = false,
  receipt,
}: Readonly<{ preview?: boolean; receipt: PaymentReceipt }>) {
  const uiText = useUiText();
  const copies = [
    { label: uiText("Client copy"), tone: "bg-cyan-50 text-cyan-800" },
    { label: uiText("Accountant copy"), tone: "bg-amber-50 text-amber-800" },
  ];

  return (
    <article
      className={`receipt-sheet ${preview ? "mx-auto max-w-3xl p-4 sm:p-6" : "print-only mx-auto hidden max-w-[190mm] p-0"} space-y-4 font-sans`}
      dir="rtl"
    >
      {copies.map((copy, index) => (
        <ReceiptSlip
          key={copy.label}
          copyLabel={copy.label}
          copyTone={copy.tone}
          backgroundTone={index === 0 ? "bg-cyan-50" : "bg-amber-50"}
          receipt={receipt}
          showCutLine={index === 0}
        />
      ))}
    </article>
  );
}

function ReceiptSlip({
  backgroundTone,
  copyLabel,
  copyTone,
  receipt,
  showCutLine,
}: Readonly<{
  backgroundTone: string;
  copyLabel: string;
  copyTone: string;
  receipt: PaymentReceipt;
  showCutLine: boolean;
}>) {
  const uiText = useUiText();
  const entry = receipt.transaction;
  const allocatedAmount = entry.allocations.reduce(
    (total, allocation) => total + Number(allocation.amount),
    0,
  );
  const unallocatedAmount = Number(entry.booking_amount) - allocatedAmount;

  return (
    <>
      <section className={`receipt-slip rounded-xl border border-slate-900 p-3 text-slate-950 print:break-inside-avoid ${backgroundTone}`}>
        <div className="flex items-start justify-between gap-4 border-b pb-3">
          <AgencyDocumentHeader
            compact
            agencyName={receipt.agency_name}
            agencyLogo={receipt.agency_logo}
            title={uiText("وصل الدفع")}
            subtitle={receipt.branch_name}
          />
          <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${copyTone}`}>
            {copyLabel}
          </span>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
          <p><b>{uiText("رقم الوصل:")}</b> {receipt.receipt_number}</p>
          <p><b>{uiText("التاريخ:")}</b> {entry.transaction_date}</p>
          <p><b>{uiText("رقم الحجز:")}</b> {receipt.booking_code}</p>
          <p><b>{uiText("طريقة الدفع:")}</b> {entry.payment_method_name}</p>
          <p><b>{uiText("الاسم واللقب:")}</b> {receipt.customer_name}</p>
          {receipt.customer_phone && <p><b>{uiText("الهاتف:")}</b> {receipt.customer_phone}</p>}
          <p className="col-span-2"><b>{uiText("نوع البرنامج:")}</b> {receipt.trip_name}</p>
        </div>

        <section className="mt-3 rounded-lg border-2 border-slate-900 p-3 text-center">
          <p className="text-xs">{uiText("المبلغ بالأرقام")}</p>
          <p className="mt-1 text-2xl font-bold">{entry.amount} {entry.currency_code}</p>
          <p className="mt-2 border-t pt-2 text-sm">
            <b>{uiText("المبلغ بالأحرف:")}</b> {receipt.amount_in_words_ar}
          </p>
        </section>

        <div className="mt-3 grid gap-3 md:grid-cols-[1.15fr_0.85fr] print:grid-cols-[1.15fr_0.85fr]">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr>
                <th className="border p-1.5 text-right">{uiText("المسافر")}</th>
                <th className="border p-1.5 text-right">{uiText("المبلغ المخصص")}</th>
              </tr>
            </thead>
            <tbody>
              {entry.allocations.map((allocation) => (
                <tr key={allocation.id}>
                  <td className="border p-1.5">{allocation.traveler_name}</td>
                  <td className="border p-1.5">{allocation.amount} {entry.booking_currency_code}</td>
                </tr>
              ))}
              {unallocatedAmount > 0 && (
                <tr>
                  <td className="border p-1.5">{uiText("دفعة غير مخصصة لمسافر")}</td>
                  <td className="border p-1.5">
                    {unallocatedAmount.toFixed(4)} {entry.booking_currency_code}
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          <div className="grid grid-cols-1 border text-center text-xs">
            <div className="p-2">
              <b className="block">{uiText("إجمالي الحجز")}</b>
              {receipt.financial_summary.booking_total} {receipt.financial_summary.currency}
            </div>
            <div className="border-y p-2">
              <b className="block">{uiText("المدفوع حتى الآن")}</b>
              {receipt.financial_summary.paid_amount} {receipt.financial_summary.currency}
            </div>
            <div className="p-2">
              <b className="block">{uiText("المبلغ المتبقي")}</b>
              {receipt.financial_summary.remaining_amount} {receipt.financial_summary.currency}
            </div>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
          {!!receipt.hotels.length && <p><b>{uiText("الفنادق:")}</b> {receipt.hotels.join("، ")}</p>}
          {!!receipt.room_types.length && <p><b>{uiText("نوع الغرفة:")}</b> {receipt.room_types.join("، ")}</p>}
          {entry.reference && <p><b>{uiText("المرجع:")}</b> {entry.reference}</p>}
        </div>

        <footer className="mt-6 grid grid-cols-2 pb-[15mm] text-center text-xs">
          <p>{uiText("توقيع الموظف")}</p>
          <p>{uiText("ختم الوكالة")}</p>
        </footer>
      </section>
      {showCutLine && <div className="border-t border-dashed border-slate-400 print:my-2" />}
    </>
  );
}


function PaymentAllocationBreakdown({
  summary,
  copy,
}: Readonly<{ summary: FinancialSummary; copy: (typeof text)["ar"] }>) {
  const allocated = summary.traveler_balances.reduce(
    (total, traveler) => total + Number(traveler.paid_amount),
    0,
  );
  const unallocated = Number(summary.paid_amount) - allocated;
  return (
    <section className="rounded-xl border bg-white">
      <header className="border-b p-5">
        <h2 className="font-semibold">{copy.allocationTitle}</h2>
        <p className="text-sm text-slate-500">{copy.allocationHelp}</p>
      </header>
      <div className="divide-y">
        {summary.traveler_balances.map((traveler) => (
          <div key={traveler.booking_traveler} className="flex justify-between gap-4 p-4 text-sm">
            <span className="font-medium">{traveler.traveler_name}</span>
            <span className="text-left">
              <b>{traveler.paid_amount} {summary.currency}</b> {copy.paid}
              <span className="mr-3 text-slate-500">{traveler.remaining_amount} {copy.remaining}</span>
            </span>
          </div>
        ))}
        {unallocated > 0.00005 && (
          <div className="flex justify-between gap-4 bg-amber-50 p-4 text-sm text-amber-900">
            <span className="font-medium">{copy.unallocated}</span>
            <b>{unallocated.toFixed(4)} {summary.currency}</b>
          </div>
        )}
      </div>
    </section>
  );
}

function Metric({
  label,
  value,
  currency,
  tone = "slate",
}: Readonly<{
  label: string;
  value?: string;
  currency?: string;
  tone?: "slate" | "emerald" | "amber";
}>) {
  const colors = {
    slate: "border-slate-200 bg-white",
    emerald: "border-emerald-200 bg-emerald-50",
    amber: "border-amber-200 bg-amber-50",
  };
  return (
    <div className={`rounded-xl border p-5 ${colors[tone]}`}>
      <p className="text-sm">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value} {currency}</p>
    </div>
  );
}

function Input({
  value,
  setValue,
  placeholder,
  type = "text",
}: Readonly<{
  value: string;
  setValue: (value: string) => void;
  placeholder: string;
  type?: string;
}>) {
  return (
    <input
      value={value}
      onChange={(event) => setValue(event.target.value)}
      type={type}
      min={type === "number" ? "0" : undefined}
      step={type === "number" ? "0.0001" : undefined}
      placeholder={placeholder}
      className="rounded-lg border px-3 py-2 text-sm"
    />
  );
}

function Action({
  children,
  onClick,
  disabled,
}: Readonly<{
  children: React.ReactNode;
  onClick: () => void;
  disabled: boolean;
}>) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-2 rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
    >
      {children}
    </button>
  );
}
