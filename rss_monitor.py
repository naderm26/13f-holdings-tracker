import re
import urllib.request
import urllib.error
import json
import os
import time
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "13fai@proton.me"}
LOOKBACK_DAYS = 2  # ignore filings older than this

# count=100 is the SEC maximum
RSS_URLS = [
    ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13F-HR&dateb=&owner=include&count=100&search_text=&output=atom", "13F-HR"),
    ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13F-HR%2FA&dateb=&owner=include&count=100&search_text=&output=atom", "13F-HR/A"),
]

def fetch_url(url, retries=3):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            response = urllib.request.urlopen(req, timeout=30)
            data = response.read().decode("utf-8", errors="replace")
            print(f"  HTTP {response.status} — {len(data)} chars received")
            return data
        except urllib.error.HTTPError as e:
            print(f"  HTTPError {e.code}: {e.reason}")
            if e.code == 429:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                time.sleep(3)
        except Exception as e:
            print(f"  Error (attempt {attempt+1}): {type(e).__name__}: {e}")
            time.sleep(3)
    print(f"  All retries exhausted.")
    return None

def get_tracked_ciks():
    with open("funds.json") as f:
        funds = json.load(f)
    return {str(int(fund["cik"])): fund for fund in funds}

def parse_rss_filings(url, form_type):
    """
    Parse SEC RSS feed using simple regex on raw text.
    SEC Atom entry format:
      <link href="https://www.sec.gov/Archives/edgar/data/{CIK}/..."/>
      <summary> <b>Filed:</b> 2026-04-20 <b>AccNo:</b> 0001234567-26-000001 <b>Size:</b> 70 KB </summary>
      <updated>2026-04-20T00:00:00-04:00</updated>
    Only includes filings from the last LOOKBACK_DAYS days.
    """
    print(f"\nFetching {form_type} feed...")
    text = fetch_url(url)
    if not text:
        print(f"  ERROR: fetch returned nothing")
        return []

    # Split into individual entry blocks
    entries = re.split(r'<entry[\s>]', text)
    entries = entries[1:]  # drop feed header before first entry
    print(f"  Found {len(entries)} entries")

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    print(f"  Cutoff date: {cutoff.strftime('%Y-%m-%d')} (lookback {LOOKBACK_DAYS} days)")

    filings = []
    skipped_old = 0
    for entry in entries:
        # Check filing date — <updated>2026-04-20T...</updated>
        date_match = re.search(r'<updated>(\d{4}-\d{2}-\d{2})', entry)
        if date_match:
            filed_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if filed_date < cutoff:
                skipped_old += 1
                continue

        # CIK from link href: /edgar/data/{CIK}/
        cik_match = re.search(r'/edgar/data/(\d+)/', entry)
        if not cik_match:
            continue
        cik = str(int(cik_match.group(1)))

        # Accession number after AccNo:
        acc_match = re.search(r'AccNo[^0-9]*(\d{10}-\d{2}-\d{6})', entry)
        if not acc_match:
            continue
        acc = acc_match.group(1).replace("-", "")
        filings.append((cik, acc, form_type))

    print(f"  Parsed {len(filings)} filings within lookback window ({skipped_old} older entries skipped)")
    return filings

def trigger_fetch_workflow(repo, token):
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
print(f"Tracking {len(tracked)} funds")

all_filings = []
for url, form_type in RSS_URLS:
    results = parse_rss_filings(url, form_type)
    all_filings.extend(results)
    time.sleep(1)

print(f"\nTotal filings in lookback window: {len(all_filings)}")

# Debug: print all CIKs found in feed to diagnose mismatches
all_ciks_in_feed = sorted(set(cik for cik, _, _ in all_filings))
print(f"All CIKs in feed ({len(all_ciks_in_feed)}): {all_ciks_in_feed}")
print(f"Olstein CIK in tracked: {'947996' in tracked}")
print(f"Olstein CIK in feed: {'947996' in all_ciks_in_feed}")

tracked_in_feed = [(cik, ftype) for cik, _, ftype in all_filings if cik in tracked]
if tracked_in_feed:
    print("Tracked funds seen in feed:")
    for cik, ftype in tracked_in_feed:
        print(f"  {ftype}: {tracked[cik]['name']} (CIK: {cik})")
else:
    print("No tracked fund CIKs found in feed.")

new_filing_found = False
os.makedirs("data", exist_ok=True)

for cik, accession, form_type in all_filings:
    if cik not in tracked:
        continue

    fund    = tracked[cik]
    fund_id = fund["id"]
    marker  = f"data/{fund_id}_rss_{accession}.seen"

    if os.path.exists(marker):
        continue

    label = "AMENDMENT" if form_type == "13F-HR/A" else "NEW FILING"
    print(f"\n{label} detected: {fund['name']} (CIK: {cik}, form: {form_type}, accession: {accession})")

    if form_type == "13F-HR/A":
        print(f"  -> Amendment. fetch_data.py will overwrite prior data for that period.")

    with open(marker, "w") as f:
        f.write(f"{form_type}:{accession}")

    new_filing_found = True
    break

if new_filing_found:
    repo  = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if repo and token:
        trigger_fetch_workflow(repo, token)
    else:
        print("Missing GITHUB_REPOSITORY or GITHUB_TOKEN — cannot trigger workflow")
else:
    print("\nNo new filings found for tracked funds.")

with open("rss_check_result.txt", "w") as f:
    f.write("triggered" if new_filing_found else "none")
