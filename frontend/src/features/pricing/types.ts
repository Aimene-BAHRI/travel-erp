export type QuoteStatus = "DRAFT" | "ISSUED" | "ACCEPTED" | "EXPIRED" | "CANCELLED";

export interface QuoteLineRecord {
  id: string;
  kind: "HOTEL" | "FLIGHT";
  description: string;
  quantity: number;
  source_unit_amount: string;
  source_currency_code: string;
  exchange_rate: string;
  total_amount: string;
}

export interface QuoteSnapshotRecord {
  sha256: string;
  quote_total: string;
  quote_currency: string;
  accounting_total: string;
  accounting_currency: string;
  created_at: string;
}

export interface QuoteRecord {
  id: string;
  code: string;
  branch: string;
  branch_name: string;
  customer: string;
  customer_name: string;
  trip: string;
  trip_name: string;
  currency: string;
  accounting_currency: string;
  accounting_exchange_rate: string;
  status: QuoteStatus;
  valid_until: string;
  notes: string;
  total: string;
  lines: QuoteLineRecord[];
  snapshot: QuoteSnapshotRecord | null;
}

export interface HotelPriceRecord {
  passenger_category_code: string;
  scope: "HOTEL_STAY" | "TRIP_PACKAGE";
  id: string;
  trip_hotel: string;
  hotel_name: string;
  room_type_name: string;
  room_type: string;
  passenger_category_name: string;
  passenger_category: string;
  bed_basis: string;
  promotion_code?: string;
  price_kind: "STANDARD" | "PROMOTIONAL";
  promotion: string | null;
  amount: string;
  currency_code: string;
  currency: string;
  notes: string;
}

export interface FlightPriceRecord {
  id: string;
  trip: string;
  fare_name: string;
  airline: string | null;
  passenger_category_name: string;
  passenger_category: string;
  sales_start_date: string;
  sales_end_date: string;
  amount: string;
  currency_code: string;
  currency: string;
  source_reference: string;
  notes: string;
  is_active: boolean;
}

export interface PromotionRecord {
  id: string;
  code: string;
  name: string;
  sales_start_date: string;
  sales_end_date: string;
  description: string;
  is_active: boolean;
}

export interface CostComponentRecord {
  id: string;
  trip: string;
  code: string;
  label: string;
  basis: "PER_TRAVELER" | "MAKKAH_ROOM" | "MADINAH_ROOM";
  applies_to: "ALL" | "ADULT" | "CHILD_BED" | "CHILD_NO_BED" | "INFANT";
  source_amount: string;
  source_currency: string;
  currency_code: string;
  exchange_rate: string;
  quantity: string;
  converted_amount: string;
  is_active: boolean;
}

export interface OccupancyPackageRecord {
  adult_price: string | null;
  id: string;
  trip: string;
  code: string;
  name: string;
  makkah_occupancy: number;
  madinah_occupancy: number;
  margin_adult: string;
  margin_child_bed: string;
  margin_child_no_bed: string;
  margin_infant: string;
  override_adult: string | null;
  override_child_bed: string | null;
  override_child_no_bed: string | null;
  override_infant: string | null;
  rounding_increment: number;
  is_published: boolean;
  calculated: null | {
    currency: string;
    unit_prices: Record<"adult" | "child_bed" | "child_no_bed" | "infant", string>;
  };
}
