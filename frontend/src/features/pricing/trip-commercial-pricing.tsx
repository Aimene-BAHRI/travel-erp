"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BedDouble, Calculator, Pencil, Plus } from "lucide-react";
import { useState } from "react";

import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { AgencyCurrency, Paginated } from "@/features/reference/types";
import type { RoomTypeRecord } from "@/features/catalog/types";
import type { TripHotelRecord } from "@/features/trips/types";
import { apiRequest } from "@/lib/api/client";

import type { OccupancyPackageRecord, HotelPriceRecord } from "./types";

const packageBlank = {
  adult_price: "",
  trip_hotel: "",
  room_type: "",
  adult_amount: "",
  currency: "",
  code: "",
  name: "",
  makkah_occupancy: 1,
  madinah_occupancy: 1,
  override_adult: "",
  override_child_bed: "",
  override_child_no_bed: "",
  override_infant: "",
  rounding_increment: 100,
  is_published: false,
};

type PackageDraft = typeof packageBlank;

function Field({
  label,
  children,
}: Readonly<{ label: string; children: React.ReactNode }>) {
  const uiText = useUiText();
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{uiText(label)}</span>
      {children}
    </label>
  );
}

export function TripCommercialPricing({
  tripId,
}: Readonly<{ tripId: string }>) {
  const uiText = useUiText();
  const cache = useQueryClient();
  const [packageOpen, setPackageOpen] = useState(false);
  const [packageId, setPackageId] = useState<string | null>(null);
  const [pkg, setPkg] = useState<PackageDraft>(packageBlank);
  const trip = useQuery({
    queryKey: ["trip", tripId],
    queryFn: () => apiRequest<import("@/features/trips/types").TripRecord>(`/trips/${tripId}/`),
  });
  const packages = useQuery({
    queryKey: ["occupancy-packages", tripId],
    queryFn: () =>
      apiRequest<Paginated<OccupancyPackageRecord>>(
        `/pricing/occupancy-packages/?trip=${tripId}`,
      ),
  });
  const hotelPrices = useQuery({
    queryKey: ["package-hotel-prices", tripId],
    queryFn: () =>
      apiRequest<Paginated<HotelPriceRecord>>(
        `/pricing/hotel-prices/?trip=${tripId}&scope=TRIP_PACKAGE`,
      ),
  });
  const tripHotels = useQuery({
    queryKey: ["trip-hotels", tripId],
    queryFn: () =>
      apiRequest<Paginated<TripHotelRecord>>(`/trips/hotels/?trip=${tripId}`),
  });
  const roomTypes = useQuery({
    queryKey: ["room-types"],
    queryFn: () =>
      apiRequest<Paginated<RoomTypeRecord>>(
        "/catalog/room-types/?ordering=sort_order",
      ),
  });
  const childWithBedPrice =
    pkg.adult_amount && trip.data?.child_with_bed_discount != null
      ? Math.max(
          0,
          Number(pkg.adult_amount) - Number(trip.data.child_with_bed_discount),
        )
      : null;
  const currencies = useQuery({
    queryKey: ["agency-currencies"],
    queryFn: () =>
      apiRequest<Paginated<AgencyCurrency>>("/reference/agency-currencies/"),
  });
  const refresh = () => {
    cache.invalidateQueries({ queryKey: ["occupancy-packages", tripId] });
    cache.invalidateQueries({ queryKey: ["public-trip", tripId] });
  };
  const savePackage = useMutation({
    mutationFn: () => {
      const payload = {
        ...pkg,
        adult_price: undefined,
        override_adult: null,
        override_child_bed: null,
        override_child_no_bed: null,
        override_infant: null,
        trip: tripId,
      };
      return apiRequest(
        packageId
          ? `/pricing/occupancy-packages/${packageId}/`
          : "/pricing/occupancy-packages/",
        {
          method: packageId ? "PATCH" : "POST",
          body: JSON.stringify(payload),
        },
      );
    },
    onSuccess: () => {
      refresh();
      setPackageOpen(false);
    },
  });
  const editPackage = (x?: OccupancyPackageRecord) => {
    setPackageId(x?.id ?? null);
    setPkg(
      x
        ? {
            adult_price: x.adult_price ?? "",
            trip_hotel:
              hotelPrices.data?.results.find(
                (price) => price.id === x.adult_price,
              )?.trip_hotel ?? "",
            room_type:
              hotelPrices.data?.results.find(
                (price) => price.id === x.adult_price,
              )?.room_type ?? "",
            adult_amount:
              hotelPrices.data?.results.find(
                (price) => price.id === x.adult_price,
              )?.amount ?? "",
            currency:
              hotelPrices.data?.results.find(
                (price) => price.id === x.adult_price,
              )?.currency ?? "",
            code: x.code,
            name: x.name,
            makkah_occupancy: x.makkah_occupancy,
            madinah_occupancy: x.madinah_occupancy,
            override_adult: x.override_adult ?? "",
            override_child_bed: "",
            override_child_no_bed: x.override_child_no_bed ?? "",
            override_infant: x.override_infant ?? "",
            rounding_increment: x.rounding_increment,
            is_published: x.is_published,
          }
        : {
            ...packageBlank,
            trip_hotel: tripHotels.data?.results[0]?.id ?? "",
            room_type: roomTypes.data?.results[0]?.id ?? "",
            currency:
              currencies.data?.results.find((item) => item.is_accounting)
                ?.currency ??
              currencies.data?.results[0]?.currency ??
              "",
          },
    );
    savePackage.reset();
    setPackageOpen(true);
  };
  return (
    <div className="space-y-6">
      <section className="rounded-xl border bg-white">
        <header className="flex items-center justify-between border-b p-5">
          <div>
            <h2 className="font-semibold">{uiText("Occupancy packages")}</h2>
            <p className="text-sm text-slate-500">
              {uiText(
                "Set the selling price for each traveler type. Only published packages appear publicly.",
              )}
            </p>
          </div>
          <button
            onClick={() => editPackage()}
            className="inline-flex items-center gap-1 rounded-lg bg-cyan-800 px-3 py-2 text-sm text-white"
          >
            <Plus className="size-4" />
            {uiText("Add package")}
          </button>
        </header>
        <div className="grid gap-4 p-5 lg:grid-cols-2">
          {packages.data?.results.map((x) => (
            <article key={x.id} className="rounded-xl border p-4">
              <div className="flex justify-between">
                <div>
                  <p className="font-semibold">{x.name}</p>
                  <p className="text-xs text-slate-500">
                    {x.adult_price
                      ? `${uiText("Hotel room package")} · ${x.adult_price}`
                      : `${uiText("Makkah")} ${x.makkah_occupancy} ${uiText("· Madinah")} ${x.madinah_occupancy}`}{" "}
                    {x.is_published ? uiText("· Published") : uiText("· Draft")}
                  </p>
                </div>
                <button
                  onClick={() => editPackage(x)}
                  className="text-cyan-800"
                >
                  <Pencil className="size-4" />
                </button>
              </div>
              {x.calculated ? (
                <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                  {Object.entries(x.calculated.unit_prices).map(
                    ([key, value]) => (
                      <p key={key} className="rounded bg-slate-50 p-2">
                        <span className="block text-xs text-slate-500">
                          {uiText(
                            key === "child_bed"
                              ? "Child with bed price"
                              : key === "child_no_bed"
                                ? "Child without bed price"
                                : key === "infant"
                                  ? "Infant price"
                                  : "Adult price",
                          )}
                        </span>
                        <b>
                          {Number(value).toLocaleString("fr-DZ")}{" "}
                          {x.calculated?.currency}
                        </b>
                      </p>
                    ),
                  )}
                </div>
              ) : (
                <p className="mt-4 text-sm text-amber-700">
                  {uiText(
                    "Configure all four prices and the accounting currency to calculate.",
                  )}
                </p>
              )}
            </article>
          ))}
        </div>
      </section>
      <FormDialog
        open={packageOpen}
        onClose={() => setPackageOpen(false)}
        title={
          packageId
            ? uiText("Edit occupancy package")
            : uiText("Add occupancy package")
        }
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            savePackage.mutate();
          }}
          className="space-y-4"
        >
          <div className="space-y-5">
            <section className="rounded-xl border border-cyan-200 bg-cyan-50/60 p-4">
              <div className="mb-3 flex items-start gap-3">
                <BedDouble className="mt-0.5 size-5 text-cyan-800" />
                <div>
                  <h3 className="font-semibold text-cyan-950">
                    {uiText("1. Choose the trip hotel and room")}
                  </h3>
                  <p className="text-sm text-cyan-900">
                    {uiText(
                      "The package will use this room's adult price and will remain linked to this trip.",
                    )}
                  </p>
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={uiText("Trip hotel")}>
                  <select
                    required
                    className="input"
                    value={pkg.trip_hotel}
                    onChange={(event) =>
                      setPkg({ ...pkg, trip_hotel: event.target.value })
                    }
                  >
                    <option value="">{uiText("Select")}</option>
                    {tripHotels.data?.results.map((hotel) => (
                      <option key={hotel.id} value={hotel.id}>
                        {hotel.hotel_name} · {hotel.city_name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label={uiText("Room type")}>
                  <select
                    required
                    className="input"
                    value={pkg.room_type}
                    onChange={(event) =>
                      setPkg({ ...pkg, room_type: event.target.value })
                    }
                  >
                    <option value="">{uiText("Select")}</option>
                    {roomTypes.data?.results.map((room) => (
                      <option key={room.id} value={room.id}>
                        {room.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label={uiText("Adult price")}>
                  <input
                    required
                    type="number"
                    min="0"
                    step="0.0001"
                    className="input"
                    value={pkg.adult_amount}
                    onChange={(event) =>
                      setPkg({
                        ...pkg,
                        adult_amount: event.target.value,
                        override_adult: event.target.value,
                      })
                    }
                  />
                </Field>
                <Field label={uiText("Currency")}>
                  <select
                    required
                    className="input"
                    value={pkg.currency}
                    onChange={(event) =>
                      setPkg({ ...pkg, currency: event.target.value })
                    }
                  >
                    <option value="">{uiText("Select")}</option>
                    {currencies.data?.results
                      .filter((item) => item.is_enabled)
                      .map((item) => (
                        <option key={item.currency} value={item.currency}>
                          {item.currency} · {item.currency_name}
                        </option>
                      ))}
                  </select>
                </Field>
              </div>
            </section>
            <section className="grid gap-4 sm:grid-cols-2">
            </section>
            <section className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <h3 className="font-semibold">
                  {uiText("3. Set traveler prices")}
                </h3>
                <p className="text-sm text-slate-500">
                  {uiText(
            "The child-with-bed price is calculated from the selected room's adult price and the trip's child discount. Child-without-bed and infant prices come from trip details.",
                  )}
                </p>
              </div>
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm">
                <span className="block text-xs text-emerald-800">
                  {uiText("Adult price")}
                </span>
                <b>
                  {pkg.adult_amount
                    ? `${pkg.adult_amount} ${pkg.currency}`
                    : uiText("Enter the adult price above")}
                </b>
              </div>
              <div className="rounded-lg border border-cyan-200 bg-cyan-50 p-3 text-sm">
                <span className="block text-xs text-cyan-800">
                  {uiText("Child with bed price")}
                </span>
                <b>
                  {childWithBedPrice == null
                    ? uiText("Set the trip discount and adult price to calculate")
                    : `${childWithBedPrice.toLocaleString("fr-DZ")} ${pkg.currency}`}
                </b>
                {trip.data?.child_with_bed_discount != null && (
                  <span className="mt-1 block text-xs text-cyan-800">
                    {uiText("Trip discount")}: {trip.data.child_with_bed_discount} {pkg.currency}
                  </span>
                )}
              </div>
            </section>
          </div>
          <label className="flex items-start gap-3 rounded-lg border p-3 text-sm">
            <input
              type="checkbox"
              checked={pkg.is_published}
              onChange={(event) =>
                setPkg({ ...pkg, is_published: event.target.checked })
              }
            />
            <span>
              <b className="block">
                {uiText("Publish this package on the public trip page")}
              </b>
              <span className="text-slate-500">
                {uiText(
                  "Clients will see this package in the trip offer preview.",
                )}
              </span>
            </span>
          </label>
          <MutationMessage error={savePackage.error} />
          <button className="flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-800 py-2 text-white">
            <Calculator className="size-4" />
            {uiText("Save package")}
          </button>
        </form>
      </FormDialog>
    </div>
  );
}
