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
            # Group all rows by CUSIP first, then write once per CUSIP.
            # This prevents a CALL/PUT options row from overwriting the underlying
            # stock position when both share the same CUSIP in the same quarter.
            # Rows without a putcall value (plain stock) take priority; shares and
            # values are summed across all rows for the same CUSIP so nothing is lost.
            cusip_groups = defaultdict(lambda: {
                "company": "",
                "shares": 0,
                "value": 0,
                "putcall_set": set(),
                "has_stock": False,   # True if any row has no putcall (plain equity)
            })

            with open(csv_file, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cusip   = row.get("CUSIP", "").strip()
                    company = row.get("Company", "").strip()
                    shares  = int(row.get("Shares", 0) or 0)
                    value   = int(row.get("Value", 0) or 0) * mult
                    putcall = row.get("PutCall", "").strip()

                    if not cusip or not company:
                        continue

                    g = cusip_groups[cusip]
                    if not g["company"]:
                        g["company"] = company
                    g["shares"] += shares
                    g["value"]  += value
                    if putcall:
                        g["putcall_set"].add(putcall)
                    else:
                        g["has_stock"] = True

            # Write one entry per CUSIP into the index
            for cusip, g in cusip_groups.items():
                company = g["company"]
                shares  = g["shares"]
                value   = g["value"]

                # putcall: only set if ALL rows for this CUSIP are options (no plain equity row).
                # If there's a mix (stock + options on same CUSIP), treat as plain equity.
                if g["has_stock"] or not g["putcall_set"]:
                    putcall = ""
                else:
                    # All rows are options — use the option type (Put or Call)
                    putcall = list(g["putcall_set"])[0] if len(g["putcall_set"]) == 1 else ""

                # Skip zero-share rows
                if shares == 0:
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
                    "shares":  shares,
                    "value":   value,
                    "putcall": putcall
                }

        except Exception as e:
            print(f"Error processing {csv_file}: {e}")

with open("stock_index.json", "w") as f:
    json.dump(stock_index, f)

print(f"Done. Indexed {len(stock_index)} unique stocks across all funds.")
