import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
import json
import os
import time
import subprocess

HEADERS = {"User-Agent": "nadermassoudi@aol.com"}
RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13F-HR&dateb=&owner=include&count=40&search_text=&output=atom"

def fetch_url(url, retries=3):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                time.sleep(3)
        except Exception as e:
            print(f"  Error: {e}, retrying...")
            time.sleep(3)
    return None

def get_tracked_ciks():
    with open("funds.json") as f:
        funds = json.load(f)
    return {str(int(fund["cik"])): fund for fund in funds}

def parse_rss_filings():
    """Fetch SEC RSS feed and return list of (cik, accession) tuples for 13F-HR filings."""
    data = fetch_url(RSS_URL)
    if not data:
        print("Failed to fetch RSS feed")
        return []

    root = ET.fromstring(data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    filings = []

    for entry in root.findall("atom:entry", ns):
        # Extract CIK from the filing URL
        link = entry.find("atom:link", ns)
        if link is None:
            continue
        href = link.get("href", "")

        # CIK is in the URL like: .../cgi-bin/browse-edgar?action=getcompany&CIK=0001067983&...
        if "CIK=" in href:
            cik_raw = href.split("CIK=")[1].split("&")[0]
            cik = str(int(cik_raw))
        else:
            continue

        # Get accession number from content
        content = entry.find("atom:content", ns)
        if content is None:
            continue
        text = content.text or ""
        if "Accession" not in text:
            continue

        # Extract accession number
        for line in text.split("\n"):
            if "Accession" in line:
                acc = line.split(":")[-1].strip().replace("-", "")
                filings.append((cik, acc))
                break

    return filings

def quarter_label(date_str):
    year, month, _ = date_str.split("-")
    q = (int(month) - 1) // 3 + 1
    return f"{year}Q{q}"

def get_infotable_filename(cik_stripped, accession):
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/index.json"
    try:
        data = json.loads(fetch_url(index_url))
        for item in data.get("directory", {}).get("item", []):
            name = item.get("name", "")
            lower = name.lower()
            if lower.endswith(".xml") and lower != "primary_doc.xml":
                if any(k in lower for k in ["infotable", "informationtable", "form13f", "13f"]):
                    return name
        for item in data.get("directory", {}).get("item", []):
            name = item.get("name", "")
            if name.lower().endswith(".xml") and name.lower() != "primary_doc.xml":
                return name
    except Exception as e:
        print(f"  Index lookup failed: {e}")
    return "infotable.xml"

def fetch_new_filing(fund, cik_stripped, accession):
    fund_id = fund["id"]

    # Get filing metadata
    try:
        submissions_url = f"https://data.sec.gov/submissions/CIK{fund['cik']}.json"
        subs = json.loads(fetch_url(submissions_url))
        filings = subs["filings"]["recent"]

        period = None
        filed  = None
        for i, acc in enumerate(filings["accessionNumber"]):
            if acc.replace("-", "") == accession:
                period = filings["reportDate"][i]
                filed  = filings["filingDate"][i]
                break

        if not period:
            print(f"  Could not find period for accession {accession}")
            return False

    except Exception as e:
        print(f"  Failed to get metadata: {e}")
        return False

    label    = quarter_label(period)
    out_file = f"data/{fund_id}_{label}.xml"
    meta_file = f"data/{fund_id}_{label}.json"

    if os.path.exists(out_file):
        print(f"  {label} already exists, skipping")
        return False

    try:
        filename = get_infotable_filename(cik_stripped, accession)
        info_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{filename}"
        print(f"  Fetching {label}: {filename}")
        xml_data = fetch_url(info_url).decode("utf-8")
        os.makedirs("data", exist_ok=True)
        with open(out_file, "w") as f:
            f.write(xml_data)
        with open(meta_file, "w") as f:
            json.dump({"filed": filed, "period": period}, f)
        print(f"  Saved {out_file}")
        return True
    except Exception as e:
        print(f"  Failed: {e}")
        return False

# ── Main ──────────────────────────────────────────────────────────
print("Checking SEC RSS feed for new 13F-HR filings...")
tracked = get_tracked_ciks()
filings = parse_rss_filings()
print(f"Found {len(filings)} recent filings in RSS feed")

new_files = []
for cik, accession in filings:
    if cik in tracked:
        fund = tracked[cik]
        print(f"\nTracked fund found: {fund['name']} (CIK: {cik})")
        if fetch_new_filing(fund, cik, accession):
            new_files.append(fund["id"])

if new_files:
    print(f"\nNew data fetched for: {', '.join(new_files)}")
    # Parse the new XMLs to CSVs
    os.system("python parse_13f.py")
else:
    print("\nNo new filings found for tracked funds.")

# Save result for workflow to check
with open("rss_check_result.txt", "w") as f:
    f.write(",".join(new_files) if new_files else "none")
