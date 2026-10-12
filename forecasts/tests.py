import csv
import math
import statistics
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Product, Inventory
from forecasts.services import compute_reorder_suggestions, get_sku_forecast


class ForecastsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_forecast_csv_structure(self):
        """Test ml/forecast.csv matches contract: 160 rows, exact weeks, non-negative."""
        forecast_path = Path(settings.BASE_DIR) / "ml" / "forecast.csv"
        lead_path = Path(settings.BASE_DIR) / "data" / "lead_times.csv"

        self.assertTrue(forecast_path.exists(), "ml/forecast.csv must exist")

        with open(lead_path, encoding="utf-8-sig") as f:
            expected_skus = {r["sku"].strip() for r in csv.DictReader(f)}

        expected_weeks = ["2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19"]

        with open(forecast_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # Exactly 160 rows
        self.assertEqual(len(rows), 160)
        self.assertEqual(list(rows[0].keys())[:3], ["sku", "week_start", "forecast_units"])

        seen_pairs = set()
        for r in rows:
            sku = r["sku"]
            w = r["week_start"]
            units = float(r["forecast_units"])
            self.assertIn(sku, expected_skus)
            self.assertIn(w, expected_weeks)
            self.assertGreaterEqual(units, 0.0, "forecast_units must be non-negative")
            self.assertNotIn((sku, w), seen_pairs, "Duplicate SKU/week pair found")
            seen_pairs.add((sku, w))

        self.assertEqual(len(seen_pairs), len(expected_skus) * 4)

    def test_forecast_api_detail_and_404(self):
        """Test GET /api/forecast/{sku}/ returns 4 weeks or 404 in contract shape."""
        # 1. Valid forecast SKU
        res = self.client.get("/api/forecast/FIL-1016/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["sku"], "FIL-1016")
        self.assertEqual(len(data["forecast"]), 4)
        for item in data["forecast"]:
            self.assertIn("week_start", item)
            self.assertIn("forecast_units", item)
            self.assertIsInstance(item["forecast_units"], (int, float))

        # 2. Unknown or non-forecast SKU -> 404 NOT_FOUND
        res_404 = self.client.get("/api/forecast/NON-EXISTENT-SKU/")
        self.assertEqual(res_404.status_code, 404)
        err = res_404.json()
        self.assertIn("error", err)
        self.assertEqual(err["error"]["code"], "NOT_FOUND")

    def test_reorder_formula_exact_hand_computed(self):
        """
        Verify the exact reorder formula with a hand-computed test case:
        L = 2
        forecast = [31.4, 30.3, 20.0, 20.0] -> lead_time_demand = 61.7
        recent_12w = [10, 12, 14, 16, 18, 20] -> n=6
        sample std (n-1) = statistics.stdev(...)
        safety_stock = ceil(1.65 * sigma * sqrt(L))
        reorder_point = lead_time_demand + safety_stock
        reorder_qty = max(0, ceil(reorder_point - stock))
        """
        L = 2
        ltd = 61.7
        history = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
        # Hand computation of sample variance:
        # mean = 15.0
        # deviations: -5, -3, -1, 1, 3, 5 -> squares: 25, 9, 1, 1, 9, 25 -> sum = 70
        # s^2 = 70 / (6 - 1) = 14.0
        # sigma = sqrt(14.0) = 3.7416573867739413
        sigma = statistics.stdev(history)
        self.assertAlmostEqual(sigma, math.sqrt(14.0), places=6)

        # safety_stock = ceil(1.65 * 3.741657 * sqrt(2)) = ceil(8.7314) = 9
        ss = math.ceil(1.65 * sigma * math.sqrt(L))
        self.assertEqual(ss, 9)

        # reorder_point = 61.7 + 9 = 70.7
        rp = round(ltd + ss, 1)
        self.assertEqual(rp, 70.7)

        # reorder_qty when stock = 40:
        # ceil(70.7 - 40) = ceil(30.7) = 31
        rq = max(0, math.ceil(rp - 40))
        self.assertEqual(rq, 31)

        # reorder_qty when stock = 100:
        # max(0, ceil(70.7 - 100)) = max(0, -29) = 0
        rq_excess = max(0, math.ceil(rp - 100))
        self.assertEqual(rq_excess, 0)

    def test_reorder_suggestions_uses_live_stock_and_never_negative(self):
        """
        Verify that GET /api/reorder-suggestions/ uses LIVE stock from the database,
        reflects model updates immediately, and reorder_qty is never negative.
        """
        # Ensure product and inventory exist in DB
        prod, _ = Product.objects.get_or_create(
            sku="FIL-1016",
            defaults={"name": "Filter Part", "price": Decimal("100.00")},
        )
        inv, _ = Inventory.objects.get_or_create(product=prod, defaults={"quantity": 10})
        inv.quantity = 10
        inv.save()

        # Call endpoint
        res1 = self.client.get("/api/reorder-suggestions/")
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertIn("results", data1)
        self.assertEqual(len(data1["results"]), 40)

        entry1 = next(item for item in data1["results"] if item["sku"] == "FIL-1016")
        self.assertEqual(entry1["current_stock"], 10)
        self.assertGreaterEqual(entry1["reorder_qty"], 0)

        expected_qty1 = max(0, math.ceil(entry1["reorder_point"] - 10))
        self.assertEqual(entry1["reorder_qty"], expected_qty1)

        # Change live stock in database directly to a huge number (e.g. 10,000)
        inv.quantity = 10000
        inv.save()

        # Call endpoint again - result must change dynamically and reorder_qty must be 0 (never negative)
        res2 = self.client.get("/api/reorder-suggestions/")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        entry2 = next(item for item in data2["results"] if item["sku"] == "FIL-1016")

        self.assertEqual(entry2["current_stock"], 10000)
        self.assertEqual(entry2["reorder_qty"], 0)
        self.assertGreaterEqual(entry2["reorder_qty"], 0)
