"""Shared, read-only operational rules for APIs, payments, alerts and exports."""
from collections import Counter
from django.utils import timezone
from .models import Booking, BookingTraveler
from travelers.rules import passport_validity

ACTIVE = [Booking.Status.CONFIRMED, Booking.Status.COMPLETED]


def consumes_seat(link):
    return link.seat_required if link.seat_required is not None else link.passenger_category.code.upper() != "INF"


def consumes_bed(link):
    return link.bed_requirement == "REQUIRED" and link.passenger_category.code.upper() != "INF"


def required_stops(link, stops):
    if not consumes_bed(link) or link.service_type in {"VISA_ONLY", "TICKET_ONLY"}:
        return []
    if link.service_type == "CUSTOM":
        selected = {stop.pk for stop in link.included_stops.all()}
        return [stop for stop in stops if stop.pk in selected]
    return stops


def loaded_links(queryset):
    return queryset.select_related("traveler", "passenger_category", "booking__trip", "booking__customer", "booking__branch").prefetch_related("traveler__passports", "included_stops", "charges__discounts", "charges__source_price__trip_hotel__stop", "charges__source_price__trip_hotel__hotel", "charges__source_price__room_type", "charges__source_price__passenger_category", "trip_room_assignments__room__trip_hotel__hotel", "trip_room_assignments__room__room_type", "trip_room_assignments__stop", "payment_allocations__transaction__reverses").order_by("added_at", "id")


def seat_summary(trip, links=None):
    if links is None:
        links = BookingTraveler.objects.filter(booking__trip=trip, booking__status__in=ACTIVE).select_related("passenger_category")
    counts = Counter(link.passenger_category.code.upper() for link in links)
    occupied = sum(consumes_seat(link) for link in links)
    maximum = trip.max_travelers
    return {"capacity": maximum, "occupied": occupied, "remaining": None if maximum is None else max(maximum - occupied, 0), "overbooked_places": 0 if maximum is None else max(occupied - maximum, 0), "total": sum(counts.values()), "adt": counts["ADT"], "chd": counts["CHD"], "inf": counts["INF"]}


def current_passport(link):
    return next((p for p in link.traveler.passports.all() if p.status == "CURRENT"), None)


def passport_issues(link):
    p = current_passport(link)
    if p is None or not p.passport_number.strip():
        return ["Passport is required"]
    if p.issue_date > timezone.localdate() or not passport_validity(p.expiry_date, link.booking.trip.return_date).is_valid:
        return ["Passport is not valid for travel"]
    return []


def traveler_issues(link):
    p = current_passport(link)
    person = p or link.traveler
    issues = []
    if not (person.first_name.strip() and person.last_name.strip()):
        issues.append("First and last name are required")
    if not person.birth_date:
        issues.append("Birth date is required")
    if link.passenger_category.code.upper() not in {"ADT", "CHD", "INF"}:
        issues.append("Invalid traveler category")
    charges = list(link.charges.all())
    if not charges:
        issues.append("Individual price is required")
    for c in charges:
        if not c.source_price_id:
            continue
        price = c.source_price
        if price.trip_hotel.stop.trip_id != link.booking.trip_id:
            issues.append("Price belongs to another trip")
        derived_child = c.pricing_snapshot.get("passenger_category") == "CHD" and price.passenger_category.code.upper() == "ADT"
        if price.passenger_category_id != link.passenger_category_id and not derived_child:
            issues.append("Price category does not match traveler")
    return list(dict.fromkeys(issues))


def room_assignment_issues(link, required=None):
    if required is None:
        required = list(link.booking.trip.stops.filter(hotels__isnull=False).select_related("city").distinct())
    required = required_stops(link, required)
    assignments = list(link.trip_room_assignments.all())
    issues = []
    for stop in required:
        if not any(a.stop_id == stop.pk for a in assignments):
            issues.append(f"Room allocation is incomplete for {stop.city.name}")
    for a in assignments:
        if a.stop.trip_id != link.booking.trip_id or a.room.trip_hotel.stop_id != a.stop_id:
            issues.append("Room assignment belongs to another trip or stop")
        if not consumes_bed(link):
            issues.append("Non-bed traveler has a normal bed assignment")
        if a.bed_number > a.room.capacity:
            issues.append("Room assignment exceeds room capacity")
        for c in link.charges.all():
            if c.source_price_id and c.source_price.trip_hotel.stop_id == a.stop_id:
                if c.source_price.trip_hotel_id != a.room.trip_hotel_id or c.source_price.room_type_id != a.room.room_type_id:
                    issues.append("Hotel or room type does not match agreed pricing")
    return list(dict.fromkeys(issues))


def require_room_ready(link):
    from django.core.exceptions import ValidationError
    issues = traveler_issues(link) + passport_issues(link)
    if not consumes_bed(link) or link.service_type in {"VISA_ONLY", "TICKET_ONLY"}:
        issues.append("This traveler does not require a normal room bed")
    if issues:
        raise ValidationError(f"Complete traveler details before room allocation: {'; '.join(issues)}")


def payment_issues(booking):
    links = list(loaded_links(booking.travelers.all()))
    if len(links) != booking.expected_travelers:
        return ["Add all requested travelers and their valid passports before taking payment."]
    return [f"{link.traveler}: {issue}" for link in links for issue in passport_issues(link)]


def booking_capacity(booking):
    links = list(BookingTraveler.objects.filter(booking__trip_id=booking.trip_id, booking__status__in=ACTIVE).select_related("passenger_category"))
    summary = seat_summary(booking.trip, links)
    own = list(booking.travelers.select_related("passenger_category"))
    required = sum(consumes_seat(link) for link in own) + max(booking.expected_travelers - len(own), 0)
    others = sum(consumes_seat(link) for link in links if link.booking_id != booking.pk)
    maximum = summary["capacity"]
    available = None if maximum is None else max(maximum - others, 0)
    return {"maximum": maximum, "booked": summary["occupied"], "remaining": summary["remaining"], "overbooked_places": summary["overbooked_places"], "available_for_booking": available, "has_capacity": available is None or required <= available}


def analyze_booking(booking, links, stops, seats):
    counts = Counter(link.passenger_category.code.upper() for link in links)
    missing = dict.fromkeys(["passport", "phone", "hotel", "room", "price"], 0)
    invalid = dict.fromkeys(["passport", "hotel_price_mismatch", "room_assignment", "category"], 0)
    details = []
    valid = 0
    for link in links:
        identity = traveler_issues(link)
        passport = passport_issues(link)
        room = room_assignment_issues(link, stops)
        charges = list(link.charges.all())
        assignments = list(link.trip_room_assignments.all())
        required = required_stops(link, stops)
        states = {"identity": "INVALID" if identity and any("name" in i.lower() or "Birth" in i for i in identity) else "VALID", "category": "VALID" if link.passenger_category.code.upper() in {"ADT", "CHD", "INF"} else "INVALID", "passport": "MISSING" if "Passport is required" in passport else "INVALID" if passport else "VALID", "price": "MISSING" if not charges else "INVALID" if any("Price" in i for i in identity) else "VALID", "room": "NOT_REQUIRED" if not required else "MISSING" if any("incomplete" in i for i in room) else "INVALID" if room else "VALID", "phone": "VALID" if link.traveler.phone or booking.customer.phone else "MISSING", "visa": "NOT_TRACKED", "ticket": "NOT_TRACKED"}
        for key in ["passport", "price", "phone", "room"]:
            if states[key] == "MISSING": missing[key] += 1
        if states["passport"] == "INVALID": invalid["passport"] += 1
        if states["category"] == "INVALID": invalid["category"] += 1
        if any("match agreed" in issue or "another trip" in issue for issue in identity + room): invalid["hotel_price_mismatch"] += 1
        if any("assignment" in issue.lower() and "incomplete" not in issue for issue in room): invalid["room_assignment"] += 1
        if any(not any(a.stop_id == stop.pk for a in assignments) and not any(c.source_price_id and c.source_price.trip_hotel.stop_id == stop.pk for c in charges) for stop in required): missing["hotel"] += 1
        issues = identity + passport + room
        if not issues: valid += 1
        details.append({"id": str(link.pk), "name": str(link.traveler), "category": link.passenger_category.code.upper(), "seat_consuming": consumes_seat(link), "bed_consuming": consumes_bed(link), "service_type": link.service_type, "required_stops": [str(stop.pk) for stop in required], "assigned_stops": [str(a.stop_id) for a in assignments], "eligible_for_room": consumes_bed(link) and not identity and not passport, "status": "VALID" if not issues else "INVALID" if any(state == "INVALID" for state in states.values()) else "MISSING", "fields": states, "issues": list(dict.fromkeys(issues))})
    required_count = sum(len(required_stops(link, stops)) for link in links)
    completed_count = sum(len({a.stop_id for a in link.trip_room_assignments.all()} & {stop.pk for stop in required_stops(link, stops)}) for link in links)
    contact = bool(booking.customer.phone.strip() or booking.customer.email.strip())
    commercial = bool(links) and len(links) == booking.expected_travelers and contact and all(not traveler_issues(link) for link in links)
    count = len(links)
    return {"commercial_ready": commercial, "contact_complete": contact, "required_room_assignments": required_count, "completed_room_assignments": completed_count, "is_ready": count > 0 and count == booking.expected_travelers and valid == count and not seats["overbooked_places"], "travelers": {"total": count, "adt": counts["ADT"], "chd": counts["CHD"], "inf": counts["INF"], "seat_consuming": sum(consumes_seat(link) for link in links), "bed_consuming": sum(consumes_bed(link) for link in links)}, "seats": seats, "data_quality": {"valid": valid, "incomplete": count - valid}, "missing": missing, "invalid": invalid, "travelers_detail": details, "untracked": ["visa", "ticket", "meals", "manasik"]}


def trip_readiness(trip):
    bookings = list(trip.bookings.filter(status__in=ACTIVE).select_related("customer", "trip", "branch"))
    links = list(loaded_links(BookingTraveler.objects.filter(booking__in=bookings)))
    stops = list(trip.stops.filter(hotels__isnull=False).select_related("city").distinct())
    seats = seat_summary(trip, links)
    results = {str(booking.pk): analyze_booking(booking, [link for link in links if link.booking_id == booking.pk], stops, seats) for booking in bookings}
    details = [row for result in results.values() for row in result["travelers_detail"]]
    missing = dict(Counter({key: sum(result["missing"][key] for result in results.values()) for key in ["passport", "phone", "hotel", "room", "price"]}))
    invalid = {key: sum(result["invalid"][key] for result in results.values()) for key in ["passport", "hotel_price_mismatch", "room_assignment", "category"]}
    assigned = [a for link in links if consumes_bed(link) for a in link.trip_room_assignments.all()]
    room_counts = Counter(a.room_id for a in assigned)
    rooms = {a.room_id: a.room for a in assigned}
    over_rooms = sum(room_counts[pk] > room.capacity for pk, room in rooms.items())
    valid = sum(result["data_quality"]["valid"] for result in results.values())
    return {"is_ready": bool(results) and all(r["is_ready"] for r in results.values()) and over_rooms == 0, "travelers": {"total": len(links), "adt": seats["adt"], "chd": seats["chd"], "inf": seats["inf"], "seat_consuming": seats["occupied"], "bed_consuming": sum(consumes_bed(link) for link in links)}, "seats": seats, "beds": {"occupied": len(assigned), "over_capacity_rooms": over_rooms}, "data_quality": {"valid": valid, "incomplete": len(links) - valid}, "missing": missing, "invalid": invalid, "travelers_detail": details, "bookings": results, "errors": ([f"Trip is over capacity by {seats['overbooked_places']} seats."] if seats["overbooked_places"] else [])}


def booking_readiness(booking):
    links = list(loaded_links(booking.travelers.all()))
    stops = list(booking.trip.stops.filter(hotels__isnull=False).select_related("city").distinct())
    return analyze_booking(booking, links, stops, seat_summary(booking.trip))
