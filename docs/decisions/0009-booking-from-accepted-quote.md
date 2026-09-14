# ADR 0009: Create bookings from accepted quotes

## Status

Accepted in Phase 7.

## Decision

A booking is created exactly once from an accepted, snapshotted quote. Conversion copies totals,
sold accommodation, and scheduled trip flights in one database transaction and creates a booking
snapshot containing the source quote snapshot.

Customers and travelers stay separate. Booking accommodation refers to the commercial room type,
not a physical room. Physical room assignment remains a later operational process.

## Consequences

- A booking cannot silently diverge from the offer accepted by the customer.
- Traveler records remain reusable across bookings without duplicating identity data.
- Payments can use the immutable booking total in the next phase without storing paid or remaining
  balance fields on the booking.
