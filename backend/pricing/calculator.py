from decimal import ROUND_CEILING, Decimal

from django.core.exceptions import ValidationError

from pricing.models import TripCostComponent, TripOccupancyPackage
from reference.models import AgencyCurrency

CATEGORIES = ("adult", "child_bed", "child_no_bed", "infant")
APPLIES_TO = {
    "adult": TripCostComponent.AppliesTo.ADULT,
    "child_bed": TripCostComponent.AppliesTo.CHILD_BED,
    "child_no_bed": TripCostComponent.AppliesTo.CHILD_NO_BED,
    "infant": TripCostComponent.AppliesTo.INFANT,
}


def _round_up(value: Decimal, increment: int) -> Decimal:
    step = Decimal(increment)
    return (value / step).quantize(Decimal("1"), rounding=ROUND_CEILING) * step


def calculate_package(package: TripOccupancyPackage, counts=None):
    """Calculate immutable, public-safe unit prices and an optional party total."""
    if package.adult_price_id:
        return calculate_hotel_package(package, counts)
    if min(package.makkah_occupancy, package.madinah_occupancy, package.rounding_increment) < 1:
        raise ValidationError("Occupancies and rounding must be positive.")
    components = list(package.trip.cost_components.filter(is_active=True))
    currency = (
        AgencyCurrency.objects.filter(agency=package.agency, is_accounting=True, is_enabled=True)
        .values_list("currency_id", flat=True)
        .first()
    )
    if not currency:
        raise ValidationError("Configure an accounting currency before publishing packages.")

    unit_prices = {}
    breakdown = {}
    for category in CATEGORIES:
        lines = []
        base = Decimal("0")
        applicable = [c for c in components if c.applies_to == APPLIES_TO[category]]
        replaced_codes = {c.code for c in applicable}
        for component in components:
            if component.applies_to == "ALL" and component.code in replaced_codes:
                continue
            if component.applies_to not in (
                TripCostComponent.AppliesTo.ALL,
                APPLIES_TO[category],
            ):
                continue
            amount = component.converted_amount
            if component.basis == TripCostComponent.Basis.MAKKAH_ROOM:
                if category not in ("adult", "child_bed"):
                    continue
                amount /= Decimal(package.makkah_occupancy)
            elif component.basis == TripCostComponent.Basis.MADINAH_ROOM:
                if category not in ("adult", "child_bed"):
                    continue
                amount /= Decimal(package.madinah_occupancy)
            base += amount
            lines.append({"code": component.code, "label": component.label, "amount": str(amount)})

        margin = getattr(package, f"margin_{category}")
        override = getattr(package, f"override_{category}")
        selling = override if override is not None else base + margin
        if selling < 0:
            raise ValidationError("Selling prices cannot be negative.")
        if override is None and not lines:
            raise ValidationError(f"Configure components or an override for {category}.")
        selling = (
            override if override is not None else _round_up(selling, package.rounding_increment)
        )
        unit_prices[category] = selling
        breakdown[category] = {
            "base": str(base),
            "margin": str(margin),
            "override": str(override) if override is not None else None,
            "selling": str(selling),
            "components": lines,
        }

    normalized_counts = {category: int((counts or {}).get(category, 0)) for category in CATEGORIES}
    if any(value < 0 or value > 99 for value in normalized_counts.values()):
        raise ValidationError("Traveler counts are invalid.")
    if counts is not None and normalized_counts["adult"] < 1:
        raise ValidationError("At least one adult is required.")
    total = sum(
        (unit_prices[category] * normalized_counts[category] for category in CATEGORIES),
        Decimal("0"),
    )
    return {
        "package_id": str(package.pk),
        "package_code": package.code,
        "package_name": package.name,
        "makkah_occupancy": package.makkah_occupancy,
        "madinah_occupancy": package.madinah_occupancy,
        "currency": currency,
        "unit_prices": {key: str(value) for key, value in unit_prices.items()},
        "counts": normalized_counts,
        "total": str(total),
        "breakdown": breakdown,
    }


def public_package(package):
    result = calculate_package(package)
    result.pop("breakdown")
    return result


def calculate_hotel_package(package, counts=None):
    from types import SimpleNamespace
    from .services import resolve_traveler_price

    price = package.adult_price
    if price.trip_hotel.stop.trip_id != package.trip_id or price.scope != "TRIP_PACKAGE":
        raise ValidationError("Package price belongs to another trip or is not a whole-trip price.")
    unit_prices = {}
    breakdown = {}
    for key, category, bed in [("adult", "ADT", "REQUIRED"), ("child_bed", "CHD", "REQUIRED"), ("child_no_bed", "CHD", "NOT_REQUIRED"), ("infant", "INF", "NOT_REQUIRED")]:
        if key == "child_no_bed":
            resolved = resolve_traveler_price(trip=package.trip, trip_hotel=price.trip_hotel, room_type=price.room_type, passenger_category=SimpleNamespace(code=category), bed_requirement=bed)
            unit_prices[key] = resolved.amount
            breakdown[key] = {"base": str(resolved.base_amount), "discount": str(resolved.discount_amount), "selling": str(resolved.amount), "hotel": str(price.trip_hotel_id), "room_type": None}
            continue
        if key == "infant":
            resolved = resolve_traveler_price(trip=package.trip, trip_hotel=price.trip_hotel, room_type=price.room_type, passenger_category=SimpleNamespace(code=category), bed_requirement=bed)
            unit_prices[key] = resolved.amount
            breakdown[key] = {"base": str(resolved.base_amount), "discount": str(resolved.discount_amount), "selling": str(resolved.amount), "hotel": str(price.trip_hotel_id), "room_type": None}
            continue
        override = getattr(package, f"override_{key}")
        if override is not None:
            amount = override
            base_amount = price.amount if key == "adult" else amount
            discount = max(base_amount - amount, Decimal("0"))
            currency_id = price.currency_id
        else:
            result = resolve_traveler_price(trip=package.trip, trip_hotel=price.trip_hotel, room_type=price.room_type, passenger_category=SimpleNamespace(code=category), bed_requirement=bed)
            if result.currency_id != price.currency_id:
                raise ValidationError("Package and fixed trip prices must use the same currency.")
            amount = result.amount
            base_amount = result.base_amount
            discount = result.discount_amount
            currency_id = result.currency_id
        unit_prices[key] = amount
        breakdown[key] = {"base": str(base_amount), "discount": str(discount), "selling": str(amount), "hotel": str(price.trip_hotel_id), "room_type": str(price.room_type_id)}
    party = {key: int((counts or {}).get(key, 0)) for key in CATEGORIES}
    if any(n < 0 or n > 99 for n in party.values()) or (counts is not None and party["adult"] < 1):
        raise ValidationError("Traveler counts are invalid.")
    return {"package_id": str(package.pk), "package_code": package.code, "package_name": package.name, "makkah_occupancy": package.makkah_occupancy, "madinah_occupancy": package.madinah_occupancy, "currency": price.currency_id, "unit_prices": {key: str(value) for key, value in unit_prices.items()}, "breakdown": breakdown, "counts": party, "total": str(sum((unit_prices[key] * party[key] for key in CATEGORIES), Decimal("0"))), "trip_hotel": str(price.trip_hotel_id), "hotel_name": price.trip_hotel.hotel.name, "room_type": str(price.room_type_id), "pricing_mode": "HOTEL_PACKAGE"}
