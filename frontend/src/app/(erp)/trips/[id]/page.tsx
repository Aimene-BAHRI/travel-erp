"use client";

import { useParams } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { TripProfile, type TripTab } from "@/features/trips/trip-profile";
import { useLocale } from "@/lib/i18n/context";

const tabs: Array<[TripTab, { ar: string; en: string }]> = [
  ["itinerary", { ar: "البرنامج والطيران", en: "Itinerary & flights" }],
  ["accommodation", { ar: "الإقامة", en: "Accommodation" }],
  ["transport", { ar: "النقل", en: "Transport" }],
  ["documents", { ar: "المستندات", en: "Documents" }],
  ["commercial", { ar: "التسعير", en: "Pricing" }],
  ["closing", { ar: "الإغلاق والأرشيف", en: "Closing & archive" }],
];

export default function TripProfilePage() {
  const params = useParams<{ id: string }>();
  const [tab, setTab] = useState<TripTab>("itinerary");
  const { locale } = useLocale();

  return (
    <AuthGate>
      {(user) => (
        <AppShell user={user}>
          <div className="space-y-6">
            <nav className="sticky top-0 z-20 flex gap-1 overflow-x-auto rounded-xl border bg-white p-2 shadow-sm">
              {tabs.map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium ${
                    tab === key ? "bg-cyan-800 text-white" : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  {label[locale]}
                </button>
              ))}
            </nav>
            <TripProfile tripId={params.id} activeTab={tab} />
          </div>
        </AppShell>
      )}
    </AuthGate>
  );
}
