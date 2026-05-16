"""
generate_insider_index.py
Builds insider_index.json from per-stock insider JSON files in data/insiders/.
Aggregates buy/sell counts, net shares, and recent transactions per stock.
"""

import json
import os
from datetime import datetime, timezone, timedelta

LOOKBACK_DAYS = 90

cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
print(f"Building insider_index.json (lookback: {cutoff})...")

insider_index = {}

insiders_dir = "data/insiders"
if not os.path.exists(insiders_dir):
    print("No data/insiders/ directory found. Run fetch_insider_data.py first.")
    exit(0)

files = [f for f in os.listdir(insiders_dir) if f.endswith(".json")]
print(f"Found {len(files)} stock files")

for filename in sorted(files):
    ticker = filename.replace(".json", "")
    path   = os.path.join(insiders_dir, filename)

    with open(path) as f:
        data = json.load(f)

    all_txs = data.get("transactions", [])

    # Filter to lookback window
    recent_txs = [t for t in all_txs if t.get("date", "") >= cutoff]

    buys  = [t for t in recent_txs if t["code"] == "P"]
    sells = [t for t in recent_txs if t["code"] == "S"]

    net_shares = sum(t["shares"] for t in buys) - sum(t["shares"] for t in sells)
    net_value  = sum(t["value"]  for t in buys) - sum(t["value"]  for t in sells)

    last_tx_date = all_txs[0]["date"] if all_txs else ""

    insider_index[ticker] = {
        "company":        data.get("company", ""),
        "cik":            data.get("cik", ""),
        "buys_90d":       len(buys),
        "sells_90d":      len(sells),
        "net_shares_90d": int(net_shares),
        "net_value_90d":  round(net_value, 2),
        "last_tx_date":   last_tx_date,
        "updated":        data.get("updated", ""),
        "transactions":   recent_txs  # only recent transactions in index
    }

# Sort by net_value_90d descending for easy consumption
sorted_index = dict(
    sorted(insider_index.items(),
           key=lambda x: x[1]["net_value_90d"],
           reverse=True)
)

today = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d")
with open("insider_index.json", "w") as f:
    json.dump({"last_updated": today, "stocks": sorted_index}, f)

total_buys  = sum(v["buys_90d"]  for v in sorted_index.values())
total_sells = sum(v["sells_90d"] for v in sorted_index.values())
print(f"Done. Indexed {len(sorted_index)} stocks — "
      f"{total_buys} buys, {total_sells} sells in last {LOOKBACK_DAYS} days.")
