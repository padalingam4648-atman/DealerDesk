from decimal import Decimal
from rest_framework import serializers
from common.exceptions import DuplicateError, ValidationError
from common.money import MoneyField, format_money
from catalog.models import Product, Inventory


class ProductSerializer(serializers.ModelSerializer):
    price = MoneyField(allow_zero=False)
    stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "stock",
            "description",
        ]
        read_only_fields = ["stock"]
        extra_kwargs = {
            "sku": {"validators": []},
        }

    def get_stock(self, obj) -> int:
        if hasattr(obj, "inventory") and obj.inventory is not None:
            return obj.inventory.quantity
        return 0

    def validate_sku(self, value):
        value = str(value).strip()
        if not value:
            raise serializers.ValidationError("SKU cannot be empty.")
        if self.instance is None:
            # On create, check for duplicate SKU
            if Product.objects.filter(sku=value).exists():
                raise DuplicateError(f"Product with SKU '{value}' already exists.")
        return value

    def create(self, validated_data):
        product = Product.objects.create(**validated_data)
        # A product created via POST gets an Inventory row with quantity 0
        Inventory.objects.create(product=product, quantity=0)
        return product

    def update(self, instance, validated_data):
        # sku cannot change
        validated_data.pop("sku", None)
        validated_data.pop("stock", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class InventoryUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_quantity(self, value):
        raw_val = self.initial_data.get("quantity")
        # Reject booleans (in Python, isinstance(True, int) is True)
        if isinstance(raw_val, bool):
            raise serializers.ValidationError("Quantity must be a valid integer, not a boolean.")
        # Reject floats and string representations of numbers
        if not isinstance(raw_val, int):
            raise serializers.ValidationError("Quantity must be a real integer.")
        if value < 0:
            raise serializers.ValidationError("Quantity must be greater than or equal to 0.")
        return value
