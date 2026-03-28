"""
aggregate_holdings.py
─────────────────────
Reads all per-fund JSONs (data/{fund_id}.json) and the master funds.json,
then writes a single CSV containing every holding across all funds and all
available quarters (up to 8 per fund).

Output: aggregate_holdings.csv

Columns:
  fund_id         – internal fund identifier (e.g. "berkshire")
  fund_name       – display name (e.g. "Berkshire Hathaway (Warren Buffett)")
  quarter         – quarter label (e.g. "2025Q4")
  filed_date      – SEC filing date for that quarter (e.g. "2026-02-17")
  period_date     – quarter end date (e.g. "2025-12-31")
  company         – issuer name from 13F
  cusip           – CUSIP identifier
  ticker          – ticker symbol (from cusip_to_ticker.json, if mapped)
  shares          – number of shares reported
  value_raw       – value as reported in the filing (in $thousands)
  value_adjusted  – value after applying value_multiplier ($thousands)
  value_usd       – value_adjusted converted to full dollars
  putcall         – PUT / CALL / blank for regular equity positions
"""

import json
import csv
import os

# ── Paths ──────────────────────────────────────────────────────────────────
REPO_ROOT  = os.path.dirname(os.path.abspath(__file__))
FUNDS_JSON = os.path.join(REPO_ROOT, "funds.json")
DATA_DIR   = os.path.join(REPO_ROOT, "data")
CUSIP_MAP  = os.path.join(REPO_ROOT, "cusip_to_ticker.json")
OUTPUT_CSV = os.path.join(REPO_ROOT, "aggregate_holdings.csv")

# ── Load funds config ──────────────────────────────────────────────────────
with open(FUNDS_JSON, "r") as f:
    funds = json.load(f)

# ── Load CUSIP → ticker map ────────────────────────────────────────────────
ticker_map = {}
if os.path.exists(CUSIP_MAP):
    with open(CUSIP_MAP, "r") as f:
        ticker_map = json.load(f)
    print(f"  Loaded {len(ticker_map):,} CUSIP->ticker mappings")
else:
    print("  Warning: cusip_to_ticker.json not found -- ticker column will be empty")

# ── Write CSV ──────────────────────────────────────────────────────────────
fieldnames = [
    "fund_id", "fund_name", "quarter", "filed_date", "period_date",
    "company", "cusip", "ticker",
    "shares", "value_raw", "value_adjusted", "value_usd",
    "putcall"
]

total_rows    = 0
funds_written = 0
funds_missing = 0

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

    for fund in funds:
        fund_id   = fund["id"]
        fund_name = fund.get("name", fund_id)
        mult      = fund.get("value_multiplier", 1)

        json_path = os.path.join(DATA_DIR, f"{fund_id}.json")
        if not os.path.exists(json_path):
            print(f"  MISSING  {fund_id} -- no data file found")
            funds_missing += 1
            continue

        with open(json_path, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"  ERROR    {fund_id} -- JSON parse error: {e}")
                funds_missing += 1
                continue

        quarters = data.get("quarters", {})
        if not quarters:
            print(f"  EMPTY    {fund_id} -- no quarters in JSON")
            funds_missing += 1
            continue

        fund_rows = 0
        for quarter_label, qdata in sorted(quarters.items()):
            filed_date  = qdata.get("filed",  "")
            period_date = qdata.get("period", "")
            holdings    = qdata.get("holdings", [])

            for h in holdings:
                shares    = h.get("shares", 0)
                value_raw = h.get("value",  0)
                cusip     = h.get("cusip",  "").strip()
                company   = h.get("company","").strip()
                putcall   = h.get("putcall","").strip()

                # Skip zero-share rows (same filter as frontend)
                if shares <= 0:
                    continue

                value_adj = value_raw * mult   # $thousands, multiplier applied
                value_usd = value_adj * 1000   # full dollars

                ticker = ticker_map.get(cusip, "")

                writer.writerow({
                    "fund_id":        fund_id,
                    "fund_name":      fund_name,
                    "quarter":        quarter_label,
                    "filed_date":     filed_date,
                    "period_date":    period_date,
                    "company":        company,
                    "cusip":          cusip,
                    "ticker":         ticker,
                    "shares":         shares,
                    "value_raw":      value_raw,
                    "value_adjusted": value_adj,
                    "value_usd":      value_usd,
                    "putcall":        putcall,
                })
                fund_rows += 1

        print(f"  OK       {fund_id} -- {len(quarters)} quarters, {fund_rows:,} rows")
        total_rows    += fund_rows
        funds_written += 1

print()
print(f"Done.")
print(f"  Funds written : {funds_written}")
print(f"  Funds missing : {funds_missing}")
print(f"  Total rows    : {total_rows:,}")
print(f"  Output        : {OUTPUT_CSV}")
