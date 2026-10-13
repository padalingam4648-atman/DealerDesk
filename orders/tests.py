from decimal import Decimal
import threading
from django.db import connections
from django.test import TestCase, TransactionTestCase
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
from orders.services import (
    create_draft_order,
    generate_order_number,
    confirm_order,
    cancel_order,
    dispatch_order,
    deliver_order,
)


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

    def test_multiple_lines_gst_rounding_edge_cases(self):
        # Multiple line items with .xx5 rounding edge cases
        # Line 1: 1.25 * 1 = 1.25 -> tax 0.23, line_total 1.48
        # Line 2: 2.75 * 1 = 2.75 -> tax 0.50, line_total 3.25
        # Line 3: 3.25 * 1 = 3.25 -> tax 0.59, line_total 3.84
        # Line 4: 0.25 * 1 = 0.25 -> tax 0.05, line_total 0.30
        l1 = calculate_line(Decimal("1.25"), 1)
        l2 = calculate_line(Decimal("2.75"), 1)
        l3 = calculate_line(Decimal("3.25"), 1)
        l4 = calculate_line(Decimal("0.25"), 1)

        self.assertEqual(l1.line_tax, Decimal("0.23"))
        self.assertEqual(l2.line_tax, Decimal("0.50"))
        self.assertEqual(l3.line_tax, Decimal("0.59"))
        self.assertEqual(l4.line_tax, Decimal("0.05"))

        totals = calculate_order_totals([l1, l2, l3, l4])
        # subtotal = 1.25 + 2.75 + 3.25 + 0.25 = 7.50
        # tax_total = 0.23 + 0.50 + 0.59 + 0.05 = 1.37
        # grand_total = 7.50 + 1.37 = 8.87
        self.assertEqual(totals.subtotal, Decimal("7.50"))
        self.assertEqual(totals.tax_total, Decimal("1.37"))
        self.assertEqual(totals.grand_total, Decimal("8.87"))


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
        self.prod1.inventory.refresh_from_db()
        self.prod2.inventory.refresh_from_db()
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


class OrderLifecycleTestCase(TestCase):
    """
    Tests for Part A2 Order Engine status transitions, stock rules, price locks, and editing.
    """
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-LC-01",
            name="Lifecycle Motors",
            credit_limit=Decimal("100000.00"),
        )
        self.p1 = Product.objects.create(
            sku="LC-101",
            name="Front Brake Caliper",
            price=Decimal("1500.00"),
        )
        self.inv1 = Inventory.objects.create(product=self.p1, quantity=10)

        self.p2 = Product.objects.create(
            sku="LC-102",
            name="Clutch Cable",
            price=Decimal("250.00"),
        )
        self.inv2 = Inventory.objects.create(product=self.p2, quantity=5)

    def test_full_valid_lifecycle(self):
        # 1. Create DRAFT
        payload = {
            "dealer_id": self.dealer.id,
            "items": [
                {"sku": "LC-101", "quantity": 2},
                {"sku": "LC-102", "quantity": 3},
            ],
        }
        res_create = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(res_create.status_code, 201)
        order_num = res_create.json()["order_number"]
        self.assertEqual(res_create.json()["status"], "DRAFT")

        # Inventory unchanged in DRAFT
        self.inv1.refresh_from_db()
        self.inv2.refresh_from_db()
        self.assertEqual(self.inv1.quantity, 10)
        self.assertEqual(self.inv2.quantity, 5)

        # 2. Confirm: DRAFT -> CONFIRMED
        res_conf = self.client.post(f"/api/orders/{order_num}/confirm/")
        self.assertEqual(res_conf.status_code, 200)
        self.assertEqual(res_conf.json()["status"], "CONFIRMED")

        # Inventory deducted exactly
        self.inv1.refresh_from_db()
        self.inv2.refresh_from_db()
        self.assertEqual(self.inv1.quantity, 8)  # 10 - 2 = 8
        self.assertEqual(self.inv2.quantity, 2)  # 5 - 3 = 2

        # 3. Dispatch: CONFIRMED -> DISPATCHED
        res_disp = self.client.post(f"/api/orders/{order_num}/dispatch/")
        self.assertEqual(res_disp.status_code, 200)
        self.assertEqual(res_disp.json()["status"], "DISPATCHED")

        # 4. Deliver: DISPATCHED -> DELIVERED
        res_deliv = self.client.post(f"/api/orders/{order_num}/deliver/")
        self.assertEqual(res_deliv.status_code, 200)
        self.assertEqual(res_deliv.json()["status"], "DELIVERED")

    def test_cancel_draft_order_leaves_stock_untouched(self):
        order = create_draft_order(
            self.dealer.id,
            [{"sku": "LC-101", "quantity": 3}],
        )
        self.assertEqual(self.inv1.quantity, 10)

        res_cancel = self.client.post(f"/api/orders/{order.order_number}/cancel/")
        self.assertEqual(res_cancel.status_code, 200)
        self.assertEqual(res_cancel.json()["status"], "CANCELLED")

        self.inv1.refresh_from_db()
        self.assertEqual(self.inv1.quantity, 10)  # Stock untouched

    def test_cancel_confirmed_order_restores_stock_exactly_once(self):
        order = create_draft_order(
            self.dealer.id,
            [{"sku": "LC-101", "quantity": 4}],
        )
        res_conf = self.client.post(f"/api/orders/{order.order_number}/confirm/")
        self.assertEqual(res_conf.status_code, 200)
        self.inv1.refresh_from_db()
        self.assertEqual(self.inv1.quantity, 6)

        # Cancel confirmed order: restores stock
        res_cancel = self.client.post(f"/api/orders/{order.order_number}/cancel/")
        self.assertEqual(res_cancel.status_code, 200)
        self.assertEqual(res_cancel.json()["status"], "CANCELLED")

        self.inv1.refresh_from_db()
        self.assertEqual(self.inv1.quantity, 10)  # Restored from 6 to 10

        # Attempt to cancel again (double cancel) must fail with 409 INVALID_TRANSITION
        res_cancel_again = self.client.post(f"/api/orders/{order.order_number}/cancel/")
        self.assertEqual(res_cancel_again.status_code, 409)
        self.assertEqual(res_cancel_again.json()["error"]["code"], "INVALID_TRANSITION")

        # Stock is NOT restored twice
        self.inv1.refresh_from_db()
        self.assertEqual(self.inv1.quantity, 10)

    def test_invalid_transitions(self):
        order = create_draft_order(
            self.dealer.id,
            [{"sku": "LC-101", "quantity": 1}],
        )
        n = order.order_number

        # From DRAFT: dispatch or deliver are invalid
        r = self.client.post(f"/api/orders/{n}/dispatch/")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "INVALID_TRANSITION")

        r = self.client.post(f"/api/orders/{n}/deliver/")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "INVALID_TRANSITION")

        # Transition to CONFIRMED
        self.client.post(f"/api/orders/{n}/confirm/")

        # From CONFIRMED: confirm or deliver are invalid
        r = self.client.post(f"/api/orders/{n}/confirm/")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "INVALID_TRANSITION")

        r = self.client.post(f"/api/orders/{n}/deliver/")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "INVALID_TRANSITION")

        # Transition to DISPATCHED
        self.client.post(f"/api/orders/{n}/dispatch/")

        # From DISPATCHED: confirm, dispatch, and cancel are invalid
        r = self.client.post(f"/api/orders/{n}/confirm/")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "INVALID_TRANSITION")

        r = self.client.post(f"/api/orders/{n}/dispatch/")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "INVALID_TRANSITION")

        r = self.client.post(f"/api/orders/{n}/cancel/")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "INVALID_TRANSITION")

        # Transition to DELIVERED (final)
        self.client.post(f"/api/orders/{n}/deliver/")

        # From DELIVERED: any action is invalid
        for action in ("confirm", "dispatch", "deliver", "cancel"):
            r = self.client.post(f"/api/orders/{n}/{action}/")
            self.assertEqual(r.status_code, 409)
            self.assertEqual(r.json()["error"]["code"], "INVALID_TRANSITION")

    def test_edit_draft_order_and_order_locked(self):
        order = create_draft_order(
            self.dealer.id,
            [{"sku": "LC-101", "quantity": 1}],
        )
        n = order.order_number

        # PUT replaces items while DRAFT
        edit_payload = {
            "items": [
                {"sku": "LC-102", "quantity": 4},
            ]
        }
        res_edit = self.client.put(f"/api/orders/{n}/", edit_payload, format="json")
        self.assertEqual(res_edit.status_code, 200)
        data = res_edit.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["sku"], "LC-102")
        self.assertEqual(data["items"][0]["quantity"], 4)
        # 4 * 250.00 = 1000.00, tax = 180.00, total = 1180.00
        self.assertEqual(data["subtotal"], "1000.00")
        self.assertEqual(data["tax_total"], "180.00")
        self.assertEqual(data["grand_total"], "1180.00")

        # Confirm the order
        self.client.post(f"/api/orders/{n}/confirm/")

        # Editing a non-DRAFT order must return 409 ORDER_LOCKED
        res_locked = self.client.put(f"/api/orders/{n}/", edit_payload, format="json")
        self.assertEqual(res_locked.status_code, 409)
        self.assertEqual(res_locked.json()["error"]["code"], "ORDER_LOCKED")

    def test_confirm_all_or_nothing_insufficient_stock(self):
        # p1 has 10 units, p2 has 5 units
        # Request 4 of p1 (available: 10), 10 of p2 (available: 5)
        order = create_draft_order(
            self.dealer.id,
            [
                {"sku": "LC-101", "quantity": 4},
                {"sku": "LC-102", "quantity": 10},
            ],
        )
        n = order.order_number

        res = self.client.post(f"/api/orders/{n}/confirm/")
        self.assertEqual(res.status_code, 409)
        err = res.json()["error"]
        self.assertEqual(err["code"], "INSUFFICIENT_STOCK")
        self.assertIn("Insufficient stock for Clutch Cable", err["message"])
        self.assertIn("Available: 5, Requested: 10", err["message"])
        self.assertEqual(len(err["details"]), 1)
        self.assertEqual(err["details"][0], {
            "sku": "LC-102",
            "requested": 10,
            "available": 5,
        })

        # All-or-nothing: NO stock changed for ANY line
        self.inv1.refresh_from_db()
        self.inv2.refresh_from_db()
        self.assertEqual(self.inv1.quantity, 10)
        self.assertEqual(self.inv2.quantity, 5)

        # Order remains in DRAFT status
        order.refresh_from_db()
        self.assertEqual(order.status, "DRAFT")

    def test_price_lock_on_confirm(self):
        order = create_draft_order(
            self.dealer.id,
            [{"sku": "LC-101", "quantity": 2}],
        )
        n = order.order_number

        # Initial price is 1500.00 -> subtotal 3000.00
        r_get1 = self.client.get(f"/api/orders/{n}/")
        self.assertEqual(r_get1.json()["subtotal"], "3000.00")

        # Change catalogue price before confirm -> DRAFT updates dynamically
        self.p1.price = Decimal("1800.00")
        self.p1.save()
        r_get2 = self.client.get(f"/api/orders/{n}/")
        self.assertEqual(r_get2.json()["subtotal"], "3600.00")

        # Confirm the order -> unit_price is locked permanently at 1800.00
        res_conf = self.client.post(f"/api/orders/{n}/confirm/")
        self.assertEqual(res_conf.status_code, 200)
        self.assertEqual(res_conf.json()["subtotal"], "3600.00")

        # Change catalogue price after confirm -> CONFIRMED order remains frozen
        self.p1.price = Decimal("2500.00")
        self.p1.save()

        r_get3 = self.client.get(f"/api/orders/{n}/")
        self.assertEqual(r_get3.json()["subtotal"], "3600.00")
        self.assertEqual(r_get3.json()["items"][0]["unit_price"], "1800.00")

    def test_non_existent_order_actions_return_404(self):
        for endpoint in ("confirm", "dispatch", "deliver", "cancel"):
            res = self.client.post(f"/api/orders/ORD-99999999-9999/{endpoint}/")
            self.assertEqual(res.status_code, 404)
            self.assertEqual(res.json()["error"]["code"], "NOT_FOUND")


class OrderIdempotencyTestCase(TestCase):
    """
    Tests for Idempotency-Key support on POST /api/orders/ (Contract Section 7.5).
    """
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-IDEM-01",
            name="Idempotency Dealership",
            credit_limit=Decimal("50000.00"),
        )
        self.p = Product.objects.create(
            sku="IDEM-101",
            name="Spark Plug",
            price=Decimal("120.00"),
        )
        Inventory.objects.create(product=self.p, quantity=50)

    def test_sequential_replay_returns_original_order(self):
        payload = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "IDEM-101", "quantity": 3}],
        }
        # First request with Idempotency-Key
        r1 = self.client.post(
            "/api/orders/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="idem-test-key-01",
        )
        self.assertEqual(r1.status_code, 201)
        ord_num = r1.json()["order_number"]

        # Duplicate request with SAME key and SAME body
        r2 = self.client.post(
            "/api/orders/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="idem-test-key-01",
        )
        # Returns 200 with the original order and creates nothing new
        self.assertIn(r2.status_code, [200, 201])
        self.assertEqual(r2.json()["order_number"], ord_num)

        # Total orders in database must be exactly 1
        self.assertEqual(Order.objects.filter(dealer=self.dealer).count(), 1)

    def test_idempotency_conflict_with_different_body(self):
        payload1 = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "IDEM-101", "quantity": 3}],
        }
        r1 = self.client.post(
            "/api/orders/",
            payload1,
            format="json",
            HTTP_IDEMPOTENCY_KEY="idem-conflict-key",
        )
        self.assertEqual(r1.status_code, 201)

        # Same key with DIFFERENT payload (quantity 5)
        payload2 = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "IDEM-101", "quantity": 5}],
        }
        r2 = self.client.post(
            "/api/orders/",
            payload2,
            format="json",
            HTTP_IDEMPOTENCY_KEY="idem-conflict-key",
        )
        self.assertEqual(r2.status_code, 409)
        self.assertEqual(r2.json()["error"]["code"], "IDEMPOTENCY_CONFLICT")

    def test_no_idempotency_key_creates_distinct_orders(self):
        payload = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "IDEM-101", "quantity": 1}],
        }
        r1 = self.client.post("/api/orders/", payload, format="json")
        r2 = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.json()["order_number"], r2.json()["order_number"])
        self.assertEqual(Order.objects.filter(dealer=self.dealer).count(), 2)


class OrderConcurrencyTestCase(TransactionTestCase):
    """
    Tests concurrency guarantees using real threads against real transactions:
    - Multiple threads confirming for last K units (preventing overselling)
    - Two threads confirming the SAME order
    - Two threads cancelling the SAME order
    - Concurrent creation with same idempotency key
    - Concurrent order number generation
    """
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from django.db import connection
        if connection.vendor == "sqlite":
            with connection.cursor() as c:
                c.execute("PRAGMA journal_mode = WAL;")
                c.execute("PRAGMA busy_timeout = 10000;")

    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-CONC-01",
            name="Concurrency Dealership",
            credit_limit=Decimal("500000.00"),
        )
        self.product = Product.objects.create(
            sku="CONC-901",
            name="Race Chain Kit",
            price=Decimal("4500.00"),
        )
        self.inventory = Inventory.objects.create(
            product=self.product,
            quantity=5,  # Only 5 units in stock!
        )

    def test_concurrency_oversell_prevention(self):
        # We have 5 units in stock.
        # We create 6 draft orders, each requesting 2 units (6 * 2 = 12 requested).
        # At most 2 orders can be confirmed (2 * 2 = 4 units <= 5; 3 * 2 = 6 > 5).
        draft_orders = [
            create_draft_order(self.dealer.id, [{"sku": "CONC-901", "quantity": 2}])
            for _ in range(6)
        ]

        results = []
        errors = []

        def worker(order_num):
            connections.close_all()
            from django.db import connection
            if connection.vendor == "sqlite":
                with connection.cursor() as c:
                    c.execute("PRAGMA busy_timeout = 10000;")
            try:
                c = APIClient()
                res = c.post(f"/api/orders/{order_num}/confirm/")
                results.append((order_num, res.status_code, res.json()))
            except Exception as e:
                errors.append(e)
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=worker, args=(o.order_number,))
            for o in draft_orders
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 6)

        success_count = sum(1 for _, code, _ in results if code == 200)
        insufficient_count = sum(
            1 for _, code, b in results
            if code == 409 and b.get("error", {}).get("code") == "INSUFFICIENT_STOCK"
        )

        # Exactly 2 orders must succeed (2 * 2 = 4 units)
        self.assertEqual(success_count, 2)
        # Exactly 4 orders must fail with INSUFFICIENT_STOCK
        self.assertEqual(insufficient_count, 4)

        # Stock in DB must be exactly 1 (5 - 4 = 1), never negative!
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 1)
        self.assertGreaterEqual(self.inventory.quantity, 0)

    def test_concurrency_same_order_confirm(self):
        # Single order confirmed by 2 threads simultaneously
        order = create_draft_order(
            self.dealer.id,
            [{"sku": "CONC-901", "quantity": 2}],
        )
        results = []

        def worker():
            connections.close_all()
            from django.db import connection
            if connection.vendor == "sqlite":
                with connection.cursor() as c:
                    c.execute("PRAGMA busy_timeout = 10000;")
            try:
                c = APIClient()
                res = c.post(f"/api/orders/{order.order_number}/confirm/")
                results.append((res.status_code, res.json()))
            finally:
                connections.close_all()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(results), 2)
        status_codes = sorted([code for code, _ in results])
        # Exactly one succeeds (200), the other receives 409 INVALID_TRANSITION
        self.assertEqual(status_codes, [200, 409])

        # Stock deducted exactly once (5 - 2 = 3)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 3)

    def test_concurrency_same_order_cancel_restores_once(self):
        # Confirm order first
        order = create_draft_order(
            self.dealer.id,
            [{"sku": "CONC-901", "quantity": 2}],
        )
        confirm_order(order.order_number)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 3)

        # Two threads simultaneously cancel the confirmed order
        results = []

        def worker():
            connections.close_all()
            from django.db import connection
            if connection.vendor == "sqlite":
                with connection.cursor() as c:
                    c.execute("PRAGMA busy_timeout = 10000;")
            try:
                c = APIClient()
                res = c.post(f"/api/orders/{order.order_number}/cancel/")
                results.append((res.status_code, res.json()))
            finally:
                connections.close_all()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(results), 2)
        status_codes = sorted([code for code, _ in results])
        # Exactly one succeeds (200), the other receives 409 INVALID_TRANSITION
        self.assertEqual(status_codes, [200, 409])

        # Stock restored exactly once back to 5 (never to 7!)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 5)

    def test_concurrency_parallel_idempotency(self):
        # 5 threads sending POST /api/orders/ with the SAME idempotency key simultaneously
        key = "parallel-key-xyz"
        payload = {
            "dealer_id": self.dealer.id,
            "items": [{"sku": "CONC-901", "quantity": 1}],
        }
        results = []

        def worker():
            connections.close_all()
            from django.db import connection
            if connection.vendor == "sqlite":
                with connection.cursor() as c:
                    c.execute("PRAGMA busy_timeout = 10000;")
            try:
                c = APIClient()
                res = c.post(
                    "/api/orders/",
                    payload,
                    format="json",
                    HTTP_IDEMPOTENCY_KEY=key,
                )
                results.append((res.status_code, res.json()))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 5)
        # All requests must succeed with 200 or 201
        for code, b in results:
            self.assertIn(code, [200, 201])

        # All must refer to the EXACT SAME order number
        order_numbers = {b["order_number"] for _, b in results}
        self.assertEqual(len(order_numbers), 1)

        # Exactly 1 order created in DB
        self.assertEqual(Order.objects.filter(dealer=self.dealer).count(), 1)

    def test_concurrency_order_number_uniqueness(self):
        # 10 threads generating order numbers concurrently
        order_numbers = []
        errors = []

        def worker():
            connections.close_all()
            from django.db import connection
            if connection.vendor == "sqlite":
                with connection.cursor() as c:
                    c.execute("PRAGMA busy_timeout = 10000;")
            try:
                num = generate_order_number()
                order_numbers.append(num)
            except Exception as e:
                errors.append(e)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(order_numbers), 10)
        # All generated order numbers must be completely unique
        self.assertEqual(len(set(order_numbers)), 10)
