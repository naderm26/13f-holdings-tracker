import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import json
import os
import time

HEADERS = {"User-Agent": "nadermassoudi@aol.com"}
RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13F-HR&dateb=&owner=include&count=40&search_text=&output=atom"

def fetch_url(url, retries=3):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                time.sleep(3)
        except Exception as e:
            print(f"  Error: {e}, retrying...")
            time.sleep(3)
    return None

def get_tracked_ciks():
    with open("funds.json") as f:
        funds = json.load(f)
    return {str(int(fund["cik"])): fund for fund in funds}

def parse_rss_filings():
    data = fetch_url(RSS_URL)
    if not data:
        print("Failed to fetch RSS feed")
        return []

    root = ET.fromstring(data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    filings = []

    for entry in root.findall("atom:entry", ns):
        link = entry.find("atom:link", ns)
        if link is None:
            continue
        href = link.get("href", "")
        if "CIK=" in href:
            cik = str(int(href.split("CIK=")[1].split("&")[0]))
        else:
            continue
        content = entry.find("atom:content", ns)
        if content is None:
            continue
        text = content.text or ""
        if "Accession" not in text:
            continue
        for line in text.split("\n"):
            if "Accession" in line:
                acc = line.split(":")[-1].strip().replace("-", "")
                filings.append((cik, acc))
                break

    return filings

def already_fetched(fund_id, cik):
    """Check if we already have recent data for this fund by looking at data/ folder."""
    import glob
    existing = glob.glob(f"data/{fund_id}_*.json")
    return len(existing) > 0

def trigger_fetch_workflow(repo, token):
    """Trigger fetch2.yml via GitHub API."""
    url = f"https://api.github.com/repos/{repo}/actions/workflows/fetch2.yml/dispatches"
    payload = json.dumps({"ref": "main"}).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    })
    try:
        urllib.request.urlopen(req, timeout=30)
        print("✓ Triggered fetch2.yml successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to trigger fetch2.yml: {e}")
        return False

# ── Main ─────────────────────────────────────────────────────────
print("Checking SEC RSS feed for new 13F-HR filings...")
tracked = get_tracked_ciks()
filings = parse_rss_filings()
print(f"Found {len(filings)} recent filings in RSS feed")

new_filing_found = False
for cik, accession in filings:
    if cik in tracked:
        fund = tracked[cik]
        fund_id = fund["id"]
        # Check if we already have data for this accession
        marker = f"data/{fund_id}_rss_{accession}.seen"
        if os.path.exists(marker):
            continue
        print(f"\nNew filing detected: {fund['name']} (CIK: {cik}, accession: {accession})")
        # Mark as seen so we don't trigger multiple times for the same filing
        os.makedirs("data", exist_ok=True)
        with open(marker, "w") as f:
            f.write(accession)
        new_filing_found = True
        break  # one trigger per run is enough

if new_filing_found:
    repo  = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if repo and token:
        trigger_fetch_workflow(repo, token)
    else:
        print("Missing GITHUB_REPOSITORY or GITHUB_TOKEN — cannot trigger workflow")
else:
    print("\nNo new filings found for tracked funds.")

# Save result for workflow step
with open("rss_check_result.txt", "w") as f:
    f.write("triggered" if new_filing_found else "none")
