import urllib.request

HEADERS = {"User-Agent": "nadermassoudi@aol.com"}

FUNDS = [
    {
        "name": "Pershing Square Capital Management",
        "url": "https://www.sec.gov/Archives/edgar/data/1336528/000117266126001091/infotable.xml",
        "output_xml": "pershing_latest_13f.xml"
    },
    {
        "name": "Duquesne Family Office LLC",
        "url": "https://www.sec.gov/Archives/edgar/data/1536411/000153641126000002/form13f_20251231.xml",
        "output_xml": "duquesne_latest_13f.xml"
    }
]

for fund in FUNDS:
    print(f"Fetching {fund['name']}...")
    req = urllib.request.Request(fund["url"], headers=HEADERS)
    xml_data = urllib.request.urlopen(req).read().decode("utf-8")
    with open(fund["output_xml"], "w") as f:
        f.write(xml_data)
    print(f"Saved to {fund['output_xml']}")
