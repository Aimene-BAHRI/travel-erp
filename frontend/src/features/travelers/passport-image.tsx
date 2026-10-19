"use client";

import { useState } from "react";
import { useLocale } from "@/lib/i18n/context";

export function PassportImage({ url }: { url?: string | null }) {
  const { locale } = useLocale();
  const t = (en: string, ar: string) => locale === "ar" ? ar : en;
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  return <section className="rounded-xl border border-slate-200 p-4">
    <div className="mb-3 flex items-center justify-between gap-3">
      <h3 className="font-semibold">{t("Full passport image", "صورة جواز السفر الكاملة")}</h3>
      {url && <a href={url} target="_blank" rel="noreferrer" className="text-sm text-cyan-800 underline">{t("Download original", "تحميل الصورة الأصلية")}</a>}
    </div>
    {url && failedUrl !== url ? (
      // The protected document is fetched with the user's existing browser session.
      // eslint-disable-next-line @next/next/no-img-element
      <img src={url} alt={t("Full passport scan", "صورة الجواز كاملة")} onError={() => setFailedUrl(url)} className="max-h-[32rem] w-full rounded-lg bg-slate-50 object-contain" />
    ) : <p className="text-sm text-slate-500">{url ? t("Image could not load. Use the download link to access the original.", "تعذر عرض الصورة. استخدم رابط تحميل الأصل.") : t("No full passport image saved. Add it when completing the booking passport details.", "لم تحفظ صورة الجواز الكاملة. أضفها عند إكمال بيانات الجواز في الحجز.")}</p>}
  </section>;
}
