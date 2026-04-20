"""
generate_llms_txt.py
Generates llms.txt — a directory of all pages on 13fai.com for LLMs and AI agents.
Run after generate_stock_index.py so stock_index.json is fresh.
"""

import json
import os

BASE_URL = "https://13fai.com"

# ── Load data files ──────────────────────────────────────────────────────────

with open("funds.json", encoding="utf-8") as f:
    funds = json.load(f)

with open("funds_content.json", encoding="utf-8") as f:
    funds_content = json.load(f)

with open("stock_index.json", encoding="utf-8") as f:
    raw = json.load(f)
    stocks = raw.get("stocks", raw)  # handle both schema versions

# ── Build output ─────────────────────────────────────────────────────────────

lines = []

# Header
lines += [
    "# 13FAI",
    "",
    "> Hedge fund holdings tracker built on SEC EDGAR 13F-HR filings. "
    "Tracks 82 institutional investors including Berkshire Hathaway, Pershing Square, "
    "Duquesne Family Office, Baupost Group, and more. "
    "Updated quarterly. 8 quarters of history per fund. "
    "Data is for informational purposes only — not investment advice.",
    "",
]

# Static site pages
lines += [
    "## Site Pages",
    "",
    f"- [Homepage]({BASE_URL}/): Fund list with search, sorted by recently filed",
    f"- [Top Holdings]({BASE_URL}/top-holdings.html): Top 10 and Top 100 stocks by aggregate hedge fund ownership value",
    f"- [Manager Bios]({BASE_URL}/managers.html): 28 hedge fund managers — biography, investment philosophy, notable trades",
    f"- [Consensus Buys & Sells]({BASE_URL}/hedge-fund-activity.html): Most widely bought and sold stocks this quarter",
    f"- [Fund Comparison]({BASE_URL}/portfolio-overlap.html): Compare holdings overlap across up to 5 funds simultaneously",
    f"- [13F Filing Calendar]({BASE_URL}/filing-calendar.html): Latest filed dates and next expected filing dates per fund",
    f"- [FAQ]({BASE_URL}/faq.html): What is a 13F filing, how to interpret hedge fund holdings, glossary",
    f"- [About]({BASE_URL}/about.html): About 13FAI and data methodology",
    f"- [Disclaimer]({BASE_URL}/disclaimer.html): Full legal disclaimer and terms of use",
    "",
]

# Fund pages (all 82)
lines += [
    "## Fund Pages",
    "",
    "Each fund page shows holdings by quarter, period-over-period changes, new positions, exits, and portfolio insights.",
    "",
]
for fund in funds:
    fid   = fund.get("id", "")
    name  = fund.get("name", fid)
    lines.append(f"- [{name}]({BASE_URL}/fund.html?fund={fid})")

lines.append("")

# Manager bio pages (all 28)
lines += [
    "## Manager Bio Pages",
    "",
    "Static pages optimised for manager-name searches. "
    "Each includes biography, investment philosophy, notable trades, and live top-5 holdings.",
    "",
]

# funds_content.json can be keyed by fund_id or be a list — handle both
if isinstance(funds_content, dict):
    bio_entries = funds_content.values()
else:
    bio_entries = funds_content

for m in bio_entries:
    manager = m.get("manager_name", "")
    slug    = m.get("slug", "")
    fund_name = m.get("fund_name", m.get("fund_id", ""))
    if slug and manager:
        lines.append(f"- [{manager}]({BASE_URL}/{slug}.html) — {fund_name}")

lines.append("")

# Stock pages (all tickers in stock_index, skipping BRK/B style slashes)
lines += [
    "## Stock Pages",
    "",
    "Each stock page shows which tracked hedge funds hold the stock, "
    "shares and portfolio weight per fund, quarter-over-quarter changes, and aggregate ownership trends.",
    "",
]

valid_tickers = sorted(
    ticker for ticker in stocks.keys()
    if "/" not in ticker and ticker.strip()
)

for ticker in valid_tickers:
    name = stocks[ticker].get("name", ticker)
    lines.append(
        f"- [{name} ({ticker})]({BASE_URL}/stocks/{ticker}-hedge-fund-ownership.html)"
    )

lines.append("")

# Data notes
lines += [
    "## Data Notes",
    "",
    "- Source: SEC EDGAR 13F-HR filings (public domain), filed quarterly by institutional investors managing >$100M",
    "- Options (PUT/CALL) are displayed but excluded from portfolio weight and share count calculations",
    "- Value reported in USD thousands as filed; multiplier applied for funds that report in different units",
    "- \"Price at Last Filing\" is implied average (portfolio value ÷ shares), not actual trade price",
    "- Filing lag: 13Fs are due 45 days after quarter end, so Q4 data typically appears mid-February",
    "- Disclaimer: for informational purposes only, not investment advice",
    "",
]

# ── Write file ───────────────────────────────────────────────────────────────

output = "\n".join(lines)

with open("llms.txt", "w", encoding="utf-8") as f:
    f.write(output)

ticker_count = len(valid_tickers)
bio_count    = sum(1 for m in bio_entries if m.get("slug"))
fund_count   = len(funds)

print(f"✅ llms.txt written")
print(f"   {fund_count} fund pages")
print(f"   {bio_count} bio pages")
print(f"   {ticker_count} stock pages")
print(f"   Total size: {len(output):,} chars")
