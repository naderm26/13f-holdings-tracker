#!/usr/bin/env python3
"""
generate_stock_pages.py — generates static hedge fund ownership pages per stock.

Reads:
  - stock_index.json   (all stock/fund data)
  - funds.json         (fund names, bio slugs)

Writes:
  - {TICKER}-hedge-fund-ownership.html  (one page per stock, in repo root)
  - Updates sitemap.xml to include all stock pages

Top N stocks are selected by aggregate hedge fund value.
Run via GitHub Actions after each quarterly data update.
"""

import json
import re
import math
from pathlib import Path

SCRIPT_DIR   = Path(__file__).parent
OUTPUT_DIR   = SCRIPT_DIR / "stocks"
STOCK_INDEX  = SCRIPT_DIR / "stock_index.json"
FUNDS_JSON   = SCRIPT_DIR / "funds.json"
SITEMAP      = SCRIPT_DIR / "sitemap.xml"

TOP_N = 500  # number of hedge-fund-held stock pages to generate

# Full S&P 500 ticker list — pages generated for these even if no tracked fund holds them
# Update this list when S&P 500 composition changes (~quarterly)
SP500_TICKERS = {
    "AAPL","NVDA","MSFT","GOOGL","GOOG","AMZN","META","TSLA","BRK.B","WMT",
    "LLY","JPM","V","XOM","MA","AVGO","HD","JNJ","COST","PG","ABBV","MRK",
    "CVX","KO","NFLX","AMD","BAC","GE","CSCO","CRM","IBM","LIN","RTX","GS",
    "MS","NOW","TMO","PEP","NEE","ISRG","MCD","T","TXN","CAT","VZ","PM",
    "WFC","DIS","UNH","LOW","GEV","QCOM","ABT","DHR","CB","ACN","HON","SPGI",
    "INTU","ETN","TJX","BLK","SYK","BKNG","PGR","MDT","PLD","ANET","ADI",
    "COP","CME","SCHW","MO","GILD","BMY","HCA","PANW","LRCX","TMUS","NEM",
    "SO","SBUX","CEG","COF","VRTX","DUK","MCK","NOC","AMAT","PH","APH","BA",
    "UBER","DE","WELL","BSX","CMCSA","CRWD","AXP","MCO","MU","ORCL","ADBE",
    "HWM","NRG","EQIX","AMP","MMC","CI","CTAS","USB","PNC","TDG","CARR","EOG",
    "SHW","ZTS","BDX","ICE","AON","EMR","NSC","FCX","FDX","GM","MET","AFL",
    "PCAR","OKE","PSX","CMG","ELV","HLT","FICO","REGN","KLAC","SPG","ECL",
    "EW","GWW","NXPI","ITW","URI","D","ROP","KMB","PSA","ALL","WM","FTNT",
    "AME","MSCI","MDLZ","CCI","MCO","AIG","IDXX","BIIB","TFC","CSGP","EXC",
    "TROW","KEYS","LHX","GIS","A","RSG","PPG","STZ","YUM","HES","SRE","DVN",
    "IQV","ODFL","VRSK","PRU","MCHP","TEL","PWR","ALNY","DAL","EBAY","NUE",
    "MTD","ES","WAT","ROL","MTB","PEG","FANG","BK","FIS","WY","AVB","DLTR",
    "FAST","VMC","RF","GPN","HPE","XEL","DOV","EIX","CF","CTSH","ZBRA","ALB",
    "TTWO","VICI","WST","CAH","MNST","VLTO","RMD","ANSS","CBRE","CDW","LUV",
    "FITB","DFS","DECK","AKAM","EFX","ROK","HBAN","TRGP","TRV","PCG","BAX",
    "ACGL","LDOS","LVS","CINF","ATO","PPL","CNP","WEC","NI","IEX","MPWR",
    "BALL","SWKS","FMC","TER","CE","NTRS","STE","L","BRO","PKG","RL","MHK",
    "POOL","PFG","WRB","CPT","INCY","EXPD","DVA","UDR","NDAQ","TSN","IPG",
    "LKQ","IFF","AES","AIZ","CLX","BIO","HSIC","EMN","FRT","UHS","TAP","BWA",
    "FOXA","FOX","WYNN","CZR","MGM","CCL","RCL","NCLH","AAL","UAL","ALK",
    "HAS","MAT","MOS","HII","CPB","SJM","CAG","HRL","K","MKC","DRI","QSR",
    "DPZ","EAT","TXRH","ULTA","TGT","ROST","DG","BBY","GPC","AAP","AZO",
    "ORLY","KMX","AN","WBA","CVS","HUM","CNC","MOH","HIG","LNC","UNM","IVZ",
    "BEN","STT","ZION","CMA","FHN","SBCF","WTFC","EWBC","NWBI","FULT","PACW",
    "WAL","CBSH","UMBF","FFIN","BOKF","BPOP","GBCI","CVBF",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def fmt_val(v):
    if not v or v == 0: return "—"
    if v >= 1e9: return f"${v/1e9:.2f}B"
    if v >= 1e6: return f"${v/1e6:.1f}M"
    return f"${v:,.0f}"

def fmt_shares(n):
    if not n or n == 0: return "—"
    if n >= 1e9: return f"{n/1e9:.2f}B"
    if n >= 1e6: return f"{n/1e6:.1f}M"
    if n >= 1e3: return f"{n/1e3:.0f}K"
    return str(int(n))

def fmt_pct(v):
    if v is None or math.isnan(v) or v == 0: return "—"
    return f"{v:.2f}%"

def fmt_chg(val):
    if val is None: return '<span class="chg na">—</span>'
    if val == "NEW": return '<span class="chg new">NEW</span>'
    if val == "EXITED": return '<span class="chg exited">EXITED</span>'
    if abs(val) < 0.005: return '<span class="chg na">—</span>'
    sign = "+" if val >= 0 else ""
    cls  = "pos" if val >= 0 else "neg"
    return f'<span class="chg {cls}">{sign}{val:.2f}%</span>'

def smart_round(v):
    r = round(v)
    if r == 0 and abs(v) >= 0.05:
        return f"{v:.1f}"
    return str(r)

def quarter_label(q):
    m = re.match(r"(\d{4})Q(\d)", q)
    return f"Q{m.group(2)} {m.group(1)}" if m else q

def prev_quarter(q):
    yr, qn = q.split("Q")
    pq = int(qn) - 1
    py = int(yr)
    if pq == 0:
        pq = 4
        py -= 1
    return f"{py}Q{pq}"

def prev_year_quarter(q):
    yr, qn = q.split("Q")
    return f"{int(yr)-1}Q{qn}"

def fund_short_name(name):
    m = re.match(r"^(.+?)\s*\(", name)
    return m.group(1).strip() if m else name

def fund_manager(name):
    m = re.match(r"^.+?\s*\((.+?)\)$", name)
    return m.group(1).strip() if m else ""

# ── Build insights (plain text for static pages) ──────────────────────────────

def build_insights(stock, holding_funds, exited_fids, fund_map, fund_totals, selected_q, total_funds):
    ticker     = stock.get("ticker", "")
    name       = stock.get("name", "")
    stock_label = f"{name} ({ticker})" if ticker and ticker != name else name
    short_ticker = ticker or name
    sentences  = []

    prev_q    = prev_quarter(selected_q)
    prev_yr_q = prev_year_quarter(selected_q)

    def fund_link(fid):
        f = fund_map.get(fid)
        if not f: return fid
        return f'<a class="ins-fund" href="../fund.html?fund={fid}">{fund_short_name(f["name"])}</a>'

    # S1: Concentration
    fund_count = len(holding_funds)

    # S&P 500 stocks with no tracked fund holdings — return early with simple message
    if fund_count == 0:
        sentences.append(f"{stock_label} is not currently held by any of the {total_funds} hedge funds tracked on 13FAI.")
        return "<ul>" + "".join(f"<li>{s}</li>" for s in sentences) + "</ul>"

    by_pct = sorted(
        [x for x in holding_funds if fund_totals.get(x["fid"], {}).get(selected_q, 0) > 0],
        key=lambda x: x["latest"]["value"] / fund_totals[x["fid"]][selected_q],
        reverse=True
    )
    top2 = by_pct[:2]
    def fmt_holder(x):
        ft = fund_totals.get(x["fid"], {}).get(selected_q, 0)
        pct = smart_round((x["latest"]["value"] / ft) * 100) if ft > 0 else "0"
        return f'{fund_link(x["fid"])} (<b>{pct}%</b>)'
    hold_str = ""
    if len(top2) == 1:   hold_str = f", with {fmt_holder(top2[0])} holding the largest stake"
    elif len(top2) >= 2: hold_str = f", with {fmt_holder(top2[0])} and {fmt_holder(top2[1])} holding the largest stakes"
    ratio = (fund_count / total_funds * 100) if total_funds > 0 else 0
    tier  = "high" if ratio >= 30 else "elevated" if ratio >= 20 else "moderate" if ratio >= 10 else "limited"
    sentences.append(f"{stock_label} is held by <b>{fund_count}</b> of <b>{total_funds}</b> tracked hedge funds{hold_str}, indicating {tier} hedge fund interest relative to peers.")

    # S2: New positions
    new_pos = []
    for x in holding_funds:
        prev = x.get("prev1")
        if prev and prev.get("shares", 0) > 0: continue
        ft = fund_totals.get(x["fid"], {}).get(selected_q, 0)
        if ft > 0 and (x["latest"]["value"] / ft) * 100 >= 1:
            new_pos.append(x)
    new_pos = sorted(new_pos, key=lambda x: x["latest"]["value"] / (fund_totals.get(x["fid"], {}).get(selected_q, 1)), reverse=True)[:3]
    if new_pos:
        parts = [f'{fund_link(x["fid"])} (<b>{smart_round((x["latest"]["value"] / fund_totals.get(x["fid"], {}).get(selected_q, 1)) * 100)}%</b>)' for x in new_pos]
        joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + ", and " + parts[-1]
        verb = "was initiated" if len(parts) == 1 else "were initiated"
        noun = "New position" if len(parts) == 1 else "New positions"
        sentences.append(f"{noun} in {short_ticker} stock {verb} by {joined}.")

    # S3: Biggest increases
    increases = []
    for x in holding_funds:
        prev = x.get("prev1")
        if not prev or prev.get("shares", 0) == 0 or x["latest"]["shares"] <= prev["shares"]: continue
        delta = x["latest"]["shares"] - prev["shares"]
        price = x["latest"]["value"] / x["latest"]["shares"] if x["latest"]["shares"] > 0 else 0
        increases.append({"fid": x["fid"], "share_pct": (delta / prev["shares"]) * 100, "dollar": delta * price})
    increases = sorted(increases, key=lambda x: x["dollar"], reverse=True)[:2]
    if increases:
        parts = [f'{fund_link(x["fid"])} (<span class="ins-green"><b>+{smart_round(x["share_pct"])}%</b></span>)' for x in increases]
        sentences.append(f'The biggest increases in {short_ticker} holdings came from {" and ".join(parts)}, highlighting conviction.')

    # S4: Biggest decreases
    decreases = []
    for x in holding_funds:
        prev = x.get("prev1")
        if not prev or prev.get("shares", 0) == 0 or x["latest"]["shares"] >= prev["shares"]: continue
        delta = x["latest"]["shares"] - prev["shares"]
        price = x["latest"]["value"] / x["latest"]["shares"] if x["latest"]["shares"] > 0 else prev["value"] / prev["shares"] if prev.get("shares") else 0
        decreases.append({"fid": x["fid"], "share_pct": (delta / prev["shares"]) * 100, "dollar": abs(delta) * price})
    decreases = sorted(decreases, key=lambda x: x["dollar"], reverse=True)[:2]
    if decreases:
        parts = [f'{fund_link(x["fid"])} (<span class="ins-red"><b>{smart_round(x["share_pct"])}%</b></span>)' for x in decreases]
        sentences.append(f'The biggest decreases in {short_ticker} holdings came from {" and ".join(parts)}, suggesting profit-taking or de-risking.')

    # S5: Exits
    if exited_fids:
        exits_sorted = sorted(exited_fids, key=lambda fid: (fund_totals.get(fid, {}).get(prev_q, 0) and
            stock["funds"][fid]["quarters"].get(prev_q, {}).get("value", 0) / fund_totals[fid].get(prev_q, 1)),
            reverse=True)
        notable = [fid for fid in exits_sorted if
            fund_totals.get(fid, {}).get(prev_q, 0) > 0 and
            stock["funds"][fid]["quarters"].get(prev_q, {}).get("value", 0) /
            fund_totals[fid].get(prev_q, 1) * 100 >= 1][:2]
        led_by = ""
        if notable:
            parts = []
            for fid in notable:
                ft  = fund_totals.get(fid, {}).get(prev_q, 0)
                val = stock["funds"][fid]["quarters"].get(prev_q, {}).get("value", 0)
                pct = smart_round((val / ft) * 100) if ft > 0 else "0"
                parts.append(f'{fund_link(fid)} (<b>{pct}%</b>)')
            led_by = f', led by {" and ".join(parts)}'
        n = len(exited_fids)
        sentences.append(f'<b>{n}</b> {"hedge fund" if n == 1 else "hedge funds"} exited {short_ticker}{led_by}.')

    # Net trend
    ns1, pt1, ns4, pt4 = 0, 0, 0, 0
    for x in holding_funds:
        p1 = x.get("prev1")
        p4 = x.get("prev4")
        if p1 and p1.get("shares", 0) > 0: ns1 += x["latest"]["shares"] - p1["shares"]; pt1 += p1["shares"]
        if p4 and p4.get("shares", 0) > 0: ns4 += x["latest"]["shares"] - p4["shares"]; pt4 += p4["shares"]
    for fid in exited_fids:
        p1d = stock["funds"][fid]["quarters"].get(prev_q)
        p4d = stock["funds"][fid]["quarters"].get(prev_yr_q)
        if p1d and p1d.get("shares", 0) > 0: ns1 += -p1d["shares"]; pt1 += p1d["shares"]
        if p4d and p4d.get("shares", 0) > 0: ns4 += -p4d["shares"]; pt4 += p4d["shares"]
    if pt1 > 0:
        p1v = (ns1 / pt1) * 100
        s1  = "+" if p1v >= 0 else ""
        c1  = "var(--green)" if p1v >= 0 else "var(--red)"
        verb = "increased" if p1v >= 0 else "decreased"
        year_str = ""
        if pt4 > 0:
            p4v = (ns4 / pt4) * 100
            s4  = "+" if p4v >= 0 else ""
            c4  = "var(--green)" if p4v >= 0 else "var(--red)"
            year_str = f' and <span style="color:{c4}"><b>{s4}{smart_round(p4v)}%</b></span> vs prior year'
        sentences.append(f'Overall, hedge funds {verb} exposure to {stock_label} by <span style="color:{c1}"><b>{s1}{smart_round(p1v)}%</b></span> vs the prior quarter{year_str}.')

    return "<ul>" + "".join(f"<li>{s}</li>" for s in sentences) + "</ul>"

# ── Build table rows ──────────────────────────────────────────────────────────

def build_table(stock, holding_funds, exited_fids, fund_map, fund_totals, selected_q):
    prev_q    = prev_quarter(selected_q)
    prev_yr_q = prev_year_quarter(selected_q)
    rows = []

    for i, x in enumerate(holding_funds):
        fid    = x["fid"]
        fund   = fund_map.get(fid, {})
        latest = x["latest"]
        prev1  = x.get("prev1")
        prev4  = x.get("prev4")
        fund_name = fund.get("name", fid)
        fund_only = fund_short_name(fund_name)
        manager   = fund_manager(fund_name)
        bio_slug  = fund.get("bio_slug", "")
        manager_html = ""
        if manager:
            if bio_slug:
                manager_html = f'<div class="manager-cell"><a href="../{bio_slug}.html" style="color:#2563eb;text-decoration:none;">{manager}</a></div>'
            else:
                manager_html = f'<div class="manager-cell">{manager}</div>'

        ft  = fund_totals.get(fid, {}).get(selected_q, 0)
        pct = fmt_pct((latest["value"] / ft) * 100) if ft > 0 else "—"

        p1e = prev1 if prev1 and not prev1.get("putcall") else None
        p4e = prev4 if prev4 and not prev4.get("putcall") else None
        if not p1e:
            chg1 = "NEW" if selected_q != "" else None
        elif p1e["shares"] == 0:
            chg1 = "NEW"
        else:
            chg1 = (latest["shares"] - p1e["shares"]) / p1e["shares"] * 100

        chg4 = None
        if p4e:
            chg4 = None if p4e["shares"] == 0 else (latest["shares"] - p4e["shares"]) / p4e["shares"] * 100

        rep_price = latest["value"] / latest["shares"] if latest.get("shares", 0) > 0 else 0
        rep_price_str = f'${rep_price:,.2f}' if rep_price > 0 else "—"
        putcall = latest.get("putcall", "")
        putcall_html = f'<span class="putcall {putcall.lower()}">{putcall}</span>' if putcall else '<span class="chg na">—</span>'

        rows.append(f"""<tr>
          <td class="col-num num" style="color:var(--muted);font-size:0.72rem">{i+1}</td>
          <td class="col-fund"><a class="fund-link" href="../fund.html?fund={fid}">
            <div class="fund-name-cell">{fund_only}</div>{manager_html}
          </a></td>
          <td class="col-data num">{pct}</td>
          <td class="col-data num">{fmt_shares(latest.get("shares",0))}</td>
          <td class="col-data num">{fmt_chg(chg1)}</td>
          <td class="col-data num">{fmt_chg(chg4)}</td>
          <td class="col-data num">{fmt_val(latest.get("value",0))}</td>
          <td class="col-data num">{rep_price_str}</td>
          <td class="col-data num">{putcall_html}</td>
        </tr>""")

    for fid in exited_fids:
        fund = fund_map.get(fid, {})
        fund_name = fund.get("name", fid)
        fund_only = fund_short_name(fund_name)
        manager   = fund_manager(fund_name)
        bio_slug  = fund.get("bio_slug", "")
        manager_html = ""
        if manager:
            if bio_slug:
                manager_html = f'<div class="manager-cell"><a href="../{bio_slug}.html" style="color:#2563eb;text-decoration:none;">{manager}</a></div>'
            else:
                manager_html = f'<div class="manager-cell">{manager}</div>'
        rows.append(f"""<tr class="exited">
          <td class="col-num num" style="font-size:0.72rem">—</td>
          <td class="col-fund"><a class="fund-link" href="../fund.html?fund={fid}">
            <div class="fund-name-cell">{fund_only}</div>{manager_html}
          </a></td>
          <td class="col-data num">—</td><td class="col-data num">—</td>
          <td class="col-data num"><span class="chg exited">EXITED</span></td>
          <td class="col-data num">—</td><td class="col-data num">—</td>
          <td class="col-data num">—</td><td class="col-data num">—</td>
        </tr>""")

    # Total row
    total_shares = sum(x["latest"].get("shares", 0) for x in holding_funds)
    total_value  = sum(x["latest"].get("value", 0) for x in holding_funds)
    ns1, pt1, ns4, pt4 = 0, 0, 0, 0
    for x in holding_funds:
        p1 = x.get("prev1")
        p4 = x.get("prev4")
        if p1 and p1.get("shares", 0) > 0 and not p1.get("putcall"): ns1 += x["latest"]["shares"] - p1["shares"]; pt1 += p1["shares"]
        if p4 and p4.get("shares", 0) > 0 and not p4.get("putcall"): ns4 += x["latest"]["shares"] - p4["shares"]; pt4 += p4["shares"]
    for fid in exited_fids:
        p1d = stock["funds"][fid]["quarters"].get(prev_q)
        p4d = stock["funds"][fid]["quarters"].get(prev_yr_q)
        if p1d and p1d.get("shares", 0) > 0 and not p1d.get("putcall"): ns1 += -p1d["shares"]; pt1 += p1d["shares"]
        if p4d and p4d.get("shares", 0) > 0 and not p4d.get("putcall"): ns4 += -p4d["shares"]; pt4 += p4d["shares"]

    def fmt_total_chg(ns, pt):
        if pt <= 0: return "—"
        v = (ns / pt) * 100
        s = "+" if v >= 0 else ""
        cls = "pos" if v >= 0 else "neg"
        return f'<span class="chg {cls}">{s}{v:.2f}%</span>'

    rows.append(f"""<tr class="total-row">
      <td class="col-num num">{len(holding_funds)}</td>
      <td class="col-fund">Total</td>
      <td class="col-data num">—</td>
      <td class="col-data num">{fmt_shares(total_shares)}</td>
      <td class="col-data num">{fmt_total_chg(ns1,pt1)}</td>
      <td class="col-data num">{fmt_total_chg(ns4,pt4)}</td>
      <td class="col-data num">{fmt_val(total_value)}</td>
      <td class="col-data num">—</td><td class="col-data num">—</td>
    </tr>""")

    return "\n".join(rows)

# ── Full page template ────────────────────────────────────────────────────────

def render_page(stock, holding_funds, exited_fids, fund_map, fund_totals, selected_q, total_funds, safe_ticker=None):
    ticker     = stock.get("ticker", "")
    if safe_ticker is None:
        safe_ticker = ticker.replace("/", "-")
    name       = stock.get("name", "")
    ql         = quarter_label(selected_q)
    title_str  = f"{name} ({ticker}) — Hedge Fund Ownership {ql}" if ticker else f"{name} — Hedge Fund Ownership {ql}"
    description = f"See which hedge funds own {name}{f' ({ticker})' if ticker else ''} as of {ql}. Track position sizes, portfolio weights, and quarterly changes from 13F filings."
    canonical  = f"https://13fai.com/stocks/{safe_ticker}-hedge-fund-ownership.html" if ticker else ""

    insights_html = build_insights(stock, holding_funds, exited_fids, fund_map, fund_totals, selected_q, total_funds)
    table_html    = build_table(stock, holding_funds, exited_fids, fund_map, fund_totals, selected_q)
    fund_count    = len(holding_funds)

    # Quarter tabs (show up to 4)
    all_qs = sorted({q for fd in stock["funds"].values() for q in fd.get("quarters", {}).keys()}, reverse=True)
    tab_qs = all_qs[:4]
    tabs_html = "".join(
        f'<a class="q-btn{" active" if q == selected_q else ""}" href="{safe_ticker}-hedge-fund-ownership.html">{quarter_label(q)}</a>'
        for q in tab_qs
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-2TBN6R2JZC"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-2TBN6R2JZC');
</script>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title_str} | 13FAI</title>
  <meta name="description" content="{description}"/>
  <meta property="og:title" content="{title_str}"/>
  <meta property="og:description" content="{description}"/>
  <meta property="og:type" content="website"/>
  <link rel="canonical" href="{canonical}"/>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet"/>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: #ffffff; --surface: #f0f0f0; --border: #dedede;
      --text: #1a1917; --muted: #8a8780; --accent: #2d5a3d;
      --accent-light: #eef4f0; --green: #2d6a3f; --red: #b91c1c;
      --mono: 'DM Mono', monospace; --sans: 'DM Sans', sans-serif;
    }}
    body {{ background: var(--bg); color: var(--text); font-family: var(--sans); min-height: 100vh; }}
    header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 1rem 1.25rem; }}
    .header-top {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; }}
    .brand {{ display: flex; flex-direction: column; gap: 0.1rem; }}
    .brand-name {{ font-size: 1.1rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; text-decoration: none; color: var(--text); line-height: 1; }}
    .brand-sub {{ font-family: var(--mono); font-size: 0.62rem; color: var(--muted); letter-spacing: 0.02em; }}
    .nav-links {{ display: flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }}
    .nav-link {{ font-family: var(--mono); font-size: 0.72rem; color: var(--muted); text-decoration: none; padding: 0.35rem 0.6rem; border-radius: 4px; transition: color 0.15s, background 0.15s; white-space: nowrap; }}
    .nav-link:hover {{ color: var(--accent); background: var(--accent-light); }}
    .nav-link.active {{ color: var(--accent); font-weight: 500; }}
    .header-nav-row {{ margin-top: 0.6rem; border-top: 1px solid var(--border); padding-top: 0.6rem; }}
    @media (min-width: 700px) {{ header {{ padding: 1.5rem 3rem; }} .header-nav-row {{ display: none; }} .desktop-nav {{ display: flex !important; }} }}
    @media (max-width: 699px) {{ .desktop-nav {{ display: none !important; }} }}
    main {{ padding: 1.5rem 1.25rem 4rem; max-width: 1200px; margin: 0 auto; }}
    @media (min-width: 700px) {{ main {{ padding: 2.5rem 3rem; }} }}
    h1 {{ font-size: 1.4rem; font-weight: 500; margin-bottom: 0.3rem; }}
    .stock-ticker {{ font-family: var(--mono); font-size: 0.85rem; color: #2563eb; font-weight: 600; margin-bottom: 0.75rem; }}
    .quarter-selector {{ display: flex; gap: 0.5rem; margin-bottom: 1.25rem; flex-wrap: wrap; }}
    .q-btn {{ font-family: var(--mono); font-size: 0.72rem; padding: 0.35rem 0.75rem; border: 1px solid var(--border); border-radius: 4px; background: var(--surface); color: var(--muted); text-decoration: none; transition: all 0.15s; display: inline-block; }}
    .q-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
    .q-btn.active {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
    .insights-wrap {{ border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 0.9rem 0; margin-bottom: 1.25rem; }}
    .insights {{ font-size: 0.875rem; line-height: 1.75; color: var(--text); }}
    .insights ul {{ list-style: none; margin: 0; padding: 0; }}
    .insights li {{ position: relative; padding-left: 1rem; padding-top: 0.15rem; padding-bottom: 0.15rem; }}
    .insights li::before {{ content: "•"; position: absolute; left: 0; color: var(--muted); font-size: 0.75rem; top: 0.22rem; }}
    .ins-green {{ color: var(--green); font-weight: 500; }}
    .ins-red   {{ color: var(--red); font-weight: 500; }}
    .ins-fund  {{ color: #2563eb; font-weight: 600; text-decoration: none; }}
    .ins-fund:hover {{ text-decoration: underline; }}
    .table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; border: 1px solid var(--border); border-radius: 6px; }}
    table {{ width: 100%; min-width: 900px; border-collapse: collapse; background: var(--surface); }}
    thead tr {{ background: var(--bg); border-bottom: 1px solid var(--border); }}
    th {{ font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 500; color: var(--muted); padding: 0.75rem 0.6rem; text-align: center; white-space: normal; line-height: 1.4; }}
    th.col-num  {{ width: 2.5rem; min-width: 2.5rem; max-width: 2.5rem; }}
    th.col-fund {{ text-align: left; width: 20%; min-width: 140px; }}
    th.col-data {{ min-width: 80px; text-align: center; }}
    td {{ padding: 0.85rem 0.6rem; font-size: 0.875rem; border-bottom: 1px solid var(--border); vertical-align: middle; white-space: nowrap; text-align: center; }}
    td.col-num  {{ width: 2.5rem; min-width: 2.5rem; max-width: 2.5rem; }}
    td.col-fund {{ text-align: left; white-space: normal; min-width: 140px; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: var(--accent-light); }}
    td.num {{ font-family: var(--mono); font-size: 0.82rem; padding: 0.85rem 0.6rem; text-align: center; }}
    .fund-name-cell {{ font-weight: 500; }}
    .manager-cell {{ font-size: 0.75rem; color: var(--muted); margin-top: 0.1rem; }}
    .fund-link {{ text-decoration: none; color: var(--text); }}
    .fund-link:hover .fund-name-cell {{ color: var(--accent); }}
    .chg {{ font-family: var(--mono); font-size: 0.82rem; font-weight: 500; }}
    .chg.pos {{ color: var(--green); }}
    .chg.neg {{ color: var(--red); }}
    .chg.new {{ color: var(--green); font-size: 0.72rem; letter-spacing: 0.05em; }}
    .chg.exited {{ color: var(--red); font-size: 0.72rem; letter-spacing: 0.05em; }}
    .chg.na {{ color: var(--muted); }}
    .putcall {{ font-family: var(--mono); font-size: 0.72rem; font-weight: 600; letter-spacing: 0.05em; }}
    .putcall.put  {{ color: var(--red); }}
    .putcall.call {{ color: var(--green); }}
    tr.exited td {{ color: var(--muted); background: #f0ede8; }}
    tr.total-row td {{ background: var(--bg); border-top: 2px solid var(--border); font-family: var(--mono); font-size: 0.82rem; }}
    tr.total-row td.col-fund {{ font-family: var(--sans); font-size: 0.875rem; }}
    footer {{ text-align: center; padding: 2rem; font-family: var(--mono); font-size: 0.7rem; color: var(--muted); border-top: 1px solid var(--border); margin-top: 2rem; }}
    footer a {{ color: var(--muted); text-decoration: none; }}
    footer a:hover {{ color: var(--accent); }}
  </style>
</head>
<body>

<header>
  <div class="header-top">
    <div style="display:flex; align-items:center; gap:1.75rem;">
      <div class="brand">
        <a class="brand-name" href="../index.html">13FAI</a>
        <span class="brand-sub">ai-powered hedge fund tracker</span>
      </div>
      <nav class="nav-links desktop-nav">
        <a class="nav-link" href="../index.html">Funds</a>
        <a class="nav-link" href="../managers.html">Manager Bios</a>
        <a class="nav-link" href="../top-holdings.html">Top Holdings</a>
        <a class="nav-link" href="../hedge-fund-activity.html">Consensus Buys &amp; Sells</a>
        <a class="nav-link" href="../portfolio-overlap.html">Fund Comparison</a>
        <a class="nav-link" href="../filing-calendar.html">13F Filing Calendar</a>
        <a class="nav-link" href="../insider-activity.html">Insider Trading</a>
        <a class="nav-link" href="../faq.html">FAQ</a>
        <a class="nav-link" href="../about.html">About</a>
      </nav>
    </div>
  </div>
  <div class="header-nav-row">
    <nav class="nav-links">
      <a class="nav-link" href="../index.html">Funds</a>
      <a class="nav-link" href="../managers.html">Manager Bios</a>
      <a class="nav-link" href="../top-holdings.html">Top Holdings</a>
      <a class="nav-link" href="../hedge-fund-activity.html">Consensus Buys &amp; Sells</a>
      <a class="nav-link" href="../portfolio-overlap.html">Fund Comparison</a>
      <a class="nav-link" href="../filing-calendar.html">13F Filing Calendar</a>
      <a class="nav-link" href="../insider-activity.html">Insider Trading</a>
      <a class="nav-link" href="../faq.html">FAQ</a>
      <a class="nav-link" href="../about.html">About</a>
    </nav>
  </div>
</header>

<main>
  <h1>{title_str}</h1>
  <div class="stock-ticker">{ticker}</div>
  <div class="quarter-selector">{tabs_html}</div>
  <div class="insights-wrap">
    <div class="insights">{insights_html}</div>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th class="col-num" style="color:var(--muted)">#</th>
        <th class="col-fund">Fund</th>
        <th class="col-data num">% of Portfolio †</th>
        <th class="col-data num">Shares †</th>
        <th class="col-data num">Shares vs Prior Quarter †</th>
        <th class="col-data num">Shares vs Prior Year †</th>
        <th class="col-data num">Aggregate Value †</th>
        <th class="col-data num">Reported Price *</th>
        <th class="col-data num">Option</th>
      </tr></thead>
      <tbody>{table_html}</tbody>
    </table>
  </div>
  <div style="font-family:var(--mono);font-size:0.68rem;color:var(--muted);margin-top:0.75rem;line-height:1.8;">
    * Reported price is not an actual purchase or sale price. It is the price as of the last portfolio date.<br/>
    † Portfolio value, share counts, and period-over-period changes exclude options positions (PUT/CALL), which are shown in the Option column for reference only.
  </div>
</main>

<footer>
  For informational purposes only · Not investment advice · <a href="../disclaimer.html">Full Disclaimer</a>
</footer>

</body>
</html>"""

# ── Update sitemap ────────────────────────────────────────────────────────────

def update_sitemap(tickers):
    if not SITEMAP.exists():
        print("  ⚠️  sitemap.xml not found — skipping sitemap update")
        return

    with open(SITEMAP) as f:
        content = f.read()

    # Remove existing stock page entries
    content = re.sub(r'\s*<!-- Stock pages -->.+?(?=\s*</urlset>)', '', content, flags=re.DOTALL)

    # Build new stock entries
    stock_entries = "\n  <!-- Stock pages -->\n"
    for ticker in tickers:
        stock_entries += f"  <url><loc>https://13fai.com/stocks/{ticker}-hedge-fund-ownership.html</loc><changefreq>quarterly</changefreq><priority>0.8</priority></url>\n"

    content = content.replace("</urlset>", stock_entries + "</urlset>")

    with open(SITEMAP, "w") as f:
        f.write(content)

    print(f"  ✓  sitemap.xml updated with {len(tickers)} stock URLs")

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading data...")
    OUTPUT_DIR.mkdir(exist_ok=True)  # create /stocks/ folder if needed
    with open(STOCK_INDEX) as f:
        raw = json.load(f)
    with open(FUNDS_JSON) as f:
        funds_list = json.load(f)

    stock_index = raw.get("stocks", raw)
    fund_totals = raw.get("fund_totals", {})
    fund_latest_q = raw.get("fund_latest_q", {})
    fund_map    = {f["id"]: f for f in funds_list}
    total_funds = len(funds_list)

    # Rank stocks by aggregate hedge fund value (latest quarter only)
    ranked = []
    hedge_fund_tickers = set()
    for key, stock in stock_index.items():
        ticker = stock.get("ticker", "")
        if not ticker or "/" in ticker:
            continue  # skip unmapped or slash tickers
        agg_val = 0
        for fid, fd in stock["funds"].items():
            lq = fund_latest_q.get(fid)
            if lq:
                qd = fd.get("quarters", {}).get(lq)
                if qd and qd.get("shares", 0) > 0 and not qd.get("putcall"):
                    agg_val += qd.get("value", 0)
        if agg_val > 0:
            ranked.append((key, stock, agg_val))
            hedge_fund_tickers.add(ticker)
        else:
            # Stock was held historically but has 0 current holders — skip
            # (still included if it's in SP500_TICKERS via the supplement logic)
            pass

    ranked.sort(key=lambda x: x[2], reverse=True)
    top_stocks = ranked[:TOP_N]

    # Add S&P 500 stocks not already covered by hedge fund holdings
    sp500_only = []
    for ticker in sorted(SP500_TICKERS):
        if "/" in ticker or ticker in hedge_fund_tickers:
            continue  # already covered or invalid
        # Check if ticker exists in stock_index under any key
        stock = None
        for key, s in stock_index.items():
            if s.get("ticker") == ticker:
                stock = (key, s, 0)
                break
        if stock:
            sp500_only.append(stock)
        else:
            # Create a minimal stub for S&P 500 stocks not in index at all
            sp500_only.append((ticker, {
                "ticker": ticker, "name": ticker, "cusip": "", "funds": {}
            }, 0))

    print(f"Generating {len(top_stocks)} hedge-fund stock pages + {len(sp500_only)} S&P 500 supplement pages...")
    all_stocks = top_stocks + sp500_only

    generated_tickers = []

    for rank, (key, stock, _) in enumerate(all_stocks, 1):
        ticker = stock.get("ticker", key)
        print(f"DEBUG rank={rank} ticker={repr(ticker)}")
        if "/" in ticker:
            continue  # skip tickers like BRK/B that would break filenames
        safe_ticker = ticker

        # Determine selected quarter (most common latest quarter across holding funds)
        q_counts = {}
        for fid, fd in stock["funds"].items():
            lq = fund_latest_q.get(fid)
            if lq and fd.get("quarters", {}).get(lq, {}).get("shares", 0) > 0:
                q_counts[lq] = q_counts.get(lq, 0) + 1
        if not q_counts:
            # No current holders — use most recent global quarter
            all_lq = sorted(set(fund_latest_q.values()), reverse=True)
            selected_q = all_lq[0] if all_lq else "2025Q4"
        else:
            selected_q = max(q_counts, key=q_counts.get)
        prev_q     = prev_quarter(selected_q)
        prev_yr_q  = prev_year_quarter(selected_q)

        # Build holding and exited fund lists
        holding_funds = []
        exited_fids   = []

        for fid, fd in stock["funds"].items():
            if fid not in fund_map:
                continue
            qdata  = fd.get("quarters", {})
            latest = qdata.get(selected_q)
            prev1  = qdata.get(prev_q)
            prev4  = qdata.get(prev_yr_q)

            if latest and latest.get("putcall") and latest.get("shares", 0) == 0:
                continue
            if latest and latest.get("shares", 0) > 0:
                holding_funds.append({"fid": fid, "latest": latest, "prev1": prev1, "prev4": prev4})
            elif prev1 and prev1.get("shares", 0) > 0:
                exited_fids.append(fid)

        # Skip stocks with no current holders unless they are in the S&P 500 list
        if not holding_funds and ticker not in SP500_TICKERS:
            continue

        # Sort by portfolio weight descending
        holding_funds.sort(
            key=lambda x: x["latest"]["value"] / fund_totals.get(x["fid"], {}).get(selected_q, 1) if fund_totals.get(x["fid"], {}).get(selected_q, 0) > 0 else 0,
            reverse=True
        )

        # Handle S&P 500 stocks with no hedge fund holdings
        if not holding_funds and not exited_fids:
            selected_q = sorted(fund_latest_q.values())[-1] if fund_latest_q else "2025Q4"

        html = render_page(stock, holding_funds, exited_fids, fund_map, fund_totals, selected_q, total_funds, safe_ticker)
        filename = f"{safe_ticker}-hedge-fund-ownership.html"
        out_path = str(OUTPUT_DIR) + "/" + filename

        with open(out_path, "w") as f:
            f.write(html)

        generated_tickers.append(safe_ticker)
        print(f"  ✓  [{rank:3d}] {filename}")

    update_sitemap(generated_tickers)
    print(f"\n✅  Generated {len(generated_tickers)} stock pages")

if __name__ == "__main__":
    main()
