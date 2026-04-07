# US Crop Price Vulnerability & Forecasting

**Business Question:** Which US crops are most vulnerable to price volatility and supply disruptions — and can we predict price movement 3–6 months out?

---

## Project Overview

A full end-to-end data analysis pipeline using USDA farm-gate price data (2010–2024) and FRED commodity CPI indices to identify price risk across wheat, corn, and soybean markets — with a 6-month Prophet forecast and Tableau dashboard.

### Key Findings
- 🌽 **Corn** is the most volatile crop (CV 28.5%), followed by Wheat (25.5%) and Soybeans (20.5%)
- 🗺️ **Colorado, Texas, Kansas, Nebraska** are the highest price-risk states
- 📈 **Soybeans** forecast to rise +17% over the next 6 months (Apr–Oct 2026)
- 🔗 Farm prices track commodity CPI with **r = 0.90–0.96** — CPI is a reliable 4–6 week leading indicator

---

## Project Structure

```
├── 01_build_database.py     # Clean raw CSVs → SQLite database
├── 02_sql_analysis.py       # SQL: volatility, state exposure, CPI correlation
├── 03_eda.py                # 6 EDA charts (trends, heatmap, swings, CPI overlay)
├── 04_forecast.py           # Prophet time series forecast (6-month horizon)
├── 05_export_tableau.py     # Export flat CSVs for Tableau dashboard
├── memo.md                  # Business memo for food retailers
├── requirements.txt
│
└── data/
    ├── raw/                 # Source data (USDA NASS + FRED)
    ├── figures/             # All chart outputs (9 PNGs)
    ├── forecast/            # Prophet forecast CSVs per commodity
    └── tableau/             # Dashboard-ready flat CSVs
```

---

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Build the database
python3 01_build_database.py

# 3. Run SQL analysis
python3 02_sql_analysis.py

# 4. Generate EDA charts
python3 03_eda.py

# 5. Run Prophet forecast
python3 04_forecast.py

# 6. Export Tableau files
python3 05_export_tableau.py
```

---

## Data Sources

| Source | Data | Coverage |
|---|---|---|
| [USDA NASS QuickStats](https://quickstats.nass.usda.gov/) | Farm-gate prices by state | 2010–2024, 34 states |
| [FRED](https://fred.stlouisfed.org/) | Commodity price indices | 2010–2026 |

**Crops:** Wheat · Corn · Soybeans  
**Total observations:** 9,942 state-level monthly price records

---

## Charts

| # | Chart | Key Insight |
|---|---|---|
| 1 | Price Trend Lines | 2022 spike visible across all crops |
| 2 | Volatility Heatmap | Corn + Plains states = highest risk |
| 3 | Price Swings Bar | Texas wheat swung 360% trough to peak |
| 4 | Farm Price vs CPI | Near-perfect co-movement (r = 0.90–0.96) |
| 5 | Rolling Volatility | 2022 was a 14-year volatility peak |
| 6 | State Exposure Ranking | Colorado and Texas most exposed |
| 7–9 | Prophet Forecasts | Soybeans +17%, Corn +9%, Wheat –1% |

---

## 6-Month Forecast (April–October 2026)

| Crop | Current | Forecast | Change | 90% CI |
|---|---|---|---|---|
| Wheat | $5.46/bu | $5.38/bu | ▼ –1.3% | $4.42–$6.28 |
| Corn | $4.33/bu | $4.73/bu | ▲ +9.2% | $3.81–$5.60 |
| **Soybeans** | $9.84/bu | $11.53/bu | **▲ +17.2%** | $10.16–$12.78 |

*Model: Facebook Prophet · Multiplicative seasonality · 90% credible intervals*

---

## Tableau Dashboard

Connect Tableau to the three files in `data/tableau/`:
- `prices_long.csv` — price trend + volatility sheet
- `state_exposure.csv` — state risk map (includes lat/lon)
- `forecast.csv` — forecast chart with confidence band

---

## Business Memo

See [`memo.md`](memo.md) for a one-page brief written for food retail leadership covering findings, forecast, and procurement recommendations.
