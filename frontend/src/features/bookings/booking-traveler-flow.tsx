"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import { PassportScanAssistant } from "@/features/travelers/passport-scan-assistant";
import type { HotelPriceRecord } from "@/features/pricing/types";
import type { AccommodationPlan } from "@/features/trips/types";
import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";
import type { BookingRecord, BookingTravelerRecord } from "./types";

type Country = { id: string; name: string; code: string };
const blank = { first_name: "", last_name: "", birth_date: "", gender: "X", passport_number: "", issue_date: "", expiry_date: "", nationality: "", issuing_country: "", mrz: "" };
const input = "mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm";

export function BookingTravelerFlow({ booking, onChange }: { booking: BookingRecord; onChange: (booking: BookingRecord) => void }) {
  const { locale } = useLocale();
  const t = (en: string, ar: string) => locale === "ar" ? ar : en;
  const cache = useQueryClient();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [link, setLink] = useState<BookingTravelerRecord | null>(null);
  const [draft, setDraft] = useState(blank);
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState("INCLUDED");
  const [amount, setAmount] = useState("");
  const [useTripPrice, setUseTripPrice] = useState(true);
  const [sourcePrice, setSourcePrice] = useState("");
  const [bed, setBed] = useState("REQUIRED");
  const [service, setService] = useState("PACK");
  const [includedStops, setIncludedStops] = useState<string[]>([]);
  const prices = useQuery({queryKey: ["package-hotel-prices", booking.trip], queryFn: () => apiRequest<Paginated<HotelPriceRecord>>(`/pricing/hotel-prices/?trip=${booking.trip}&scope=TRIP_PACKAGE`), enabled: open});
  const preview = useQuery({queryKey: ["traveler-preview", booking.trip, draft.birth_date, bed, service, includedStops, sourcePrice, useTripPrice], enabled: open && Boolean(draft.birth_date), queryFn: () => apiRequest<{category:string; bed_requirement:string; required_stops:string[]; price?: {amount:string; base_amount:string; discount_amount:string; currency_id:string}}>(`/trips/${booking.trip}/traveler-preview/`, {method:"POST", body:JSON.stringify({birth_date:draft.birth_date, bed_requirement:bed, service_type:service, included_stops:includedStops, use_trip_price:useTripPrice && !link?.charges.length, source_price:sourcePrice || null})})});
  const [rooms, setRooms] = useState<Record<string, string>>({});
  const [warnings, setWarnings] = useState<string[]>([]);
  const countries = useQuery({ queryKey: ["countries", "traveler-flow-all"], queryFn: async () => {
    const first = await apiRequest<Paginated<Country>>("/reference/countries/?ordering=name");
    const results = [...first.results];
    let next = first.next;
    while (next) {
      const page = await apiRequest<Paginated<Country>>(`/reference/countries/${new URL(next, "http://localhost").search}`);
      results.push(...page.results); next = page.next;
    }
    return { ...first, next: null, results };
  }, enabled: open });
  const plan = useQuery({ queryKey: ["trip-accommodation-plan", booking.trip], queryFn: () => apiRequest<AccommodationPlan>(`/trips/${booking.trip}/accommodation-plan/`), enabled: open });
  useEffect(() => {
    if (!open || !link || !plan.data) return;
    const assignments = plan.data.travelers.find((item) => item.id === link.id)?.assignments ?? [];
    setRooms((current) => ({ ...Object.fromEntries(assignments.map((item) => [item.stop, item.room])), ...current }));
  }, [open, link, plan.data]);
  const parse = useMutation({
    mutationFn: () => apiRequest<Partial<typeof blank> & { nationality_code?: string; issuing_country_code?: string; mrz_warnings?: string[] }>(`/bookings/${booking.id}/parse-passport-mrz/`, { method: "POST", body: JSON.stringify({ mrz: draft.mrz }) }),
    onSuccess: (value) => {
      const country = (code?: string) => countries.data?.results.find((item) => item.code === code || (code === "DZA" && item.code === "DZ"))?.id;
      setDraft({ ...draft, ...value, nationality: country(value.nationality_code) || draft.nationality, issuing_country: country(value.issuing_country_code) || draft.issuing_country });
      setWarnings(value.mrz_warnings ?? []);
    },
  });
  const save = useMutation({
    mutationFn: (namesOnly: boolean) => apiRequest<BookingRecord>(`/bookings/${booking.id}/traveler-flow/`, {
      method: "POST", body: JSON.stringify({ link_id: link?.id, names_only: namesOnly, first_name: draft.first_name, last_name: draft.last_name, birth_date: draft.birth_date || null, gender: draft.gender, bed_requirement: bed, service_type: service, included_stops: includedStops, use_trip_price: useTripPrice, source_price: sourcePrice || null,
        ...(!namesOnly ? { passport: draft, price_mode: mode, ...(mode !== "EXISTING" && !useTripPrice ? { amount } : {}), rooms: Object.entries(rooms).filter(([stop, room]) => room && preview.data?.required_stops.includes(stop)).map(([, room]) => room) } : {}),
      }),
    }),
    onSuccess: (record) => { onChange(record); setOpen(false); cache.invalidateQueries({ queryKey: ["trip-accommodation-plan", booking.trip] }); cache.invalidateQueries({ queryKey: ["notifications"] }); cache.invalidateQueries({ queryKey: ["financial-summary", booking.id] }); },
  });
  const start = (traveler: BookingTravelerRecord | null) => {
    setLink(traveler); setStep(0); setFile(null); setWarnings([]); save.reset(); parse.reset();
    const p = traveler?.passport_details;
    setDraft(p ? { ...blank, ...p } : { ...blank, first_name: traveler?.first_name ?? "", last_name: traveler?.last_name ?? "", birth_date: traveler?.birth_date ?? "", gender: traveler?.gender ?? "X" });
    setUseTripPrice(!traveler?.charges.length); setSourcePrice(""); setBed(traveler?.bed_requirement ?? "REQUIRED"); setService(traveler?.service_type ?? "PACK"); setIncludedStops(traveler?.included_stops ?? []);
    setMode(traveler?.charges.length ? "EXISTING" : "INCLUDED"); setAmount("");
    const assigned = plan.data?.travelers.find((item) => item.id === traveler?.id)?.assignments ?? [];
    setRooms(Object.fromEntries(assigned.map((item) => [item.stop, item.room])));
    setOpen(true);
  };
  const field = (key: keyof typeof blank, label: string, type = "text") => <label className="text-sm">{label}<input className={input} type={type} value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} /></label>;
  const identityReady = Boolean(draft.first_name.trim() && draft.last_name.trim() && draft.birth_date && draft.passport_number.trim() && draft.issue_date && draft.expiry_date && draft.nationality && draft.issuing_country);
  const stops = plan.data?.stops.filter((stop) => preview.data?.required_stops.includes(stop.id)) ?? [];
  const roomsReady = Boolean(plan.data && preview.data) && stops.every((stop) => Boolean(rooms[stop.id]));
  const titles = [t("Identity & passport", "الهوية والجواز"), t("Individual price", "السعر الفردي"), t("Rooms", "الغرف"), t("Review", "المراجعة")];
  if (!["DRAFT", "CONFIRMED"].includes(booking.status)) return null;
  return <div className="my-4 space-y-3">
    {booking.readiness.remaining_travelers > 0 && <button onClick={() => start(null)} className="rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white">{t("Add traveler", "إضافة مسافر")}</button>}
    <div className="divide-y rounded-lg border">
      {booking.travelers.map((traveler) => {
        const issues = booking.readiness.completion.find((item) => item.id === traveler.id)?.issues ?? [];
        return <div key={traveler.id} className="flex flex-wrap items-center justify-between gap-3 p-3"><div><p className="text-sm font-medium">{traveler.traveler_name}</p><p className={`text-xs ${issues.length ? "text-amber-800" : "text-emerald-700"}`}>{issues.length ? t(`Missing details: ${issues.join(" · ")}`, `بيانات ناقصة (${issues.length}) — أكمل البيانات قبل تخصيص الغرف والدفع`) : t("Identity, passport and price complete", "الهوية والجواز والسعر مكتملة")}</p></div><button onClick={() => start(traveler)} className="rounded-lg border px-3 py-2 text-sm">{t("Complete details / rooms", "إكمال البيانات والغرف")}</button></div>;
      })}
    </div>
    <FormDialog open={open} onClose={() => setOpen(false)} title={link ? t("Complete traveler", "إكمال بيانات المسافر") : t("Add traveler", "إضافة مسافر")}>
      <div className="space-y-4">
        <ol className="flex flex-wrap gap-2">{titles.map((title, index) => <li key={title} className={`rounded-full px-3 py-1 text-xs ${step === index ? "bg-cyan-800 text-white" : "bg-slate-100"}`}>{index + 1}. {title}</li>)}</ol>
        {step === 0 && <>
          <PassportScanAssistant photoEnabled={false} file={file} setFile={setFile} mrz={draft.mrz} setMrz={(mrz) => setDraft({ ...draft, mrz })} onPhoto={() => {}} />
          <button disabled={!draft.mrz || parse.isPending} onClick={() => parse.mutate()} className="rounded-lg border px-3 py-2 text-sm">{t("Fill from scanned MRZ", "تعبئة من بيانات الجواز الممسوحة")}</button>
          <MutationMessage error={parse.error || countries.error} />
          {warnings.length > 0 && <p className="text-sm text-amber-800">{warnings.join(" ? ")}</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            {field("first_name", t("First name", "الاسم"))}{field("last_name", t("Last name", "اللقب"))}{field("birth_date", t("Birth date", "تاريخ الميلاد"), "date")}
            <label className="text-sm">{t("Gender", "الجنس")}<select className={input} value={draft.gender} onChange={(e) => setDraft({ ...draft, gender: e.target.value })}><option value="X">{t("Unspecified", "غير محدد")}</option><option value="M">{t("Male", "ذكر")}</option><option value="F">{t("Female", "أنثى")}</option></select></label>
            {field("passport_number", t("Passport number", "رقم الجواز"))}{field("issue_date", t("Issue date", "تاريخ الإصدار"), "date")}{field("expiry_date", t("Expiry date", "تاريخ الانتهاء"), "date")}
            {(["nationality", "issuing_country"] as const).map((key) => <label key={key} className="text-sm">{key === "nationality" ? t("Nationality", "الجنسية") : t("Issuing country", "بلد الإصدار")}<select className={input} value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}><option value="">{t("Select", "اختر")}</option>{countries.data?.results.map((country) => <option key={country.id} value={country.id}>{country.name}</option>)}</select></label>)}
          </div>
          <p className="text-xs text-slate-500">{t("Scan fills the fields; review them before saving. A valid passport is required for rooms and payments.", "راجع البيانات المستخرجة قبل الحفظ. يلزم جواز صالح لتخصيص الغرف وتسجيل الدفعات.")}</p>
          {!link && <button disabled={!draft.first_name.trim() || save.isPending} onClick={() => save.mutate(true)} className="rounded-lg border border-amber-300 px-3 py-2 text-sm text-amber-900">{t("Save names only ? complete details later", "حفظ الأسماء فقط وإكمال البيانات لاحقاً")}</button>}
        </>}
        {step === 1 && <div className="space-y-3">
          {!link?.charges.length && <>
            <label className="block text-sm">{t("Price source", "مصدر السعر")}<select className={input} value={useTripPrice ? "TRIP" : "MANUAL"} onChange={e=>setUseTripPrice(e.target.value === "TRIP")}><option value="TRIP">Hotel-specific trip pricing</option><option value="MANUAL">Existing agreement / manual price</option></select></label>
            <label className="block text-sm">{t("Bed requirement", "السرير")}<select className={input} value={bed} onChange={e=>setBed(e.target.value)}><option value="REQUIRED">With bed</option><option value="NOT_REQUIRED">Child without bed / infant</option></select></label>
            <label className="block text-sm">{t("Service", "الخدمة")}<select className={input} value={service} onChange={e=>setService(e.target.value)}><option value="PACK">Full package</option><option value="VISA_ONLY">Visa only</option><option value="TICKET_ONLY">Ticket only</option><option value="CUSTOM">Selected hotel stays</option></select></label>
            {service === "CUSTOM" && plan.data?.stops.map(stop=><label key={stop.id} className="flex gap-2 text-sm"><input type="checkbox" checked={includedStops.includes(stop.id)} onChange={e=>setIncludedStops(e.target.checked ? [...includedStops,stop.id] : includedStops.filter(id=>id!==stop.id))}/>{stop.city_name}</label>)}
            {useTripPrice && <label className="block text-sm">Hotel / room adult package (not required for infant or child without bed)<select className={input} value={sourcePrice} onChange={e=>setSourcePrice(e.target.value)}><option value="">Select / fixed trip price</option>{prices.data?.results.map(price=><option key={price.id} value={price.id}>{price.hotel_name} / {price.room_type_name}: {price.amount} {price.currency_code}</option>)}</select></label>}
          </>}
          {preview.data && <p className="rounded-lg bg-cyan-50 p-3 text-sm">{preview.data.category} / {preview.data.bed_requirement}{preview.data.price && `: ${preview.data.price.base_amount} - ${preview.data.price.discount_amount} = ${preview.data.price.amount} ${preview.data.price.currency_id}`}</p>}
          <MutationMessage error={preview.error || prices.error} />
          <p className="text-sm">{t("Current booking total", "إجمالي الحجز الحالي")}: {booking.total_amount} {booking.currency_code}</p>
          <label className="block text-sm">{t("Price treatment", "طريقة احتساب السعر")}<select className={input} value={mode} onChange={(e) => setMode(e.target.value)} disabled={Boolean(link?.charges.length)}>{link?.charges.length ? <option value="EXISTING">{t("Keep existing individual price", "الاحتفاظ بالسعر الفردي الحالي")}</option> : <><option value="INCLUDED">{t("Included in confirmed total", "مشمول في الإجمالي المؤكد")}</option><option value="ADDITIONAL">{t("Additional charge ? increases total", "مبلغ إضافي يزيد الإجمالي")}</option></>}</select></label>
          {mode !== "EXISTING" && !useTripPrice && <label className="block text-sm">{t("Individual amount", "المبلغ الفردي")} ({booking.currency_code})<input type="number" min="0" step="0.0001" className={input} value={amount} onChange={(e) => setAmount(e.target.value)} /></label>}
          <p className="text-sm text-slate-600">{mode === "EXISTING" ? `${link?.final_amount} ${booking.currency_code}` : mode === "INCLUDED" ? t("Allocates an unassigned part of the existing total; cannot exceed that total. Draft prices build the draft total.", "يخصص جزءاً من الإجمالي الحالي دون تجاوزه. أسعار المسودة تُضاف إلى إجماليها.") : t("Adds this amount to the booking total. The change is recorded in the audit history; no payment is taken.", "يُضاف المبلغ إلى إجمالي الحجز ويُسجل التغيير في سجل التدقيق دون تسجيل دفعة.")}</p>
        </div>}
        {step === 2 && <div className="space-y-3">
          {plan.isPending && <p>{t("Loading rooms?", "جارٍ تحميل الغرف…")}</p>}<MutationMessage error={plan.error} />
          {stops.map((stop) => <label key={stop.id} className="block text-sm">{stop.city_name} ? {stop.arrival_date} ? {stop.departure_date}<select className={input} value={rooms[stop.id] ?? ""} onChange={(e) => setRooms({ ...rooms, [stop.id]: e.target.value })}><option value="">{t("Select available room", "اختر غرفة متاحة")}</option>{stop.hotels.flatMap((hotel) => hotel.rooms.map((room) => {
            const free = room.capacity - room.assignments.filter((a) => a.booking_traveler !== link?.id).length;
            return <option key={room.id} value={room.id} disabled={free <= 0}>{hotel.hotel_name} ? {room.label} ? {room.occupancy_policy} ? {free} {t("places available", "أماكن متاحة")}</option>;
          }))}</select></label>)}
          {!plan.isPending && plan.data && !stops.length && <p>{t("No hotel stays require allocation.", "لا توجد إقامات فندقية تتطلب توزيعاً.")}</p>}
          <p className="text-xs text-slate-500">{t("Room availability and traveler details are rechecked when you validate. If a room is taken, nothing is partially saved.", "يُعاد التحقق من توفر الغرف والبيانات عند التأكيد. إذا لم تتوفر الغرفة فلن تُحفظ العملية جزئياً.")}</p>
        </div>}
        {step === 3 && <div className="space-y-2 rounded-lg bg-slate-50 p-4 text-sm"><p className="font-semibold">{draft.first_name} {draft.last_name}</p><p>{t("Passport", "الجواز")}: {draft.passport_number} ? {t("Expires", "ينتهي")}: {draft.expiry_date}</p><p>{t("Individual price", "السعر الفردي")}: {mode === "EXISTING" ? link?.final_amount : useTripPrice ? preview.data?.price?.amount : amount} {booking.currency_code} ? {mode === "ADDITIONAL" ? t("Additional", "إضافي") : t("Included / existing", "مشمول / حالي")}</p><p>{t("Hotel stays selected", "الإقامات المختارة")}: {Object.values(rooms).filter(Boolean).length} / {stops.length}</p><p>{t("Validate saves the traveler, passport, price and rooms together. No payment is recorded.", "التأكيد يحفظ المسافر والجواز والسعر والغرف معاً دون تسجيل دفعة.")}</p></div>}
        <MutationMessage error={save.error} />
        <div className="flex justify-between gap-2">
          <button disabled={save.isPending} onClick={() => step ? setStep(step - 1) : setOpen(false)} className="rounded-lg border px-4 py-2 text-sm">{step ? t("Back", "رجوع") : t("Cancel", "إلغاء")}</button>
          {step < 3 ? <button disabled={(step === 0 && !identityReady) || (step === 1 && mode !== "EXISTING" && (useTripPrice ? !preview.data?.price : amount === "" || Number(amount) < 0)) || (step === 2 && !roomsReady)} onClick={() => setStep(step + 1)} className="rounded-lg bg-cyan-800 px-4 py-2 text-sm text-white disabled:opacity-50">{t("Continue", "متابعة")}</button> : <button disabled={save.isPending} onClick={() => save.mutate(false)} className="rounded-lg bg-cyan-800 px-4 py-2 text-sm text-white disabled:opacity-50">{t("Validate and save traveler", "اعتماد وحفظ المسافر")}</button>}
        </div>
      </div>
    </FormDialog>
  </div>;
}
