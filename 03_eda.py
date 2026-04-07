"""
Step 3: Python EDA — Price trends, volatility analysis, CPI correlation
Outputs 6 publication-quality charts to data/figures/
"""

import sqlite3
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pathlib import Path

# ── Setup ─────────────────────────────────────────────────────────────────────

Path("data/figures").mkdir(parents=True, exist_ok=True)

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

# SQLite STDEV aggregate
class StdDev:
    def __init__(self):  self.n = 0; self.mean = 0.0; self.M2 = 0.0
    def step(self, v):
        if v is None: return
        self.n += 1; d = v - self.mean; self.mean += d / self.n; self.M2 += d*(v-self.mean)
    def finalize(self):
        return math.sqrt(self.M2/(self.n-1)) if self.n >= 2 else None

conn = sqlite3.connect("data/agri.db")
conn.create_aggregate("STDEV", 1, StdDev)

# ── Load base data ─────────────────────────────────────────────────────────────

prices = pd.read_sql("""
    SELECT commodity, state, date, price_usd_per_bu
    FROM crop_prices
""", conn, parse_dates=["date"])

cpi = pd.read_sql("""
    SELECT commodity, date, price_index
    FROM commodity_cpi
""", conn, parse_dates=["date"])

# Normalise commodity case
prices["commodity"] = prices["commodity"].str.title()
cpi["commodity"]    = cpi["commodity"].str.title()

national = (prices
            .groupby(["commodity", "date"])["price_usd_per_bu"]
            .mean()
            .reset_index())

print("Data loaded. Building charts...\n")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 1 — Monthly average price trend by commodity
# ══════════════════════════════════════════════════════════════════════════════

fig, ax = plt.subplots(figsize=(12, 5))

for crop, g in national.groupby("commodity"):
    ax.plot(g["date"], g["price_usd_per_bu"],
            label=crop, color=PALETTE[crop], linewidth=2)

# Shade notable price shock (2021-2022 supply crunch)
ax.axvspan(pd.Timestamp("2021-06-01"), pd.Timestamp("2023-01-01"),
           alpha=0.08, color="red", label="2021–22 Supply Crunch")

ax.set_title("US Crop Prices — Monthly National Average (2010–2024)",
             fontsize=14, fontweight="bold", pad=12)
ax.set_xlabel("")
ax.set_ylabel("Price ($/bushel)")
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.2f"))
ax.legend(framealpha=0.9)
fig.tight_layout()
fig.savefig("data/figures/01_price_trends.png")
plt.close(fig)
print("  ✅ Chart 1: Price Trends")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 2 — Volatility heatmap: CV% by state × commodity
# ══════════════════════════════════════════════════════════════════════════════

cv_df = pd.read_sql("""
    SELECT commodity, state,
           ROUND(100.0 * STDEV(price_usd_per_bu) / AVG(price_usd_per_bu), 1) AS cv_pct,
           COUNT(*) AS n
    FROM crop_prices
    GROUP BY commodity, state
    HAVING n >= 24
""", conn)
cv_df["commodity"] = cv_df["commodity"].str.title()

# Pivot: rows = state, cols = commodity
pivot = cv_df.pivot(index="state", columns="commodity", values="cv_pct")
# Keep states with at least 2 crops
pivot = pivot.dropna(thresh=2).fillna(0)
pivot = pivot.loc[pivot.max(axis=1).sort_values(ascending=False).index]

fig, ax = plt.subplots(figsize=(9, max(8, len(pivot)*0.32)))
sns.heatmap(pivot, ax=ax, cmap="YlOrRd", annot=True, fmt=".1f",
            linewidths=0.4, linecolor="#ddd",
            cbar_kws={"label": "CV% (higher = more volatile)"})
ax.set_title("Price Volatility Heatmap — CV% by State × Commodity",
             fontsize=13, fontweight="bold", pad=12)
ax.set_xlabel("")
ax.set_ylabel("")
ax.tick_params(axis="x", labelsize=10)
ax.tick_params(axis="y", labelsize=7)
fig.tight_layout()
fig.savefig("data/figures/02_volatility_heatmap.png", bbox_inches="tight")
plt.close(fig)
print("  ✅ Chart 2: Volatility Heatmap")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 3 — Top 15 price swings by state × crop (swing %)
# ══════════════════════════════════════════════════════════════════════════════

swing = pd.read_sql("""
    SELECT state, commodity,
           ROUND(100.0*(MAX(price_usd_per_bu)-MIN(price_usd_per_bu))
                      / MIN(price_usd_per_bu), 1) AS swing_pct
    FROM crop_prices
    GROUP BY state, commodity
    ORDER BY swing_pct DESC
    LIMIT 15
""", conn)
swing["commodity"] = swing["commodity"].str.title()
swing["label"] = swing["state"].str.title() + " · " + swing["commodity"]

fig, ax = plt.subplots(figsize=(10, 6))
bar_colors = [PALETTE[c] for c in swing["commodity"]]
bars = ax.barh(swing["label"][::-1], swing["swing_pct"][::-1],
               color=bar_colors[::-1], edgecolor="white", height=0.7)

for bar, val in zip(bars, swing["swing_pct"][::-1]):
    ax.text(bar.get_width() + 3, bar.get_y() + bar.get_height()/2,
            f"{val:.0f}%", va="center", fontsize=8.5, color="#333")

ax.set_title("Biggest Price Swings by State & Crop  (2010–2024 peak vs trough)",
             fontsize=13, fontweight="bold", pad=12)
ax.set_xlabel("Price Swing (max − min) / min  (%)")
ax.set_xlim(0, swing["swing_pct"].max() * 1.15)

# Legend
from matplotlib.patches import Patch
legend_els = [Patch(facecolor=PALETTE[c], label=c) for c in PALETTE]
ax.legend(handles=legend_els, loc="lower right", framealpha=0.9)

fig.tight_layout()
fig.savefig("data/figures/03_price_swings.png", bbox_inches="tight")
plt.close(fig)
print("  ✅ Chart 3: Price Swings")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 4 — Farm price vs CPI dual-axis (one subplot per commodity)
# ══════════════════════════════════════════════════════════════════════════════

commodities = ["Wheat", "Corn", "Soybeans"]
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for ax, crop in zip(axes, commodities):
    p = national[national["commodity"] == crop].set_index("date").sort_index()
    c = cpi[cpi["commodity"] == crop.upper()].set_index("date").sort_index()

    color_farm = PALETTE[crop]
    ax2 = ax.twinx()

    ax.plot(p.index, p["price_usd_per_bu"],
            color=color_farm, linewidth=2, label="Farm Price")
    ax2.plot(c.index, c["price_index"],
             color="grey", linewidth=1.5, linestyle="--", label="CPI Index")

    ax.set_title(crop, fontsize=12, fontweight="bold")
    ax.set_ylabel("Farm Price ($/bu)", color=color_farm, fontsize=9)
    ax2.set_ylabel("CPI Index", color="grey", fontsize=9)
    ax.tick_params(axis="y", labelcolor=color_farm)
    ax2.tick_params(axis="y", labelcolor="grey")
    ax.tick_params(axis="x", rotation=30, labelsize=8)

    # Combined legend
    lines1, labs1 = ax.get_legend_handles_labels()
    lines2, labs2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labs1 + labs2, fontsize=8, loc="upper left")

fig.suptitle("Farm Price vs CPI Index — Tight Co-movement by Commodity",
             fontsize=13, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig("data/figures/04_farm_price_vs_cpi.png", bbox_inches="tight")
plt.close(fig)
print("  ✅ Chart 4: Farm Price vs CPI")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 5 — Rolling 12-month price volatility (std dev) per crop
# ══════════════════════════════════════════════════════════════════════════════

fig, ax = plt.subplots(figsize=(12, 5))

for crop, g in national.groupby("commodity"):
    g = g.set_index("date").sort_index()
    rolling_vol = g["price_usd_per_bu"].rolling(12).std()
    ax.plot(rolling_vol.index, rolling_vol,
            label=crop, color=PALETTE[crop], linewidth=2)

ax.axvspan(pd.Timestamp("2021-06-01"), pd.Timestamp("2023-01-01"),
           alpha=0.08, color="red")
ax.set_title("Rolling 12-Month Price Volatility by Commodity",
             fontsize=14, fontweight="bold", pad=12)
ax.set_xlabel("")
ax.set_ylabel("Std Dev of Monthly Price ($/bu)")
ax.legend(framealpha=0.9)
fig.tight_layout()
fig.savefig("data/figures/05_rolling_volatility.png")
plt.close(fig)
print("  ✅ Chart 5: Rolling Volatility")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 6 — State exposure ranked bar chart (avg CV% across crops)
# ══════════════════════════════════════════════════════════════════════════════

state_exp = pd.read_sql("""
    WITH cv AS (
        SELECT state, commodity,
               100.0 * STDEV(price_usd_per_bu) / AVG(price_usd_per_bu) AS cv_pct,
               COUNT(*) AS n
        FROM crop_prices GROUP BY state, commodity HAVING n >= 24
    )
    SELECT state,
           COUNT(DISTINCT commodity) AS n_crops,
           ROUND(AVG(cv_pct), 2)     AS avg_cv_pct
    FROM cv
    GROUP BY state
    HAVING n_crops >= 2
    ORDER BY avg_cv_pct DESC
""", conn)

fig, ax = plt.subplots(figsize=(10, 7))
colors = plt.cm.RdYlGn_r(np.linspace(0.1, 0.9, len(state_exp)))
bars = ax.barh(state_exp["state"][::-1], state_exp["avg_cv_pct"][::-1],
               color=colors[::-1], edgecolor="white", height=0.75)

for bar, val in zip(bars, state_exp["avg_cv_pct"][::-1]):
    ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2,
            f"{val:.1f}%", va="center", fontsize=8.5)

ax.set_title("State Price-Exposure Ranking  (avg CV% across all commodities grown)",
             fontsize=13, fontweight="bold", pad=12)
ax.set_xlabel("Average Coefficient of Variation (%)")
ax.set_xlim(0, state_exp["avg_cv_pct"].max() * 1.15)
fig.tight_layout()
fig.savefig("data/figures/06_state_exposure.png", bbox_inches="tight")
plt.close(fig)
print("  ✅ Chart 6: State Exposure")

conn.close()
print("\n✅ All 6 charts saved to data/figures/")
