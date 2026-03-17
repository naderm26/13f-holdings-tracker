import urllib.request
import urllib.error
import urllib.parse
import json
import os
import time
import glob
import csv

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; 13FAI/1.0)"}

def lookup_via_yahoo(cusip):
    """Try to find ticker via Yahoo Finance search."""
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={cusip}&quotesCount=1&newsCount=0"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        quotes = data.get("quotes", [])
        for q in quotes:
            ticker = q.get("symbol", "")
            # Prefer US-listed tickers (no dot in symbol = US exchange)
            if ticker and "." not in ticker:
                return ticker
        # Fallback to first result even if foreign
        if quotes:
            return quotes[0].get("symbol", "")
    except Exception:
        pass
    return None

def lookup_via_openfigi(cusip):
    """Try OpenFIGI as fallback."""
    url = "https://api.openfigi.com/v3/mapping"
    payload = json.dumps([{"idType": "ID_CUSIP", "idValue": cusip}]).encode()
    headers = {**HEADERS, "Content-Type": "application/json"}
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if data and data[0].get("data"):
            for item in data[0]["data"]:
                if item.get("exchCode") in ("US", "UW", "UN", "UA", "UR"):
                    return item.get("ticker")
            return data[0]["data"][0].get("ticker")
    except Exception:
        pass
    return None

def get_all_cusips_from_csvs():
    """Get all unique CUSIPs from CSV files."""
    cusips = set()
    for csv_file in glob.glob("data/*.csv"):
        try:
            with open(csv_file, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    c = row.get("CUSIP", "").strip()
                    if c and len(c) == 9:
                        cusips.add(c)
        except Exception:
            pass
    return cusips

# ── Main ──────────────────────────────────────────────────────────
existing = {}
if os.path.exists("cusip_to_ticker.json"):
    with open("cusip_to_ticker.json") as f:
        existing = json.load(f)
    print(f"Loaded {len(existing)} existing mappings")

all_cusips   = get_all_cusips_from_csvs()
missing      = [c for c in all_cusips if c not in existing]
print(f"Found {len(missing)} unmapped CUSIPs out of {len(all_cusips)} total")

added = 0
failed = []

for i, cusip in enumerate(missing):
    if (i + 1) % 50 == 0:
        print(f"  [{i+1}/{len(missing)}] mapped {added} so far...")

    # Try Yahoo Finance first
    ticker = lookup_via_yahoo(cusip)
    time.sleep(0.3)

    # Fallback to OpenFIGI if Yahoo fails
    if not ticker:
        ticker = lookup_via_openfigi(cusip)
        time.sleep(1)

    if ticker:
        existing[cusip] = ticker
        added += 1
        print(f"  {cusip} -> {ticker}")
    else:
        failed.append(cusip)

with open("cusip_to_ticker.json", "w") as f:
    json.dump(existing, f, indent=2)

print(f"\nDone. Added {added} new mappings.")
print(f"Still unmapped: {len(failed)}")
if failed:
    print("Failed CUSIPs:")
    for c in failed:
        print(f"  {c}")
