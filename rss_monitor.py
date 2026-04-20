import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import json
import os
import time

HEADERS = {"User-Agent": "nadermassoudi@aol.com"}

# Two RSS URLs — one for original filings, one for amendments
# count=100 is the SEC maximum — gives largest possible window to avoid missing filings
# that appear in the feed after a delay and risk scrolling off before next daily run
RSS_URLS = [
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13F-HR&dateb=&owner=include&count=100&search_text=&output=atom",
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13F-HR%2FA&dateb=&owner=include&count=100&search_text=&output=atom",
]

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

def parse_rss_filings(url, form_type):
    """Fetch one RSS feed and return list of (cik, accession, form_type) tuples."""
    data = fetch_url(url)
    if not data:
        print(f"Failed to fetch RSS feed: {url}")
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
                filings.append((cik, acc, form_type))
                break

    return filings

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
print("Checking SEC RSS feed for new 13F-HR and 13F-HR/A filings...")
tracked = get_tracked_ciks()

# Collect filings from both feeds (originals + amendments)
all_filings = []
for url, form_type in [
    (RSS_URLS[0], "13F-HR"),
    (RSS_URLS[1], "13F-HR/A"),
]:
    results = parse_rss_filings(url, form_type)
    print(f"  {form_type}: {len(results)} recent filings in feed")
    all_filings.extend(results)
    time.sleep(1)  # brief pause between RSS requests

print(f"Total filings found across both feeds: {len(all_filings)}")

# Log all tracked fund CIKs seen in feed — helps diagnose future misses
tracked_in_feed = [(cik, ftype) for cik, _, ftype in all_filings if cik in tracked]
if tracked_in_feed:
    print("Tracked fund CIKs seen in feed:")
    for cik, ftype in tracked_in_feed:
        print(f"  {ftype}: {tracked[cik]['name']} (CIK: {cik})")
else:
    print("No tracked fund CIKs found in feed at all.")

new_filing_found = False
os.makedirs("data", exist_ok=True)

for cik, accession, form_type in all_filings:
    if cik not in tracked:
        continue

    fund     = tracked[cik]
    fund_id  = fund["id"]
    marker   = f"data/{fund_id}_rss_{accession}.seen"

    if os.path.exists(marker):
        continue

    label = "AMENDMENT" if form_type == "13F-HR/A" else "NEW FILING"
    print(f"\n{label} detected: {fund['name']} (CIK: {cik}, form: {form_type}, accession: {accession})")

    if form_type == "13F-HR/A":
        print(f"  → Amendment for an existing quarter. fetch_data.py will overwrite the prior data for that period.")

    # Mark as seen so we don't trigger multiple times for the same filing
    with open(marker, "w") as f:
        f.write(f"{form_type}:{accession}")

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
