"""
migrate_to_fund_json.py
-----------------------
One-time script to convert existing CSV + metadata JSON files in data/
into the new per-fund JSON format (data/{fund_id}.json).

Run once after deploying the new fetch_data.py:
    python migrate_to_fund_json.py

Safe to re-run — skips quarters already present in the per-fund JSON.
Does NOT delete any existing CSV files (that's handled by fetch_data.py going forward).
"""

import json
import csv
import os
import glob


def load_csv(csv_file):
    holdings = []
    with open(csv_file, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            shares = row.get("Shares", "0").strip()
            value  = row.get("Value",  "0").strip()
            holdings.append({
                "company":    row.get("Company",    "").strip(),
                "cusip":      row.get("CUSIP",      "").strip(),
                "shares":     int(shares) if shares.isdigit() else 0,
                "value":      int(value)  if value.isdigit()  else 0,
                "discretion": row.get("Discretion", "").strip(),
                "putcall":    row.get("PutCall",    "").strip()
            })
    return holdings


def quarter_from_filename(filename):
    # data/berkshire_2025Q4.csv -> 2025Q4
    base = os.path.basename(filename)
    return base.replace(".csv", "").split("_")[-1]


def fund_id_from_filename(filename):
    base = os.path.basename(filename)
    parts = base.replace(".csv", "").split("_")
    return "_".join(parts[:-1])


with open("funds.json") as f:
    funds = json.load(f)

fund_map = {f["id"]: f for f in funds}

migrated_funds  = 0
migrated_quarters = 0
skipped_quarters  = 0

for fund in funds:
    fund_id   = fund["id"]
    fund_name = fund["name"]

    # Load existing per-fund JSON if present
    fund_json_path = f"data/{fund_id}.json"
    if os.path.exists(fund_json_path):
        with open(fund_json_path) as f:
            fund_data = json.load(f)
    else:
        fund_data = {"quarters": {}}

    # Find all CSVs for this fund, sorted newest first
    csvs = sorted(glob.glob(f"data/{fund_id}_*.csv"), reverse=True)
    if not csvs:
        print(f"  {fund_id}: no CSVs found, skipping")
        continue

    changed = False

    for csv_file in csvs[:8]:  # only process 8 most recent
        label = quarter_from_filename(csv_file)

        if label in fund_data.get("quarters", {}):
            print(f"  {fund_id} {label}: already in fund JSON, skipping")
            skipped_quarters += 1
            continue

        # Load holdings from CSV
        holdings = load_csv(csv_file)

        # Load metadata from companion JSON if available
        meta_file = csv_file.replace(".csv", ".json")
        filed  = ""
        period = ""
        if os.path.exists(meta_file):
            with open(meta_file) as f:
                meta = json.load(f)
            filed  = meta.get("filed",  "")
            period = meta.get("period", "")

        if "quarters" not in fund_data:
            fund_data["quarters"] = {}

        fund_data["quarters"][label] = {
            "filed":    filed,
            "period":   period,
            "holdings": holdings
        }
        changed = True
        migrated_quarters += 1
        print(f"  {fund_id} {label}: migrated {len(holdings)} holdings")

    # Keep only 8 most recent quarters
    if "quarters" in fund_data:
        all_quarters = sorted(fund_data["quarters"].keys(), reverse=True)
        for old_q in all_quarters[8:]:
            del fund_data["quarters"][old_q]
            print(f"  {fund_id} {old_q}: pruned from JSON (beyond 8 quarters)")
            changed = True

    if changed:
        fund_data["id"]   = fund_id
        fund_data["name"] = fund_name
        with open(fund_json_path, "w") as f:
            json.dump(fund_data, f)
        print(f"  {fund_id}: saved {fund_json_path}")
        migrated_funds += 1

print(f"\nDone. {migrated_funds} funds updated, {migrated_quarters} quarters migrated, {skipped_quarters} already present.")
