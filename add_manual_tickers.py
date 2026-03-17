import json
import os

# Manual CUSIP -> ticker mappings for foreign-listed stocks
# that OpenFIGI misses or maps incorrectly
MANUAL_MAPPINGS = {
    # Chubb Limited (NYSE: CB) - Swiss company, CUSIP changed after ACE merger
    "H1467J104": "CB",
    
    # AON PLC (NYSE: AON) - Irish company, two CUSIPs due to redomicile
    "G0403H108": "AON",
    "G0408V102": "AON",
    
    # Allegion PLC (NYSE: ALLE) - Irish company
    "G0176J109": "ALLE",
    
    # Liberty Latin America (NASDAQ: LILA / LILAK) - Bermuda company
    "G54790109": "LILA",   # Class A
    "G54790208": "LILAK",  # Class C
    "G9001E128": "LILAK",  # Class C (alternate CUSIP)
    
    # Liberty Global (NASDAQ: LBTYA / LBTYK)
    "G5480U104": "LBTYA",  # Class A
    "G5480U203": "LBTYK",  # Class C
    
    # CRH PLC (NYSE: CRH) - Irish building materials
    "G25508105": "CRH",
    "G25715140": "CRH",
    
    # Flutter Entertainment (NYSE: FLUT) - Irish gambling company
    "G35234107": "FLUT",
    
    # ASML Holding (NASDAQ: ASML) - Dutch semiconductor equipment
    "N07059210": "ASML",
    "N0706C100": "ASML",
    
    # Willis Towers Watson (NASDAQ: WTW) - Irish insurance broker
    "G96629103": "WTW",
    
    # Herbalife (NYSE: HLF)
    "G4412G101": "HLF",
    
    # Deutsche Bank (NYSE: DB) - German bank
    "D18190898": "DB",
    
    # NewAmsterdam Pharma (NASDAQ: NAMS)
    "N6388T108": "NAMS",
    
    # BBB Foods (NYSE: TBBB)
    "G07817104": "TBBB",
    
    # Wave Life Sciences (NASDAQ: WVE)
    "Y9516M105": "WVE",
}

# Load existing mappings
existing = {}
if os.path.exists("cusip_to_ticker.json"):
    with open("cusip_to_ticker.json") as f:
        existing = json.load(f)
    print(f"Loaded {len(existing)} existing mappings")

# Add manual mappings
added = 0
for cusip, ticker in MANUAL_MAPPINGS.items():
    if cusip not in existing:
        existing[cusip] = ticker
        print(f"  Added: {cusip} -> {ticker}")
        added += 1
    else:
        print(f"  Already mapped: {cusip} -> {existing[cusip]} (skipped)")

with open("cusip_to_ticker.json", "w") as f:
    json.dump(existing, f, indent=2)

print(f"\nDone. Added {added} manual mappings. Total: {len(existing)}")
