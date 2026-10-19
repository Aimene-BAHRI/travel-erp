import type { TripFlightRecord, TripStopRecord } from "./types";

export const nextOrder = (rows: { order: number }[]) => Math.max(0, ...rows.map(row => row.order)) + 1;

export function flightDefaults(trip: { departure_date: string; return_date: string }, stops: TripStopRecord[], flights: TripFlightRecord[], direction?: string) {
  const ordered = [...stops].sort((a, b) => a.order - b.order);
  const outbound = flights.find(flight => flight.direction === "OUTBOUND");
  const route = direction ?? (outbound && !flights.some(flight => flight.direction === "RETURN") ? "RETURN" : "OUTBOUND");
  const date = route === "RETURN" ? trip.return_date : trip.departure_date;
  // Reuse only airport/city pairs actually recorded on this trip.
  const airport = (city: string) => {
    const codes = new Set(flights.flatMap(f => [f.origin_city === city ? f.origin_airport_code : "", f.destination_city === city ? f.destination_airport_code : ""]).filter(Boolean));
    return codes.size === 1 ? [...codes][0] : "";
  };
  const origin = route === "RETURN" ? ordered.at(-1)?.city ?? outbound?.destination_city ?? "" : outbound?.origin_city ?? "";
  const destination = route === "RETURN" ? outbound?.origin_city ?? "" : ordered[0]?.city ?? "";
  return { direction: route, airline: outbound?.airline ?? "", origin_city: origin, destination_city: destination, origin_airport_code: airport(origin), destination_airport_code: airport(destination), departure_at: `${date}T`, arrival_at: `${date}T`, order: nextOrder(flights) };
}
