# ADR 0005: Typed document ownership

- Status: Accepted
- Date: 2026-08-22

## Decision

Store common file metadata once in `Document`, but associate documents through explicit relational
models such as `TravelerDocument` and `PassportDocument`. Future booking and trip domains will add
their own typed association models.

## Consequences

Owner relationships retain foreign-key integrity and tenant validation. Adding a new owner type
requires a deliberate migration and API change. Storage paths are private implementation details;
all downloads pass through authorized API endpoints.
