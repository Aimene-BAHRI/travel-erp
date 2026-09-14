# ADR 0008: Immutable commercial quote snapshots

## Status

Accepted in Phase 6.

## Decision

Editable price catalogs and issued commercial facts are separate. Adding a price to a draft copies
its money values, exchange rate, and descriptive data into a quote line. Issuing atomically creates
a canonical JSON snapshot with totals and a SHA-256 fingerprint. The snapshot and issued lines are
immutable.

Seasonal flight prices represent complete round trips. Hotel prices use a normalized model with
passenger category, room type, bed basis, and standard or promotional dimensions.

## Consequences

- Later catalog, promotion, or exchange-rate changes cannot rewrite an issued offer.
- Auditors can read the exact payload without joining mutable catalog tables.
- Corrections require a new quote rather than editing an issued one.
