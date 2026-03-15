import urllib.request
import urllib.error
import json
import os
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; 13FInsider/1.0)"}

def fetch_yahoo(ticker):
    """Fetch last price and 52wk high/low from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        meta = data["chart"]["result"][0]["meta"]
        return {
            "price":     round(meta.get("regularMarketPrice", 0), 2),
            "week52High": round(meta.get("fiftyTwoWeekHigh", 0), 2),
            "week52Low":  round(meta.get("fiftyTwoWeekLow", 0), 2),
            "currency":  meta.get("currency", "USD")
        }
    except Exception as e:
        return None

# ── Main ──────────────────────────────────────────────────────────
if not os.path.exists("cusip_to_ticker.json"):
    print("cusip_to_ticker.json not found — run fetch_tickers.py first")
    exit(1)

with open("cusip_to_ticker.json") as f:
    cusip_map = json.load(f)

# Load existing prices
existing = {}
if os.path.exists("prices.json"):
    with open("prices.json") as f:
        existing = json.load(f)
    print(f"Loaded {len(existing)} existing prices")

tickers = list(set(t for t in cusip_map.values() if t))
print(f"Fetching prices for {len(tickers)} tickers...")

updated = 0
for i, ticker in enumerate(tickers):
    data = fetch_yahoo(ticker)
    if data and data["price"] > 0:
        existing[ticker] = data
        updated += 1
    if (i + 1) % 50 == 0:
        print(f"  [{i+1}/{len(tickers)}] fetched {updated} prices so far...")
    time.sleep(0.2)

with open("prices.json", "w") as f:
    json.dump(existing, f, indent=2)

print(f"\nDone. {updated} prices saved to prices.json")
