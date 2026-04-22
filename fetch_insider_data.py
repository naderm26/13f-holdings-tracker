"""
fetch_insider_data.py
Fetches Form 4 insider trading data from SEC EDGAR for tracked companies.
Stores per-stock JSON files in data/insiders/{ticker}.json
Only captures open market purchases (P) and sales (S) — discretionary trades only.
"""

import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import json
import os
import time
from datetime import datetime, timezone, timedelta

# Hard timeout — stop fetching new companies after this many minutes
# Protects GitHub Actions minutes budget
MAX_RUNTIME_MINUTES = 25

HEADERS = {"User-Agent": "13fai@proton.me"}
# On initial run (no data yet): uses LOOKBACK_DAYS_INIT = 90
# On daily incremental runs (data exists): uses LOOKBACK_DAYS_DAILY = 5
# This avoids scanning 200 filings per company every day
LOOKBACK_DAYS_INIT  = 90
LOOKBACK_DAYS_DAILY = 5
MAX_FILINGS         = 40   # plenty for a 5-day window; was 200 which was wasteful daily

# Transaction codes we care about — open market buys and sells only
SIGNAL_CODES = {"P", "S"}

# Load companies from company_ciks.json (built by build_company_ciks.py)
# Falls back to pilot 10 if file not found
import os as _os
if _os.path.exists("company_ciks.json"):
    with open("company_ciks.json") as _f:
        _raw = json.load(_f)
    PILOT_COMPANIES = {
        ticker: {"cik": info["cik"], "name": info["name"]}
        for ticker, info in _raw.items()
    }
    print(f"Loaded {len(PILOT_COMPANIES)} companies from company_ciks.json")
else:
    print("company_ciks.json not found — using pilot 10 stocks")
    PILOT_COMPANIES = {
        "AAPL": {"cik": "0000320193", "name": "Apple Inc"},
        "AXP":  {"cik": "0000004962", "name": "American Express Co"},
        "MSFT": {"cik": "0000789019", "name": "Microsoft Corp"},
        "BAC":  {"cik": "0000070858", "name": "Bank of America Corp"},
        "KO":   {"cik": "0000021344", "name": "Coca-Cola Co"},
        "MCO":  {"cik": "0001059556", "name": "Moody's Corp"},
        "GOOGL":{"cik": "0001652044", "name": "Alphabet Inc"},
        "V":    {"cik": "0001403161", "name": "Visa Inc"},
        "AMZN": {"cik": "0001018724", "name": "Amazon.com Inc"},
        "CVX":  {"cik": "0000093410", "name": "Chevron Corp"},
    }

def fetch_url(url, retries=3):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif e.code == 404:
                return None
            else:
                print(f"  HTTP {e.code}, retrying...")
                time.sleep(3)
        except Exception as e:
            print(f"  Error: {e}, retrying...")
            time.sleep(3)
    return None

def collect_form4_filings(cik, cutoff_date):
    """
    Collect Form 4 filing accession numbers for a company CIK
    filed on or after cutoff_date.
    Uses the same EDGAR submissions API as fetch_data.py.
    """
    cik_padded = cik.zfill(10) if not cik.startswith("0") else cik
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    data = fetch_url(url)
    if not data:
        print(f"  Could not load submissions for CIK {cik}")
        return []

    try:
        submissions = json.loads(data)
    except Exception as e:
        print(f"  Failed to parse submissions JSON: {e}")
        return []

    collected = []

    def scan_filings(filings_obj):
        forms   = filings_obj.get("form", [])
        accnums = filings_obj.get("accessionNumber", [])
        dates   = filings_obj.get("filingDate", [])
        for i, form in enumerate(forms):
            if form not in ("4", "4/A"):
                continue
            filed = dates[i] if i < len(dates) else ""
            if filed < cutoff_date:
                # Filings are sorted newest first — stop once we go past cutoff
                return True  # signal to stop
            collected.append({
                "accession": accnums[i].replace("-", ""),
                "accession_raw": accnums[i],
                "filed": filed
            })
            if len(collected) >= MAX_FILINGS:
                return True
        return False

    # Scan recent filings
    recent = submissions.get("filings", {}).get("recent", {})
    stop = scan_filings(recent)

    # Paginate if needed and not yet at cutoff
    if not stop:
        for file_entry in submissions.get("filings", {}).get("files", []):
            if len(collected) >= MAX_FILINGS:
                break
            try:
                page_url  = f"https://data.sec.gov/submissions/{file_entry['name']}"
                page_data = fetch_url(page_url)
                if page_data:
                    page = json.loads(page_data)
                    stop = scan_filings(page)
                    if stop:
                        break
            except Exception as e:
                print(f"  Pagination error: {e}")

    return collected

def parse_form4_xml(xml_bytes, filed_date):
    """
    Parse Form 4 XML and extract non-derivative transactions
    with code P (purchase) or S (sale) only.
    Returns list of transaction dicts.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  XML parse error: {e}")
        return []

    # Reporting person info
    rp = root.find(".//reportingOwner")
    if rp is None:
        return []

    insider_name  = ""
    insider_title = ""
    name_el = rp.find(".//rptOwnerName")
    if name_el is not None and name_el.text:
        insider_name = name_el.text.strip()

    # Title from relationship
    rel = rp.find(".//reportingOwnerRelationship")
    if rel is not None:
        title_el = rel.find("officerTitle")
        is_dir   = rel.findtext("isDirector", "0").strip()
        is_off   = rel.findtext("isOfficer",  "0").strip()
        is_ten   = rel.findtext("isTenPercentOwner", "0").strip()
        if title_el is not None and title_el.text:
            insider_title = title_el.text.strip()
        elif is_dir == "1":
            insider_title = "Director"
        elif is_ten == "1":
            insider_title = "10% Owner"

    if not insider_name:
        return []

    transactions = []
    for tx in root.findall(".//nonDerivativeTransaction"):
        code_el = tx.find(".//transactionCode")
        if code_el is None or not code_el.text:
            continue
        code = code_el.text.strip().upper()
        if code not in SIGNAL_CODES:
            continue

        # Transaction date
        date_el = tx.find(".//transactionDate/value")
        tx_date = date_el.text.strip() if date_el is not None and date_el.text else filed_date

        # Shares
        shares_el = tx.find(".//transactionShares/value")
        shares = 0
        if shares_el is not None and shares_el.text:
            try:
                shares = float(shares_el.text.strip())
            except ValueError:
                pass

        # Price per share
        price_el = tx.find(".//transactionPricePerShare/value")
        price = 0.0
        if price_el is not None and price_el.text:
            try:
                price = float(price_el.text.strip())
            except ValueError:
                pass

        # Shares owned after transaction
        after_el = tx.find(".//sharesOwnedFollowingTransaction/value")
        shares_after = 0
        if after_el is not None and after_el.text:
            try:
                shares_after = float(after_el.text.strip())
            except ValueError:
                pass

        # Skip zero-share entries
        if shares == 0:
            continue

        value = round(shares * price, 2) if price > 0 else 0

        transactions.append({
            "insider":      insider_name,
            "title":        insider_title,
            "date":         tx_date,
            "filed":        filed_date,
            "code":         code,           # P = buy, S = sell
            "shares":       int(shares),
            "price":        price,
            "value":        value,
            "shares_after": int(shares_after),
        })

    return transactions

def get_form4_xml_url(cik, accession):
    """Find the Form 4 XML file URL from the filing index."""
    cik_stripped = str(int(cik))
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/index.json"
    data = fetch_url(index_url)
    if not data:
        return None
    try:
        index = json.loads(data)
        for item in index.get("directory", {}).get("item", []):
            name = item.get("name", "").lower()
            if name.endswith(".xml") and name != "primary_doc.xml":
                if any(k in name for k in ["form4", "form-4", "xslf4", "ownership", "doc4"]):
                    return f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{item['name']}"
        # Fallback: first XML that isn't primary_doc
        for item in index.get("directory", {}).get("item", []):
            name = item.get("name", "").lower()
            if name.endswith(".xml") and name != "primary_doc.xml":
                return f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{item['name']}"
    except Exception as e:
        print(f"  Index parse error: {e}")
    return None

def load_existing(ticker):
    """Load existing per-stock insider JSON or return empty structure."""
    path = f"data/insiders/{ticker}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"ticker": ticker, "transactions": []}

def save_stock(ticker, company_name, cik, data):
    """Save per-stock insider JSON."""
    data["ticker"]  = ticker
    data["company"] = company_name
    data["cik"]     = cik
    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = f"data/insiders/{ticker}.json"
    with open(path, "w") as f:
        json.dump(data, f)
    print(f"  Saved {path}")

# ── Main ─────────────────────────────────────────────────────────
# Use short lookback if we already have data for at least half the companies
# (indicates this is an incremental run not an initial backfill)
_existing_count = sum(
    1 for t in PILOT_COMPANIES
    if os.path.exists(f"data/insiders/{t}.json")
)
_is_incremental = _existing_count >= len(PILOT_COMPANIES) // 2
_lookback = LOOKBACK_DAYS_DAILY if _is_incremental else LOOKBACK_DAYS_INIT

cutoff     = (datetime.now(timezone.utc) - timedelta(days=_lookback)).strftime("%Y-%m-%d")
start_time = time.time()
run_type   = "incremental" if _is_incremental else "initial backfill"
print(f"Fetching Form 4 insider data ({run_type}, cutoff: {cutoff})...")
print(f"Tracking {len(PILOT_COMPANIES)} companies | timeout: {MAX_RUNTIME_MINUTES} min\n")

os.makedirs("data/insiders", exist_ok=True)
timed_out = False

for ticker, info in PILOT_COMPANIES.items():
    elapsed = (time.time() - start_time) / 60
    if elapsed >= MAX_RUNTIME_MINUTES:
        print(f"\n⚠ Timeout reached ({MAX_RUNTIME_MINUTES} min). Stopping early.")
        print(f"  Completed {list(PILOT_COMPANIES.keys()).index(ticker)} of {len(PILOT_COMPANIES)} companies.")
        print(f"  Remaining companies will be fetched on the next run.")
        timed_out = True
        break
    cik          = info["cik"]
    company_name = info["name"]
    print(f"\n{ticker} ({company_name})...")

    # Load existing data — skip accessions we already have
    stock_data   = load_existing(ticker)
    existing_acc = {tx.get("accession", "") for tx in stock_data.get("transactions", [])}

    filings = collect_form4_filings(cik, cutoff)
    print(f"  Found {len(filings)} Form 4 filings since {cutoff}")

    new_transactions = []
    for filing in filings:
        accession  = filing["accession"]
        filed_date = filing["filed"]

        # Attach accession to each transaction for dedup
        if accession in existing_acc:
            continue

        xml_url = get_form4_xml_url(cik, accession)
        if not xml_url:
            print(f"  Could not find XML for {accession}")
            time.sleep(0.3)
            continue

        xml_bytes = fetch_url(xml_url)
        if not xml_bytes:
            time.sleep(0.3)
            continue

        txs = parse_form4_xml(xml_bytes, filed_date)
        for tx in txs:
            tx["accession"] = filing["accession_raw"]
        new_transactions.extend(txs)
        time.sleep(0.3)

    if new_transactions:
        # Merge with existing, sort by date descending
        all_txs = stock_data.get("transactions", []) + new_transactions
        all_txs.sort(key=lambda x: x["date"], reverse=True)
        stock_data["transactions"] = all_txs
        print(f"  Added {len(new_transactions)} new transactions "
              f"(P={sum(1 for t in new_transactions if t['code']=='P')}, "
              f"S={sum(1 for t in new_transactions if t['code']=='S')})")
        save_stock(ticker, company_name, cik, stock_data)
    else:
        print(f"  No new transactions — skipping save")

    time.sleep(0.5)  # reduced from 1s since we skip save on no-change

elapsed_total = (time.time() - start_time) / 60
if timed_out:
    print(f"\nStopped early after {elapsed_total:.1f} min — budget limit reached.")
else:
    print(f"\nDone fetching insider data in {elapsed_total:.1f} min.")
