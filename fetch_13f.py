import urllib.request
import json
import xml.etree.ElementTree as ET

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
    response = urllib.request.urlopen(req)
    data = json.loads(response.read())

    filings = data["filings"]["recent"]
    for i, form in enumerate(filings["form"]):
        if form == "13F-HR":
            accession_raw = filings["accessionNumber"][i]
            period = filings["reportDate"][i]
            break

    accession = accession_raw.replace("-", "")
    print(f"{fund['name']}: {accession_raw} | Period: {period}")

    info_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/"
        f"{accession}/infotable.xml"
    )
    req2 = urllib.request.Request(info_url, headers=HEADERS)
    xml_data = urllib.request.urlopen(req2).read().decode("utf-8")

    with open(fund["output_xml"], "w") as f:
        f.write(xml_data)
    print(f"Saved to {fund['output_xml']}")

for fund in FUNDS:
    fetch_latest_13f(fund)
