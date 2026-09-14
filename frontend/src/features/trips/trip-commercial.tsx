"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck, CircleDollarSign, FileCheck2, Handshake, LoaderCircle, ReceiptText } from "lucide-react";
import Link from "next/link";

import type { BookingRecord } from "@/features/bookings/types";
import type { FinancialTransactionRecord } from "@/features/finance/types";
import { TripExpenses } from "@/features/finance/trip-expenses";
import type { AllocationRecord, CommissionRecord } from "@/features/partners/types";
import { TripPromotions } from "@/features/pricing/trip-promotions";
import type { QuoteRecord } from "@/features/pricing/types";
import { PricingPrerequisites } from "@/features/pricing/pricing-prerequisites";
import { TripPricing } from "@/features/pricing/trip-pricing";
import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";

export function TripCommercial({ tripId }: Readonly<{ tripId: string }>) {
  const quotes = useQuery({ queryKey: ["trip-quotes", tripId], queryFn: () => apiRequest<Paginated<QuoteRecord>>(`/pricing/quotes/?trip=${tripId}`) });
  const bookings = useQuery({ queryKey: ["trip-bookings", tripId], queryFn: () => apiRequest<Paginated<BookingRecord>>(`/bookings/?trip=${tripId}`) });
  const payments = useQuery({ queryKey: ["trip-payments", tripId], queryFn: () => apiRequest<Paginated<FinancialTransactionRecord>>(`/finance/transactions/?trip=${tripId}`) });
  const allocations = useQuery({ queryKey: ["trip-allocations", tripId], queryFn: () => apiRequest<Paginated<AllocationRecord>>(`/partners/allocations/?trip=${tripId}`) });
  const commissions = useQuery({ queryKey: ["trip-commissions", tripId], queryFn: () => apiRequest<Paginated<CommissionRecord>>(`/partners/commissions/?trip=${tripId}`) });
  const pending = [quotes, bookings, payments, allocations, commissions].some((query) => query.isPending);
  if (pending) return <div className="grid min-h-48 place-items-center"><LoaderCircle className="size-7 animate-spin text-cyan-800" /></div>;

  const revenue = (payments.data?.results ?? []).reduce<Record<string, number>>((totals, item) => { totals[item.booking_currency_code] = (totals[item.booking_currency_code] ?? 0) + Number(item.signed_booking_amount); return totals; }, {});
  const bookingValue = (bookings.data?.results ?? []).reduce<Record<string, number>>((totals, item) => { totals[item.currency_code] = (totals[item.currency_code] ?? 0) + Number(item.total_amount); return totals; }, {});
  const money = (totals: Record<string, number>) => Object.entries(totals).map(([currency, amount]) => `${amount.toFixed(2)} ${currency}`).join(" · ") || "0";

  return <div className="space-y-6">
    <div className="flex items-end justify-between gap-4"><div><p className="text-sm font-medium text-cyan-800">Commercial workspace</p><h2 className="mt-1 text-2xl font-semibold">Sales, revenue, and distribution</h2></div><div className="flex gap-2"><Link href="/quotes" className="rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white">Create quote</Link><Link href="/payments" className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium">Post payment</Link></div></div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric icon={<BookOpenCheck />} label="Bookings" value={String(bookings.data?.count ?? 0)} detail={money(bookingValue)} /><Metric icon={<CircleDollarSign />} label="Collected revenue" value={money(revenue)} detail={`${payments.data?.count ?? 0} ledger entries`} /><Metric icon={<FileCheck2 />} label="Quotes" value={String(quotes.data?.count ?? 0)} detail={`${quotes.data?.results.filter((x) => x.status === "ACCEPTED").length ?? 0} accepted`} /><Metric icon={<Handshake />} label="Allocations" value={String(allocations.data?.count ?? 0)} detail={`${commissions.data?.count ?? 0} commissions`} /></div>
    <PricingPrerequisites tripId={tripId} />
    <TripPricing tripId={tripId} />
    <TripExpenses tripId={tripId} />
    <TripPromotions tripId={tripId} />
    <div className="grid gap-6 xl:grid-cols-2">
      <Related title="Quotes" icon={<FileCheck2 className="size-5" />} empty="No quotes for this trip.">{quotes.data?.results.map((item) => <Link key={item.id} href={`/quotes/${item.id}`} className="flex justify-between p-4 hover:bg-slate-50"><div><p className="font-medium text-cyan-900">{item.code} · {item.customer_name}</p><p className="text-xs text-slate-500">Valid until {item.valid_until}</p></div><span className="text-sm font-semibold">{item.total} {item.currency}</span></Link>)}</Related>
      <Related title="Bookings" icon={<BookOpenCheck className="size-5" />} empty="No bookings for this trip.">{bookings.data?.results.map((item) => <Link key={item.id} href={`/bookings/${item.id}`} className="flex justify-between p-4 hover:bg-slate-50"><div><p className="font-medium text-cyan-900">{item.code} · {item.customer_name}</p><p className="text-xs text-slate-500">{item.traveler_count} travelers · {item.status}</p></div><span className="text-sm font-semibold">{item.total_amount} {item.currency_code}</span></Link>)}</Related>
      <Related title="Revenue ledger" icon={<ReceiptText className="size-5" />} empty="No customer payments posted.">{payments.data?.results.map((item) => <div key={item.id} className="flex justify-between p-4"><div><p className="font-medium">{item.number} · {item.booking_code}</p><p className="text-xs text-slate-500">{item.transaction_date} · {item.payment_method_name} · {item.kind}</p></div><span className="text-sm font-semibold">{item.signed_booking_amount} {item.booking_currency_code}</span></div>)}</Related>
      <Related title="Partner allocations" icon={<Handshake className="size-5" />} empty="No partner allocations.">{allocations.data?.results.map((item) => <div key={item.id} className="flex justify-between p-4"><div><p className="font-medium">{item.partner_name} · {item.kind}</p><p className="text-xs text-slate-500">{item.used_quantity} used</p></div><span className="text-sm font-semibold">{item.remaining_quantity} / {item.quantity}</span></div>)}</Related>
      <Related title="Commissions" icon={<CircleDollarSign className="size-5" />} empty="No commissions accrued.">{commissions.data?.results.map((item) => <div key={item.id} className="flex justify-between p-4"><div><p className="font-medium">{item.partner_name} · {item.booking_code}</p><p className="text-xs text-slate-500">{item.status} · paid {item.paid_amount}</p></div><span className="text-sm font-semibold">{item.amount} {item.currency}</span></div>)}</Related>
    </div>
  </div>;
}

function Metric({ icon, label, value, detail }: Readonly<{ icon: React.ReactNode; label: string; value: string; detail: string }>) { return <div className="rounded-xl border border-slate-200 bg-white p-5"><span className="inline-flex rounded-lg bg-cyan-50 p-2 text-cyan-800 [&_svg]:size-5">{icon}</span><p className="mt-4 text-2xl font-semibold">{value}</p><p className="mt-1 text-sm font-medium">{label}</p><p className="mt-1 text-xs text-slate-500">{detail}</p></div>; }
function Related({ title, icon, empty, children }: Readonly<{ title: string; icon: React.ReactNode; empty: string; children: React.ReactNode }>) { const hasChildren = Array.isArray(children) ? children.length > 0 : Boolean(children); return <section className="rounded-xl border border-slate-200 bg-white"><header className="flex items-center gap-2 border-b border-slate-200 p-5 text-cyan-800">{icon}<h3 className="font-semibold text-slate-900">{title}</h3></header><div className="divide-y divide-slate-100">{hasChildren ? children : <p className="p-6 text-sm text-slate-500">{empty}</p>}</div></section>; }
