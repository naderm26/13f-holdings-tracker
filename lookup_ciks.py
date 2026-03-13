import urllib.request
import json
import time

HEADERS = {"User-Agent": "nadermassoudi@aol.com"}

# Fund names to search — mapped to search terms that work best on EDGAR
FUNDS_TO_LOOKUP = [
    "Meridian Contrarian Fund",
    "Longleaf Partners",
    "Ariel Focus Fund",
    "Ariel Appreciation Fund",
    "Oakmark Select Fund",
    "Sequoia Fund",
    "Viking Global Investors",
    "Trian Fund Management",
    "Third Point",
    "Icahn Capital Management",
    "Greenlight Capital",
    "ValueAct Capital",
    "Bill & Melinda Gates Foundation Trust",
    "Semper Augustus",
    "Lone Pine Capital",
    "Fairholme Capital",
    "Punch Card Management",
    "Durable Capital Partners",
    "Wedgewood Partners",
    "Himalaya Capital Management",
    "Valley Forge Capital Management",
    "Atlantic Investment Management",
    "Berkshire Hathaway",
    "Brave Warrior Advisors",
    "Appaloosa Management",
    "Oakcliff Capital",
    "Engaged Capital",
    "Tiger Global Management",
    "Oaktree Capital Management",
    "AKO Capital",
    "Leon Cooperman",
    "CAS Investment Partners",
    "TCI Fund Management",
    "H&H International Investment",
    "Miller Value Partners",
    "Dorsey Asset Management",
    "Greenlea Lane Capital",
    "Fundsmith",
    "Fairfax Financial Holdings",
    "Patient Capital Management",
    "Maverick Capital",
    "AltaRock Partners",
    "Akre Capital Management",
    "Baupost Group",
    "Abrams Capital Management",
    "Chou Associates",
    "Giverny Capital",
    "Causeway Capital Management",
    "ShawSpring Partners",
    "Pabrai Investments",
    "Triple Frond Partners",
    "Conifer Management",
    "Third Avenue Management",
    "Gardner Russo",
    "Kahn Brothers",
    "Weitz Investment Management",
    "Polen Capital Management",
    "Makaira Partners",
    "Lindsell Train",
    "Jensen Investment Management",
    "Cantillon Capital Management",
    "Egerton Capital",
    "Sound Shore",
    "Markel Group",
    "First Eagle Investment Management",
    "Yacktman Asset Management",
    "Olstein Capital Management",
    "Davis Advisors",
    "RV Capital",
    "Torray",
    "Tweedy Browne",
    "Mairs & Power",
    "Dodge & Cox",
    "Matrix Asset Advisors",
    "Pzena Investment Management",
    "Aquamarine Capital",
    "FPA Crescent Fund",
    "Hillman Capital",
    "Greenhaven Associates",
    "Scion Asset Management",
]

def search_edgar(name):
    query = urllib.parse.quote(name)
    url = f"https://efts.sec.gov/LATEST/search-index?q=%22{query}%22&forms=13F-HR&dateRange=custom&startdt=2024-01-01"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        data = json.loads(urllib.request.urlopen(req).read())
        hits = data.get("hits", {}).get("hits", [])
        if hits:
            cik = hits[0].get("_source", {}).get("entity_id", "")
            entity = hits[0].get("_source", {}).get("display_names", [""])[0]
            return cik, entity
    except:
        pass
    return None, None

import urllib.parse

results = []
for name in FUNDS_TO_LOOKUP:
    cik, entity = search_edgar(name)
    status = f"CIK: {cik} | Entity: {entity}" if cik else "NOT FOUND"
    print(f"{name}: {status}")
    results.append({"search": name, "cik": cik, "entity": entity})
    time.sleep(0.3)  # be polite to EDGAR

with open("cik_lookup_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nSaved to cik_lookup_results.json")
