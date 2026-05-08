"""
debug_pdf.py
Inspects all PDFs in _ptr_cache/ and cross-checks against parsed JSON.
Run after fetch_congress_data.py --keep-pdfs

Usage:
    python debug_pdf.py              # inspect all cached PDFs
    python debug_pdf.py pelosi       # filter by member name
    python debug_pdf.py 20029138     # deep-dive a specific doc ID
"""

import json
import re
import sys
from pathlib import Path

import pdfplumber

PDF_CACHE    = Path("_ptr_cache")
DATA_DIR     = Path("data/congress")
MEMBERS_FILE = "congress_members.json"

FILTER = sys.argv[1].lower() if len(sys.argv) > 1 else None


def is_data_row(row):
    if not row or len(row) < 7:
        return False
    if row[1] is None and row[2] is None:
        return False
    date = (row[4] or "").strip()
    return bool(re.match(r"\d{2}/\d{2}/\d{4}", date))


def deep_dive(pdf_path):
    """Print every raw row from every table in the PDF — for debugging a specific doc."""
    print(f"\n{'='*70}")
    print(f"DEEP DIVE: {pdf_path.name}")
    print(f"{'='*70}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                print(f"\n--- PAGE {page_num + 1} ---")
                text = page.extract_text() or ""
                if text:
                    print("RAW TEXT (first 800 chars):")
                    print(text[:800])

                tables = page.extract_tables()
                print(f"\nTables found: {len(tables)}")
                for t_idx, table in enumerate(tables):
                    print(f"\n  Table {t_idx + 1} ({len(table)} rows):")
                    for r_idx, row in enumerate(table):
                        is_data = is_data_row(row)
                        marker  = "DATA" if is_data else "    "
                        print(f"    [{marker}] Row {r_idx:02d}: {row}")
    except Exception as e:
        print(f"ERROR: {e}")


def parse_merged_row(text):
    """Same fallback parser as fetch_congress_data.py."""
    text = re.sub(r'\x00+', '', text)
    text = re.sub(r'\s*\[(?:ST|OP|OT|MF|DC|GS)\]', '', text)
    text = re.sub(r'F\s+S\s*:.*$', '', text, flags=re.DOTALL)
    text = re.sub(r'\n', ' ', text).strip()
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\s+(?:Class\s+[A-Z]\s+)?(?:Common\s+Stock\s+)?\([A-Z]{1,5}\)\s*$', '', text).strip()
    text = re.sub(r'\s+(?:Registry\s+)?(?:Common\s+)?(?:Ordinary\s+)?(?:Shares?|Stock)\s*$', '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'\s+\([A-Z]{1,5}\)\s*$', '', text).strip()
    m = re.search(
        r'^(.+?)\s+(P|S(?:\s*\((?:partial|full)\))?|E)\s+(\d{2}/\d{2}/\d{4})\s+\d{2}/\d{2}/\d{4}\s+(\$[\d,]+\s*-\s*\$[\d,]+|\$[\d,]+)\s*$',
        text, re.IGNORECASE
    )
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()


def inspect_pdf(pdf_path):
    """Return all rows that look like trade data, including merged single-cell rows."""
    rows = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                for t_idx, table in enumerate(page.extract_tables()):
                    for r_idx, row in enumerate(table):
                        if not row:
                            continue
                        if (row[0] or "").strip() == "ID":
                            continue

                        if is_data_row(row):
                            asset  = (row[2] or "").strip().replace("\n", " ")
                            tx     = (row[3] or "").strip()
                            date   = (row[4] or "").strip()
                            amount = (row[6] or "").strip().replace("\n", " ")
                        elif row[0] and all(c is None for c in row[1:]):
                            parsed = parse_merged_row(row[0])
                            if not parsed:
                                continue
                            asset, tx, date, amount = parsed
                        else:
                            continue

                        ticker_match = re.search(r"\(([A-Z]{1,5})\)", asset)
                        rows.append({
                            "page":   page_num + 1,
                            "asset":  asset,
                            "tx":     tx,
                            "date":   date,
                            "amount": amount,
                            "ticker": ticker_match.group(1) if ticker_match else "—",
                        })
    except Exception as e:
        print(f"  ERROR reading {pdf_path.name}: {e}")
    return rows


def main():
    if not PDF_CACHE.exists():
        print("No _ptr_cache/ folder found.")
        print("Run: python fetch_congress_data.py --keep-pdfs")
        return

    # Load parsed data for cross-checking
    parsed_by_doc = {}
    for json_path in DATA_DIR.glob("*.json"):
        try:
            with open(json_path) as f:
                data = json.load(f)
            for trade in data.get("trades", []):
                doc_id = trade.get("doc_id")
                if doc_id:
                    parsed_by_doc.setdefault(doc_id, []).append(trade)
        except Exception:
            pass

    pdfs = sorted(PDF_CACHE.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {PDF_CACHE}/")
        return

    # If filter looks like a doc ID, do a deep dive on that specific PDF
    if FILTER and re.match(r"^\d{7,9}$", FILTER):
        pdf_path = PDF_CACHE / f"{FILTER}.pdf"
        if pdf_path.exists():
            deep_dive(pdf_path)
            parsed = parsed_by_doc.get(FILTER, [])
            print(f"\nParsed trades for this doc: {len(parsed)}")
            for t in parsed:
                print(f"  {t['date']}  {t.get('ticker','—')}  {t['transaction']}  {t['amount_range']}")
        else:
            print(f"PDF not found: {pdf_path}")
        return

    print(f"Found {len(pdfs)} PDF(s) in {PDF_CACHE}/\n")

    total_raw    = 0
    total_parsed = 0
    issues       = []

    for pdf_path in pdfs:
        doc_id = pdf_path.stem

        # Skip old-format doc IDs
        if doc_id.startswith("8") or doc_id.startswith("9"):
            continue

        # Apply name filter
        if FILTER:
            matched = False
            if doc_id in parsed_by_doc:
                member_name = (parsed_by_doc[doc_id][0].get("member") or "").lower()
                if FILTER in member_name:
                    matched = True
            if not matched:
                continue

        raw_rows    = inspect_pdf(pdf_path)
        parsed_rows = parsed_by_doc.get(doc_id, [])

        total_raw    += len(raw_rows)
        total_parsed += len(parsed_rows)

        if len(raw_rows) == 0 and len(parsed_rows) == 0:
            continue  # silent skip for genuinely empty docs

        print(f"{'─'*60}")
        member = parsed_rows[0].get("member", "?") if parsed_rows else "?"
        print(f"Doc {doc_id}  [{member}]  ({len(raw_rows)} raw, {len(parsed_rows)} parsed)")
        print(f"{'─'*60}")

        for row in raw_rows:
            parsed_match = any(
                t.get("doc_id") == doc_id and
                t.get("date")   == row["date"] and
                t.get("ticker") == row["ticker"]
                for t in parsed_rows
            )
            status = "✓" if parsed_match else "✗ MISSING"
            print(f"  {status}  {row['date']:<12} {row['ticker']:<8} {row['tx']:<16} {row['amount']:<30}  {row['asset'][:45]}")

        if len(raw_rows) != len(parsed_rows):
            diff = len(raw_rows) - len(parsed_rows)
            msg  = f"Doc {doc_id} [{member}]: {len(raw_rows)} raw but {len(parsed_rows)} parsed ({diff} missing)"
            issues.append(msg)
            print(f"\n  ⚠  {msg}")

        print()

    # Summary
    print(f"{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total raw data rows  : {total_raw}")
    print(f"Total parsed trades  : {total_parsed}")
    print(f"Discrepancies        : {len(issues)}")

    if issues:
        print("\nIssues:")
        for issue in issues:
            print(f"  ⚠  {issue}")
        print("\nTo deep-dive a specific doc:")
        print("  python debug_pdf.py <doc_id>")
    else:
        print("\nAll rows accounted for.")


if __name__ == "__main__":
    main()
