# API conventions

- API prefix: `/api/v1/`
- JSON is the default representation.
- Authentication is required by default; public endpoints opt out explicitly.
- Collection endpoints use page-number pagination initially.
- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/docs/`
- Dates use ISO 8601 and timestamps are transmitted with an explicit timezone.
- Monetary values will be serialized as decimal strings, never floating-point numbers.

## Phase 1 endpoints

- `GET /api/v1/auth/csrf/`
- `POST /api/v1/auth/login/`
- `POST /api/v1/auth/refresh/`
- `POST /api/v1/auth/logout/`
- `GET /api/v1/auth/me/`
- `GET|PATCH /api/v1/organizations/agency/`
- `/api/v1/organizations/branches/`
- `/api/v1/accounts/users/`
- `/api/v1/accounts/roles/`
- `/api/v1/accounts/permissions/`
- `/api/v1/reference/countries/`
- `/api/v1/reference/cities/`
- `/api/v1/reference/currencies/`
- `/api/v1/reference/agency-currencies/`
- `/api/v1/reference/passenger-categories/`
- `/api/v1/reference/payment-methods/`

Changing the accounting currency uses the transactional command endpoint:

- `POST /api/v1/reference/agency-currencies/{id}/make-accounting/`
- `/api/v1/customers/`
- `/api/v1/travelers/`
- `/api/v1/travelers/passports/`
- `/api/v1/documents/`
- `GET /api/v1/documents/{id}/download/`
- `/api/v1/catalog/suppliers/`
- `/api/v1/catalog/airlines/`
- `/api/v1/catalog/hotels/`
- `/api/v1/catalog/room-types/`
- `/api/v1/catalog/rooms/`

Hotels, suppliers, room types, and rooms are tenant-scoped. Airlines are authenticated shared
reference data and are read-only through tenant APIs. Rooms support `hotel` and `room_type` query
filters.

## Phase 5 trip endpoints

- `/api/v1/trips/`
- `/api/v1/trips/stops/`
- `/api/v1/trips/hotels/`
- `/api/v1/trips/flights/`
- `POST /api/v1/trips/{id}/transition/`
- `POST /api/v1/trips/{id}/reorder-stops/`

Trip child collections accept a `trip` query parameter. Hotels also accept `stop`. Lifecycle and
reordering operations are transactional command endpoints rather than arbitrary field updates.

## Phase 6 pricing endpoints

- `/api/v1/pricing/promotions/`
- `/api/v1/pricing/hotel-prices/`
- `/api/v1/pricing/flight-prices/`
- `/api/v1/pricing/quotes/`
- `POST /api/v1/pricing/quotes/{id}/add-hotel-price/`
- `POST /api/v1/pricing/quotes/{id}/add-flight-price/`
- `DELETE /api/v1/pricing/quotes/{id}/lines/{line_id}/`
- `POST /api/v1/pricing/quotes/{id}/issue/`
- `POST /api/v1/pricing/quotes/{id}/transition/`

Issue is atomic: it locks the draft and lines, calculates currency-aware totals, creates the
commercial snapshot, and changes status only if every step succeeds.

## Phase 7 booking endpoints

- `GET /api/v1/bookings/`
- `GET /api/v1/bookings/{id}/`
- `POST /api/v1/bookings/from-quote/`
- `POST /api/v1/bookings/{id}/travelers/`
- `DELETE /api/v1/bookings/{id}/travelers/{link_id}/`
- `POST /api/v1/bookings/{id}/transition/`

Quote conversion is atomic and only accepts an accepted, snapshotted quote that has not already
been converted. Booking collections accept `trip`, `customer`, and `status` filters. Physical room
assignment is deliberately absent from these endpoints and belongs to the rooming phase.

## Phase 8 finance endpoints

- `/api/v1/finance/exchange-rates/`
- `/api/v1/finance/transactions/`
- `POST /api/v1/finance/transactions/payments/`
- `POST /api/v1/finance/transactions/refunds/`
- `POST /api/v1/finance/transactions/{id}/reverse/`
- `GET /api/v1/finance/transactions/{id}/receipt/`
- `GET /api/v1/finance/transactions/booking-summary/?booking={id}`

Transactions cannot be edited or deleted. A correction creates a reversal entry. Booking summaries
derive net paid and remaining values from the complete signed ledger.

## Phase 9 partner endpoints

- `/api/v1/partners/`
- `/api/v1/partners/allocations/`
- `POST /api/v1/partners/allocations/{id}/use/`
- `/api/v1/partners/commissions/`
- `POST /api/v1/partners/commissions/{id}/transition/`
- `POST /api/v1/partners/commissions/{id}/pay/`
- `/api/v1/partners/commission-payments/`
- `POST /api/v1/partners/commission-payments/{id}/reverse/`

Document uploads use multipart form data with `owner_type`, `owner_id`, `category`, `title`, and
`file`. The API returns an authorized download endpoint and never returns the underlying storage
path or a public media URL.

JWT access and refresh tokens are stored in HTTP-only cookies. Cookie-authenticated unsafe
requests require the Django CSRF cookie and `X-CSRFToken` header.
