"""
build_company_ciks.py
Builds company_ciks.json mapping top 100 S&P 500 tickers to EDGAR CIKs.
Uses SEC EDGAR's public company_tickers.json endpoint — no scraping needed.
Run once, then update manually when composition changes.
To expand coverage later, add tickers to SP500_TICKERS below.
"""

import urllib.request
import json

HEADERS = {"User-Agent": "13fai@proton.me"}

# Top 100 S&P 500 companies by market cap as of April 2026
# Add more tickers here to expand coverage
SP500_TICKERS = [
    "NVDA", "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA",
    "BRK.B", "WMT", "LLY", "JPM", "V", "XOM", "MA", "AVGO",
    "HD", "JNJ", "COST", "PG", "ABBV", "MRK", "CVX", "KO",
    "NFLX", "AMD", "BAC", "GE", "CSCO", "CRM", "IBM", "LIN",
    "RTX", "GS", "MS", "NOW", "TMO", "PEP", "NEE", "ISRG",
    "MCD", "T", "TXN", "CAT", "VZ", "PM", "WFC", "DIS",
    "UNH", "LOW", "GEV", "QCOM", "ABT", "DHR", "CB", "ACN",
    "HON", "SPGI", "INTU", "ETN", "TJX", "BLK", "SYK", "BKNG",
    "PGR", "MDT", "PLD", "ANET", "ADI", "COP", "CME", "SCHW",
    "MO", "GILD", "BMY", "HCA", "PANW", "LRCX", "TMUS", "NEM",
    "SO", "SBUX", "CEG", "COF", "VRTX", "DUK", "MCK", "NOC",
    "AMAT", "PH", "APH", "BA", "UBER", "DE", "WELL", "BSX",
    "CMCSA", "CRWD", "AXP", "MCO",
]

# Deduplicate while preserving order
seen = set()
TICKERS = []
for t in SP500_TICKERS:
    if t not in seen:
        seen.add(t)
        TICKERS.append(t)

def fetch_url(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        return urllib.request.urlopen(req, timeout=30).read()
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None

print(f"Building company_ciks.json for {len(TICKERS)} tickers...")
print("Fetching EDGAR company ticker map...")

data = fetch_url("https://www.sec.gov/files/company_tickers.json")
if not data:
    print("Failed to fetch company_tickers.json from EDGAR")
    exit(1)

edgar_map = json.loads(data)

# Build ticker -> CIK lookup
# EDGAR format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
ticker_to_cik = {}
for entry in edgar_map.values():
    ticker = entry.get("ticker", "").upper()
    cik_int = entry.get("cik_str", 0)
    cik_str = str(cik_int).zfill(10)
    if ticker:
        ticker_to_cik[ticker] = {
            "cik":  "0" + cik_str.lstrip("0").zfill(9),
            "name": entry.get("title", ticker)
        }

print(f"EDGAR map loaded: {len(ticker_to_cik)} total companies")

# Match tickers
company_ciks = {}
not_found    = []

for ticker in TICKERS:
    # BRK.B -> BRK-B in EDGAR
    edgar_ticker = ticker.replace(".", "-")
    if edgar_ticker in ticker_to_cik:
        company_ciks[ticker] = ticker_to_cik[edgar_ticker]
    elif ticker in ticker_to_cik:
        company_ciks[ticker] = ticker_to_cik[ticker]
    else:
        not_found.append(ticker)

print(f"Matched: {len(company_ciks)} / {len(TICKERS)} tickers")
if not_found:
    print(f"Not found in EDGAR (may need manual CIK): {not_found}")

with open("company_ciks.json", "w") as f:
    json.dump(company_ciks, f, indent=2)

print(f"\nSaved company_ciks.json")
print("Sample entries:")
for ticker in list(company_ciks.keys())[:5]:
    d = company_ciks[ticker]
    print(f"  {ticker}: CIK {d['cik']} — {d['name']}")
