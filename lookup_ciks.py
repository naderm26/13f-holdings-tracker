import urllib.request
import urllib.parse
import json
import time
import re

HEADERS = {"User-Agent": "nadermassoudi@aol.com"}

FUNDS_TO_LOOKUP = [
    ("meridian_contrarian", "Meridian Contrarian Fund", "Meridian Contrarian"),
    ("longleaf", "Mason Hawkins - Longleaf Partners", "Southeastern Asset Management"),
    ("ariel_focus", "Charles Bobrinskoy - Ariel Focus Fund", "Ariel Investments"),
    ("ariel_appreciation", "John Rogers - Ariel Appreciation Fund", "Ariel Investments"),
    ("oakmark_select", "Bill Nygren - Oakmark Select Fund", "Harris Associates"),
    ("sequoia", "Ruane Cunniff - Sequoia Fund", "Ruane Cunniff"),
    ("viking", "Viking Global Investors", "Viking Global Investors"),
    ("trian", "Nelson Peltz - Trian Fund Management", "Trian Fund Management"),
    ("third_point", "Daniel Loeb - Third Point", "Third Point LLC"),
    ("icahn", "Carl Icahn - Icahn Capital Management", "Icahn Capital Management"),
    ("greenlight", "David Einhorn - Greenlight Capital", "Greenlight Capital"),
    ("valueact", "ValueAct Capital", "ValueAct Capital"),
    ("gates", "Bill & Melinda Gates Foundation Trust", "Bill & Melinda Gates Foundation Trust"),
    ("semper_augustus", "Christopher Bloomstran - Semper Augustus", "Semper Augustus"),
    ("lone_pine", "Stephen Mandel - Lone Pine Capital", "Lone Pine Capital"),
    ("fairholme", "Bruce Berkowitz - Fairholme Capital", "Fairholme Capital"),
    ("punch_card", "Norbert Lou - Punch Card Management", "Punch Card Management"),
    ("durable_capital", "Henry Ellenbogen - Durable Capital Partners", "Durable Capital Partners"),
    ("wedgewood", "David Rolfe - Wedgewood Partners", "Wedgewood Partners"),
    ("himalaya", "Li Lu - Himalaya Capital Management", "Himalaya Capital Management"),
    ("valley_forge", "Valley Forge Capital Management", "Valley Forge Capital Management"),
    ("atlantic_inv", "Alex Roepers - Atlantic Investment Management", "Atlantic Investment Management"),
    ("berkshire", "Warren Buffett - Berkshire Hathaway", "Berkshire Hathaway"),
    ("brave_warrior", "Glenn Greenberg - Brave Warrior Advisors", "Brave Warrior Advisors"),
    ("appaloosa", "David Tepper - Appaloosa Management", "Appaloosa Management"),
    ("oakcliff", "Bryan Lawrence - Oakcliff Capital", "Oakcliff Capital"),
    ("engaged", "Glenn Welling - Engaged Capital", "Engaged Capital"),
    ("tiger_global", "Chase Coleman - Tiger Global Management", "Tiger Global Management"),
    ("oaktree", "Howard Marks - Oaktree Capital Management", "Oaktree Capital Management"),
    ("ako", "AKO Capital", "AKO Capital"),
    ("cooperman", "Leon Cooperman", "Omega Advisors"),
    ("cas", "Clifford Sosin - CAS Investment Partners", "CAS Investment Partners"),
    ("tci", "Chris Hohn - TCI Fund Management", "TCI Fund Management"),
    ("hh_intl", "Duan Yongping - H&H International Investment", "H&H International Investment"),
    ("miller_value", "Bill Miller - Miller Value Partners", "Miller Value Partners"),
    ("dorsey", "Pat Dorsey - Dorsey Asset Management", "Dorsey Asset Management"),
    ("greenlea_lane", "Josh Tarasoff - Greenlea Lane Capital", "Greenlea Lane Capital"),
    ("fundsmith", "Terry Smith - Fundsmith", "Fundsmith"),
    ("fairfax", "Prem Watsa - Fairfax Financial Holdings", "Fairfax Financial Holdings"),
    ("patient_capital", "Samantha McLemore - Patient Capital Management", "Patient Capital Management"),
    ("maverick", "Lee Ainslie - Maverick Capital", "Maverick Capital"),
    ("altarock", "AltaRock Partners", "AltaRock Partners"),
    ("akre", "Chuck Akre - Akre Capital Management", "Akre Capital Management"),
    ("baupost", "Seth Klarman - Baupost Group", "Baupost Group"),
    ("abrams", "David Abrams - Abrams Capital Management", "Abrams Capital Management"),
    ("chou", "Francis Chou - Chou Associates", "Chou Associates"),
    ("giverny", "Francois Rochon - Giverny Capital", "Giverny Capital"),
    ("causeway", "Sarah Ketterer - Causeway Capital Management", "Causeway Capital Management"),
    ("shawspring", "Dennis Hong - ShawSpring Partners", "ShawSpring Partners"),
    ("pabrai", "Mohnish Pabrai - Pabrai Investments", "Pabrai Investments"),
    ("triple_frond", "Triple Frond Partners", "Triple Frond Partners"),
    ("conifer", "Greg Alexander - Conifer Management", "Conifer Management"),
    ("third_avenue", "Third Avenue Management", "Third Avenue Management"),
    ("gardner_russo", "Thomas Russo - Gardner Russo & Quinn", "Gardner Russo"),
    ("kahn_brothers", "Kahn Brothers Group", "Kahn Brothers"),
    ("weitz", "Wallace Weitz - Weitz Investment Management", "Weitz Investment Management"),
    ("polen", "Polen Capital Management", "Polen Capital Management"),
    ("makaira", "Tom Bancroft - Makaira Partners", "Makaira Partners"),
    ("lindsell_train", "Lindsell Train", "Lindsell Train"),
    ("jensen", "Jensen Investment Management", "Jensen Investment Management"),
    ("cantillon", "William Von Mueffling - Cantillon Capital Management", "Cantillon Capital Management"),
    ("egerton", "John Armitage - Egerton Capital", "Egerton Capital"),
    ("sound_shore", "Harry Burn - Sound Shore", "Sound Shore"),
    ("markel", "Thomas Gayner - Markel Group", "Markel Corporation"),
    ("first_eagle", "First Eagle Investment Management", "First Eagle Investment Management"),
    ("yacktman", "Yacktman Asset Management", "Yacktman Asset Management"),
    ("olstein", "Robert Olstein - Olstein Capital Management", "Olstein Capital Management"),
    ("davis", "Christopher Davis - Davis Advisors", "Davis Selected Advisers"),
    ("rv_capital", "Robert Vinall - RV Capital GmbH", "RV Capital"),
    ("torray", "Torray Funds", "Torray LLC"),
    ("tweedy_browne", "Tweedy Browne Co.", "Tweedy Browne"),
    ("mairs_power", "Mairs & Power Growth Fund", "Mairs & Power"),
    ("dodge_cox", "Dodge & Cox", "Dodge & Cox"),
    ("matrix", "David Katz - Matrix Asset Advisors", "Matrix Asset Advisors"),
    ("pzena", "Richard Pzena - Hancock Classic Value", "Pzena Investment Management"),
    ("aquamarine", "Guy Spier - Aquamarine Capital", "Aquamarine Capital"),
    ("fpa_queens", "FPA Queens Road Small Cap Value Fund", "First Pacific Advisors"),
    ("fpa_crescent", "Steven Romick - FPA Crescent Fund", "First Pacific Advisors"),
    ("hillman", "Hillman Value Fund", "Hillman Capital"),
    ("greenhaven", "Greenhaven Associates", "Greenhaven Associates"),
    ("scion", "Michael Burry - Scion Asset Management", "Scion Asset Management"),
]

def search_cik(search_term):
    query = urllib.parse.quote(search_term)
    url = f"https://efts.sec.gov/LATEST/search-index?q=%22{query}%22&forms=13F-HR&dateRange=custom&startdt=2024-01-01"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        hits = data.get("hits", {}).get("hits", [])
        if hits:
            src = hits[0].get("_source", {})
            display = src.get("display_names", [""])[0]
            m = re.search(r'CIK (\d+)', display)
            if m:
                return m.group(1).lstrip("0"), display
    except Exception as e:
        pass
    return None, None

results = []
for fund_id, display_name, search_term in FUNDS_TO_LOOKUP:
    cik, entity = search_cik(search_term)
    status = f"FOUND: {cik} | {entity}" if cik else "NOT FOUND"
    print(f"{display_name}: {status}")
    results.append({"id": fund_id, "name": display_name, "cik": cik, "entity": entity})
    time.sleep(0.4)

with open("cik_lookup_results.json", "w") as f:
    json.dump(results, f, indent=2)

found = sum(1 for r in results if r["cik"])
print(f"\nDone. Found {found} / {len(results)}")
