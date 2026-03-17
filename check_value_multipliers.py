import csv
import glob
import json
import os

with open("funds.json") as f:
    funds = json.load(f)
fund_map = {f["id"]: f for f in funds}

print(f"{'Fund':<50} {'Raw Total Value':>20} {'Multiplier':>12} {'Adj Total Value':>20}")
print("-" * 105)

for fund in funds:
    fid  = fund["id"]
    mult = fund.get("value_multiplier", 1)

    # Find most recent CSV
    csvs = sorted(glob.glob(f"data/{fid}_*.csv"), reverse=True)
    if not csvs:
        continue

    total = 0
    try:
        with open(csvs[0], newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += int(row.get("Value", 0) or 0)
    except Exception:
        continue

    adj_total = total * mult
    raw_str   = f"${total:,.0f}"
    adj_str   = f"${adj_total:,.0f}"

    # Flag if adjusted total seems too low (under $50M) or suspiciously round
    flag = ""
    if adj_total > 0 and adj_total < 50_000_000:
        flag = "⚠️  POSSIBLY UNDERSTATED"
    elif adj_total > 0 and adj_total < 500_000_000 and mult == 1:
        flag = "❓ CHECK — under $500M"

    print(f"{fund['name']:<50} {raw_str:>20} {str(mult):>12} {adj_str:>20}  {flag}")

