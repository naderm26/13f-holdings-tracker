import xml.etree.ElementTree as ET
import csv
import os
import glob
import json

def parse_xml(xml_file, csv_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Company", "CUSIP", "Shares", "Value", "Discretion"])
        for entry in root.findall(".//{*}infoTable"):
            name       = entry.findtext("{*}nameOfIssuer", default="").strip()
            cusip      = entry.findtext("{*}cusip", default="").strip()
            shares     = entry.findtext(".//{*}sshPrnamt", default="0").strip()
            value      = entry.findtext("{*}value", default="0").strip()
            discretion = entry.findtext("{*}investmentDiscretion", default="").strip()
            writer.writerow([name, cusip, int(shares), int(value), discretion])

    print(f"  Parsed {xml_file} -> {csv_file}")

with open("funds.json") as f:
    funds = json.load(f)

os.makedirs("data", exist_ok=True)

for fund in funds:
    fund_id = fund["id"]
    xml_files = sorted(glob.glob(f"data/{fund_id}_*.xml"), reverse=True)
    for xml_file in xml_files:
        csv_file = xml_file.replace(".xml", ".csv")
        if not os.path.exists(csv_file):
            parse_xml(xml_file, csv_file)
        else:
            print(f"  {csv_file} already exists, skipping")

print("\nDone parsing all funds.")
