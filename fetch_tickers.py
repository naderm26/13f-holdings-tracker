import urllib.request
import urllib.error
import json
import os
import glob
import csv
import time
from collections import defaultdict

HEADERS = {"User-Agent": "nadermassoudi@aol.com", "Content-Type": "application/json"}
FIGI_URL = "https://api.openfigi.com/v3/mapping"

def get_cusips_by_value():
    """Collect all CUSIPs ranked by total value across all funds."""
    cusip_value = defaultdict(int)

    with open("funds.json") as f:
        funds = json.load(f)

    # Build multiplier map
    multipliers = {f["id"]: f.get("value_multiplier", 1) for f in funds}

    for csv_file in glob.glob("data/*.csv"):
        # Get fund id from filename e.g. data/berkshire_2025Q4.csv
        fund_id = os.path.basename(csv_file).split("_")[0]
        mult = multipliers.get(fund_id, 1)

        try:
            with open(csv_file, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cusip = row.get("CUSIP", "").strip()
                    value = int(row.get("Value", 0) or 0)
                    if cusip and len(cusip) == 9:
                        cusip_value[cusip] += value * mult
        except Exception:
            pass

    # Sort by total value descending
    sorted_cusips = sorted(cusip_value.keys(), key=lambda c: cusip_value[c], reverse=True)
    print(f"Found {len(sorted_cusips)} unique CUSIPs, sorted by total value")
    print(f"Top 5 by value:")
    for c in sorted_cusips[:5]:
        print(f"  {c}: ${cusip_value[c]:,.0f}")
    return sorted_cusips

def lookup_batch(cusips):
    payload = json.dumps([{"idType": "ID_CUSIP", "idValue": c} for c in cusips]).encode()
    req = urllib.request.Request(FIGI_URL, data=payload, headers=HEADERS, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=30).read()
        return json.loads(resp)
    except Exception as e:
        print(f"  OpenFIGI error: {e}")
        return [None] * len(cusips)

def fetch_all_tickers(cusips):
    mapping = {}
    batch_size = 10
    total = len(cusips)

    for i in range(0, total, batch_size):
        batch = cusips[i:i + batch_size]
        if (i // batch_size) % 10 == 0:
            print(f"  Looking up {i+1}-{min(i+batch_size, total)} of {total}...")
        results = lookup_batch(batch)

        for cusip, result in zip(batch, results):
            if result and result.get("data"):
                ticker = None
                for item in result["data"]:
                    if item.get("exchCode") in ("US", "UW", "UN", "UA", "UR"):
                        ticker = item.get("ticker")
                        break
                if not ticker:
                    ticker = result["data"][0].get("ticker")
                if ticker:
                    mapping[cusip] = ticker

        time.sleep(0.5)

    return mapping

# ── Main ──────────────────────────────────────────────────────────
existing = {}
if os.path.exists("cusip_to_ticker.json"):
    with open("cusip_to_ticker.json") as f:
        existing = json.load(f)
    print(f"Loaded {len(existing)} existing mappings")

all_cusips = get_cusips_by_value()
new_cusips = [c for c in all_cusips if c not in existing]
print(f"Looking up {len(new_cusips)} new CUSIPs (skipping {len(existing)} already mapped)")

if new_cusips:
    new_mapping = fetch_all_tickers(new_cusips)
    existing.update(new_mapping)
    print(f"Added {len(new_mapping)} new ticker mappings")

with open("cusip_to_ticker.json", "w") as f:
    json.dump(existing, f, indent=2)

found = sum(1 for v in existing.values() if v)
print(f"\nDone. {found} / {len(existing)} CUSIPs mapped to tickers")
print("Saved to cusip_to_ticker.json")
