from django.urls import reverse
from tests.test_bookings import booking_data, client_for
from partners.models import Partner
from bookings.models import Booking
from customers.models import Customer


def body(d, partner):
    return {'partner': str(partner.pk), 'branch': str(d['branch'].pk), 'trip': str(d['trip'].pk), 'expected_travelers': 3, 'currency': 'DZD', 'accounting_currency': 'DZD', 'accounting_exchange_rate': '1'}


def test_create_partner_then_start_booking(booking_data):
    d = booking_data
    client = client_for(d['owner'])
    result = client.post(reverse('partner-list'), {'name': 'Partner agency', 'kind': 'COMPANY', 'branch': str(d['branch'].pk), 'phone': '0555555555', 'contact_name': 'Contact'}, format='json')
    assert result.status_code == 201, result.data
    partner = Partner.objects.get(pk=result.data['id'])
    response = client.post(reverse('booking-draft'), body(d, partner), format='json')
    assert response.status_code == 201, response.data
    booking = Booking.objects.get(pk=response.data['id'])
    assert booking.partner == partner
    assert response.data['partner_name'] == partner.name
    assert booking.customer.company_name == partner.name
    assert booking.customer.phone == partner.phone
    assert booking.travelers.count() == 0
    before = Customer.objects.count()
    response = client.post(reverse('booking-draft'), body(d, partner), format='json')
    assert response.status_code == 201
    assert Customer.objects.count() == before


def test_foreign_and_inactive_partners_cannot_be_selected(booking_data):
    d = booking_data
    partner = Partner.objects.create(agency=d['foreign_agency'], branch=d['foreign_branch'], created_by=d['foreign_owner'], name='Foreign')
    client = client_for(d['owner'])
    assert client.post(reverse('booking-draft'), body(d, partner), format='json').status_code == 400
    partner = Partner.objects.create(agency=d['agency'], branch=d['branch'], created_by=d['owner'], name='Inactive', is_active=False)
    assert client.post(reverse('booking-draft'), body(d, partner), format='json').status_code == 400
    assert Booking.objects.count() == 0


def test_partner_cannot_be_combined_with_unrelated_customer(booking_data):
    d = booking_data
    partner = Partner.objects.create(agency=d['agency'], branch=d['branch'], created_by=d['owner'], name='Partner')
    data = {**body(d, partner), 'customer': str(d['customer'].pk)}
    assert client_for(d['owner']).post(reverse('booking-draft'), data, format='json').status_code == 400
    assert Booking.objects.count() == 0
