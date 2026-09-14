"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { MutationMessage } from "@/components/forms/mutation-message";
import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import type { Paginated } from "@/features/reference/types";
import { apiRequest, downloadFile } from "@/lib/api/client";
import { statusAr } from "@/lib/i18n/ar";

type Lead = {
  id: string;
  reference: string;
  trip_name: string;
  customer_name: string;
  phone: string;
  email: string;
  adults: number;
  children: number;
  children_with_bed: number;
  children_without_bed: number;
  infants: number;
  package_name?: string;
  calculated_total: string | null;
  currency_code: string;
  notes: string;
  status: string;
  booking_id?: string | null;
  attachments: { id: string; original_filename: string; size_bytes: number }[];
  pricing_snapshot: {
    unit_prices?: Record<string, string>;
    counts?: Record<string, number>;
  };
};

const categoryLabels: Record<string, string> = {
  adult: "بالغ",
  child_bed: "طفل بسرير",
  child_no_bed: "طفل بدون سرير",
  infant: "رضيع",
};

const requestStatuses = ["NEW", "CONTACTED", "QUALIFIED", "CONVERTED", "REJECTED"];

export default function RequestsPage() {
  return (
    <AuthGate>
      {(user) => (
        <AppShell user={user}>
          <Requests />
        </AppShell>
      )}
    </AuthGate>
  );
}

function Requests() {
  const uiText = useUiText();
  const router = useRouter();
  const cache = useQueryClient();
  const [page, setPage] = useState(1);
  const leads = useQuery({
    queryKey: ["booking-requests", page],
    queryFn: () => apiRequest<Paginated<Lead>>(`/bookings/requests/?page=${page}`),
  });
  const save = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      apiRequest(`/bookings/requests/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["booking-requests"] }),
  });
  const convert = useMutation({
    mutationFn: (id: string) =>
      apiRequest<{ id: string }>(`/bookings/requests/${id}/convert/`, {
        method: "POST",
      }),
    onSuccess: (booking) => {
      cache.invalidateQueries({ queryKey: ["booking-requests"] });
      router.push(`/bookings/${booking.id}`);
    },
  });
  const download = useMutation({
    mutationFn: ({
      lead,
      attachment,
    }: {
      lead: Lead;
      attachment: Lead["attachments"][number];
    }) =>
      downloadFile(
        `/bookings/requests/${lead.id}/attachments/${attachment.id}/download/`,
        attachment.original_filename,
      ),
  });

  return (
    <div>
      <h1 className="text-3xl font-semibold">{uiText("طلبات الحجز")}</h1>
      <p className="mb-6 mt-2 text-slate-600">
        {uiText("تقديرات الرحلات المحفوظة ومرفقات جوازات السفر الخاصة.")}
      </p>
      <MutationMessage error={save.error || convert.error || download.error || leads.error} />
      {leads.isPending ? (
        <p>{uiText("جاري تحميل الطلبات...")}</p>
      ) : (
        <div className="space-y-4">
          {leads.data?.results.map((lead) => (
            <article key={lead.id} className="rounded-xl border bg-white p-5">
              <div className="flex flex-wrap justify-between gap-4">
                <div>
                  <h2 className="font-semibold">{lead.customer_name}</h2>
                  <p className="font-mono text-xs text-slate-500">{lead.reference}</p>
                  <p className="mt-2">
                    {lead.trip_name} · {lead.package_name || uiText("لم يتم تسجيل الباقة")}
                  </p>
                  <p className="text-sm">
                    {lead.adults} {uiText("بالغ ·")} {lead.children} {uiText("طفل (")}{lead.children_with_bed} {uiText("بسرير،")}{" "}
                    {lead.children_without_bed} {uiText("بدون سرير) ·")} {lead.infants} {uiText("رضيع")}
                  </p>
                  <a href={`tel:${lead.phone}`} className="text-cyan-800">
                    {lead.phone}
                  </a>
                  <p>{lead.email}</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm">{lead.notes}</p>
                </div>
                <div>
                  <p className="text-sm text-slate-500">{uiText("التقدير عند الإرسال")}</p>
                  <p className="text-xl font-bold">
                    {lead.calculated_total !== null
                      ? `${Number(lead.calculated_total).toLocaleString("fr-DZ")} ${lead.currency_code}`
                      : uiText("غير محسوب (طلب قديم)")}
                  </p>
                  <select
                    aria-label={`حالة الطلب ${lead.reference}`}
                    disabled={save.isPending || Boolean(lead.booking_id)}
                    value={lead.status}
                    onChange={(event) => save.mutate({ id: lead.id, status: event.target.value })}
                    className="mt-3 rounded-lg border p-2"
                  >
                    {requestStatuses.map((status) => (
                      <option key={status} value={status}>
                        {uiText(statusAr(status))}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {lead.pricing_snapshot.unit_prices && (
                <details className="mt-3 text-sm">
                  <summary>{uiText("تفاصيل السعر المحفوظ")}</summary>
                  {Object.entries(lead.pricing_snapshot.unit_prices).map(([key, value]) => (
                    <p key={key}>
                      {uiText(categoryLabels[key] ?? key.replaceAll("_", " "))}:{" "}
                      {lead.pricing_snapshot.counts?.[key] ?? 0} ×{" "}
                      {Number(value).toLocaleString("fr-DZ")} {lead.currency_code}
                    </p>
                  ))}
                </details>
              )}
              <div className="mt-4 flex flex-wrap items-center gap-3 border-t pt-3">
                {lead.booking_id ? (
                  <button
                    onClick={() => router.push(`/bookings/${lead.booking_id}`)}
                    className="rounded-lg bg-cyan-800 px-3 py-2 text-sm text-white"
                  >
                    {uiText("فتح الحجز المسودة")}
                  </button>
                ) : (
                  <button
                    disabled={convert.isPending || lead.status === "REJECTED"}
                    onClick={() => convert.mutate(lead.id)}
                    className="rounded-lg bg-cyan-800 px-3 py-2 text-sm text-white"
                  >
                    {convert.isPending ? uiText("جاري إنشاء المسودة...") : uiText("تحويل إلى حجز مسودة")}
                  </button>
                )}
              </div>
              {lead.attachments.length > 0 && (
                <div className="mt-4 border-t pt-3">
                  <p className="mb-2 text-sm font-medium">{uiText("مرفقات جوازات السفر الخاصة")}</p>
                  {lead.attachments.map((attachment) => (
                    <button
                      key={attachment.id}
                      disabled={download.isPending}
                      onClick={() => download.mutate({ lead, attachment })}
                      className="mb-2 ml-3 max-w-full break-all rounded-lg border px-3 py-2 text-sm text-cyan-800"
                    >
                      {uiText("تحميل")} {attachment.original_filename} (
                      {Math.ceil(attachment.size_bytes / 1024)} KB)
                    </button>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
      {!leads.isPending && leads.data?.count === 0 && <p>{uiText("لا توجد طلبات حجز بعد.")}</p>}
      <div className="mt-5 flex gap-3">
        <button disabled={!leads.data?.previous} onClick={() => setPage(page - 1)}>
          {uiText("السابق")}
        </button>
        <span>{uiText("الصفحة")} {page}</span>
        <button disabled={!leads.data?.next} onClick={() => setPage(page + 1)}>
          {uiText("التالي")}
        </button>
      </div>
    </div>
  );
}
