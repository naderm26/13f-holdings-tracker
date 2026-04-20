import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import json
import os
import time

HEADERS = {"User-Agent": "nadermassoudi@aol.com"}

# Two RSS URLs — one for original filings, one for amendments
# count=100 is the SEC maximum — largest possible window to avoid missing filings
RSS_URLS = [
    ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13F-HR&dateb=&owner=include&count=100&search_text=&output=atom",    "13F-HR"),
    ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13F-HR%2FA&dateb=&owner=include&count=100&search_text=&output=atom", "13F-HR/A"),
]

def fetch_url(url, retries=3):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            response = urllib.request.urlopen(req, timeout=30)
            data = response.read()
            print(f"  HTTP {response.status} — {len(data)} bytes received")
            return data
        except urllib.error.HTTPError as e:
            body_preview = ""
            try:
                body_preview = e.read()[:300].decode("utf-8", errors="replace")
            except Exception:
                pass
            print(f"  HTTP {e.code} error — body preview: {body_preview}")
            if e.code == 429:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                time.sleep(3)
        except Exception as e:
            print(f"  Error (attempt {attempt+1}): {e}")
            time.sleep(3)
    print(f"  All retries exhausted.")
    return None

def get_tracked_ciks():
    with open("funds.json") as f:
        funds = json.load(f)
    return {str(int(fund["cik"])): fund for fund in funds}

def strip_ns(tag):
    """Strip XML namespace from a tag, e.g. '{http://...}entry' -> 'entry'."""
    return tag.split("}")[-1] if "}" in tag else tag

def parse_rss_filings(url, form_type):
    """Fetch one RSS feed and return list of (cik, accession, form_type) tuples."""
    print(f"\nFetching {form_type} feed...")
    data = fetch_url(url)
    if not data:
        print(f"  ERROR: fetch returned nothing for {form_type} feed")
        return []

    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        print(f"  ERROR: failed to parse XML — {e}")
        print(f"  Raw response preview: {data[:300].decode('utf-8', errors='replace')}")
        return []

    print(f"  Root tag: {root.tag}")

    # Namespace-agnostic entry search — strips namespace prefix before comparing
    # Handles both namespaced ({http://www.w3.org/2005/Atom}entry) and bare (entry) tags
    entries = [child for child in root if strip_ns(child.tag) == "entry"]
    print(f"  Found {len(entries)} entries (namespace-agnostic)")

    # Debug: show tags in first entry to help diagnose parsing
    if entries:
        first_tags = [strip_ns(c.tag) for c in entries[0]]
        print(f"  First entry child tags: {first_tags}")
    if len(entries) == 0:
        # Show first 500 chars of raw feed to help diagnose
        print(f"  Raw feed preview: {data[:500].decode('utf-8', errors='replace')}")

    filings = []
    for entry in entries:
        # Find link element (namespace-agnostic)
        link = next((c for c in entry if strip_ns(c.tag) == "link"), None)
        if link is None:
            continue
        href = link.get("href", "")
        if "CIK=" not in href:
            continue
        try:
            cik = str(int(href.split("CIK=")[1].split("&")[0]))
        except (ValueError, IndexError):
            continue

        # Find content element (namespace-agnostic)
        content = next((c for c in entry if strip_ns(c.tag) in ("content", "summary")), None)
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
print(f"Tracking {len(tracked)} funds")

# Collect filings from both feeds
all_filings = []
for url, form_type in RSS_URLS:
    results = parse_rss_filings(url, form_type)
    print(f"  {form_type}: {len(results)} filings parsed")
    all_filings.extend(results)
    time.sleep(1)

print(f"\nTotal filings across both feeds: {len(all_filings)}")

# Log all tracked fund CIKs seen in feed
tracked_in_feed = [(cik, ftype) for cik, _, ftype in all_filings if cik in tracked]
if tracked_in_feed:
    print("Tracked fund CIKs seen in feed:")
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
        print(f"  → Amendment. fetch_data.py will overwrite prior data for that period.")

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
