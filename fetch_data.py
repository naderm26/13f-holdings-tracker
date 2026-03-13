import urllib.request
import json
import os

HEADERS = {"User-Agent": "nadermassoudi@aol.com"}

def fetch_url(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req).read()

def quarter_label(date_str):
    # "2025-09-30" -> "2025Q3"
    year, month, _ = date_str.split("-")
    q = (int(month) - 1) // 3 + 1
    return f"{year}Q{q}"

def get_infotable_filename(cik_stripped, accession, accession_raw):
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/index.json"
    try:
        data = json.loads(fetch_url(index_url))
        for item in data.get("directory", {}).get("item", []):
            name = item.get("name", "")
            lower = name.lower()
            if lower.endswith(".xml") and lower not in ["primary_doc.xml"]:
                if any(k in lower for k in ["infotable", "informationtable", "form13f", "13f"]):
                    return name
        # fallback: return any xml that isn't primary_doc
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

    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = json.loads(fetch_url(submissions_url))

    filings = data["filings"]["recent"]
    collected = []
    for i, form in enumerate(filings["form"]):
        if form == "13F-HR":
            collected.append({
                "accession_raw": filings["accessionNumber"][i],
                "period": filings["reportDate"][i]
            })
        if len(collected) == 4:
            break

    os.makedirs("data", exist_ok=True)

    for filing in collected:
        accession_raw = filing["accession_raw"]
        period = filing["period"]
        accession = accession_raw.replace("-", "")
        label = quarter_label(period)
        out_file = f"data/{fund_id}_{label}.xml"

        if os.path.exists(out_file):
            print(f"  {label} already exists, skipping")
            continue

        filename = get_infotable_filename(cik_stripped, accession, accession_raw)
        info_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{filename}"
        print(f"  Fetching {label}: {filename}")

        try:
            xml_data = fetch_url(info_url).decode("utf-8")
            with open(out_file, "w") as f:
                f.write(xml_data)
            print(f"  Saved {out_file}")
        except Exception as e:
            print(f"  Failed {label}: {e}")

with open("funds.json") as f:
    funds = json.load(f)

for fund in funds:
    fetch_fund(fund)

print("\nDone fetching all funds.")
