# ADR 0011: Partner allocations and separate commission ledger

## Status

Accepted in Phase 9.

## Decision

Partner allocations and commissions are separate aggregates. Allocation remaining quantities are
derived from booking usage. Commission balances are derived from immutable payment and reversal
entries, independently of customer payments.

## Consequences

- Package, ticket, and room quotas cannot be overspent.
- Commission corrections retain history through reversals.
- Partners remain distinct from customers and suppliers.
