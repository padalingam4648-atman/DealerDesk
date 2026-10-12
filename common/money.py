from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from rest_framework import serializers

TWOPLACES = Decimal("0.01")


def quantize_money(value: Decimal | str | int | None) -> Decimal:
    """Quantize amount to exactly 2 decimal places using ROUND_HALF_UP."""
    if value is None:
        return Decimal("0.00")
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            raise ValueError(f"Invalid monetary value: {value}")
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def format_money(value: Decimal | str | int | None) -> str:
    """Format decimal amount as a string with exactly 2 decimal places (e.g. '1459.50')."""
    return f"{quantize_money(value):.2f}"


class MoneyField(serializers.Field):
    """
    Serializer field that outputs strings with exactly 2 decimal places (e.g. '1459.50'),
    and validates incoming values strictly as Decimals > 0 or >= 0.
    """
    def __init__(self, *args, min_value=None, allow_zero=False, **kwargs):
        self.min_value = min_value
        self.allow_zero = allow_zero
        super().__init__(*args, **kwargs)

    def to_representation(self, value):
        if value is None:
            return None
        return format_money(value)

    def to_internal_value(self, data):
        if data is None or data == "":
            if self.allow_null:
                return None
            raise serializers.ValidationError("This field is required.")
        
        # Avoid treating boolean as number
        if isinstance(data, bool):
            raise serializers.ValidationError("A valid decimal number is required.")

        try:
            val_str = str(data).strip()
            # Check maximum 2 decimal places if decimal point present
            if "." in val_str:
                decimals = val_str.split(".")[1]
                if len(decimals) > 2:
                    raise serializers.ValidationError("Value must have at most 2 decimal places.")
            val = Decimal(val_str)
        except (InvalidOperation, ValueError):
            raise serializers.ValidationError("A valid decimal number is required.")

        if not self.allow_zero and val <= 0:
            raise serializers.ValidationError("Value must be strictly greater than 0.")
        if self.allow_zero and val < 0:
            raise serializers.ValidationError("Value cannot be negative.")

        return quantize_money(val)
