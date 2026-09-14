"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, LoaderCircle, MapPin, Pencil, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";
import { statusAr } from "@/lib/i18n/ar";
import { useLocale } from "@/lib/i18n/context";

import type { TripRecord } from "./types";

type Branch = { id: string; name: string };
type TripDraft = {
  code: string;
  name: string;
  branch: string;
  departure_date: string;
  return_date: string;
  booking_open_date: string;
  booking_close_date: string;
  max_travelers: string;
  description: string;
  notes: string;
};

const blank: TripDraft = {
  code: "",
  name: "",
  branch: "",
  departure_date: "",
  return_date: "",
  booking_open_date: "",
  booking_close_date: "",
  max_travelers: "",
  description: "",
  notes: "",
};

const statusStyle: Record<TripRecord["status"], string> = {
  DRAFT: "bg-slate-100 text-slate-600",
  OPEN: "bg-emerald-50 text-emerald-700",
  CLOSED: "bg-amber-50 text-amber-700",
  DEPARTED: "bg-blue-50 text-blue-700",
  COMPLETED: "bg-cyan-50 text-cyan-800",
  CANCELLED: "bg-red-50 text-red-700",
};

const text = {
  ar: {
    title: "المغادرات",
    subtitle: "أنشئ وأدر كل رحلة بتاريخها.",
    search: "ابحث في الرحلات أو المدن",
    newTrip: "رحلة جديدة",
    edit: "تعديل",
    stops: "محطات",
    hotels: "فنادق",
    flights: "رحلات جوية",
    capacityNotSet: "السعة غير محددة",
    placesLeft: "أماكن متبقية",
    noTrips: "لا توجد رحلات",
    noTripsHelp: "أنشئ أول رحلة بتاريخ محدد للبدء.",
    createTrip: "إنشاء رحلة",
    editTrip: "تعديل الرحلة",
    dialogNew: "رحلة جديدة",
    dialogDescription: "حدد تاريخ الرحلة وفترة فتح الحجوزات. تفاصيل البرنامج تضاف من صفحة الرحلة.",
    branchRequired: "يجب إنشاء فرع مسؤول قبل إنشاء رحلة.",
    createBranch: "إنشاء فرع من الإعدادات",
    code: "الكود",
    branch: "الفرع المسؤول",
    selectBranch: "اختر الفرع",
    tripName: "اسم الرحلة",
    departure: "تاريخ الذهاب",
    return: "تاريخ العودة",
    bookingOpens: "فتح الحجوزات",
    bookingCloses: "غلق الحجوزات",
    maxTravelers: "الحد الأقصى للمسافرين",
    optional: "اختياري",
    description: "الوصف",
    notes: "ملاحظات داخلية",
    cancel: "إلغاء",
    saving: "جاري الحفظ...",
    save: "حفظ التغييرات",
  },
  en: {
    title: "Departures",
    subtitle: "Create and manage each dated departure.",
    search: "Search trips or cities",
    newTrip: "New trip",
    edit: "Edit",
    stops: "stops",
    hotels: "hotels",
    flights: "flights",
    capacityNotSet: "Capacity not set",
    placesLeft: "places left",
    noTrips: "No trips found",
    noTripsHelp: "Create the first dated departure to begin.",
    createTrip: "Create trip",
    editTrip: "Edit trip",
    dialogNew: "New trip",
    dialogDescription: "Define the departure and booking window. Itinerary details are added from the trip profile.",
    branchRequired: "A managing branch is required before a trip can be created.",
    createBranch: "Create a branch in Settings",
    code: "Code",
    branch: "Managing branch",
    selectBranch: "Select branch",
    tripName: "Trip name",
    departure: "Departure date",
    return: "Return date",
    bookingOpens: "Booking opens",
    bookingCloses: "Booking closes",
    maxTravelers: "Maximum travelers",
    optional: "Optional",
    description: "Description",
    notes: "Internal notes",
    cancel: "Cancel",
    saving: "Saving...",
    save: "Save changes",
  },
};

export function TripList() {
  const { locale } = useLocale();
  const copy = text[locale];
  const cache = useQueryClient();
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<TripRecord | null>(null);
  const [draft, setDraft] = useState<TripDraft>(blank);
  const trips = useQuery({
    queryKey: ["trips", search],
    queryFn: () => apiRequest<Paginated<TripRecord>>(`/trips/?search=${encodeURIComponent(search)}`),
  });
  const branches = useQuery({
    queryKey: ["branches"],
    queryFn: () => apiRequest<Paginated<Branch>>("/organizations/branches/"),
  });
  const save = useMutation({
    mutationFn: () =>
      apiRequest<TripRecord>(editing ? `/trips/${editing.id}/` : "/trips/", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify({
          ...draft,
          booking_open_date: draft.booking_open_date || null,
          booking_close_date: draft.booking_close_date || null,
          max_travelers: draft.max_travelers ? Number(draft.max_travelers) : null,
        }),
      }),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["trips"] });
      cache.invalidateQueries({ queryKey: ["dashboard"] });
      setOpen(false);
    },
  });
  const change = (key: keyof TripDraft, value: string) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const create = () => {
    setEditing(null);
    setDraft({ ...blank, branch: branches.data?.results[0]?.id ?? "" });
    save.reset();
    setOpen(true);
  };
  const edit = (trip: TripRecord) => {
    setEditing(trip);
    setDraft({
      code: trip.code,
      name: trip.name,
      branch: trip.branch,
      departure_date: trip.departure_date,
      return_date: trip.return_date,
      booking_open_date: trip.booking_open_date ?? "",
      booking_close_date: trip.booking_close_date ?? "",
      max_travelers: trip.max_travelers?.toString() ?? "",
      description: trip.description,
      notes: trip.notes,
    });
    save.reset();
    setOpen(true);
  };

  return (
    <>
      <section className="rounded-xl border border-slate-200 bg-white">
        <div className="flex flex-col gap-4 border-b border-slate-200 p-5 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="font-semibold">{copy.title}</h2>
            <p className="text-sm text-slate-500">{copy.subtitle}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <label className="flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2">
              <Search className="size-4 text-slate-400" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={copy.search}
                className="w-56 border-0 bg-transparent text-sm outline-none"
              />
            </label>
            <button
              type="button"
              onClick={create}
              className="inline-flex items-center gap-2 rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-900"
            >
              <Plus className="size-4" />
              {copy.newTrip}
            </button>
          </div>
        </div>
        {trips.isPending ? (
          <div className="grid min-h-60 place-items-center">
            <LoaderCircle className="size-7 animate-spin text-cyan-800" />
          </div>
        ) : trips.data?.results.length ? (
          <div className="divide-y divide-slate-100">
            {trips.data.results.map((trip) => (
              <div
                key={trip.id}
                className="grid gap-4 p-5 hover:bg-slate-50 md:grid-cols-[1fr_auto_auto_auto] md:items-center"
              >
                <Link href={`/trips/${trip.id}`}>
                  <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-cyan-900">{trip.name}</h3>
                    <span className={`rounded-full px-2 py-1 text-xs font-medium ${statusStyle[trip.status]}`}>
                      {locale === "ar" ? statusAr(trip.status) : trip.status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                    {trip.code} · {trip.branch_name}
                  </p>
                </Link>
                <div className="flex items-center gap-2 text-sm text-slate-600">
                  <CalendarDays className="size-4" />
                  {trip.departure_date} → {trip.return_date}
                </div>
                <div className="flex items-center gap-2 text-sm text-slate-600">
                  <MapPin className="size-4" />
                  {trip.stop_count} {copy.stops} · {trip.hotel_count} {copy.hotels} ·{" "}
                  {trip.flight_count} {copy.flights} ·{" "}
                  {trip.remaining_places === null
                    ? copy.capacityNotSet
                    : `${trip.remaining_places} ${copy.placesLeft}`}
                </div>
                <button
                  type="button"
                  onClick={() => edit(trip)}
                  className="inline-flex items-center gap-1 text-sm font-medium text-cyan-800"
                >
                  <Pencil className="size-4" />
                  {copy.edit}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid min-h-60 place-items-center text-center">
            <div>
              <CalendarDays className="mx-auto size-9 text-slate-300" />
              <p className="mt-3 font-medium">{copy.noTrips}</p>
              <p className="text-sm text-slate-500">{copy.noTripsHelp}</p>
              <button
                type="button"
                onClick={create}
                className="mt-4 inline-flex items-center gap-2 rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white"
              >
                <Plus className="size-4" />
                {copy.createTrip}
              </button>
            </div>
          </div>
        )}
      </section>
      <FormDialog
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? copy.editTrip : copy.dialogNew}
        description={copy.dialogDescription}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
          className="space-y-5"
        >
          {!branches.isPending && !branches.data?.results.length && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              {copy.branchRequired}{" "}
              <Link href="/settings" className="font-semibold underline">
                {copy.createBranch}
              </Link>
              .
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={copy.code}>
              <input required value={draft.code} onChange={(event) => change("code", event.target.value)} placeholder="IST-2026-09" className="input" />
            </Field>
            <Field label={copy.branch}>
              <select required value={draft.branch} onChange={(event) => change("branch", event.target.value)} className="input">
                <option value="">{copy.selectBranch}</option>
                {branches.data?.results.map((branch) => (
                  <option key={branch.id} value={branch.id}>{branch.name}</option>
                ))}
              </select>
            </Field>
            <Field label={copy.tripName} wide>
              <input required value={draft.name} onChange={(event) => change("name", event.target.value)} className="input" />
            </Field>
            <Field label={copy.departure}>
              <input required type="date" value={draft.departure_date} onChange={(event) => change("departure_date", event.target.value)} className="input" />
            </Field>
            <Field label={copy.return}>
              <input required type="date" min={draft.departure_date} value={draft.return_date} onChange={(event) => change("return_date", event.target.value)} className="input" />
            </Field>
            <Field label={copy.bookingOpens}>
              <input type="date" value={draft.booking_open_date} onChange={(event) => change("booking_open_date", event.target.value)} className="input" />
            </Field>
            <Field label={copy.bookingCloses}>
              <input type="date" max={draft.departure_date} value={draft.booking_close_date} onChange={(event) => change("booking_close_date", event.target.value)} className="input" />
            </Field>
            <Field label={copy.maxTravelers}>
              <input type="number" min="1" value={draft.max_travelers} onChange={(event) => change("max_travelers", event.target.value)} placeholder={copy.optional} className="input" />
            </Field>
            <Field label={copy.description} wide>
              <textarea rows={3} value={draft.description} onChange={(event) => change("description", event.target.value)} className="input" />
            </Field>
            <Field label={copy.notes} wide>
              <textarea rows={3} value={draft.notes} onChange={(event) => change("notes", event.target.value)} className="input" />
            </Field>
          </div>
          <MutationMessage error={save.error} />
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium">
              {copy.cancel}
            </button>
            <button disabled={save.isPending || branches.isPending || !branches.data?.results.length} className="rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
              {save.isPending ? copy.saving : editing ? copy.save : copy.createTrip}
            </button>
          </div>
        </form>
      </FormDialog>
    </>
  );
}

function Field({
  label,
  wide,
  children,
}: Readonly<{ label: string; wide?: boolean; children: React.ReactNode }>) {
  return (
    <label className={`text-sm font-medium text-slate-700 ${wide ? "sm:col-span-2" : ""}`}>
      {label}
      <div className="mt-1 [&_.input]:w-full [&_.input]:rounded-lg [&_.input]:border [&_.input]:border-slate-300 [&_.input]:bg-white [&_.input]:px-3 [&_.input]:py-2 [&_.input]:outline-none [&_.input]:focus:border-cyan-600">
        {children}
      </div>
    </label>
  );
}
