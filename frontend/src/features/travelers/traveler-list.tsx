"use client";

import { useQuery } from "@tanstack/react-query";
import { Eye, LoaderCircle, Search, Users, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";
import type { PassportDetail, Traveler } from "./types";
import { PassportImage } from "./passport-image";

function useText() {
  const { locale } = useLocale();
  return (en: string, ar: string) => locale === "ar" ? ar : en;
}

function nameOf(traveler: Traveler) {
  return traveler.current_passport?.full_name || traveler.display_name;
}

function Photo({ traveler, large = false }: { traveler: Traveler; large?: boolean }) {
  const [failed, setFailed] = useState(false);
  const size = large ? "h-32 w-24" : "h-14 w-11";
  return traveler.current_photo_url && !failed ? (
    // Authenticated document endpoint; request directly from the user's browser.
    // eslint-disable-next-line @next/next/no-img-element
    <img src={traveler.current_photo_url} alt={nameOf(traveler)} onError={() => setFailed(true)}
      className={`${size} shrink-0 rounded-lg border border-slate-200 object-cover`} />
  ) : <div aria-hidden="true" className={`${size} flex shrink-0 items-center justify-center rounded-lg bg-cyan-50 font-semibold text-cyan-800`}>
    {nameOf(traveler).split(/\s+/).map(part => part[0]).slice(0, 2).join("")}
  </div>;
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return <div className="min-w-0"><dt className="text-xs text-slate-500">{label}</dt>
    <dd className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-900">{value?.trim() || "—"}</dd></div>;
}

function TravelerPreview({ selected, onClose }: { selected: Traveler; onClose: () => void }) {
  const t = useText();
  const dialog = useRef<HTMLDialogElement>(null);
  const traveler = useQuery({ queryKey: ["traveler", selected.id],
    queryFn: () => apiRequest<Traveler>(`/travelers/${selected.id}/`), initialData: selected });
  const data = traveler.data;
  const passportId = data.current_passport?.id;
  const passport = useQuery({ queryKey: ["passport-preview", passportId],
    queryFn: () => apiRequest<PassportDetail>(`/travelers/passports/${passportId}/`), enabled: !!passportId });
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  const gender = (value?: string) => value === "M" ? t("Male", "ذكر") : value === "F" ? t("Female", "أنثى") : t("Unspecified", "غير محدد");
  const photoSource = data.current_photo_source === "PASSPORT_MANUAL_CROP" ? t("Cropped from passport", "مقتصة من جواز السفر")
    : data.current_photo_source === "PASSPORT_AUTO_CROP" ? t("Extracted from passport", "مستخرجة من جواز السفر")
    : data.current_photo_source === "MANUAL_UPLOAD" ? t("Uploaded photo", "صورة مرفوعة") : "—";
  return <dialog ref={dialog} aria-labelledby="traveler-preview-title" onCancel={onClose}
    className="m-auto max-h-[90vh] w-[calc(100%_-_2rem)] max-w-3xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-0 shadow-xl backdrop:bg-slate-950/50">
    <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b bg-white p-5">
      <div><p className="text-xs font-medium text-cyan-800">{t("Traveler preview", "معاينة المسافر")}</p>
        <h2 id="traveler-preview-title" className="mt-1 text-xl font-semibold">{nameOf(data)}</h2></div>
      <button autoFocus onClick={onClose} aria-label={t("Close preview", "إغلاق المعاينة")} className="rounded-lg p-2 hover:bg-slate-100"><X className="size-5" /></button>
    </header>
    <div className="space-y-6 p-5 sm:p-6">
      {traveler.isError && <p role="alert" className="text-sm text-amber-800">{t("Could not refresh this profile. Showing the directory record.", "تعذر تحديث الملف. تعرض بيانات الدليل الحالية.")}</p>}
      <div className="flex gap-5"><Photo key={`${data.id}-${data.current_photo_url}`} traveler={data} large />
        <dl className="grid flex-1 grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t("Profile name", "اسم الملف")} value={[data.first_name, data.last_name].filter(Boolean).join(" ")} />
          <Field label={t("Branch", "الفرع")} value={data.branch_name} />
          <Field label={t("Profile birth date", "تاريخ الميلاد في الملف")} value={data.birth_date} />
          <Field label={t("Gender", "الجنس")} value={gender(data.gender)} />
          <Field label={t("Profile status", "حالة الملف")} value={data.is_active ? t("Active", "نشط") : t("Inactive", "غير نشط")} />
          <Field label={t("Photo source", "مصدر الصورة")} value={photoSource} />
        </dl></div>
      <section><h3 className="mb-3 font-semibold">{t("Contact details", "بيانات الاتصال")}</h3>
        <dl className="grid gap-4 sm:grid-cols-2"><Field label={t("Phone", "الهاتف")} value={data.phone} /><Field label={t("Email", "البريد الإلكتروني")} value={data.email} />
          <div className="sm:col-span-2"><Field label={t("Address", "العنوان")} value={data.address} /></div></dl></section>
      <section className="rounded-xl border border-slate-200 p-4"><h3 className="mb-3 font-semibold">{t("Current passport", "جواز السفر الحالي")}</h3>
        {data.current_passport ? <>
          <dl className="grid gap-4 sm:grid-cols-2">
            <Field label={t("Full passport name", "الاسم الكامل في الجواز")} value={data.current_passport.full_name} />
            <Field label={t("Passport number", "رقم جواز السفر")} value={data.current_passport.passport_number} />
            <Field label={t("Nationality", "الجنسية")} value={data.current_passport.nationality_code} />
            <Field label={t("Birth date", "تاريخ الميلاد")} value={data.current_passport.birth_date} />
            <Field label={t("Gender", "الجنس")} value={gender(data.current_passport.gender)} />
            <Field label={t("Expiry date", "تاريخ الانتهاء")} value={data.current_passport.expiry_date} />
            <Field label={t("Record status", "حالة السجل")} value={data.current_passport.status === "CURRENT" ? t("Current", "حالي") : data.current_passport.status === "EXPIRED" ? t("Expired", "منتهي") : t("Replaced", "مستبدل")} />
            {passport.data && <><Field label={t("Issue date", "تاريخ الإصدار")} value={passport.data.issue_date} />
              <Field label={t("Birth place", "مكان الميلاد")} value={passport.data.birth_place} />
              <Field label={t("Issue place", "مكان الإصدار")} value={passport.data.issue_place} />
              <div className="sm:col-span-2"><Field label={t("Machine-readable passport text", "النص المقروء آلياً للجواز")} value={passport.data.mrz} /></div></>}
          </dl>
          {passport.isPending && <p role="status" className="mt-3 text-sm text-slate-500">{t("Loading passport details…", "جار تحميل بيانات الجواز…")}</p>}
          {passport.isError && <button onClick={() => passport.refetch()} className="mt-3 text-sm text-cyan-800 underline">{t("Passport details could not load. Retry", "تعذر تحميل بيانات الجواز. إعادة المحاولة")}</button>}
        </> : <p className="text-sm text-slate-500">{t("No current passport", "لا يوجد جواز سفر حالي")}</p>}
      </section>
      <PassportImage url={data.current_passport?.passport_image_url} />
      <dl><Field label={t("Notes", "ملاحظات")} value={data.notes} /></dl>
      <dl className="grid gap-4 border-t pt-4 sm:grid-cols-2">
        <Field label={t("Created", "تاريخ الإنشاء")} value={data.created_at ? new Date(data.created_at).toLocaleString() : null} />
        <Field label={t("Last updated", "آخر تحديث")} value={data.updated_at ? new Date(data.updated_at).toLocaleString() : null} />
      </dl>
      <details className="text-sm text-slate-500"><summary className="cursor-pointer">{t("Record references", "مراجع السجلات")}</summary>
        <dl className="mt-3 grid gap-3"><Field label={t("Traveler ID", "معرف المسافر")} value={data.id} /><Field label={t("Branch ID", "معرف الفرع")} value={data.branch} /><Field label={t("Passport ID", "معرف الجواز")} value={passportId} /><Field label={t("Photo ID", "معرف الصورة")} value={data.current_photo} /></dl>
      </details>
    </div>
    <footer className="sticky bottom-0 flex justify-end gap-3 border-t bg-white p-4">
      <button onClick={onClose} className="rounded-lg border px-4 py-2 text-sm">{t("Close", "إغلاق")}</button>
      <Link href={`/travelers/${data.id}`} className="rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white">{t("Open full profile", "فتح الملف الكامل")}</Link>
    </footer>
  </dialog>;
}

export function TravelerList() {
  const t = useText();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Traveler | null>(null);
  const travelers = useQuery({ queryKey: ["travelers", search, page],
    queryFn: () => apiRequest<Paginated<Traveler>>(`/travelers/?search=${encodeURIComponent(search)}&page=${page}`) });
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  return <section className="rounded-xl border border-slate-200 bg-white">
    <div className="flex flex-col gap-4 border-b border-slate-200 p-5 md:flex-row md:items-center md:justify-between">
      <div><h2 className="font-semibold">{t("Traveler directory", "دليل المسافرين")}</h2>
        <p className="text-sm text-slate-500">{t("Identity, passport and contact details. Preview any traveler for more.", "الهوية والجواز وبيانات الاتصال. افتح المعاينة لعرض المزيد.")}</p></div>
      <label className="flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2"><Search className="size-4 text-slate-400" />
        <span className="sr-only">{t("Search travelers", "البحث عن مسافر")}</span>
        <input value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} placeholder={t("Name, passport or phone", "الاسم أو الجواز أو الهاتف")} className="min-w-0 flex-1 border-0 text-sm outline-none md:w-56" /></label>
    </div>
    {travelers.isPending ? <div role="status" aria-label={t("Loading travelers", "جار تحميل المسافرين")} className="grid min-h-56 place-items-center"><LoaderCircle className="size-7 animate-spin text-cyan-800" /></div>
      : travelers.isError ? <div role="alert" className="p-8 text-center"><p>{t("Could not load travelers.", "تعذر تحميل المسافرين.")}</p><button onClick={() => travelers.refetch()} className="mt-2 text-cyan-800 underline">{t("Try again", "إعادة المحاولة")}</button></div>
      : travelers.data?.results.length ? <>
        <div className="overflow-x-auto"><table className="w-full text-start text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr>
          {[t("Traveler", "المسافر"), t("Passport", "جواز السفر"), t("Contact", "الاتصال"), t("Branch / status", "الفرع / الحالة"), t("Details", "التفاصيل")].map(label => <th key={label} scope="col" className="px-5 py-3 text-start font-medium">{label}</th>)}
        </tr></thead><tbody className="divide-y divide-slate-100">{travelers.data.results.map(traveler => {
          const passport = traveler.current_passport;
          const expired = !!passport?.expiry_date && passport.expiry_date < today;
          return <tr key={traveler.id} className="hover:bg-slate-50/70">
            <td className="px-5 py-4"><div className="flex min-w-56 items-center gap-3"><Photo key={`${traveler.id}-${traveler.current_photo_url}`} traveler={traveler} /><div>
              <Link href={`/travelers/${traveler.id}`} className="font-semibold text-cyan-800 hover:underline">{nameOf(traveler)}</Link>
              <p className="mt-1 text-xs text-slate-500">{t("Born", "الميلاد")}: {passport?.birth_date || traveler.birth_date || "—"} · {(passport?.gender || traveler.gender) === "M" ? t("Male", "ذكر") : (passport?.gender || traveler.gender) === "F" ? t("Female", "أنثى") : t("Unspecified", "غير محدد")}</p>
            </div></div></td>
            <td className="px-5 py-4">{passport ? <><p className="whitespace-nowrap font-mono text-sm" dir="ltr">{passport.passport_number} <span className="font-sans text-xs text-slate-500">· {passport.nationality_code}</span></p><p className={`mt-1 whitespace-nowrap text-xs ${expired ? "font-medium text-red-700" : "text-slate-500"}`}>{expired ? t("Expired", "منتهي") : t("Expires", "ينتهي")}: {passport.expiry_date}</p></> : <span className="text-amber-800">{t("No current passport", "لا يوجد جواز حالي")}</span>}</td>
            <td className="px-5 py-4"><p dir="auto">{traveler.phone || "—"}</p><p className="mt-1 text-xs text-slate-500" dir="auto">{traveler.email || t("No email", "لا يوجد بريد")}</p></td>
            <td className="px-5 py-4"><p>{traveler.branch_name || "—"}</p><span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs ${traveler.is_active ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{traveler.is_active ? t("Active", "نشط") : t("Inactive", "غير نشط")}</span></td>
            <td className="px-5 py-4"><button onClick={() => setSelected(traveler)} aria-label={`${t("Preview", "معاينة")} ${nameOf(traveler)}`} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 font-medium text-cyan-800 hover:bg-cyan-50"><Eye className="size-4" />{t("Preview", "معاينة")}</button></td>
          </tr>;
        })}</tbody></table></div>
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t p-4 text-sm"><p className="text-slate-500">{travelers.data.count} {t("travelers", "مسافر")} · {t("Page", "صفحة")} {page}</p><div className="flex gap-2">
          <button disabled={!travelers.data.previous} onClick={() => setPage(page - 1)} className="rounded-lg border px-3 py-2 disabled:opacity-40">{t("Previous", "السابق")}</button>
          <button disabled={!travelers.data.next} onClick={() => setPage(page + 1)} className="rounded-lg border px-3 py-2 disabled:opacity-40">{t("Next", "التالي")}</button>
        </div></footer>
      </> : <div className="grid min-h-56 place-items-center text-center"><div><Users className="mx-auto size-8 text-slate-300" /><p className="mt-3 font-medium">{t("No travelers found", "لم يتم العثور على مسافرين")}</p><p className="text-sm text-slate-500">{t("Try a different search or add a traveler.", "جرب بحثاً آخر أو أضف مسافراً.")}</p></div></div>}
    {selected && <TravelerPreview key={selected.id} selected={selected} onClose={() => setSelected(null)} />}
  </section>;
}
