from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import filters, mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response

from audit.services import record_event
from bookings.models import Booking, BookingTraveler
from trips.models import (
    Trip,
    TripAllocationRoom,
    TripClosingItem,
    TripFlight,
    TripHotel,
    TripRoomAssignment,
    TripStop,
    TripTransport,
)
from trips.services import (
    assign_traveler_to_room,
    close_trip,
    reopen_trip_closing,
    reorder_trip_stops,
    start_trip_closing,
    transition_trip,
    trip_closing_summary,
    update_trip_closing_item,
)

from .serializers import (
    RoomAssignmentInputSerializer,
    StopReorderSerializer,
    TripAllocationRoomSerializer,
    TripClosingItemSerializer,
    TripClosingItemUpdateSerializer,
    TripFlightSerializer,
    TripHotelSerializer,
    TripRoomAssignmentSerializer,
    TripSerializer,
    TripStopSerializer,
    TripTransitionSerializer,
    TripTransportSerializer,
)


class TripViewSet(viewsets.ModelViewSet):
    queryset = (
        Trip.objects.select_related("branch")
        .annotate(
            stop_count=Count("stops", distinct=True),
            hotel_count=Count("stops__hotels", distinct=True),
            flight_count=Count("flights", distinct=True),
            booked_places=Count(
                "bookings__travelers",
                filter=Q(bookings__status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED]),
                distinct=True,
            ),
        )
        .order_by("-departure_date", "name", "id")
    )
    serializer_class = TripSerializer
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["code", "name", "stops__city__name"]
    ordering_fields = ["departure_date", "return_date", "name", "status", "created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset().filter(agency=user.agency)
        if user.branch_id and not user.has_perm("trips.view_all_trips"):
            queryset = queryset.filter(branch=user.branch)
        trip_status = self.request.query_params.get("status")
        return queryset.filter(status=trip_status) if trip_status else queryset

    def perform_create(self, serializer):
        trip = serializer.save(agency=self.request.user.agency, created_by=self.request.user)
        self._audit("trip.created", trip)

    def perform_update(self, serializer):
        trip = serializer.save()
        self._audit("trip.updated", trip)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        current = self.get_object()
        input_serializer = TripTransitionSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            trip = transition_trip(
                trip_id=current.pk,
                agency=request.user.agency,
                target_status=input_serializer.validated_data["status"],
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        self._audit(
            "trip.status_changed",
            trip,
            metadata={"from": current.status, "to": trip.status},
        )
        return Response(self.get_serializer(trip).data)

    def _closing_response(self, trip):
        summary = trip_closing_summary(trip)
        summary["items"] = TripClosingItemSerializer(summary["items"], many=True).data
        return Response(summary)

    @action(detail=True, methods=["get"], url_path="closing")
    def closing(self, request, pk=None):
        return self._closing_response(self.get_object())

    @action(detail=True, methods=["post"], url_path="closing/start")
    def start_closing(self, request, pk=None):
        current = self.get_object()
        try:
            trip = start_trip_closing(trip_id=current.pk, agency=request.user.agency)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        self._audit("trip.closing_started", trip)
        return self._closing_response(trip)

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"closing/items/(?P<item_key>[^/.]+)",
    )
    def update_closing_item(self, request, pk=None, item_key=None):
        current = self.get_object()
        if item_key not in TripClosingItem.Key.values:
            raise serializers.ValidationError({"item": "Unknown closing checklist item."})
        input_serializer = TripClosingItemUpdateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            trip = update_trip_closing_item(
                trip_id=current.pk,
                agency=request.user.agency,
                actor=request.user,
                key=item_key,
                **input_serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        self._audit("trip.closing_item_updated", trip, {"item": item_key})
        return self._closing_response(trip)

    @action(detail=True, methods=["post"], url_path="closing/close")
    def close_closing(self, request, pk=None):
        current = self.get_object()
        if not request.user.has_perm("trips.close_trip"):
            self.permission_denied(request, message="You cannot close trips.")
        try:
            trip = close_trip(trip_id=current.pk, agency=request.user.agency, actor=request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        self._audit("trip.closing_completed", trip)
        return self._closing_response(trip)

    @action(detail=True, methods=["post"], url_path="closing/reopen")
    def reopen_closing(self, request, pk=None):
        current = self.get_object()
        if not request.user.has_perm("trips.close_trip"):
            self.permission_denied(request, message="You cannot reopen trip closing.")
        try:
            trip = reopen_trip_closing(trip_id=current.pk, agency=request.user.agency)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        self._audit("trip.closing_reopened", trip)
        return self._closing_response(trip)

    @action(detail=True, methods=["post"], url_path="reorder-stops")
    def reorder_stops(self, request, pk=None):
        trip = self.get_object()
        input_serializer = StopReorderSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            stops = reorder_trip_stops(
                trip=trip, ordered_ids=input_serializer.validated_data["stop_ids"]
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        self._audit("trip.itinerary_reordered", trip)
        return Response(TripStopSerializer(stops, many=True, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="traveler-preview")
    def traveler_preview(self, request, pk=None):
        from dataclasses import asdict
        from types import SimpleNamespace
        from travelers.rules import passenger_category_code
        from pricing.models import TripHotelPrice
        from pricing.services import resolve_traveler_price
        trip = self.get_object()
        birth = serializers.DateField().run_validation(request.data.get("birth_date"))
        from django.utils import timezone
        from bookings.readiness import required_stops
        if birth > timezone.localdate():
            raise serializers.ValidationError("Birth date cannot be in the future.")
        code = passenger_category_code(birth, trip.return_date)
        bed = serializers.ChoiceField(choices=["REQUIRED", "NOT_REQUIRED"]).run_validation(request.data.get("bed_requirement", "REQUIRED"))
        bed = "NOT_REQUIRED" if code == "INF" else bed
        service = serializers.ChoiceField(choices=["PACK", "VISA_ONLY", "TICKET_ONLY", "CUSTOM"]).run_validation(request.data.get("service_type", "PACK"))
        included = serializers.ListField(child=serializers.UUIDField()).run_validation(request.data.get("included_stops", []))
        selected = trip.stops.filter(pk__in=included)
        if selected.count() != len(included):
            raise serializers.ValidationError("Selected service stays must belong to this trip.")
        stops = trip.stops.filter(hotels__isnull=False).distinct()
        stops = required_stops(SimpleNamespace(passenger_category=SimpleNamespace(code=code), bed_requirement=bed, service_type=service, included_stops=selected), list(stops))
        result = {"category": code, "bed_requirement": bed, "seat_required": code != "INF", "required_stops": [str(stop.pk) for stop in stops]}
        if request.data.get("use_trip_price"):
            price = TripHotelPrice.objects.select_related("trip_hotel__stop", "room_type").filter(pk=request.data.get("source_price"), agency=request.user.agency, scope="TRIP_PACKAGE").first() if request.data.get("source_price") else None
            try:
                result["price"] = asdict(resolve_traveler_price(trip=trip, trip_hotel=price.trip_hotel if price else None, room_type=price.room_type if price else None, passenger_category=SimpleNamespace(code=code), bed_requirement=bed))
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.messages) from exc
        return Response(result)

    @action(detail=True, methods=["get"], url_path="readiness")
    def readiness(self, request, pk=None):
        from bookings.readiness import trip_readiness
        return Response(trip_readiness(self.get_object()))

    @action(detail=True, methods=["get"], url_path="export-xlsx")
    def export_xlsx(self, request, pk=None):
        from django.http import HttpResponse
        from trips.export import build_trip_workbook
        trip = self.get_object()
        response = HttpResponse(build_trip_workbook(trip, request.user), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="trip-{trip.pk}.xlsx"'
        return response

    @action(detail=True, methods=["get"], url_path="accommodation-plan")
    def accommodation_plan(self, request, pk=None):
        trip = self.get_object()
        travelers = list(
            BookingTraveler.objects.filter(
                booking__trip=trip,
                booking__status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
            )
            .select_related(
                "traveler",
                "traveler__current_photo",
                "passenger_category",
                "booking__customer",
                "booking__trip",
            )
            .prefetch_related(
                "trip_room_assignments__room__trip_hotel",
                "room_assignments__room_group__trip_hotel__hotel",
                "room_assignments__room_group__room_type",
            )
            .order_by("booking__code", "traveler__last_name", "traveler__first_name")
        )
        rooms = list(
            TripAllocationRoom.objects.filter(trip_hotel__stop__trip=trip)
            .select_related("trip_hotel__hotel", "trip_hotel__stop__city", "room_type")
            .prefetch_related(
                "assignments__booking_traveler__traveler__current_photo",
                "assignments__booking_traveler__booking",
            )
        )
        rooms_by_hotel = {}
        for room in rooms:
            rooms_by_hotel.setdefault(room.trip_hotel_id, []).append(room)
        required_stops = list(
            trip.stops.filter(hotels__isnull=False)
            .distinct()
            .select_related("city")
            .prefetch_related("hotels__hotel")
            .order_by("order")
        )
        from bookings.readiness import trip_readiness
        readiness = trip_readiness(trip)
        readiness_rows = {row["id"]: row for row in readiness["travelers_detail"]}
        traveler_payload = []
        for traveler in travelers:
            preferences = [
                {
                    "stop": str(link.room_group.trip_hotel.stop_id),
                    "hotel": link.room_group.trip_hotel.hotel.name,
                    "room_type": link.room_group.room_type.name,
                }
                for link in traveler.room_assignments.all()
            ]
            traveler_payload.append(
                {
                    "id": str(traveler.pk),
                    "required_stops": readiness_rows[str(traveler.pk)]["required_stops"],
                    "eligible_for_room": readiness_rows[str(traveler.pk)]["eligible_for_room"],
                    "name": traveler.traveler.display_name,
                    "booking_code": traveler.booking.code,
                    "group_name": traveler.booking.customer.display_name,
                    "gender": traveler.traveler.gender,
                    "photo_url": (
                        request.build_absolute_uri(
                            f"/api/v1/documents/{traveler.traveler.current_photo_id}/download/"
                        )
                        if traveler.traveler.current_photo_id
                        else None
                    ),
                    "passenger_category": traveler.passenger_category.code.upper(),
                    "preferences": preferences,
                    "assignments": TripRoomAssignmentSerializer(
                        traveler.trip_room_assignments.all(),
                        many=True,
                        context={"request": request},
                    ).data,
                }
            )
        stop_payload = []
        total_assignments = 0
        for stop in required_stops:
            assigned_count = sum(str(stop.pk) in row["required_stops"] and str(stop.pk) in row["assigned_stops"] for row in readiness_rows.values())
            required_count = sum(str(stop.pk) in row["required_stops"] for row in readiness_rows.values())
            total_assignments += assigned_count
            stop_payload.append(
                {
                    "id": str(stop.pk),
                    "city_name": stop.city.name,
                    "arrival_date": stop.arrival_date,
                    "departure_date": stop.departure_date,
                    "order": stop.order,
                    "assigned_count": assigned_count,
                    "unassigned_count": max(required_count - assigned_count, 0),
                    "hotels": [
                        {
                            "id": str(hotel.pk),
                            "hotel_name": hotel.hotel.name,
                            "is_primary": hotel.is_primary,
                            "rooms": TripAllocationRoomSerializer(
                                rooms_by_hotel.get(hotel.pk, []),
                                many=True,
                                context={"request": request},
                            ).data,
                        }
                        for hotel in stop.hotels.all()
                    ],
                }
            )
        required_assignments = sum(len(row["required_stops"]) for row in readiness_rows.values())
        return Response(
            {
                "trip": str(trip.pk),
                "travelers": traveler_payload,
                "stops": stop_payload,
                "summary": {
                    "traveler_count": len(travelers),
                    "required_stop_count": len(required_stops),
                    "assignment_count": total_assignments,
                    "required_assignment_count": required_assignments,
                    "is_complete": total_assignments == required_assignments,
                },
            }
        )

    def _audit(self, action, trip, metadata=None):
        record_event(
            actor=self.request.user,
            action=action,
            target_type="trips.Trip",
            target_id=trip.pk,
            metadata=metadata,
            request=self.request,
        )


class TripChildViewSet(viewsets.ModelViewSet):
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    audit_target = ""

    def _trip_scope(self, queryset):
        user = self.request.user
        queryset = queryset.filter(trip__agency=user.agency)
        if user.branch_id and not user.has_perm("trips.view_all_trips"):
            queryset = queryset.filter(trip__branch=user.branch)
        trip_id = self.request.query_params.get("trip")
        return queryset.filter(trip_id=trip_id) if trip_id else queryset

    def perform_create(self, serializer):
        instance = serializer.save()
        self._audit("created", instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._audit("updated", instance)

    def perform_destroy(self, instance):
        trip = instance.trip if hasattr(instance, "trip") else instance.stop.trip
        if trip.status not in [Trip.Status.DRAFT, Trip.Status.OPEN]:
            raise serializers.ValidationError(
                "Trip details can only be deleted while the trip is draft or open."
            )
        self._audit("deleted", instance)
        instance.delete()

    def _audit(self, verb, instance):
        trip = instance.trip
        record_event(
            actor=self.request.user,
            action=f"{self.audit_target.lower()}.{verb}",
            target_type=f"trips.{self.audit_target}",
            target_id=instance.pk,
            metadata={"trip_id": str(trip.pk)},
            request=self.request,
        )


class TripStopViewSet(TripChildViewSet):
    queryset = TripStop.objects.select_related("trip", "city__country")
    serializer_class = TripStopSerializer
    search_fields = ["city__name", "city__country__name"]
    ordering_fields = ["order", "arrival_date", "departure_date"]
    audit_target = "TripStop"

    def get_queryset(self):
        return self._trip_scope(super().get_queryset())


class TripHotelViewSet(TripChildViewSet):
    queryset = TripHotel.objects.select_related("stop__trip", "stop__city", "hotel")
    serializer_class = TripHotelSerializer
    search_fields = ["hotel__name", "stop__city__name"]
    ordering_fields = ["stop__order", "hotel__name"]
    audit_target = "TripHotel"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        queryset = queryset.filter(stop__trip__agency=user.agency)
        if user.branch_id and not user.has_perm("trips.view_all_trips"):
            queryset = queryset.filter(stop__trip__branch=user.branch)
        trip_id = self.request.query_params.get("trip")
        stop_id = self.request.query_params.get("stop")
        if trip_id:
            queryset = queryset.filter(stop__trip_id=trip_id)
        if stop_id:
            queryset = queryset.filter(stop_id=stop_id)
        return queryset

    def _audit(self, verb, instance):
        record_event(
            actor=self.request.user,
            action=f"triphotel.{verb}",
            target_type="trips.TripHotel",
            target_id=instance.pk,
            metadata={"trip_id": str(instance.stop.trip_id)},
            request=self.request,
        )


class TripAllocationRoomViewSet(viewsets.ModelViewSet):
    queryset = TripAllocationRoom.objects.select_related(
        "trip_hotel__stop__trip", "trip_hotel__stop__city", "trip_hotel__hotel", "room_type"
    ).prefetch_related(
        "assignments__booking_traveler__traveler",
        "assignments__booking_traveler__booking",
    )
    serializer_class = TripAllocationRoomSerializer
    permission_classes = [DjangoModelPermissions]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = (
            super().get_queryset().filter(trip_hotel__stop__trip__agency=self.request.user.agency)
        )
        trip_id = self.request.query_params.get("trip")
        trip_hotel_id = self.request.query_params.get("trip_hotel")
        if trip_id:
            queryset = queryset.filter(trip_hotel__stop__trip_id=trip_id)
        if trip_hotel_id:
            queryset = queryset.filter(trip_hotel_id=trip_hotel_id)
        return queryset

    def perform_create(self, serializer):
        room = serializer.save(created_by=self.request.user)
        room.full_clean()
        room.save()
        self._audit("trip_allocation_room.created", room)

    def perform_update(self, serializer):
        room = serializer.save()
        room.full_clean()
        room.save()
        self._audit("trip_allocation_room.updated", room)

    def perform_destroy(self, instance):
        if instance.assignments.exists():
            raise serializers.ValidationError("Move all travelers before deleting this room.")
        self._audit("trip_allocation_room.deleted", instance)
        instance.delete()

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        room = self.get_object()
        input_serializer = RoomAssignmentInputSerializer(
            data=request.data, context={"request": request}
        )
        input_serializer.is_valid(raise_exception=True)
        try:
            assignment = assign_traveler_to_room(
                room_id=room.pk,
                booking_traveler=input_serializer.validated_data["booking_traveler"],
                bed_number=input_serializer.validated_data.get("bed_number"),
                agency=request.user.agency,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        self._audit("trip_room_assignment.saved", room)
        return Response(
            TripRoomAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED
        )

    def _audit(self, action_name, room):
        record_event(
            actor=self.request.user,
            action=action_name,
            target_type="trips.TripAllocationRoom",
            target_id=room.pk,
            metadata={"trip_id": str(room.trip_hotel.stop.trip_id)},
            request=self.request,
        )


class TripRoomAssignmentViewSet(
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = TripRoomAssignment.objects.select_related(
        "stop__trip", "room__trip_hotel", "booking_traveler__traveler"
    )
    serializer_class = TripRoomAssignmentSerializer
    permission_classes = [DjangoModelPermissions]
    http_method_names = ["get", "delete", "head", "options"]

    def get_queryset(self):
        return super().get_queryset().filter(stop__trip__agency=self.request.user.agency)

    def perform_destroy(self, instance):
        record_event(
            actor=self.request.user,
            action="trip_room_assignment.removed",
            target_type="trips.TripRoomAssignment",
            target_id=instance.pk,
            metadata={"trip_id": str(instance.stop.trip_id)},
            request=self.request,
        )
        instance.delete()


class TripFlightViewSet(TripChildViewSet):
    queryset = TripFlight.objects.select_related(
        "trip", "airline", "origin_city", "destination_city"
    )
    serializer_class = TripFlightSerializer
    search_fields = [
        "flight_number",
        "airline__name",
        "origin_airport_code",
        "destination_airport_code",
    ]
    ordering_fields = ["order", "departure_at", "arrival_at"]
    audit_target = "TripFlight"

    def get_queryset(self):
        return self._trip_scope(super().get_queryset())


class TripTransportViewSet(TripChildViewSet):
    queryset = TripTransport.objects.select_related(
        "trip", "supplier", "origin_city", "destination_city"
    ).annotate(passenger_count=Count("trip__bookings__travelers", distinct=True))
    serializer_class = TripTransportSerializer
    search_fields = [
        "reference",
        "vehicle_details",
        "supplier__name",
        "origin_city__name",
        "destination_city__name",
    ]
    ordering_fields = ["order", "departure_at", "arrival_at", "mode"]
    audit_target = "TripTransport"

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        today = timezone.localdate()
        transports = self._trip_scope(super().get_queryset())
        if request.query_params.get("scope", "upcoming") != "all":
            transports = transports.filter(departure_at__date__gte=today)
        results = list(
            transports.order_by("departure_at", "trip__code", "order")
        )
        return Response(
            {
                "counts": {
                    "today": sum(item.departure_at.date() == today for item in results),
                    "urgent": sum(item.departure_at.date() <= today + timedelta(days=2) for item in results),
                    "week": sum(item.departure_at.date() <= today + timedelta(days=6) for item in results),
                    "month": sum(item.departure_at.date() <= today + timedelta(days=29) for item in results),
                    "total": len(results),
                },
                "results": TripTransportSerializer(
                    results, many=True, context={"request": request}
                ).data,
            }
        )

    def get_queryset(self):
        return self._trip_scope(super().get_queryset())
