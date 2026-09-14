# ADR 0004: Reference data ownership

- Status: Accepted
- Date: 2026-08-22

## Decision

Countries, cities, and currencies are global reference records. Passenger categories and payment
methods combine protected system defaults with agency-owned extensions. Currency enablement and
the accounting-currency choice belong to each agency.

## Consequences

Tenant APIs may read shared records but cannot modify protected system defaults. Custom records
are filtered by agency. Database constraints enforce one enabled accounting currency per agency.
