"""
Step 4: Time Series Forecasting — Prophet model, 6-month price forecast
Outputs: data/forecast/*.csv  +  data/figures/07-09_forecast_*.png
"""

import warnings
warnings.filterwarnings("ignore")

import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from prophet import Prophet
from pathlib import Path

Path("data/figures").mkdir(parents=True, exist_ok=True)
Path("data/forecast").mkdir(parents=True, exist_ok=True)

PALETTE = {"Corn": "#F4A62A", "Wheat": "#6D9E4F", "Soybeans": "#3B82B5"}
STYLE = {
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.dpi": 150,
}
plt.rcParams.update(STYLE)

conn = sqlite3.connect("data/agri.db")

prices = pd.read_sql("""
    SELECT commodity, date, AVG(price_usd_per_bu) AS price
    FROM crop_prices
    GROUP BY commodity, date
    ORDER BY commodity, date
""", conn, parse_dates=["date"])
prices["commodity"] = prices["commodity"].str.title()
conn.close()

FORECAST_MONTHS = 6
all_forecasts = []

for crop in ["Wheat", "Corn", "Soybeans"]:
    print(f"\n  Fitting Prophet model for {crop}...")

    g = prices[prices["commodity"] == crop][["date", "price"]].copy()
    g.columns = ["ds", "y"]
    g = g.sort_values("ds").reset_index(drop=True)

    # Prophet: yearly seasonality on, weekly off (monthly data)
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode="multiplicative",   # ag prices scale with level
        interval_width=0.90,
        changepoint_prior_scale=0.15,        # moderate flexibility
    )
    model.fit(g)

    future = model.make_future_dataframe(periods=FORECAST_MONTHS, freq="MS")
    forecast = model.predict(future)

    # Save CSV
    out = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    out.columns = ["date", "forecast_price", "lower_90", "upper_90"]
    out["commodity"] = crop
    out["is_forecast"] = out["date"] > g["ds"].max()
    out.to_csv(f"data/forecast/{crop.lower()}_forecast.csv", index=False)
    all_forecasts.append(out)

    # ── Chart ─────────────────────────────────────────────────────────────────
    color = PALETTE[crop]
    fig, ax = plt.subplots(figsize=(13, 5))

    # Historical actuals
    ax.plot(g["ds"], g["y"], color=color, linewidth=2, label="Historical Price", zorder=3)

    # Forecast line
    fc_future = out[out["is_forecast"]]
    fc_all    = out[~out["is_forecast"]]

    ax.plot(fc_all["date"], fc_all["forecast_price"],
            color=color, linewidth=1, linestyle="--", alpha=0.5)
    ax.plot(fc_future["date"], fc_future["forecast_price"],
            color=color, linewidth=2.5, linestyle="--", label="Forecast (6 mo)", zorder=4)

    # Confidence band
    ax.fill_between(out["date"], out["lower_90"], out["upper_90"],
                    color=color, alpha=0.12, label="90% Confidence Interval")

    # Vertical line at forecast start
    split = g["ds"].max()
    ax.axvline(split, color="#999", linewidth=1, linestyle=":", label="Forecast Start")

    # Annotate final forecast value
    last_row = fc_future.iloc[-1]
    ax.annotate(
        f"${last_row['forecast_price']:.2f}/bu\n(±${(last_row['upper_90']-last_row['lower_90'])/2:.2f})",
        xy=(last_row["date"], last_row["forecast_price"]),
        xytext=(15, 10), textcoords="offset points",
        fontsize=9, color=color,
        arrowprops=dict(arrowstyle="->", color=color, lw=1.2)
    )

    ax.set_title(f"{crop} — National Average Price Forecast  (Prophet, 6-Month Horizon)",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("Price ($/bushel)")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.2f"))
    ax.legend(framealpha=0.9, fontsize=9)

    idx = ["Wheat", "Corn", "Soybeans"].index(crop) + 7
    fig.tight_layout()
    fig.savefig(f"data/figures/{idx:02d}_forecast_{crop.lower()}.png")
    plt.close(fig)
    print(f"  ✅ {crop}: chart saved")

# ── Combined forecast summary CSV ─────────────────────────────────────────────
combined = pd.concat(all_forecasts)
combined.to_csv("data/forecast/all_forecasts.csv", index=False)

# Print 6-month outlook table
print("\n" + "="*65)
print("  6-Month Price Forecast Summary")
print("="*65)
for crop in ["Wheat", "Corn", "Soybeans"]:
    fc = combined[(combined["commodity"] == crop) & combined["is_forecast"]]
    latest_hist = prices[prices["commodity"] == crop]["price"].iloc[-1]
    forecast_end = fc.iloc[-1]
    chg = ((forecast_end["forecast_price"] - latest_hist) / latest_hist) * 100
    direction = "▲" if chg > 0 else "▼"
    print(f"  {crop:<10}  Current: ${latest_hist:.2f}  →  "
          f"Forecast: ${forecast_end['forecast_price']:.2f}  "
          f"({direction} {abs(chg):.1f}%)  "
          f"[90% CI: ${forecast_end['lower_90']:.2f}–${forecast_end['upper_90']:.2f}]")

print("\n✅ Forecasts complete → data/forecast/ + data/figures/")
