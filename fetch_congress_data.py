"""
fetch_congress_data.py
Scrapes congress' Periodic Transaction Reports (PTRs) from the
US House of Representatives financial disclosure system.

Usage:
    pip install pdfplumber requests
    python fetch_pelosi_trades.py

Output:
    pelosi_trades.json  — structured list of all trades found
"""

import json
import re
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import pdfplumber
import requests

# ── Config ─────────────────────────────────────────────────────────────────
LAST_NAME   = "Pelosi"
FIRST_NAME  = "Nancy"
YEARS       = [2024, 2025, 2026]   # years to fetch
OUTPUT_FILE = "pelosi_trades.json"
PDF_CACHE   = Path("_ptr_cache")    # local cache folder so we don't re-download

BASE_URL    = "https://disclosures-clerk.house.gov"
XML_URL     = BASE_URL + "/public_disc/financial-pdfs/{year}/FD.xml"
PDF_URL     = BASE_URL + "/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://disclosures-clerk.house.gov/",
}

# Amount range midpoints (USD) — House uses these standard buckets
AMOUNT_MIDPOINTS = {
    "$1,001 - $15,000":       8000,
    "$15,001 - $50,000":     32500,
    "$50,001 - $100,000":    75000,
    "$100,001 - $250,000":  175000,
    "$250,001 - $500,000":  375000,
    "$500,001 - $1,000,000": 750000,
    "$1,000,001 - $5,000,000": 3000000,
    "Over $5,000,000":       5000000,
}

# ── Helpers ────────────────────────────────────────────────────────────────

def fetch(url, binary=False):
    """Fetch URL with retries."""
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.content if binary else r.text
        except requests.RequestException as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)
    return None


def get_filing_ids(year):
    """
    Parse the annual FD XML index and return PTR filing metadata
    for the target member.
    """
    url = XML_URL.format(year=year)
    print(f"Fetching index for {year}: {url}")
    xml_text = fetch(url)
    if not xml_text:
        print(f"  Could not fetch index for {year}")
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"  XML parse error for {year}: {e}")
        return []

    filings = []
    # The XML structure: <FinancialDisclosure> → <Member> elements
    # Each <Member> has: <Last>, <First>, <FilingType>, <DocID>, <Year>, <FilingDate>
    for member in root.findall(".//Member"):
        last  = (member.findtext("Last")  or "").strip().upper()
        first = (member.findtext("First") or "").strip().upper()
        ftype = (member.findtext("FilingType") or "").strip()

        if last != LAST_NAME.upper():
            continue
        if FIRST_NAME and FIRST_NAME.upper() not in first:
            continue
        if ftype != "P":   # "P" = Periodic Transaction Report
            continue

        doc_id      = (member.findtext("DocID") or "").strip()
        filing_date = (member.findtext("FilingDate") or "").strip()
        office      = (member.findtext("StateDst") or "").strip()

        if doc_id:
            filings.append({
                "year":        year,
                "doc_id":      doc_id,
                "filing_date": filing_date,
                "office":      office,
            })

    print(f"  Found {len(filings)} PTR filing(s) for {LAST_NAME} in {year}")
    return filings


def download_pdf(year, doc_id):
    """Download PDF to cache, return local path."""
    PDF_CACHE.mkdir(exist_ok=True)
    path = PDF_CACHE / f"{doc_id}.pdf"
    if path.exists():
        print(f"  Using cached PDF: {path}")
        return path

    url = PDF_URL.format(year=year, doc_id=doc_id)
    print(f"  Downloading: {url}")
    data = fetch(url, binary=True)
    if not data:
        print(f"  Failed to download {doc_id}")
        return None

    path.write_bytes(data)
    print(f"  Saved: {path} ({len(data):,} bytes)")
    time.sleep(1)  # be polite
    return path


def parse_amount(raw):
    """Convert amount range string to midpoint integer."""
    if not raw:
        return None
    raw = raw.strip()
    for label, mid in AMOUNT_MIDPOINTS.items():
        if label.lower() in raw.lower():
            return mid
    # Try to parse a plain number
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def parse_pdf(pdf_path, filing_meta):
    """
    Extract transaction rows from a House PTR PDF.

    The PDF table typically has columns:
      SP* | Asset Name | Asset Type | Transaction Type | Date | Notify Date |
      Amount | Cap Gains | Description

    We extract: asset name, ticker (if in name), transaction type, date, amount.
    """
    trades = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 5:
                            continue

                        # Skip header rows
                        first_cell = (row[0] or "").strip().lower()
                        if first_cell in ("sp*", "asset name", "owner", ""):
                            continue
                        # Skip rows that look like page headers/footers
                        joined = " ".join(str(c or "") for c in row)
                        if "Clerk of the House" in joined or "PERIODIC" in joined.upper():
                            continue

                        # Columns vary slightly by form version — try to detect
                        # by looking for a date-shaped cell
                        # Typical order: [SP, Asset, AssetType, TxType, Date, NotifyDate, Amount, CapGains, Description]
                        asset_name    = (row[1] if len(row) > 1 else "") or ""
                        tx_type_raw   = (row[3] if len(row) > 3 else "") or ""
                        date_raw      = (row[4] if len(row) > 4 else "") or ""
                        amount_raw    = (row[6] if len(row) > 6 else "") or ""
                        description   = (row[8] if len(row) > 8 else "") or ""

                        asset_name  = asset_name.strip().replace("\n", " ")
                        tx_type_raw = tx_type_raw.strip()
                        date_raw    = date_raw.strip()

                        # Skip rows without a recognisable transaction type
                        tx_type_norm = tx_type_raw.upper()
                        if not any(t in tx_type_norm for t in ("PURCHASE", "SALE", "EXCHANGE", "RECEIPT")):
                            continue

                        # Extract ticker from asset name — often in parentheses: "Apple Inc. (AAPL)"
                        ticker_match = re.search(r"\(([A-Z]{1,5})\)", asset_name)
                        ticker = ticker_match.group(1) if ticker_match else None

                        # Normalise transaction type
                        if "PURCHASE" in tx_type_norm:
                            tx_type = "Purchase"
                        elif "SALE (FULL)" in tx_type_norm:
                            tx_type = "Sale (Full)"
                        elif "SALE (PARTIAL)" in tx_type_norm:
                            tx_type = "Sale (Partial)"
                        elif "SALE" in tx_type_norm:
                            tx_type = "Sale"
                        elif "EXCHANGE" in tx_type_norm:
                            tx_type = "Exchange"
                        else:
                            tx_type = tx_type_raw

                        trade = {
                            "member":       f"{FIRST_NAME} {LAST_NAME}",
                            "filing_date":  filing_meta["filing_date"],
                            "doc_id":       filing_meta["doc_id"],
                            "asset":        asset_name,
                            "ticker":       ticker,
                            "transaction":  tx_type,
                            "date":         date_raw,
                            "amount_range": amount_raw.strip(),
                            "amount_mid":   parse_amount(amount_raw),
                            "description":  description.strip().replace("\n", " "),
                        }
                        trades.append(trade)

    except Exception as e:
        print(f"  PDF parse error for {pdf_path}: {e}")

    return trades


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    all_trades = []

    for year in YEARS:
        filings = get_filing_ids(year)
        for filing in filings:
            pdf_path = download_pdf(filing["year"], filing["doc_id"])
            if not pdf_path:
                continue
            trades = parse_pdf(pdf_path, filing)
            print(f"  Parsed {len(trades)} trade(s) from doc {filing['doc_id']}")
            all_trades.extend(trades)

    # Sort by date descending
    all_trades.sort(key=lambda t: t.get("date") or "", reverse=True)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_trades, f, indent=2)

    print(f"\nDone. {len(all_trades)} total trades written to {OUTPUT_FILE}")

    # Print a quick summary table
    print(f"\n{'Date':<12} {'Ticker':<8} {'Transaction':<18} {'Amount Range':<30} {'Asset'}")
    print("-" * 100)
    for t in all_trades[:30]:
        print(
            f"{t['date']:<12} "
            f"{(t['ticker'] or '—'):<8} "
            f"{t['transaction']:<18} "
            f"{t['amount_range']:<30} "
            f"{t['asset'][:45]}"
        )
    if len(all_trades) > 30:
        print(f"  ... and {len(all_trades) - 30} more in {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
