export interface DashboardData {
  operational: Array<{ trip: string; name: string; readiness: import("@/features/trips/operational-summary").ReadinessReport }>;
  counts: {
    open_trips: number;
    booking_requests: number;
    confirmed_bookings: number;
    payment_entries: number;
  };
  upcoming_trips: Array<{
    id: string;
    code: string;
    name: string;
    departure_date: string;
    status: string;
  }>;
  recent_bookings: Array<{
    id: string;
    code: string;
    customer_name: string;
    trip_name: string;
    status: string;
    created_at: string;
  }>;
}
