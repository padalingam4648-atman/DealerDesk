from django.test import TestCase
from rest_framework.test import APIClient


class CommonErrorHandlingTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_unmapped_api_route_returns_404_in_standard_shape(self):
        response = self.client.get("/api/completely-unknown-route/")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "NOT_FOUND")
        self.assertTrue(isinstance(data["error"]["details"], list))

    def test_malformed_json_returns_400_validation_error(self):
        response = self.client.post(
            "/api/products/",
            data="{malformed json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")
        self.assertTrue(isinstance(data["error"]["details"], list))
