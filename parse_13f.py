import xml.etree.ElementTree as ET
import csv

FUNDS = [
    {
        "input_xml":  "pershing_latest_13f.xml",
        "output_csv": "pershing_latest_13f.csv"
    },
    {
        "input_xml":  "duquesne_latest_13f.xml",
        "output_csv": "duquesne_latest_13f.csv"
    }
]

def parse_fund(fund):
    tree = ET.parse(fund["input_xml"])
    root = tree.getroot()

    with open(fund["output_csv"], "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Company", "CUSIP", "Shares", "Value", "Discretion"])

        for entry in root.findall(".//{*}infoTable"):
            name       = entry.findtext("{*}nameOfIssuer", default="").strip()
            cusip      = entry.findtext("{*}cusip", default="").strip()
            shares     = entry.findtext(".//{*}sshPrnamt", default="0").strip()
            value      = entry.findtext("{*}value", default="0").strip()
            discretion = entry.findtext("{*}investmentDiscretion", default="").strip()
            writer.writerow([name, cusip, int(shares), int(value), discretion])

    print(f"Saved to {fund['output_csv']}")

for fund in FUNDS:
    parse_fund(fund)
