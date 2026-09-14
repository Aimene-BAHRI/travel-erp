# Decision register

Architecture Decision Records in this directory document durable technical and business choices.

## Accepted

- ADR 0001: Modular monolith
- ADR 0002: Backend-enforced tenant isolation
- ADR 0003: JWT authentication with secure cookies
- ADR 0004: Reference data ownership
- ADR 0005: Typed document ownership
- ADR 0006: Catalog ownership and room separation
- ADR 0007: Trip aggregate and lifecycle
- ADR 0008: Immutable commercial quote snapshots
- ADR 0009: Booking from accepted quote
- ADR 0010: Immutable financial ledger
- ADR 0011: Partner allocations and separate commission ledger

## Resolved for Phase 1

- Configurable agency roles with protected system roles where shared defaults are required
- Agency-neutral platform administrators outside ordinary tenant APIs
- Rotating JWT cookies with CSRF enforcement and refresh-token revocation
- Permanent audit retention with sensitive-value redaction

Unresolved decisions must not be silently encoded as business rules.
