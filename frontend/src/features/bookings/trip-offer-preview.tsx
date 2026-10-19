"use client";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { HotelPriceRecord } from "@/features/pricing/types";
import type { OccupancyPackageRecord } from "@/features/pricing/types";
import type { Paginated } from "@/features/reference/types";
import type { AccommodationPlan } from "@/features/trips/types";

export function TripOfferPreview({ trip }: { trip: string }) {
  const { locale } = useLocale();
  const t = (en: string, ar: string) => (locale === "ar" ? ar : en);
  const packages = useQuery({
    queryKey: ["trip-offer-packages", trip],
    enabled: Boolean(trip),
    queryFn: async () => {
      const first = await apiRequest<Paginated<OccupancyPackageRecord>>(
        `/pricing/occupancy-packages/?trip=${trip}&is_published=true`,
      );
      const results = [...first.results];
      let next = first.next;
      while (next) {
        const page = await apiRequest<Paginated<OccupancyPackageRecord>>(
          `/pricing/occupancy-packages/${new URL(next, "http://localhost").search}`,
        );
        results.push(...page.results);
        next = page.next;
      }
      return results;
    },
  });
  const prices = useQuery({
    queryKey: ["trip-offer-prices", trip],
    enabled: Boolean(trip),
    queryFn: async () => {
      const first = await apiRequest<Paginated<HotelPriceRecord>>(
        `/pricing/hotel-prices/?trip=${trip}&scope=TRIP_PACKAGE`,
      );
      const results = [...first.results];
      let next = first.next;
      while (next) {
        const page = await apiRequest<Paginated<HotelPriceRecord>>(
          `/pricing/hotel-prices/${new URL(next, "http://localhost").search}`,
        );
        results.push(...page.results);
        next = page.next;
      }
      return results;
    },
  });
  const plan = useQuery({
    queryKey: ["trip-accommodation-plan", trip],
    enabled: Boolean(trip),
    queryFn: () =>
      apiRequest<AccommodationPlan>(`/trips/${trip}/accommodation-plan/`),
  });
  if (!trip) return null;
  return (
    <details className="rounded-lg border p-3 sm:col-span-2">
      <summary className="cursor-pointer font-medium text-cyan-800">
        {t("Browse occupancy packages", "عرض باقات الإشغال")}
      </summary>
      <div className="mt-3 space-y-2 text-sm">
        {packages.data
          ?.filter((pkg) => pkg.is_published)
          .map((pkg) => {
            const adultPrice = prices.data?.find(
              (price) => price.id === pkg.adult_price,
            );
            const rooms = adultPrice
              ? (plan.data?.stops.flatMap((stop) =>
                  stop.hotels
                    .filter((h) => h.id === adultPrice.trip_hotel)
                    .flatMap((h) =>
                      h.rooms.filter(
                        (r) => r.room_type === adultPrice.room_type,
                      ),
                    ),
                ) ?? [])
              : [];
            const free = rooms.reduce(
              (n, room) =>
                n + Math.max(0, room.capacity - room.assignments.length),
              0,
            );
            return (
              <div key={pkg.id} className="rounded bg-slate-50 p-3">
                <p className="font-medium">{pkg.name}</p>
                {adultPrice && (
                  <p className="text-xs text-slate-500">
                    {adultPrice.hotel_name} · {adultPrice.room_type_name} ·{" "}
                    {free} {t("available beds", "أسرّة متاحة")}
                  </p>
                )}
                {pkg.calculated && (
                  <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {Object.entries(pkg.calculated.unit_prices).map(
                      ([key, value]) => (
                        <p key={key}>
                          <span className="block text-xs text-slate-500">
                            {key === "child_bed"
                              ? t("Child with bed", "طفل بسرير")
                              : key === "child_no_bed"
                                ? t("Child without bed", "طفل بدون سرير")
                                : key === "infant"
                                  ? t("Infant", "رضيع")
                                  : t("Adult", "بالغ")}
                          </span>
                          <b>
                            {Number(value).toLocaleString("fr-DZ")}{" "}
                            {pkg.calculated?.currency}
                          </b>
                        </p>
                      ),
                    )}
                  </div>
                )}
              </div>
            );
          })}
        {!packages.isPending && !packages.data?.length && (
          <p>
            {t(
              "No published occupancy packages configured yet.",
              "لا توجد باقات إشغال منشورة بعد.",
            )}
          </p>
        )}
        <p className="text-xs text-slate-500">
          {t(
            "These are estimates. Review rooms, extras and discounts with the client before confirmation.",
            "هذه أسعار استرشادية. راجع الغرف والإضافات والتخفيضات مع العميل قبل التأكيد.",
          )}
        </p>
        <MutationMessage error={packages.error || prices.error || plan.error} />
      </div>
    </details>
  );
}
