from rest_framework import serializers

from reference.models import (
    AgencyCurrency,
    City,
    Country,
    Currency,
    PassengerCategory,
    PaymentMethod,
)


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "name", "code"]


class CitySerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source="country.code", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = City
        fields = ["id", "name", "country", "country_code", "country_name"]


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["code", "name", "symbol", "decimal_places", "is_active"]


class AgencyCurrencySerializer(serializers.ModelSerializer):
    currency_name = serializers.CharField(source="currency.name", read_only=True)
    currency_symbol = serializers.CharField(source="currency.symbol", read_only=True)

    class Meta:
        model = AgencyCurrency
        fields = [
            "id",
            "currency",
            "currency_name",
            "currency_symbol",
            "is_enabled",
            "is_accounting",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        agency = self.context["request"].user.agency
        is_accounting = attrs.get(
            "is_accounting", self.instance.is_accounting if self.instance else False
        )
        is_enabled = attrs.get("is_enabled", self.instance.is_enabled if self.instance else True)
        if is_accounting and not is_enabled:
            raise serializers.ValidationError("The accounting currency must be enabled.")
        if is_accounting:
            existing = AgencyCurrency.objects.filter(agency=agency, is_accounting=True)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError("The agency already has an accounting currency.")
        return attrs


class PassengerCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PassengerCategory
        fields = [
            "id",
            "code",
            "name",
            "requires_bed_by_default",
            "is_system",
            "is_active",
            "sort_order",
        ]
        read_only_fields = ["id", "is_system"]


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ["id", "code", "name", "is_system", "is_active", "sort_order"]
        read_only_fields = ["id", "is_system"]
