import urllib.request
import urllib.error
import json
import os
import csv
import glob
import time
import xml.etree.ElementTree as ET

HEADERS = {"User-Agent": "nadermassoudi@aol.com"}

def fetch_url(url, retries=4):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif e.code == 404:
                raise
            else:
                print(f"  HTTP {e.code}, retrying...")
                time.sleep(3)
        except Exception as e:
            print(f"  Error: {e}, retrying...")
            time.sleep(3)
    raise Exception(f"Failed after {retries} retries: {url}")

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

def parse_xml_to_holdings(xml_text):
    """Parse XML string into a list of holding dicts."""
    root = ET.fromstring(xml_text)
    holdings = []
    for entry in root.findall(".//{*}infoTable"):
        company    = entry.findtext("{*}nameOfIssuer", default="").strip()
        cusip      = entry.findtext("{*}cusip", default="").strip()
        shares     = entry.findtext(".//{*}sshPrnamt", default="0").strip()
        value      = entry.findtext("{*}value", default="0").strip()
        discretion = entry.findtext("{*}investmentDiscretion", default="").strip()
        putcall    = entry.findtext("{*}putCall", default="").strip()
        if company or cusip:
            holdings.append({
                "company":    company,
                "cusip":      cusip,
                "shares":     int(shares) if shares.isdigit() else 0,
                "value":      int(value)  if value.isdigit()  else 0,
                "discretion": discretion,
                "putcall":    putcall
            })
    return holdings

def write_csv(csv_file, holdings):
    """Write holdings to CSV for human verification."""
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Company", "CUSIP", "Shares", "Value", "Discretion", "PutCall"])
        for h in holdings:
            writer.writerow([h["company"], h["cusip"], h["shares"], h["value"], h["discretion"], h["putcall"]])

def prune_old_csvs(fund_id, keep=8):
    """Delete CSVs beyond the most recent `keep` quarters for a fund."""
    csvs = sorted(glob.glob(f"data/{fund_id}_*.csv"), reverse=True)
    for old_csv in csvs[keep:]:
        os.remove(old_csv)
        print(f"  Pruned old CSV: {old_csv}")

def load_fund_json(fund_id):
    """Load existing per-fund JSON or return empty structure."""
    path = f"data/{fund_id}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"quarters": {}}

def save_fund_json(fund_id, fund_name, fund_data):
    """Write per-fund JSON with id and name at top level."""
    fund_data["id"]   = fund_id
    fund_data["name"] = fund_name
    path = f"data/{fund_id}.json"
    with open(path, "w") as f:
        json.dump(fund_data, f)
    print(f"  Saved {path}")

def collect_filings(data):
    """Collect up to 8 most recent 13F-HR filings with pagination fallback."""
    collected = []
    filings = data["filings"]["recent"]
    for i, form in enumerate(filings["form"]):
        if form == "13F-HR":
            collected.append({
                "accession_raw": filings["accessionNumber"][i],
                "period":        filings["reportDate"][i],
                "filed":         filings["filingDate"][i]
            })
        if len(collected) == 8:
            return collected

    for file_entry in data["filings"].get("files", []):
        if len(collected) >= 8:
            break
        try:
            url = f"https://data.sec.gov/submissions/{file_entry['name']}"
            old_data = json.loads(fetch_url(url))
            for i, form in enumerate(old_data["form"]):
                if form == "13F-HR":
                    collected.append({
                        "accession_raw": old_data["accessionNumber"][i],
                        "period":        old_data["reportDate"][i],
                        "filed":         old_data["filingDate"][i]
                    })
                if len(collected) == 8:
                    break
        except Exception as e:
            print(f"  Pagination fetch failed: {e}")

    return collected

def fetch_fund(fund):
    cik        = fund["cik"]
    cik_stripped = str(int(cik))
    fund_id    = fund["id"]
    fund_name  = fund["name"]

    print(f"\nFetching {fund_name}...")

    try:
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        data = json.loads(fetch_url(submissions_url))
    except Exception as e:
        print(f"  Skipping — could not load submissions: {e}")
        return

    collected = collect_filings(data)
    if not collected:
        print(f"  No 13F-HR filings found, skipping")
        return

    os.makedirs("data", exist_ok=True)

    # Load existing per-fund JSON so we only fetch quarters we don't have yet
    fund_data = load_fund_json(fund_id)
    changed = False

    for filing in collected:
        accession_raw = filing["accession_raw"]
        period        = filing["period"]
        filed         = filing["filed"]
        accession     = accession_raw.replace("-", "")
        label         = quarter_label(period)
        csv_file      = f"data/{fund_id}_{label}.csv"

        # Skip if already in per-fund JSON
        if label in fund_data.get("quarters", {}):
            print(f"  {label} already in fund JSON, skipping")
            # Still write CSV if missing (for verification)
            if not os.path.exists(csv_file):
                holdings = fund_data["quarters"][label]["holdings"]
                write_csv(csv_file, holdings)
                print(f"  Wrote missing CSV: {csv_file}")
            continue

        try:
            filename = get_infotable_filename(cik_stripped, accession)
            info_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{filename}"
            print(f"  Fetching {label}: {filename}")
            xml_text = fetch_url(info_url).decode("utf-8")

            # Parse holdings from XML in memory — no XML file saved
            holdings = parse_xml_to_holdings(xml_text)

            # Write CSV for human verification
            write_csv(csv_file, holdings)
            print(f"  Saved CSV: {csv_file}")

            # Add to per-fund JSON
            if "quarters" not in fund_data:
                fund_data["quarters"] = {}
            fund_data["quarters"][label] = {
                "filed":    filed,
                "period":   period,
                "holdings": holdings
            }
            changed = True

        except Exception as e:
            print(f"  Failed {label}: {e}")

        time.sleep(0.5)

    # Keep only 8 most recent quarters in the fund JSON
    if "quarters" in fund_data:
        all_quarters = sorted(fund_data["quarters"].keys(), reverse=True)
        for old_q in all_quarters[8:]:
            del fund_data["quarters"][old_q]
            print(f"  Pruned old quarter from JSON: {old_q}")
            changed = True

    # Save per-fund JSON if anything changed
    if changed:
        save_fund_json(fund_id, fund_name, fund_data)

    # Prune CSVs to rolling 8-quarter window
    prune_old_csvs(fund_id, keep=8)

    time.sleep(1)

# ── Main ──────────────────────────────────────────────────────────
with open("funds.json") as f:
    funds = json.load(f)

for fund in funds:
    fetch_fund(fund)

print("\nDone fetching all funds.")
