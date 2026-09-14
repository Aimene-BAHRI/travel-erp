# Finance

Financial implementation starts only after money, currency, rounding, exchange-rate, booking
snapshot, refund, and reversal decisions are approved. Monetary values use decimal arithmetic,
and historical records preserve their original currency and transaction-time exchange rate.

Phase 2 establishes DZD, EUR, SAR, and USD as global currencies. Each agency has explicit enabled
currencies and exactly one enabled accounting currency. Existing and newly bootstrapped Algerian
agencies default to DZD for accounting. Changing this configuration does not rewrite historical
transactions.

Phase 6 catalog and quote values continue to use decimal arithmetic. Conversion rounds half-up to
the configured currency precision. Each quote line freezes its source amount and exchange rate;
the quote separately records its quote-to-accounting rate. Equal currencies require a rate of one.
Issued totals live in an immutable, SHA-256-fingerprinted commercial snapshot.

Phase 8 uses an immutable booking ledger. Payments, refunds, and reversals preserve original
amount and currency, the transaction-to-booking exchange rate, converted booking value, and
accounting value. Reversals append an opposite entry rather than editing history. Net paid and
remaining balances are calculated from signed ledger entries and are never booking fields.

## Agency and trip cash flow

The finance API exposes `cash-entries` for money that is not a customer booking payment or a
supplier payment. Entries are immutable, require a positive amount and payment method, and may be
linked to a trip. Use `POST /api/v1/finance/cash-entries/post/` for an agency or trip inflow/outflow.

`GET /api/v1/finance/cash-entries/report/` returns all booking receipts, supplier payments, and
manual cash entries grouped by currency. Pass `?trip=<trip-id>` to return only that trip's cash flow.
Each currency includes `inflow`, `outflow`, and `net`; the entry list supports reconciliation.
