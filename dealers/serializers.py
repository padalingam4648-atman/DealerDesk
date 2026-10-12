from decimal import Decimal
from rest_framework import serializers
from common.exceptions import DuplicateError
from common.money import MoneyField
from dealers.models import Dealer


class DealerSerializer(serializers.ModelSerializer):
    credit_limit = MoneyField(allow_zero=True, default=Decimal("0.00"), required=False)

    class Meta:
        model = Dealer
        fields = [
            "id",
            "dealer_code",
            "name",
            "city",
            "phone",
            "email",
            "gstin",
            "credit_limit",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "dealer_code": {"validators": []},
        }

    def validate_dealer_code(self, value):
        value = str(value).strip()
        if not value:
            raise serializers.ValidationError("Dealer code cannot be empty.")
        if self.instance is None:
            if Dealer.objects.filter(dealer_code=value).exists():
                raise DuplicateError(f"Dealer with code '{value}' already exists.")
        return value
