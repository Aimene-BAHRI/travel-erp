"use client";
import { useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { PassportScanAssistant } from "@/features/travelers/passport-scan-assistant";
import { MutationMessage } from "@/components/forms/mutation-message";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";
import type { Country, Paginated } from "@/features/reference/types";
import { passportYears, suggestedIssueDate, type PassportPhoto } from "./passport-helpers";

export const blankPassport = { first_name: "", middle_name: "", last_name: "", birth_date: "", birth_place: "", issue_place: "", gender: "X", passport_number: "", issue_date: "", expiry_date: "", nationality: "", issuing_country: "", mrz: "" };
export type IntakePassport = typeof blankPassport;

export function PassportIntake({ value, onChange, returnDate, photo, onPhoto, scan, onScan, requireFields = true }: { value: IntakePassport; onChange: (value: IntakePassport) => void; returnDate?: string; photo: PassportPhoto | null; onPhoto: (photo: PassportPhoto | null) => void; scan: File | null; onScan: (file: File | null) => void; requireFields?: boolean }) {
  const { locale } = useLocale();
  const t = (en: string, ar: string) => locale === "ar" ? ar : en;
  const [warnings, setWarnings] = useState<string[]>([]);
  const [years, setYears] = useState<number | null>(null);
  const lastSuggestion = useRef("");
  const duration = years ?? passportYears(value.birth_date);
  const update = (next: IntakePassport) => {
    if (!next.issue_date || next.issue_date === lastSuggestion.current) {
      const suggestion = suggestedIssueDate(next.expiry_date, years ?? passportYears(next.birth_date));
      lastSuggestion.current = suggestion;
      onChange({ ...next, issue_date: suggestion });
    } else onChange(next);
  };
  const countries = useQuery({ queryKey: ["passport-intake-countries"], queryFn: async () => {
    const first = await apiRequest<Paginated<Country>>("/reference/countries/?ordering=name");
    let next = first.next;
    while (next) {
      const page = await apiRequest<Paginated<Country>>(`/reference/countries/${new URL(next, "http://localhost").search}`);
      first.results.push(...page.results); next = page.next;
    }
    return first.results;
  }});
  const parse = useMutation({ mutationFn: () => apiRequest<Partial<IntakePassport> & { nationality_code: string; issuing_country_code: string; mrz_warnings: string[] }>("/travelers/passports/parse-mrz/", { method: "POST", body: JSON.stringify({ mrz: value.mrz, reference_date: returnDate }) }), onSuccess: result => {
    const country = (code: string) => countries.data?.find(item => item.code === ({ DZA: "DZ", FRA: "FR", SAU: "SA", MAR: "MA", TUN: "TN" }[code] ?? code))?.id ?? "";
    update({ ...value, ...result, nationality: country(result.nationality_code) || value.nationality, issuing_country: country(result.issuing_country_code) || value.issuing_country });
    setWarnings(result.mrz_warnings ?? []);
  }});
  return <div className="space-y-4">
    <PassportScanAssistant file={scan} setFile={next => { onScan(next); onPhoto(null); }} mrz={value.mrz} setMrz={mrz => onChange({ ...value, mrz })} onPhoto={(file, source) => onPhoto({ file, source })} />
    {scan && <p className="text-sm text-cyan-800">{t("Full passport image will be saved when you validate the passport:", "ستحفظ صورة الجواز الكاملة عند اعتماد بيانات الجواز:")} {scan.name}</p>}
    {photo && <p className="text-sm text-emerald-700">{t("Cropped traveler photo ready:", "صورة المسافر المقصوصة جاهزة:")} {photo.file.name}</p>}
    <button type="button" disabled={!value.mrz || !countries.data || parse.isPending} className="rounded-lg bg-cyan-800 px-4 py-2 text-white disabled:opacity-50" onClick={() => parse.mutate()}>{t("Fill from passport", "تعبئة البيانات من الجواز")}</button>
    <MutationMessage error={parse.error || countries.error} />
    {warnings.map(warning => <p key={warning} className="text-sm text-amber-800">{warning}</p>)}
    <p className="text-sm text-slate-600">{t("Review all fields against the passport. The issue date is an editable estimate from expiry, not a scanned value.", "راجع جميع البيانات مع الجواز. تاريخ الإصدار اقتراح قابل للتعديل محسوب من الانتهاء وليس بياناً ممسوحاً.")}</p>
    <label className="block text-sm">{t("Passport duration for issue-date suggestion", "مدة الجواز لاقتراح تاريخ الإصدار")}<select className="mx-2 rounded-lg border p-2" value={duration} onChange={e => { const years = Number(e.target.value); setYears(years); onChange({ ...value, issue_date: suggestedIssueDate(value.expiry_date, years) }); }}><option value={10}>{t("10 years", "10 سنوات")}</option><option value={5}>{t("5 years", "5 سنوات")}</option></select></label>
    <div className="grid gap-3 sm:grid-cols-2">
      {([["passport_number", "Passport number", "رقم الجواز", "text"], ["first_name", "First name", "الاسم", "text"], ["middle_name", "Middle name", "الاسم الأوسط", "text"], ["last_name", "Last name", "اللقب", "text"], ["birth_date", "Birth date", "تاريخ الميلاد", "date"], ["issue_date", "Issue date", "تاريخ الإصدار", "date"], ["expiry_date", "Expiry date", "تاريخ الانتهاء", "date"], ["birth_place", "Birth place", "مكان الميلاد", "text"], ["issue_place", "Issue place", "مكان الإصدار", "text"]] as const).map(([key, en, ar, type]) => <label key={key} className="text-sm">{t(en, ar)}<input required={requireFields && !['middle_name', 'birth_place', 'issue_place'].includes(key)} type={type} dir={key === 'passport_number' ? 'ltr' : undefined} className="mt-1 w-full rounded-lg border px-3 py-2" value={value[key]} onChange={e => update({ ...value, [key]: e.target.value })} /></label>)}
      {(['nationality', 'issuing_country'] as const).map(key => <label key={key} className="text-sm">{key === 'nationality' ? t('Nationality', 'الجنسية') : t('Issuing country', 'بلد الإصدار')}<select required={requireFields} className="mt-1 w-full rounded-lg border px-3 py-2" value={value[key]} onChange={e => update({ ...value, [key]: e.target.value })}><option value="">{t('Select', 'اختر')}</option>{countries.data?.map(country => <option key={country.id} value={country.id}>{country.name}</option>)}</select></label>)}
      <label className="text-sm">{t('Gender', 'الجنس')}<select className="mt-1 w-full rounded-lg border px-3 py-2" value={value.gender} onChange={e => onChange({ ...value, gender: e.target.value })}><option value="X">{t('Unspecified', 'غير محدد')}</option><option value="M">{t('Male', 'ذكر')}</option><option value="F">{t('Female', 'أنثى')}</option></select></label>
    </div>
  </div>;
}
