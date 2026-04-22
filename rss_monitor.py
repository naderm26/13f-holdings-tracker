"""
rss_monitor.py
Checks EDGAR directly for new 13F-HR filings across all tracked funds.
Triggers fetch2.yml once if ANY fund has a newer filing than what we have stored.
Replaces RSS-based approach which was unreliable during peak filing season.
"""

import urllib.request
import urllib.error
import json
import os
import time

HEADERS = {"User-Agent": "13fai@proton.me"}

def fetch_url(url, retries=3):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            response = urllib.request.urlopen(req, timeout=30)
            return response.read()
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} for {url}")
            if e.code == 429:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif e.code == 404:
                return None
            else:
                time.sleep(3)
        except Exception as e:
            print(f"  Error (attempt {attempt+1}): {type(e).__name__}: {e}")
            time.sleep(3)
    return None

def get_latest_edgar_filing(cik):
    """
    Fetch EDGAR submissions for a fund and return the most recent 13F-HR filing date.
    Returns (filed_date, accession) or (None, None) if no filing found.
    """
    cik_padded = cik.zfill(10) if not cik.startswith("0") else cik
    url  = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    data = fetch_url(url)
    if not data:
        return None, None
    try:
        submissions = json.loads(data)
        filings     = submissions.get("filings", {}).get("recent", {})
        forms       = filings.get("form", [])
        dates       = filings.get("filingDate", [])
        accessions  = filings.get("accessionNumber", [])
        for i, form in enumerate(forms):
            if form in ("13F-HR", "13F-HR/A"):
                return dates[i], accessions[i].replace("-", "")
    except Exception as e:
        print(f"  Parse error: {e}")
    return None, None

def get_stored_latest(fund_id):
    """
    Return the most recent quarter's filed date from our stored per-fund JSON.
    Returns None if no data stored yet.
    """
    path = f"data/{fund_id}.json"
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        quarters = data.get("quarters", {})
        if not quarters:
            return None
        # Most recent quarter sorted descending
        latest_q = sorted(quarters.keys(), reverse=True)[0]
        return quarters[latest_q].get("filed", None)
    except Exception:
        return None

def trigger_fetch_workflow(repo, token):
    """Trigger fetch2.yml via GitHub API."""
    url     = f"https://api.github.com/repos/{repo}/actions/workflows/fetch2.yml/dispatches"
    payload = json.dumps({"ref": "main"}).encode()
    req     = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"token {token}",
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json"
    })
    try:
        urllib.request.urlopen(req, timeout=30)
        print("✓ Triggered fetch2.yml successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to trigger fetch2.yml: {e}")
        return False

# ── Main ─────────────────────────────────────────────────────────
print("Checking EDGAR for new 13F-HR filings across tracked funds...")

with open("funds.json") as f:
    funds = json.load(f)

print(f"Checking {len(funds)} funds...\n")

new_filing_found = False
funds_with_new   = []

for fund in funds:
    fund_id  = fund["id"]
    cik      = fund["cik"]
    name     = fund["name"]

    edgar_date, accession = get_latest_edgar_filing(cik)
    if not edgar_date:
        continue

    stored_date = get_stored_latest(fund_id)

    if stored_date is None or edgar_date > stored_date:
        print(f"  NEW: {name}")
        print(f"    EDGAR latest: {edgar_date} | Stored latest: {stored_date or 'none'}")
        funds_with_new.append(name)
        new_filing_found = True
        break  # one trigger is enough — fetch2.yml picks up everything

    time.sleep(0.3)  # be polite to EDGAR

if funds_with_new:
    print(f"\nNew filing detected for: {funds_with_new[0]}")
    print("Triggering fetch2.yml to update all funds...")
else:
    print("\nNo new filings found — all funds are up to date.")

# Trigger fetch2.yml once if anything new found
if new_filing_found:
    repo  = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if repo and token:
        trigger_fetch_workflow(repo, token)
    else:
        print("Missing GITHUB_REPOSITORY or GITHUB_TOKEN — cannot trigger workflow")

# Save result for workflow step
with open("rss_check_result.txt", "w") as f:
    f.write("triggered" if new_filing_found else "none")
