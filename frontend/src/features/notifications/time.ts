import type { Locale } from "@/lib/i18n/context";

export function formatNotificationTime(value: string, locale: Locale) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const now = new Date();
  const diffSeconds = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 1000));
  const rtf = new Intl.RelativeTimeFormat(locale === "ar" ? "ar-DZ" : "en", {
    numeric: "auto",
  });

  if (diffSeconds < 60) return rtf.format(-diffSeconds, "second");

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return rtf.format(-diffMinutes, "minute");

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return rtf.format(-diffHours, "hour");

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return rtf.format(-diffDays, "day");

  return new Intl.DateTimeFormat(locale === "ar" ? "ar-DZ" : "en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
