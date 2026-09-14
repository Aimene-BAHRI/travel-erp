"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Printer } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";

import { AgencyDocumentHeader } from "@/components/documents/agency-document-header";
import type { AccommodationPlan, TripRecord } from "@/features/trips/types";
import { apiRequest } from "@/lib/api/client";

export default function AccommodationReportPage() {
  const uiText = useUiText();
  const { id, stopId } = useParams<{ id: string; stopId: string }>();
  const trip = useQuery({
    queryKey: ["trip", id],
    queryFn: () => apiRequest<TripRecord>(`/trips/${id}/`),
  });
  const plan = useQuery({
    queryKey: ["trip-accommodation-plan", id],
    queryFn: () =>
      apiRequest<AccommodationPlan>(`/trips/${id}/accommodation-plan/`),
  });
  const stop = plan.data?.stops.find((item) => item.id === stopId);

  useEffect(() => {
    if (trip.data && stop)
      document.title = `${trip.data.code}-${stop.city_name}-accommodation`;
  }, [stop, trip.data]);

  if (trip.isPending || plan.isPending)
    return <p className="p-10">{uiText("Loading accommodation report…")}</p>;
  if (!trip.data || !plan.data || !stop)
    return <p className="p-10 text-red-700">{uiText("Accommodation stay not found.")}</p>;

  const unassigned = plan.data.travelers.filter(
    (traveler) => !traveler.assignments.some((item) => item.stop === stop.id),
  );

  return (
    <main className="mx-auto min-h-[297mm] max-w-[210mm] bg-white p-8 text-slate-950 print:min-h-0 print:max-w-none print:p-0">
      <div className="no-print mb-6 flex items-center justify-between">
        <Link
          href={`/trips/${id}`}
          className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm"
        >
          <ArrowLeft className="size-4" /> {uiText("Back to trip")}
        </Link>
        <button
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white"
        >
          <Printer className="size-4" /> {uiText("Print / Download PDF")}
        </button>
      </div>

      <AgencyDocumentHeader
        agencyName={trip.data.agency_name}
        agencyLogo={trip.data.agency_logo}
        title={`${uiText("Accommodation list")} · ${stop.city_name}`}
        subtitle={`${trip.data.code} · ${trip.data.name} · ${stop.arrival_date} → ${stop.departure_date}`}
      />

      <section className="mt-5 grid grid-cols-3 gap-3 text-sm">
        <Summary
          label={uiText("Travelers")}
          value={String(plan.data.summary.traveler_count)}
        />
        <Summary label={uiText("Assigned")} value={String(stop.assigned_count)} />
        <Summary label={uiText("Unassigned")} value={String(stop.unassigned_count)} />
      </section>

      {stop.hotels.map((hotel) => (
        <section key={hotel.id} className="mt-7 break-inside-avoid">
          <div className="flex items-end justify-between border-b-2 border-slate-800 pb-2">
            <h2 className="text-lg font-bold">{hotel.hotel_name}</h2>
            <span className="text-xs text-slate-500">
              {hotel.is_primary ? uiText("Primary hotel") : uiText("Additional hotel")}
            </span>
          </div>
          {hotel.rooms.length ? (
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              {hotel.rooms.map((room) => (
                <article
                  key={room.id}
                  className="break-inside-avoid rounded-lg border border-slate-300 p-4"
                >
                  <header className="flex items-start justify-between border-b border-slate-200 pb-3">
                    <div>
                      <h3 className="font-bold">
                        {room.label}
                        {room.actual_room_number
                          ? ` · ${room.actual_room_number}`
                          : ""}
                      </h3>
                      <p className="text-xs text-slate-500">
                        {room.room_type_name} · {room.capacity} {uiText("beds")}
                      </p>
                    </div>
                    <span className="text-xs text-slate-500">
                      {uiText(room.occupancy_policy)}
                    </span>
                  </header>
                  <div className="mt-3 space-y-2">
                    {Array.from({ length: room.capacity }, (_, index) => {
                      const bed = index + 1;
                      const occupant = room.assignments.find(
                        (item) => item.bed_number === bed,
                      );
                      return (
                        <div
                          key={`${room.id}-${bed}`}
                          className="flex items-center gap-3 rounded-md bg-slate-50 p-2"
                        >
                          {occupant ? (
                            <TravelerAvatar
                              name={occupant.traveler_name}
                              photoUrl={occupant.traveler_photo_url}
                            />
                          ) : (
                            <span className="grid size-10 shrink-0 place-items-center rounded-full border border-dashed border-slate-300 text-xs text-slate-400">
                              {bed}
                            </span>
                          )}
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold">
                              {occupant?.traveler_name ?? uiText("Vacant bed")}
                            </p>
                            <p className="text-xs text-slate-500">
                              {uiText("Bed")} {bed} · {uiText(occupant?.gender ?? "—")}
                              {occupant?.booking_code
                                ? ` · ${occupant.booking_code}`
                                : ""}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="mt-3 border p-4 text-sm text-slate-500">
              {uiText("No rooms created for this hotel.")}
            </p>
          )}
        </section>
      ))}

      {!stop.hotels.length && (
        <p className="mt-7 border p-5 text-sm">
          {uiText("No hotel is assigned to this stay.")}
        </p>
      )}
      {unassigned.length > 0 && (
        <section className="mt-7 break-inside-avoid border border-amber-400 p-4">
          <h2 className="font-bold">
            {uiText("Unassigned travelers (")}{unassigned.length})
          </h2>
          <p className="mt-2 text-sm">
            {unassigned
              .map((traveler) => `${traveler.name} (${traveler.booking_code})`)
              .join(" · ")}
          </p>
        </section>
      )}
      <footer className="mt-12 flex justify-between border-t pt-5 text-sm">
        <span>{uiText("Prepared by: ____________________")}</span>
        <span>{uiText("Hotel confirmation: ____________________")}</span>
      </footer>
    </main>
  );
}

function Summary({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="border p-3 text-center">
      <b className="block text-xl">{value}</b>
      <span className="text-xs uppercase text-slate-500">{label}</span>
    </div>
  );
}

function TravelerAvatar({
  name,
  photoUrl,
}: Readonly<{ name: string; photoUrl: string | null }>) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
  return photoUrl ? (
    <img
      src={photoUrl}
      alt={`${name} profile`}
      className="size-10 shrink-0 rounded-full object-cover ring-1 ring-slate-300"
    />
  ) : (
    <span className="grid size-10 shrink-0 place-items-center rounded-full bg-cyan-100 text-xs font-semibold text-cyan-800">
      {initials || "?"}
    </span>
  );
}
