"""
Step 2: SQL Analysis — Crop Price Volatility, State Exposure & CPI Correlation

SQLite doesn't include STDEV or CORR natively, so we register them
as custom Python aggregate functions before running queries.
"""

import sqlite3
import math
import pandas as pd

DB_PATH = "data/agri.db"


# ── Register custom aggregate functions ──────────────────────────────────────

class StdDev:
    """Population std-dev aggregate for SQLite."""
    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0

    def step(self, value):
        if value is None:
            return
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.M2 += delta * (value - self.mean)

    def finalize(self):
        if self.n < 2:
            return None
        return math.sqrt(self.M2 / (self.n - 1))   # sample std-dev


conn = sqlite3.connect(DB_PATH)
conn.create_aggregate("STDEV", 1, StdDev)


def run(title, sql):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print('='*65)
    df = pd.read_sql(sql, conn)
    print(df.to_string(index=False))
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Q1 · Which crop has the highest price volatility by state?
#      Metric: Coefficient of Variation (CV%) = std_dev / mean × 100
# ─────────────────────────────────────────────────────────────────────────────

q1 = run("Q1 · Price Volatility by Commodity × State  (Top 20 by CV%)", """
    SELECT
        commodity,
        state,
        ROUND(AVG(price_usd_per_bu), 2)                          AS avg_price,
        ROUND(STDEV(price_usd_per_bu), 3)                        AS std_dev,
        ROUND(100.0 * STDEV(price_usd_per_bu)
                    / AVG(price_usd_per_bu), 2)                  AS cv_pct,
        COUNT(*)                                                  AS n_months
    FROM crop_prices
    GROUP BY commodity, state
    HAVING n_months >= 24
    ORDER BY cv_pct DESC
    LIMIT 20
""")

q1b = run("Q1b · Overall Volatility per Commodity (all states pooled)", """
    SELECT
        commodity,
        ROUND(AVG(price_usd_per_bu), 2)                         AS avg_price,
        ROUND(STDEV(price_usd_per_bu), 3)                       AS std_dev,
        ROUND(100.0 * STDEV(price_usd_per_bu)
                    / AVG(price_usd_per_bu), 2)                 AS cv_pct,
        COUNT(DISTINCT state)                                    AS n_states,
        COUNT(*)                                                 AS n_obs
    FROM crop_prices
    GROUP BY commodity
    ORDER BY cv_pct DESC
""")


# ─────────────────────────────────────────────────────────────────────────────
# Q2 · Which states are most exposed to price swings?
#      Metric 1: Average CV% across all commodities grown in each state
#      Metric 2: Raw price swing (max − min)
# ─────────────────────────────────────────────────────────────────────────────

q2 = run("Q2 · States Most Exposed to Price Swings  (avg CV% across crops)", """
    WITH state_cv AS (
        SELECT
            state,
            commodity,
            ROUND(100.0 * STDEV(price_usd_per_bu)
                        / AVG(price_usd_per_bu), 2)  AS cv_pct,
            COUNT(*)                                  AS n_obs
        FROM crop_prices
        GROUP BY state, commodity
        HAVING n_obs >= 24
    )
    SELECT
        state,
        COUNT(DISTINCT commodity)           AS n_crops,
        ROUND(AVG(cv_pct), 2)              AS avg_cv_pct,
        ROUND(MAX(cv_pct), 2)              AS max_cv_pct,
        SUM(n_obs)                         AS total_obs
    FROM state_cv
    GROUP BY state
    HAVING n_crops >= 2
    ORDER BY avg_cv_pct DESC
    LIMIT 20
""")

q2b = run("Q2b · Biggest Raw Price Swings by State + Crop  (Top 20)", """
    SELECT
        state,
        commodity,
        ROUND(MIN(price_usd_per_bu), 2)               AS min_price,
        ROUND(MAX(price_usd_per_bu), 2)               AS max_price,
        ROUND(MAX(price_usd_per_bu)
            - MIN(price_usd_per_bu), 2)               AS price_swing,
        ROUND(100.0 * (MAX(price_usd_per_bu) - MIN(price_usd_per_bu))
                    /  MIN(price_usd_per_bu), 1)      AS swing_pct
    FROM crop_prices
    GROUP BY state, commodity
    ORDER BY swing_pct DESC
    LIMIT 20
""")


# ─────────────────────────────────────────────────────────────────────────────
# Q3 · How do farm prices correlate with the commodity CPI?
#      SQLite has no CORR() — we compute Pearson r in pandas after the join.
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n{'='*65}")
print("  Q3 · Farm Price vs CPI Correlation by Commodity")
print('='*65)

joined = pd.read_sql("""
    SELECT
        UPPER(p.commodity)          AS commodity,
        p.state,
        strftime('%Y-%m', p.date)   AS ym,
        p.price_usd_per_bu          AS farm_price,
        c.price_index               AS cpi
    FROM crop_prices  p
    JOIN commodity_cpi c
      ON UPPER(p.commodity) = UPPER(c.commodity)
     AND strftime('%Y-%m', p.date) = strftime('%Y-%m', c.date)
""", conn)

import numpy as np

def pearson_r(x, y):
    """Pearson r between two array-like sequences."""
    x, y = np.array(x, dtype=float), np.array(y, dtype=float)
    if len(x) < 2:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])

# ── Q3 · Commodity-level correlation ─────────────────────────────────────────
print(f"\n{'='*65}")
print("  Q3 · Farm Price vs CPI Correlation by Commodity")
print('='*65)

rows = []
for commodity, g in joined.groupby("commodity"):
    r = pearson_r(g["farm_price"], g["cpi"])
    rows.append({"commodity": commodity, "n_obs": len(g), "pearson_r": round(r, 4)})
q3 = pd.DataFrame(rows).sort_values("pearson_r", ascending=False)
print(q3.to_string(index=False))

# ── Q3b · State × commodity correlation ──────────────────────────────────────
print(f"\n{'='*65}")
print("  Q3b · Farm–CPI Correlation by Commodity × State  (top & bottom 10)")
print('='*65)

rows = []
for (commodity, state), g in joined.groupby(["commodity", "state"]):
    if len(g) < 24:
        continue
    r = pearson_r(g["farm_price"], g["cpi"])
    rows.append({"commodity": commodity, "state": state,
                 "n_obs": len(g), "pearson_r": round(r, 4)})
q3b = pd.DataFrame(rows).sort_values("pearson_r", ascending=False)

top10 = q3b.head(10).assign(rank_group="high")
bot10 = q3b.tail(10).assign(rank_group="low")
print(pd.concat([top10, bot10]).to_string(index=False))


conn.close()
print("\n✅ Analysis complete.")
