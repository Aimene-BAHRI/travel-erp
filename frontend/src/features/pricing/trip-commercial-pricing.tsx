"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, Pencil, Plus } from "lucide-react";
import { useState } from "react";

import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";

import type { OccupancyPackageRecord, HotelPriceRecord } from "./types";

const packageBlank = {
  adult_price: "",
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

const priceLabels = {
  adult: "Adult price",
  child_bed: "Child with bed price",
  child_no_bed: "Child without bed price",
  infant: "Infant price",
} as const;

type PackageDraft = typeof packageBlank;

type PriceKey = keyof typeof priceLabels;

function overrideKey(key: PriceKey): keyof PackageDraft {
  return `override_${key}` as keyof PackageDraft;
}

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
  const packages = useQuery({
    queryKey: ["occupancy-packages", tripId],
    queryFn: () =>
      apiRequest<Paginated<OccupancyPackageRecord>>(
        `/pricing/occupancy-packages/?trip=${tripId}`,
      ),
  });
  const hotelPrices = useQuery({queryKey: ["package-hotel-prices", tripId], queryFn: () => apiRequest<Paginated<HotelPriceRecord>>(`/pricing/hotel-prices/?trip=${tripId}&scope=TRIP_PACKAGE`)});
  const refresh = () => {
    cache.invalidateQueries({ queryKey: ["occupancy-packages", tripId] });
    cache.invalidateQueries({ queryKey: ["public-trip", tripId] });
  };
  const savePackage = useMutation({
    mutationFn: () =>
      apiRequest(
        packageId
          ? `/pricing/occupancy-packages/${packageId}/`
          : "/pricing/occupancy-packages/",
        {
          method: packageId ? "PATCH" : "POST",
          body: JSON.stringify({ ...pkg, adult_price: pkg.adult_price || null, trip: tripId }),
        },
      ),
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
            code: x.code,
            name: x.name,
            makkah_occupancy: x.makkah_occupancy,
            madinah_occupancy: x.madinah_occupancy,
            override_adult: x.override_adult ?? "",
            override_child_bed: x.override_child_bed ?? "",
            override_child_no_bed: x.override_child_no_bed ?? "",
            override_infant: x.override_infant ?? "",
            rounding_increment: x.rounding_increment,
            is_published: x.is_published,
          }
        : packageBlank,
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
              {uiText("Set the selling price for each traveler type. Only published packages appear publicly.")}
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
                    {uiText("Makkah")} {x.makkah_occupancy} {uiText("· Madinah")} {x.madinah_occupancy}{" "}
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
                          {uiText(priceLabels[key as PriceKey])}
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
                  {uiText("Configure all four prices and the accounting currency to calculate.")}
                </p>
              )}
            </article>
          ))}
        </div>
      </section>
      <FormDialog
        open={packageOpen}
        onClose={() => setPackageOpen(false)}
        title={packageId ? uiText("Edit occupancy package") : uiText("Add occupancy package")}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            savePackage.mutate();
          }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Hotel-specific adult package"><select required={!packageId} className="input" value={pkg.adult_price} onChange={(e) => setPkg({ ...pkg, adult_price: e.target.value })}><option value="">{packageId ? "Legacy package ? no hotel link" : "Select hotel / room / adult price"}</option>{hotelPrices.data?.results.map((price) => <option key={price.id} value={price.id}>{price.hotel_name} ? {price.room_type_name} ? {price.amount} {price.currency_code}</option>)}</select></Field>
              <Field label={uiText("Code")}>
              <input
                required
                className="input"
                value={pkg.code}
                onChange={(event) =>
                  setPkg({ ...pkg, code: event.target.value })
                }
              />
            </Field>
            <Field label={uiText("Name")}>
              <input
                required
                className="input"
                value={pkg.name}
                onChange={(event) =>
                  setPkg({ ...pkg, name: event.target.value })
                }
              />
            </Field>
            <Field label={uiText("Makkah occupancy")}>
              <input
                required
                type="number"
                min="1"
                className="input"
                value={pkg.makkah_occupancy}
                onChange={(event) =>
                  setPkg({
                    ...pkg,
                    makkah_occupancy: Number(event.target.value),
                  })
                }
              />
            </Field>
            <Field label={uiText("Madinah occupancy")}>
              <input
                required
                type="number"
                min="1"
                className="input"
                value={pkg.madinah_occupancy}
                onChange={(event) =>
                  setPkg({
                    ...pkg,
                    madinah_occupancy: Number(event.target.value),
                  })
                }
              />
            </Field>
            {(Object.keys(priceLabels) as PriceKey[]).map((key) => (
              <Field key={key} label={priceLabels[key]}>
                <input
                  required
                  type="number"
                  min="0"
                  step="0.0001"
                  className="input"
                  value={pkg[overrideKey(key)] as string}
                  onChange={(event) =>
                    setPkg({
                      ...pkg,
                      [overrideKey(key)]: event.target.value,
                    } as PackageDraft)
                  }
                />
              </Field>
            ))}
            <Field label={uiText("Rounding increment")}>
              <input
                required
                type="number"
                min="1"
                className="input"
                value={pkg.rounding_increment}
                onChange={(event) =>
                  setPkg({
                    ...pkg,
                    rounding_increment: Number(event.target.value),
                  })
                }
              />
            </Field>
          </div>
          <label className="flex gap-2 text-sm">
            <input
              type="checkbox"
              checked={pkg.is_published}
              onChange={(event) =>
                setPkg({ ...pkg, is_published: event.target.checked })
              }
            />
            {uiText("Publish this package on the public trip page")}
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
