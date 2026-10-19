from django.urls import reverse
from tests.test_bookings import booking_data, client_for
from bookings.models import Booking, BookingTraveler
from customers.models import Customer
from travelers.models import Traveler, Passport


def payload(d):
    return {
        'branch': str(d['branch'].pk), 'trip': str(d['trip'].pk),
        'currency': 'DZD', 'accounting_currency': 'DZD', 'accounting_exchange_rate': '1',
        'phone': '0555555555',
        'passport': {
            'first_name': 'Walk', 'last_name': 'In', 'passport_number': 'WALK123',
            'birth_date': '1990-01-01', 'gender': 'M', 'issue_date': '2025-01-01',
            'expiry_date': '2035-01-01', 'nationality': str(d['country'].pk),
            'issuing_country': str(d['country'].pk),
        },
    }


def test_walk_in_passport_creates_contact_and_traveler_atomically(booking_data):
    d = booking_data
    response = client_for(d['owner']).post(reverse('booking-passport-start'), payload(d), format='json')
    assert response.status_code == 201, response.data
    booking = Booking.objects.get(pk=response.data['id'])
    assert booking.status == 'DRAFT'
    assert booking.total_amount == 0
    assert booking.expected_travelers == 1
    assert booking.customer.first_name == 'Walk'
    link = booking.travelers.get()
    assert link.is_customer_contact
    assert link.traveler.phone == booking.customer.phone
    assert link.traveler.passports.get().passport_number == 'WALK123'
    assert link.charges.count() == 0


def test_invalid_passport_does_not_leave_empty_booking_or_customer(booking_data):
    d = booking_data
    counts = [model.objects.count() for model in [Booking, Customer, Traveler, Passport]]
    body = payload(d)
    body['passport']['expiry_date'] = '2020-01-01'
    response = client_for(d['owner']).post(reverse('booking-passport-start'), body, format='json')
    assert response.status_code == 400
    assert counts == [model.objects.count() for model in [Booking, Customer, Traveler, Passport]]


def test_returning_traveler_reuses_passport_without_overwriting(booking_data):
    d = booking_data
    client = client_for(d['owner'])
    url = reverse('booking-passport-start')
    assert client.post(url, payload(d), format='json').status_code == 201
    first = Passport.objects.get(passport_number='WALK123')
    assert client.post(url, payload(d), format='json').status_code == 201
    assert Passport.objects.filter(passport_number='WALK123').count() == 1
    assert BookingTraveler.objects.filter(traveler=first.traveler).count() == 2
    body = payload(d)
    body['passport']['first_name'] = 'Different'
    before = Booking.objects.count()
    response = client.post(url, body, format='json')
    assert response.status_code == 400
    assert Booking.objects.count() == before
    first.refresh_from_db()
    assert first.first_name == 'Walk'


def test_foreign_trip_rejected(booking_data):
    d = booking_data
    response = client_for(d['foreign_owner']).post(reverse('booking-passport-start'), payload(d), format='json')
    assert response.status_code == 400
    assert not Booking.objects.exists()


def test_agency_contact_does_not_become_a_traveler(booking_data):
    d = booking_data
    body = payload(d)
    body.pop('passport')
    body.pop('phone')
    body['expected_travelers'] = 5
    body['new_customer'] = {'kind': 'COMPANY', 'company_name': 'Sending agency', 'phone': '0555555555'}
    response = client_for(d['owner']).post(reverse('booking-draft'), body, format='json')
    assert response.status_code == 201, response.data
    booking = Booking.objects.get(pk=response.data['id'])
    assert booking.customer.kind == 'COMPANY'
    assert booking.expected_travelers == 5
    assert booking.travelers.count() == 0


def test_cropped_photo_and_full_passport_fields_are_saved(booking_data, settings, tmp_path):
    import base64
    from io import BytesIO
    from PIL import Image
    settings.MEDIA_ROOT = tmp_path
    settings.PRIVATE_PASSPORT_ROOT = tmp_path / 'private'
    d = booking_data
    body = payload(d)
    body['passport'].update(middle_name='Middle', birth_place='Tlemcen', issue_place='Oran')
    buffer = BytesIO()
    Image.new('RGB', (32, 32), 'white').save(buffer, format='JPEG')
    body['photo'] = {'data': base64.b64encode(buffer.getvalue()).decode(), 'source': 'PASSPORT_MANUAL_CROP'}
    response = client_for(d['owner']).post(reverse('booking-passport-start'), body, format='json')
    assert response.status_code == 201, response.data
    person = Booking.objects.get(pk=response.data['id']).travelers.get().traveler
    assert person.current_photo_id
    assert person.current_photo_source == 'PASSPORT_MANUAL_CROP'
    assert person.current_photo.file.size > 0
    passport = person.passports.get()
    assert (passport.middle_name, passport.birth_place, passport.issue_place) == ('Middle', 'Tlemcen', 'Oran')


def test_invalid_cropped_photo_rolls_back_booking(booking_data):
    body = payload(booking_data)
    body['photo'] = {'data': 'not-an-image', 'source': 'PASSPORT_MANUAL_CROP'}
    before = Booking.objects.count(), Traveler.objects.count(), Customer.objects.count()
    response = client_for(booking_data['owner']).post(reverse('booking-passport-start'), body, format='json')
    assert response.status_code == 400
    assert before == (Booking.objects.count(), Traveler.objects.count(), Customer.objects.count())
