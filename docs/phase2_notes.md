# Phase 2: Demand Forecasting & Reorder Recommendations

## 1. Executive Summary & Architecture Overview

Phase 2 introduces the predictive intelligence layer for DealerDesk:
1. **Machine Learning Pipeline (`ml/`)**: Generates an exact 4-week ahead demand forecast for all 40 critical spare part SKUs across the horizon `2026-09-28` to `2026-10-19` (`ml/forecast.csv`, 160 rows).
2. **Forecast Endpoint (`GET /api/forecast/{sku}/`)**: Delivers the 4-week demand projection with exact contract schema and 404 error handling for non-forecast SKUs.
3. **Reorder Engine (`GET /api/reorder-suggestions/`)**: Calculates inventory replenishment recommendations using live, un-cached warehouse inventory (`Inventory.quantity`), lead-time demand, sample standard deviation ($n-1$) over the last 12 weeks of historical sales, and safety stock formulas specified by the contract.
4. **Lightweight Web Runtime**: Standard library `csv`, `math`, and `statistics` are used in the Django application layer (`forecasts/services.py`). Heavy ML dependencies (`lightgbm`, `pandas`, `scikit-learn`) are isolated strictly inside `ml/requirements-ml.txt`, guaranteeing fast and clean deployment for standard web workers and test runners.

---

## 2. SKU Segmentation & Modelling Strategy

Inspection of `data/sales_history.csv` across the 40 SKUs revealed three distinct demand profiles requiring dedicated statistical treatment:

| Group | Count | Identification Rule | Target Strategy |
|---|---|---|---|
| **Regular** | 34 | Dense history, zero-sales weeks $\le$ 35% | Pooled Direct Multi-Horizon Gradient Boosted Trees (LightGBM) |
| **Intermittent** | 4 | Zero-sales weeks > 35% (`ELE-1006`, `GRP-1043`, `BRK-1088`, `ELE-1031`) | Syntetos-Boylan Approximation (SBA) intermittent demand model |
| **New SKUs** | 2 | History < 12 weeks (`BRK-1105`, `CHN-1006` with ~6 weeks) | Adaptive Damped Recent Mean with Promo Multiplier |

### Why Direct Multi-Horizon vs. Recursive Forecasting?
In multi-step forecasting ($h \in \{1, 2, 3, 4\}$):
- **Recursive Forecasting**: Predicts $t+1$, feeds the prediction back as a lag to predict $t+2$, and so forth. In spare parts demand, errors compound geometrically ("error snowballing"), particularly when promotional spikes or festive ramps occur in early horizons.
- **Direct Multi-Horizon (Chosen)**: We condition each forecast horizon $h$ solely on features verified and observable prior to the forecast origin date $T$. By pooling all horizons into a single LightGBM model with an explicit `horizon` feature ($h \in \{1, 2, 3, 4\}$), the model shares representation across products while learning horizon-specific decay and dynamics. This eliminates error cascading and ensures deterministic, reproducible inferences.

---

## 3. Handling Data Hazards

### 1. Promotions (`data/promo_calendar.csv`)
- **Hazard**: Promotions cause significant demand spikes; treating promo periods like baseline sales leads to severe over-prediction once the promo ends.
- **Mitigation**: Future promotions for the 4 forecast weeks are known in advance from `data/promo_calendar.csv`. We incorporate `promo_flag` as an exogenous feature in the LightGBM model. For New SKUs, historical promo lift is estimated and applied strictly when a future promotion is scheduled.

### 2. Diwali & Festive Lift (`data/festival_calendar.csv`)
- **Hazard**: Diwali falls on `2024-11-01`, `2025-10-21`, and `2026-11-08`. Calendar week-of-year or "same week last year" (SWLY) baselines fail catastrophically: in 2025, the forecast calendar weeks coincided directly with the Diwali pre-stocking peak, whereas in 2026, Diwali occurs 3 to 6 weeks *after* the forecast window.
- **Mitigation**: We engineered a continuous signed `weeks_to_diwali` feature and a binary `festive_window` flag ($[-3, +1]$ weeks around Diwali). The model learns demand variation relative to the floating lunar festival rather than fixed Gregorian calendar weeks.

### 3. Intermittent & Lumpy Demand
- **Hazard**: Standard regression models trained on intermittent demand (many zero weeks) predict fractional noise (e.g. 0.4 units) and over-react to single batch spikes.
- **Mitigation**: We implement the Syntetos-Boylan Approximation (SBA), which decomposes demand into non-zero demand size $z_t$ and inter-arrival intervals $p_t$, modified by the debiasing correction factor $(1 - \alpha/2)$:
  $$\hat{y} = \left(1 - \frac{\alpha}{2}\right) \frac{\hat{z}}{\hat{p}}$$
  Backtesting confirmed SBA reduced intermittent SKU WAPE compared to unconstrained regression.

### 4. New SKUs with Short History
- **Hazard**: `BRK-1105` and `CHN-1006` have only ~6 weeks of historical observations. They have no 52-week lag (SWLY) and unstable rolling 8-week standard deviations.
- **Mitigation**: Rather than hardcoding SKU IDs, an automated detection threshold (`history_weeks < 12`) routes them to an adaptive fallback model: a damped recent moving average scaled by scheduled promotion factors, avoiding erratic tree splits on minimal sample sizes.

---

## 4. Leakage Cutoff Citation & Temporal Validation

### Leakage Cutoff Location
Strict time-series causality is enforced in code:
- **File**: `ml/evaluate.py`
- **Lines**: `61-64`
```python
train_pool = panel_df[panel_df["week_start"] < origin].copy()
assert train_pool["week_start"].max() < origin, (
    f"LEAKAGE ASSERTION FAILED: Train data max ({train_pool['week_start'].max()}) >= origin ({origin})"
)
```
Every lag feature ($h=1 \dots 4$), rolling mean ($4w$, $8w$), rolling standard deviation, and target variable is strictly computed using timestamps strictly prior to the rolling origin date `origin`. Shuffling and random splits are prohibited.

---

## 5. Backtest Benchmark Results

### Evaluation Protocol
Rolling-origin backtest evaluated over 5 distinct historical forecast origins:
- `2025-09-08` (Crucial origin ~6 weeks before Diwali 2025, identical temporal context to the 2026 forecast)
- `2026-03-02`
- `2026-05-04`
- `2026-07-06`
- `2026-08-17`

### Overall Benchmark Performance
| Model / Baseline | MAE | WAPE (%) | Status |
|---|---|---|---|
| **Baseline 1: Last Value** | 12.02 | 34.14% | Outperformed |
| **Baseline 2: Recent Average (4w)** | 10.05 | 28.57% | Best baseline |
| **Baseline 3: Same Week Last Year (SWLY)** | 11.26 | 32.00% | Vulnerable to Diwali shift |
| **DealerDesk Model (Ours)** | **7.76** | **22.06%** | **Beats best baseline by 6.51 pp (22.8% relative error reduction)** |

### Performance Breakdown by SKU Group
| SKU Group | Model Strategy | Recent Avg WAPE | DealerDesk Model WAPE |
|---|---|---|---|
| **Regular (34 SKUs)** | LightGBM Direct Multi-Horizon | 28.46% | **22.01%** |
| **Intermittent (4 SKUs)** | Syntetos-Boylan Approximation | 93.97% | **91.24%** |
| **New (2 SKUs)** | Damped Adaptive Mean + Promo | 24.89% | **10.82%** |

---

## 6. Error Analysis: 5 Worst SKUs by Absolute Error

| SKU | Actual Units | Cumulative Absolute Error | WAPE (%) | Primary Driver & Root Cause |
|---|---|---|---|---|
| **`BRK-1085`** | 1,622.0 | 429.9 | 26.50% | High-volume universal brake pads; sudden bulk purchases by multi-brand service centers during promotional windows. |
| **`ELE-1043`** | 1,371.0 | 325.7 | 23.76% | High baseline starter relays with lumpy dealer batch replenishment patterns. |
| **`BRK-1019`** | 1,437.0 | 320.7 | 22.32% | Disc brake pads exhibiting steep pre-festive stocking ramp before festival dates. |
| **`GRP-1024`** | 1,293.0 | 312.7 | 24.19% | Handlebar grips exhibiting strong promotional elasticity with steep post-promo drops. |
| **`FIL-1031`** | 1,011.0 | 249.7 | 24.70% | High-capacity oil filters with bulk fleet maintenance ordering cycles. |

---

## 7. Reorder Suggestions Formula & Hand Verification

The replenishment engine in `forecasts/services.py` calculates suggestions for all 40 forecast SKUs dynamically:

### Exact Formula
1. $L = \text{lead\_time\_weeks}$ (from `data/lead_times.csv`)
2. $\text{lead\_time\_demand} = \sum_{i=1}^L \text{forecast\_units}_i$
3. $\sigma = \text{sample standard deviation with degrees of freedom } (n - 1) \text{ over the last 12 weeks of historical sales}$
   *(If history has $< 2$ data points, $\sigma = 0$)*
4. $\text{safety\_stock} = \lceil 1.65 \times \sigma \times \sqrt{L} \rceil$
5. $\text{reorder\_point} = \text{lead\_time\_demand} + \text{safety\_stock}$
6. $\text{reorder\_qty} = \max(0, \lceil \text{reorder\_point} - \text{current\_stock} \rceil)$

### Hand-Computed Verification Example (`FIL-1016`)
- `current_stock` = 80 (live database query)
- `lead_time_weeks` = 2
- Forecast week 1 = 7.74, week 2 = 6.84 $\implies \text{lead\_time\_demand} = 7.74 + 6.84 = 14.58$
- Last 12 weeks sales history: `[12, 10, 8, 11, 9, 13, 10, 7, 12, 11, 8, 10]`
- Mean = $10.0833$, Sample Variance $s^2 = 3.3561$, Sample Std $\sigma = 1.83195$
- $\text{safety\_stock} = \lceil 1.65 \times 1.83195 \times \sqrt{2} \rceil = \lceil 4.2748 \rceil = 5$
- $\text{reorder\_point} = 14.58 + 5 = 19.58$
- $\text{reorder\_qty} = \max(0, \lceil 19.58 - 80 \rceil) = 0$

Verified via both unit tests (`forecasts/tests.py`) and live HTTP call to `/api/reorder-suggestions/`.

---

## 8. Known Limitations & Future Improvements

### Known Limitations
1. **Limited Festival Cycles**: Only two historical Diwali cycles (2024 and 2025) are available in sales history, constraining the statistical depth for non-linear festive interactions.
2. **Independent SKU Demand**: The model treats spare parts independently, omitting substitution effects (e.g. OEM brake pads vs. aftermarket equivalents).
3. **Parametric Normal Safety Stock**: The safety stock formula relies on Gaussian assumptions ($z = 1.65$ for 95% service level), which under-represents heavy-tailed demand distributions common in intermittent automotive components.

### What to Build with Two More Days
1. **Quantile / Pinball Loss Modeling**: Train direct quantile gradient boosters ($q_{0.95}$) to predict lead-time demand intervals directly, avoiding symmetric standard deviation approximations.
2. **Hierarchical Reconciliation (MinT)**: Implement Minimum Trace reconciliation across Vehicle Category $\rightarrow$ Product Brand $\rightarrow$ SKU level to ensure bottom-up and top-down coherence.
3. **Automated Hyperparameter Search**: Employ Optuna with group-aware time-series cross-validation to tune regularization parameters per SKU sub-cluster.
4. **Automated Reorder Triggering**: Connect `reorder-suggestions` directly to the `orders` module to draft supplier purchase orders when inventory dips below `reorder_point`.
