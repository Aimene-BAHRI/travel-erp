# ADR 0001: Modular monolith

- Status: Accepted
- Date: 2026-08-22

## Decision

Build the ERP as a modular monolith: one Django API, one Next.js frontend, and one PostgreSQL
database. Organize backend capabilities by business domain and keep cross-domain dependencies
explicit.

## Consequences

Multi-domain workflows can use database transactions, deployment remains simple, and domain
boundaries can be refined without introducing premature distributed-system complexity.

