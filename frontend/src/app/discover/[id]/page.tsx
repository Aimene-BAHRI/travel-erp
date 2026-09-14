"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type CSSProperties, type ReactNode } from "react";
import { apiRequest } from "@/lib/api/client";
import { MutationMessage } from "@/components/forms/mutation-message";

const categories = ["adult", "child_bed", "child_no_bed", "infant"] as const;
const labels = {
  adult: "Adults",
  child_bed: "Children with bed",
  child_no_bed: "Children without bed",
  infant: "Infants",
};
type Package = {
  package_id: string;
  package_name: string;
  makkah_occupancy: number;
  madinah_occupancy: number;
  currency: string;
  unit_prices: Record<(typeof categories)[number], string>;
};
type Detail = {
  id: string;
  name: string;
  code: string;
  description: string;
  departure_date: string;
  return_date: string;
  is_bookable: boolean;
  max_travelers: number | null;
  booked_places: number;
  remaining_places: number | null;
  agency: {
    name: string;
    phone: string;
    primary_color: string;
    secondary_color: string;
  };
  packages: Package[];
  stops: {
    city: string;
    nights: number;
    hotels: { name: string; stars: number }[];
  }[];
  flights: {
    direction: string;
    airline: string;
    flight_number: string;
    origin: string;
    destination: string;
  }[];
};

export default function PublicTripPage() {
  const { id } = useParams<{ id: string }>();
  const trip = useQuery({
    queryKey: ["public-trip", id],
    queryFn: () => apiRequest<Detail>(`/public/trips/${id}/`),
  });
  const [packageId, setPackageId] = useState("");
  const [counts, setCounts] = useState({
    adult: 1,
    child_bed: 0,
    child_no_bed: 0,
    infant: 0,
  });
  const [contact, setContact] = useState({
    customer_name: "",
    phone: "",
    email: "",
    notes: "",
  });
  const [consent, setConsent] = useState(false);
  const [passportConsent, setPassportConsent] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState("");
  const selected = trip.data?.packages.find((p) => p.package_id === packageId);
  const total = selected
    ? categories.reduce(
        (sum, k) => sum + Number(selected.unit_prices[k]) * counts[k],
        0,
      )
    : null;
  const request = useMutation({
    mutationFn: () => {
      const body = new FormData();
      if (total !== null) body.append("expected_total", total.toFixed(4));
      Object.entries(contact).forEach(([k, v]) => body.append(k, v));
      Object.entries({
        trip: id,
        package: packageId,
        adults: counts.adult,
        children_with_bed: counts.child_bed,
        children_without_bed: counts.child_no_bed,
        infants: counts.infant,
        consent,
        passport_consent: passportConsent,
      }).forEach(([k, v]) => body.append(k, String(v)));
      files.forEach((file) => body.append("passports", file));
      return apiRequest<{ reference: string; total: string; currency: string }>(
        "/public/booking-requests/",
        { method: "POST", body },
      );
    },
  });
  if (trip.isPending) return <p className="p-10">Loading trip…</p>;
  if (!trip.data)
    return (
      <div className="p-10">
        <p>Trip unavailable.</p>
        <Link href="/">All trips</Link>
      </div>
    );
  const t = trip.data;
  return (
    <main
      className="min-h-screen bg-slate-50"
      style={{ "--brand": t.agency.primary_color } as CSSProperties}
    >
      <header
        className="p-8 text-white"
        style={{
          background: `linear-gradient(120deg,${t.agency.secondary_color},${t.agency.primary_color})`,
        }}
      >
        <div className="mx-auto max-w-6xl">
          <Link href="/">← All trips</Link>
          <p className="mt-8">{t.code}</p>
          <h1 className="mt-2 text-4xl font-bold" dir="auto">
            {t.name}
          </h1>
          <p className="mt-4">{t.description}</p>
          <p className="mt-4">
            {t.departure_date} → {t.return_date}
          </p>
          <p className="mt-2 font-semibold">
            {t.remaining_places === null
              ? "Availability confirmed by the agency"
              : t.remaining_places > 0
                ? `${t.remaining_places} places available`
                : "Fully booked"}
          </p>
        </div>
      </header>
      <div className="mx-auto grid max-w-6xl gap-6 p-5 py-10 lg:grid-cols-[1fr_420px]">
        <div className="space-y-6">
          <Section title="Itinerary & accommodation">
            {t.stops.map((s, i) => (
              <div key={i} className="border-b py-4 last:border-0">
                <b>
                  {s.city} · {s.nights} nights
                </b>
                <p dir="auto">
                  {s.hotels.map((h) => h.name).join(" · ") ||
                    "Hotel to be confirmed"}
                </p>
              </div>
            ))}
          </Section>
          <Section title="Flights">
            {t.flights.map((f, i) => (
              <p key={i} className="py-3">
                {f.direction}: {f.origin} → {f.destination}
                <br />
                {f.airline} · {f.flight_number}
              </p>
            ))}
          </Section>
          <Section title="Available packages">
            {t.packages.length ? (
              t.packages.map((p) => (
                <button
                  type="button"
                  key={p.package_id}
                  onClick={() => setPackageId(p.package_id)}
                  className={`mb-3 w-full rounded-xl border p-4 text-left ${packageId === p.package_id ? "border-cyan-700 bg-cyan-50" : "bg-white"}`}
                >
                  <b dir="auto">{p.package_name}</b>
                  <p className="mt-1 text-sm">
                    Makkah: {p.makkah_occupancy} per room · Madinah:{" "}
                    {p.madinah_occupancy} per room
                  </p>
                  <p className="mt-2 font-semibold">
                    {Number(p.unit_prices.adult).toLocaleString("fr-DZ")}{" "}
                    {p.currency} per adult
                  </p>
                </button>
              ))
            ) : (
              <p>
                Packages are being prepared.{" "}
                <a className="underline" href={`tel:${t.agency.phone}`}>
                  Contact the agency for a quote.
                </a>
              </p>
            )}
          </Section>
        </div>
        <Section
          title={request.data ? "Request received" : "Calculate your trip"}
        >
          {request.data ? (
            <div>
              <p>Our team will contact you. Keep this reference:</p>
              <p className="my-4 rounded-lg bg-slate-100 p-4 font-mono font-bold">
                {request.data.reference}
              </p>
              <p>
                Saved estimate:{" "}
                <b>
                  {Number(request.data.total).toLocaleString("fr-DZ")}{" "}
                  {request.data.currency}
                </b>
              </p>
            </div>
          ) : (
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                request.mutate();
              }}
            >
              <Field label="Package">
                <select
                  required
                  className="input"
                  value={packageId}
                  onChange={(e) => setPackageId(e.target.value)}
                >
                  <option value="">Choose a package</option>
                  {t.packages.map((p) => (
                    <option key={p.package_id} value={p.package_id}>
                      {p.package_name}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                {categories.map((k) => (
                  <Field key={k} label={labels[k]}>
                    <input
                      className="input"
                      required
                      type="number"
                      min={k === "adult" ? 1 : 0}
                      max="99"
                      step="1"
                      value={counts[k]}
                      onChange={(e) =>
                        setCounts({ ...counts, [k]: Number(e.target.value) })
                      }
                    />
                  </Field>
                ))}
              </div>
              {selected && (
                <div className="rounded-xl bg-cyan-50 p-4">
                  {categories
                    .filter((k) => counts[k] > 0)
                    .map((k) => (
                      <p key={k} className="mb-2 text-sm">
                        {labels[k]}: {counts[k]} ×{" "}
                        {Number(selected.unit_prices[k]).toLocaleString(
                          "fr-DZ",
                        )}{" "}
                        {selected.currency}
                      </p>
                    ))}
                  <p className="border-t pt-3 text-xl font-bold">
                    Total: {total?.toLocaleString("fr-DZ")} {selected.currency}
                  </p>
                  <p className="mt-2 text-xs text-slate-600">
                    Per-person sharing prices at the selected occupancy. Room
                    availability and the final booking are confirmed by the
                    agency. No payment is required here.
                  </p>
                </div>
              )}
              {(["customer_name", "phone", "email"] as const).map((k) => (
                <Field
                  key={k}
                  label={
                    {
                      customer_name: "Full name",
                      phone: "Phone",
                      email: "Email (optional)",
                    }[k]
                  }
                >
                  <input
                    className="input"
                    required={k !== "email"}
                    type={k === "email" ? "email" : "text"}
                    maxLength={
                      k === "customer_name" ? 180 : k === "phone" ? 40 : 254
                    }
                    value={contact[k]}
                    onChange={(e) =>
                      setContact({ ...contact, [k]: e.target.value })
                    }
                  />
                </Field>
              ))}
              <Field label="Notes">
                <textarea
                  className="input"
                  maxLength={2000}
                  value={contact.notes}
                  onChange={(e) =>
                    setContact({ ...contact, notes: e.target.value })
                  }
                />
              </Field>
              <Field label="Passport pictures (optional)">
                <input
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => {
                    const next = Array.from(e.target.files ?? []);
                    const invalid =
                      next.length > 10 ||
                      next.some((f) => f.size > 10 * 1024 * 1024) ||
                      next.reduce((s, f) => s + f.size, 0) > 25 * 1024 * 1024;
                    setFileError(
                      invalid
                        ? "Maximum 10 images, 10 MB each, 25 MB combined."
                        : "",
                    );
                    setFiles(invalid ? [] : next);
                  }}
                />
              </Field>
              <p className="text-xs text-slate-500">
                JPEG, PNG or WebP. Up to 10 images, 10 MB each, 25 MB combined.
                Only authorized agency staff can download them.
              </p>
              {fileError && (
                <p role="alert" className="text-sm text-red-700">
                  {fileError}
                </p>
              )}
              {files.map((f, i) => (
                <p key={i} className="break-all text-xs">
                  {f.name}
                </p>
              ))}
              {files.length > 0 && (
                <label className="flex gap-2 text-sm">
                  <input
                    type="checkbox"
                    required
                    checked={passportConsent}
                    onChange={(e) => setPassportConsent(e.target.checked)}
                  />
                  I have permission to share these passports with{" "}
                  {t.agency.name} for this trip request.
                </label>
              )}
              <label className="flex gap-2 text-sm">
                <input
                  required
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                />
                I agree that the agency may contact me about this request.
              </label>
              <MutationMessage error={request.error} />
              <button
                disabled={
                  !selected ||
                  !t.is_bookable ||
                  t.remaining_places === 0 ||
                  !!fileError ||
                  request.isPending
                }
                className="w-full rounded-lg bg-[var(--brand)] p-3 font-semibold text-white disabled:opacity-50"
              >
                {request.isPending
                  ? "Sending…"
                  : !t.is_bookable
                    ? "Booking is closed"
                    : t.remaining_places === 0
                      ? "Fully booked"
                      : "Send booking request"}
              </button>
            </form>
          )}
        </Section>
      </div>
    </main>
  );
}
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="h-fit rounded-2xl border bg-white p-6">
      <h2 className="mb-5 text-xl font-bold">{title}</h2>
      {children}
    </section>
  );
}
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      {children}
    </label>
  );
}
