from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from catalog.models import Product, Inventory
from dealers.models import Dealer


class CoreAndSeedTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_check(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_seed_data_idempotency_and_preserves_stock(self):
        call_command("seed_data")
        self.assertEqual(Product.objects.count(), 600)
        self.assertEqual(Dealer.objects.count(), 25)

        # Modify live stock for one product
        prod = Product.objects.first()
        prod.inventory.quantity = 9999
        prod.inventory.save()

        # Re-run seed_data
        call_command("seed_data")

        # Counts must remain identical
        self.assertEqual(Product.objects.count(), 600)
        self.assertEqual(Dealer.objects.count(), 25)

        # Modified live stock must NOT be reset by re-run
        prod.inventory.refresh_from_db()
        self.assertEqual(prod.inventory.quantity, 9999)
