import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Quote, QuoteLine, QuoteSnapshot, SeasonalFlightPrice, TripHotelPrice


@dataclass(frozen=True)
class ResolvedTravelerPrice:
    amount: Decimal
    currency_id: str
    source_price_id: str | None
    base_amount: Decimal
    discount_amount: Decimal
    passenger_category: str
    bed_basis: str


def resolve_traveler_price(*, trip, trip_hotel=None, room_type=None, passenger_category, bed_requirement, scope="TRIP_PACKAGE"):
    """Resolve a new traveler price without changing any existing charge snapshot."""
    category = passenger_category.code.upper()
    if category == "INF":
        if trip.infant_price is None or trip.pricing_currency_id is None:
            raise ValidationError("This trip has no infant price configured.")
        return ResolvedTravelerPrice(
            amount=trip.infant_price,
            currency_id=trip.pricing_currency_id,
            source_price_id=None,
            base_amount=trip.infant_price,
            discount_amount=Decimal("0"),
            passenger_category=category,
            bed_basis="N_A",
        )
    if category == "CHD" and bed_requirement == "NOT_REQUIRED":
        if trip.child_without_bed_price is None or trip.pricing_currency_id is None:
            raise ValidationError("This trip has no child-without-bed price configured.")
        return ResolvedTravelerPrice(
            amount=trip.child_without_bed_price,
            currency_id=trip.pricing_currency_id,
            source_price_id=None,
            base_amount=trip.child_without_bed_price,
            discount_amount=Decimal("0"),
            passenger_category=category,
            bed_basis="WITHOUT_BED",
        )

    if trip_hotel is None or room_type is None:
        raise ValidationError("Select a hotel and room type for a bed-consuming traveler.")
    if trip_hotel.stop.trip_id != trip.pk:
        raise ValidationError("The selected hotel must belong to the selected trip.")
    if room_type.agency_id != trip.agency_id:
        raise ValidationError("Room type must belong to the trip agency.")
    if category == "ADT" and bed_requirement != "REQUIRED":
        raise ValidationError("Adult package pricing requires a bed.")
    adult = (
        TripHotelPrice.objects.select_related("currency", "passenger_category")
        .filter(
            trip_hotel=trip_hotel,
            scope=scope,
            room_type=room_type,
            passenger_category__code__iexact="adt",
            price_kind=TripHotelPrice.PriceKind.STANDARD,
            bed_basis=TripHotelPrice.BedBasis.STANDARD,
        )
        .first()
    )
    if adult is None:
        raise ValidationError("No adult price exists for the selected hotel and room type.")
    discount = Decimal("0")
    if category == "CHD":
        if trip.child_with_bed_discount is None:
            raise ValidationError("This trip has no child-with-bed discount configured.")
        discount = trip.child_with_bed_discount
    elif category != "ADT":
        raise ValidationError(f"Unsupported passenger category: {category}.")
    if discount < 0 or discount > adult.amount:
        raise ValidationError("Child discount must be between zero and the adult price.")
    if discount and trip.pricing_currency_id != adult.currency_id:
        raise ValidationError("Child discount and adult price must use the same currency.")
    amount = adult.amount - discount
    return ResolvedTravelerPrice(
        amount=amount,
        currency_id=adult.currency_id,
        source_price_id=str(adult.pk),
        base_amount=adult.amount,
        discount_amount=discount,
        passenger_category=category,
        bed_basis=TripHotelPrice.BedBasis.WITH_BED if category == "CHD" else TripHotelPrice.BedBasis.STANDARD,
    )

ALLOWED_QUOTE_TRANSITIONS = {
    Quote.Status.DRAFT: {Quote.Status.CANCELLED},
    Quote.Status.ISSUED: {
        Quote.Status.ACCEPTED,
        Quote.Status.EXPIRED,
        Quote.Status.CANCELLED,
    },
    Quote.Status.ACCEPTED: set(),
    Quote.Status.EXPIRED: set(),
    Quote.Status.CANCELLED: set(),
}


def quantize_money(amount, currency):
    quantum = Decimal(1).scaleb(-currency.decimal_places)
    return Decimal(amount).quantize(quantum, rounding=ROUND_HALF_UP)


def _validate_draft_source(*, quote, price, source_trip_id):
    if quote.status != Quote.Status.DRAFT:
        raise ValidationError("Only draft quotes can be changed.")
    if price.agency_id != quote.agency_id or source_trip_id != quote.trip_id:
        raise ValidationError("The price must belong to the quote's trip and agency.")


def _source_label(price):
    if isinstance(price, TripHotelPrice):
        return (
            f"{price.trip_hotel.hotel.name} / {price.room_type.name} / "
            f"{price.passenger_category.name} ({price.get_bed_basis_display()})"
        )
    return f"{price.fare_name} / {price.passenger_category.name} round trip"


def _source_payload(price):
    common = {
        "id": str(price.pk),
        "amount": str(price.amount),
        "currency": price.currency_id,
        "passenger_category": {
            "id": str(price.passenger_category_id),
            "code": price.passenger_category.code,
            "name": price.passenger_category.name,
        },
    }
    if isinstance(price, TripHotelPrice):
        return {
            **common,
            "type": "trip_hotel_price",
            "hotel": {
                "id": str(price.trip_hotel.hotel_id),
                "name": price.trip_hotel.hotel.name,
            },
            "room_type": {"id": str(price.room_type_id), "name": price.room_type.name},
            "bed_basis": price.bed_basis,
            "price_kind": price.price_kind,
            "promotion": (
                {"id": str(price.promotion_id), "code": price.promotion.code}
                if price.promotion_id
                else None
            ),
        }
    return {
        **common,
        "type": "seasonal_round_trip_flight_price",
        "fare_name": price.fare_name,
        "airline": (
            {"id": str(price.airline_id), "name": price.airline.name}
            if price.airline_id
            else None
        ),
        "sales_start_date": price.sales_start_date.isoformat(),
        "sales_end_date": price.sales_end_date.isoformat(),
    }


@transaction.atomic
def add_price_to_quote(*, quote_id, agency, price, quantity, exchange_rate):
    quote = Quote.objects.select_for_update().select_related("currency").get(
        pk=quote_id, agency=agency
    )
    source_trip_id = (
        price.trip_hotel.stop.trip_id if isinstance(price, TripHotelPrice) else price.trip_id
    )
    _validate_draft_source(quote=quote, price=price, source_trip_id=source_trip_id)
    if quantity < 1:
        raise ValidationError("Quantity must be at least 1.")
    exchange_rate = Decimal(exchange_rate)
    if exchange_rate <= 0:
        raise ValidationError("Exchange rate must be greater than 0.")
    if price.currency_id == quote.currency_id and exchange_rate != Decimal("1"):
        raise ValidationError("Same-currency exchange rate must equal 1.")

    unit_amount = quantize_money(price.amount * exchange_rate, quote.currency)
    line = QuoteLine(
        quote=quote,
        kind=(
            QuoteLine.Kind.HOTEL
            if isinstance(price, TripHotelPrice)
            else QuoteLine.Kind.FLIGHT
        ),
        hotel_price=price if isinstance(price, TripHotelPrice) else None,
        flight_price=price if isinstance(price, SeasonalFlightPrice) else None,
        description=_source_label(price),
        quantity=quantity,
        source_unit_amount=price.amount,
        source_currency=price.currency,
        exchange_rate=exchange_rate,
        unit_amount=unit_amount,
        total_amount=quantize_money(unit_amount * quantity, quote.currency),
        source_snapshot=_source_payload(price),
    )
    line.full_clean()
    line.save()
    return line


@transaction.atomic
def remove_quote_line(*, quote_id, line_id, agency):
    quote = Quote.objects.select_for_update().get(pk=quote_id, agency=agency)
    if quote.status != Quote.Status.DRAFT:
        raise ValidationError("Issued quote lines are immutable.")
    line = QuoteLine.objects.get(pk=line_id, quote=quote)
    line.delete()


def _snapshot_payload(quote, lines):
    return {
        "schema_version": 1,
        "quote": {
            "id": str(quote.pk),
            "code": quote.code,
            "agency": {"id": str(quote.agency_id), "name": quote.agency.name},
            "branch": {"id": str(quote.branch_id), "name": quote.branch.name},
            "customer": {"id": str(quote.customer_id), "name": quote.customer.display_name},
            "trip": {
                "id": str(quote.trip_id),
                "code": quote.trip.code,
                "name": quote.trip.name,
            },
            "currency": quote.currency_id,
            "accounting_currency": quote.accounting_currency_id,
            "accounting_exchange_rate": str(quote.accounting_exchange_rate),
            "valid_until": quote.valid_until.isoformat(),
            "notes": quote.notes,
        },
        "lines": [
            {
                "id": str(line.pk),
                "kind": line.kind,
                "description": line.description,
                "quantity": line.quantity,
                "source_unit_amount": str(line.source_unit_amount),
                "source_currency": line.source_currency_id,
                "exchange_rate": str(line.exchange_rate),
                "unit_amount": str(line.unit_amount),
                "total_amount": str(line.total_amount),
                "source": line.source_snapshot,
            }
            for line in lines
        ],
    }


@transaction.atomic
def issue_quote(*, quote_id, agency):
    quote = (
        Quote.objects.select_for_update()
        .select_related(
            "agency", "branch", "customer", "trip", "currency", "accounting_currency"
        )
        .get(pk=quote_id, agency=agency)
    )
    if quote.status != Quote.Status.DRAFT:
        raise ValidationError("Only draft quotes can be issued.")
    lines = list(QuoteLine.objects.select_for_update().filter(quote=quote))
    if not lines:
        raise ValidationError("A quote requires at least one line before issue.")

    quote_total = quantize_money(
        sum((line.total_amount for line in lines), Decimal(0)), quote.currency
    )
    accounting_total = quantize_money(
        quote_total * quote.accounting_exchange_rate, quote.accounting_currency
    )
    payload = _snapshot_payload(quote, lines)
    payload["totals"] = {
        "quote_total": str(quote_total),
        "quote_currency": quote.currency_id,
        "accounting_total": str(accounting_total),
        "accounting_currency": quote.accounting_currency_id,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    snapshot = QuoteSnapshot(
        quote=quote,
        payload=payload,
        sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        quote_total=quote_total,
        quote_currency=quote.currency_id,
        accounting_total=accounting_total,
        accounting_currency=quote.accounting_currency_id,
    )
    snapshot.full_clean()
    snapshot.save()
    quote.status = Quote.Status.ISSUED
    quote.issued_at = timezone.now()
    quote.save(update_fields=["status", "issued_at", "updated_at"])
    return quote


@transaction.atomic
def transition_quote(*, quote_id, agency, target_status):
    quote = Quote.objects.select_for_update().get(pk=quote_id, agency=agency)
    if target_status not in ALLOWED_QUOTE_TRANSITIONS[quote.status]:
        raise ValidationError(
            f"Quote cannot transition from {quote.status} to {target_status}."
        )
    quote.status = target_status
    fields = ["status", "updated_at"]
    if target_status == Quote.Status.ACCEPTED:
        quote.accepted_at = timezone.now()
        fields.append("accepted_at")
    quote.save(update_fields=fields)
    return quote
