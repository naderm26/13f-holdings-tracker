"""
fetch_congress_data.py
Fetches Nancy Pelosi's Periodic Transaction Reports (PTRs) from the
House financial disclosure system.

Usage:
    pip install pdfplumber requests beautifulsoup4
    python fetch_congress_data.py

Output:
    pelosi_trades.json
"""

import json
import re
import time
from pathlib import Path

import pdfplumber
import requests
from bs4 import BeautifulSoup

# ── Config ───────────────────────────────────────────────────────────────────
LAST_NAME   = "Pelosi"
FIRST_NAME  = "Nancy"
YEARS       = ["2024", "2025", "2026"]
OUTPUT_FILE = "pelosi_trades.json"
PDF_CACHE   = Path("_ptr_cache")

BASE       = "https://disclosures-clerk.house.gov"
SEARCH_URL = BASE + "/FinancialDisclosure/ViewMemberSearchResult"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": BASE + "/FinancialDisclosure/ViewSearch",
}

AMOUNT_MIDPOINTS = {
    "$1,001 - $15,000":           8000,
    "$15,001 - $50,000":         32500,
    "$50,001 - $100,000":        75000,
    "$100,001 - $250,000":      175000,
    "$250,001 - $500,000":      375000,
    "$500,001 - $1,000,000":    750000,
    "$1,000,001 - $5,000,000": 3000000,
    "Over $5,000,000":         5000000,
}

# ── Search ───────────────────────────────────────────────────────────────────

def search_filings(session, year):
    payload = {
        "LastName":    LAST_NAME,
        "FilingYear":  year,
        "State":       "",
        "District":    "",
        "btn_search":  "Search",
    }
    print(f"  Searching {year}...")
    r = session.post(SEARCH_URL, data=payload, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    filings = []
    for row in soup.find_all("tr", role="row"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        filing_type = cells[3].get_text(strip=True)
        if "PTR" not in filing_type.upper():
            continue

        a = cells[0].find("a", href=True)
        if not a:
            continue

        href = a["href"]
        m = re.search(r"ptr-pdfs/(\d{4})/(\d+)\.pdf", href)
        if not m:
            continue

        pdf_year = m.group(1)
        doc_id   = m.group(2)
        url      = BASE + "/" + href

        filings.append({
            "year":        pdf_year,
            "doc_id":      doc_id,
            "filing_date": cells[2].get_text(strip=True),
            "filing_type": filing_type,
            "url":         url,
        })
        print(f"    Found: {filing_type} {pdf_year} doc {doc_id}")

    print(f"    Total PTR filings: {len(filings)}")
    return filings


# ── Download ─────────────────────────────────────────────────────────────────

def download_pdf(filing, session):
    PDF_CACHE.mkdir(exist_ok=True)
    path = PDF_CACHE / f"{filing['doc_id']}.pdf"
    if path.exists():
        print(f"  Cached: {path.name}")
        return path

    print(f"  Downloading: {filing['url']}")
    try:
        r = session.get(filing["url"], timeout=20)
        r.raise_for_status()
        path.write_bytes(r.content)
        print(f"  Saved {len(r.content):,} bytes")
        time.sleep(1)
        return path
    except Exception as e:
        print(f"  Download failed: {e}")
        return None


# ── Parse PDF ────────────────────────────────────────────────────────────────

def parse_amount(raw):
    if not raw:
        return None
    raw = raw.strip()
    for label, mid in AMOUNT_MIDPOINTS.items():
        if label.lower() in raw.lower():
            return mid
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def is_data_row(row):
    """
    A valid data row has:
    - cell[2] (asset) non-empty
    - cell[3] (tx type) is a single letter like P, S, E
    - cell[4] (date) looks like MM/DD/YYYY
    - cell[6] (amount) contains a dollar sign
    All cells must be present (no None merging into first cell).
    """
    if len(row) < 7:
        return False
    # If most cells after index 0 are None, it's a merged/description row
    if row[1] is None and row[2] is None:
        return False
    asset    = (row[2] or "").strip()
    tx_type  = (row[3] or "").strip()
    date     = (row[4] or "").strip()
    amount   = (row[6] or "").strip()
    if not asset or not tx_type or not date:
        return False
    if not re.match(r"\d{2}/\d{2}/\d{4}", date):
        return False
    return True


def parse_pdf(pdf_path, filing_meta):
    trades = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row:
                            continue
                        # Skip header row
                        if (row[0] or "").strip() == "ID":
                            continue
                        if not is_data_row(row):
                            continue

                        asset_name  = (row[2] or "").strip().replace("\n", " ")
                        tx_type_raw = (row[3] or "").strip()
                        date_raw    = (row[4] or "").strip()
                        amount_raw  = (row[6] or "").strip().replace("\n", " ")

                        # Extract ticker from asset name e.g. "Apple Inc. (AAPL)"
                        ticker_match = re.search(r"\(([A-Z]{1,5})\)", asset_name)
                        ticker = ticker_match.group(1) if ticker_match else None

                        # Normalise transaction type
                        # P = Purchase, S = Sale, E = Exchange
                        tx_map = {"P": "Purchase", "S": "Sale", "E": "Exchange"}
                        tx_type = tx_map.get(tx_type_raw.upper(), tx_type_raw)

                        trades.append({
                            "member":       f"{FIRST_NAME} {LAST_NAME}",
                            "filing_year":  filing_meta["filing_date"],
                            "doc_id":       filing_meta["doc_id"],
                            "asset":        asset_name,
                            "ticker":       ticker,
                            "transaction":  tx_type,
                            "date":         date_raw,
                            "amount_range": amount_raw,
                            "amount_mid":   parse_amount(amount_raw),
                        })
    except Exception as e:
        print(f"  PDF parse error: {e}")

    return trades


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    session = requests.Session()

    all_filings = []
    for year in YEARS:
        try:
            filings = search_filings(session, year)
            all_filings.extend(filings)
        except Exception as e:
            print(f"  Search failed for {year}: {e}")
        time.sleep(1)

    if not all_filings:
        print("\nNo filings found.")
        with open(OUTPUT_FILE, "w") as f:
            json.dump([], f)
        return

    all_trades = []
    for filing in all_filings:
        print(f"\nProcessing {filing['doc_id']} ({filing['filing_date']})...")
        pdf_path = download_pdf(filing, session)
        if not pdf_path:
            continue
        trades = parse_pdf(pdf_path, filing)
        print(f"  Parsed {len(trades)} trade(s)")
        all_trades.extend(trades)

    all_trades.sort(key=lambda t: t.get("date") or "", reverse=True)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_trades, f, indent=2)

    print(f"\nDone. {len(all_trades)} total trades -> {OUTPUT_FILE}")
    print(f"\n{'Date':<12} {'Ticker':<8} {'Transaction':<12} {'Amount Range':<30} {'Asset'}")
    print("-" * 95)
    for t in all_trades[:30]:
        print(
            f"{t['date']:<12} "
            f"{(t['ticker'] or '-'):<8} "
            f"{t['transaction']:<12} "
            f"{t['amount_range']:<30} "
            f"{t['asset'][:40]}"
        )
    if len(all_trades) > 30:
        print(f"  ... and {len(all_trades) - 30} more in {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
