import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import numpy as np
import lightgbm as lgb
from ml.features import (
    load_raw_data,
    classify_skus,
    prepare_base_panel,
    FEATURE_COLS,
)

DEFAULT_ORIGINS = [
    pd.to_datetime("2025-09-08"),  # Mimics ~6 weeks before Diwali in 2025 (festive handling test)
    pd.to_datetime("2026-03-30"),  # Spring baseline period
    pd.to_datetime("2026-05-18"),  # Summer period
    pd.to_datetime("2026-07-06"),  # Mid-summer period
    pd.to_datetime("2026-08-24"),  # Recent origin right before final cutoff
]


def train_lgb_model(train_df: pd.DataFrame, feature_cols: list[str]) -> lgb.LGBMRegressor:
    """Train pooled LightGBM regressor on regular SKUs."""
    model = lgb.LGBMRegressor(
        objective="regression_l1",
        n_estimators=100,
        learning_rate=0.04,
        num_leaves=16,
        min_child_samples=5,
        random_state=42,
        verbosity=-1,
    )
    model.fit(train_df[feature_cols], train_df["units_sold"])
    return model


def run_rolling_origin_backtest(origins: list[pd.Timestamp] = None):
    """
    Run rolling-origin backtesting comparing baselines and the specialized model.
    Enforces strict temporal separation: no training rows are at or after the origin date.
    """
    if origins is None:
        origins = DEFAULT_ORIGINS

    sales_df, meta_df, festivals, _ = load_raw_data()
    all_skus = meta_df["sku"].tolist()
    regular_skus, intermittent_skus, new_skus = classify_skus(sales_df, all_skus)
    panel_df = prepare_base_panel(sales_df, meta_df, festivals)

    records = []

    for origin in origins:
        # =========================================================================
        # LEAKAGE CUTOFF: strictly train on history strictly before origin date
        # =========================================================================
        train_pool = panel_df[panel_df["week_start"] < origin].copy()
        assert train_pool["week_start"].max() < origin, (
            f"LEAKAGE ASSERTION FAILED: Train data max ({train_pool['week_start'].max()}) >= origin ({origin})"
        )

        future_weeks = [origin + pd.Timedelta(weeks=i) for i in range(4)]
        test_pool = panel_df[panel_df["week_start"].isin(future_weeks)].copy()
        if len(test_pool) == 0:
            continue

        # Prepare pooled training data with horizon feature h in [1, 2, 3, 4]
        h_train_list = []
        for h in [1, 2, 3, 4]:
            sub = train_pool[train_pool["sku"].isin(regular_skus) & train_pool[f"lag_{h}"].notnull()].copy()
            sub["horizon"] = h
            sub["lag_h"] = sub[f"lag_{h}"]
            sub["mean_4w_h"] = sub[f"mean_4w_{h}"]
            sub["mean_8w_h"] = sub[f"mean_8w_{h}"]
            sub["std_4w_h"] = sub[f"std_4w_{h}"]
            sub["swly"] = sub["swly"].fillna(sub["mean_4w_h"])
            h_train_list.append(sub[FEATURE_COLS + ["units_sold", "sku", "week_start"]])

        all_train_h = pd.concat(h_train_list, ignore_index=True)
        model = train_lgb_model(all_train_h, FEATURE_COLS)

        # Precompute per-SKU historical data dictionaries for rapid prediction
        hist_by_sku = {s: train_pool[train_pool["sku"] == s] for s in all_skus}

        # Predict across the 4 forecast weeks
        for h, target_w in enumerate(future_weeks, start=1):
            t_h = test_pool[test_pool["week_start"] == target_w].copy()
            t_h["horizon"] = h
            t_h["lag_h"] = t_h[f"lag_{h}"]
            t_h["mean_4w_h"] = t_h[f"mean_4w_{h}"]
            t_h["mean_8w_h"] = t_h[f"mean_8w_{h}"]
            t_h["std_4w_h"] = t_h[f"std_4w_{h}"]
            t_h["swly"] = t_h["swly"].fillna(t_h["mean_4w_h"])

            # Batch predict for regular SKUs
            reg_mask = t_h["sku"].isin(regular_skus)
            if reg_mask.any():
                reg_preds = model.predict(t_h.loc[reg_mask, FEATURE_COLS])
                t_h.loc[reg_mask, "model_pred"] = np.maximum(0.0, reg_preds)

            for _, row in t_h.iterrows():
                sku = row["sku"]
                actual = row["units_sold"]
                s_hist = hist_by_sku[sku]

                # 1. Baseline 1: Last value (most recent observed units_sold)
                last_val = max(0.0, float(row["lag_h"]) if pd.notnull(row["lag_h"]) else 0.0)

                # 2. Baseline 2: Recent average (last 4 weeks observed)
                rec_avg = max(0.0, float(row["mean_4w_h"]) if pd.notnull(row["mean_4w_h"]) else 0.0)

                # 3. Baseline 3: Same week last year (52 weeks ago)
                swly = max(0.0, float(row["swly"]) if pd.notnull(row["swly"]) else rec_avg)

                # 4. Specialized Model Forecast
                if sku in intermittent_skus:
                    # Syntetos-Boylan Approximation (SBA)
                    non_zeros = s_hist[s_hist["units_sold"] > 0]
                    if len(non_zeros) >= 2:
                        z = non_zeros["units_sold"].mean()
                        p = len(s_hist) / len(non_zeros)
                        sba_val = (1.0 - 0.1 / 2.0) * (z / p)
                        if row["promo_flag"] == 1:
                            sba_val *= 1.5
                        model_pred = sba_val
                    else:
                        model_pred = rec_avg
                elif sku in new_skus:
                    # Damped recent mean + promo adjustment
                    base_rate = s_hist["units_sold"].mean() if len(s_hist) > 0 else 25.0
                    if row["promo_flag"] == 1:
                        base_rate *= 1.8
                    model_pred = base_rate
                else:
                    model_pred = float(row["model_pred"])

                group_name = "intermittent" if sku in intermittent_skus else ("new" if sku in new_skus else "regular")
                records.append({
                    "origin": origin,
                    "week_start": target_w,
                    "sku": sku,
                    "group": group_name,
                    "actual": actual,
                    "last_val": last_val,
                    "rec_avg": rec_avg,
                    "swly": swly,
                    "model": model_pred,
                })

    results_df = pd.DataFrame(records)
    return results_df, (regular_skus, intermittent_skus, new_skus)


def compute_metrics(df: pd.DataFrame, pred_col: str, actual_col: str = "actual") -> dict:
    """Compute MAE and WAPE."""
    actuals = df[actual_col]
    preds = df[pred_col]
    mae = float(np.mean(np.abs(actuals - preds)))
    tot_actual = float(np.sum(actuals))
    wape = float(np.sum(np.abs(actuals - preds)) / tot_actual) if tot_actual > 0 else 0.0
    return {"mae": mae, "wape": wape}


def get_worst_skus(results_df: pd.DataFrame, n: int = 5) -> list[dict]:
    """Identify the top N worst SKUs by error."""
    results_df["abs_err"] = np.abs(results_df["actual"] - results_df["model"])
    sku_err = results_df.groupby("sku").agg(
        total_err=("abs_err", "sum"),
        total_actual=("actual", "sum"),
        group=("group", "first"),
    )
    sku_err["wape"] = sku_err["total_err"] / sku_err["total_actual"]
    worst = sku_err.sort_values("total_err", ascending=False).head(n)
    
    worst_list = []
    for sku, row in worst.iterrows():
        worst_list.append({
            "sku": sku,
            "group": row["group"],
            "total_err": row["total_err"],
            "total_actual": row["total_actual"],
            "wape": row["wape"],
        })
    return worst_list
