import hashlib
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking, BookingRequest, BookingRequestAttachment, BookingTraveler
from bookings.public_input import PublicRequestInput, RequestThrottle, validate_passport
from finance.models import FinancialTransaction
from notifications.models import NotificationRule
from notifications.services import notify_agency
from organizations.models import Agency
from pricing.calculator import calculate_package, public_package
from pricing.models import TripOccupancyPackage
from reference.models import AgencyCurrency
from trips.models import Trip


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: dict}, auth=[])
    def get(self, request):
        return Response({"status": "ok", "service": "travel-erp-api"})


class PublicHomeView(APIView):
    """Sale-facing agency and trip data; deliberately excludes internal records."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: dict}, auth=[])
    def get(self, request):
        agencies = Agency.objects.filter(is_active=True)
        requested_slug = request.query_params.get("agency")
        agency = (
            agencies.filter(slug=requested_slug).first() if requested_slug else agencies.first()
        )
        if not agency:
            return Response({"agency": None, "available_trips": [], "upcoming_trips": []})
        today = timezone.localdate()
        trips = (
            Trip.objects.filter(agency=agency, status=Trip.Status.OPEN, departure_date__gte=today)
            .annotate(
                booked_places=Count(
                    "bookings__travelers",
                    filter=Q(
                        bookings__status__in=[
                            Booking.Status.CONFIRMED,
                            Booking.Status.COMPLETED,
                        ]
                    ),
                    distinct=True,
                )
            )
            .prefetch_related(
                "stops__city",
                "stops__hotels__hotel",
                "flights__airline",
                "stops__hotels__prices__currency",
                "cost_components",
                "occupancy_packages",
            )
            .order_by("departure_date")
        )
        available = trips.filter(
            Q(booking_open_date__isnull=True) | Q(booking_open_date__lte=today),
            Q(booking_close_date__isnull=True) | Q(booking_close_date__gte=today),
        )
        upcoming = trips.filter(booking_open_date__gt=today)

        def trip_data(trip):
            from bookings.readiness import seat_summary
            seats = seat_summary(trip)
            stops = list(trip.stops.all())
            flights = list(trip.flights.all())
            prices = [
                p for stop in stops for hotel in stop.hotels.all() for p in hotel.prices.all()
            ]
            calculated_packages = []
            for package in trip.occupancy_packages.all():
                if not package.is_published:
                    continue
                try:
                    calculated_packages.append(public_package(package))
                except DjangoValidationError:
                    continue
            starting_package = min(
                calculated_packages,
                key=lambda item: Decimal(item["unit_prices"]["adult"]),
                default=None,
            )
            return {
                "id": str(trip.id),
                "code": trip.code,
                "name": trip.name,
                "description": trip.description,
                "departure_date": trip.departure_date,
                "return_date": trip.return_date,
                "booking_open_date": trip.booking_open_date,
                "booking_close_date": trip.booking_close_date,
                "duration_days": (trip.return_date - trip.departure_date).days + 1,
                "stops": [
                    {
                        "city": s.city.name,
                        "nights": s.nights,
                        "hotels": [h.hotel.name for h in s.hotels.all()],
                    }
                    for s in stops
                ],
                "airlines": list(dict.fromkeys(f.airline.name for f in flights)),
                "departure_airport": flights[0].origin_airport_code if flights else "",
                "starting_price": (
                    starting_package["unit_prices"]["adult"] if starting_package else None
                ),
                "currency": (starting_package["currency"] if starting_package else None),
                "has_promotion": any(p.price_kind == "PROMOTIONAL" for p in prices),
                "max_travelers": trip.max_travelers,
                "booked_places": seats["occupied"],
                "remaining_places": seats["remaining"],
                "capacity_summary": seats,
            }

        settings = getattr(agency, "settings", None)
        return Response(
            {
                "agency": {
                    "name": agency.name,
                    "legal_name": agency.legal_name,
                    "logo": request.build_absolute_uri(agency.logo.url) if agency.logo else None,
                    "phone": agency.phone,
                    "email": agency.email,
                    "address": agency.address,
                    "website": agency.website,
                    "primary_color": settings.primary_color if settings else "#0e7490",
                    "secondary_color": settings.secondary_color if settings else "#0f172a",
                },
                "available_trips": [trip_data(t) for t in available],
                "upcoming_trips": [trip_data(t) for t in upcoming],
            }
        )


class PublicTripView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        today = timezone.localdate()
        trip = (
            Trip.objects.filter(
                pk=pk,
                agency__is_active=True,
                status=Trip.Status.OPEN,
                departure_date__gte=today,
            )
            .annotate(
                booked_places=Count(
                    "bookings__travelers",
                    filter=Q(
                        bookings__status__in=[
                            Booking.Status.CONFIRMED,
                            Booking.Status.COMPLETED,
                        ]
                    ),
                    distinct=True,
                )
            )
            .prefetch_related(
                "stops__city",
                "stops__hotels__hotel",
                "stops__hotels__prices__currency",
                "flights__airline",
                "flights__origin_city",
                "flights__destination_city",
                "transports__origin_city",
                "transports__destination_city",
                "cost_components",
                "occupancy_packages",
            )
            .select_related("agency")
            .first()
        )
        if not trip:
            return Response({"detail": "Trip not found."}, status=404)
        from bookings.readiness import seat_summary
        seats = seat_summary(trip)
        is_bookable = (not trip.booking_open_date or trip.booking_open_date <= today) and (
            not trip.booking_close_date or trip.booking_close_date >= today
        )
        settings = getattr(trip.agency, "settings", None)
        stops = list(trip.stops.all())
        prices = [p for stop in stops for hotel in stop.hotels.all() for p in hotel.prices.all()]
        packages = []
        for package in trip.occupancy_packages.filter(is_published=True):
            try:
                packages.append(public_package(package))
            except DjangoValidationError:
                continue
        return Response(
            {
                "id": str(trip.id),
                "code": trip.code,
                "name": trip.name,
                "description": trip.description,
                "departure_date": trip.departure_date,
                "return_date": trip.return_date,
                "duration_days": (trip.return_date - trip.departure_date).days + 1,
                "booking_close_date": trip.booking_close_date,
                "is_bookable": is_bookable,
                "max_travelers": trip.max_travelers,
                "booked_places": seats["occupied"],
                "remaining_places": seats["remaining"],
                "capacity_summary": seats,
                "package_prices": {
                    "adult": None,
                    "child": None,
                    "infant": None,
                    "currency": None,
                },
                "packages": packages,
                "agency": {
                    "name": trip.agency.name,
                    "logo": request.build_absolute_uri(trip.agency.logo.url)
                    if trip.agency.logo
                    else None,
                    "phone": trip.agency.phone,
                    "email": trip.agency.email,
                    "primary_color": settings.primary_color if settings else "#0e7490",
                    "secondary_color": settings.secondary_color if settings else "#0f172a",
                },
                "stops": [
                    {
                        "city": s.city.name,
                        "arrival_date": s.arrival_date,
                        "departure_date": s.departure_date,
                        "nights": s.nights,
                        "hotels": [
                            {
                                "name": h.hotel.name,
                                "stars": h.hotel.star_rating,
                                "primary": h.is_primary,
                            }
                            for h in s.hotels.all()
                        ],
                    }
                    for s in stops
                ],
                "flights": [
                    {
                        "airline": f.airline.name,
                        "flight_number": f.flight_number,
                        "direction": f.get_direction_display(),
                        "origin": f.origin_city.name,
                        "destination": f.destination_city.name,
                        "departure_at": f.departure_at,
                        "arrival_at": f.arrival_at,
                    }
                    for f in trip.flights.all()
                ],
                "transports": [
                    {
                        "mode": t.get_mode_display(),
                        "origin": t.origin_city.name,
                        "destination": t.destination_city.name,
                        "departure_at": t.departure_at,
                        "vehicle_details": t.vehicle_details,
                    }
                    for t in trip.transports.all()
                ],
                "prices": [
                    {
                        "room_type": p.room_type.name,
                        "passenger_category": p.passenger_category.name,
                        "bed_basis": p.get_bed_basis_display(),
                        "amount": p.amount,
                        "currency": p.currency_id,
                        "promotional": p.price_kind == "PROMOTIONAL",
                    }
                    for p in prices
                ],
            }
        )


class PublicBookingRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_classes = [RequestThrottle]

    @transaction.atomic
    def post(self, request):
        input_data = PublicRequestInput(data=request.data)
        input_data.is_valid(raise_exception=True)
        today = timezone.localdate()
        trip = Trip.objects.filter(
            pk=request.data.get("trip"),
            agency__is_active=True,
            status=Trip.Status.OPEN,
            departure_date__gte=today,
        ).first()
        if (
            not trip
            or (trip.booking_open_date and trip.booking_open_date > today)
            or (trip.booking_close_date and trip.booking_close_date < today)
        ):
            return Response({"detail": "This trip is not currently open for booking."}, status=400)
        required = {key: request.data.get(key) for key in ["customer_name", "phone"]}
        consent = request.data.get("consent")
        if not all(required.values()) or consent not in (True, "true", "True", "1", 1):
            return Response({"detail": "Name, phone, and consent are required."}, status=400)
        try:
            counts = {
                "adult": int(request.data.get("adults", 1)),
                "child_bed": int(request.data.get("children_with_bed", 0)),
                "child_no_bed": int(
                    request.data.get("children_without_bed", request.data.get("children", 0))
                ),
                "infant": int(request.data.get("infants", 0)),
            }
        except (TypeError, ValueError):
            return Response({"detail": "Traveler counts are invalid."}, status=400)
        if counts["adult"] < 1 or any(value < 0 or value > 99 for value in counts.values()):
            return Response({"detail": "Traveler counts are invalid."}, status=400)
        requested_places = sum(counts.values()) - counts.get("infant", 0)
        if trip.max_travelers is not None:
            from bookings.readiness import seat_summary
            booked_places = seat_summary(trip)["occupied"]
            if requested_places > max(trip.max_travelers - booked_places, 0):
                return Response(
                    {"detail": "This trip does not have enough remaining places."},
                    status=409,
                )
        package = TripOccupancyPackage.objects.filter(
            pk=request.data.get("package"), trip=trip, agency=trip.agency, is_published=True
        ).first()
        if not package:
            return Response({"detail": "Select an available package."}, status=400)
        try:
            calculation = calculate_package(package, counts)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)
        expected = input_data.validated_data.get("expected_total")
        if expected is not None and expected != Decimal(calculation["total"]):
            return Response(
                {"detail": "Package prices changed. Reload the trip and review the new total."},
                status=409,
            )
        currency_setting = AgencyCurrency.objects.filter(
            agency=trip.agency,
            currency_id=calculation["currency"],
            is_enabled=True,
        ).first()
        files = request.FILES.getlist("passports")
        if len(files) > 10:
            return Response({"detail": "A maximum of 10 passport files is allowed."}, status=400)
        if files and not input_data.validated_data["passport_consent"]:
            return Response({"detail": "Passport processing consent is required."}, status=400)
        for uploaded_file in files:
            validate_passport(uploaded_file)
        if sum(f.size for f in files) > 25 * 1024 * 1024:
            return Response({"detail": "Attachments must total at most 25 MB."}, status=400)
        lead = BookingRequest.objects.create(
            agency=trip.agency,
            trip=trip,
            customer_name=str(required["customer_name"])[:180],
            phone=str(required["phone"])[:40],
            email=str(request.data.get("email", ""))[:254],
            adults=counts["adult"],
            children=counts["child_bed"] + counts["child_no_bed"],
            children_with_bed=counts["child_bed"],
            children_without_bed=counts["child_no_bed"],
            infants=counts["infant"],
            package=package,
            calculated_total=calculation["total"],
            calculated_currency=currency_setting.currency if currency_setting else None,
            pricing_snapshot=calculation,
            preferred_room_type=str(request.data.get("preferred_room_type", ""))[:100],
            notes=str(request.data.get("notes", ""))[:2000],
            consent=True,
        )
        for uploaded_file in files:
            digest = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                digest.update(chunk)
            uploaded_file.seek(0)
            BookingRequestAttachment.objects.create(
                request=lead,
                file=uploaded_file,
                original_filename=uploaded_file.name[:255],
                mime_type=uploaded_file.content_type or "application/octet-stream",
                size_bytes=uploaded_file.size,
                sha256=digest.hexdigest(),
            )
        notify_agency(
            agency=trip.agency,
            branch=trip.branch,
            event=NotificationRule.Event.BOOKING_REQUEST,
            title="New booking request",
            message=f"{lead.customer_name} requested {trip.name} ({lead.reference}).",
            target_url="/booking-requests",
            dedupe_key=f"BOOKING_REQUEST:{lead.pk}",
        )
        return Response(
            {
                "reference": lead.reference,
                "status": lead.status,
                "total": str(lead.calculated_total),
                "currency": lead.calculated_currency_id,
            },
            status=201,
        )


class DashboardView(APIView):
    """A branch-aware operational summary for the signed-in user's agency."""

    def get(self, request):
        user = request.user
        today = timezone.localdate()

        trips = Trip.objects.filter(agency=user.agency)
        bookings = Booking.objects.filter(agency=user.agency)
        booking_requests = BookingRequest.objects.filter(agency=user.agency).exclude(
            status__in=[
                BookingRequest.Status.CONVERTED,
                BookingRequest.Status.REJECTED,
            ]
        )
        payments = FinancialTransaction.objects.filter(
            agency=user.agency,
            kind__in=[
                FinancialTransaction.Kind.PAYMENT,
                FinancialTransaction.Kind.REFUND,
            ],
        )
        if user.branch_id:
            if not user.has_perm("trips.view_all_trips"):
                trips = trips.filter(branch=user.branch)
            if not user.has_perm("bookings.view_all_bookings"):
                bookings = bookings.filter(branch=user.branch)
                booking_requests = booking_requests.filter(trip__branch=user.branch)
            if not user.has_perm("finance.view_all_financial_transactions"):
                payments = payments.filter(branch=user.branch)

        upcoming_trips = trips.filter(
            departure_date__gte=today,
            status__in=[Trip.Status.DRAFT, Trip.Status.OPEN, Trip.Status.CLOSED],
        ).order_by("departure_date")[:5]
        recent_bookings = bookings.select_related("customer", "trip").order_by("-created_at")[:5]

        from bookings.readiness import trip_readiness
        operational = [{"trip": str(trip.pk), "name": trip.name, "readiness": trip_readiness(trip)} for trip in upcoming_trips]
        return Response(
            {
                "operational": operational,
                "counts": {
                    "open_trips": trips.filter(status=Trip.Status.OPEN).count(),
                    "booking_requests": booking_requests.count(),
                    "confirmed_bookings": bookings.filter(status=Booking.Status.CONFIRMED).count(),
                    "payment_entries": payments.count(),
                },
                "upcoming_trips": [
                    {
                        "id": str(trip.id),
                        "code": trip.code,
                        "name": trip.name,
                        "departure_date": trip.departure_date,
                        "status": trip.status,
                    }
                    for trip in upcoming_trips
                ],
                "recent_bookings": [
                    {
                        "id": str(booking.id),
                        "code": booking.code,
                        "customer_name": str(booking.customer),
                        "trip_name": booking.trip.name,
                        "status": booking.status,
                        "created_at": booking.created_at,
                    }
                    for booking in recent_bookings
                ],
            }
        )
