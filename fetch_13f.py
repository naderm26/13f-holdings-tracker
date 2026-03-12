import urllib.request
import json

FUNDS = [
    {
        "name": "Pershing Square Capital Management",
        "cik": "0001336528",
        "output_xml": "pershing_latest_13f.xml"
    },
    {
        "name": "Duquesne Family Office LLC",
        "cik": "0001536411",
        "output_xml": "duquesne_latest_13f.xml"
    }
]

HEADERS = {"User-Agent": "nadermassoudi@aol.com"}

def fetch_latest_13f(fund):
    cik = fund["cik"]
    cik_stripped = str(int(cik))  # removes leading zeros: "0001336528" -> "1336528"

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    req = urllib.request.Request(url, headers=HEADERS)
    data = json.loads(urllib.request.urlopen(req).read())

    filings = data["filings"]["recent"]
    for i, form in enumerate(filings["form"]):
        if form == "13F-HR":
            accession_raw = filings["accessionNumber"][i]
            period = filings["reportDate"][i]
            break

    accession = accession_raw.replace("-", "")
    print(f"{fund['name']}: {accession_raw} | Period: {period}")

    # Try infotable.xml directly — works for most filers
    candidates = ["infotable.xml", "form13fInfoTable.xml", "informationtable.xml"]
    xml_data = None
    for filename in candidates:
        try:
            info_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{filename}"
            print(f"Trying: {info_url}")
            req2 = urllib.request.Request(info_url, headers=HEADERS)
            xml_data = urllib.request.urlopen(req2).read().decode("utf-8")
            print(f"Found: {filename}")
            break
        except Exception as e:
            print(f"Not found: {filename} ({e})")
            continue

    if not xml_data:
        # Fall back to index.json to find the filename
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/index.json"
        print(f"Trying index: {index_url}")
        req_idx = urllib.request.Request(index_url, headers=HEADERS)
        index_data = json.loads(urllib.request.urlopen(req_idx).read())
        files = [i["name"] for i in index_data.get("directory", {}).get("item", [])]
        print(f"Available files: {files}")
        raise Exception(f"Could not find infotable for {fund['name']}")

    with open(fund["output_xml"], "w") as f:
        f.write(xml_data)
    print(f"Saved to {fund['output_xml']}")

for fund in FUNDS:
    fetch_latest_13f(fund)
