"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";

type Rule = {
  id: string;
  event: string;
  label: string;
  is_enabled: boolean;
  lead_days: number;
  branch_only: boolean;
};

const copy = {
  ar: {
    allBranches: "كل الفروع",
    branchOnly: "مستخدمو الفرع فقط",
    days: "يوم",
    empty: "لا توجد قواعد إشعارات بعد.",
    leadDays: "قبل الموعد",
    loading: "جاري تحميل إعدادات الإشعارات...",
    off: "متوقف",
    on: "مفعّل",
    scope: "النطاق",
    settings: "إعدادات الإشعارات",
    subtitle: "فعّل أو أوقف التنبيهات وحدد توقيتها ومن تصل إليه داخل الوكالة.",
  },
  en: {
    allBranches: "All branches",
    branchOnly: "Branch users only",
    days: "days",
    empty: "No notification rules yet.",
    leadDays: "Lead days",
    loading: "Loading notification settings...",
    off: "Off",
    on: "On",
    scope: "Scope",
    settings: "Notification settings",
    subtitle:
      "Activate alerts and choose their timing and who receives them inside the agency.",
  },
};

const eventLabels: Record<string, { ar: string; en: string }> = {
  BOOKING_BALANCE: {
    ar: "رصيد الحجز قبل المغادرة",
    en: "Booking balance before departure",
  },
  BOOKING_CANCELLED: {
    ar: "إلغاء حجز",
    en: "Booking cancelled",
  },
  BOOKING_CREATED: {
    ar: "إنشاء حجز جديد",
    en: "Booking created",
  },
  BOOKING_REQUEST: {
    ar: "طلب حجز جديد من الموقع",
    en: "New public booking request",
  },
  CLOSING_OVERDUE: {
    ar: "تأخر إغلاق الرحلة",
    en: "Trip closing task overdue",
  },
  PASSPORT_ATTENTION: {
    ar: "جواز ناقص أو يحتاج متابعة",
    en: "Passport missing or expiring",
  },
  PAYMENT_RECEIVED: {
    ar: "استلام دفعة من عميل",
    en: "Customer payment received",
  },
  ROOM_ALLOCATION: {
    ar: "توزيع الغرف غير مكتمل",
    en: "Room allocation incomplete",
  },
  SUPPLIER_DUE: {
    ar: "استحقاق مصروف مورد",
    en: "Supplier expense due",
  },
  TRIP_CHANGED: {
    ar: "تغيير في برنامج الرحلة",
    en: "Trip itinerary changed",
  },
  TRIP_CLOSING: {
    ar: "رحلة تنتظر الإغلاق",
    en: "Trip pending closing",
  },
  TRIP_DEPARTURE: {
    ar: "اقتراب موعد انطلاق الرحلة",
    en: "Trip departure approaching",
  },
  TRANSPORT_DETAILS: {
    ar: "تفاصيل النقل البري غير مكتملة",
    en: "Ground transport details incomplete",
  },
};

function labelFor(rule: Rule, locale: "ar" | "en") {
  return eventLabels[rule.event]?.[locale] ?? rule.label;
}

export function NotificationSettings() {
  const cache = useQueryClient();
  const { locale, isRtl } = useLocale();
  const t = copy[locale];
  const rules = useQuery({
    queryKey: ["notification-rules"],
    queryFn: () => apiRequest<Paginated<Rule>>("/notifications/rules/"),
  });
  const save = useMutation({
    mutationFn: (rule: Rule) =>
      apiRequest<Rule>(`/notifications/rules/${rule.id}/`, {
        method: "PATCH",
        body: JSON.stringify(rule),
      }),
    onSuccess: () =>
      cache.invalidateQueries({ queryKey: ["notification-rules"] }),
  });

  return (
    <section
      className={`rounded-xl border bg-white ${isRtl ? "text-right" : "text-left"}`}
    >
      <header className="border-b p-5">
        <h2 className="font-semibold">{t.settings}</h2>
        <p className="text-sm text-slate-500">{t.subtitle}</p>
      </header>

      {rules.isPending && (
        <p className="p-6 text-sm text-slate-500">{t.loading}</p>
      )}

      <div className="divide-y">
        {rules.data?.results.map((rule) => (
          <div
            key={rule.id}
            className="grid gap-4 p-4 sm:p-5 lg:grid-cols-[minmax(0,1fr)_auto_auto]"
          >
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={rule.is_enabled}
                onChange={(event) =>
                  save.mutate({ ...rule, is_enabled: event.target.checked })
                }
              />
              <span>
                <span className="block font-medium">
                  {labelFor(rule, locale)}
                </span>
                <span
                  className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs ${
                    rule.is_enabled
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {rule.is_enabled ? t.on : t.off}
                </span>
              </span>
            </label>

            <label className="flex items-center justify-between gap-3 text-sm sm:justify-start">
              <span>{t.leadDays}</span>
              <input
                className="w-24 rounded border px-2 py-1 text-left"
                type="number"
                min="0"
                value={rule.lead_days}
                onChange={(event) =>
                  save.mutate({
                    ...rule,
                    lead_days: Number(event.target.value),
                  })
                }
              />
              <span className="text-slate-500">{t.days}</span>
            </label>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={rule.branch_only}
                onChange={(event) =>
                  save.mutate({ ...rule, branch_only: event.target.checked })
                }
              />
              <span>{rule.branch_only ? t.branchOnly : t.allBranches}</span>
            </label>
          </div>
        ))}
      </div>

      {!rules.isPending && !rules.data?.results.length && (
        <p className="p-10 text-center text-sm text-slate-500">{t.empty}</p>
      )}
    </section>
  );
}
