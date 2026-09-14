# ADR 0010: Immutable booking financial ledger

## Status

Accepted in Phase 8.

## Decision

Payments, refunds, and reversals are immutable ledger entries. Every entry preserves original,
booking-currency, and accounting-currency values with the historical rates used. Corrections append
a full reversal; they never update or delete the original entry.

## Consequences

- Paid and remaining balances are calculated, not stored on bookings.
- Historical reports never depend on a current exchange rate.
- Overpayments and refunds exceeding net paid are rejected transactionally.
