"""
add_congress_nav.py
Adds the Congressional Trades nav link to all HTML files in the repo root.
Run once from your repo root:
    python add_congress_nav.py

Rules:
- Inserts after the 13F Filing Calendar link
- On congress.html and *-trades.html pages, uses class="nav-link active"
- Updates both desktop nav and mobile nav row in each file
- Skips files that already have the link
"""

import os
import re
from pathlib import Path

# The anchor after which we insert the new link
AFTER = '<a class="nav-link" href="filing-calendar.html">13F Filing Calendar</a>'

# Pages where the link should be "active"
ACTIVE_SLUGS = ["congress.html", "-trades.html"]

def is_active_page(filename):
    return filename == "congress.html" or filename.endswith("-trades.html")

def make_link(filename):
    cls = "nav-link active" if is_active_page(filename) else "nav-link"
    return f'<a class="{cls}" href="congress.html">Congressional Trades</a>'

def process_file(filepath):
    filename = filepath.name
    content  = filepath.read_text(encoding="utf-8")

    # Skip if already has the link
    if 'href="congress.html">Congressional Trades</a>' in content:
        print(f"  SKIP (already has link): {filename}")
        return

    link     = make_link(filename)
    insert   = AFTER + "\n        " + link
    new_content = content.replace(AFTER, insert)

    if new_content == content:
        print(f"  SKIP (anchor not found): {filename}")
        return

    filepath.write_text(new_content, encoding="utf-8")
    count = new_content.count('href="congress.html">Congressional Trades</a>')
    print(f"  UPDATED ({count} insertion(s)): {filename}")

def main():
    root  = Path(".")
    htmls = sorted(root.glob("*.html"))

    if not htmls:
        print("No HTML files found. Run this from your repo root.")
        return

    print(f"Processing {len(htmls)} HTML file(s)...\n")
    for f in htmls:
        process_file(f)
    print("\nDone.")

if __name__ == "__main__":
    main()
