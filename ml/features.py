from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

FEATURE_COLS = [
    "horizon",
    "promo_flag",
    "weeks_to_diwali",
    "is_festive",
    "week_of_year",
    "month",
    "lag_h",
    "mean_4w_h",
    "mean_8w_h",
    "std_4w_h",
    "swly",
    "cat_code",
    "price",
    "lead_time_weeks",
]


def load_raw_data(data_dir: Path = DATA_DIR):
    """Load all necessary raw CSV files from data/."""
    sales_df = pd.read_csv(data_dir / "sales_history.csv")
    sales_df["week_start"] = pd.to_datetime(sales_df["week_start"])

    lead_df = pd.read_csv(data_dir / "lead_times.csv")
    cat_df = pd.read_csv(data_dir / "catalogue.csv")[["sku", "category", "brand", "price"]].drop_duplicates("sku")

    festivals_df = pd.read_csv(data_dir / "festival_calendar.csv")
    festivals = pd.to_datetime(festivals_df["date"])

    promo_cal_df = pd.read_csv(data_dir / "promo_calendar.csv")
    promo_cal_df["week_start"] = pd.to_datetime(promo_cal_df["week_start"])

    meta_df = lead_df.merge(cat_df, on="sku", how="left")
    meta_df["cat_code"] = pd.factorize(meta_df["category"])[0]

    return sales_df, meta_df, festivals, promo_cal_df


def get_weeks_to_diwali(date: pd.Timestamp, festivals: pd.Series) -> int:
    """Calculate signed distance in weeks to closest Diwali."""
    diffs = [(date - f).days / 7.0 for f in festivals]
    closest = min(diffs, key=abs)
    return round(closest)


def classify_skus(sales_df: pd.DataFrame, all_skus: list[str]) -> tuple[set, set, set]:
    """
    Classify SKUs into 3 distinct operational groups:
    - Intermittent: zero sales ratio > 35%
    - New: history length < 12 weeks
    - Regular: standard continuous history
    """
    sku_stats = sales_df.groupby("sku")["units_sold"].agg(
        count="count",
        zero_ratio=lambda s: (s == 0).mean()
    )
    intermittent_skus = set(sku_stats[sku_stats["zero_ratio"] > 0.35].index)
    new_skus = set(sku_stats[sku_stats["count"] < 12].index)
    regular_skus = set(all_skus) - intermittent_skus - new_skus

    return regular_skus, intermittent_skus, new_skus


def prepare_base_panel(sales_df: pd.DataFrame, meta_df: pd.DataFrame, festivals: pd.Series) -> pd.DataFrame:
    """Prepare enriched base panel dataset with calendar and metadata features."""
    df = sales_df.copy()
    df["weeks_to_diwali"] = df["week_start"].apply(lambda d: get_weeks_to_diwali(d, festivals))
    df["is_festive"] = df["weeks_to_diwali"].apply(lambda w: 1 if -4 <= w <= 0 else 0)
    df["week_of_year"] = df["week_start"].dt.isocalendar().week.astype(int)
    df["month"] = df["week_start"].dt.month

    df = df.merge(meta_df[["sku", "lead_time_weeks", "cat_code", "price"]], on="sku", how="left")
    df = df.sort_values(["sku", "week_start"]).reset_index(drop=True)

    # Shifted lag and rolling statistics
    for h in [1, 2, 3, 4]:
        df[f"lag_{h}"] = df.groupby("sku")["units_sold"].shift(h)
        df[f"mean_4w_{h}"] = df.groupby("sku")["units_sold"].shift(h).rolling(4, min_periods=1).mean()
        df[f"mean_8w_{h}"] = df.groupby("sku")["units_sold"].shift(h).rolling(8, min_periods=1).mean()
        df[f"std_4w_{h}"] = df.groupby("sku")["units_sold"].shift(h).rolling(4, min_periods=2).std().fillna(0.0)

    # Same week last year (52 weeks prior)
    df["swly"] = df.groupby("sku")["units_sold"].shift(52)

    return df
