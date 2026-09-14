"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { X } from "lucide-react";

export function FormDialog({ title, description, open, onClose, children }: Readonly<{ title: string; description?: string; open: boolean; onClose: () => void; children: React.ReactNode }>) {
  const uiText = useUiText();
  if (!open) return null;
  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4" role="dialog" aria-modal="true"><div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white shadow-2xl"><header className="flex items-start justify-between border-b border-slate-200 p-5"><div><h2 className="text-xl font-semibold">{title}</h2>{description && <p className="mt-1 text-sm text-slate-500">{description}</p>}</div><button onClick={onClose} aria-label={uiText("Close")} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X className="size-5" /></button></header><div className="p-5">{children}</div></div></div>;
}
