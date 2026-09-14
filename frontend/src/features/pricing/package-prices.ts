import { apiRequest } from "@/lib/api/client";
import type { Paginated } from "@/features/reference/types";
import type { HotelPriceRecord } from "./types";

export async function packagePrices(trip: string) {
  const path = "/pricing/hotel-prices/";
  const first = await apiRequest<Paginated<HotelPriceRecord>>(`${path}?trip=${trip}&scope=TRIP_PACKAGE`);
  const results = [...first.results];
  let next = first.next;
  while (next) {
    const page = await apiRequest<Paginated<HotelPriceRecord>>(`${path}${new URL(next, "http://localhost").search}`);
    results.push(...page.results);
    next = page.next;
  }
  return { ...first, next: null, results: results.filter(price => price.passenger_category_code.toUpperCase() === "ADT" && price.price_kind === "STANDARD") };
}
