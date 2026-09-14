# Domain model

The detailed model will evolve through approved phases. Initial bounded contexts are:

- Organizations and access control
- Reference data
- Customers and travelers
- Documents
- Travel catalog
- Trips and pricing
- Partners and allocations
- Bookings
- Payments and commissions
- Rooming
- Audit

No transactional domain models are introduced in Phase 0.

## Phase 2 reference data

- `Country` has a unique two-character code and a simple name.
- `City` belongs to one country and is unique by country and name.
- `Currency` is global ISO-style reference data.
- `AgencyCurrency` enables currencies per agency and identifies exactly one accounting currency.
- `PassengerCategory` provides protected system defaults plus tenant-owned extensions.
- `PaymentMethod` provides protected system defaults plus tenant-owned extensions.

## Phase 3 customer and traveler data

- `Customer` is the booking contact and may be an individual or company. It is never a traveler
  implicitly.
- `Traveler` is a permanent reusable agency record containing contact and profile information.
- `Passport` contains legal travel identity. Passport numbers are unique per agency, and only one
  passport can be current for a traveler.
- Creating a new current passport atomically marks the previous current passport as replaced.
- `Document` stores protected file metadata and storage references.
- `TravelerDocument` and `PassportDocument` provide explicit, database-backed ownership instead
  of an unconstrained generic foreign key.

## Phase 4 travel catalog

- `Supplier` is an agency-owned commercial counterpart and is not an airline.
- `Airline` is shared reference data identified by optional IATA and ICAO codes.
- `Hotel` belongs to one agency and one city. The same real-world hotel may be represented
  independently by different agencies.
- `RoomType` is an agency-configurable commercial category such as Double or Triple.
- `Room` is a physical hotel room with a hotel-specific number, commercial room type, standard
  bed count, and extra-bed limit.

The room's maximum bed capacity is `standard_beds + max_extra_beds`; adding an extra bed never
changes its `RoomType`.

## Phase 5 trips

- `Trip` represents one departure and belongs to an agency and managing branch.
- `TripStop` is an ordered city stay bounded by the trip dates. `nights` is derived from arrival
  and departure dates rather than stored.
- `TripHotel` selects one or more agency hotels for a specific stop; at most one is primary.
- `TripFlight` is an ordered airline segment with cities, airport codes, and timezone-aware
  departure/arrival timestamps.
- `TripDocument` provides a typed association to private documents.

Flights reference `Airline` directly and have no supplier relationship.

## Phase 6 pricing and quotes

- `TripHotelPrice` prices a selected trip hotel by room type, passenger category, bed basis,
  currency, and either standard or promotional price kind.
- `Promotion` is a trip-specific sales window. Promotional hotel prices must reference one.
- `SeasonalFlightPrice` is a complete round-trip fare for one passenger category and sales window.
- `Quote` is a branch-owned proposal with explicit quote and accounting currencies and rates.
- `QuoteLine` captures its source price, exchange rate, labels, and calculated values at selection.
- Issuing creates exactly one immutable `QuoteSnapshot` with all commercial values and a SHA-256
  fingerprint. Issued quote lines are immutable too.

Quote lifecycle: `DRAFT -> ISSUED -> ACCEPTED | EXPIRED | CANCELLED`. A draft may be cancelled.

## Phase 7 bookings

- `Booking` is created exactly once from an accepted quote and keeps exactly one customer.
- The customer and booked travelers remain separate concepts; a customer need not travel.
- `BookingTraveler` links reusable traveler records with a passenger category and explicit bed
  requirement.
- `BookingAccommodation` freezes the sold trip hotel, room type, passenger category, bed basis,
  quantity, and price. It never points to a physical room.
- `BookingFlight` selects the trip's scheduled flight segments for the booking.
- `BookingSnapshot` embeds the accepted quote snapshot and frozen commercial selection under a
  second SHA-256 fingerprint.

Bookings start confirmed and may become completed or cancelled. Cancellation requires a reason;
completion requires at least one traveler. Commercial fields and sold accommodation are immutable.

## Phase 9 partners and commissions

- `Partner` is an agency-owned distributor or referrer and remains separate from customers.
- `PartnerAllocation` grants package, ticket, or room quantities for one trip. Remaining quantity
  is calculated from immutable booking usage records.
- `PartnerCommission` belongs to one partner and booking and follows accrued, approved, or
  cancelled states.
- `CommissionPayment` preserves original currency and rate. Corrections append immutable reversal
  entries; paid and remaining commission values are calculated.
