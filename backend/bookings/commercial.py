from decimal import Decimal
from django.db import transaction
from rest_framework import serializers
from .models import Booking


def offer_revision(booking):
    import hashlib
    import json
    from trips.models import TripRoomAssignment
    from .models import BookingTravelerCharge
    payload = {
        'total': str(booking.total_amount), 'size': booking.expected_travelers,
        'terms': booking.commercial_details,
        'customer': [booking.customer_id, booking.customer.phone, booking.customer.email],
        'travelers': list(booking.travelers.order_by('pk').values_list('pk', 'traveler__updated_at', 'passenger_category_id', 'bed_requirement', 'service_type')),
        'charges': list(BookingTravelerCharge.objects.filter(booking_traveler__booking=booking).order_by('pk').values_list('pk', 'base_amount', 'discounts__amount')),
        'rooms': list(TripRoomAssignment.objects.filter(booking_traveler__booking=booking).order_by('pk').values_list('booking_traveler_id', 'room_id', 'room__label', 'room__room_type_id', 'room__trip_hotel_id')),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class ExtraInput(serializers.Serializer):
    service = serializers.ChoiceField(choices=['TGV', 'SPECIAL_BUS', 'FOOD', 'OTHER'])
    description = serializers.CharField(max_length=180)
    quantity = serializers.IntegerField(min_value=1, max_value=32767)
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal('0'))


class InstallmentInput(serializers.Serializer):
    due_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal('0.0001'))


class CommercialInput(serializers.Serializer):
    expected_revision = serializers.CharField(max_length=64, required=False)
    expected_total = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal('0'), required=False)
    source = serializers.ChoiceField(choices=['WALK_IN', 'SOCIAL_MEDIA', 'PARTNER', 'REFERRER', 'OTHER'])
    source_detail = serializers.CharField(max_length=250, allow_blank=True, default='')
    extras = ExtraInput(many=True, default=list)
    payment_plan = serializers.ChoiceField(choices=['FULL', 'INSTALLMENTS'], default='FULL')
    installments = InstallmentInput(many=True, default=list)
    notes = serializers.CharField(max_length=2000, allow_blank=True, default='')


def extra_total(booking):
    return sum((Decimal(item['unit_price']) * item['quantity'] for item in booking.commercial_details.get('extras', [])), Decimal('0'))


@transaction.atomic
def save_commercial(*, booking_id, agency, data, finalize=False):
    from .services import _sync_draft_total, confirm_booking_draft
    from .readiness import booking_readiness
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    if booking.status != 'DRAFT':
        raise serializers.ValidationError('The client agreement can only change in a draft.')
    parsed = CommercialInput(data=data)
    parsed.is_valid(raise_exception=True)
    # Serializer representation provides canonical decimal strings and ISO dates for the snapshot.
    details = dict(parsed.data)
    expected_total = details.pop('expected_total', None)
    expected_revision = details.pop('expected_revision', None)
    if finalize and expected_revision and expected_revision != offer_revision(booking):
        raise serializers.ValidationError('The booking details changed. Reload and review the latest offer with the client.')
    if details['source'] == 'PARTNER' and not booking.partner_id:
        raise serializers.ValidationError('Select a partner agency when starting the booking.')
    if booking.partner_id and details['source'] != 'PARTNER':
        raise serializers.ValidationError('This booking is linked to a partner agency.')
    if details['source'] == 'REFERRER' and not details['source_detail'].strip():
        raise serializers.ValidationError('Enter the referrer name or reference.')
    if details['payment_plan'] == 'FULL':
        details['installments'] = []
    booking.commercial_details = details
    booking.save(update_fields=['commercial_details', 'updated_at'])
    _sync_draft_total(booking)
    if finalize:
        if expected_total is not None and Decimal(expected_total) != booking.total_amount:
            raise serializers.ValidationError('The booking total changed. Review the updated offer with the client before confirming.')
        if not booking_readiness(booking)['is_ready']:
            raise serializers.ValidationError('Complete all traveler identities, valid passports, prices and required rooms before client confirmation.')
        return confirm_booking_draft(booking_id=booking.pk, agency=agency)
    return booking


def validate_payment_plan(booking, total):
    details = booking.commercial_details
    if details.get('payment_plan') == 'INSTALLMENTS':
        installments = details.get('installments', [])
        if len(installments) < 2 or sum((Decimal(row['amount']) for row in installments), Decimal('0')) != total:
            raise serializers.ValidationError('At least two installments are required, and their amounts must equal the final total.')
