# 13FAI Data Directory

This folder contains hedge fund 13F holdings data parsed from SEC EDGAR filings.
All data is public domain (sourced from SEC EDGAR 13F-HR filings).
Updated quarterly. All JSON files are publicly accessible via GitHub Pages.

Base URL: `https://13fai.com`

---

## Files Overview

| File | URL | Description |
|------|-----|-------------|
| `funds.json` | `/funds.json` | Master list of all 82 tracked funds (82 entries) |
| `stock_index.json` | `/stock_index.json` | All stocks with per-fund ownership across quarters |
| `cusip_to_ticker.json` | `/cusip_to_ticker.json` | CUSIP → ticker symbol mapping |
| `prices.json` | `/prices.json` | Last known price, 52-week high/low per ticker |
| `data/{fund_id}.json` | `/data/{fund_id}.json` | Per-fund holdings, all quarters |

---

## funds.json

Master list of all tracked institutional investors.

**URL:** `https://13fai.com/funds.json`

**Schema:**
```json
[
  {
    "id": "berkshire",
    "name": "Berkshire Hathaway (Warren Buffett)",
    "cik": "0001067983",
    "value_multiplier": 1,
    "bio_slug": "warren-buffett-portfolio"
  }
]
```

**Fields:**
- `id` — unique fund identifier, used to fetch per-fund JSON at `data/{id}.json`
- `name` — display name in format `"Fund Name (Manager Name)"`
- `cik` — SEC EDGAR Central Index Key (with leading zeros)
- `value_multiplier` — multiply all `value` fields by this number to get USD thousands. Most funds = 1. Some funds (Duquesne, Baupost, AKO, Olstein, Triple Frond, Aquamarine) = 1000, meaning their raw values are in millions not thousands.
- `bio_slug` — slug for the manager bio page if one exists (e.g. `"warren-buffett-portfolio"`)

**Note on value_multiplier:** To get actual USD value: `value × value_multiplier × 1000` = USD.
Example: value=57000, multiplier=1 → $57,000,000 ($57M).
Example: value=57000, multiplier=1000 → $57,000,000,000 ($57B).

---

## data/{fund_id}.json

Per-fund holdings for all available quarters (up to 8).

**URL:** `https://13fai.com/data/{fund_id}.json`
**Example:** `https://13fai.com/data/berkshire.json`

**Schema:**
```json
{
  "id": "aquamarine",
  "name": "Aquamarine Capital (Guy Spier)",
  "quarters": {
    "2026Q1": {
      "filed": "2026-04-17",
      "period": "2026-03-31",
      "holdings": [
        {
          "company": "AMERICAN EXPRESS CO",
          "cusip": "025816109",
          "shares": 65000,
          "value": 19661,
          "discretion": "SOLE",
          "putcall": ""
        }
      ]
    },
    "2025Q4": { "filed": "...", "period": "...", "holdings": [...] },
    "2025Q3": { "filed": "...", "period": "...", "holdings": [...] }
  }
}
```

**Fields:**
- `id` — matches the fund id in `funds.json`
- `name` — display name
- `quarters` — object keyed by quarter label (`"YYYYQn"`)
  - `filed` — date the 13F was filed with SEC (`YYYY-MM-DD`)
  - `period` — quarter end date this filing covers (`YYYY-MM-DD`)
  - `holdings` — array of positions
    - `company` — issuer name as reported in the 13F filing
    - `cusip` — CUSIP identifier (9 characters). Use `cusip_to_ticker.json` to resolve to ticker.
    - `shares` — number of shares (or par value for bonds)
    - `value` — reported value in USD thousands × `value_multiplier`. See value_multiplier note above.
    - `discretion` — investment discretion: `"SOLE"`, `"SHARED"`, or `"OTHER"`
    - `putcall` — `"Put"`, `"Call"`, or `""` (empty = equity position). Options are displayed but excluded from portfolio weight calculations.

**Quarter label format:** `"2026Q1"` = Q1 2026 (January–March 2026). Period end dates: Q1=Mar 31, Q2=Jun 30, Q3=Sep 30, Q4=Dec 31.

**All fund IDs (82 total):**
abrams, ako, akre, altarock, appaloosa, aquamarine, ariel_focus, atlantic_inv, baupost, berkshire, brave_warrior, cantillon, cas, causeway, chou, conifer, cooperman, daily_journal, davis, dodge_cox, dorsey, duquesne, durable_capital, egerton, engaged, fairfax, fairholme, first_eagle, fpa_crescent, fundsmith, gardner_russo, gates, giverny, greenhaven, greenlea_lane, greenlight, hh_intl, hillman, himalaya, icahn, jensen, kahn_brothers, lindsell_train, lone_pine, longleaf, mairs_power, makaira, markel, matrix, maverick, miller_value, oakcliff, oaktree, olstein, pabrai, patient_capital, pershing, polen, punch_card, pzena, rv_capital, scion, semper_augustus, sequoia, shawspring, situational_awareness, sound_shore, tci, thiel_macro, third_avenue, third_point, tiger_global, torray, trian, triple_frond, tweedy_browne, valley_forge, valueact, viking, wedgewood, weitz, yacktman

**Funds with value_multiplier: 1000** (raw values are in millions, not thousands):
ako, aquamarine, baupost, duquesne, olstein, triple_frond

---

## stock_index.json

Aggregated ownership data for all stocks across all tracked funds.

**URL:** `https://13fai.com/stock_index.json`

**Schema:**
```json
{
  "stocks": {
    "AAPL": {
      "name": "APPLE INC",
      "cusip": "037833100",
      "ticker": "AAPL",
      "funds": {
        "berkshire": {
          "quarters": {
            "2025Q4": {
              "shares": 300000000,
              "value": 57000000,
              "putcall": ""
            }
          }
        }
      }
    }
  },
  "fund_totals": {
    "berkshire": {
      "2025Q4": 300000000000
    }
  },
  "fund_latest_q": {
    "berkshire": "2025Q4",
    "aquamarine": "2026Q1"
  }
}
```

**Fields:**
- `stocks` — object keyed by ticker symbol
  - `name` — company name as reported in 13F
  - `cusip` — CUSIP identifier
  - `ticker` — resolved ticker symbol
  - `funds` — object keyed by fund_id
    - `quarters` — object keyed by quarter label
      - `shares` — shares held (options excluded from calculations)
      - `value` — value in USD (value_multiplier already applied, in thousands USD)
      - `putcall` — `"Put"`, `"Call"`, or `""` for equity
- `fund_totals` — total long stock value per fund per quarter (USD thousands, options excluded, multiplier applied). Use this to calculate `% of portfolio` for any holding.
- `fund_latest_q` — most recent quarter filed per fund. Use this to determine which funds are current holders vs stale.

**To calculate % of portfolio:**
```
pct = (holding_value / fund_totals[fund_id][quarter]) * 100
```

**To check if a fund is a current holder:**
```
fund_latest_q[fund_id] === quarter
```

---

## cusip_to_ticker.json

Maps CUSIP identifiers to ticker symbols.

**URL:** `https://13fai.com/cusip_to_ticker.json`

**Schema:**
```json
{
  "037833100": "AAPL",
  "025816109": "AXP",
  "57636Q104": "MA"
}
```

~3,177 CUSIPs mapped. Some foreign stocks and less liquid securities may not have a ticker mapping.

---

## prices.json

Last known market price and 52-week range per ticker.

**URL:** `https://13fai.com/prices.json`

**Schema:**
```json
{
  "AAPL": {
    "price": 189.30,
    "week52High": 237.23,
    "week52Low": 164.08,
    "updated": "2026-04-18"
  }
}
```

**Note:** Price fetching is periodically paused. Check `updated` field to confirm data freshness. "Reported price" on fund pages is `value / shares` (implied average at filing date), not this market price.

---

## Important Notes for Developers and AI Agents

**Options handling:** PUT and CALL positions appear in holdings arrays with a non-empty `putcall` field. They are included in the raw data but excluded from all portfolio weight, share count, and period-over-period calculations on the site. Filter them out with `putcall === ""` for equity-only analysis.

**Value units:** All `value` fields in per-fund JSONs are in USD thousands as filed with the SEC, before applying `value_multiplier`. Values in `stock_index.json` `fund_totals` already have the multiplier applied and are in USD thousands.

**Reported price is not a trade price:** The "price at last filing" shown on the site is `(value × multiplier × 1000) / shares`. This is an implied average price as of the quarter end, not an actual purchase or sale price.

**Filing lag:** 13F filings are due 45 days after quarter end. Q1 (Mar 31) → due mid-May. Q2 (Jun 30) → due mid-August. Q3 (Sep 30) → due mid-November. Q4 (Dec 31) → due mid-February. Different funds file at different times within this window.

**Data is for informational purposes only and does not constitute investment advice.**
Source: SEC EDGAR 13F-HR filings (public domain). Site: https://13fai.com
