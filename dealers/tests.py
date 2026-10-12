from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from dealers.models import Dealer


class DealerApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_dealer_create_and_duplicate_code(self):
        payload = {
            "dealer_code": "DLR-ABC",
            "name": "ABC Auto Hub",
            "city": "Bengaluru",
            "phone": "9876543210",
            "credit_limit": "250000.00",
        }
        r1 = self.client.post("/api/dealers/", payload, format="json")
        self.assertEqual(r1.status_code, 201)
        data = r1.json()
        self.assertEqual(data["dealer_code"], "DLR-ABC")
        self.assertEqual(data["credit_limit"], "250000.00")

        # Duplicate code -> 409 DUPLICATE
        r2 = self.client.post("/api/dealers/", payload, format="json")
        self.assertEqual(r2.status_code, 409)
        self.assertEqual(r2.json()["error"]["code"], "DUPLICATE")

    def test_dealer_detail_and_404(self):
        dealer = Dealer.objects.create(
            dealer_code="DLR-XYZ",
            name="XYZ Motors",
            credit_limit=Decimal("10000.00"),
        )
        r1 = self.client.get(f"/api/dealers/{dealer.id}/")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["dealer_code"], "DLR-XYZ")

        r2 = self.client.get("/api/dealers/999999/")
        self.assertEqual(r2.status_code, 404)
        self.assertEqual(r2.json()["error"]["code"], "NOT_FOUND")
