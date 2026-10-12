from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from catalog.models import Product, Inventory


class CatalogApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_product_create_and_duplicate_sku(self):
        payload = {
            "sku": "PROD-101",
            "name": "Brake Lever",
            "category": "Controls",
            "brand": "Bosch",
            "vehicle_fitment": "Universal",
            "price": "499.50",
            "description": "High quality lever",
        }
        res1 = self.client.post("/api/products/", payload, format="json")
        self.assertEqual(res1.status_code, 201)
        data = res1.json()
        self.assertEqual(data["sku"], "PROD-101")
        self.assertEqual(data["price"], "499.50")
        self.assertEqual(data["stock"], 0)

        # Duplicate SKU -> 409 DUPLICATE
        res2 = self.client.post("/api/products/", payload, format="json")
        self.assertEqual(res2.status_code, 409)
        self.assertEqual(res2.json()["error"]["code"], "DUPLICATE")

    def test_price_validation(self):
        # 1. Price <= 0
        r1 = self.client.post("/api/products/", {
            "sku": "P-01", "name": "Item", "price": "0.00"
        }, format="json")
        self.assertEqual(r1.status_code, 400)
        self.assertEqual(r1.json()["error"]["code"], "VALIDATION_ERROR")

        # 2. Negative price
        r2 = self.client.post("/api/products/", {
            "sku": "P-02", "name": "Item", "price": "-10.00"
        }, format="json")
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.json()["error"]["code"], "VALIDATION_ERROR")

        # 3. More than 2 decimals
        r3 = self.client.post("/api/products/", {
            "sku": "P-03", "name": "Item", "price": "10.999"
        }, format="json")
        self.assertEqual(r3.status_code, 400)
        self.assertEqual(r3.json()["error"]["code"], "VALIDATION_ERROR")

        # 4. Valid price
        r4 = self.client.post("/api/products/", {
            "sku": "P-04", "name": "Item", "price": "10.50"
        }, format="json")
        self.assertEqual(r4.status_code, 201)

    def test_patch_product_sku_and_stock_immutable(self):
        prod = Product.objects.create(
            sku="PATCH-01",
            name="Clutch Cable",
            price=Decimal("150.00"),
        )
        Inventory.objects.create(product=prod, quantity=25)

        patch_res = self.client.patch("/api/products/PATCH-01/", {
            "sku": "NEW-SKU",
            "price": "175.00",
            "stock": 999,
        }, format="json")
        self.assertEqual(patch_res.status_code, 200)
        data = patch_res.json()
        self.assertEqual(data["sku"], "PATCH-01")  # sku did not change
        self.assertEqual(data["price"], "175.00")
        self.assertEqual(data["stock"], 25)  # stock did not change

    def test_inventory_put_validation(self):
        prod = Product.objects.create(
            sku="INV-01",
            name="Spark Plug",
            price=Decimal("120.00"),
        )
        Inventory.objects.create(product=prod, quantity=10)

        # 1. Valid update
        r1 = self.client.put("/api/inventory/INV-01/", {"quantity": 40, "reason": "audit"}, format="json")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json(), {"sku": "INV-01", "quantity": 40})

        # 2. Reject negative
        r2 = self.client.put("/api/inventory/INV-01/", {"quantity": -5}, format="json")
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.json()["error"]["code"], "VALIDATION_ERROR")

        # 3. Reject boolean
        r3 = self.client.put("/api/inventory/INV-01/", {"quantity": True}, format="json")
        self.assertEqual(r3.status_code, 400)
        self.assertEqual(r3.json()["error"]["code"], "VALIDATION_ERROR")

        # 4. Reject float
        r4 = self.client.put("/api/inventory/INV-01/", {"quantity": 12.5}, format="json")
        self.assertEqual(r4.status_code, 400)
        self.assertEqual(r4.json()["error"]["code"], "VALIDATION_ERROR")

        # 5. Reject string
        r5 = self.client.put("/api/inventory/INV-01/", {"quantity": "50"}, format="json")
        self.assertEqual(r5.status_code, 400)
        self.assertEqual(r5.json()["error"]["code"], "VALIDATION_ERROR")

        # 6. Unknown SKU -> 404
        r6 = self.client.put("/api/inventory/UNKNOWN-SKU/", {"quantity": 10}, format="json")
        self.assertEqual(r6.status_code, 404)
        self.assertEqual(r6.json()["error"]["code"], "NOT_FOUND")
