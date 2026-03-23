"""
check_entity_names.py
---------------------
Fetches the official SEC EDGAR entity name for each fund CIK and compares
it against the name stored in funds.json. Outputs a report of mismatches
and suggests updates.

Run locally:
    python check_entity_names.py

Or add as a GitHub Actions workflow (manual trigger).
"""

import json
import time
import urllib.request
import urllib.error

FUNDS_FILE = "funds.json"
HEADERS = {"User-Agent": "13FAI admin@13fai.com"}  # SEC requires a user-agent


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def pad_cik(cik):
    # Ensure 10-digit zero-padded CIK for EDGAR API
    return str(cik).lstrip("0").zfill(10)


def main():
    with open(FUNDS_FILE) as f:
        funds = json.load(f)

    print(f"{'#':<4} {'ID':<20} {'CIK':<12} {'NAME IN funds.json':<50} {'EDGAR ENTITY NAME':<50} {'MATCH'}")
    print("-" * 160)

    mismatches = []

    for i, fund in enumerate(funds, 1):
        fid  = fund["id"]
        cik  = fund["cik"]
        name = fund["name"]
        cik_padded = pad_cik(cik)

        url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        try:
            data = fetch_json(url)
            edgar_name = data.get("name", "").strip()
            # Also grab most recent 13F filing date for sanity check
            filings = data.get("filings", {}).get("recent", {})
            forms   = filings.get("form", [])
            dates   = filings.get("filingDate", [])
            last_13f = next(
                (dates[j] for j, f in enumerate(forms) if f == "13F-HR"),
                "no 13F found"
            )

            match = "✓" if edgar_name.lower() == name.lower() else "✗"
            print(f"{i:<4} {fid:<20} {cik:<12} {name:<50} {edgar_name:<50} {match}  (last 13F: {last_13f})")

            if match == "✗":
                mismatches.append({
                    "id":          fid,
                    "cik":         cik,
                    "current_name": name,
                    "edgar_name":  edgar_name,
                    "last_13f":    last_13f
                })

        except urllib.error.HTTPError as e:
            print(f"{i:<4} {fid:<20} {cik:<12} {name:<50} {'HTTP ERROR ' + str(e.code):<50} ✗")
            mismatches.append({"id": fid, "cik": cik, "current_name": name, "edgar_name": f"HTTP {e.code}", "last_13f": "—"})
        except Exception as e:
            print(f"{i:<4} {fid:<20} {cik:<12} {name:<50} {'ERROR: ' + str(e):<50} ✗")

        time.sleep(0.15)  # SEC rate limit — max ~10 req/sec

    print()
    print(f"{'=' * 80}")
    print(f"SUMMARY: {len(mismatches)} mismatches out of {len(funds)} funds")
    print()

    if mismatches:
        print("MISMATCHES — review and update funds.json as needed:")
        print()
        for m in mismatches:
            print(f"  Fund:         {m['id']}")
            print(f"  CIK:          {m['cik']}")
            print(f"  Current name: {m['current_name']}")
            print(f"  EDGAR name:   {m['edgar_name']}")
            print(f"  Last 13F:     {m['last_13f']}")
            print()


if __name__ == "__main__":
    main()
