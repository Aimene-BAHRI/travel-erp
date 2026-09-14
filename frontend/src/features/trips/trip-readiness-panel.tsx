"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiRequest, downloadFile } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";
import { MutationMessage } from "@/components/forms/mutation-message";
import { OperationalSummary, type ReadinessReport } from "./operational-summary";
export function TripReadinessPanel({ tripId }: { tripId: string }) {
 const { locale } = useLocale();
 const report = useQuery({ queryKey: ["trip-readiness", tripId], queryFn: () => apiRequest<ReadinessReport>(`/trips/${tripId}/readiness/`) });
 const download = useMutation({ mutationFn: () => downloadFile(`/trips/${tripId}/export-xlsx/`, `Wakaltcom-${tripId}.xlsx`) });
 return <div className="space-y-3">{report.data && <OperationalSummary report={report.data} />}<div className="flex justify-end"><button disabled={download.isPending} onClick={() => download.mutate()} className="rounded-lg border bg-white px-4 py-2 text-sm">{locale === "ar" ? "تصدير Excel للمسافرين الفعليين" : "Export Excel · real travelers"}</button></div><MutationMessage error={report.error || download.error} /></div>;
}
