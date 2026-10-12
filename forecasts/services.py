import csv
from functools import lru_cache
import math
from pathlib import Path
import statistics
from django.conf import settings
from catalog.models import Inventory

BASE_DIR = Path(settings.BASE_DIR)
DATA_DIR = BASE_DIR / "data"
ML_DIR = BASE_DIR / "ml"


@lru_cache(maxsize=1)
def load_static_forecast_data():
    """
    Load and cache immutable static files (lead_times.csv, forecast.csv, sales_history.csv)
    using the Python standard library csv module.
    Stock levels are NEVER cached here.
    """
    lead_times = {}
    lead_path = DATA_DIR / "lead_times.csv"
    with open(lead_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row["sku"].strip()
            lead_times[sku] = int(row["lead_time_weeks"].strip())

    forecast_by_sku = {}
    forecast_path = ML_DIR / "forecast.csv"
    with open(forecast_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row["sku"].strip()
            if sku not in forecast_by_sku:
                forecast_by_sku[sku] = []
            forecast_by_sku[sku].append({
                "week_start": row["week_start"].strip(),
                "forecast_units": float(row["forecast_units"].strip()),
            })

    sales_by_sku = {}
    sales_path = DATA_DIR / "sales_history.csv"
    with open(sales_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row["sku"].strip()
            if sku not in sales_by_sku:
                sales_by_sku[sku] = []
            sales_by_sku[sku].append((row["week_start"].strip(), float(row["units_sold"].strip())))

    # Extract the most recent up to 12 weeks of historical units_sold for each SKU
    recent_12w_by_sku = {}
    for sku, entries in sales_by_sku.items():
        entries.sort(key=lambda x: x[0])
        recent_12w_by_sku[sku] = [x[1] for x in entries[-12:]]

    return lead_times, forecast_by_sku, recent_12w_by_sku


def get_sku_forecast(sku: str) -> dict | None:
    """
    Retrieve the 4-week forecast for a given SKU.
    Returns None if the SKU is not a valid forecast SKU.
    """
    _, forecast_by_sku, _ = load_static_forecast_data()
    forecast_list = forecast_by_sku.get(sku)
    if not forecast_list:
        return None

    return {
        "sku": sku,
        "forecast": forecast_list,
    }


def compute_reorder_suggestions() -> list[dict]:
    """
    Compute inventory reorder suggestions for all 40 forecast SKUs.
    Stock is fetched live from the database at request time and is never cached.
    
    Formula per API specification:
      L = lead_time_weeks (lead_times.csv)
      lead_time_demand = sum of first L forecast weeks
      sigma = sample standard deviation (n - 1) of last 12 weeks of units_sold in sales_history.csv
      safety_stock = ceil(1.65 * sigma * sqrt(L))
      reorder_point = lead_time_demand + safety_stock
      reorder_qty = max(0, ceil(reorder_point - current_stock))
    """
    lead_times, forecast_by_sku, recent_12w_by_sku = load_static_forecast_data()

    # LIVE DATABASE QUERY: Retrieve fresh available stock for all forecast SKUs
    live_inventories = {
        inv.product.sku: inv.quantity
        for inv in Inventory.objects.filter(product__sku__in=lead_times.keys()).select_related("product")
    }

    results = []
    for sku, lead_time_weeks in lead_times.items():
        current_stock = live_inventories.get(sku, 0)

        # 1. Lead time demand: sum of first L forecast weeks
        sku_forecast = forecast_by_sku.get(sku, [])
        lead_time_demand = round(sum(item["forecast_units"] for item in sku_forecast[:lead_time_weeks]), 1)

        # 2. Sample standard deviation (n - 1) over most recent up to 12 weeks
        hist_units = recent_12w_by_sku.get(sku, [])
        if len(hist_units) >= 2:
            sigma = statistics.stdev(hist_units)
        else:
            sigma = 0.0

        # 3. Safety stock
        safety_stock = math.ceil(1.65 * sigma * math.sqrt(lead_time_weeks))

        # 4. Reorder point
        reorder_point = round(lead_time_demand + safety_stock, 1)

        # 5. Reorder quantity
        reorder_qty = max(0, math.ceil(reorder_point - current_stock))

        results.append({
            "sku": sku,
            "current_stock": current_stock,
            "lead_time_weeks": lead_time_weeks,
            "lead_time_demand": lead_time_demand,
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "reorder_qty": reorder_qty,
        })

    return results
