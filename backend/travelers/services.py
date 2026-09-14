from django.db import transaction

from .models import Passport


def _sync_traveler_from_passport(passport):
    traveler = passport.traveler
    traveler.first_name = passport.first_name
    traveler.last_name = passport.last_name
    traveler.birth_date = passport.birth_date
    traveler.gender = passport.gender
    traveler.save(update_fields=["first_name", "last_name", "birth_date", "gender", "updated_at"])

    from bookings.models import Booking, BookingTraveler
    from reference.models import PassengerCategory
    from travelers.rules import passenger_category_code

    links = BookingTraveler.objects.select_related("booking__trip").filter(
        traveler=traveler, booking__status=Booking.Status.DRAFT
    )
    categories = {
        item.code.upper(): item
        for item in PassengerCategory.objects.filter(is_system=True, is_active=True)
    }
    for link in links:
        category = categories.get(
            passenger_category_code(passport.birth_date, link.booking.trip.return_date)
        )
        if category and link.passenger_category_id != category.pk:
            link.passenger_category = category
            link.save(update_fields=["passenger_category"])


@transaction.atomic
def save_passport(*, instance=None, traveler, actor, **data):
    list(
        Passport.objects.select_for_update().filter(traveler=traveler).values_list("pk", flat=True)
    )
    status = data.get("status", instance.status if instance else Passport.Status.CURRENT)
    if status == Passport.Status.CURRENT:
        Passport.objects.filter(traveler=traveler, status=Passport.Status.CURRENT).exclude(
            pk=instance.pk if instance else None
        ).update(status=Passport.Status.REPLACED)
    if instance is None:
        instance = Passport(agency=traveler.agency, traveler=traveler, created_by=actor)
    for field, value in data.items():
        setattr(instance, field, value)
    instance.full_clean()
    instance.save()
    if instance.status == Passport.Status.CURRENT:
        _sync_traveler_from_passport(instance)
    return instance
