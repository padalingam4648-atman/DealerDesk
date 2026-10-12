from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from catalog.models import Product, Inventory
from dealers.models import Dealer
from orders.models import Order, OrderItem
from orders.money import (
    calculate_line,
    calculate_line_tax,
    calculate_order_totals,
    quantize_money,
)
from orders.services import create_draft_order, generate_order_number


class MoneyLogicTestCase(TestCase):
    def test_gst_rounding_half_up(self):
        # Edge case: subtotal * 0.18 ends in exactly .xx5
        # Example: 1.25 * 0.18 = 0.225 -> ROUND_HALF_UP rounds to 0.23
        subtotal = Decimal("1.25")
        tax = calculate_line_tax(subtotal)
        self.assertEqual(tax, Decimal("0.23"))

        # Example: 2.75 * 0.18 = 0.495 -> rounds to 0.50
        subtotal2 = Decimal("2.75")
        tax2 = calculate_line_tax(subtotal2)
        self.assertEqual(tax2, Decimal("0.50"))

        # Example: 3.25 * 0.18 = 0.585 -> rounds to 0.59
        subtotal3 = Decimal("3.25")
        tax3 = calculate_line_tax(subtotal3)
        self.assertEqual(tax3, Decimal("0.59"))

    def test_line_totals_and_order_totals(self):
        line1 = calculate_line(Decimal("1459.50"), 3)
        # 1459.50 * 3 = 4378.50
        # tax = 4378.50 * 0.18 = 788.13
        # total = 4378.50 + 788.13 = 5166.63
        self.assertEqual(line1.line_subtotal, Decimal("4378.50"))
        self.assertEqual(line1.line_tax, Decimal("788.13"))
        self.assertEqual(line1.line_total, Decimal("5166.63"))

        order_totals = calculate_order_totals([line1])
        self.assertEqual(order_totals.subtotal, Decimal("4378.50"))
        self.assertEqual(order_totals.tax_total, Decimal("788.13"))
        self.assertEqual(order_totals.grand_total, Decimal("5166.63"))


class OrderApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-TEST-01",
            name="Test Dealership",
            credit_limit=Decimal("50000.00"),
        )
        self.prod1 = Product.objects.create(
            sku="TST-1001",
            name="Brake Disc",
            price=Decimal("100.00"),
        )
        Inventory.objects.create(product=self.prod1, quantity=50)

        self.prod2 = Product.objects.create(
            sku="TST-1002",
            name="Air Filter",
            price=Decimal("200.00"),
        )
        Inventory.objects.create(product=self.prod2, quantity=20)

    def test_create_draft_order_success(self):
        payload = {
            "dealer_id": self.dealer.id,
            "items": [
                {"sku": "TST-1001", "quantity": 2},
                {"sku": "TST-1002", "quantity": 1},
            ],
        }
        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data["order_number"].startswith("ORD-"))
        self.assertEqual(data["dealer_id"], self.dealer.id)
        self.assertEqual(data["status"], "DRAFT")
        self.assertEqual(len(data["items"]), 2)
        # subtotal: 2*100 + 1*200 = 400.00
        # tax: 200*0.18 = 36.00, 200*0.18 = 36.00 -> 72.00
        # grand_total = 472.00
        self.assertEqual(data["subtotal"], "400.00")
        self.assertEqual(data["tax_total"], "72.00")
        self.assertEqual(data["grand_total"], "472.00")

        # Inventory should NOT be modified for DRAFT
        self.assertEqual(self.prod1.inventory.quantity, 50)
        self.assertEqual(self.prod2.inventory.quantity, 20)

    def test_draft_order_reflects_current_product_price(self):
        order = create_draft_order(
            self.dealer.id,
            [{"sku": "TST-1001", "quantity": 1}],
        )
        # Price is initially 100.00
        res1 = self.client.get(f"/api/orders/{order.order_number}/")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["subtotal"], "100.00")

        # Change catalogue price to 150.00
        self.prod1.price = Decimal("150.00")
        self.prod1.save()

        # DRAFT order dynamically computes price at read time
        res2 = self.client.get(f"/api/orders/{order.order_number}/")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["subtotal"], "150.00")
        self.assertEqual(res2.json()["items"][0]["unit_price"], "150.00")

    def test_order_number_format_and_sequence(self):
        num1 = generate_order_number()
        num2 = generate_order_number()
        import re
        self.assertTrue(re.match(r"^ORD-\d{8}-\d{4}$", num1))
        self.assertTrue(re.match(r"^ORD-\d{8}-\d{4}$", num2))
        seq1 = int(num1.split("-")[-1])
        seq2 = int(num2.split("-")[-1])
        self.assertEqual(seq2, seq1 + 1)

    def test_validation_errors(self):
        # 1. Empty items
        r1 = self.client.post("/api/orders/", {"dealer_id": self.dealer.id, "items": []}, format="json")
        self.assertEqual(r1.status_code, 400)
        self.assertEqual(r1.json()["error"]["code"], "VALIDATION_ERROR")

        # 2. Quantity 0
        r2 = self.client.post("/api/orders/", {"dealer_id": self.dealer.id, "items": [{"sku": "TST-1001", "quantity": 0}]}, format="json")
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.json()["error"]["code"], "VALIDATION_ERROR")

        # 3. Quantity bool (True)
        r3 = self.client.post("/api/orders/", {"dealer_id": self.dealer.id, "items": [{"sku": "TST-1001", "quantity": True}]}, format="json")
        self.assertEqual(r3.status_code, 400)
        self.assertEqual(r3.json()["error"]["code"], "VALIDATION_ERROR")

        # 4. Duplicate SKU in items
        r4 = self.client.post("/api/orders/", {"dealer_id": self.dealer.id, "items": [
            {"sku": "TST-1001", "quantity": 1},
            {"sku": "TST-1001", "quantity": 2},
        ]}, format="json")
        self.assertEqual(r4.status_code, 400)
        self.assertEqual(r4.json()["error"]["code"], "VALIDATION_ERROR")

        # 5. Unknown SKU
        r5 = self.client.post("/api/orders/", {"dealer_id": self.dealer.id, "items": [{"sku": "NON-EXISTENT", "quantity": 1}]}, format="json")
        self.assertEqual(r5.status_code, 400)
        self.assertEqual(r5.json()["error"]["code"], "VALIDATION_ERROR")

        # 6. Unknown dealer
        r6 = self.client.post("/api/orders/", {"dealer_id": 999999, "items": [{"sku": "TST-1001", "quantity": 1}]}, format="json")
        self.assertEqual(r6.status_code, 400)
        self.assertEqual(r6.json()["error"]["code"], "VALIDATION_ERROR")
