"""
Step 1: Clean raw USDA + FRED data and load into SQLite database
"""

import pandas as pd
import sqlite3
import os

DB_PATH = "data/agri.db"
os.makedirs("data", exist_ok=True)

# ── 1. USDA CROP PRICE DATA ──────────────────────────────────────────────────

def load_usda(filepath, commodity_name):
    df = pd.read_csv(filepath)

    # Keep only the aggregate commodity row (not subtypes like WHEAT, WINTER)
    # Corn's data item starts with "CORN, GRAIN" so we match by "PRICE RECEIVED"
    df = df[df['Data Item'].str.contains("PRICE RECEIVED")]
    # For wheat, drop subtypes (WINTER, SPRING etc) — keep only the aggregate
    if commodity_name == "WHEAT":
        df = df[df['Data Item'].str.startswith("WHEAT - PRICE RECEIVED")]

    # Keep only monthly periods (drop MARKETING YEAR — it's an annual summary)
    monthly_periods = ['JAN','FEB','MAR','APR','MAY','JUN',
                       'JUL','AUG','SEP','OCT','NOV','DEC']
    df = df[df['Period'].isin(monthly_periods)]

    # Drop suppressed/withheld values: (S) and (D)
    df = df[~df['Value'].astype(str).str.strip().isin(['(S)', '(D)', '(Z)', ''])]

    # Select and rename columns
    df = df[['Year', 'Period', 'State', 'Value']].copy()
    df.columns = ['year', 'month', 'state', 'price_usd_per_bu']
    df['commodity'] = commodity_name.title()

    # Convert price to float
    df['price_usd_per_bu'] = pd.to_numeric(df['price_usd_per_bu'], errors='coerce')
    df = df.dropna(subset=['price_usd_per_bu'])

    # Create a proper date column (first day of each month)
    month_map = {'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,
                 'JUL':7,'AUG':8,'SEP':9,'OCT':10,'NOV':11,'DEC':12}
    df['month_num'] = df['month'].map(month_map)
    df['date'] = pd.to_datetime(dict(year=df['year'], month=df['month_num'], day=1))
    df = df.drop(columns=['month', 'month_num'])

    print(f"  {commodity_name}: {len(df)} rows, {df['state'].nunique()} states, "
          f"{df['year'].min()}-{df['year'].max()}")
    return df


print("Loading USDA data...")
wheat = load_usda("data/raw/wheat.csv", "WHEAT")
corn  = load_usda("data/raw/Corn.csv", "CORN")
soy   = load_usda("data/raw/soybean.csv", "SOYBEANS")

crop_prices = pd.concat([wheat, corn, soy], ignore_index=True)
print(f"  Total crop price rows: {len(crop_prices)}")


# ── 2. FRED CPI DATA ─────────────────────────────────────────────────────────

def load_fred(filepath, commodity_name):
    df = pd.read_csv(filepath)
    df.columns = ['date', 'price_index']
    df['date'] = pd.to_datetime(df['date'])
    df['commodity'] = commodity_name

    # Drop rows where index is missing
    df['price_index'] = pd.to_numeric(df['price_index'], errors='coerce')
    df = df.dropna(subset=['price_index'])

    # Filter to match USDA range: 2010 onwards
    df = df[df['date'] >= '2010-01-01']

    print(f"  {commodity_name} CPI: {len(df)} rows, "
          f"{df['date'].min().date()} to {df['date'].max().date()}")
    return df


print("\nLoading FRED CPI data...")
wheat_cpi = load_fred("data/raw/wheatCPI.csv", "WHEAT")
corn_cpi  = load_fred("data/raw/cornCPI.csv", "CORN")
soy_cpi   = load_fred("data/raw/SoybeanCPI.csv", "SOYBEANS")

commodity_cpi = pd.concat([wheat_cpi, corn_cpi, soy_cpi], ignore_index=True)
print(f"  Total CPI rows: {len(commodity_cpi)}")


# ── 3. WRITE TO SQLITE ───────────────────────────────────────────────────────

print(f"\nWriting to {DB_PATH}...")
conn = sqlite3.connect(DB_PATH)

crop_prices.to_sql("crop_prices", conn, if_exists="replace", index=False)
commodity_cpi.to_sql("commodity_cpi", conn, if_exists="replace", index=False)

# ── 4. VERIFY ────────────────────────────────────────────────────────────────

print("\n=== DATABASE TABLES ===")
for table in ["crop_prices", "commodity_cpi"]:
    count = pd.read_sql(f"SELECT COUNT(*) as n FROM {table}", conn).iloc[0,0]
    cols  = pd.read_sql(f"SELECT * FROM {table} LIMIT 1", conn).columns.tolist()
    print(f"  {table}: {count} rows | columns: {cols}")

print("\n=== SAMPLE: crop_prices ===")
print(pd.read_sql("""
    SELECT commodity, state, date, price_usd_per_bu
    FROM crop_prices
    ORDER BY date DESC
    LIMIT 6
""", conn).to_string(index=False))

print("\n=== SAMPLE: commodity_cpi ===")
print(pd.read_sql("""
    SELECT commodity, date, price_index
    FROM commodity_cpi
    ORDER BY date DESC
    LIMIT 6
""", conn).to_string(index=False))

conn.close()
print("\n✅ Database built successfully → data/agri.db")
