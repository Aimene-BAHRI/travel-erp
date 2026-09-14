import { CircleAlert, CircleCheck, Info, TriangleAlert } from "lucide-react";

import type { NotificationRecord } from "./types";

const actionEvents = new Set([
  "TRIP_CLOSING", "BOOKING_BALANCE", "SUPPLIER_DUE", "PASSPORT_ATTENTION",
  "ROOM_ALLOCATION", "CLOSING_OVERDUE", "BOOKING_REQUEST", "TRANSPORT_DETAILS",
]);
const warningEvents = new Set(["TRIP_DEPARTURE", "BOOKING_CANCELLED"]);

const appearances = {
  success: { icon: CircleCheck, label: { en: "Ready", ar: "جاهز" }, row: "border-s-emerald-500 bg-emerald-50/40 hover:bg-emerald-50", badge: "bg-emerald-100 text-emerald-800" },
  info: { icon: Info, label: { en: "Information", ar: "معلومة" }, row: "border-s-blue-500 bg-blue-50/40 hover:bg-blue-50", badge: "bg-blue-100 text-blue-800" },
  warning: { icon: TriangleAlert, label: { en: "Warning", ar: "تحذير" }, row: "border-s-amber-500 bg-amber-50/40 hover:bg-amber-50", badge: "bg-amber-100 text-amber-900" },
  action: { icon: CircleAlert, label: { en: "Action required", ar: "يتطلب إجراء" }, row: "border-s-red-500 bg-red-50/40 hover:bg-red-50", badge: "bg-red-100 text-red-800" },
  resolved: { icon: CircleCheck, label: { en: "Resolved", ar: "تمت المعالجة" }, row: "border-s-emerald-500 bg-white hover:bg-emerald-50/40", badge: "bg-emerald-100 text-emerald-800" },
};

export function notificationAppearance(note: NotificationRecord) {
  if (!note.resolved_at && note.event === "READINESS" && note.severity) return appearances[({ SUCCESS: "success", INFO: "info", WARNING: "warning", ERROR: "action" } as const)[note.severity]];
  return appearances[note.resolved_at ? "resolved" : actionEvents.has(note.event) ? "action" : warningEvents.has(note.event) ? "warning" : "info"];
}

export function NotificationStatus({ note, locale }: { note: NotificationRecord; locale: "en" | "ar" }) {
  const appearance = notificationAppearance(note);
  const Icon = appearance.icon;

  return (
    <div className="mb-2 flex flex-wrap items-center gap-2">
      <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium ${appearance.badge}`}>
        <Icon className="size-3.5" aria-hidden="true" />
        {appearance.label[locale]}
      </span>
      {!note.read_at && (
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600">
          <span className="size-1.5 rounded-full bg-slate-600" aria-hidden="true" />
          {locale === "ar" ? "غير مقروء" : "Unread"}
        </span>
      )}
    </div>
  );
}
