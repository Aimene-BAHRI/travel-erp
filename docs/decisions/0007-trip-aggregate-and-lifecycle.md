# ADR 0007: Trip aggregate and lifecycle

- Status: Accepted
- Date: 2026-08-22

## Decision

Represent every departure as its own `Trip`. Stops, selected hotels, flights, and trip documents
are children of that trip. Status changes use an explicit transactional state machine. Nights are
derived from stop dates and not persisted.

## Consequences

Opening a trip requires a valid itinerary. Date and ordering invariants are enforced centrally.
Hotel pricing and seasonal round-trip flight pricing remain separate Phase 6 commercial records
and do not contaminate operational flight segments.
