import json
import csv
import glob
import os
from collections import defaultdict

def fund_id_from_filename(filename):
    base = os.path.basename(filename)
    parts = base.replace(".csv", "").split("_")
    return "_".join(parts[:-1])

def quarter_label(filename):
    base = os.path.basename(filename)
    parts = base.replace(".csv", "").split("_")
    return parts[-1]

with open("funds.json") as f:
    funds = json.load(f)
fund_map = {f["id"]: f for f in funds}
multipliers = {f["id"]: f.get("value_multiplier", 1) for f in funds}

# Load cusip_to_ticker
ticker_map = {}
if os.path.exists("cusip_to_ticker.json"):
    with open("cusip_to_ticker.json") as f:
        ticker_map = json.load(f)

# Find the two most recent global quarters
all_quarters = set()
for csv_file in glob.glob("data/*.csv"):
    all_quarters.add(quarter_label(csv_file))
sorted_quarters = sorted(all_quarters, reverse=True)
latest_q = sorted_quarters[0] if sorted_quarters else None
prev_q   = sorted_quarters[1] if len(sorted_quarters) > 1 else None

if not latest_q or not prev_q:
    print("Not enough quarters to compute activity")
    exit(0)

print(f"Comparing {latest_q} vs {prev_q}")

# Build holdings per fund per quarter
def load_quarter(q):
    holdings = {}  # fund_id -> {cusip: {shares, value, company}}
    for csv_file in glob.glob(f"data/*_{q}.csv"):
        fid  = fund_id_from_filename(csv_file)
        mult = multipliers.get(fid, 1)
        holdings[fid] = {}
        try:
            with open(csv_file, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cusip   = row.get("CUSIP", "").strip()
                    company = row.get("Company", "").strip()
                    shares  = int(row.get("Shares", 0) or 0)
                    value   = int(row.get("Value", 0) or 0) * mult
                    putcall = row.get("PutCall", "").strip().upper()
                    # Exclude options — long equity book only
                    if putcall in ("PUT", "CALL"):
                        continue
                    if cusip and shares > 0:
                        if cusip in holdings[fid]:
                            holdings[fid][cusip]["shares"] += shares
                            holdings[fid][cusip]["value"]  += value
                        else:
                            holdings[fid][cusip] = {"shares": shares, "value": value, "company": company}
        except Exception as e:
            print(f"  Error {csv_file}: {e}")
    return holdings

latest_holdings = load_quarter(latest_q)
prev_holdings   = load_quarter(prev_q)

# Aggregate changes across all funds
# bought: new position or increased shares
# sold: exited or reduced shares
bought = defaultdict(lambda: {"company": "", "ticker": "", "cusip": "", "funds": [], "total_value": 0})
sold   = defaultdict(lambda: {"company": "", "ticker": "", "cusip": "", "funds": [], "total_value_sold": 0})

for fid, holdings in latest_holdings.items():
    fund = fund_map.get(fid)
    if not fund: continue
    prev = prev_holdings.get(fid, {})

    for cusip, data in holdings.items():
        ticker  = ticker_map.get(cusip, "")
        key     = ticker if ticker else cusip
        company = data["company"]
        shares  = data["shares"]
        value   = data["value"]
        prev_shares = prev.get(cusip, {}).get("shares", 0)

        if prev_shares == 0 and shares > 0:
            # New position
            bought[key]["company"]     = company
            bought[key]["ticker"]      = ticker
            bought[key]["cusip"]       = cusip
            bought[key]["total_value"] += value
            bought[key]["funds"].append({"id": fid, "name": fund["name"], "type": "NEW", "value": value})
        elif shares > prev_shares:
            # Increased
            bought[key]["company"]     = company
            bought[key]["ticker"]      = ticker
            bought[key]["cusip"]       = cusip
            bought[key]["total_value"] += value
            pct = ((shares - prev_shares) / prev_shares * 100)
            bought[key]["funds"].append({"id": fid, "name": fund["name"], "type": f"+{pct:.0f}%", "value": value})

    for cusip, prev_data in prev.items():
        ticker  = ticker_map.get(cusip, "")
        key     = ticker if ticker else cusip
        company = prev_data["company"]
        prev_shares = prev_data["shares"]
        curr_shares = holdings.get(cusip, {}).get("shares", 0)
        prev_value  = prev_data["value"]

        if curr_shares == 0 and prev_shares > 0:
            # Exited
            sold[key]["company"]          = company
            sold[key]["ticker"]           = ticker
            sold[key]["cusip"]            = cusip
            sold[key]["total_value_sold"] += prev_value
            sold[key]["funds"].append({"id": fid, "name": fund["name"], "type": "EXITED", "value": prev_value})
        elif curr_shares < prev_shares:
            # Reduced
            sold[key]["company"]          = company
            sold[key]["ticker"]           = ticker
            sold[key]["cusip"]            = cusip
            sold[key]["total_value_sold"] += prev_value
            pct = ((prev_shares - curr_shares) / prev_shares * 100)
            sold[key]["funds"].append({"id": fid, "name": fund["name"], "type": f"-{pct:.0f}%", "value": prev_value})

# Sort by number of funds then total value
bought_sorted = sorted(bought.items(), key=lambda x: (len(x[1]["funds"]), x[1]["total_value"]), reverse=True)
sold_sorted   = sorted(sold.items(),   key=lambda x: (len(x[1]["funds"]), x[1]["total_value_sold"]), reverse=True)

activity = {
    "latest_q": latest_q,
    "prev_q":   prev_q,
    "bought":   [{"key": k, **v} for k, v in bought_sorted[:50]],
    "sold":     [{"key": k, **v} for k, v in sold_sorted[:50]]
}

with open("activity.json", "w") as f:
    json.dump(activity, f, indent=2)

print(f"Done. {len(bought_sorted)} stocks bought, {len(sold_sorted)} stocks sold.")
print(f"Top bought: {bought_sorted[0][1]['company']} by {len(bought_sorted[0][1]['funds'])} funds")
print(f"Top sold:   {sold_sorted[0][1]['company']} by {len(sold_sorted[0][1]['funds'])} funds")
