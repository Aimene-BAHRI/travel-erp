export type TripRecord = {
  id: string;
  agency_name: string;
  agency_logo: string | null;
  code: string;
  name: string;
  branch: string;
  branch_name: string;
  departure_date: string;
  return_date: string;
  pricing_currency: string | null;
  child_with_bed_discount: string | number | null;
  child_without_bed_price: string | number | null;
  infant_price: string | number | null;
  booking_open_date: string | null;
  booking_close_date: string | null;
  max_travelers: number | null;
  booked_places: number;
  remaining_places: number | null;
  status: "DRAFT" | "OPEN" | "CLOSED" | "DEPARTED" | "COMPLETED" | "CANCELLED";
  closing_status: "NOT_DUE" | "PENDING_CLOSING" | "READY_TO_CLOSE" | "CLOSED";
  closing_started_at: string | null;
  closed_at: string | null;
  closed_by: string | null;
  description: string;
  notes: string;
  stop_count: number;
  hotel_count: number;
  flight_count: number;
};

export type TripClosingItemRecord = {
  id: string;
  key: string;
  label: string;
  state: "PENDING" | "COMPLETED" | "NOT_REQUIRED";
  notes: string;
  assigned_to: string | null;
  due_date: string | null;
  completed_by_name: string;
  completed_at: string | null;
  updated_at: string;
};

export type TripClosingSummary = {
  status: TripRecord["closing_status"];
  can_start: boolean;
  completed_count: number;
  total_count: number;
  is_ready: boolean;
  closed_at: string | null;
  closed_by: string;
  items: TripClosingItemRecord[];
  financials: {
    accounting_currency: string;
    revenue: string;
    collected: string;
    customer_outstanding: string;
    expenses_by_currency: Record<string, string>;
    supplier_outstanding_by_currency: Record<string, string>;
    profit_loss: string | null;
    profit_loss_note: string;
    document_count: number;
  };
};

export type TripStopRecord = {
  id: string;
  trip: string;
  city: string;
  city_name: string;
  country_code: string;
  arrival_date: string;
  departure_date: string;
  nights: number;
  order: number;
  notes: string;
};

export type TripHotelRecord = {
  id: string;
  stop: string;
  hotel: string;
  hotel_name: string;
  city_name: string;
  is_primary: boolean;
  notes: string;
};

export type TripFlightRecord = {
  id: string;
  trip: string;
  airline: string;
  airline_name: string;
  direction: string;
  flight_number: string;
  origin_city_name: string;
  origin_city: string;
  destination_city_name: string;
  destination_city: string;
  origin_airport_code: string;
  destination_airport_code: string;
  departure_at: string;
  arrival_at: string;
  order: number;
  booking_class: string;
  notes: string;
};

export type TripTransportRecord = {
  id: string;
  trip: string;
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
  order: number;
  notes: string;
};

export type TripRoomAssignmentRecord = {
  id: string;
  stop: string;
  room: string;
  booking_traveler: string;
  traveler_name: string;
  booking_code: string;
  gender: "M" | "F" | "X";
  traveler_photo_url: string | null;
  bed_number: number;
};

export type TripAllocationRoomRecord = {
  id: string;
  trip_hotel: string;
  hotel_name: string;
  city_name: string;
  stop: string;
  room_type: string;
  room_type_name: string;
  label: string;
  actual_room_number: string;
  standard_beds: number;
  extra_beds: number;
  capacity: number;
  occupancy_policy: "ANY" | "MALE_ONLY" | "FEMALE_ONLY" | "FAMILY";
  notes: string;
  assignments: TripRoomAssignmentRecord[];
};

export type AccommodationTravelerRecord = {
  required_stops: string[];
  eligible_for_room: boolean;
  id: string;
  name: string;
  photo_url: string | null;
  booking_code: string;
  group_name: string;
  gender: "M" | "F" | "X";
  passenger_category: string;
  preferences: Array<{ stop: string; hotel: string; room_type: string }>;
  assignments: TripRoomAssignmentRecord[];
};

export type AccommodationPlan = {
  trip: string;
  travelers: AccommodationTravelerRecord[];
  stops: Array<{
    id: string;
    city_name: string;
    arrival_date: string;
    departure_date: string;
    order: number;
    assigned_count: number;
    unassigned_count: number;
    hotels: Array<{
      id: string;
      hotel_name: string;
      is_primary: boolean;
      rooms: TripAllocationRoomRecord[];
    }>;
  }>;
  summary: {
    traveler_count: number;
    required_stop_count: number;
    assignment_count: number;
    required_assignment_count: number;
    is_complete: boolean;
  };
};
