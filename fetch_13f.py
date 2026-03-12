import urllib.request
import json
import xml.etree.ElementTree as ET

# Pershing Square's CIK
CIK = "0001336528"

# Step 1: Get their filing history
url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
req = urllib.request.Request(url, headers={"User-Agent": "nadermassoudi@aol.com"})
response = urllib.request.urlopen(req)
data = json.loads(response.read())

# Step 2: Find the most recent 13F-HR filing
filings = data["filings"]["recent"]
for i, form in enumerate(filings["form"]):
    if form == "13F-HR":
        accession_raw = filings["accessionNumber"][i]
        period = filings["reportDate"][i]
        break

accession = accession_raw.replace("-", "")
print(f"Latest 13F-HR: {accession_raw} | Period: {period}")

# Step 3: Fetch the infotable.xml (the actual holdings)
info_url = (
    f"https://www.sec.gov/Archives/edgar/data/{CIK.lstrip('0')}/"
    f"{accession}/infotable.xml"
)
req2 = urllib.request.Request(info_url, headers={"User-Agent": "nadermassoudi@aol.com"})
xml_data = urllib.request.urlopen(req2).read().decode("utf-8")

# Step 4: Save raw XML to file
with open("pershing_latest_13f.xml", "w") as f:
    f.write(xml_data)
print("Saved to pershing_latest_13f.xml")

# Step 5: Parse and print holdings
root = ET.fromstring(xml_data)
ns = {"ns": root.tag.split("}")[0].strip("{")}  # extract namespace

print(f"\n{'Company':<35} {'Shares':>15} {'Value ($000s)':>15}")
print("-" * 67)
for entry in root.findall(".//{*}infoTable"):
    name    = entry.findtext("{*}nameOfIssuer", default="?").strip()
    shares  = entry.findtext(".//{*}sshPrnamt", default="0")
    value   = entry.findtext("{*}value", default="0")
    print(f"{name:<35} {int(shares):>15,} {int(value):>15,}")
