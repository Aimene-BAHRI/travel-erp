# ADR 0006: Catalog ownership and room separation

- Status: Accepted
- Date: 2026-08-22

## Decision

Suppliers, hotels, room types, and rooms belong to one agency. Airlines are global reference data
and are not suppliers. Room types are commercial categories reusable across an agency's hotels;
rooms are physical resources belonging to one hotel.

## Consequences

Cross-agency hotel and room-type relationships are rejected. Agencies may configure their own
room categories without hardcoded enums. Physical capacity and extra beds can vary per room
without changing the category sold to a customer.
