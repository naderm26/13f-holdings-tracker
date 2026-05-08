"""
fetch_congress_data.py
Fetches Nancy Pelosi's Periodic Transaction Reports (PTRs) from the
House financial disclosure system by POSTing to the ASPX search form,
then downloading and parsing each PDF.

Usage:
    pip install pdfplumber requests
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

# ── Config ──────────────────────────────────────────────────────────────────
LAST_NAME   = "Pelosi"
FIRST_NAME  = "Nancy"
YEARS       = ["2024", "2025", "2026"]
OUTPUT_FILE = "pelosi_trades.json"
PDF_CACHE   = Path("_ptr_cache")

BASE        = "https://disclosures-clerk.house.gov"
SEARCH_URL  = BASE + "/FinancialDisclosure/ViewMemberSearchResult"
PDF_URL     = BASE + "/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE + "/FinancialDisclosure",
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

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_session():
    """Return a requests.Session with cookies from the disclosure homepage."""
    s = requests.Session()
    s.headers.update(HEADERS)
    r = s.get(BASE + "/FinancialDisclosure", timeout=15)
    r.raise_for_status()
    return s, r.text


def extract_viewstate(html):
    """Pull ASP.NET hidden form fields needed to POST."""
    fields = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        m = re.search(rf'id="{re.escape(name)}"[^>]*value="([^"]*)"', html)
        if m:
            fields[name] = m.group(1)
    return fields


def search_filings(session, home_html, year):
    """
    POST to the ASPX search form and return list of
    {doc_id, filing_date, filing_type} dicts for PTR filings.
    """
    vs = extract_viewstate(home_html)
    if not vs.get("__VIEWSTATE"):
        print(f"  Could not extract ViewState for {year}")
        return []

    payload = {
        "__VIEWSTATE":          vs.get("__VIEWSTATE", ""),
        "__VIEWSTATEGENERATOR": vs.get("__VIEWSTATEGENERATOR", ""),
        "__EVENTVALIDATION":    vs.get("__EVENTVALIDATION", ""),
        "LastName":             LAST_NAME,
        "FilingYear":           year,
        "State":                "",
        "District":             "",
        "btnSearch":            "Search",
    }

    r = session.post(
        BASE + "/FinancialDisclosure/ViewMemberSearchResult",
        data=payload,
        headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    r.raise_for_status()

    filings = []
    # Parse the result table — rows look like:
    # <tr><td>Pelosi, Nancy</td><td>PTR</td><td>01/17/2025</td>
    #     <td><a href="/public_disc/ptr-pdfs/2025/20026590.pdf">View</a></td></tr>
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.DOTALL)
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 3:
            continue

        # Strip HTML tags from cells
        def strip(s):
            return re.sub(r"<[^>]+>", "", s).strip()

        name_cell    = strip(cells[0])
        type_cell    = strip(cells[1]) if len(cells) > 1 else ""
        date_cell    = strip(cells[2]) if len(cells) > 2 else ""

        # Only PTRs
        if "PTR" not in type_cell.upper() and "Periodic" not in type_cell:
            continue

        # Extract doc ID from the PDF link href
        link_match = re.search(r"/(\d+)\.pdf", row)
        if not link_match:
            continue

        doc_id = link_match.group(1)

        filings.append({
            "year":        year,
            "doc_id":      doc_id,
            "filing_date": date_cell,
            "filing_type": type_cell,
        })

    return filings


def download_pdf(year, doc_id, session):
    PDF_CACHE.mkdir(exist_ok=True)
    path = PDF_CACHE / f"{doc_id}.pdf"
    if path.exists():
        print(f"  Cached: {path}")
        return path

    url = PDF_URL.format(year=year, doc_id=doc_id)
    print(f"  Downloading: {url}")
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        path.write_bytes(r.content)
        print(f"  Saved {len(r.content):,} bytes")
        time.sleep(1)
        return path
    except Exception as e:
        print(f"  Download failed: {e}")
        return None


def parse_amount(raw):
    if not raw:
        return None
    raw = raw.strip()
    for label, mid in AMOUNT_MIDPOINTS.items():
        if label.lower() in raw.lower():
            return mid
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def parse_pdf(pdf_path, filing_meta):
    trades = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 5:
                            continue
                        first_cell = (row[0] or "").strip().lower()
                        if first_cell in ("sp*", "asset name", "owner", ""):
                            continue
                        joined = " ".join(str(c or "") for c in row)
                        if "Clerk of the House" in joined or "PERIODIC" in joined.upper():
                            continue

                        asset_name  = (row[1] if len(row) > 1 else "") or ""
                        tx_type_raw = (row[3] if len(row) > 3 else "") or ""
                        date_raw    = (row[4] if len(row) > 4 else "") or ""
                        amount_raw  = (row[6] if len(row) > 6 else "") or ""
                        description = (row[8] if len(row) > 8 else "") or ""

                        asset_name  = asset_name.strip().replace("\n", " ")
                        tx_type_raw = tx_type_raw.strip()
                        date_raw    = date_raw.strip()

                        tx_type_norm = tx_type_raw.upper()
                        if not any(t in tx_type_norm for t in ("PURCHASE", "SALE", "EXCHANGE", "RECEIPT")):
                            continue

                        ticker_match = re.search(r"\(([A-Z]{1,5})\)", asset_name)
                        ticker = ticker_match.group(1) if ticker_match else None

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

                        trades.append({
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
                        })
    except Exception as e:
        print(f"  PDF parse error: {e}")

    return trades


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Starting session...")
    try:
        session, home_html = get_session()
    except Exception as e:
        print(f"Failed to connect to House disclosure site: {e}")
        return

    all_filings = []
    for year in YEARS:
        print(f"\nSearching {year}...")
        try:
            filings = search_filings(session, home_html, year)
            print(f"  Found {len(filings)} PTR filing(s)")
            all_filings.extend(filings)
        except Exception as e:
            print(f"  Search failed for {year}: {e}")

    if not all_filings:
        print("\nNo filings found. The search form structure may have changed.")
        print("Check https://disclosures-clerk.house.gov/FinancialDisclosure manually.")
        return

    all_trades = []
    for filing in all_filings:
        print(f"\nProcessing doc {filing['doc_id']} ({filing['filing_date']})...")
        pdf_path = download_pdf(filing["year"], filing["doc_id"], session)
        if not pdf_path:
            continue
        trades = parse_pdf(pdf_path, filing)
        print(f"  Parsed {len(trades)} trade(s)")
        all_trades.extend(trades)

    all_trades.sort(key=lambda t: t.get("date") or "", reverse=True)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_trades, f, indent=2)

    print(f"\nDone. {len(all_trades)} total trades → {OUTPUT_FILE}")
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
