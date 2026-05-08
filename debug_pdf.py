"""
debug_pdf.py
Inspects all PDFs in _ptr_cache/ and prints the raw table structure
for each one, grouped by member. Run after fetch_congress_data.py --keep-pdfs.

Also cross-checks parsed trades in data/congress/*.json against
the raw PDF content to flag any potential missed rows.

Usage:
    python debug_pdf.py              # inspect all cached PDFs
    python debug_pdf.py pelosi       # inspect only PDFs for a specific member
"""

import json
import re
import sys
from pathlib import Path

import pdfplumber

PDF_CACHE  = Path("_ptr_cache")
DATA_DIR   = Path("data/congress")
MEMBERS_FILE = "congress_members.json"

FILTER = sys.argv[1].lower() if len(sys.argv) > 1 else None


def is_data_row(row):
    if not row or len(row) < 7:
        return False
    if row[1] is None and row[2] is None:
        return False
    date = (row[4] or "").strip()
    return bool(re.match(r"\d{2}/\d{2}/\d{4}", date))


def inspect_pdf(pdf_path):
    """Return all table rows that look like trade data."""
    rows = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for t_idx, table in enumerate(tables):
                    for r_idx, row in enumerate(table):
                        if not row:
                            continue
                        if (row[0] or "").strip() == "ID":
                            continue
                        if is_data_row(row):
                            rows.append({
                                "page":    page_num + 1,
                                "table":   t_idx + 1,
                                "row_idx": r_idx,
                                "raw":     row,
                                "asset":   (row[2] or "").strip().replace("\n", " "),
                                "tx":      (row[3] or "").strip(),
                                "date":    (row[4] or "").strip(),
                                "amount":  (row[6] or "").strip().replace("\n", " "),
                            })
    except Exception as e:
        print(f"  ERROR reading {pdf_path.name}: {e}")
    return rows


def main():
    if not PDF_CACHE.exists():
        print("No _ptr_cache/ folder found.")
        print("Run: python fetch_congress_data.py --keep-pdfs")
        return

    # Load members config to map doc IDs to members
    try:
        with open(MEMBERS_FILE) as f:
            members = {m["id"]: m for m in json.load(f)}
    except FileNotFoundError:
        members = {}

    # Load existing parsed data to cross-check
    parsed_by_doc = {}
    for json_path in DATA_DIR.glob("*.json"):
        try:
            with open(json_path) as f:
                data = json.load(f)
            for trade in data.get("trades", []):
                doc_id = trade.get("doc_id")
                if doc_id:
                    parsed_by_doc.setdefault(doc_id, []).append(trade)
            for skipped in data.get("skipped", []):
                pass  # just noting they exist
        except Exception:
            pass

    pdfs = sorted(PDF_CACHE.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {PDF_CACHE}/")
        print("Run: python fetch_congress_data.py --keep-pdfs")
        return

    print(f"Found {len(pdfs)} PDF(s) in {PDF_CACHE}/\n")

    total_raw   = 0
    total_parsed = 0
    issues       = []

    for pdf_path in pdfs:
        doc_id = pdf_path.stem

        # Apply member filter if specified
        if FILTER and FILTER not in doc_id.lower():
            # Try to match against member name via parsed data
            matched_member = None
            if doc_id in parsed_by_doc:
                member_name = (parsed_by_doc[doc_id][0].get("member") or "").lower()
                if FILTER not in member_name:
                    continue
            else:
                continue

        raw_rows    = inspect_pdf(pdf_path)
        parsed_rows = parsed_by_doc.get(doc_id, [])

        total_raw    += len(raw_rows)
        total_parsed += len(parsed_rows)

        print(f"{'─'*60}")
        print(f"Doc {doc_id}  ({len(raw_rows)} raw data rows, {len(parsed_rows)} parsed trades)")
        print(f"{'─'*60}")

        if not raw_rows:
            print("  No data rows found in PDF — possible column layout mismatch")
            issues.append(f"Doc {doc_id}: 0 raw rows extracted")
            continue

        # Print each raw row
        for row in raw_rows:
            ticker_match = re.search(r"\(([A-Z]{1,5})\)", row["asset"])
            ticker = ticker_match.group(1) if ticker_match else "—"
            parsed_match = any(
                t.get("doc_id") == doc_id and t.get("date") == row["date"] and t.get("ticker") == ticker
                for t in parsed_rows
            )
            status = "✓" if parsed_match else "✗ MISSING"
            print(f"  {status}  {row['date']:<12} {ticker:<8} {row['tx']:<14} {row['amount']:<30}  {row['asset'][:50]}")

        # Flag discrepancy
        if len(raw_rows) != len(parsed_rows):
            diff = len(raw_rows) - len(parsed_rows)
            msg = f"Doc {doc_id}: {len(raw_rows)} raw rows but only {len(parsed_rows)} parsed ({diff} missing)"
            issues.append(msg)
            print(f"\n  ⚠ {msg}")

        print()

    # Summary
    print(f"{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total PDFs inspected : {len(pdfs)}")
    print(f"Total raw data rows  : {total_raw}")
    print(f"Total parsed trades  : {total_parsed}")
    print(f"Discrepancies        : {len(issues)}")

    if issues:
        print("\nIssues found:")
        for issue in issues:
            print(f"  ⚠ {issue}")
        print("\nTo investigate a specific doc, run:")
        print("  python debug_pdf.py <doc_id_or_member_name>")
    else:
        print("\nAll rows accounted for — no missing trades detected.")


if __name__ == "__main__":
    main()
