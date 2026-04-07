"""
Step 5: Tableau Export — Flat denormalised CSVs optimised for Tableau
Outputs: data/tableau/prices_long.csv
         data/tableau/state_exposure.csv   (includes lat/lon for map layer)
         data/tableau/forecast.csv
"""

import sqlite3
import math
import pandas as pd
from pathlib import Path

Path("data/tableau").mkdir(parents=True, exist_ok=True)


# ── SQLite STDEV aggregate ────────────────────────────────────────────────────
class StdDev:
    def __init__(self):  self.n = 0; self.mean = 0.0; self.M2 = 0.0
    def step(self, v):
        if v is None: return
        self.n += 1; d = v - self.mean; self.mean += d / self.n; self.M2 += d*(v-self.mean)
    def finalize(self):
        return math.sqrt(self.M2/(self.n-1)) if self.n >= 2 else None

conn = sqlite3.connect("data/agri.db")
conn.create_aggregate("STDEV", 1, StdDev)


# ── 1. prices_long.csv ────────────────────────────────────────────────────────
# All price records + CPI joined + pre-computed CV for state×commodity

print("Building prices_long.csv...")

prices = pd.read_sql("""
    SELECT commodity, state, date, price_usd_per_bu, year
    FROM crop_prices
    ORDER BY commodity, state, date
""", conn, parse_dates=["date"])
prices["commodity"] = prices["commodity"].str.title()

cpi = pd.read_sql("""
    SELECT commodity, date, price_index
    FROM commodity_cpi
""", conn, parse_dates=["date"])
cpi["commodity"] = cpi["commodity"].str.title()

# CV% lookup table per commodity × state
cv_lookup = pd.read_sql("""
    SELECT commodity, state,
           ROUND(100.0 * STDEV(price_usd_per_bu) / AVG(price_usd_per_bu), 2) AS cv_pct
    FROM crop_prices
    GROUP BY commodity, state
    HAVING COUNT(*) >= 24
""", conn)
cv_lookup["commodity"] = cv_lookup["commodity"].str.title()

prices_long = prices.merge(cv_lookup, on=["commodity", "state"], how="left")
prices_long = prices_long.merge(
    cpi.rename(columns={"price_index": "cpi"}),
    on=["commodity", "date"], how="left"
)

prices_long["date"] = prices_long["date"].dt.strftime("%Y-%m-%d")
prices_long.to_csv("data/tableau/prices_long.csv", index=False)
print(f"  ✅ prices_long.csv — {len(prices_long):,} rows")


# ── 2. state_exposure.csv (with lat/lon centroids for Tableau map layer) ──────

print("Building state_exposure.csv...")

# State centroids (lower-48)
STATE_COORDS = {
    "ALABAMA": (32.806671, -86.791130), "ARKANSAS": (34.969704, -92.373123),
    "CALIFORNIA": (36.116203, -119.681564), "COLORADO": (39.059811, -105.311104),
    "DELAWARE": (38.908734, -75.527670), "FLORIDA": (27.766279, -81.686783),
    "GEORGIA": (33.040619, -83.643074), "IDAHO": (44.240459, -114.478828),
    "ILLINOIS": (40.349457, -88.986137), "INDIANA": (39.849426, -86.258278),
    "IOWA": (42.011539, -93.210526), "KANSAS": (38.526600, -96.726486),
    "KENTUCKY": (37.668140, -84.670067), "LOUISIANA": (31.169960, -91.867805),
    "MARYLAND": (39.063946, -76.802101), "MICHIGAN": (43.326618, -84.536095),
    "MINNESOTA": (45.694454, -93.900192), "MISSISSIPPI": (32.741646, -89.678696),
    "MISSOURI": (38.456085, -92.288368), "MONTANA": (46.921925, -110.454353),
    "NEBRASKA": (41.125370, -98.268082), "NEW JERSEY": (40.298904, -74.521011),
    "NEW YORK": (42.165726, -74.948051), "NORTH CAROLINA": (35.630066, -79.806419),
    "NORTH DAKOTA": (47.528912, -99.784012), "OHIO": (40.388783, -82.764915),
    "OKLAHOMA": (35.565342, -96.928917), "OREGON": (44.572021, -122.070938),
    "PENNSYLVANIA": (40.590752, -77.209755), "SOUTH CAROLINA": (33.856892, -80.945007),
    "SOUTH DAKOTA": (44.299782, -99.438828), "TENNESSEE": (35.747845, -86.692345),
    "TEXAS": (31.054487, -97.563461), "VIRGINIA": (37.769337, -78.169968),
    "WASHINGTON": (47.400902, -121.490494), "WEST VIRGINIA": (38.491226, -80.954453),
    "WISCONSIN": (44.268543, -89.616508),
}

state_exp = pd.read_sql("""
    WITH cv AS (
        SELECT state, commodity,
               100.0 * STDEV(price_usd_per_bu) / AVG(price_usd_per_bu) AS cv_pct,
               ROUND(MIN(price_usd_per_bu), 2) AS min_price,
               ROUND(MAX(price_usd_per_bu), 2) AS max_price,
               COUNT(*) AS n_obs
        FROM crop_prices GROUP BY state, commodity HAVING n_obs >= 24
    )
    SELECT state,
           COUNT(DISTINCT commodity)  AS n_crops,
           ROUND(AVG(cv_pct), 2)      AS avg_cv_pct,
           ROUND(MAX(cv_pct), 2)      AS max_cv_pct,
           SUM(n_obs)                 AS total_obs
    FROM cv GROUP BY state
""", conn)

state_exp["lat"] = state_exp["state"].map(lambda s: STATE_COORDS.get(s, (None, None))[0])
state_exp["lon"] = state_exp["state"].map(lambda s: STATE_COORDS.get(s, (None, None))[1])
state_exp["risk_tier"] = pd.cut(
    state_exp["avg_cv_pct"],
    bins=[0, 20, 25, 30, 100],
    labels=["Low", "Moderate", "High", "Very High"]
)

state_exp.to_csv("data/tableau/state_exposure.csv", index=False)
print(f"  ✅ state_exposure.csv — {len(state_exp)} states")


# ── 3. forecast.csv ───────────────────────────────────────────────────────────

print("Building forecast.csv...")

import os
fc_files = [f for f in Path("data/forecast").glob("*_forecast.csv")
            if f.name != "all_forecasts.csv"]

if fc_files:
    dfs = [pd.read_csv(f, encoding="utf-8") for f in sorted(fc_files)]
    forecast_combined = pd.concat(dfs, ignore_index=True)

    # Merge in current (last historical) price for pct-change calc
    last_price = (prices
                  .groupby("commodity")["price_usd_per_bu"]
                  .last()
                  .reset_index()
                  .rename(columns={"price_usd_per_bu": "last_actual_price"}))
    forecast_combined = forecast_combined.merge(last_price, on="commodity", how="left")
    forecast_combined["pct_change_from_last"] = (
        (forecast_combined["forecast_price"] - forecast_combined["last_actual_price"])
        / forecast_combined["last_actual_price"] * 100
    ).round(2)

    forecast_combined.to_csv("data/tableau/forecast.csv", index=False)
    print(f"  ✅ forecast.csv — {len(forecast_combined):,} rows")
else:
    print("  ⚠️  No forecast files found — run 04_forecast.py first, then re-run this script.")

conn.close()
print("\n✅ Tableau exports complete → data/tableau/")
print("   Files:")
for f in sorted(Path("data/tableau").glob("*.csv")):
    if f.name.startswith("._"):
        continue
    rows = sum(1 for _ in open(f, encoding="utf-8", errors="ignore")) - 1
    print(f"   · {f.name:<30} {rows:>6,} rows")
