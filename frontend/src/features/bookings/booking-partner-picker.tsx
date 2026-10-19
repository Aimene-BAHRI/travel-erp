"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { PartnerRecord } from "@/features/partners/types";
import type { Paginated } from "@/features/reference/types";

export function BookingPartnerPicker({ value, onChange, branch }: { value: string; onChange: (id: string) => void; branch: string }) {
  const { locale } = useLocale();
  const t = (en: string, ar: string) => locale === "ar" ? ar : en;
  const cache = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState({ name: "", contact_name: "", phone: "", email: "" });
  const partners = useQuery({ queryKey: ["booking-partners"], queryFn: async () => {
    const first = await apiRequest<Paginated<PartnerRecord>>("/partners/?ordering=name");
    const results = [...first.results]; let next = first.next;
    while (next) { const page = await apiRequest<Paginated<PartnerRecord>>(`/partners/${new URL(next, "http://localhost").search}`); results.push(...page.results); next = page.next; }
    return results.filter(item => item.kind === "COMPANY" && item.is_active);
  }});
  const create = useMutation({ mutationFn: () => apiRequest<PartnerRecord>("/partners/", { method: "POST", body: JSON.stringify({ ...draft, branch, kind: "COMPANY", is_active: true }) }), onSuccess: partner => {
    cache.setQueryData<PartnerRecord[]>(["booking-partners"], rows => [...(rows ?? []), partner]);
    cache.invalidateQueries({ queryKey: ["partners"] });
    onChange(partner.id); setAdding(false); setSearch(""); setDraft({ name: "", contact_name: "", phone: "", email: "" });
  }});
  const selected = partners.data?.find(item => item.id === value);
  return <section className="space-y-3 rounded-lg border p-4 sm:col-span-2">
    <div className="flex items-center justify-between"><h3 className="font-medium">{t("Partner agency", "الوكالة الشريكة")}</h3><button type="button" className="text-sm font-medium text-cyan-800" onClick={() => { setAdding(!adding); if (!adding) onChange(""); create.reset(); }}>{adding ? t("Cancel", "إلغاء") : t("+ Add partner", "+ إضافة شريك")}</button></div>
    {!adding ? <>
      <input aria-label={t("Search partners", "البحث عن شريك")} placeholder={t("Search by agency, contact or phone", "ابحث بالوكالة أو جهة الاتصال أو الهاتف")} className="w-full rounded-lg border px-3 py-2 text-sm" value={search} onChange={e => setSearch(e.target.value)} />
      <select required className="w-full rounded-lg border px-3 py-2" aria-label={t("Partner agency", "الوكالة الشريكة")} value={value} onChange={e => onChange(e.target.value)}><option value="">{t("Select a partner agency", "اختر وكالة شريكة")}</option>{partners.data?.filter(item => item.id === value || [item.name, item.contact_name, item.phone].join(" ").toLowerCase().includes(search.toLowerCase())).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
      {selected && <p className="text-sm text-slate-600">{[selected.contact_name, selected.phone, selected.email].filter(Boolean).join(" · ")}</p>}
      {!partners.isPending && !partners.data?.length && <p className="text-sm text-slate-500">{t("No partner agencies yet. Add one here to continue.", "لا توجد وكالات شريكة بعد. أضف وكالة هنا للمتابعة.")}</p>}
    </> : <div className="space-y-3">
      {([['name', 'Agency name', 'اسم الوكالة'], ['contact_name', 'Contact person', 'جهة الاتصال'], ['phone', 'Phone', 'الهاتف'], ['email', 'Email', 'البريد الإلكتروني']] as const).map(([key, en, ar]) => <label key={key} className="block text-sm">{t(en, ar)}<input type={key === "email" ? "email" : "text"} className="mt-1 w-full rounded-lg border px-3 py-2" value={draft[key]} onChange={e => setDraft({ ...draft, [key]: e.target.value })} /></label>)}
      <button type="button" disabled={create.isPending || !branch || !draft.name.trim() || !(draft.phone.trim() || draft.email.trim())} onClick={() => create.mutate()} className="rounded-lg bg-cyan-800 px-4 py-2 text-sm text-white disabled:opacity-50">{t("Save and select partner", "حفظ واختيار الشريك")}</button>
    </div>}
    <MutationMessage error={partners.error || create.error} />
  </section>;
}
