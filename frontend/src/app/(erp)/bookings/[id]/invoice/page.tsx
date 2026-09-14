"use client";

import { useParams } from "next/navigation";

import { AuthGate } from "@/features/auth/auth-gate";
import { BookingInvoicePage } from "@/features/bookings/booking-invoice-page";

export default function InvoicePage() {
  const params = useParams<{ id: string }>();
  return (
    <AuthGate>{() => <BookingInvoicePage bookingId={params.id} />}</AuthGate>
  );
}
