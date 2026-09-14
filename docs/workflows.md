# Workflows

Workflow state machines will be documented before their corresponding implementation phase.
Booking, trip, payment, commission, allocation, and rooming transitions must be explicit,
transactional where needed, authorized by the backend, and auditable.

## Passport lifecycle

Creating or promoting a passport to `CURRENT` locks the traveler's passport records, changes the
previous current passport to `REPLACED`, and saves the new current record in one transaction.
Expired and replaced records remain available as history.

## Document lifecycle

Uploads are validated for size and MIME type, hashed with SHA-256, stored under an agency-scoped
path, linked through an explicit owner model, and audited. Downloads require an authenticated,
tenant- and branch-scoped API request and are also audited.

## Trip lifecycle

```text
DRAFT → OPEN → CLOSED → DEPARTED → COMPLETED
   └──────┴──────┘
       CANCELLED
```

`CLOSED` may return to `OPEN`. A trip can only open after it has a contiguous, non-overlapping
itinerary beginning at order 1. Departed trips cannot be cancelled, and completed/cancelled trips
are terminal. All lifecycle changes are locked, validated, and audited by the backend.

## Itinerary rules

- Stop dates must remain within the trip departure/return dates.
- Stop departure cannot precede arrival.
- Ordered stops cannot overlap.
- Stop order is contiguous and begins at 1.
- A selected hotel must belong to the trip agency and the stop city.
- Flight arrival must be after departure and origin/destination cities must differ.
# Commercial booking workflow

1. Build a draft quote from hotel and round-trip flight catalog prices.
2. Issue it to freeze a commercial snapshot.
3. Mark the issued quote accepted.
4. Convert the accepted quote once into a confirmed booking.
5. Link reusable traveler records and record passenger category and bed requirement.
6. Complete the booking after traveler assignment, or cancel it with a mandatory reason.

The customer is the buyer and does not automatically become a traveler. Sold accommodation is a
room-type selection, not a physical-room assignment. Quote and booking snapshots remain unchanged
when source catalog data changes.
