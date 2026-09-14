# ADR 0002: Tenant isolation is enforced by the backend

- Status: Accepted
- Date: 2026-08-22

## Decision

Agency scope is derived from the authenticated user. Clients may request an allowed branch
scope but may never select an arbitrary agency. Query filtering, object authorization,
same-agency relationship validation, and tenant-isolation tests are mandatory.

## Consequences

Tenant rules must be implemented in shared backend conventions before ordinary business
features are added. Frontend visibility is a usability aid and not a security boundary.

