"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Clock3 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";

import { notificationAppearance, NotificationStatus } from "./notification-appearance";
import { formatNotificationTime } from "./time";
import type { NotificationRecord as Note } from "./types";

const copy = {
  ar: {
    empty: "لا توجد إشعارات غير مقروءة",
    notifications: "الإشعارات",
    viewAll: "عرض الكل",
  },
  en: {
    empty: "No unread notifications",
    notifications: "Notifications",
    viewAll: "View all",
  },
};

export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const cache = useQueryClient();
  const { locale, isRtl } = useLocale();
  const t = copy[locale];
  const notes = useQuery({
    queryKey: ["notifications", "unread"],
    refetchInterval: 60000,
    queryFn: () => apiRequest<Paginated<Note>>("/notifications/?view=unread"),
  });
  const read = useMutation({
    mutationFn: (id: string) => apiRequest(`/notifications/${id}/read/`, { method: "POST" }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const unread = notes.data?.count ?? 0;

  return (
    <div className="relative">
      <button
        aria-label={t.notifications}
        onClick={() => setOpen(!open)}
        className="relative rounded-lg p-2 hover:bg-slate-100"
      >
        <Bell className="size-5" />
        {unread > 0 && (
          <span
            className={`absolute top-0 grid size-4 place-items-center rounded-full bg-red-600 text-[10px] text-white ${
              isRtl ? "left-0" : "right-0"
            }`}
          >
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div
          className={`fixed inset-x-3 top-16 z-50 max-h-[calc(100vh-5rem)] overflow-hidden rounded-xl border bg-white shadow-xl sm:absolute sm:inset-x-auto sm:top-11 sm:w-96 ${
            isRtl ? "text-right sm:left-0" : "text-left sm:right-0"
          }`}
        >
          <div className="flex items-center justify-between gap-4 border-b p-4 font-semibold">
            <span>{t.notifications}</span>
            <Link
              href="/notifications"
              onClick={() => setOpen(false)}
              className="shrink-0 text-sm text-cyan-800"
            >
              {t.viewAll}
            </Link>
          </div>
          <div className="max-h-[calc(100vh-9rem)] divide-y overflow-auto">
            {notes.data?.results.map((note) => (
              <Link
                key={note.id}
                href={note.target_url}
                onClick={() => {
                  read.mutate(note.id);
                  setOpen(false);
                }}
                className={`block border-s-4 p-4 transition-colors focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-cyan-700 ${notificationAppearance(note).row}`}
              >
                <NotificationStatus note={note} locale={locale} />
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="text-sm font-semibold">{note.title}</p>
                  <span className="inline-flex shrink-0 items-center gap-1 text-[11px] text-slate-500">
                    <Clock3 className="size-3" />
                    {formatNotificationTime(note.created_at, locale)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-600">{note.message}</p>
              </Link>
            ))}
            {!notes.data?.results.length && (
              <p className="p-6 text-center text-sm text-slate-500">{t.empty}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
