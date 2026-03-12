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

    base_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{accession}"

    # Try common infotable filenames
    candidates = ["infotable.xml", "form13fInfoTable.xml", "informationtable.xml"]
    xml_data = None
    for filename in candidates:
        try:
            req2 = urllib.request.Request(f"{base_url}/{filename}", headers=HEADERS)
            xml_data = urllib.request.urlopen(req2).read().decode("utf-8")
            print(f"Found: {filename}")
            break
        except Exception:
            continue

    if not xml_data:
        # Fall back: parse the index page to find it
        index_url = f"{base_url}/{accession_raw}-index.htm"
        req_idx = urllib.request.Request(index_url, headers=HEADERS)
        html = urllib.request.urlopen(req_idx).read().decode("utf-8")
        # Find any xml file that looks like an info table
        import re
        matches = re.findall(r'href="([^"]*(?:info|table)[^"]*\.xml)"', html, re.IGNORECASE)
        if not matches:
            raise Exception(f"Could not find infotable for {fund['name']}")
        filename = matches[0].split("/")[-1]
        req2 = urllib.request.Request(f"{base_url}/{filename}", headers=HEADERS)
        xml_data = urllib.request.urlopen(req2).read().decode("utf-8")
        print(f"Found via index: {filename}")

    with open(fund["output_xml"], "w") as f:
        f.write(xml_data)
    print(f"Saved to {fund['output_xml']}")

for fund in FUNDS:
    fetch_latest_13f(fund)
