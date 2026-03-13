import urllib.request
import urllib.error
import json
import time
import re
import xml.etree.ElementTree as ET

HEADERS = {"User-Agent": "nadermassoudi@aol.com"}

def fetch_url(url, retries=3):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 15 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif e.code == 404:
                return None
            else:
                time.sleep(3)
        except Exception:
            time.sleep(3)
    return None

def get_all_13f_filers():
    """Get all 13F-HR filers from the most recent quarter via EFTS."""
    print("Fetching all 13F-HR filers from EDGAR...")
    filers = {}
    from_idx = 0
    page_size = 100

    while True:
        url = (
            f"https://efts.sec.gov/LATEST/search-index?"
            f"q=%2213F-HR%22&forms=13F-HR"
            f"&dateRange=custom&startdt=2025-10-01&enddt=2026-03-31"
            f"&from={from_idx}&hits.hits._source=period_of_report,display_names,file_num,entity_id"
        )
        data = fetch_url(url)
        if not data:
            break

        result = json.loads(data)
        hits = result.get("hits", {}).get("hits", [])
        if not hits:
            break

        for hit in hits:
            src = hit.get("_source", {})
            display = src.get("display_names", [""])[0]
            m = re.search(r'CIK (\d+)', display)
            if m:
                cik = m.group(1).lstrip("0")
                name = re.sub(r'\s*\(CIK.*\)', '', display).strip()
                # Only add once per CIK (most recent filing wins)
                if cik not in filers:
                    filers[cik] = name

        print(f"  Fetched {from_idx + len(hits)} filers so far...")
        from_idx += page_size

        if from_idx >= result.get("hits", {}).get("total", {}).get("value", 0):
            break

        time.sleep(0.3)

    print(f"Total filers found: {len(filers)}")
    return filers

def get_aum_from_submission(cik):
    """Fetch AUM from the most recent 13F filing's cover page XML."""
    padded = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{padded}.json"
    data = fetch_url(url)
    if not data:
        return None

    try:
        subs = json.loads(data)
        filings = subs["filings"]["recent"]

        # Find most recent 13F-HR
        accession = None
        for i, form in enumerate(filings["form"]):
            if form == "13F-HR":
                accession = filings["accessionNumber"][i].replace("-", "")
                break

        if not accession:
            return None

        cik_stripped = str(int(cik))

        # Fetch the index to find the primary doc
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/index.json"
        idx_data = fetch_url(index_url)
        if not idx_data:
            return None

        idx = json.loads(idx_data)
        primary_doc = None
        for item in idx.get("directory", {}).get("item", []):
            name = item.get("name", "").lower()
            if name == "primary_doc.xml" or (name.endswith(".xml") and "primary" in name):
                primary_doc = item["name"]
                break
        # fallback
        if not primary_doc:
            for item in idx.get("directory", {}).get("item", []):
                name = item.get("name", "").lower()
                if name.endswith(".xml") and "infotable" not in name and "13f" not in name:
                    primary_doc = item["name"]
                    break

        if not primary_doc:
            return None

        cover_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{primary_doc}"
        xml_data = fetch_url(cover_url)
        if not xml_data:
            return None

        # Parse tableValueTotal from cover page
        text = xml_data.decode("utf-8", errors="ignore")
        m = re.search(r'<tableValueTotal>(\d+)</tableValueTotal>', text, re.IGNORECASE)
        if m:
            return int(m.group(1)) * 1000  # reported in thousands

    except Exception as e:
        pass

    return None

# ── Main ──────────────────────────────────────────────────────────
filers = get_all_13f_filers()

print(f"\nFetching AUM for {len(filers)} filers (this will take a while)...")
results = []
total = len(filers)

for i, (cik, name) in enumerate(filers.items()):
    aum = get_aum_from_submission(cik)
    if aum and aum > 0:
        results.append({"cik": cik, "name": name, "aum": aum})
        if len(results) % 50 == 0:
            print(f"  [{i+1}/{total}] {len(results)} with AUM so far, latest: {name} ${aum:,.0f}")

    time.sleep(0.4)

# Sort by AUM descending
results.sort(key=lambda x: x["aum"], reverse=True)
top100 = results[:100]

print("\n=== TOP 100 FUNDS BY AUM ===")
for rank, f in enumerate(top100, 1):
    aum_b = f["aum"] / 1e9
    print(f"{rank:3}. {f['name'][:50]:<50} ${aum_b:.1f}B  (CIK: {f['cik']})")

with open("top100.json", "w") as f:
    json.dump(top100, f, indent=2)

print("\nSaved to top100.json")
