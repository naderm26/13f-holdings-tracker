import json
import os
from collections import defaultdict

# Load funds.json

with open(“funds.json”) as f:
funds = json.load(f)

fund_map = {f[“id”]: f for f in funds}

# Load cusip_to_ticker.json

ticker_map = {}
if os.path.exists(“cusip_to_ticker.json”):
with open(“cusip_to_ticker.json”) as f:
ticker_map = json.load(f)

stock_index = {}
fund_totals = defaultdict(dict)
fund_latest_q = {}  # fid -> most recent quarter label

for fund in funds:
fund_id   = fund[“id”]
mult      = fund.get(“value_multiplier”, 1)

```
fund_json_path = f"data/{fund_id}.json"
if not os.path.exists(fund_json_path):
    print(f"  Skipping {fund_id} — no fund JSON found")
    continue

with open(fund_json_path) as f:
    fund_data = json.load(f)

quarters = fund_data.get("quarters", {})
recent_quarters = sorted(quarters.keys(), reverse=True)[:8]
if recent_quarters:
    fund_latest_q[fund_id] = recent_quarters[0]

for ql in recent_quarters:
    holdings = quarters[ql].get("holdings", [])

    cusip_groups = defaultdict(lambda: {
        "company": "", "shares": 0, "value": 0,
        "putcall_set": set(), "has_stock": False,
    })

    for row in holdings:
        cusip   = row.get("cusip",   "").strip()
        company = row.get("company", "").strip()
        shares  = row.get("shares",  0)
        value   = row.get("value",   0) * mult
        putcall = row.get("putcall", "").strip()

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

        if not putcall:
            fund_totals[fund_id][ql] = fund_totals[fund_id].get(ql, 0) + value

    for cusip, g in cusip_groups.items():
        if g["shares"] == 0:
            continue

        if g["has_stock"] or not g["putcall_set"]:
            putcall = ""
        else:
            putcall = list(g["putcall_set"])[0] if len(g["putcall_set"]) == 1 else ""

        ticker = ticker_map.get(cusip, "")
        key    = ticker if ticker else cusip

        if key not in stock_index:
            stock_index[key] = {
                "name":   g["company"],
                "cusip":  cusip,
                "ticker": ticker,
                "funds":  {}
            }

        if fund_id not in stock_index[key]["funds"]:
            stock_index[key]["funds"][fund_id] = {"quarters": {}}

        stock_index[key]["funds"][fund_id]["quarters"][ql] = {
            "shares":  g["shares"],
            "value":   g["value"],
            "putcall": putcall
        }
```

with open(“stock_index.json”, “w”) as f:
json.dump({“stocks”: stock_index, “fund_totals”: dict(fund_totals), “fund_latest_q”: fund_latest_q}, f)

print(f”Done. Indexed {len(stock_index)} unique stocks across all funds.”)