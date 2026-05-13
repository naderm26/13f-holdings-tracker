"""
fix_prn_positions.py
One-time cleanup: removes PRN (principal/debt) positions from all per-fund JSONs.
PRN positions have sshPrnamtType = "PRN" in the original XML — they represent
face value of bonds/notes not share counts, and distort portfolio calculations.

Since we don't store sshPrnamtType in the JSON, we identify PRN positions by
their CUSIP format: PRN CUSIPs typically end in letters (e.g. 594972AS0)
and have unrealistically large share counts relative to their value.

Strategy Inc (594972AS0) is the known case: 20,000,000,000 "shares" = $20B face value.

Run this once, then deploy the updated fetch_data.py which skips PRN going forward.
"""

import json
import os
import glob

PRN_CUSIPS = {
    "594972AS0",   # Strategy Inc convertible notes
    # Add others here if discovered
}

# Also catch by heuristic: shares > 1,000,000,000 and value < shares (i.e. price < $1)
# This catches large principal positions regardless of CUSIP
def is_likely_prn(holding):
    shares = holding.get("shares", 0)
    value  = holding.get("value", 0)
    cusip  = holding.get("cusip", "")
    if cusip in PRN_CUSIPS:
        return True
    # Heuristic: more than 1B "shares" at less than $1 implied price
    if shares > 1_000_000_000 and value > 0 and (value / shares) < 1:
        return True
    return False

data_dir = "data"
files = glob.glob(f"{data_dir}/*.json")
total_removed = 0
funds_updated = 0

for path in sorted(files):
    if path.endswith("_monitor_date.txt"):
        continue
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        continue

    if "quarters" not in data:
        continue

    changed = False
    for label, qdata in data["quarters"].items():
        holdings = qdata.get("holdings", [])
        filtered = [h for h in holdings if not is_likely_prn(h)]
        removed  = len(holdings) - len(filtered)
        if removed > 0:
            print(f"  {os.path.basename(path)} {label}: removed {removed} PRN position(s)")
            for h in holdings:
                if is_likely_prn(h):
                    print(f"    - {h['company']} ({h['cusip']}) shares={h['shares']:,} value={h['value']:,}")
            qdata["holdings"] = filtered
            total_removed += removed
            changed = True

    if changed:
        with open(path, "w") as f:
            json.dump(data, f)
        funds_updated += 1

print(f"\nDone. Removed {total_removed} PRN positions across {funds_updated} fund files.")
print("Now run: generate_stock_index workflow to rebuild stock_index.json")
