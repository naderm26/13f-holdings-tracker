"""
debug_pdf.py
Run this once to print the raw table structure pdfplumber sees in the PDFs.
This tells us exactly what column layout to parse.

Usage:
    python debug_pdf.py
"""
import pdfplumber
from pathlib import Path

cache = Path("_ptr_cache")
pdfs = sorted(cache.glob("*.pdf"))

if not pdfs:
    print("No PDFs found in _ptr_cache/")
    exit()

# Inspect the first PDF
pdf_path = pdfs[0]
print(f"Inspecting: {pdf_path}\n")

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages):
        print(f"=== PAGE {page_num + 1} ===")

        # Show raw text
        text = page.extract_text()
        if text:
            print("--- RAW TEXT (first 500 chars) ---")
            print(text[:500])
            print()

        # Show tables
        tables = page.extract_tables()
        print(f"Tables found: {len(tables)}")
        for t_idx, table in enumerate(tables):
            print(f"\n  TABLE {t_idx + 1} ({len(table)} rows):")
            for r_idx, row in enumerate(table):
                print(f"    Row {r_idx}: {row}")
            if t_idx > 2:
                print("  (stopping after 3 tables)")
                break

        # Also try extract_text_lines for non-table PDFs
        print()
