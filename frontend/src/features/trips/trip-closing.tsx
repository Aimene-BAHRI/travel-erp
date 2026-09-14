"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, CheckCircle2, Circle, LoaderCircle, LockKeyhole, Printer } from "lucide-react";
import Link from "next/link";

import { MutationMessage } from "@/components/forms/mutation-message";
import { apiRequest } from "@/lib/api/client";

import type { TripClosingItemRecord, TripClosingSummary } from "./types";
import type { Paginated } from "@/features/reference/types";

type UserOption = { id: string; email: string; first_name: string; last_name: string };

export function TripClosing({ tripId }: Readonly<{ tripId: string }>) {
  const uiText = useUiText();
  const cache = useQueryClient();
  const closing = useQuery({
    queryKey: ["trip-closing", tripId],
    queryFn: () => apiRequest<TripClosingSummary>(`/trips/${tripId}/closing/`),
  });
  const users = useQuery({ queryKey: ["users", "closing"], queryFn: () => apiRequest<Paginated<UserOption>>("/accounts/users/") });
  const update = (value: TripClosingSummary) => {
    cache.setQueryData(["trip-closing", tripId], value);
    cache.invalidateQueries({ queryKey: ["trip", tripId] });
    cache.invalidateQueries({ queryKey: ["trips"] });
  };
  const start = useMutation({
    mutationFn: () => apiRequest<TripClosingSummary>(`/trips/${tripId}/closing/start/`, { method: "POST" }),
    onSuccess: update,
  });
  const saveItem = useMutation({
    mutationFn: ({ item, state, notes, assigned_to = item.assigned_to, due_date = item.due_date }: { item: TripClosingItemRecord; state: TripClosingItemRecord["state"]; notes: string; assigned_to?: string|null; due_date?: string|null }) =>
      apiRequest<TripClosingSummary>(`/trips/${tripId}/closing/items/${item.key}/`, {
        method: "PATCH",
        body: JSON.stringify({ state, notes, assigned_to, due_date }),
      }),
    onSuccess: update,
  });
  const close = useMutation({
    mutationFn: () => apiRequest<TripClosingSummary>(`/trips/${tripId}/closing/close/`, { method: "POST" }),
    onSuccess: update,
  });
  const reopen = useMutation({
    mutationFn: () => apiRequest<TripClosingSummary>(`/trips/${tripId}/closing/reopen/`, { method: "POST" }),
    onSuccess: update,
  });

  if (closing.isPending)
    return <div className="grid min-h-40 place-items-center"><LoaderCircle className="size-6 animate-spin text-cyan-800" /></div>;
  if (!closing.data) return null;
  const data = closing.data;
  const progress = data.total_count ? Math.round((data.completed_count / data.total_count) * 100) : 0;
  const error = start.error ?? saveItem.error ?? close.error ?? reopen.error;

  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <header className="flex flex-col justify-between gap-4 border-b p-5 md:flex-row md:items-center">
        <div>
          <h2 className="flex items-center gap-2 font-semibold"><Archive className="size-5 text-cyan-800" />{uiText("Trip Closing &amp; Archive")}</h2>
          <p className="text-sm text-slate-500">{uiText("Operational, financial, and document controls required before final closure.")}</p>
        </div>
        <div className="flex items-center gap-3">
          {data.status !== "NOT_DUE" && <Link href={`/trips/${tripId}/closing-report`} className="inline-flex items-center gap-1 rounded-lg border px-3 py-2 text-sm"><Printer className="size-4"/>{uiText("Report")}</Link>}
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{uiText(data.status)}</span>
          {data.status === "NOT_DUE" && data.can_start && <button onClick={() => start.mutate()} className="rounded-lg bg-cyan-800 px-3 py-2 text-sm text-white">{uiText("Start closing")}</button>}
          {data.status === "READY_TO_CLOSE" && <button onClick={() => close.mutate()} className="inline-flex items-center gap-1 rounded-lg bg-emerald-700 px-3 py-2 text-sm text-white"><LockKeyhole className="size-4" />{uiText("Close trip")}</button>}
          {data.status === "CLOSED" && <button onClick={() => reopen.mutate()} className="rounded-lg border px-3 py-2 text-sm">{uiText("Reopen")}</button>}
        </div>
      </header>
      {data.status === "NOT_DUE" ? (
        <p className="p-6 text-sm text-slate-500">{uiText("Closing becomes available after the return date or when the trip is marked completed.")}</p>
      ) : (
        <>
          <div className="border-b bg-slate-50 p-5">
            <div className="mb-2 flex justify-between text-sm"><b>{data.completed_count} {uiText("of")} {data.total_count} {uiText("controls complete")}</b><span>{progress}%</span></div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-cyan-700" style={{ width: `${progress}%` }} /></div>
          </div>
          <FinancialSnapshot data={data} />
          <div className="divide-y">
            {data.items.map((item) => (
              <div key={item.id} className="grid gap-3 p-5 lg:grid-cols-[1.2fr_150px_180px_150px_1fr] lg:items-center">
                <div className="flex gap-3">
                  {item.state === "PENDING" ? <Circle className="mt-0.5 size-5 text-slate-300" /> : <CheckCircle2 className="mt-0.5 size-5 text-emerald-600" />}
                  <div><p className="font-medium">{uiText(item.label)}</p>{item.completed_by_name && <p className="text-xs text-slate-500">{uiText("By")} {item.completed_by_name} · {item.completed_at?.slice(0, 10)}</p>}</div>
                </div>
                <select disabled={data.status === "CLOSED" || saveItem.isPending} value={item.state} onChange={(event) => saveItem.mutate({ item, state: event.target.value as TripClosingItemRecord["state"], notes: item.notes })} className="rounded-lg border px-3 py-2 text-sm disabled:bg-slate-100">
                  <option value="PENDING">{uiText("Pending")}</option><option value="COMPLETED">{uiText("Completed")}</option><option value="NOT_REQUIRED">{uiText("Not required")}</option>
                </select>
                <select disabled={data.status === "CLOSED"} value={item.assigned_to??""} onChange={event=>saveItem.mutate({item,state:item.state,notes:item.notes,assigned_to:event.target.value||null})} className="rounded-lg border px-3 py-2 text-sm disabled:bg-slate-100"><option value="">{uiText("Unassigned")}</option>{users.data?.results.map(user=><option key={user.id} value={user.id}>{`${user.first_name} ${user.last_name}`.trim()||user.email}</option>)}</select>
                <input disabled={data.status === "CLOSED"} type="date" value={item.due_date??""} onChange={event=>saveItem.mutate({item,state:item.state,notes:item.notes,due_date:event.target.value||null})} className="rounded-lg border px-3 py-2 text-sm disabled:bg-slate-100" />
                <input disabled={data.status === "CLOSED"} defaultValue={item.notes} onBlur={(event) => { if (event.target.value !== item.notes) saveItem.mutate({ item, state: item.state, notes: event.target.value }); }} placeholder={uiText("Notes or reference")} className="rounded-lg border px-3 py-2 text-sm disabled:bg-slate-100" />
              </div>
            ))}
          </div>
        </>
      )}
      {data.closed_at && <p className="border-t bg-emerald-50 p-4 text-sm text-emerald-800">{uiText("Closed by")} {data.closed_by} {uiText("on")} {data.closed_at.slice(0, 10)}</p>}
      {error && <div className="p-4"><MutationMessage error={error} /></div>}
    </section>
  );
}

function FinancialSnapshot({ data }: Readonly<{ data: TripClosingSummary }>) {
  const uiText = useUiText();
  const money = (values: Record<string, string>) => Object.entries(values).map(([currency, amount]) => `${amount} ${currency}`).join(" · ") || "0";
  return (
    <div className="grid gap-3 border-b p-5 sm:grid-cols-2 xl:grid-cols-3">
      <Metric label={uiText("Revenue")} value={`${data.financials.revenue} ${data.financials.accounting_currency}`} />
      <Metric label={uiText("Collected")} value={`${data.financials.collected} ${data.financials.accounting_currency}`} />
      <Metric label={uiText("Customer outstanding")} value={`${data.financials.customer_outstanding} ${data.financials.accounting_currency}`} />
      <Metric label={uiText("Supplier outstanding")} value={money(data.financials.supplier_outstanding_by_currency)} />
      <Metric label={uiText("Expenses")} value={money(data.financials.expenses_by_currency)} />
      <Metric label={uiText("Profit / loss")} value={data.financials.profit_loss === null ? data.financials.profit_loss_note : `${data.financials.profit_loss} ${data.financials.accounting_currency}`} />
      <Metric label={uiText("Archived documents")} value={String(data.financials.document_count)} />
    </div>
  );
}

function Metric({ label, value }: Readonly<{ label: string; value: string }>) {
  return <div className="rounded-lg bg-slate-50 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>;
}
