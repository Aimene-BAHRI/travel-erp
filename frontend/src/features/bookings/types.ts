export type BookingStatus = "DRAFT" | "CONFIRMED" | "CANCELLED" | "COMPLETED";

export interface BookingDiscountRecord {
  id: string;
  kind: "AMOUNT" | "PERCENT";
  value: string;
  amount: string;
  reason: string;
}
export interface BookingChargeRecord {
  id: string;
  kind: string;
  description: string;
  source_price: string | null;
  base_amount: string;
  discount_amount: string;
  final_amount: string;
  currency: string;
  currency_code: string;
  discounts: BookingDiscountRecord[];
}

export interface BookingTravelerRecord {
  id: string;
  traveler: string;
  traveler_name: string;
  first_name: string;
  last_name: string;
  passenger_category: string;
  passenger_category_name: string;
  derived_passenger_category: "INF" | "CHD" | "ADT" | null;
  bed_requirement: "REQUIRED" | "NOT_REQUIRED";
  seat_required: boolean | null;
  service_type: "PACK" | "VISA_ONLY" | "TICKET_ONLY" | "CUSTOM";
  included_stops: string[];
  birth_date: string | null;
  gender: "F" | "M" | "X";
  gender_display: string;
  age_on_return: number | null;
  passport_number: string | null;
  passport_id: string | null;
  passport_expiry_date: string | null;
  passport_validity_status:
    "VALID" | "MISSING" | "EXPIRED" | "LESS_THAN_SIX_MONTHS";
  passport_required_until: string;
  passport_is_valid: boolean;
  passport_details: null | {
    passport_number: string;
    first_name: string;
    middle_name: string;
    last_name: string;
    birth_date: string;
    gender: "F" | "M" | "X";
    nationality: string;
    issuing_country: string;
    birth_country: string;
    birth_place: string;
    issue_date: string;
    expiry_date: string;
    issue_place: string;
    mrz: string;
  };
  final_amount: string;
  is_customer_contact: boolean;
  room_assignments: Array<{
    id: string;
    room_group: string | null;
    hotel: string;
    city: string;
    room_type: string;
    label: string;
  }>;
  notes: string;
  charges: BookingChargeRecord[];
}

export interface BookingRoomGroupRecord {
  id: string;
  trip_hotel: string;
  hotel_name: string;
  city_name: string;
  room_type: string;
  room_type_name: string;
  label: string;
  capacity: number;
  notes: string;
  traveler_assignments: Array<{
    id: string;
    booking_traveler: string;
    traveler_name: string;
  }>;
}

export interface BookingAccommodationRecord {
  id: string;
  hotel_name: string;
  city_name: string;
  room_type_name: string;
  passenger_category_name: string;
  bed_basis: string;
  quantity: number;
  total_amount: string;
  currency_code: string;
}

export interface BookingFlightRecord {
  id: string;
  flight_number: string;
  direction: string;
  origin_airport_code: string;
  destination_airport_code: string;
  departure_at: string;
  arrival_at: string;
}

export interface BookingRecord {
  offer_revision: string | null;
  commercial_details: Partial<CommercialDetails>;
  partner: string | null;
  partner_name: string | null;
  id: string;
  code: string;
  agency_name: string;
  agency_logo: string | null;
  branch: string;
  branch_name: string;
  customer: string;
  trip: string;
  customer_name: string;
  customer_first_name: string;
  customer_last_name: string;
  customer_phone: string;
  customer_email: string;
  customer_address: string;
  trip_name: string;
  return_date: string;
  source_quote_code: string;
  currency_code: string;
  currency: string;
  total_amount: string;
  paid_amount: string;
  remaining_amount: string;
  accounting_currency_code: string;
  accounting_currency: string;
  accounting_exchange_rate: string;
  accounting_total_amount: string;
  status: BookingStatus;
  cancellation_reason: string;
  traveler_count: number;
  travelers: BookingTravelerRecord[];
  accommodations: BookingAccommodationRecord[];
  room_groups: BookingRoomGroupRecord[];
  flights: BookingFlightRecord[];
  snapshot: { sha256: string; created_at: string } | null;
  expected_travelers: number;
  capacity: { maximum: number | null; booked: number; remaining: number | null; available_for_booking: number | null; has_capacity: boolean };
  readiness: {
    structured: import("@/features/trips/operational-summary").ReadinessReport;
    payment_blockers: string[];
    completion: Array<{ id: string; issues: string[] }>;
    expected_travelers: number;
    remaining_travelers: number;
    validated_travelers: number;
    traveler_validation: Array<{ id: string; name: string; issues: string[] }>;
    contact_complete: boolean;
    traveler_count: number;
    missing_passports: number;
    invalid_passports: number;
    missing_rooms: number;
    missing_prices: number;
    price_category_mismatches: number;
    allocation_status: "NOT_REQUIRED" | "NOT_STARTED" | "PARTIAL" | "COMPLETE";
    required_room_assignments: number;
    completed_room_assignments: number;
    commercial_ready: boolean;
    operational_ready: boolean;
    is_ready: boolean;
  };
  created_at: string;
}

export type CommercialDetails = {
  source: 'WALK_IN' | 'SOCIAL_MEDIA' | 'PARTNER' | 'REFERRER' | 'OTHER';
  source_detail: string;
  extras: { service: 'TGV' | 'SPECIAL_BUS' | 'FOOD' | 'OTHER'; description: string; quantity: number; unit_price: string }[];
  payment_plan: 'FULL' | 'INSTALLMENTS';
  installments: { due_date: string; amount: string }[];
  notes: string;
};
