from rest_framework import serializers
from common.money import format_money
from orders.models import Order, OrderItem
from orders.money import calculate_line, calculate_order_totals


class OrderItemReadSerializer(serializers.Serializer):
    sku = serializers.CharField(source="product.sku")
    name = serializers.CharField(source="product.name")
    quantity = serializers.IntegerField()
    unit_price = serializers.CharField()
    line_subtotal = serializers.CharField()
    line_tax = serializers.CharField()
    line_total = serializers.CharField()


class OrderSerializer(serializers.ModelSerializer):
    dealer_id = serializers.IntegerField(source="dealer.id")
    items = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    tax_total = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    class Meta:
        model = Order
        fields = [
            "order_number",
            "dealer_id",
            "status",
            "items",
            "subtotal",
            "tax_total",
            "grand_total",
            "created_at",
            "updated_at",
        ]

    def _get_computed_lines_and_totals(self, obj):
        # Cache computation on the model instance to avoid recalculating across methods
        if hasattr(obj, "_computed_totals"):
            return obj._computed_items_data, obj._computed_totals

        items_data = []
        line_totals_list = []

        # Iterate through pre-fetched items
        for item in obj.items.all():
            # While DRAFT, unit_price is the product's current catalogue price
            if obj.status == "DRAFT" or item.unit_price is None:
                price = item.product.price
            else:
                price = item.unit_price

            calc = calculate_line(price, item.quantity)
            line_totals_list.append(calc)

            items_data.append({
                "sku": item.product.sku,
                "name": item.product.name,
                "quantity": item.quantity,
                "unit_price": format_money(calc.unit_price),
                "line_subtotal": format_money(calc.line_subtotal),
                "line_tax": format_money(calc.line_tax),
                "line_total": format_money(calc.line_total),
            })

        totals = calculate_order_totals(line_totals_list)
        obj._computed_items_data = items_data
        obj._computed_totals = totals
        return items_data, totals

    def get_items(self, obj):
        items_data, _ = self._get_computed_lines_and_totals(obj)
        return items_data

    def get_subtotal(self, obj):
        _, totals = self._get_computed_lines_and_totals(obj)
        return format_money(totals.subtotal)

    def get_tax_total(self, obj):
        _, totals = self._get_computed_lines_and_totals(obj)
        return format_money(totals.tax_total)

    def get_grand_total(self, obj):
        _, totals = self._get_computed_lines_and_totals(obj)
        return format_money(totals.grand_total)
