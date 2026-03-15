import urllib.request
import urllib.error
import json
import os
import time

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
                raise  # don't retry 404s
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
        # fallback: any non-primary xml
        for item in data.get("directory", {}).get("item", []):
            name = item.get("name", "")
            if name.lower().endswith(".xml") and name.lower() != "primary_doc.xml":
                return name
    except Exception as e:
        print(f"  Index lookup failed: {e}")
    return "infotable.xml"

def fetch_fund(fund):
    cik = fund["cik"]
    cik_stripped = str(int(cik))
    fund_id = fund["id"]

    print(f"\nFetching {fund['name']}...")

    try:
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        data = json.loads(fetch_url(submissions_url))
    except Exception as e:
        print(f"  Skipping — could not load submissions: {e}")
        return

    filings = data["filings"]["recent"]
    collected = []
    for i, form in enumerate(filings["form"]):
        if form == "13F-HR":
            collected.append({
                "accession_raw": filings["accessionNumber"][i],
                "period":        filings["reportDate"][i],
                "filed":         filings["filingDate"][i]
            })
        if len(collected) == 8:
            break

    if not collected:
        print(f"  No 13F-HR filings found, skipping")
        return

    os.makedirs("data", exist_ok=True)

    for filing in collected:
        accession_raw = filing["accession_raw"]
        period = filing["period"]
        filed  = filing["filed"]
        accession = accession_raw.replace("-", "")
        label = quarter_label(period)
        out_file  = f"data/{fund_id}_{label}.xml"
        meta_file = f"data/{fund_id}_{label}.json"

        if os.path.exists(out_file):
            print(f"  {label} already exists, skipping")
            # Write meta if missing
            if not os.path.exists(meta_file):
                with open(meta_file, "w") as f:
                    json.dump({"filed": filed, "period": period}, f)
            continue

        try:
            filename = get_infotable_filename(cik_stripped, accession)
            info_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{filename}"
            print(f"  Fetching {label}: {filename}")
            xml_data = fetch_url(info_url).decode("utf-8")
            with open(out_file, "w") as f:
                f.write(xml_data)
            with open(meta_file, "w") as f:
                json.dump({"filed": filed, "period": period}, f)
            print(f"  Saved {out_file}")
        except Exception as e:
            print(f"  Failed {label}: {e}")

        time.sleep(0.5)  # be polite between filings

    time.sleep(1)  # pause between funds

with open("funds.json") as f:
    funds = json.load(f)

for fund in funds:
    fetch_fund(fund)

print("\nDone fetching all funds.")
