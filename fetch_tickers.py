import urllib.request
import urllib.error
import json
import os
import glob
import csv
import time

HEADERS = {"User-Agent": "nadermassoudi@aol.com", "Content-Type": "application/json"}
FIGI_URL = "https://api.openfigi.com/v3/mapping"

def get_all_cusips():
    """Collect all unique CUSIPs from all CSVs in data/."""
    cusips = set()
    for csv_file in glob.glob("data/*.csv"):
        with open(csv_file, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                c = row.get("CUSIP", "").strip()
                if c and len(c) == 9:
                    cusips.add(c)
    print(f"Found {len(cusips)} unique CUSIPs")
    return list(cusips)

def lookup_batch(cusips):
    """Look up a batch of up to 100 CUSIPs via OpenFIGI."""
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
    batch_size = 100
    total = len(cusips)

    for i in range(0, total, batch_size):
        batch = cusips[i:i + batch_size]
        print(f"  Looking up {i+1}-{min(i+batch_size, total)} of {total}...")
        results = lookup_batch(batch)

        for cusip, result in zip(batch, results):
            if result and result.get("data"):
                # Prefer common stock on US exchanges
                ticker = None
                for item in result["data"]:
                    if item.get("exchCode") in ("US", "UW", "UN", "UA", "UR"):
                        ticker = item.get("ticker")
                        break
                if not ticker:
                    ticker = result["data"][0].get("ticker")
                if ticker:
                    mapping[cusip] = ticker

        time.sleep(1)  # OpenFIGI rate limit

    return mapping

# ── Main ──────────────────────────────────────────────────────────
# Load existing mapping if it exists
existing = {}
if os.path.exists("cusip_to_ticker.json"):
    with open("cusip_to_ticker.json") as f:
        existing = json.load(f)
    print(f"Loaded {len(existing)} existing mappings")

all_cusips = get_all_cusips()
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
