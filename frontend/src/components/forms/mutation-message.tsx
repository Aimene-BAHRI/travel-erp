"use client";

import { ApiError } from "@/lib/api/client";
import { useOperationalText } from "@/lib/i18n/operational";

function flatten(value: unknown, t: (text: string) => string): string {
  if (typeof value === "string") return t(value);
  if (Array.isArray(value)) return value.map(item => flatten(item, t)).join(" ");
  if (value && typeof value === "object") return Object.entries(value).map(([key, item]) => {
    const label = key.replaceAll("_", " ");
    const prefix = ["detail", "non_field_errors"].includes(key) ? "" : `${t(label.charAt(0).toUpperCase() + label.slice(1))}: `;
    return `${prefix}${flatten(item, t)}`;
  }).join(" ");
  return t("The request could not be completed.");
}

export function MutationMessage({ error, success }: Readonly<{ error?: Error | null; success?: string }>) {
  const t = useOperationalText();
  if (error) return <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error instanceof ApiError ? flatten(error.body, t) : t(error.message)}</p>;
  if (success) return <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{t(success)}</p>;
  return null;
}
