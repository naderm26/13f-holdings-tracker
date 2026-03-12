import xml.etree.ElementTree as ET
import csv

# Load the XML file
tree = ET.parse("pershing_latest_13f.xml")
root = tree.getroot()

# Open a CSV to write to
with open("pershing_latest_13f.csv", "w", newline="") as f:
    writer = csv.writer(f)
    # Header row
    writer.writerow(["Company", "CUSIP", "Shares", "Value ($000s)", "Discretion"])

    for entry in root.findall(".//{*}infoTable"):
        name      = entry.findtext("{*}nameOfIssuer", default="").strip()
        cusip     = entry.findtext("{*}cusip", default="").strip()
        shares    = entry.findtext(".//{*}sshPrnamt", default="0").strip()
        value     = entry.findtext("{*}value", default="0").strip()
        discretion = entry.findtext("{*}investmentDiscretion", default="").strip()
        writer.writerow([name, cusip, int(shares), int(value), discretion])

print("Done! Saved to pershing_latest_13f.csv")
