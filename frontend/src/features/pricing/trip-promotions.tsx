"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgePercent, Pencil, Plus } from "lucide-react";
import { useState } from "react";
import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";
import type { PromotionRecord } from "./types";

type Draft = { code: string; name: string; sales_start_date: string; sales_end_date: string; description: string; is_active: boolean };
const blank: Draft = { code: "", name: "", sales_start_date: "", sales_end_date: "", description: "", is_active: true };

export function TripPromotions({ tripId }: Readonly<{ tripId: string }>) {
  const uiText = useUiText();
  const cache = useQueryClient(); const [open, setOpen] = useState(false); const [editing, setEditing] = useState<PromotionRecord | null>(null); const [draft, setDraft] = useState<Draft>(blank);
  const promotions = useQuery({ queryKey: ["trip-promotions", tripId], queryFn: () => apiRequest<Paginated<PromotionRecord>>(`/pricing/promotions/?trip=${tripId}`) });
  const refresh = () => cache.invalidateQueries({ queryKey: ["trip-promotions", tripId] });
  const save = useMutation({ mutationFn: () => apiRequest<PromotionRecord>(editing ? `/pricing/promotions/${editing.id}/` : "/pricing/promotions/", { method: editing ? "PATCH" : "POST", body: JSON.stringify({ ...draft, trip: tripId }) }), onSuccess: () => { refresh(); setOpen(false); } });
  const toggle = useMutation({ mutationFn: (item: PromotionRecord) => apiRequest<PromotionRecord>(`/pricing/promotions/${item.id}/`, { method: "PATCH", body: JSON.stringify({ is_active: !item.is_active }) }), onSuccess: refresh });
  const create = () => { setEditing(null); setDraft(blank); save.reset(); setOpen(true); };
  const edit = (item: PromotionRecord) => { setEditing(item); setDraft({ code: item.code, name: item.name, sales_start_date: item.sales_start_date, sales_end_date: item.sales_end_date, description: item.description, is_active: item.is_active }); save.reset(); setOpen(true); };
  return <><section className="rounded-xl border border-slate-200 bg-white"><header className="flex items-center justify-between border-b p-5"><div className="flex items-center gap-2"><BadgePercent className="size-5 text-cyan-800" /><div><h3 className="font-semibold">{uiText("Promotions")}</h3><p className="text-sm text-slate-500">{uiText("Sales periods available to promotional hotel prices.")}</p></div></div><button onClick={create} className="inline-flex items-center gap-1 text-sm font-medium text-cyan-800"><Plus className="size-4" />{uiText("Add promotion")}</button></header><div className="divide-y">{promotions.data?.results.map((item) => <div key={item.id} className="flex items-center justify-between p-4"><div><p className="font-medium">{item.code} · {item.name}</p><p className="text-xs text-slate-500">{item.sales_start_date} → {item.sales_end_date} · {item.is_active ? uiText("Active") : uiText("Inactive")}</p></div><div className="flex gap-3"><button onClick={() => edit(item)} className="text-cyan-800"><Pencil className="size-4" /></button><button onClick={() => toggle.mutate(item)} className="text-xs text-slate-600">{item.is_active ? uiText("Deactivate") : uiText("Reactivate")}</button></div></div>)}{!promotions.isPending && !promotions.data?.results.length && <p className="p-6 text-sm text-slate-500">{uiText("No promotions configured.")}</p>}</div></section><FormDialog open={open} onClose={() => setOpen(false)} title={editing ? uiText("Edit promotion") : uiText("Add promotion")}><form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="space-y-4"><div className="grid gap-4 sm:grid-cols-2"><Field label={uiText("Code")}><input required className="input" value={draft.code} onChange={(e) => setDraft({ ...draft, code: e.target.value.toLowerCase().replaceAll(" ", "-") })} /></Field><Field label={uiText("Name")}><input required className="input" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></Field><Field label={uiText("Sales start")}><input required type="date" className="input" value={draft.sales_start_date} onChange={(e) => setDraft({ ...draft, sales_start_date: e.target.value })} /></Field><Field label={uiText("Sales end")}><input required type="date" className="input" value={draft.sales_end_date} onChange={(e) => setDraft({ ...draft, sales_end_date: e.target.value })} /></Field><Field label={uiText("Description")} wide><textarea className="input" value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></Field></div><MutationMessage error={save.error} /><div className="flex justify-end gap-2"><button type="button" onClick={() => setOpen(false)} className="rounded-lg border px-4 py-2">{uiText("Cancel")}</button><button disabled={save.isPending} className="rounded-lg bg-cyan-800 px-4 py-2 text-white">{uiText("Save promotion")}</button></div></form></FormDialog></>;
}

function Field({ label, wide, children }: Readonly<{ label: string; wide?: boolean; children: React.ReactNode }>) { return <label className={`text-sm font-medium ${wide ? "sm:col-span-2" : ""}`}>{label}<div className="mt-1 [&_.input]:w-full [&_.input]:rounded-lg [&_.input]:border [&_.input]:border-slate-300 [&_.input]:px-3 [&_.input]:py-2">{children}</div></label>; }
