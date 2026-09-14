# ADR 0003: JWT authentication with secure cookies

- Status: Accepted
- Date: 2026-08-22

## Decision

Use short-lived JWT access tokens and rotating refresh tokens. Both are stored in HTTP-only,
secure cookies in production. Refresh tokens are blacklisted after rotation or logout, and
cookie-authenticated unsafe requests require CSRF validation.

## Consequences

Frontend JavaScript cannot read bearer tokens. Browser requests must include credentials and a
CSRF header for unsafe methods. HTTPS is mandatory in production.
