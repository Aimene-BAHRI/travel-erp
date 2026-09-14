"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Headphones,
  LoaderCircle,
  Mail,
  MapPin,
  Phone,
  Plane,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useMemo, useState, type CSSProperties } from "react";
import { apiRequest } from "@/lib/api/client";

type PublicTrip = {
  id: string;
  code: string;
  name: string;
  description: string;
  departure_date: string;
  return_date: string;
  booking_open_date: string | null;
  booking_close_date: string | null;
  duration_days: number;
  max_travelers: number | null;
  booked_places: number;
  remaining_places: number | null;
  stops: Array<{ city: string; nights: number; hotels: string[] }>;
  airlines: string[];
  departure_airport: string;
  starting_price: string | null;
  currency: string | null;
  has_promotion: boolean;
};
type HomeData = {
  agency: null | {
    name: string;
    legal_name: string;
    logo: string | null;
    phone: string;
    email: string;
    address: string;
    website: string;
    primary_color: string;
    secondary_color: string;
  };
  available_trips: PublicTrip[];
  upcoming_trips: PublicTrip[];
};

export function PublicHome() {
  const [destination, setDestination] = useState("");
  const [departure, setDeparture] = useState("");
  const home = useQuery({
    queryKey: ["public-home"],
    queryFn: () => apiRequest<HomeData>("/public/home/"),
  });
  const trips = useMemo(
    () =>
      (home.data?.available_trips ?? []).filter(
        (t) =>
          (!destination ||
            t.stops.some((s) =>
              s.city.toLowerCase().includes(destination.toLowerCase()),
            )) &&
          (!departure || t.departure_date >= departure),
      ),
    [departure, destination, home.data],
  );
  if (home.isPending)
    return (
      <div className="grid min-h-screen place-items-center bg-slate-950">
        <LoaderCircle className="size-8 animate-spin text-cyan-300" />
      </div>
    );
  if (!home.data?.agency)
    return (
      <main className="grid min-h-screen place-items-center bg-slate-950 p-8 text-center text-white">
        <div>
          <Plane className="mx-auto size-12 text-cyan-300" />
          <h1 className="mt-5 text-3xl font-bold">
            Travel experiences are coming soon
          </h1>
          <p className="mt-2 text-slate-300">
            The agency storefront is being prepared.
          </p>
        </div>
      </main>
    );
  const agency = home.data.agency;
  const contact = agency.email
    ? `mailto:${agency.email}`
    : `tel:${agency.phone}`;
  const theme = {
    "--brand": agency.primary_color,
    "--brand-secondary": agency.secondary_color,
  } as CSSProperties;
  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" style={theme}>
      <header className="absolute inset-x-0 top-0 z-10 border-b border-white/10 text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 lg:px-8">
          <a href="#top" className="flex items-center gap-3">
            {agency.logo ? (
              <span
                className="size-11 rounded-lg bg-white bg-contain bg-center bg-no-repeat"
                style={{ backgroundImage: `url(${agency.logo})` }}
              />
            ) : (
              <span className="grid size-11 place-items-center rounded-lg bg-cyan-500">
                <Plane className="size-6" />
              </span>
            )}
            <span className="text-lg font-bold">{agency.name}</span>
          </a>
          <div className="flex items-center gap-3">
            <a href="#trips" className="hidden text-sm sm:block">
              Available trips
            </a>
            {agency.phone && (
              <a
                href={`tel:${agency.phone}`}
                className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-950"
              >
                Contact us
              </a>
            )}
            <a href="/login" className="text-sm text-slate-300">
              Staff login
            </a>
          </div>
        </div>
      </header>
      <section
        id="top"
        className="relative overflow-hidden px-5 pb-28 pt-36 text-white"
        style={{
          background: `linear-gradient(125deg, ${agency.secondary_color}, ${agency.primary_color})`,
        }}
      >
        <div className="absolute -right-28 top-16 size-96 rounded-full bg-white/10 blur-3xl" />
        <div className="relative mx-auto max-w-7xl">
          <div className="max-w-3xl">
            <p className="font-semibold uppercase tracking-[.22em] text-white/75">
              Travel with confidence
            </p>
            <h1 className="mt-5 text-4xl font-bold leading-tight sm:text-6xl">
              Find your next journey with {agency.name}
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-white/75">
              Organized flights, trusted accommodation, transportation, and
              traveler support—all coordinated by one experienced team.
            </p>
          </div>
          <div className="mt-10 grid gap-3 rounded-2xl bg-white p-4 text-slate-950 shadow-2xl md:grid-cols-[1fr_1fr_auto]">
            <SearchField label="Destination" icon={<MapPin />}>
              <input
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                placeholder="Makkah, Madinah…"
                className="w-full outline-none"
              />
            </SearchField>
            <SearchField label="Departing after" icon={<CalendarDays />}>
              <input
                type="date"
                value={departure}
                onChange={(e) => setDeparture(e.target.value)}
                className="w-full outline-none"
              />
            </SearchField>
            <a
              href="#trips"
              className="flex items-center justify-center gap-2 rounded-xl bg-[var(--brand)] px-7 py-4 font-semibold text-white"
            >
              <Search className="size-5" />
              Find trips
            </a>
          </div>
        </div>
      </section>
      <section id="trips" className="mx-auto max-w-7xl px-5 py-20 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-semibold text-cyan-800">Open for booking</p>
            <h2 className="mt-2 text-3xl font-bold">Available trips</h2>
            <p className="mt-2 text-slate-600">
              Choose an itinerary and contact our team to reserve your place.
            </p>
          </div>
          <span className="rounded-full bg-cyan-50 px-4 py-2 text-sm font-medium text-cyan-800">
            {trips.length} trip{trips.length === 1 ? "" : "s"}
          </span>
        </div>
        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          {trips.map((t) => (
            <TripCard key={t.id} trip={t} contact={contact} />
          ))}
          {!trips.length && (
            <div className="col-span-full rounded-2xl border-2 border-dashed bg-white p-12 text-center">
              <CalendarDays className="mx-auto size-10 text-slate-300" />
              <h3 className="mt-4 text-lg font-semibold">
                No matching trips right now
              </h3>
              <p className="mt-1 text-slate-500">
                Clear the filters or contact the agency for the next departure.
              </p>
            </div>
          )}
        </div>
      </section>
      {!!home.data.upcoming_trips.length && (
        <section className="bg-white">
          <div className="mx-auto max-w-7xl px-5 py-16 lg:px-8">
            <p className="font-semibold text-cyan-800">Plan ahead</p>
            <h2 className="mt-2 text-3xl font-bold">Opening soon</h2>
            <div className="mt-7 grid gap-4 md:grid-cols-3">
              {home.data.upcoming_trips.map((t) => (
                <article key={t.id} className="rounded-xl border p-5">
                  <Clock3 className="size-5 text-cyan-700" />
                  <h3 className="mt-3 font-bold">{t.name}</h3>
                  <p className="mt-1 text-sm text-slate-500">
                    Departs {date(t.departure_date)}
                  </p>
                  <p className="mt-4 text-sm font-medium text-cyan-800">
                    Booking opens{" "}
                    {t.booking_open_date ? date(t.booking_open_date) : "soon"}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>
      )}
      <section className="mx-auto grid max-w-7xl gap-5 px-5 py-20 md:grid-cols-3 lg:px-8">
        <Benefit
          icon={<ShieldCheck />}
          title="Trusted organization"
          text="Itinerary, accommodation, and transport coordinated from departure to return."
        />
        <Benefit
          icon={<Headphones />}
          title="Traveler follow-up"
          text="Support before departure and throughout the journey."
        />
        <Benefit
          icon={<CheckCircle2 />}
          title="Clear arrangements"
          text="Trip dates, hotels, flights, and booking details presented clearly."
        />
      </section>
      <footer className="bg-slate-950 text-slate-300">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-12 md:grid-cols-2 lg:px-8">
          <div>
            <h2 className="text-xl font-bold text-white">{agency.name}</h2>
            <p className="mt-3 text-sm">
              {agency.legal_name || "Your trusted travel partner."}
            </p>
          </div>
          <div className="space-y-2 text-sm md:justify-self-end">
            {agency.address && (
              <p className="flex gap-2">
                <MapPin className="size-4 text-cyan-300" />
                {agency.address}
              </p>
            )}
            {agency.phone && (
              <a href={`tel:${agency.phone}`} className="flex gap-2">
                <Phone className="size-4 text-cyan-300" />
                {agency.phone}
              </a>
            )}
            {agency.email && (
              <a href={`mailto:${agency.email}`} className="flex gap-2">
                <Mail className="size-4 text-cyan-300" />
                {agency.email}
              </a>
            )}
          </div>
        </div>
      </footer>
    </main>
  );
}

function TripCard({ trip, contact }: { trip: PublicTrip; contact: string }) {
  return (
    <article className="overflow-hidden rounded-2xl border bg-white shadow-sm">
      <div
        className="p-6 text-white"
        style={{
          background:
            "linear-gradient(110deg, var(--brand), var(--brand-secondary))",
        }}
      >
        <div className="flex justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-white/70">
              {trip.code}
            </p>
            <h3 className="mt-2 text-2xl font-bold">{trip.name}</h3>
          </div>
          {trip.has_promotion && (
            <span className="h-fit rounded-full bg-amber-300 px-3 py-1 text-xs font-bold text-amber-950">
              Promotion
            </span>
          )}
        </div>
        <p className="mt-4 line-clamp-2 text-sm text-white/75">
          {trip.description || "A complete organized travel program."}
        </p>
      </div>
      <div className="p-6">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <Info
            icon={<CalendarDays />}
            label="Travel dates"
            value={`${date(trip.departure_date)} – ${date(trip.return_date)}`}
          />
          <Info
            icon={<Clock3 />}
            label="Duration"
            value={`${trip.duration_days} days`}
          />
          <Info
            icon={<Plane />}
            label="Flight"
            value={
              [trip.departure_airport, ...trip.airlines]
                .filter(Boolean)
                .join(" · ") || "To be confirmed"
            }
          />
          <Info
            icon={<Building2 />}
            label="Accommodation"
            value={
              trip.stops
                .map(
                  (s) => `${s.city}${s.hotels[0] ? ` · ${s.hotels[0]}` : ""}`,
                )
                .join(" / ") || "To be confirmed"
            }
          />
        </div>
        <div className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700">
          {trip.remaining_places === null
            ? "Availability confirmed by the agency"
            : trip.remaining_places > 0
              ? `${trip.remaining_places} places available`
              : "Fully booked"}
        </div>
        <div className="mt-6 flex items-end justify-between gap-3 border-t pt-5">
          <div>
            <p className="text-xs uppercase text-slate-500">Starting from</p>
            <p className="mt-1 text-xl font-bold">
              {trip.starting_price
                ? `${amount(trip.starting_price)} ${trip.currency}`
                : "Contact us"}
            </p>
          </div>
          <div className="flex gap-2">
            <a
              href={contact}
              className="rounded-lg border px-3 py-2.5 text-sm font-semibold"
            >
              Contact
            </a>
            <a
              href={`/discover/${trip.id}`}
              className="inline-flex items-center gap-2 rounded-lg bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white"
            >
              View details <ArrowRight className="size-4" />
            </a>
          </div>
        </div>
      </div>
    </article>
  );
}
function SearchField({
  label,
  icon,
  children,
}: {
  label: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <label className="rounded-xl border px-4 py-3 text-sm">
      <span className="block text-xs font-medium uppercase text-slate-500">
        {label}
      </span>
      <div className="mt-1 flex items-center gap-2 text-cyan-700 [&>svg]:size-4">
        {icon}
        <span className="flex-1 text-slate-950">{children}</span>
      </div>
    </label>
  );
}
function Info({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 text-cyan-700 [&>svg]:size-4">{icon}</span>
      <div>
        <p className="text-xs uppercase text-slate-400">{label}</p>
        <p className="mt-1 font-medium">{value}</p>
      </div>
    </div>
  );
}
function Benefit({
  icon,
  title,
  text,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <article className="rounded-2xl border bg-white p-6">
      <span className="text-cyan-700 [&>svg]:size-7">{icon}</span>
      <h3 className="mt-4 text-lg font-bold">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-600">{text}</p>
    </article>
  );
}
function date(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}
function amount(value: string) {
  return new Intl.NumberFormat("fr-DZ", { maximumFractionDigits: 0 }).format(
    Number(value),
  );
}
