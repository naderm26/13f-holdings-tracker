import os
import json
import glob

with open("funds.json") as f:
    funds = json.load(f)

print("=" * 60)
print("FUND DATA STATUS CHECK")
print("=" * 60)

missing_all = []
missing_recent = []

for fund in funds:
    fund_id = fund["id"]
    name = fund["name"]
    
    xmls = sorted(glob.glob(f"data/{fund_id}_*.xml"))
    csvs = sorted(glob.glob(f"data/{fund_id}_*.csv"))
    
    if not xmls:
        missing_all.append(name)
        print(f"❌ NO DATA:     {name}")
    else:
        # Check if most recent is 2025Q3 or later
        latest = xmls[-1]
        quarter = latest.replace(f"data/{fund_id}_", "").replace(".xml", "")
        if quarter < "2025Q3":
            missing_recent.append((name, quarter))
            print(f"⚠️  STALE ({quarter}): {name}")
        else:
            print(f"✅ OK ({quarter}):   {name}")

print("\n" + "=" * 60)
print(f"Missing data entirely: {len(missing_all)}")
for n in missing_all:
    print(f"  - {n}")

print(f"\nStale data (older than 2025Q3): {len(missing_recent)}")
for n, q in missing_recent:
    print(f"  - {n} (latest: {q})")

print(f"\nTotal funds: {len(funds)}")
print(f"Fully loaded: {len(funds) - len(missing_all) - len(missing_recent)}")
