"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useQuery } from "@tanstack/react-query";
import { LoaderCircle, Search, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";

import type { Traveler } from "./types";

export function TravelerList() {
  const uiText = useUiText();
  const [search, setSearch] = useState("");
  const travelers = useQuery({ queryKey: ["travelers", search], queryFn: () => apiRequest<Paginated<Traveler>>(`/travelers/?search=${encodeURIComponent(search)}`) });
  return <section className="rounded-xl border border-slate-200 bg-white"><div className="flex flex-col gap-4 border-b border-slate-200 p-5 md:flex-row md:items-center md:justify-between"><div><h2 className="font-semibold">{uiText("Traveler directory")}</h2><p className="text-sm text-slate-500">{uiText("Reusable profiles and current travel identity")}</p></div><label className="flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2"><Search className="size-4 text-slate-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={uiText("Name, passport or phone")} className="w-56 border-0 text-sm outline-none" /></label></div>{travelers.isPending ? <div className="grid min-h-56 place-items-center"><LoaderCircle className="size-7 animate-spin text-cyan-800" /></div> : travelers.data?.results.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-5 py-3">{uiText("Traveler")}</th><th className="px-5 py-3">{uiText("Passport")}</th><th className="px-5 py-3">{uiText("Contact")}</th><th className="px-5 py-3">{uiText("Branch")}</th></tr></thead><tbody className="divide-y divide-slate-100">{travelers.data.results.map((traveler) => <tr key={traveler.id}><td className="px-5 py-4"><Link href={`/travelers/${traveler.id}`} className="font-medium text-cyan-800 hover:underline">{traveler.display_name}</Link></td><td className="px-5 py-4"><p className="font-mono text-xs">{traveler.current_passport?.passport_number ?? uiText("No current passport")}</p><p className="text-xs text-slate-500">{traveler.current_passport ? `Expires ${traveler.current_passport.expiry_date}` : ""}</p></td><td className="px-5 py-4"><p>{traveler.phone || "—"}</p><p className="text-xs text-slate-500">{traveler.email}</p></td><td className="px-5 py-4 text-slate-600">{traveler.branch_name}</td></tr>)}</tbody></table></div> : <div className="grid min-h-56 place-items-center text-center"><div><Users className="mx-auto size-8 text-slate-300" /><p className="mt-3 font-medium">{uiText("No travelers found")}</p><p className="text-sm text-slate-500">{uiText("Traveler profiles will appear here.")}</p></div></div>}</section>;
}
