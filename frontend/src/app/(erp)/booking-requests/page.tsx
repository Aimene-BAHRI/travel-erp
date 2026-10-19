"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { MutationMessage } from "@/components/forms/mutation-message";
import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import type { Paginated } from "@/features/reference/types";
import { apiRequest, downloadFile, fetchPrivatePreview } from "@/lib/api/client";
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
  attachments: { id: string; original_filename: string; mime_type: string; size_bytes: number }[];
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
  const [preview, setPreview] = useState<{ lead: Lead; attachment: Lead["attachments"][number] } | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);
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
  const openPreview = async (lead: Lead, attachment: Lead["attachments"][number]) => {
    try {
      const url = await fetchPrivatePreview(`/bookings/requests/${lead.id}/attachments/${attachment.id}/preview/`);
      setPreviewUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return url;
      });
      setPreview({ lead, attachment });
    } catch (error) {
      console.error("Could not preview private passport attachment", error);
    }
  };

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
                    <div key={attachment.id} className="mb-3 rounded-lg border p-3 sm:inline-flex sm:items-center sm:gap-3">
                      {attachment.mime_type.startsWith("image/") && (
                        <button type="button" onClick={() => openPreview(lead, attachment)} className="mb-2 flex size-24 items-center justify-center rounded bg-slate-100 text-xs text-cyan-800 sm:mb-0">
                          {uiText("Preview image")}
                        </button>
                      )}
                      <div className="min-w-0">
                        <p className="max-w-72 break-all text-sm">{attachment.original_filename}</p>
                        <p className="text-xs text-slate-500">{Math.ceil(attachment.size_bytes / 1024)} KB</p>
                        <div className="mt-2 flex gap-2">
                          {attachment.mime_type.startsWith("image/") && <button type="button" onClick={() => openPreview(lead, attachment)} className="rounded border px-3 py-1.5 text-sm text-cyan-800">{uiText("Preview")}</button>}
                          <button type="button" disabled={download.isPending} onClick={() => download.mutate({ lead, attachment })} className="rounded border px-3 py-1.5 text-sm text-cyan-800">{uiText("Download")}</button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
      {!leads.isPending && leads.data?.count === 0 && <p>{uiText("لا توجد طلبات حجز بعد.")}</p>}
      {preview && previewUrl && (
        <div role="dialog" aria-modal="true" aria-label={uiText("Passport image preview")} className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => { URL.revokeObjectURL(previewUrl); setPreviewUrl(null); setPreview(null); }}>
          <div className="max-h-[95vh] w-full max-w-5xl rounded-xl bg-white p-4" onClick={(event) => event.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="truncate font-medium">{preview.attachment.original_filename}</p>
              <div className="flex shrink-0 gap-2">
                <button type="button" onClick={() => download.mutate({ lead: preview.lead, attachment: preview.attachment })} className="rounded border px-3 py-2 text-sm text-cyan-800">{uiText("Download")}</button>
                <button type="button" onClick={() => { URL.revokeObjectURL(previewUrl); setPreviewUrl(null); setPreview(null); }} className="rounded border px-3 py-2 text-sm">{uiText("Close")}</button>
              </div>
            </div>
            <div className="flex max-h-[calc(95vh-5rem)] justify-center overflow-auto bg-slate-100 p-2">
              <img src={previewUrl} alt={preview.attachment.original_filename} className="max-h-[calc(95vh-6rem)] max-w-full object-contain" />
            </div>
          </div>
        </div>
      )}      <div className="mt-5 flex gap-3">
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
