from decimal import Decimal
from django.urls import reverse
from tests.test_bookings import booking_data, client_for, group_draft, flow_room, flow_payload
from trips.models import TripAllocationRoom
from catalog.models import RoomType


def ready_booking(d):
    booking = group_draft(d, 1)
    room = flow_room(d)
    client = client_for(d['owner'])
    result = client.post(reverse('booking-traveler-flow', args=[booking.pk]), flow_payload(d, room), format='json')
    assert result.status_code == 200, result.data
    booking.refresh_from_db()
    return booking, client, room


def terms(**changes):
    result = {'source': 'SOCIAL_MEDIA', 'source_detail': 'Facebook', 'extras': [{'service': 'TGV', 'description': 'Madinah to Makkah', 'quantity': 2, 'unit_price': '25'}], 'payment_plan': 'INSTALLMENTS', 'installments': [{'due_date': '2027-01-01', 'amount': '50'}, {'due_date': '2027-05-01', 'amount': '100'}], 'expected_total': '150'}
    result.update(changes)
    return result


def test_final_agreement_includes_extras_and_preserves_accountant_copy(booking_data):
    booking, client, room = ready_booking(booking_data)
    result = client.post(reverse('booking-client-review', args=[booking.pk]), terms(), format='json')
    assert result.status_code == 200, result.data
    booking.refresh_from_db()
    assert booking.total_amount == Decimal('150')
    assert booking.status == 'CONFIRMED'
    assert booking.financial_transactions.count() == 0
    frozen = booking.snapshot.payload
    assert frozen['commercial_details']['installments'][1]['amount'] == '100.0000'
    assert frozen['assigned_rooms'][0]['room'] == room.label
    archive_url = reverse('booking-accountant-copy', args=[booking.pk])
    before = client.get(archive_url)
    assert before.status_code == 200
    assert b'150.0000' in before.content
    assert b'Facebook' in before.content
    room.label = 'Changed after confirmation'
    room.save()
    assert client.get(archive_url).content == before.content
    assert client.patch(reverse('booking-client-review', args=[booking.pk]), terms(), format='json').status_code == 400


def test_invalid_schedule_rolls_back_entire_confirmation(booking_data):
    booking, client, _ = ready_booking(booking_data)
    result = client.post(reverse('booking-client-review', args=[booking.pk]), terms(installments=[{'due_date': '2027-01-01', 'amount': '20'}, {'due_date': '2027-02-01', 'amount': '30'}]), format='json')
    assert result.status_code == 400
    booking.refresh_from_db()
    assert booking.status == 'DRAFT'
    assert booking.total_amount == Decimal('100')
    assert booking.commercial_details == {}
    assert not hasattr(booking, 'snapshot')


def test_stale_total_requires_new_client_review(booking_data):
    booking, client, _ = ready_booking(booking_data)
    result = client.post(reverse('booking-client-review', args=[booking.pk]), terms(expected_total='120'), format='json')
    assert result.status_code == 400
    assert 'total changed' in str(result.data)
    booking.refresh_from_db()
    assert booking.status == 'DRAFT'


def test_room_change_at_same_price_requires_new_review(booking_data):
    booking, client, room = ready_booking(booking_data)
    revision = client.get(reverse('booking-detail', args=[booking.pk])).data['offer_revision']
    room.label = 'Different room agreement'
    room.save()
    result = client.post(reverse('booking-client-review', args=[booking.pk]), terms(expected_revision=revision), format='json')
    assert result.status_code == 400
    assert 'details changed' in str(result.data)


def test_missing_room_blocks_final_confirmation(booking_data):
    booking, client, _ = ready_booking(booking_data)
    booking.travelers.get().trip_room_assignments.all().delete()
    result = client.post(reverse('booking-client-review', args=[booking.pk]), terms(), format='json')
    assert result.status_code == 400
    booking.refresh_from_db()
    assert booking.status == 'DRAFT'


def test_draft_room_type_and_price_can_change_together(booking_data):
    d = booking_data
    booking, client, _ = ready_booking(d)
    room_type = RoomType.objects.create(agency=d['agency'], code='quint', name='Quintuple', default_standard_beds=5)
    created = client.post(reverse('trip-allocation-room-list'), {'trip_hotel': str(d['trip_hotel'].pk), 'room_type': str(room_type.pk), 'label': 'New quintuple', 'standard_beds': 5, 'extra_beds': 0, 'occupancy_policy': 'ANY'}, format='json')
    assert created.status_code == 201, created.data
    room = TripAllocationRoom.objects.get(pk=created.data['id'])
    link = booking.travelers.get()
    response = client.post(reverse('booking-traveler-flow', args=[booking.pk]), flow_payload(d, room, link_id=str(link.pk), price_mode='REPLACE_DRAFT', amount='80'), format='json')
    assert response.status_code == 200, response.data
    booking.refresh_from_db()
    assert booking.total_amount == Decimal('80')
    assert link.trip_room_assignments.get().room == room
    assert link.charges.count() == 1
    assert link.charges.get().final_amount == Decimal('80')


def test_offer_can_be_saved_and_extras_survive_traveler_price_change(booking_data):
    d = booking_data
    booking, client, room = ready_booking(d)
    url = reverse('booking-client-review', args=[booking.pk])
    assert client.patch(url, terms(payment_plan='FULL'), format='json').status_code == 200
    link = booking.travelers.get()
    response = client.post(reverse('booking-traveler-flow', args=[booking.pk]), flow_payload(d, room, link_id=str(link.pk), price_mode='REPLACE_DRAFT', amount='90'), format='json')
    assert response.status_code == 200, response.data
    booking.refresh_from_db()
    assert booking.total_amount == Decimal('140')
    assert booking.commercial_details['installments'] == []


def test_foreign_user_cannot_download_archive_or_update_offer(booking_data):
    d = booking_data
    booking, _, _ = ready_booking(d)
    other = client_for(d['foreign_owner'])
    assert other.get(reverse('booking-accountant-copy', args=[booking.pk])).status_code == 404
    assert other.patch(reverse('booking-client-review', args=[booking.pk]), terms(), format='json').status_code == 404
