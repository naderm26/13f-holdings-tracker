"""
fetch_congress_data.py
Fetches Periodic Transaction Reports (PTRs) for all members listed in
congress_members.json from the House financial disclosure system.

Usage:
    pip install pdfplumber requests beautifulsoup4
    python fetch_congress_data.py            # fetches and deletes PDFs after
    python fetch_congress_data.py --keep-pdfs  # keeps PDFs in _ptr_cache/ for debugging

Output:
    data/congress/{member_id}.json   — one file per member
"""

import json
import re
import shutil
import sys
import time
from pathlib import Path

import pdfplumber
import requests
from bs4 import BeautifulSoup

# ── Config ───────────────────────────────────────────────────────────────────
MEMBERS_FILE = "congress_members.json"
OUTPUT_DIR   = Path("data/congress")
PDF_CACHE    = Path("_ptr_cache")
YEARS        = ["2023", "2024", "2025", "2026"]
KEEP_PDFS    = "--keep-pdfs" in sys.argv

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
    "$5,000,001 - $25,000,000": 15000000,
    "Over $25,000,000":        25000000,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def toISO(date_str):
    if not date_str:
        return ""
    parts = date_str.split("/")
    if len(parts) != 3:
        return date_str
    m, d, y = parts
    return f"{y}-{m.zfill(2)}-{d.zfill(2)}"


def parse_amount(raw):
    if not raw:
        return None
    raw = raw.strip()
    for label, mid in AMOUNT_MIDPOINTS.items():
        if label.lower() in raw.lower():
            return mid
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def clean_asset_name(asset):
    s = asset.replace("\n", " ")
    s = re.sub(r"\s*\[(ST|OP|OT|MF|DC)\]\s*", "", s).strip()
    s = re.sub(r"\s*\([A-Z]{1,5}\)\s*$", "", s).strip()
    s = re.sub(r"\s*-\s*(Class [A-Z]\s+)?(Common Stock|Common|Ordinary Shares?|ADR|ADS).*$", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"[\s\-,]+$", "", s).strip()
    return s


def asset_type(asset):
    if "[OP]" in asset: return "Option"
    if "[OT]" in asset: return "Other"
    if "[MF]" in asset: return "Fund"
    return ""


def is_valid_trade(tx, amount_mid):
    if not tx:
        return False
    if tx.lower() == "exchange":
        return False
    if not amount_mid or amount_mid < 1000:
        return False
    return True


# ── Search ────────────────────────────────────────────────────────────────────

def search_filings(session, last_name, year):
    payload = {
        "LastName":   last_name,
        "FilingYear": year,
        "State":      "",
        "District":   "",
        "btn_search": "Search",
    }
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
        doc_id = m.group(2)
        # Skip old scanned-PDF format — doc IDs starting with 8 or 9 are
        # pre-eFD paper filings with no extractable table structure
        if doc_id.startswith("8") or doc_id.startswith("9"):
            continue
        filings.append({
            "year":        m.group(1),
            "doc_id":      doc_id,
            "filing_year": cells[2].get_text(strip=True),
            "filing_type": filing_type,
            "url":         BASE + "/" + href,
        })

    return filings


# ── Download ──────────────────────────────────────────────────────────────────

def download_pdf(filing, session):
    PDF_CACHE.mkdir(exist_ok=True)
    path = PDF_CACHE / f"{filing['doc_id']}.pdf"
    if path.exists():
        return path
    try:
        r = session.get(filing["url"], timeout=20)
        r.raise_for_status()
        path.write_bytes(r.content)
        time.sleep(1)
        return path
    except Exception as e:
        print(f"    Download failed {filing['doc_id']}: {e}")
        return None


# ── Parse PDF ─────────────────────────────────────────────────────────────────

def is_data_row(row):
    if len(row) < 7:
        return False
    if row[1] is None and row[2] is None:
        return False
    date = (row[4] or "").strip()
    if not re.match(r"\d{2}/\d{2}/\d{4}", date):
        return False
    return True


def parse_merged_row(text):
    """
    Some rows get merged into a single cell by pdfplumber, e.g.:
    'Nike, Inc. (NKE) [ST] P 04/08/2025 04/09/2025 $1,001 - $15,000'
    Extract fields using regex on the raw text.
    Returns (asset, tx, date, amount) or None if no match.
    """
    text = text.replace("\n", " ").strip()
    # Match: ...asset... TX_CODE MM/DD/YYYY MM/DD/YYYY $amount
    m = re.search(
        r"^(.+?)\s+([PSE](?:\s*\((?:partial|full)\))?)\s+(\d{2}/\d{2}/\d{4})\s+\d{2}/\d{2}/\d{4}\s+(\$[\d,\s\-]+(?:,\d{3})*(?:\s*-\s*\$[\d,\s]+)?)\s*$",
        text, re.IGNORECASE
    )
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()


def parse_pdf(pdf_path, filing_meta, member_name):
    trades = []
    skipped = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    for row in table:
                        if not row:
                            continue
                        if (row[0] or "").strip() == "ID":
                            continue

                        # ── Normal well-structured row ────────────────────
                        if is_data_row(row):
                            asset_raw  = (row[2] or "").strip().replace("\n", " ")
                            tx_raw     = (row[3] or "").strip()
                            date_raw   = (row[4] or "").strip()
                            amount_raw = (row[6] or "").strip().replace("\n", " ")
                            amount_mid = parse_amount(amount_raw)

                        # ── Merged single-cell row fallback ───────────────
                        elif row[0] and all(c is None for c in row[1:]):
                            parsed = parse_merged_row(row[0])
                            if not parsed:
                                continue
                            asset_raw, tx_raw, date_raw, amount_raw = parsed
                            amount_mid = parse_amount(amount_raw)

                        else:
                            continue

                        if not is_valid_trade(tx_raw, amount_mid):
                            skipped.append({
                                "asset": asset_raw,
                                "tx":    tx_raw,
                                "date":  date_raw,
                                "amount": amount_raw,
                                "reason": "exchange" if tx_raw.lower() == "exchange" else "below_threshold"
                            })
                            continue

                        ticker_match = re.search(r"\(([A-Z]{1,5})\)", asset_raw)
                        ticker = ticker_match.group(1) if ticker_match else None

                        tx_map = {
                            "P":           "Purchase",
                            "S":           "Sale",
                            "S (PARTIAL)": "S (partial)",
                            "S (FULL)":    "S (full)",
                            "E":           "Exchange",
                        }
                        tx = tx_map.get(tx_raw.upper(), tx_raw)

                        trades.append({
                            "member":       member_name,
                            "filing_year":  filing_meta["filing_year"],
                            "doc_id":       filing_meta["doc_id"],
                            "asset":        asset_raw,
                            "asset_clean":  clean_asset_name(asset_raw),
                            "asset_type":   asset_type(asset_raw),
                            "ticker":       ticker,
                            "transaction":  tx,
                            "date":         date_raw,
                            "date_iso":     toISO(date_raw),
                            "amount_range": amount_raw,
                            "amount_mid":   amount_mid,
                        })
    except Exception as e:
        print(f"    PDF parse error {pdf_path}: {e}")
    return trades, skipped


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    with open(MEMBERS_FILE) as f:
        members = json.load(f)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    if KEEP_PDFS:
        print("-- keep-pdfs mode: PDFs will NOT be deleted after parsing --\n")

    for member in members:
        print(f"\n{'='*60}")
        print(f"Processing: {member['name']}")
        print(f"{'='*60}")

        all_trades  = []
        all_skipped = []

        for year in YEARS:
            print(f"  Searching {year}...")
            try:
                filings = search_filings(session, member["last_name"], year)
                print(f"    Found {len(filings)} PTR filing(s)")
            except Exception as e:
                print(f"    Search failed: {e}")
                filings = []
            time.sleep(0.5)

            for filing in filings:
                pdf_path = download_pdf(filing, session)
                if not pdf_path:
                    continue
                trades, skipped = parse_pdf(pdf_path, filing, member["name"])
                print(f"    Doc {filing['doc_id']}: {len(trades)} trade(s) parsed, {len(skipped)} skipped")
                all_trades.extend(trades)
                all_skipped.extend(skipped)

        all_trades.sort(key=lambda t: t.get("date_iso") or "", reverse=True)

        out_path = OUTPUT_DIR / f"{member['id']}.json"
        with open(out_path, "w") as f:
            json.dump({
                "id":       member["id"],
                "name":     member["name"],
                "slug":     member["slug"],
                "party":    member["party"],
                "state":    member["state"],
                "district": member["district"],
                "chamber":  member["chamber"],
                "title":    member["title"],
                "trades":   all_trades,
                "skipped":  all_skipped,
            }, f, indent=2)

        print(f"  Total: {len(all_trades)} trades, {len(all_skipped)} skipped -> {out_path}")

    if not KEEP_PDFS:
        if PDF_CACHE.exists():
            shutil.rmtree(PDF_CACHE)
            print(f"\nDeleted PDF cache: {PDF_CACHE}")
    else:
        print(f"\nPDFs kept in {PDF_CACHE}/ for debugging")

    print("\nDone.")


if __name__ == "__main__":
    main()
