from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Prefetch
from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response

from audit.services import record_event
from bookings.models import (
    Booking,
    BookingDiscount,
    BookingRequest,
    BookingRequestAttachment,
    BookingRoomGroup,
    BookingRoomTraveler,
    BookingTraveler,
    BookingTravelerCharge,
)
from bookings.services import (
    add_booking_traveler,
    add_charge_discount,
    add_inline_booking_traveler,
    add_room_group,
    add_traveler_charge,
    assign_room_traveler,
    confirm_booking_draft,
    convert_booking_request_to_draft,
    create_booking_draft,
    create_booking_from_quote,
    create_direct_booking,
    remove_booking_traveler,
    remove_draft_item,
    transition_booking,
    update_booking_size,
)
from travelers.api.serializers import PassportSerializer
from travelers.models import Passport
from travelers.rules import parse_td3_mrz

from .serializers import (
    AddBookingTravelerSerializer,
    AddChargeDiscountSerializer,
    AddRoomGroupSerializer,
    AddTravelerChargeSerializer,
    AssignRoomTravelerSerializer,
    BookingCustomerContactSerializer,
    BookingDraftSerializer,
    BookingFromQuoteSerializer,
    BookingRequestSerializer,
    BookingSerializer,
    BookingTransitionSerializer,
    DirectBookingSerializer,
    InlineBookingTravelerSerializer,
    MrzInputSerializer,
)


class RequestPermissions(DjangoModelPermissions):
    perms_map = {**DjangoModelPermissions.perms_map, "GET": ["bookings.view_bookingrequest"]}


class BookingRequestViewSet(viewsets.ModelViewSet):
    serializer_class = BookingRequestSerializer
    permission_classes = [RequestPermissions]
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_queryset(self):
        queryset = (
            BookingRequest.objects.filter(agency=self.request.user.agency)
            .select_related("trip", "package", "calculated_currency")
            .prefetch_related("attachments")
        )
        user = self.request.user
        if user.branch_id and not user.has_perm("bookings.view_all_bookings"):
            queryset = queryset.filter(trip__branch_id=user.branch_id)
        return queryset

    def partial_update(self, request, *args, **kwargs):
        if request.data.get("status") == BookingRequest.Status.CONVERTED:
            return Response(
                {"detail": "Use the convert action to create a booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="convert")
    def convert(self, request, pk=None):
        lead = self.get_object()
        try:
            booking = convert_booking_request_to_draft(
                request_id=lead.pk,
                agency=request.user.agency,
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        record_event(
            actor=request.user,
            action="booking_request.converted",
            target_type="bookings.BookingRequest",
            target_id=lead.pk,
            request=request,
            metadata={"booking_id": str(booking.pk)},
        )
        return Response(
            BookingSerializer(booking, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path=r"attachments/(?P<attachment_id>[^/.]+)/download",
    )
    def download_attachment(self, request, pk=None, attachment_id=None):
        lead = self.get_object()
        attachment = BookingRequestAttachment.objects.filter(pk=attachment_id, request=lead).first()
        if not attachment:
            return Response(status=status.HTTP_404_NOT_FOUND)
        record_event(
            actor=request.user,
            action="booking_request.passport_downloaded",
            target_type="bookings.BookingRequestAttachment",
            target_id=attachment.pk,
            request=request,
        )
        response = FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.original_filename,
            content_type=attachment.mime_type,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class BookingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        Booking.objects.select_related(
            "agency",
            "branch",
            "customer",
            "trip",
            "source_quote",
            "currency",
            "accounting_currency",
            "snapshot",
        )
        .prefetch_related(
            Prefetch(
                "travelers",
                queryset=BookingTraveler.objects.select_related(
                    "traveler", "passenger_category"
                ).prefetch_related(
                    Prefetch("traveler__passports", queryset=Passport.objects.all()),
                    "charges__discounts",
                    "room_assignments__room_group__trip_hotel__hotel",
                    "room_assignments__room_group__trip_hotel__stop__city",
                    "room_assignments__room_group__room_type",
                    "trip_room_assignments__stop",
                ),
            ),
            "accommodations__trip_hotel__stop__city",
            "accommodations__trip_hotel__hotel",
            "accommodations__room_type",
            "accommodations__passenger_category",
            "flights__trip_flight",
            "room_groups__trip_hotel__stop__city",
            "room_groups__trip_hotel__hotel",
            "room_groups__room_type",
            "room_groups__traveler_assignments__booking_traveler__traveler",
            "travelers__charges__discounts",
            "trip__stops__hotels",
            "financial_transactions__reverses",
        )
        .annotate(traveler_count=Count("travelers", distinct=True))
        .order_by("-created_at", "id")
    )
    serializer_class = BookingSerializer
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "code",
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
        "trip__name",
    ]
    ordering_fields = ["created_at", "status", "code", "trip__departure_date"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(agency=self.request.user.agency)
        user = self.request.user
        if user.branch_id and not user.has_perm("bookings.view_all_bookings"):
            queryset = queryset.filter(branch=user.branch)
        for parameter in ["trip", "customer", "status"]:
            value = self.request.query_params.get(parameter)
            if value:
                queryset = queryset.filter(**{parameter: value})
        return queryset

    def _command(self, service, **kwargs):
        try:
            return service(agency=self.request.user.agency, **kwargs)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    @action(detail=False, methods=["post"], url_path="from-quote")
    def from_quote(self, request):
        input_serializer = BookingFromQuoteSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        booking = self._command(
            create_booking_from_quote,
            quote_id=input_serializer.validated_data["quote_id"],
            code=input_serializer.validated_data["code"],
            actor=request.user,
        )
        self._audit("booking.created_from_quote", booking)
        return Response(self.get_serializer(booking).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="direct")
    def direct(self, request):
        input_serializer = DirectBookingSerializer(data=request.data, context={"request": request})
        input_serializer.is_valid(raise_exception=True)
        booking = self._command(
            create_direct_booking,
            actor=request.user,
            **input_serializer.validated_data,
        )
        self._audit("booking.created_directly", booking)
        return Response(self.get_serializer(booking).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="draft")
    def draft(self, request):
        input_serializer = BookingDraftSerializer(data=request.data, context={"request": request})
        input_serializer.is_valid(raise_exception=True)
        booking = self._command(
            create_booking_draft, actor=request.user, **input_serializer.validated_data
        )
        self._audit("booking.draft_created", booking)
        return Response(self.get_serializer(booking).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="traveler-flow")
    def traveler_flow(self, request, pk=None):
        from bookings.traveler_flow import TravelerFlowInput, save_traveler_flow

        booking = self.get_object()
        payload = TravelerFlowInput(data=request.data)
        payload.is_valid(raise_exception=True)
        self._command(save_traveler_flow, booking_id=booking.pk, request=request, data=payload.validated_data)
        return Response(self.get_serializer(self.get_queryset().get(pk=booking.pk)).data)

    @action(detail=True, methods=["patch"], url_path="size")
    def size(self, request, pk=None):
        booking = self.get_object()
        field = serializers.IntegerField(min_value=1, max_value=32767)
        count = field.run_validation(request.data.get("expected_travelers"))
        booking = self._command(update_booking_size, booking_id=booking.pk, expected_travelers=count)
        self._audit("booking.size_updated", booking)
        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=["post"], url_path="inline-travelers")
    def inline_traveler(self, request, pk=None):
        booking = self.get_object()
        serializer = InlineBookingTravelerSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        self._command(
            add_inline_booking_traveler,
            booking_id=booking.pk,
            actor=request.user,
            **serializer.validated_data,
        )
        return Response(
            self.get_serializer(self.get_queryset().get(pk=booking.pk)).data, status=201
        )

    @action(detail=True, methods=["patch"], url_path="customer-contact")
    def customer_contact(self, request, pk=None):
        booking = self.get_object()
        if booking.status != Booking.Status.DRAFT:
            raise serializers.ValidationError(
                "Customer contact can only change while the booking is a draft."
            )
        serializer = BookingCustomerContactSerializer(
            data=request.data,
            partial=True,
            context={"customer": booking.customer},
        )
        serializer.is_valid(raise_exception=True)
        customer = booking.customer
        for field, value in serializer.validated_data.items():
            setattr(customer, field, value)
        customer.save(update_fields=[*serializer.validated_data, "updated_at"])
        self._audit("booking.customer_contact_updated", booking)
        return Response(self.get_serializer(self.get_queryset().get(pk=booking.pk)).data)

    @action(
        detail=True,
        methods=["post", "patch"],
        url_path=r"travelers/(?P<link_id>[^/.]+)/passport",
    )
    def traveler_passport(self, request, pk=None, link_id=None):
        booking = self.get_object()
        if booking.status != Booking.Status.DRAFT:
            raise serializers.ValidationError(
                "Passport details can only change while the booking is a draft."
            )
        link = BookingTraveler.objects.select_related("traveler").get(pk=link_id, booking=booking)
        current = link.traveler.passports.filter(status=Passport.Status.CURRENT).first()
        payload = request.data.copy()
        payload["traveler"] = str(link.traveler_id)
        passport_serializer = PassportSerializer(
            instance=current if request.method == "PATCH" else None,
            data=payload,
            partial=request.method == "PATCH",
            context={"request": request},
        )
        passport_serializer.is_valid(raise_exception=True)
        passport = passport_serializer.save()
        self._audit(
            "booking.traveler_passport_saved",
            booking,
            {"link_id": str(link.pk), "passport_id": str(passport.pk)},
        )
        return Response(
            self.get_serializer(self.get_queryset().get(pk=booking.pk)).data,
            status=status.HTTP_201_CREATED if request.method == "POST" else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="parse-passport-mrz")
    def parse_passport_mrz(self, request, pk=None):
        booking = self.get_object()
        serializer = MrzInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            parsed = parse_td3_mrz(
                serializer.validated_data["mrz"],
                reference_date=booking.trip.return_date,
            )
        except (ValueError, TypeError) as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return Response(parsed)

    @action(detail=True, methods=["post"], url_path="rooms")
    def add_room(self, request, pk=None):
        booking = self.get_object()
        serializer = AddRoomGroupSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        self._command(add_room_group, booking_id=booking.pk, **serializer.validated_data)
        return Response(
            self.get_serializer(self.get_queryset().get(pk=booking.pk)).data, status=201
        )

    @action(detail=True, methods=["delete"], url_path=r"rooms/(?P<room_id>[^/.]+)")
    def remove_room(self, request, pk=None, room_id=None):
        booking = self.get_object()
        self._command(
            remove_draft_item,
            booking_id=booking.pk,
            model=BookingRoomGroup,
            item_id=room_id,
            relation="booking",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path=r"rooms/(?P<room_id>[^/.]+)/travelers")
    def assign_room(self, request, pk=None, room_id=None):
        booking = self.get_object()
        serializer = AssignRoomTravelerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._command(
            assign_room_traveler,
            booking_id=booking.pk,
            room_id=room_id,
            **serializer.validated_data,
        )
        return Response(
            self.get_serializer(self.get_queryset().get(pk=booking.pk)).data, status=201
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"rooms/(?P<room_id>[^/.]+)/travelers/(?P<assignment_id>[^/.]+)",
    )
    def unassign_room(self, request, pk=None, room_id=None, assignment_id=None):
        booking = self.get_object()
        self._command(
            remove_draft_item,
            booking_id=booking.pk,
            model=BookingRoomTraveler,
            item_id=assignment_id,
            relation="room_group__booking",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="charges")
    def add_charge(self, request, pk=None):
        booking = self.get_object()
        serializer = AddTravelerChargeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        self._command(add_traveler_charge, booking_id=booking.pk, **serializer.validated_data)
        return Response(
            self.get_serializer(self.get_queryset().get(pk=booking.pk)).data, status=201
        )

    @action(detail=True, methods=["delete"], url_path=r"charges/(?P<charge_id>[^/.]+)")
    def remove_charge(self, request, pk=None, charge_id=None):
        booking = self.get_object()
        self._command(
            remove_draft_item,
            booking_id=booking.pk,
            model=BookingTravelerCharge,
            item_id=charge_id,
            relation="booking_traveler__booking",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path=r"charges/(?P<charge_id>[^/.]+)/discounts")
    def add_discount(self, request, pk=None, charge_id=None):
        booking = self.get_object()
        serializer = AddChargeDiscountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._command(
            add_charge_discount,
            booking_id=booking.pk,
            charge_id=charge_id,
            actor=request.user,
            **serializer.validated_data,
        )
        return Response(
            self.get_serializer(self.get_queryset().get(pk=booking.pk)).data, status=201
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"charges/(?P<charge_id>[^/.]+)/discounts/(?P<discount_id>[^/.]+)",
    )
    def remove_discount(self, request, pk=None, charge_id=None, discount_id=None):
        booking = self.get_object()
        self._command(
            remove_draft_item,
            booking_id=booking.pk,
            model=BookingDiscount,
            item_id=discount_id,
            relation="charge__booking_traveler__booking",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        booking = self.get_object()
        booking = self._command(confirm_booking_draft, booking_id=booking.pk)
        self._audit("booking.confirmed", booking)
        return Response(self.get_serializer(self.get_queryset().get(pk=booking.pk)).data)

    @action(detail=True, methods=["post"], url_path="travelers")
    def add_traveler(self, request, pk=None):
        booking = self.get_object()
        input_serializer = AddBookingTravelerSerializer(
            data=request.data, context={"request": request}
        )
        input_serializer.is_valid(raise_exception=True)
        link = self._command(
            add_booking_traveler,
            booking_id=booking.pk,
            **input_serializer.validated_data,
        )
        self._audit(
            "booking.traveler_added",
            booking,
            {"link_id": str(link.pk), "traveler_id": str(link.traveler_id)},
        )
        booking = self.get_queryset().get(pk=booking.pk)
        return Response(self.get_serializer(booking).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[OpenApiParameter("link_id", OpenApiTypes.UUID, OpenApiParameter.PATH)]
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"travelers/(?P<link_id>[^/.]+)",
    )
    def remove_traveler(self, request, pk=None, link_id=None):
        booking = self.get_object()
        self._command(remove_booking_traveler, booking_id=booking.pk, link_id=link_id)
        self._audit("booking.traveler_removed", booking, {"link_id": str(link_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        booking = self.get_object()
        input_serializer = BookingTransitionSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        previous = booking.status
        transition_data = input_serializer.validated_data
        booking = self._command(
            transition_booking,
            booking_id=booking.pk,
            target_status=transition_data["status"],
            cancellation_reason=transition_data.get("cancellation_reason", ""),
        )
        self._audit("booking.status_changed", booking, {"from": previous, "to": booking.status})
        return Response(self.get_serializer(booking).data)

    def _audit(self, action_name, booking, metadata=None):
        record_event(
            actor=self.request.user,
            action=action_name,
            target_type="bookings.Booking",
            target_id=booking.pk,
            metadata=metadata,
            request=self.request,
        )
