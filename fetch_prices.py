import urllib.request
import urllib.error
import json
import os
import time
from datetime import datetime, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; 13FAI/1.0)"}

def fetch_yahoo(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        meta = data["chart"]["result"][0]["meta"]
        return {
            "price":      round(meta.get("regularMarketPrice", 0), 2),
            "week52High": round(meta.get("fiftyTwoWeekHigh", 0), 2),
            "week52Low":  round(meta.get("fiftyTwoWeekLow", 0), 2),
            "currency":   meta.get("currency", "USD"),
            "updated":    datetime.utcnow().strftime("%Y-%m-%d")
        }
    except Exception:
        return None

if not os.path.exists("cusip_to_ticker.json"):
    print("cusip_to_ticker.json not found — run fetch_tickers.py first")
    exit(1)

with open("cusip_to_ticker.json") as f:
    cusip_map = json.load(f)

existing = {}
if os.path.exists("prices.json"):
    with open("prices.json") as f:
        existing = json.load(f)
    print(f"Loaded {len(existing)} existing prices")

tickers = list(set(t for t in cusip_map.values() if t))

# Only fetch new tickers or ones older than 7 days
week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
new_tickers   = [t for t in tickers if t not in existing]
stale_tickers = [t for t in tickers if t in existing and existing[t].get("updated", "") <= week_ago]
refresh_tickers = new_tickers + stale_tickers

print(f"Total tickers: {len(tickers)}")
print(f"New (never fetched): {len(new_tickers)}")
print(f"Stale (>7 days): {len(stale_tickers)}")
print(f"Fetching {len(refresh_tickers)} tickers...")

updated = 0
for i, ticker in enumerate(refresh_tickers):
    data = fetch_yahoo(ticker)
    if data and data["price"] > 0:
        existing[ticker] = data
        updated += 1
    if (i + 1) % 100 == 0:
        print(f"  [{i+1}/{len(refresh_tickers)}] fetched {updated} so far...")
    time.sleep(0.2)

with open("prices.json", "w") as f:
    json.dump(existing, f, indent=2)

print(f"\nDone. Updated {updated} prices. Total: {len(existing)}")
