"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock3 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";

import { notificationAppearance, NotificationStatus } from "./notification-appearance";
import { formatNotificationTime } from "./time";
import type { NotificationRecord } from "./types";

const copy = {
  ar: {
    all: "الكل",
    active: "النشطة",
    empty: "لا توجد إشعارات في هذا العرض.",
    earlier: "أقدم",
    inbox: "صندوق الإشعارات",
    markAllRead: "تعليم الكل كمقروء",
    resolved: "تمت المعالجة",
    subtitle: "تنبيهات تشغيلية للرحلات والحجوزات والمسافرين والمصاريف.",
    today: "اليوم",
    unread: "غير المقروءة",
    yesterday: "أمس",
  },
  en: {
    all: "All",
    active: "Active",
    empty: "No notifications in this view.",
    earlier: "Earlier",
    inbox: "Notification inbox",
    markAllRead: "Mark all read",
    resolved: "Resolved",
    subtitle: "Operational alerts for trips, bookings, travelers, and expenses.",
    today: "Today",
    unread: "Unread",
    yesterday: "Yesterday",
  },
};

type View = "unread" | "active" | "all";

export function NotificationInbox() {
  const [view, setView] = useState<View>("unread");
  const cache = useQueryClient();
  const { locale, isRtl } = useLocale();
  const t = copy[locale];
  const views: View[] = ["unread", "active", "all"];

  const notes = useQuery({
    queryKey: ["notifications", view],
    queryFn: () => apiRequest<Paginated<NotificationRecord>>(`/notifications/?view=${view}`),
  });
  const groupedNotes = groupNotifications(notes.data?.results ?? []);
  const refresh = () => cache.invalidateQueries({ queryKey: ["notifications"] });
  const readAll = useMutation({
    mutationFn: () => apiRequest("/notifications/read-all/", { method: "POST" }),
    onSuccess: refresh,
  });
  const read = useMutation({
    mutationFn: (id: string) => apiRequest(`/notifications/${id}/read/`, { method: "POST" }),
    onSuccess: refresh,
  });

  return (
    <section className={`rounded-xl border bg-white ${isRtl ? "text-right" : "text-left"}`}>
      <header className="flex flex-col gap-4 border-b p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
        <div>
          <h2 className="font-semibold">{t.inbox}</h2>
          <p className="text-sm text-slate-500">{t.subtitle}</p>
        </div>
        <button
          onClick={() => readAll.mutate()}
          className="w-full rounded-lg border px-3 py-2 text-sm sm:w-auto"
        >
          {t.markAllRead}
        </button>
      </header>
      <div className="flex gap-2 overflow-x-auto border-b p-4">
        {views.map((x) => (
          <button
            key={x}
            onClick={() => setView(x)}
            className={`shrink-0 rounded-full px-3 py-1 text-sm ${
              view === x ? "bg-cyan-800 text-white" : "bg-slate-100"
            }`}
          >
            {t[x]}
          </button>
        ))}
      </div>
      <div>
        {groupedNotes.map((group) => (
          <section key={group.key}>
            <h3 className="border-b bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 sm:px-5">
              {t[group.key]}
            </h3>
            <div className="divide-y">
              {group.items.map((n) => (
                <Link
                  key={n.id}
                  href={n.target_url}
                  onClick={() => read.mutate(n.id)}
                  className={`block border-s-4 p-4 transition-colors focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-cyan-700 sm:p-5 ${notificationAppearance(n).row}`}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <div>
                      <NotificationStatus note={n} locale={locale} />
                      <p className="font-semibold">{n.title}</p>
                      <p className="mt-1 text-sm text-slate-600">{n.message}</p>
                      <p className="mt-2 inline-flex items-center gap-1 text-xs text-slate-500">
                        <Clock3 className="size-3" />
                        {formatNotificationTime(n.created_at, locale)}
                      </p>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        ))}
        {!notes.isPending && !notes.data?.results.length && (
          <p className="p-10 text-center text-sm text-slate-500">{t.empty}</p>
        )}
      </div>
    </section>
  );
}

function groupNotifications(items: NotificationRecord[]) {
  const groups: Array<{ key: "today" | "yesterday" | "earlier"; items: NotificationRecord[] }> = [
    { key: "today", items: [] },
    { key: "yesterday", items: [] },
    { key: "earlier", items: [] },
  ];
  const now = new Date();
  const today = startOfDay(now);
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  for (const item of items) {
    const created = startOfDay(new Date(item.created_at));
    if (created.getTime() === today.getTime()) {
      groups[0].items.push(item);
    } else if (created.getTime() === yesterday.getTime()) {
      groups[1].items.push(item);
    } else {
      groups[2].items.push(item);
    }
  }

  return groups.filter((group) => group.items.length);
}

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}
