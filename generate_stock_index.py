import json
import csv
import glob
import os
from collections import defaultdict

def quarter_label(filename):
    # data/berkshire_2025Q4.csv -> 2025Q4
    base = os.path.basename(filename)
    parts = base.replace(".csv", "").split("_")
    return parts[-1]

def fund_id_from_filename(filename):
    base = os.path.basename(filename)
    # Remove the quarter part e.g. berkshire_2025Q4.csv -> berkshire
    parts = base.replace(".csv", "").split("_")
    return "_".join(parts[:-1])

# Load funds.json for name/multiplier lookup
with open("funds.json") as f:
    funds = json.load(f)

fund_map = {f["id"]: f for f in funds}

# Load cusip_to_ticker.json
ticker_map = {}
if os.path.exists("cusip_to_ticker.json"):
    with open("cusip_to_ticker.json") as f:
        ticker_map = json.load(f)

# stock_index structure:
# { "AAPL": { "name": "APPLE INC", "cusip": "037833100", "funds": {
#     "berkshire": { "quarters": { "2025Q4": { "shares": 900000000, "value": 166000000000 }, ... } }
# }}}

stock_index = {}

# Process all CSVs — only most recent 8 quarters per fund
fund_quarters = defaultdict(list)
for csv_file in sorted(glob.glob("data/*.csv")):
    fid = fund_id_from_filename(csv_file)
    ql  = quarter_label(csv_file)
    fund_quarters[fid].append((ql, csv_file))

# Keep only 8 most recent per fund
for fid in fund_quarters:
    fund_quarters[fid] = sorted(fund_quarters[fid], reverse=True)[:8]

for fid, quarter_files in fund_quarters.items():
    fund = fund_map.get(fid)
    if not fund:
        continue
    mult = fund.get("value_multiplier", 1)

    for ql, csv_file in quarter_files:
        try:
            with open(csv_file, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cusip   = row.get("CUSIP", "").strip()
                    company = row.get("Company", "").strip()
                    shares  = int(row.get("Shares", 0) or 0)
                    value   = int(row.get("Value", 0) or 0) * mult

                    if not cusip or not company:
                        continue

                    ticker = ticker_map.get(cusip, "")
                    key    = ticker if ticker else cusip

                    if key not in stock_index:
                        stock_index[key] = {
                            "name":   company,
                            "cusip":  cusip,
                            "ticker": ticker,
                            "funds":  {}
                        }

                    if fid not in stock_index[key]["funds"]:
                        stock_index[key]["funds"][fid] = {"quarters": {}}

                    stock_index[key]["funds"][fid]["quarters"][ql] = {
                        "shares": shares,
                        "value":  value
                    }
        except Exception as e:
            print(f"Error processing {csv_file}: {e}")

with open("stock_index.json", "w") as f:
    json.dump(stock_index, f)

print(f"Done. Indexed {len(stock_index)} unique stocks across all funds.")
