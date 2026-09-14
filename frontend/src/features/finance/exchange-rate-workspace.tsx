"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRightLeft, LoaderCircle } from "lucide-react";
import { useState } from "react";

import type { AgencyCurrency, Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";

import type { ExchangeRateRecord } from "./types";

export function ExchangeRateWorkspace() {
  const uiText = useUiText();
  const queryClient = useQueryClient();
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [rate, setRate] = useState("");
  const [effectiveDate, setEffectiveDate] = useState(new Date().toISOString().slice(0, 10));
  const [reference, setReference] = useState("");
  const currencies = useQuery({ queryKey: ["agency-currencies"], queryFn: () => apiRequest<Paginated<AgencyCurrency>>("/reference/agency-currencies/") });
  const rates = useQuery({ queryKey: ["exchange-rates"], queryFn: () => apiRequest<Paginated<ExchangeRateRecord>>("/finance/exchange-rates/") });
  const create = useMutation({ mutationFn: () => apiRequest<ExchangeRateRecord>("/finance/exchange-rates/", { method: "POST", body: JSON.stringify({ source_currency: source, target_currency: target, rate, effective_date: effectiveDate, source_reference: reference }) }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["exchange-rates"] }); setRate(""); setReference(""); } });
  if (rates.isPending) return <div className="grid min-h-72 place-items-center"><LoaderCircle className="size-8 animate-spin text-cyan-800" /></div>;
  const enabled = currencies.data?.results.filter((item) => item.is_enabled) ?? [];
  return <div className="space-y-6"><section className="rounded-xl border border-slate-200 bg-white"><header className="border-b border-slate-200 p-5"><h2 className="flex items-center gap-2 font-semibold"><ArrowRightLeft className="size-5 text-cyan-700" />{uiText("Record an exchange rate")}</h2><p className="text-sm text-slate-500">{uiText("Rates are historical records and cannot be edited or deleted.")}</p></header><div className="grid gap-3 p-5 md:grid-cols-5"><select value={source} onChange={(event) => setSource(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm"><option value="">{uiText("Source currency")}</option>{enabled.map((item) => <option key={item.id} value={item.currency}>{item.currency}</option>)}</select><select value={target} onChange={(event) => setTarget(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm"><option value="">{uiText("Target currency")}</option>{enabled.map((item) => <option key={item.id} value={item.currency}>{item.currency}</option>)}</select><input value={rate} onChange={(event) => setRate(event.target.value)} type="number" min="0" step="0.00000001" placeholder={uiText("Exchange rate")} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" /><input value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} type="date" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" /><input value={reference} onChange={(event) => setReference(event.target.value)} placeholder={uiText("Rate source/reference")} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" /></div><div className="px-5 pb-5"><button onClick={() => create.mutate()} disabled={!source || !target || source === target || !rate || create.isPending} className="rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{uiText("Save historical rate")}</button></div></section><section className="rounded-xl border border-slate-200 bg-white"><header className="border-b border-slate-200 p-5"><h2 className="font-semibold">{uiText("Exchange-rate history")}</h2></header><div className="divide-y divide-slate-100">{rates.data?.results.map((item) => <div key={item.id} className="grid gap-3 p-5 md:grid-cols-[1fr_auto_auto]"><div><p className="font-medium">{item.source_currency} → {item.target_currency}</p><p className="text-xs text-slate-500">{item.source_reference || uiText("Manual rate")}</p></div><p className="text-sm text-slate-500">{item.effective_date}</p><p className="font-mono font-semibold">{item.rate}</p></div>)}{!rates.data?.results.length && <p className="p-5 text-sm text-slate-500">{uiText("No exchange rates recorded.")}</p>}</div></section>{create.isError && <p className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{uiText("The rate was rejected. Check the currencies, date, and existing history.")}</p>}</div>;
}
