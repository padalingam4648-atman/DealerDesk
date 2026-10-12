import csv
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import numpy as np
import pandas as pd

from ml.features import (
    load_raw_data,
    classify_skus,
    prepare_base_panel,
    get_weeks_to_diwali,
    FEATURE_COLS,
)
from ml.evaluate import (
    run_rolling_origin_backtest,
    compute_metrics,
    get_worst_skus,
    train_lgb_model,
)

BASE_DIR = Path(__file__).resolve().parent.parent
ML_DIR = BASE_DIR / "ml"
FORECAST_WEEKS = ["2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19"]


def generate_production_forecast():
    """
    Train on all available history up to 2026-09-21 and forecast the 4 weeks starting 2026-09-28.
    Generates ml/forecast.csv with exactly 160 rows (40 SKUs x 4 weeks).
    """
    sales_df, meta_df, festivals, promo_cal_df = load_raw_data()
    all_skus = meta_df["sku"].tolist()
    regular_skus, intermittent_skus, new_skus = classify_skus(sales_df, all_skus)
    panel_df = prepare_base_panel(sales_df, meta_df, festivals)

    origin_date = pd.to_datetime("2026-09-28")

    # =========================================================================
    # PRODUCTION CUTOFF: Train strictly on all historical data before origin
    # =========================================================================
    train_pool = panel_df[panel_df["week_start"] < origin_date].copy()
    assert train_pool["week_start"].max() < origin_date, "Production leakage check failed"

    # Pool training data across horizons h in [1, 2, 3, 4]
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

    # Map future promotions from promo_calendar.csv
    promo_lookup = {
        (r["sku"], r["week_start"].strftime("%Y-%m-%d")): int(r["promo_flag"])
        for _, r in promo_cal_df.iterrows()
    }

    # Precompute SKU histories
    hist_by_sku = {s: train_pool[train_pool["sku"] == s].sort_values("week_start") for s in all_skus}

    forecast_rows = []

    for h, week_str in enumerate(FORECAST_WEEKS, start=1):
        target_w = pd.to_datetime(week_str)
        w_diwali = get_weeks_to_diwali(target_w, festivals)
        is_festive = 1 if -4 <= w_diwali <= 0 else 0
        woy = int(target_w.isocalendar().week)
        month = int(target_w.month)

        for sku in all_skus:
            s_hist = hist_by_sku[sku]
            promo_flag = promo_lookup.get((sku, week_str), 0)

            # Features computed strictly at the origin
            lag_val = float(s_hist.iloc[-1]["units_sold"]) if len(s_hist) >= 1 else 0.0
            mean_4w = float(s_hist.iloc[-4:]["units_sold"].mean()) if len(s_hist) >= 1 else 0.0
            mean_8w = float(s_hist.iloc[-8:]["units_sold"].mean()) if len(s_hist) >= 1 else mean_4w
            std_4w = float(s_hist.iloc[-4:]["units_sold"].std(ddof=1)) if len(s_hist) >= 2 else 0.0
            if np.isnan(std_4w):
                std_4w = 0.0

            # 52 weeks ago
            w_prev = target_w - pd.Timedelta(weeks=52)
            swly_match = s_hist[s_hist["week_start"] == w_prev]
            swly = float(swly_match.iloc[0]["units_sold"]) if len(swly_match) > 0 else mean_4w

            if sku in intermittent_skus:
                # SBA method
                non_zeros = s_hist[s_hist["units_sold"] > 0]
                if len(non_zeros) >= 2:
                    z = non_zeros["units_sold"].mean()
                    p = len(s_hist) / len(non_zeros)
                    sba_val = (1.0 - 0.1 / 2.0) * (z / p)
                    if promo_flag == 1:
                        sba_val *= 1.5
                    forecast_units = sba_val
                else:
                    forecast_units = mean_4w
            elif sku in new_skus:
                # Damped recent mean + promo adjustment
                base_rate = s_hist["units_sold"].mean() if len(s_hist) > 0 else 25.0
                if promo_flag == 1:
                    base_rate *= 1.8
                forecast_units = base_rate
            else:
                # Regular SKU via GBDT
                sku_row = meta_df[meta_df["sku"] == sku].iloc[0]
                feat_dict = {
                    "horizon": h,
                    "promo_flag": promo_flag,
                    "weeks_to_diwali": w_diwali,
                    "is_festive": is_festive,
                    "week_of_year": woy,
                    "month": month,
                    "lag_h": lag_val,
                    "mean_4w_h": mean_4w,
                    "mean_8w_h": mean_8w,
                    "std_4w_h": std_4w,
                    "swly": swly,
                    "cat_code": sku_row["cat_code"],
                    "price": sku_row["price"],
                    "lead_time_weeks": sku_row["lead_time_weeks"],
                }
                pred = float(model.predict(pd.DataFrame([feat_dict])[FEATURE_COLS])[0])
                forecast_units = max(0.0, pred)

            # Round forecast units to 1 decimal place as in API spec
            forecast_rows.append({
                "sku": sku,
                "week_start": week_str,
                "forecast_units": round(float(forecast_units), 1),
            })

    output_path = ML_DIR / "forecast.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["sku", "week_start", "forecast_units"])
        writer.writeheader()
        writer.writerows(forecast_rows)

    print(f"Generated {output_path} with {len(forecast_rows)} rows.")
    return forecast_rows


def main():
    print("=" * 70)
    print("VIKMO DealerDesk — Demand Forecasting Evaluation & Training")
    print("=" * 70)

    print("\nRunning rolling-origin backtest across 5 historical origins...")
    res_df, (regular_skus, intermittent_skus, new_skus) = run_rolling_origin_backtest()
    tot_act = res_df["actual"].sum()

    print(f"\nBacktest completed on {len(res_df)} total observations ({tot_act:.0f} actual units).")

    print("\n" + "=" * 60)
    print("BACKTEST BENCHMARK RESULTS (Model vs Baselines)")
    print("=" * 60)
    print(f"{'Method / Model':<26} | {'MAE':>8} | {'WAPE':>10}")
    print("-" * 60)
    for m, label in [
        ("last_val", "Baseline: Last Value"),
        ("rec_avg", "Baseline: Recent Average"),
        ("swly", "Baseline: Same Week Last Year"),
        ("model", "DealerDesk Model (Ours)"),
    ]:
        met = compute_metrics(res_df, m)
        print(f"{label:<26} | {met['mae']:8.2f} | {met['wape']:9.2%}")
    print("-" * 60)

    print("\nPER-GROUP PERFORMANCE BREAKDOWN:")
    for grp_name, desc in [
        ("regular", f"Regular SKUs ({len(regular_skus)} SKUs - GBDT multi-horizon)"),
        ("intermittent", f"Intermittent SKUs ({len(intermittent_skus)} SKUs - SBA method)"),
        ("new", f"New SKUs ({len(new_skus)} SKUs - Adaptive peer baseline)"),
    ]:
        sub = res_df[res_df["group"] == grp_name]
        grp_act = sub["actual"].sum()
        print(f"\n  [{desc}] - N={len(sub)}, Actuals={grp_act:.0f}")
        for m, label in [
            ("last_val", "Last Value"),
            ("rec_avg", "Recent Avg"),
            ("swly", "Same Wk Last Yr"),
            ("model", "Our Model"),
        ]:
            met = compute_metrics(sub, m)
            print(f"    {label:<18} : MAE={met['mae']:5.2f}, WAPE={met['wape']:6.2%}")

    print("\n" + "=" * 60)
    print("WORST 5 SKUS BY ABSOLUTE ERROR")
    print("=" * 60)
    worst = get_worst_skus(res_df, 5)
    for idx, w in enumerate(worst, start=1):
        print(f"  {idx}. {w['sku']} ({w['group']}): Abs Error = {w['total_err']:.1f}, Actual = {w['total_actual']:.1f}, WAPE = {w['wape']:.2%}")

    print("\n" + "=" * 60)
    print("GENERATING PRODUCTION FORECAST (ml/forecast.csv)...")
    print("=" * 60)
    forecast_rows = generate_production_forecast()

    print("\nFirst 5 rows of ml/forecast.csv:")
    for r in forecast_rows[:5]:
        print(f"  {r['sku']}, {r['week_start']}, {r['forecast_units']}")

    print("\nAll forecasting tasks completed successfully!")


if __name__ == "__main__":
    main()
