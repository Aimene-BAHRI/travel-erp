"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, Building2, Check, CircleDollarSign, LoaderCircle, Pencil, Plus, Users } from "lucide-react";
import { useState } from "react";

import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import { apiRequest } from "@/lib/api/client";

import type { AgencyCurrency, Paginated, PassengerCategory, PaymentMethod } from "./types";

type Branch = { id: string; name: string; code: string; address: string; phone: string; email: string; is_active: boolean };
type BranchDraft = Omit<Branch, "id">;
const blankBranch: BranchDraft = { name: "", code: "", address: "", phone: "", email: "", is_active: true };

function StatusBadge({ active }: Readonly<{ active: boolean }>) {
  const uiText = useUiText();
  return <span className={`rounded-full px-2 py-1 text-xs font-medium ${active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{active ? uiText("Active") : uiText("Inactive")}</span>;
}

export function ReferenceSettings() {
  const uiText = useUiText();
  const queryClient = useQueryClient();
  const currencies = useQuery({
    queryKey: ["agency-currencies"],
    queryFn: () => apiRequest<Paginated<AgencyCurrency>>("/reference/agency-currencies/"),
  });
  const categories = useQuery({
    queryKey: ["passenger-categories"],
    queryFn: () => apiRequest<Paginated<PassengerCategory>>("/reference/passenger-categories/"),
  });
  const paymentMethods = useQuery({
    queryKey: ["payment-methods"],
    queryFn: () => apiRequest<Paginated<PaymentMethod>>("/reference/payment-methods/"),
  });
  const makeAccounting = useMutation({
    mutationFn: (id: string) => apiRequest<AgencyCurrency>(`/reference/agency-currencies/${id}/make-accounting/`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["agency-currencies"] }),
  });

  if (currencies.isPending || categories.isPending || paymentMethods.isPending) {
    return <div className="grid min-h-64 place-items-center"><LoaderCircle className="size-7 animate-spin text-cyan-800" /></div>;
  }

  return (
    <div className="space-y-8">
      <BranchSettings />
      <section className="rounded-xl border border-slate-200 bg-white">
        <header className="flex items-center gap-3 border-b border-slate-200 p-5"><CircleDollarSign className="size-5 text-cyan-700" /><div><h2 className="font-semibold">{uiText("Currencies")}</h2><p className="text-sm text-slate-500">{uiText("Enabled transaction currencies and the agency accounting currency.")}</p></div></header>
        <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-5 py-3">{uiText("Currency")}</th><th className="px-5 py-3">{uiText("Status")}</th><th className="px-5 py-3">{uiText("Accounting")}</th><th className="px-5 py-3 text-right">{uiText("Action")}</th></tr></thead><tbody className="divide-y divide-slate-100">{currencies.data?.results.map((item) => <tr key={item.id}><td className="px-5 py-4 font-medium">{item.currency} <span className="font-normal text-slate-500">· {item.currency_name}</span></td><td className="px-5 py-4"><StatusBadge active={item.is_enabled} /></td><td className="px-5 py-4">{item.is_accounting && <span className="inline-flex items-center gap-1 font-medium text-cyan-800"><Check className="size-4" />{uiText("Primary")}</span>}</td><td className="px-5 py-4 text-right">{!item.is_accounting && <button onClick={() => makeAccounting.mutate(item.id)} disabled={makeAccounting.isPending} className="font-medium text-cyan-800 hover:text-cyan-950 disabled:opacity-50">{uiText("Make accounting")}</button>}</td></tr>)}</tbody></table></div>
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <ReferenceList icon={<Users className="size-5 text-cyan-700" />} title={uiText("Passenger categories")} description={uiText("System defaults and agency extensions")} items={categories.data?.results.map((item) => ({ id: item.id, code: item.code, name: item.name, active: item.is_active, detail: item.requires_bed_by_default ? "Bed by default" : "No bed by default" })) ?? []} />
        <ReferenceList icon={<Banknote className="size-5 text-cyan-700" />} title={uiText("Payment methods")} description={uiText("Available methods for customer payments")} items={paymentMethods.data?.results.map((item) => ({ id: item.id, code: item.code, name: item.name, active: item.is_active, detail: item.is_system ? "System" : "Agency" })) ?? []} />
      </div>
    </div>
  );
}

function BranchSettings() {
  const uiText = useUiText();
  const cache = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Branch | null>(null);
  const [draft, setDraft] = useState<BranchDraft>(blankBranch);
  const branches = useQuery({ queryKey: ["branches"], queryFn: () => apiRequest<Paginated<Branch>>("/organizations/branches/") });
  const refresh = () => cache.invalidateQueries({ queryKey: ["branches"] });
  const save = useMutation({ mutationFn: () => apiRequest<Branch>(editing ? `/organizations/branches/${editing.id}/` : "/organizations/branches/", { method: editing ? "PATCH" : "POST", body: JSON.stringify(draft) }), onSuccess: () => { refresh(); setOpen(false); } });
  const toggle = useMutation({ mutationFn: (branch: Branch) => apiRequest<Branch>(`/organizations/branches/${branch.id}/`, { method: "PATCH", body: JSON.stringify({ is_active: !branch.is_active }) }), onSuccess: refresh });
  const change = (key: keyof BranchDraft, value: string) => setDraft((current) => ({ ...current, [key]: value }));
  const create = () => { setEditing(null); setDraft(blankBranch); save.reset(); setOpen(true); };
  const edit = (branch: Branch) => { setEditing(branch); setDraft({ name: branch.name, code: branch.code, address: branch.address, phone: branch.phone, email: branch.email, is_active: branch.is_active }); save.reset(); setOpen(true); };
  return <>
    <section className="rounded-xl border border-slate-200 bg-white"><header className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-center gap-3"><Building2 className="size-5 text-cyan-700" /><div><h2 className="font-semibold">{uiText("Branches")}</h2><p className="text-sm text-slate-500">{uiText("Managing offices used by trips, quotes, bookings, and payments.")}</p></div></div><button type="button" onClick={create} className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white"><Plus className="size-4" />{uiText("New branch")}</button></header>
      {branches.isPending ? <div className="grid min-h-32 place-items-center"><LoaderCircle className="size-6 animate-spin text-cyan-800" /></div> : branches.data?.results.length ? <div className="divide-y divide-slate-100">{branches.data.results.map((branch) => <div key={branch.id} className="grid gap-3 p-5 md:grid-cols-[1fr_1fr_auto] md:items-center"><div><div className="flex items-center gap-2"><p className="font-medium">{branch.name}</p><StatusBadge active={branch.is_active} /></div><p className="mt-1 text-xs uppercase text-slate-500">{branch.code}</p></div><div className="text-sm text-slate-600"><p>{branch.phone || uiText("No phone")}</p><p className="text-xs text-slate-500">{branch.email || branch.address || uiText("No contact details")}</p></div><div className="flex gap-3"><button type="button" onClick={() => edit(branch)} className="inline-flex items-center gap-1 text-sm font-medium text-cyan-800"><Pencil className="size-3.5" />{uiText("Edit")}</button><button type="button" disabled={toggle.isPending} onClick={() => toggle.mutate(branch)} className="text-sm text-slate-600">{branch.is_active ? uiText("Deactivate") : uiText("Reactivate")}</button></div></div>)}</div> : <div className="p-8 text-center"><Building2 className="mx-auto size-9 text-slate-300" /><p className="mt-3 font-medium">{uiText("No branches configured")}</p><p className="text-sm text-slate-500">{uiText("Create your first managing office to begin operational work.")}</p><button type="button" onClick={create} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white"><Plus className="size-4" />{uiText("Create branch")}</button></div>}
    </section>
    <FormDialog open={open} onClose={() => setOpen(false)} title={editing ? uiText("Edit branch") : uiText("New branch")} description={uiText("Add the office responsible for managing operational records.")}><form onSubmit={(event) => { event.preventDefault(); save.mutate(); }} className="space-y-5"><div className="grid gap-4 sm:grid-cols-2"><Field label={uiText("Branch name")}><input required value={draft.name} onChange={(event) => change("name", event.target.value)} placeholder={uiText("e.g. Main office")} className="input" /></Field><Field label={uiText("Branch code")}><input required value={draft.code} onChange={(event) => change("code", event.target.value.toUpperCase())} placeholder={uiText("e.g. HQ")} className="input" /></Field><Field label={uiText("Phone")}><input value={draft.phone} onChange={(event) => change("phone", event.target.value)} className="input" /></Field><Field label={uiText("Email")}><input type="email" value={draft.email} onChange={(event) => change("email", event.target.value)} className="input" /></Field><Field label={uiText("Address")} wide><textarea rows={3} value={draft.address} onChange={(event) => change("address", event.target.value)} className="input" /></Field></div><MutationMessage error={save.error} /><div className="flex justify-end gap-2"><button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium">{uiText("Cancel")}</button><button disabled={save.isPending} className="rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{save.isPending ? uiText("Saving…") : uiText("Save branch")}</button></div></form></FormDialog>
  </>;
}

function Field({ label, wide, children }: Readonly<{ label: string; wide?: boolean; children: React.ReactNode }>) { return <label className={`text-sm font-medium text-slate-700 ${wide ? "sm:col-span-2" : ""}`}>{label}<div className="mt-1 [&_.input]:w-full [&_.input]:rounded-lg [&_.input]:border [&_.input]:border-slate-300 [&_.input]:px-3 [&_.input]:py-2 [&_.input]:outline-none [&_.input]:focus:border-cyan-600">{children}</div></label>; }

type ReferenceItem = { id: string; code: string; name: string; active: boolean; detail: string };

function ReferenceList({ icon, title, description, items }: Readonly<{ icon: React.ReactNode; title: string; description: string; items: ReferenceItem[] }>) {
  const uiText = useUiText();
  return <section className="rounded-xl border border-slate-200 bg-white"><header className="flex items-center gap-3 border-b border-slate-200 p-5">{icon}<div><h2 className="font-semibold">{title}</h2><p className="text-sm text-slate-500">{description}</p></div></header><ul className="divide-y divide-slate-100">{items.map((item) => <li key={item.id} className="flex items-center justify-between px-5 py-4"><div><p className="font-medium">{uiText(item.name)}</p><p className="text-xs uppercase text-slate-500">{item.code} · {uiText(item.detail)}</p></div><StatusBadge active={item.active} /></li>)}</ul></section>;
}
