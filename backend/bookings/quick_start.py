"""Atomic passport-first draft creation; confirmation uses the normal booking rules."""
from django.db import transaction
from rest_framework import serializers
from travelers.api.serializers import PassportSerializer
from travelers.models import Traveler, Passport
from reference.models import PassengerCategory
from travelers.rules import passenger_category_code
from .models import BookingTraveler
from .services import create_booking_draft
from .api.serializers import BookingDraftSerializer


@transaction.atomic
def start_from_passport(request):
    payload = request.data.copy()
    scan = serializers.DictField().run_validation(payload.pop('passport_scan')) if 'passport_scan' in payload else None
    photo = serializers.DictField(required=False).run_validation(payload.pop('photo')) if 'photo' in payload else None
    passport_data = serializers.DictField().run_validation(payload.pop('passport', {}))
    passport_data['passport_number'] = str(passport_data.get('passport_number', '')).upper().replace(' ', '')
    payload['expected_travelers'] = 1
    payload.pop('customer', None)
    payload['new_customer'] = {
        'kind': 'INDIVIDUAL',
        'first_name': passport_data.get('first_name', ''),
        'last_name': passport_data.get('last_name', ''),
        'phone': payload.pop('phone', ''),
        'email': payload.pop('email', ''),
    }
    draft = BookingDraftSerializer(data=payload, context={'request': request})
    draft.is_valid(raise_exception=True)
    booking = create_booking_draft(agency=request.user.agency, actor=request.user, **draft.validated_data)
    existing = Passport.objects.filter(
        traveler__agency=request.user.agency,
        passport_number=passport_data.get('passport_number', ''),
        issuing_country_id=passport_data.get('issuing_country'),
        status='CURRENT',
    ).select_related('traveler').first()
    person = existing.traveler if existing else Traveler.objects.create(
        agency=request.user.agency, branch=booking.branch, created_by=request.user,
        phone=booking.customer.phone, email=booking.customer.email,
    )
    passport = PassportSerializer(instance=existing, data={**passport_data, 'traveler': str(person.pk), 'status': 'CURRENT'}, context={'request': request})
    passport.is_valid(raise_exception=True)
    if existing:
        for field in ['first_name', 'last_name', 'birth_date', 'expiry_date', 'issue_date', 'gender', 'nationality']:
            if passport.validated_data.get(field) != getattr(existing, field):
                raise serializers.ValidationError('This passport already exists with different details. Review the existing traveler record first.')
    else:
        passport.save()
    person.refresh_from_db()
    category = PassengerCategory.objects.get(code__iexact=passenger_category_code(person.birth_date, booking.trip.return_date), is_system=True, is_active=True)
    link = BookingTraveler(booking=booking, traveler=person, passenger_category=category, bed_requirement='NOT_REQUIRED' if category.code.upper() == 'INF' else 'REQUIRED', is_customer_contact=True)
    link.full_clean()
    link.save()
    from .passport_photo import save_cropped_photo, save_passport_image
    save_cropped_photo(person, photo, request)
    save_passport_image(existing or passport.instance, scan, request)
    return booking
