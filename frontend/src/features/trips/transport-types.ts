export type TransportRecord = {
  id: string;
  trip: string;
  trip_code: string;
  trip_name: string;
  passenger_count: number;
  mode: "BUS" | "PRIVATE_CAR" | "TRAIN" | "FERRY" | "OTHER";
  mode_display: string;
  supplier: string | null;
  supplier_name: string | null;
  origin_city: string;
  origin_city_name: string;
  destination_city: string;
  destination_city_name: string;
  departure_at: string;
  arrival_at: string;
  reference: string;
  vehicle_details: string;
  vehicle_number: string;
  notes: string;
  order: number;
};

export type TransportOverview = {
  counts: {
    today: number;
    urgent: number;
    week: number;
    month: number;
    total: number;
  };
  results: TransportRecord[];
};
