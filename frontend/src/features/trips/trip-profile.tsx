"use client";
import { flightDefaults, nextOrder } from "./form-defaults";
import { TripReadinessPanel } from "./trip-readiness-panel";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bus,
  CalendarDays,
  Download,
  FileText,
  Hotel,
  LoaderCircle,
  Pencil,
  Plane,
  Plus,
  Trash2,
  Upload,
} from "lucide-react";
import { useState } from "react";

import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import type {
  AirlineRecord,
  HotelRecord,
  SupplierRecord,
} from "@/features/catalog/types";
import type { Paginated } from "@/features/reference/types";
import type { DocumentRecord } from "@/features/travelers/types";
import { apiRequest } from "@/lib/api/client";
import { useOperationalText } from "@/lib/i18n/operational";
import { TripAccommodationAllocation } from "./trip-accommodation-allocation";
import { TripClosing } from "./trip-closing";
import { TripCommercialPricing } from "@/features/pricing/trip-commercial-pricing";
import { TripPricing } from "@/features/pricing/trip-pricing";
import { TripPartnerTicketReservations } from "./trip-partner-ticket-reservations";
import { TripBookings } from "./trip-bookings";
import type {
  TripFlightRecord,
  TripHotelRecord,
  TripRecord,
  TripStopRecord,
  TripTransportRecord,
} from "./types";

type Branch = { id: string; name: string };
type City = { id: string; name: string; country_code: string };
type HotelOption = HotelRecord & { city: string };
type DetailsDraft = Pick<
  TripRecord,
  | "code"
  | "name"
  | "branch"
  | "departure_date"
  | "return_date"
  | "description"
  | "notes"
> & {
  booking_open_date: string;
  booking_close_date: string;
  pricing_currency: string;
  child_with_bed_discount: string;
  child_without_bed_price: string;
  infant_price: string;
};
type DetailsDraftWithCapacity = DetailsDraft & { max_travelers: string };
type StopDraft = {
  city: string;
  arrival_date: string;
  departure_date: string;
  order: number;
  notes: string;
};
type HotelDraft = {
  stop: string;
  hotel: string;
  is_primary: boolean;
  notes: string;
};
type FlightDraft = {
  airline: string;
  direction: string;
  flight_number: string;
  origin_city: string;
  destination_city: string;
  origin_airport_code: string;
  destination_airport_code: string;
  departure_at: string;
  arrival_at: string;
  booking_class: string;
  order: number;
  notes: string;
};
type TransportDraft = {
  mode: TripTransportRecord["mode"];
  supplier: string;
  origin_city: string;
  destination_city: string;
  departure_at: string;
  arrival_at: string;
  reference: string;
  vehicle_details: string;
  vehicle_number: string;
  order: number;
  notes: string;
};

const transitions: Partial<
  Record<TripRecord["status"], TripRecord["status"][]>
> = {
  DRAFT: ["OPEN", "CANCELLED"],
  OPEN: ["CLOSED", "CANCELLED"],
  CLOSED: ["OPEN", "DEPARTED", "CANCELLED"],
  DEPARTED: ["COMPLETED"],
};
const emptyStop: StopDraft = {
  city: "",
  arrival_date: "",
  departure_date: "",
  order: 1,
  notes: "",
};
const emptyHotel: HotelDraft = {
  stop: "",
  hotel: "",
  is_primary: false,
  notes: "",
};
const emptyFlight: FlightDraft = {
  airline: "",
  direction: "OUTBOUND",
  flight_number: "",
  origin_city: "",
  destination_city: "",
  origin_airport_code: "",
  destination_airport_code: "",
  departure_at: "",
  arrival_at: "",
  booking_class: "",
  order: 1,
  notes: "",
};
const emptyTransport: TransportDraft = {
  mode: "BUS",
  supplier: "",
  origin_city: "",
  destination_city: "",
  departure_at: "",
  arrival_at: "",
  reference: "",
  vehicle_details: "",
  vehicle_number: "",
  order: 1,
  notes: "",
};
const localDateTime = (value: string) =>
  value ? new Date(value).toISOString().slice(0, 16) : "";
const localFlightDateTime = (value: string) =>
  value
    ? new Date(
        new Date(value).getTime() - new Date(value).getTimezoneOffset() * 60000,
      )
        .toISOString()
        .slice(0, 16)
    : "";

function FlightDateHint({
  start,
  end,
  departure,
  arrival,
}: {
  start: string;
  end: string;
  departure: string;
  arrival: string;
}) {
  const t = useOperationalText();
  const outside = [departure, arrival].some(
    (value) =>
      value && (value.slice(0, 10) < start || value.slice(0, 10) > end),
  );
  const reversed =
    departure.length >= 16 && arrival.length >= 16 && arrival <= departure;
  if (!outside && !reversed) return null;
  return (
    <p
      role="status"
      className="my-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900"
    >
      {reversed
        ? t("Arrival must be after departure.")
        : t(
            "Flight dates fall outside the trip dates. Review the flight or the trip dates.",
          )}{" "}
      ({start} → {end})
    </p>
  );
}

export type TripTab =
  | "itinerary"
  | "accommodation"
  | "transport"
  | "documents"
  | "bookings"
  | "commercial"
  | "closing";

export function TripProfile({
  tripId,
  activeTab,
}: Readonly<{ tripId: string; activeTab: TripTab }>) {
  const uiText = useUiText();
  const t = useOperationalText();
  const cache = useQueryClient();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [stopOpen, setStopOpen] = useState(false);
  const [editingStop, setEditingStop] = useState<TripStopRecord | null>(null);
  const [hotelOpen, setHotelOpen] = useState(false);
  const [editingHotel, setEditingHotel] = useState<TripHotelRecord | null>(
    null,
  );
  const [flightOpen, setFlightOpen] = useState(false);
  const [editingFlight, setEditingFlight] = useState<TripFlightRecord | null>(
    null,
  );
  const [documentOpen, setDocumentOpen] = useState(false);
  const [transportOpen, setTransportOpen] = useState(false);
  const [editingTransport, setEditingTransport] =
    useState<TripTransportRecord | null>(null);
  const [transportDraft, setTransportDraft] =
    useState<TransportDraft>(emptyTransport);
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [documentTitle, setDocumentTitle] = useState("");
  const [documentCategory, setDocumentCategory] = useState("CONTRACT");
  const [documentPurpose, setDocumentPurpose] = useState("");
  const [detailsDraft, setDetailsDraft] =
    useState<DetailsDraftWithCapacity | null>(null);
  const [stopDraft, setStopDraft] = useState<StopDraft>(emptyStop);
  const [hotelDraft, setHotelDraft] = useState<HotelDraft>(emptyHotel);
  const [flightDraft, setFlightDraft] = useState<FlightDraft>(emptyFlight);

  const trip = useQuery({
    queryKey: ["trip", tripId],
    queryFn: () => apiRequest<TripRecord>(`/trips/${tripId}/`),
  });
  const stops = useQuery({
    queryKey: ["trip-stops", tripId],
    queryFn: () =>
      apiRequest<Paginated<TripStopRecord>>(
        `/trips/stops/?trip=${tripId}&ordering=order`,
      ),
  });
  const hotels = useQuery({
    queryKey: ["trip-hotels", tripId],
    queryFn: () =>
      apiRequest<Paginated<TripHotelRecord>>(`/trips/hotels/?trip=${tripId}`),
  });
  const flights = useQuery({
    queryKey: ["trip-flights", tripId],
    queryFn: () =>
      apiRequest<Paginated<TripFlightRecord>>(
        `/trips/flights/?trip=${tripId}&ordering=order`,
      ),
  });
  const transports = useQuery({
    queryKey: ["trip-transports", tripId],
    queryFn: () =>
      apiRequest<Paginated<TripTransportRecord>>(
        `/trips/transports/?trip=${tripId}&ordering=order`,
      ),
  });
  const documents = useQuery({
    queryKey: ["trip-documents", tripId],
    queryFn: () =>
      apiRequest<Paginated<DocumentRecord>>(
        `/documents/?owner_type=TRIP&owner_id=${tripId}`,
      ),
  });
  const branches = useQuery({
    queryKey: ["branches"],
    queryFn: () => apiRequest<Paginated<Branch>>("/organizations/branches/"),
  });
  const currencies = useQuery({
    queryKey: ["agency-currencies"],
    queryFn: () =>
      apiRequest<
        Paginated<{
          currency: string;
          currency_name: string;
          is_enabled: boolean;
        }>
      >("/reference/agency-currencies/"),
  });
  const cities = useQuery({
    queryKey: ["cities"],
    queryFn: () =>
      apiRequest<Paginated<City>>("/reference/cities/?ordering=name"),
  });
  const hotelOptions = useQuery({
    queryKey: ["hotels", "options"],
    queryFn: () =>
      apiRequest<Paginated<HotelOption>>("/catalog/hotels/?ordering=name"),
  });
  const airlines = useQuery({
    queryKey: ["airlines"],
    queryFn: () =>
      apiRequest<Paginated<AirlineRecord>>("/catalog/airlines/?ordering=name"),
  });
  const suppliers = useQuery({
    queryKey: ["suppliers", "options"],
    queryFn: () =>
      apiRequest<Paginated<SupplierRecord>>(
        "/catalog/suppliers/?ordering=name",
      ),
  });
  const refresh = (key: string) => {
    cache.invalidateQueries({ queryKey: [key, tripId] });
    cache.invalidateQueries({ queryKey: ["trip", tripId] });
    cache.invalidateQueries({ queryKey: ["trips"] });
  };

  const saveDetails = useMutation({
    mutationFn: () =>
      apiRequest<TripRecord>(`/trips/${tripId}/`, {
        method: "PATCH",
        body: JSON.stringify({
          ...detailsDraft,
          booking_open_date: detailsDraft?.booking_open_date || null,
          booking_close_date: detailsDraft?.booking_close_date || null,
          pricing_currency: detailsDraft?.pricing_currency || null,
          child_with_bed_discount:
            detailsDraft?.child_with_bed_discount || null,
          child_without_bed_price:
            detailsDraft?.child_without_bed_price || null,
          infant_price: detailsDraft?.infant_price || null,
          max_travelers: detailsDraft?.max_travelers
            ? Number(detailsDraft.max_travelers)
            : null,
        }),
      }),
    onSuccess: (value) => {
      cache.setQueryData(["trip", tripId], value);
      cache.invalidateQueries({ queryKey: ["trips"] });
      setDetailsOpen(false);
    },
  });
  const saveStop = useMutation({
    mutationFn: () =>
      apiRequest<TripStopRecord>(
        editingStop ? `/trips/stops/${editingStop.id}/` : "/trips/stops/",
        {
          method: editingStop ? "PATCH" : "POST",
          body: JSON.stringify({ ...stopDraft, trip: tripId }),
        },
      ),
    onSuccess: () => {
      refresh("trip-stops");
      setStopOpen(false);
    },
  });
  const saveHotel = useMutation({
    mutationFn: () =>
      apiRequest<TripHotelRecord>(
        editingHotel ? `/trips/hotels/${editingHotel.id}/` : "/trips/hotels/",
        {
          method: editingHotel ? "PATCH" : "POST",
          body: JSON.stringify(hotelDraft),
        },
      ),
    onSuccess: () => {
      refresh("trip-hotels");
      setHotelOpen(false);
    },
  });
  const saveFlight = useMutation({
    mutationFn: () =>
      apiRequest<TripFlightRecord>(
        editingFlight
          ? `/trips/flights/${editingFlight.id}/`
          : "/trips/flights/",
        {
          method: editingFlight ? "PATCH" : "POST",
          body: JSON.stringify({
            ...flightDraft,
            departure_at: new Date(flightDraft.departure_at).toISOString(),
            arrival_at: new Date(flightDraft.arrival_at).toISOString(),
            trip: tripId,
          }),
        },
      ),
    onSuccess: () => {
      refresh("trip-flights");
      setFlightOpen(false);
    },
  });
  const saveTransport = useMutation({
    mutationFn: () =>
      apiRequest<TripTransportRecord>(
        editingTransport
          ? `/trips/transports/${editingTransport.id}/`
          : "/trips/transports/",
        {
          method: editingTransport ? "PATCH" : "POST",
          body: JSON.stringify({
            ...transportDraft,
            supplier: transportDraft.supplier || null,
            trip: tripId,
          }),
        },
      ),
    onSuccess: () => {
      refresh("trip-transports");
      setTransportOpen(false);
    },
  });
  const uploadDocument = useMutation({
    mutationFn: () => {
      if (!documentFile) throw new Error(t("Choose a file to upload."));
      const body = new FormData();
      body.append("file", documentFile);
      body.append("category", documentCategory);
      body.append("title", documentTitle);
      body.append("owner_type", "TRIP");
      body.append("owner_id", tripId);
      body.append("purpose", documentPurpose);
      return apiRequest<DocumentRecord>("/documents/", {
        method: "POST",
        body,
      });
    },
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["trip-documents", tripId] });
      setDocumentOpen(false);
      setDocumentFile(null);
    },
  });
  const remove = useMutation({
    mutationFn: ({ path }: { path: string; key: string }) =>
      apiRequest<void>(path, { method: "DELETE" }),
    onSuccess: (_, input) => refresh(input.key),
  });
  const transition = useMutation({
    mutationFn: (status: TripRecord["status"]) =>
      apiRequest<TripRecord>(`/trips/${tripId}/transition/`, {
        method: "POST",
        body: JSON.stringify({ status }),
      }),
    onSuccess: (updated) => {
      cache.setQueryData(["trip", tripId], updated);
      cache.invalidateQueries({ queryKey: ["trips"] });
    },
  });

  const deleteItem = (label: string, path: string, key: string) => {
    if (window.confirm(`${t("Delete this item?")} (${t(label)})`))
      remove.mutate({ path, key });
  };
  const openDetails = () => {
    if (!trip.data) return;
    setDetailsDraft({
      code: trip.data.code,
      name: trip.data.name,
      branch: trip.data.branch,
      departure_date: trip.data.departure_date,
      return_date: trip.data.return_date,
      booking_open_date: trip.data.booking_open_date ?? "",
      booking_close_date: trip.data.booking_close_date ?? "",
      pricing_currency: trip.data.pricing_currency ?? "",
      child_with_bed_discount:
        trip.data.child_with_bed_discount?.toString() ?? "",
      child_without_bed_price:
        trip.data.child_without_bed_price?.toString() ?? "",
      infant_price: trip.data.infant_price?.toString() ?? "",
      max_travelers: trip.data.max_travelers?.toString() ?? "",
      description: trip.data.description,
      notes: trip.data.notes,
    });
    saveDetails.reset();
    setDetailsOpen(true);
  };
  const openStopForm = (item?: TripStopRecord) => {
    setEditingStop(item ?? null);
    setStopDraft(
      item
        ? {
            city: item.city,
            arrival_date: item.arrival_date,
            departure_date: item.departure_date,
            order: item.order,
            notes: item.notes,
          }
        : {
            ...emptyStop,
            order: nextOrder(stops.data?.results ?? []),
            arrival_date:
              [...(stops.data?.results ?? [])].sort(
                (a, b) => b.order - a.order,
              )[0]?.departure_date ??
              trip.data?.departure_date ??
              "",
            departure_date: trip.data?.return_date ?? "",
          },
    );
    saveStop.reset();
    setStopOpen(true);
  };
  const openHotelForm = (item?: TripHotelRecord) => {
    const suggestedStop =
      stops.data?.results.find(
        (stop) => !hotels.data?.results.some((hotel) => hotel.stop === stop.id),
      ) ?? stops.data?.results[0];
    setEditingHotel(item ?? null);
    setHotelDraft(
      item
        ? {
            stop: item.stop,
            hotel: item.hotel,
            is_primary: item.is_primary,
            notes: item.notes,
          }
        : {
            ...emptyHotel,
            stop: suggestedStop?.id ?? "",
            is_primary: !hotels.data?.results.some(
              (hotel) => hotel.stop === suggestedStop?.id && hotel.is_primary,
            ),
          },
    );
    saveHotel.reset();
    setHotelOpen(true);
  };
  const openFlightForm = (item?: TripFlightRecord) => {
    setEditingFlight(item ?? null);
    setFlightDraft(
      item
        ? {
            airline: item.airline,
            direction: item.direction,
            flight_number: item.flight_number,
            origin_city: item.origin_city,
            destination_city: item.destination_city,
            origin_airport_code: item.origin_airport_code,
            destination_airport_code: item.destination_airport_code,
            departure_at: localFlightDateTime(item.departure_at),
            arrival_at: localFlightDateTime(item.arrival_at),
            booking_class: item.booking_class,
            order: item.order,
            notes: item.notes,
          }
        : {
            ...emptyFlight,
            ...(trip.data
              ? flightDefaults(
                  trip.data,
                  stops.data?.results ?? [],
                  flights.data?.results ?? [],
                )
              : {}),
          },
    );
    saveFlight.reset();
    setFlightOpen(true);
  };
  const openTransportForm = (item?: TripTransportRecord) => {
    setEditingTransport(item ?? null);
    setTransportDraft(
      item
        ? {
            mode: item.mode,
            supplier: item.supplier ?? "",
            origin_city: item.origin_city,
            destination_city: item.destination_city,
            departure_at: localDateTime(item.departure_at),
            arrival_at: localDateTime(item.arrival_at),
            reference: item.reference,
            vehicle_details: item.vehicle_details,
            vehicle_number: item.vehicle_number,
            order: item.order,
            notes: item.notes,
          }
        : {
            ...emptyTransport,
            order: (transports.data?.results.length ?? 0) + 1,
          },
    );
    saveTransport.reset();
    setTransportOpen(true);
  };
  const openDocumentForm = () => {
    setDocumentTitle("");
    setDocumentCategory("CONTRACT");
    setDocumentPurpose("");
    setDocumentFile(null);
    uploadDocument.reset();
    setDocumentOpen(true);
  };

  if (
    trip.isPending ||
    stops.isPending ||
    hotels.isPending ||
    flights.isPending ||
    transports.isPending ||
    documents.isPending
  )
    return (
      <div className="grid min-h-72 place-items-center">
        <LoaderCircle className="size-8 animate-spin text-cyan-800" />
      </div>
    );
  if (!trip.data)
    return (
      <p className="rounded-lg bg-red-50 p-4 text-red-700">
        {t("Trip is unavailable.")}
      </p>
    );
  const editable = ["DRAFT", "OPEN"].includes(trip.data.status);

  return (
    <div className="space-y-6">
      <TripReadinessPanel tripId={tripId} />
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-col justify-between gap-5 lg:flex-row">
          <div>
            <div className="flex items-center gap-3">
              <p className="text-sm uppercase tracking-wide text-slate-500">
                {trip.data.code}
              </p>
              <span className="rounded-full bg-cyan-50 px-2 py-1 text-xs font-semibold text-cyan-800">
                {t(trip.data.status)}
              </span>
            </div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">
              {trip.data.name}
            </h1>
            <p className="mt-2 text-sm text-slate-600">
              {trip.data.branch_name}
            </p>
            {trip.data.description && (
              <p className="mt-3 max-w-2xl text-sm text-slate-600">
                {trip.data.description}
              </p>
            )}
          </div>
          <div>
            <div className="flex items-center gap-2 text-sm font-medium">
              <CalendarDays className="size-4 text-cyan-700" />
              {trip.data.departure_date} → {trip.data.return_date}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                onClick={openDetails}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium"
              >
                <Pencil className="size-4" />
                {t("Edit details")}
              </button>
              {transitions[trip.data.status]?.map((status) => (
                <button
                  key={status}
                  onClick={() => transition.mutate(status)}
                  disabled={transition.isPending}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:border-cyan-600 hover:text-cyan-800 disabled:opacity-50"
                >
                  {t("Change status to:")} {t(status)}
                </button>
              ))}
            </div>
            {transition.isError && <MutationMessage error={transition.error} />}
          </div>
        </div>
      </section>

      {activeTab === "closing" && <TripClosing tripId={tripId} />}

      {activeTab === "commercial" && (
        <div className="space-y-6">
          <div id="hotel-pricing">
            <TripPricing tripId={tripId} />
          </div>
          <TripCommercialPricing tripId={tripId} />
          <TripPartnerTicketReservations tripId={tripId} />
        </div>
      )}

      {activeTab === "bookings" && <TripBookings tripId={tripId} />}

      {activeTab === "itinerary" && (
        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <section className="rounded-xl border border-slate-200 bg-white">
            <header className="flex items-center justify-between border-b border-slate-200 p-5">
              <div>
                <h2 className="font-semibold">{t("Itinerary")}</h2>
                <p className="text-sm text-slate-500">
                  {t("Ordered cities and hotel selections")}
                </p>
              </div>
              {editable && (
                <button
                  onClick={() => openStopForm()}
                  className="inline-flex items-center gap-1 rounded-lg bg-cyan-800 px-3 py-2 text-sm font-medium text-white"
                >
                  <Plus className="size-4" />
                  {t("Add stop")}
                </button>
              )}
            </header>
            {stops.data?.results.length ? (
              <ol className="divide-y divide-slate-100">
                {stops.data.results.map((stop) => (
                  <li key={stop.id} className="p-5">
                    <div className="flex gap-4">
                      <div className="grid size-8 shrink-0 place-items-center rounded-full bg-cyan-800 text-sm font-semibold text-white">
                        {stop.order}
                      </div>
                      <div className="flex-1">
                        <div className="flex justify-between gap-2">
                          <div>
                            <p className="font-semibold">
                              {stop.city_name}, {stop.country_code}
                            </p>
                            <p className="mt-1 text-sm text-slate-500">
                              {stop.arrival_date} → {stop.departure_date} ·{" "}
                              {stop.nights} {uiText("nights")}
                            </p>
                          </div>
                          {editable && (
                            <Actions
                              onEdit={() => openStopForm(stop)}
                              onDelete={() =>
                                deleteItem(
                                  "stop",
                                  `/trips/stops/${stop.id}/`,
                                  "trip-stops",
                                )
                              }
                            />
                          )}
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {hotels.data?.results
                            .filter((item) => item.stop === stop.id)
                            .map((item) => (
                              <span
                                key={item.id}
                                className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2 py-1 text-xs"
                              >
                                <Hotel className="size-3" />
                                {item.hotel_name}
                                {item.is_primary && ` · ${t("Primary")}`}
                              </span>
                            ))}
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="p-8 text-center text-sm text-slate-500">
                {t("No itinerary stops yet.")}
              </p>
            )}
            {editable && stops.data?.results.length ? (
              <div className="border-t border-slate-100 p-4">
                <button
                  onClick={() => openHotelForm()}
                  className="inline-flex items-center gap-1 text-sm font-medium text-cyan-800"
                >
                  <Plus className="size-4" />
                  {t("Assign hotel to a stop")}
                </button>
              </div>
            ) : null}
          </section>
          <section className="rounded-xl border border-slate-200 bg-white">
            <header className="flex items-center justify-between border-b border-slate-200 p-5">
              <div>
                <h2 className="font-semibold">{t("Flights")}</h2>
                <p className="text-sm text-slate-500">
                  {t("Scheduled airline segments")}
                </p>
              </div>
              {editable && (
                <button
                  onClick={() => openFlightForm()}
                  className="inline-flex items-center gap-1 rounded-lg bg-cyan-800 px-3 py-2 text-sm font-medium text-white"
                >
                  <Plus className="size-4" />
                  {t("Add flight")}
                </button>
              )}
            </header>
            {flights.data?.results.length ? (
              <ul className="divide-y divide-slate-100">
                {flights.data.results.map((flight) => (
                  <li key={flight.id} className="p-5">
                    <FlightDateHint
                      start={trip.data.departure_date}
                      end={trip.data.return_date}
                      departure={localFlightDateTime(flight.departure_at)}
                      arrival={localFlightDateTime(flight.arrival_at)}
                    />
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">
                        {flight.airline_name} {flight.flight_number}
                      </span>
                      {editable ? (
                        <Actions
                          onEdit={() => openFlightForm(flight)}
                          onDelete={() =>
                            deleteItem(
                              "flight",
                              `/trips/flights/${flight.id}/`,
                              "trip-flights",
                            )
                          }
                        />
                      ) : (
                        <span className="text-xs text-slate-500">
                          {t(flight.direction)}
                        </span>
                      )}
                    </div>
                    <div className="mt-3 flex items-center gap-3">
                      <div>
                        <p className="font-mono font-semibold">
                          {flight.origin_airport_code}
                        </p>
                        <p className="text-xs text-slate-500">
                          {flight.origin_city_name}
                        </p>
                      </div>
                      <Plane className="size-4 text-cyan-700" />
                      <div>
                        <p className="font-mono font-semibold">
                          {flight.destination_airport_code}
                        </p>
                        <p className="text-xs text-slate-500">
                          {flight.destination_city_name}
                        </p>
                      </div>
                    </div>
                    <p className="mt-3 text-xs text-slate-500">
                      {new Date(flight.departure_at).toLocaleString()} →{" "}
                      {new Date(flight.arrival_at).toLocaleString()}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="p-8 text-center text-sm text-slate-500">
                {t("No flights scheduled.")}
              </p>
            )}
          </section>
        </div>
      )}

      {activeTab === "accommodation" && (
        <TripAccommodationAllocation tripId={tripId} />
      )}

      {activeTab === "documents" && (
        <section className="rounded-xl border border-slate-200 bg-white">
          <header className="flex items-center justify-between border-b border-slate-200 p-5">
            <div>
              <h2 className="font-semibold">{t("Trip documents")}</h2>
              <p className="text-sm text-slate-500">
                {t("Contracts, vouchers, manifests, and operational files.")}
              </p>
            </div>
            <button
              type="button"
              onClick={openDocumentForm}
              className="inline-flex items-center gap-1 rounded-lg bg-cyan-800 px-3 py-2 text-sm font-medium text-white"
            >
              <Upload className="size-4" />
              {t("Upload document")}
            </button>
          </header>
          {documents.data?.results.length ? (
            <ul className="divide-y divide-slate-100">
              {documents.data.results.map((document) => (
                <li
                  key={document.id}
                  className="flex flex-col justify-between gap-3 px-5 py-4 sm:flex-row sm:items-center"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="size-5 text-slate-400" />
                    <div>
                      <p className="font-medium">{document.title}</p>
                      <p className="text-xs text-slate-500">
                        {t(document.category)} · {document.original_filename} ·{" "}
                        {Math.ceil(document.size_bytes / 1024)} KB
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <a
                      href={document.download_url}
                      className="flex items-center gap-2 text-sm font-medium text-cyan-800"
                    >
                      <Download className="size-4" />
                      {t("Download")}
                    </a>
                    <button
                      type="button"
                      onClick={() =>
                        deleteItem(
                          "document",
                          `/documents/${document.id}/`,
                          "trip-documents",
                        )
                      }
                      className="inline-flex items-center gap-1 text-sm font-medium text-red-600"
                    >
                      <Trash2 className="size-4" />
                      {t("Remove")}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-6 text-sm text-slate-500">
              {t("No trip documents attached.")}
            </p>
          )}
        </section>
      )}

      <FormDialog
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        title={t("Edit trip details")}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveDetails.mutate();
          }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            {detailsDraft && (
              <>
                <Field label={t("Code")}>
                  <input
                    required
                    className="input"
                    value={detailsDraft.code}
                    onChange={(e) =>
                      setDetailsDraft({ ...detailsDraft, code: e.target.value })
                    }
                  />
                </Field>
                <Field label={t("Branch")}>
                  <select
                    required
                    className="input"
                    value={detailsDraft.branch}
                    onChange={(e) =>
                      setDetailsDraft({
                        ...detailsDraft,
                        branch: e.target.value,
                      })
                    }
                  >
                    {branches.data?.results.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label={t("Name")} wide>
                  <input
                    required
                    className="input"
                    value={detailsDraft.name}
                    onChange={(e) =>
                      setDetailsDraft({ ...detailsDraft, name: e.target.value })
                    }
                  />
                </Field>
                <DateField
                  label={t("Departure")}
                  value={detailsDraft.departure_date}
                  onChange={(v) =>
                    setDetailsDraft({ ...detailsDraft, departure_date: v })
                  }
                />
                <DateField
                  label={t("Return")}
                  value={detailsDraft.return_date}
                  onChange={(v) =>
                    setDetailsDraft({ ...detailsDraft, return_date: v })
                  }
                />
                <DateField
                  label={t("Booking opens")}
                  required={false}
                  value={detailsDraft.booking_open_date}
                  onChange={(v) =>
                    setDetailsDraft({ ...detailsDraft, booking_open_date: v })
                  }
                />
                <DateField
                  label={t("Booking closes")}
                  required={false}
                  value={detailsDraft.booking_close_date}
                  onChange={(v) =>
                    setDetailsDraft({ ...detailsDraft, booking_close_date: v })
                  }
                />
                <Field label={t("Maximum travelers")}>
                  <input
                    type="number"
                    min="1"
                    className="input"
                    placeholder={t("Optional")}
                    value={detailsDraft.max_travelers}
                    onChange={(e) =>
                      setDetailsDraft({
                        ...detailsDraft,
                        max_travelers: e.target.value,
                      })
                    }
                  />
                </Field>
                <Field label={t("Pricing currency")}>
                  <select
                    className="input"
                    value={detailsDraft.pricing_currency}
                    onChange={(e) =>
                      setDetailsDraft({
                        ...detailsDraft,
                        pricing_currency: e.target.value,
                      })
                    }
                  >
                    <option value="">{t("Not configured")}</option>
                    {currencies.data?.results
                      .filter((x) => x.is_enabled)
                      .map((x) => (
                        <option key={x.currency} value={x.currency}>
                          {x.currency} · {x.currency_name}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field label={t("Child with bed discount")}>
                  <input
                    type="number"
                    min="0"
                    step="0.0001"
                    className="input"
                    value={detailsDraft.child_with_bed_discount}
                    onChange={(e) =>
                      setDetailsDraft({
                        ...detailsDraft,
                        child_with_bed_discount: e.target.value,
                      })
                    }
                  />
                </Field>
                <Field label={t("Child without bed price")}>
                  <input
                    type="number"
                    min="0"
                    step="0.0001"
                    className="input"
                    value={detailsDraft.child_without_bed_price}
                    onChange={(e) =>
                      setDetailsDraft({
                        ...detailsDraft,
                        child_without_bed_price: e.target.value,
                      })
                    }
                  />
                </Field>
                <Field label={t("Infant price")}>
                  <input
                    type="number"
                    min="0"
                    step="0.0001"
                    className="input"
                    value={detailsDraft.infant_price}
                    onChange={(e) =>
                      setDetailsDraft({
                        ...detailsDraft,
                        infant_price: e.target.value,
                      })
                    }
                  />
                </Field>
                <Field label={t("Description")} wide>
                  <textarea
                    className="input"
                    value={detailsDraft.description}
                    onChange={(e) =>
                      setDetailsDraft({
                        ...detailsDraft,
                        description: e.target.value,
                      })
                    }
                  />
                </Field>
                <Field label={t("Notes")} wide>
                  <textarea
                    className="input"
                    value={detailsDraft.notes}
                    onChange={(e) =>
                      setDetailsDraft({
                        ...detailsDraft,
                        notes: e.target.value,
                      })
                    }
                  />
                </Field>
              </>
            )}
          </div>
          <DialogFooter
            mutation={saveDetails}
            close={() => setDetailsOpen(false)}
            label={t("Save details")}
          />
        </form>
      </FormDialog>

      <FormDialog
        open={stopOpen}
        onClose={() => setStopOpen(false)}
        title={editingStop ? t("Edit itinerary stop") : t("Add itinerary stop")}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveStop.mutate();
          }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("City")} wide>
              <select
                required
                className="input"
                value={stopDraft.city}
                onChange={(e) =>
                  setStopDraft({ ...stopDraft, city: e.target.value })
                }
              >
                <option value="">{t("Select city")}</option>
                {cities.data?.results.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name}, {x.country_code}
                  </option>
                ))}
              </select>
            </Field>
            <DateField
              label={t("Arrival")}
              value={stopDraft.arrival_date}
              onChange={(v) => setStopDraft({ ...stopDraft, arrival_date: v })}
            />
            <DateField
              label={t("Departure")}
              value={stopDraft.departure_date}
              onChange={(v) =>
                setStopDraft({ ...stopDraft, departure_date: v })
              }
            />
            <Field label={t("Number of nights")}>
              <input
                type="number"
                min={0}
                className="input"
                value={
                  stopDraft.arrival_date && stopDraft.departure_date
                    ? Math.max(
                        0,
                        Math.round(
                          (Date.parse(stopDraft.departure_date) -
                            Date.parse(stopDraft.arrival_date)) /
                            86400000,
                        ),
                      )
                    : ""
                }
                onChange={(event) => {
                  if (!stopDraft.arrival_date || event.target.value === "")
                    return;
                  const date = new Date(`${stopDraft.arrival_date}T00:00:00Z`);
                  date.setUTCDate(
                    date.getUTCDate() + Number(event.target.value),
                  );
                  if (!Number.isNaN(date.getTime()))
                    setStopDraft({
                      ...stopDraft,
                      departure_date: date.toISOString().slice(0, 10),
                    });
                }}
              />
            </Field>
            <Field label={t("Order")}>
              <input
                required
                min={1}
                type="number"
                className="input"
                value={stopDraft.order}
                onChange={(e) =>
                  setStopDraft({ ...stopDraft, order: Number(e.target.value) })
                }
              />
            </Field>
            <Field label={t("Notes")} wide>
              <textarea
                className="input"
                value={stopDraft.notes}
                onChange={(e) =>
                  setStopDraft({ ...stopDraft, notes: e.target.value })
                }
              />
            </Field>
          </div>
          <DialogFooter
            mutation={saveStop}
            close={() => setStopOpen(false)}
            label={t("Save stop")}
          />
        </form>
      </FormDialog>

      <FormDialog
        open={hotelOpen}
        onClose={() => setHotelOpen(false)}
        title={editingHotel ? t("Edit trip hotel") : t("Assign hotel")}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveHotel.mutate();
          }}
          className="space-y-4"
        >
          <Field label={t("Itinerary stop")}>
            <select
              required
              className="input"
              value={hotelDraft.stop}
              onChange={(e) =>
                setHotelDraft({
                  ...hotelDraft,
                  stop: e.target.value,
                  hotel: "",
                  is_primary: !hotels.data?.results.some(
                    (hotel) =>
                      hotel.stop === e.target.value && hotel.is_primary,
                  ),
                })
              }
            >
              {stops.data?.results.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.order}. {x.city_name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("Hotel")}>
            <select
              required
              className="input"
              value={hotelDraft.hotel}
              onChange={(e) =>
                setHotelDraft({ ...hotelDraft, hotel: e.target.value })
              }
            >
              <option value="">{t("Select hotel")}</option>
              {hotelOptions.data?.results
                .filter(
                  (hotel) =>
                    hotel.id === editingHotel?.hotel ||
                    (hotel.city ===
                      stops.data?.results.find(
                        (stop) => stop.id === hotelDraft.stop,
                      )?.city &&
                      !hotels.data?.results.some(
                        (link) =>
                          link.stop === hotelDraft.stop &&
                          link.hotel === hotel.id,
                      )),
                )
                .map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name} · {x.city_name}
                  </option>
                ))}
            </select>
          </Field>
          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={hotelDraft.is_primary}
              onChange={(e) =>
                setHotelDraft({ ...hotelDraft, is_primary: e.target.checked })
              }
            />
            {t("Primary hotel for this stop")}
          </label>
          <Field label={t("Notes")}>
            <textarea
              className="input"
              value={hotelDraft.notes}
              onChange={(e) =>
                setHotelDraft({ ...hotelDraft, notes: e.target.value })
              }
            />
          </Field>
          <DialogFooter
            mutation={saveHotel}
            close={() => setHotelOpen(false)}
            label={t("Save hotel")}
          />
        </form>
      </FormDialog>

      <FormDialog
        open={flightOpen}
        onClose={() => setFlightOpen(false)}
        title={editingFlight ? t("Edit flight") : t("Add flight segment")}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveFlight.mutate();
          }}
          className="space-y-4"
        >
          <p className="text-sm text-slate-600">
            {t(
              "Suggested dates and route remain editable. Enter the actual flight times in your local time zone.",
            )}{" "}
            ({Intl.DateTimeFormat().resolvedOptions().timeZone})
          </p>
          <FlightDateHint
            start={trip.data.departure_date}
            end={trip.data.return_date}
            departure={flightDraft.departure_at}
            arrival={flightDraft.arrival_at}
          />
          {!editingFlight && (
            <button
              type="button"
              className="text-sm font-medium text-cyan-800 underline"
              onClick={() =>
                setFlightDraft({
                  ...flightDraft,
                  ...flightDefaults(
                    trip.data,
                    stops.data?.results ?? [],
                    flights.data?.results ?? [],
                    flightDraft.direction,
                  ),
                })
              }
            >
              {t("Use trip dates and suggested route")}
            </button>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("Airline")}>
              <select
                required
                className="input"
                value={flightDraft.airline}
                onChange={(e) =>
                  setFlightDraft({ ...flightDraft, airline: e.target.value })
                }
              >
                <option value="">{t("Select airline")}</option>
                {airlines.data?.results.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("Direction")}>
              <select
                className="input"
                value={flightDraft.direction}
                onChange={(e) =>
                  setFlightDraft({ ...flightDraft, direction: e.target.value })
                }
              >
                <option value="OUTBOUND">{t("Outbound")}</option>
                <option value="RETURN">{t("Return")}</option>
                <option value="INTERNAL">{t("Internal")}</option>
              </select>
            </Field>
            <Field label={t("Flight number")}>
              <input
                required
                className="input"
                value={flightDraft.flight_number}
                onChange={(e) =>
                  setFlightDraft({
                    ...flightDraft,
                    flight_number: e.target.value,
                  })
                }
              />
            </Field>
            <Field label={t("Order")}>
              <input
                required
                min={1}
                type="number"
                className="input"
                value={flightDraft.order}
                onChange={(e) =>
                  setFlightDraft({
                    ...flightDraft,
                    order: Number(e.target.value),
                  })
                }
              />
            </Field>
            <CitySelect
              label={t("Origin city")}
              value={flightDraft.origin_city}
              cities={cities.data?.results ?? []}
              onChange={(v) =>
                setFlightDraft({ ...flightDraft, origin_city: v })
              }
            />
            <Field label={t("Origin airport")}>
              <input
                required
                maxLength={3}
                className="input uppercase"
                value={flightDraft.origin_airport_code}
                onChange={(e) =>
                  setFlightDraft({
                    ...flightDraft,
                    origin_airport_code: e.target.value.toUpperCase(),
                  })
                }
              />
            </Field>
            <CitySelect
              label={t("Destination city")}
              value={flightDraft.destination_city}
              cities={cities.data?.results ?? []}
              onChange={(v) =>
                setFlightDraft({ ...flightDraft, destination_city: v })
              }
            />
            <Field label={t("Destination airport")}>
              <input
                required
                maxLength={3}
                className="input uppercase"
                value={flightDraft.destination_airport_code}
                onChange={(e) =>
                  setFlightDraft({
                    ...flightDraft,
                    destination_airport_code: e.target.value.toUpperCase(),
                  })
                }
              />
            </Field>
            {(["departure_at", "arrival_at"] as const).map((key) => (
              <Field
                key={key}
                label={t(
                  key === "departure_at" ? "Departure time" : "Arrival time",
                )}
              >
                <div className="flex gap-2">
                  <input
                    required
                    aria-label={t("Date")}
                    type="date"
                    className="input"
                    value={flightDraft[key].slice(0, 10)}
                    onChange={(e) =>
                      setFlightDraft({
                        ...flightDraft,
                        [key]: `${e.target.value}T${flightDraft[key].slice(11)}`,
                      })
                    }
                  />
                  <input
                    required
                    aria-label={t("Time")}
                    type="time"
                    className="input"
                    value={flightDraft[key].slice(11)}
                    onChange={(e) =>
                      setFlightDraft({
                        ...flightDraft,
                        [key]: `${flightDraft[key].slice(0, 10)}T${e.target.value}`,
                      })
                    }
                  />
                </div>
              </Field>
            ))}
            <Field label={t("Booking class")}>
              <input
                className="input"
                value={flightDraft.booking_class}
                onChange={(e) =>
                  setFlightDraft({
                    ...flightDraft,
                    booking_class: e.target.value,
                  })
                }
              />
            </Field>
            <Field label={t("Notes")}>
              <input
                className="input"
                value={flightDraft.notes}
                onChange={(e) =>
                  setFlightDraft({ ...flightDraft, notes: e.target.value })
                }
              />
            </Field>
          </div>
          <DialogFooter
            mutation={saveFlight}
            close={() => setFlightOpen(false)}
            label={t("Save flight")}
          />
        </form>
      </FormDialog>
      <FormDialog
        open={documentOpen}
        onClose={() => setDocumentOpen(false)}
        title={t("Upload trip document")}
        description={t(
          "Attach a contract, voucher, manifest, or other operational file.",
        )}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            uploadDocument.mutate();
          }}
          className="space-y-4"
        >
          <Field label={t("Title")}>
            <input
              required
              className="input"
              value={documentTitle}
              onChange={(e) => setDocumentTitle(e.target.value)}
              placeholder={t("e.g. Hotel confirmation voucher")}
            />
          </Field>
          <Field label={t("Category")}>
            <select
              className="input"
              value={documentCategory}
              onChange={(e) => setDocumentCategory(e.target.value)}
            >
              <option value="CONTRACT">{t("Contract")}</option>
              <option value="VISA">{t("Visa")}</option>
              <option value="IDENTITY">{t("Identity")}</option>
              <option value="PHOTO">{t("Photo")}</option>
              <option value="PASSPORT">{t("Passport")}</option>
              <option value="OTHER">{t("Other")}</option>
            </select>
          </Field>
          <Field label={t("Purpose")}>
            <input
              className="input"
              value={documentPurpose}
              onChange={(e) => setDocumentPurpose(e.target.value)}
              placeholder={t("Optional operational purpose")}
            />
          </Field>
          <Field label={t("File")}>
            <input
              required
              type="file"
              className="input"
              onChange={(e) => setDocumentFile(e.target.files?.[0] ?? null)}
            />
          </Field>
          <p className="text-xs text-slate-500">
            {uiText(
              "Maximum size and accepted file types follow the agency document security policy.",
            )}
          </p>
          <DialogFooter
            mutation={uploadDocument}
            close={() => setDocumentOpen(false)}
            label={t("Upload document")}
          />
        </form>
      </FormDialog>
      {activeTab === "transport" && (
        <TransportManager
          items={transports.data?.results ?? []}
          editable={editable}
          open={transportOpen}
          editing={editingTransport}
          draft={transportDraft}
          setDraft={setTransportDraft}
          onAdd={() => openTransportForm()}
          onEdit={openTransportForm}
          onDelete={(item) =>
            deleteItem(
              "transport leg",
              `/trips/transports/${item.id}/`,
              "trip-transports",
            )
          }
          onClose={() => setTransportOpen(false)}
          save={saveTransport}
          cities={cities.data?.results ?? []}
          suppliers={suppliers.data?.results ?? []}
        />
      )}
    </div>
  );
}

function TransportManager({
  items,
  editable,
  open,
  editing,
  draft,
  setDraft,
  onAdd,
  onEdit,
  onDelete,
  onClose,
  save,
  cities,
  suppliers,
}: Readonly<{
  items: TripTransportRecord[];
  editable: boolean;
  open: boolean;
  editing: TripTransportRecord | null;
  draft: TransportDraft;
  setDraft: React.Dispatch<React.SetStateAction<TransportDraft>>;
  onAdd: () => void;
  onEdit: (item: TripTransportRecord) => void;
  onDelete: (item: TripTransportRecord) => void;
  onClose: () => void;
  save: { mutate: () => void; isPending: boolean; error: Error | null };
  cities: City[];
  suppliers: SupplierRecord[];
}>) {
  const t = useOperationalText();
  return (
    <>
      <section className="rounded-xl border border-slate-200 bg-white">
        <header className="flex items-center justify-between border-b border-slate-200 p-5">
          <div>
            <h2 className="font-semibold">{t("Ground transport")}</h2>
            <p className="text-sm text-slate-500">
              {t(
                "Road, rail, ferry, and private transfers between destinations.",
              )}
            </p>
          </div>
          {editable && (
            <button
              type="button"
              onClick={onAdd}
              className="inline-flex items-center gap-1 rounded-lg bg-cyan-800 px-3 py-2 text-sm font-medium text-white"
            >
              <Plus className="size-4" />
              {t("Add transport")}
            </button>
          )}
        </header>
        {items.length ? (
          <div className="divide-y divide-slate-100">
            {items.map((item) => (
              <div
                key={item.id}
                className="grid gap-3 p-5 md:grid-cols-[auto_1fr_auto] md:items-center"
              >
                <span className="grid size-10 place-items-center rounded-lg bg-cyan-50 text-cyan-800">
                  <Bus className="size-5" />
                </span>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold">
                      {item.origin_city_name} → {item.destination_city_name}
                    </p>
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium">
                      {t(item.mode_display)}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">
                    {new Date(item.departure_at).toLocaleString()} →{" "}
                    {new Date(item.arrival_at).toLocaleString()}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {[
                      item.supplier_name,
                      item.reference,
                      item.vehicle_details,
                      item.vehicle_number,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                {editable && (
                  <Actions
                    onEdit={() => onEdit(item)}
                    onDelete={() => onDelete(item)}
                  />
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="p-6 text-sm text-slate-500">
            {t("No ground transport scheduled.")}
          </p>
        )}
      </section>
      <FormDialog
        open={open}
        onClose={onClose}
        title={editing ? t("Edit transport leg") : t("Add transport leg")}
        description={t(
          "Schedule road, rail, ferry, or private travel between cities.",
        )}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("Mode")}>
              <select
                className="input"
                value={draft.mode}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    mode: e.target.value as TransportDraft["mode"],
                  })
                }
              >
                <option value="BUS">{t("Bus")}</option>
                <option value="PRIVATE_CAR">{t("Private car")}</option>
                <option value="TRAIN">{t("Train")}</option>
                <option value="FERRY">{t("Ferry")}</option>
                <option value="OTHER">{t("Other")}</option>
              </select>
            </Field>
            <Field label={t("Supplier")}>
              <select
                className="input"
                value={draft.supplier}
                onChange={(e) =>
                  setDraft({ ...draft, supplier: e.target.value })
                }
              >
                <option value="">{t("No supplier selected")}</option>
                {suppliers.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name}
                  </option>
                ))}
              </select>
            </Field>
            <CitySelect
              label={t("Origin city")}
              value={draft.origin_city}
              cities={cities}
              onChange={(v) => setDraft({ ...draft, origin_city: v })}
            />
            <CitySelect
              label={t("Destination city")}
              value={draft.destination_city}
              cities={cities}
              onChange={(v) => setDraft({ ...draft, destination_city: v })}
            />
            <Field label={t("Departure")}>
              <input
                required
                type="datetime-local"
                className="input"
                value={draft.departure_at}
                onChange={(e) =>
                  setDraft({ ...draft, departure_at: e.target.value })
                }
              />
            </Field>
            <Field label={t("Arrival")}>
              <input
                required
                type="datetime-local"
                className="input"
                value={draft.arrival_at}
                onChange={(e) =>
                  setDraft({ ...draft, arrival_at: e.target.value })
                }
              />
            </Field>
            <Field label={t("Reference")}>
              <input
                className="input"
                value={draft.reference}
                onChange={(e) =>
                  setDraft({ ...draft, reference: e.target.value })
                }
                placeholder={t("Booking or voucher reference")}
              />
            </Field>
            <Field label={t("Vehicle details")}>
              <input
                className="input"
                value={draft.vehicle_details}
                onChange={(e) =>
                  setDraft({ ...draft, vehicle_details: e.target.value })
                }
                placeholder={t("Coach, plate, seat, etc.")}
              />
            </Field>
            <Field label={t("Vehicle number")}>
              <input
                className="input"
                value={draft.vehicle_number}
                onChange={(e) =>
                  setDraft({ ...draft, vehicle_number: e.target.value })
                }
              />
            </Field>
            <Field label={t("Order")}>
              <input
                required
                min={1}
                type="number"
                className="input"
                value={draft.order}
                onChange={(e) =>
                  setDraft({ ...draft, order: Number(e.target.value) })
                }
              />
            </Field>
            <Field label={t("Notes")} wide>
              <textarea
                className="input"
                value={draft.notes}
                onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
              />
            </Field>
          </div>
          <DialogFooter
            mutation={save}
            close={onClose}
            label={t("Save transport")}
          />
        </form>
      </FormDialog>
    </>
  );
}

function Actions({
  onEdit,
  onDelete,
}: Readonly<{ onEdit: () => void; onDelete: () => void }>) {
  const t = useOperationalText();
  return (
    <div className="flex gap-2">
      <button
        onClick={onEdit}
        aria-label={t("Edit")}
        className="rounded p-1 text-cyan-800"
      >
        <Pencil className="size-4" />
      </button>
      <button
        onClick={onDelete}
        aria-label={t("Delete")}
        className="rounded p-1 text-red-600"
      >
        <Trash2 className="size-4" />
      </button>
    </div>
  );
}
function Field({
  label,
  wide,
  children,
}: Readonly<{ label: string; wide?: boolean; children: React.ReactNode }>) {
  return (
    <label
      className={`block text-sm font-medium text-slate-700 ${wide ? "sm:col-span-2" : ""}`}
    >
      {label}
      <div className="mt-1 [&_.input]:w-full [&_.input]:rounded-lg [&_.input]:border [&_.input]:border-slate-300 [&_.input]:px-3 [&_.input]:py-2">
        {children}
      </div>
    </label>
  );
}
function DateField({
  label,
  value,
  onChange,
  required = true,
}: Readonly<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}>) {
  return (
    <Field label={label}>
      <input
        required={required}
        type="date"
        className="input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </Field>
  );
}
function CitySelect({
  label,
  value,
  cities,
  onChange,
}: Readonly<{
  label: string;
  value: string;
  cities: City[];
  onChange: (value: string) => void;
}>) {
  const t = useOperationalText();
  return (
    <Field label={label}>
      <select
        required
        className="input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{t("Select city")}</option>
        {cities.map((x) => (
          <option key={x.id} value={x.id}>
            {x.name}, {x.country_code}
          </option>
        ))}
      </select>
    </Field>
  );
}
function DialogFooter({
  mutation,
  close,
  label,
}: Readonly<{
  mutation: { isPending: boolean; error: Error | null };
  close: () => void;
  label: string;
}>) {
  const uiText = useUiText();
  const t = useOperationalText();
  return (
    <>
      <MutationMessage error={mutation.error} />
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={close}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm"
        >
          {t("Cancel")}
        </button>
        <button
          disabled={mutation.isPending}
          className="rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {mutation.isPending ? uiText("Saving…") : label}
        </button>
      </div>
    </>
  );
}
