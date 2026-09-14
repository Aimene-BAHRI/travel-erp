"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CheckCircle2, Circle, LoaderCircle, Settings2 } from "lucide-react";
import { useEffect, useState } from "react";

import { MutationMessage } from "@/components/forms/mutation-message";
import { NotificationSettings } from "@/features/notifications/notification-settings";
import { ReferenceSettings } from "@/features/reference/reference-settings";
import { apiRequest } from "@/lib/api/client";

type Section = "overview" | "agency" | "operations" | "notifications";
type SetupSummary = {
  status: "SETUP" | "READY" | "ACTIVE";
  complete_count: number;
  total_count: number;
  items: Array<{ key: string; label: string; complete: boolean; section: Section }>;
};
type Agency = {
  id: string; name: string; legal_name: string; registration_number: string;
  tax_number: string; address: string; phone: string; email: string; website: string;
  logo: string | null;
  settings?: { timezone: string; default_language: string; setup_status: string; invoice_footer: string; primary_color: string; secondary_color: string };
};

const sections: Array<[Section, string]> = [
  ["overview", "Setup overview"], ["agency", "Agency profile"],
  ["operations", "Branches & finance"], ["notifications", "Notifications"],
];

export function AgencySetupWorkspace() {
  const uiText = useUiText();
  const cache = useQueryClient();
  const [section, setSection] = useState<Section>("overview");
  const setup = useQuery({ queryKey: ["agency-setup"], queryFn: () => apiRequest<SetupSummary>("/organizations/setup/") });
  const activate = useMutation({
    mutationFn: () => apiRequest<SetupSummary>("/organizations/setup/", { method: "POST" }),
    onSuccess: (data) => cache.setQueryData(["agency-setup"], data),
  });
  return <div className="space-y-6">
    <nav className="flex gap-1 overflow-x-auto rounded-xl border bg-white p-2 shadow-sm">
      {sections.map(([key, label]) => <button key={key} onClick={() => setSection(key)} className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium ${section === key ? "bg-cyan-800 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{uiText(label)}</button>)}
    </nav>
    {setup.isPending ? <div className="grid min-h-56 place-items-center"><LoaderCircle className="size-7 animate-spin text-cyan-800" /></div> : setup.data && <>
      {section === "overview" && <SetupOverview summary={setup.data} onOpen={setSection} onActivate={() => activate.mutate()} activating={activate.isPending} error={activate.error} />}
      {section === "agency" && <AgencyProfile onSaved={() => { cache.invalidateQueries({ queryKey: ["agency-setup"] }); }} />}
      {section === "operations" && <ReferenceSettings />}
      {section === "notifications" && <NotificationSettings />}
    </>}
  </div>;
}

function SetupOverview({ summary, onOpen, onActivate, activating, error }: Readonly<{ summary: SetupSummary; onOpen: (section: Section) => void; onActivate: () => void; activating: boolean; error: Error | null }>) {
  const uiText = useUiText();
  const percent = Math.round((summary.complete_count / summary.total_count) * 100);
  return <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
    <section className="rounded-xl border bg-white">
      <header className="border-b p-6"><div className="flex items-center justify-between gap-4"><div><h2 className="text-xl font-semibold">{uiText("Agency launch checklist")}</h2><p className="mt-1 text-sm text-slate-500">{uiText("Complete the required foundation before activating operational use.")}</p></div><span className={`rounded-full px-3 py-1 text-xs font-semibold ${summary.status === "ACTIVE" ? "bg-emerald-100 text-emerald-800" : summary.status === "READY" ? "bg-cyan-100 text-cyan-800" : "bg-amber-100 text-amber-800"}`}>{uiText(summary.status)}</span></div><div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-cyan-700" style={{ width: `${percent}%` }} /></div><p className="mt-2 text-xs text-slate-500">{summary.complete_count} {uiText("of")} {summary.total_count} {uiText("required items complete")}</p></header>
      <div className="divide-y">{summary.items.map((item) => <button key={item.key} onClick={() => onOpen(item.section)} className="flex w-full items-center justify-between gap-4 p-5 text-start hover:bg-slate-50"><span className="flex items-center gap-3">{item.complete ? <CheckCircle2 className="size-5 text-emerald-600" /> : <Circle className="size-5 text-amber-500" />}<span className="font-medium">{uiText(item.label)}</span></span><span className="text-sm text-cyan-800">{uiText("Open →")}</span></button>)}</div>
    </section>
    <aside className="h-fit rounded-xl border bg-slate-950 p-6 text-white"><Settings2 className="size-7 text-cyan-300" /><h2 className="mt-4 text-xl font-semibold">{uiText("Ready to launch?")}</h2><p className="mt-2 text-sm text-slate-300">{uiText("Activation records the agency as operationally configured. You can continue changing settings afterward.")}</p><button onClick={onActivate} disabled={summary.status !== "READY" || activating} className="mt-6 w-full rounded-lg bg-cyan-500 px-4 py-2.5 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">{summary.status === "ACTIVE" ? uiText("Agency active") : activating ? uiText("Activating…") : uiText("Activate agency")}</button><MutationMessage error={error} /></aside>
  </div>;
}

function AgencyProfile({ onSaved }: Readonly<{ onSaved: () => void }>) {
  const uiText = useUiText();
  const cache = useQueryClient();
  const agency = useQuery({ queryKey: ["current-agency"], queryFn: () => apiRequest<Agency>("/organizations/agency/") });
  const [draft, setDraft] = useState<Agency | null>(null);
  useEffect(() => { if (agency.data) setDraft(agency.data); }, [agency.data]);
  const updateAgency = (data: Agency) => { setDraft(data); cache.setQueryData(["current-agency"], data); onSaved(); };
  const save = useMutation({ mutationFn: () => apiRequest<Agency>("/organizations/agency/", { method: "PATCH", body: JSON.stringify({ name: draft?.name, legal_name: draft?.legal_name, registration_number: draft?.registration_number, tax_number: draft?.tax_number, address: draft?.address, phone: draft?.phone, email: draft?.email, website: draft?.website, settings: draft?.settings }) }), onSuccess: updateAgency });
  const uploadLogo = useMutation({ mutationFn: async (file: File) => { const [primary_color, secondary_color] = await extractLogoColors(file); const body = new FormData(); body.append("logo", file); await apiRequest<Agency>("/organizations/agency/", { method: "PATCH", body }); return apiRequest<Agency>("/organizations/agency/", { method: "PATCH", body: JSON.stringify({ settings: { ...draft?.settings, primary_color, secondary_color } }) }); }, onSuccess: (data) => updateAgency({ ...data, logo: data.logo ? `${data.logo}${data.logo.includes("?") ? "&" : "?"}v=${Date.now()}` : null }) });
  if (!draft) return <div className="grid min-h-56 place-items-center"><LoaderCircle className="size-7 animate-spin text-cyan-800" /></div>;
  const change = (key: keyof Agency, value: string) => setDraft({ ...draft, [key]: value });
  const changeSetting = (key: "timezone" | "default_language" | "invoice_footer" | "primary_color" | "secondary_color", value: string) => setDraft({ ...draft, settings: { timezone: draft.settings?.timezone ?? "Africa/Algiers", default_language: draft.settings?.default_language ?? "en", setup_status: draft.settings?.setup_status ?? "SETUP", invoice_footer: draft.settings?.invoice_footer ?? "", primary_color: draft.settings?.primary_color ?? "#0e7490", secondary_color: draft.settings?.secondary_color ?? "#0f172a", [key]: value } });
  return <section className="rounded-xl border bg-white"><header className="flex items-center gap-3 border-b p-5"><Building2 className="size-5 text-cyan-700" /><div><h2 className="font-semibold">{uiText("Agency identity")}</h2><p className="text-sm text-slate-500">{uiText("Legal, contact, localization, and printed-document details.")}</p></div></header><form onSubmit={(event) => { event.preventDefault(); save.mutate(); }} className="space-y-5 p-6"><div className="flex flex-wrap items-center gap-5 rounded-xl border bg-slate-50 p-4"><div className="grid size-24 place-items-center overflow-hidden rounded-xl border bg-white bg-contain bg-center bg-no-repeat" style={draft.logo ? { backgroundImage: `url(${draft.logo})` } : undefined}>{!draft.logo && <Building2 className="size-9 text-slate-300" />}</div><div><p className="font-medium">{uiText("Agency logo")}</p><p className="mt-1 text-sm text-slate-500">{uiText("PNG, JPG or WebP. This logo is used on agency documents.")}</p><label className="mt-3 inline-flex cursor-pointer rounded-lg border bg-white px-4 py-2 text-sm font-medium text-cyan-800"><input type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" disabled={uploadLogo.isPending} onChange={(event) => { const file = event.target.files?.[0]; if (file) uploadLogo.mutate(file); event.target.value = ""; }} />{uploadLogo.isPending ? uiText("Uploading…") : draft.logo ? uiText("Replace logo") : uiText("Upload logo")}</label></div></div><MutationMessage error={uploadLogo.error} /><div className="grid gap-4 md:grid-cols-2">
    <Field label={uiText("Commercial name")}><input required value={draft.name} onChange={(e) => change("name", e.target.value)} /></Field><Field label={uiText("Legal name")}><input required value={draft.legal_name} onChange={(e) => change("legal_name", e.target.value)} /></Field><Field label={uiText("Registration number")}><input value={draft.registration_number} onChange={(e) => change("registration_number", e.target.value)} /></Field><Field label={uiText("Tax number")}><input value={draft.tax_number} onChange={(e) => change("tax_number", e.target.value)} /></Field><Field label={uiText("Phone")}><input required value={draft.phone} onChange={(e) => change("phone", e.target.value)} /></Field><Field label={uiText("Email")}><input required type="email" value={draft.email} onChange={(e) => change("email", e.target.value)} /></Field><Field label={uiText("Website")}><input type="url" value={draft.website} onChange={(e) => change("website", e.target.value)} /></Field><Field label={uiText("Time zone")}><input required value={draft.settings?.timezone ?? "Africa/Algiers"} onChange={(e) => changeSetting("timezone", e.target.value)} /></Field><Field label={uiText("Default language")}><select value={draft.settings?.default_language ?? "en"} onChange={(e) => changeSetting("default_language", e.target.value)}><option value="ar">{uiText("Arabic")}</option><option value="fr">{uiText("French")}</option><option value="en">{uiText("English")}</option></select></Field><Field label={uiText("Primary brand color")}><input type="color" className="h-11" value={draft.settings?.primary_color ?? "#0e7490"} onChange={(e) => changeSetting("primary_color", e.target.value)} /></Field><Field label={uiText("Secondary brand color")}><input type="color" className="h-11" value={draft.settings?.secondary_color ?? "#0f172a"} onChange={(e) => changeSetting("secondary_color", e.target.value)} /></Field><Field label={uiText("Address")} wide><textarea required rows={3} value={draft.address} onChange={(e) => change("address", e.target.value)} /></Field><Field label={uiText("Invoice and receipt footer")} wide><textarea rows={3} value={draft.settings?.invoice_footer ?? ""} onChange={(e) => changeSetting("invoice_footer", e.target.value)} /></Field>
  </div><MutationMessage error={save.error} /><div className="flex justify-end"><button disabled={save.isPending} className="rounded-lg bg-cyan-800 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50">{save.isPending ? uiText("Saving…") : uiText("Save agency profile")}</button></div></form></section>;
}

function Field({ label, wide, children }: Readonly<{ label: string; wide?: boolean; children: React.ReactNode }>) {
  const uiText = useUiText(); return <label className={`text-sm font-medium text-slate-700 ${wide ? "md:col-span-2" : ""}`}>{uiText(label)}<div className="mt-1 [&>*]:w-full [&>*]:rounded-lg [&>*]:border [&>*]:border-slate-300 [&>*]:px-3 [&>*]:py-2">{children}</div></label>; }

async function extractLogoColors(file: File): Promise<[string, string]> {
  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = 80; canvas.height = 80;
  const context = canvas.getContext("2d");
  if (!context) return ["#0e7490", "#0f172a"];
  context.drawImage(bitmap, 0, 0, 80, 80); bitmap.close();
  const pixels = context.getImageData(0, 0, 80, 80).data;
  const buckets = new Map<string, number>();
  for (let index = 0; index < pixels.length; index += 16) {
    if (pixels[index + 3] < 180) continue;
    const rgb = [pixels[index], pixels[index + 1], pixels[index + 2]];
    if (Math.max(...rgb) > 245 || Math.max(...rgb) - Math.min(...rgb) < 18) continue;
    const key = rgb.map((value) => Math.min(255, Math.round(value / 32) * 32)).join(",");
    buckets.set(key, (buckets.get(key) ?? 0) + 1);
  }
  const colors = [...buckets.entries()].sort((a, b) => b[1] - a[1]).map(([key]) => `#${key.split(",").map((value) => Number(value).toString(16).padStart(2, "0")).join("")}`);
  return [colors[0] ?? "#0e7490", colors.find((color) => color !== colors[0]) ?? "#0f172a"];
}
