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
    cik_stripped = cik.lstrip("0")
    print(f"{fund['name']}: {accession_raw} | Period: {period}")

    # Use EDGAR's filing index JSON
    index_url = f"https://data.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{accession_raw}-index.json"
    req_idx = urllib.request.Request(index_url, headers=HEADERS)
    index_data = json.loads(urllib.request.urlopen(req_idx).read())

    # Find the information table XML file
    info_file = None
    for item in index_data.get("documents", []):
        doc_type = item.get("type", "").upper()
        name = item.get("name", "").lower()
        if doc_type == "INFORMATION TABLE" or "table" in name or "infotable" in name:
            info_file = item["name"]
            break

    if not info_file:
        raise Exception(f"Could not find infotable for {fund['name']}. Files: {[d['name'] for d in index_data.get('documents', [])]}")

    info_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}/{info_file}"
    print(f"Fetching: {info_file}")
    req2 = urllib.request.Request(info_url, headers=HEADERS)
    xml_data = urllib.request.urlopen(req2).read().decode("utf-8")

    with open(fund["output_xml"], "w") as f:
        f.write(xml_data)
    print(f"Saved to {fund['output_xml']}")

for fund in FUNDS:
    fetch_latest_13f(fund)
