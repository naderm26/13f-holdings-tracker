"""
generate_insider_pages.py
Generates static per-stock insider trading pages in /insiders/ folder.
Example output: insiders/AAPL-insider-trading.html
"""

import json
import os
from datetime import datetime, timezone

def fmt_val(v):
    if not v:
        return "—"
    abs_v = abs(v)
    if abs_v >= 1e9: return f"${v/1e9:.1f}B"
    if abs_v >= 1e6: return f"${v/1e6:.1f}M"
    if abs_v >= 1e3: return f"${v/1e3:.0f}K"
    return f"${v:,.0f}"

def fmt_shares(n):
    if not n: return "—"
    if n >= 1e6: return f"{n/1e6:.1f}M"
    if n >= 1e3: return f"{n/1e3:.0f}K"
    return f"{n:,}"

def fmt_date(d):
    if not d: return "—"
    try:
        y, m, day = d.split("-")
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        return f"{months[int(m)-1]} {int(day)}, {y}"
    except:
        return d

def build_page(ticker, data):
    company    = data.get("company", ticker)
    cik        = data.get("cik", "")
    updated    = data.get("updated", "")
    txs        = data.get("transactions", [])

    # Aggregate same-day trades per insider before computing stats
    from collections import defaultdict
    agg_map = {}
    for t in txs:
        key = f"{t['insider']}|{t['date']}|{t['code']}"
        if key not in agg_map:
            agg_map[key] = {**t, "shares": 0, "value": 0}
        agg_map[key]["shares"] += t.get("shares", 0)
        agg_map[key]["value"]  += t.get("value", 0)
        agg_map[key]["shares_after"] = t.get("shares_after", agg_map[key].get("shares_after", 0))
    agg_txs = sorted(agg_map.values(), key=lambda x: (x["date"], -x.get("value", 0)), reverse=True)

    buys  = [t for t in agg_txs if t["code"] == "P"]
    sells = [t for t in agg_txs if t["code"] == "S"]

    total_buy_val  = sum(t.get("value", 0) for t in buys)
    total_sell_val = sum(t.get("value", 0) for t in sells)
    net_val        = total_buy_val - total_sell_val
    net_cls        = "green" if net_val >= 0 else "red"
    net_sign       = "+" if net_val >= 0 else ""

    # Insights sentences
    insights = []
    if not agg_txs:
        insights.append(f"No open market insider transactions recorded for {company} ({ticker}) in the last 90 days.")
    else:
        # S1 — summary (uses aggregated counts)
        unique_insiders = len({t["insider"] for t in agg_txs})
        if buys and sells:
            insights.append(
                f"{company} ({ticker}) had {len(buys)} insider purchase{'s' if len(buys)>1 else ''} "
                f"and {len(sells)} insider sale{'s' if len(sells)>1 else ''} "
                f"from {unique_insiders} insider{'s' if unique_insiders>1 else ''} in the last 90 days."
            )
        elif buys:
            insights.append(
                f"{company} ({ticker}) had {len(buys)} insider purchase{'s' if len(buys)>1 else ''} "
                f"from {unique_insiders} insider{'s' if unique_insiders>1 else ''} in the last 90 days — no insider sales recorded."
            )
        else:
            insights.append(
                f"{company} ({ticker}) had {len(sells)} insider sale{'s' if len(sells)>1 else ''} "
                f"from {unique_insiders} insider{'s' if unique_insiders>1 else ''} in the last 90 days — no insider purchases recorded."
            )

        # S2 — biggest buyer
        if buys:
            top_buy = max(buys, key=lambda t: t.get("value", 0))
            insights.append(
                f"The largest insider purchase was by {top_buy['insider']} "
                f"({top_buy.get('title','')}) who bought {fmt_shares(top_buy['shares'])} shares "
                f"worth {fmt_val(top_buy['value'])} on {fmt_date(top_buy['date'])}."
            )

        # S3 — biggest seller
        if sells:
            top_sell = max(sells, key=lambda t: t.get("value", 0))
            insights.append(
                f"The largest insider sale was by {top_sell['insider']} "
                f"({top_sell.get('title','')}) who sold {fmt_shares(top_sell['shares'])} shares "
                f"worth {fmt_val(top_sell['value'])} on {fmt_date(top_sell['date'])}."
            )

        # S4 — net signal
        if buys and sells:
            direction = "net buyers" if net_val >= 0 else "net sellers"
            insights.append(
                f"On balance, insiders were {direction} of {ticker} stock, "
                f"with net {'purchases' if net_val >= 0 else 'sales'} of {fmt_val(abs(net_val))} over the period."
            )

    insights_html = "\n".join(f"<li>{s}</li>" for s in insights)

    # Cross-reference link — only shown if stock exists in stock_index.json
    stock_index_path = "stock_index.json"
    cross_ref_html   = ""
    if os.path.exists(stock_index_path):
        try:
            with open(stock_index_path) as _f:
                _si = json.load(_f)
            _stocks = _si.get("stocks", _si)
            if ticker in _stocks:
                cross_ref_html = f'''  <div class="cross-ref">
    Also see: <a href="../stock.html?ticker={ticker}">hedge fund ownership of {ticker}</a> — which institutional investors hold this stock and how positions are changing.
  </div>''' 
        except Exception:
            pass

    # Build transaction rows
    def tx_row(t, i):
        is_buy = t["code"] == "P"
        badge  = '<span class="badge buy">BUY</span>' if is_buy else '<span class="badge sell">SELL</span>'
        val_cls = "green" if is_buy else "red"
        price_str = f"${t['price']:.2f}" if t.get("price", 0) > 0 else "—"
        return f"""
        <tr>
          <td class="num" style="color:var(--muted);font-size:0.72rem">{i+1}</td>
          <td style="text-align:left">
            <div style="font-weight:500">{t['insider']}</div>
            <div style="font-family:var(--mono);font-size:0.72rem;color:var(--muted)">{t.get('title','')}</div>
          </td>
          <td>{badge}</td>
          <td class="num">{fmt_shares(t.get('shares',0))}</td>
          <td class="num">{price_str}</td>
          <td class="num" style="color:var(--{val_cls})">{fmt_val(t.get('value',0))}</td>
          <td class="num">{fmt_shares(t.get('shares_after',0))}</td>
          <td class="num">{fmt_date(t.get('date',''))}</td>
          <td class="num" style="font-size:0.68rem;color:var(--muted)">{fmt_date(t.get('filed',''))}</td>
        </tr>"""

    # rows_html no longer used — table rendered by JS from TX_DATA
    rows_html = ""  # kept for template compatibility
    import json as _json
    tx_data_json = _json.dumps(txs)

    edgar_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=40"

    page = f"""<!DOCTYPE html>
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
  <title>{company} ({ticker}) Insider Trading — SEC Form 4 Filings | 13FAI</title>
  <meta name="description" content="Track insider buying and selling at {company} ({ticker}). See which executives and directors are trading {ticker} stock, sourced from SEC Form 4 filings."/>
  <link rel="canonical" href="https://13fai.com/insiders/{ticker}-insider-trading.html"/>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet"/>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Dataset",
    "name": "{company} ({ticker}) Insider Trading Activity",
    "description": "SEC Form 4 insider trading transactions for {company} ({ticker}) — open market purchases and sales by officers, directors, and 10% owners.",
    "url": "https://13fai.com/insiders/{ticker}-insider-trading.html",
    "creator": {{"@type": "Organization", "name": "13FAI", "url": "https://13fai.com"}},
    "about": {{"@type": "Corporation", "name": "{company}", "tickerSymbol": "{ticker}"}}
  }}
  </script>
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
    h1 {{ font-size: 1.4rem; font-weight: 500; letter-spacing: 0.02em; margin-bottom: 0.3rem; }}
    .period-line {{ font-family: var(--mono); font-size: 0.75rem; color: var(--muted); margin-bottom: 1rem; }}
    .stats-strip {{ display: flex; gap: 2rem; margin-bottom: 1.25rem; flex-wrap: wrap; }}
    .stat {{ font-family: var(--mono); }}
    .stat-label {{ font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); }}
    .stat-value {{ font-size: 1.1rem; font-weight: 500; margin-top: 0.1rem; }}
    .green {{ color: var(--green); }}
    .red {{ color: var(--red); }}
    .insights-wrap {{ border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 0.9rem 0; margin-bottom: 1.25rem; }}
    .insights {{ font-size: 0.875rem; line-height: 1.75; }}
    .insights ul {{ list-style: none; margin: 0; padding: 0; }}
    .insights li {{ position: relative; padding-left: 1rem; padding-top: 0.15rem; padding-bottom: 0.15rem; }}
    .insights li::before {{ content: "•"; position: absolute; left: 0; color: var(--muted); font-size: 0.75rem; top: 0.22rem; }}
    table {{ width: 100%; min-width: 700px; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; overflow-x: auto; display: block; }}
    .table-wrap {{ overflow-x: auto; }}
    thead tr {{ background: var(--bg); border-bottom: 1px solid var(--border); }}
    th {{ font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 500; color: var(--muted); padding: 0.75rem 0.6rem; text-align: center; white-space: normal; line-height: 1.4; cursor: pointer; user-select: none; }}
    th:hover {{ color: var(--text); }}
    th.left {{ text-align: left; }}
    td {{ padding: 0.75rem 0.6rem; font-size: 0.875rem; border-bottom: 1px solid var(--border); vertical-align: middle; text-align: center; }}
    td.num {{ font-family: var(--mono); font-size: 0.82rem; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: var(--accent-light); }}
    .badge {{ font-family: var(--mono); font-size: 0.65rem; font-weight: 600; letter-spacing: 0.06em; padding: 0.15rem 0.4rem; border-radius: 3px; text-transform: uppercase; }}
    .badge.buy {{ background: #dcfce7; color: var(--green); }}
    .badge.sell {{ background: #fee2e2; color: var(--red); }}
    .breadcrumb {{ font-family: var(--mono); font-size: 0.72rem; color: var(--muted); margin-bottom: 1rem; }}
    .breadcrumb a {{ color: var(--muted); text-decoration: none; }}
    .breadcrumb a:hover {{ color: var(--accent); }}
    .cross-ref {{ background: var(--accent-light); border: 1px solid var(--border); border-radius: 6px; padding: 0.85rem 1rem; margin-bottom: 1.25rem; font-size: 0.875rem; }}
    .cross-ref a {{ color: var(--accent); text-decoration: none; font-weight: 500; }}
    .cross-ref a:hover {{ text-decoration: underline; }}
    footer {{ text-align: center; padding: 2rem; font-family: var(--mono); font-size: 0.7rem; color: var(--muted); border-top: 1px solid var(--border); }}
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
        <a class="nav-link active" href="../insider-activity.html">Insider Trading</a>
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
      <a class="nav-link active" href="../insider-activity.html">Insider Trading</a>
      <a class="nav-link" href="../faq.html">FAQ</a>
      <a class="nav-link" href="../about.html">About</a>
    </nav>
  </div>
</header>

<main>
  <div class="breadcrumb">
    <a href="../insider-activity.html">Insider Trading</a> › {ticker}
  </div>

  <h1>{company} ({ticker}) — Insider Trading</h1>
  <p class="period-line">Open market purchases and sales · Last 90 days · Updated {fmt_date(updated)} · <a href="{edgar_url}" target="_blank" rel="noopener" style="color:var(--muted)">View on EDGAR ↗</a></p>

  <div class="stats-strip">
    <div class="stat"><div class="stat-label">Buys</div><div class="stat-value green">{len(buys)}</div></div>
    <div class="stat"><div class="stat-label">Sells</div><div class="stat-value red">{len(sells)}</div></div>
    <div class="stat"><div class="stat-label">Buy Value</div><div class="stat-value green">{fmt_val(total_buy_val)}</div></div>
    <div class="stat"><div class="stat-label">Sell Value</div><div class="stat-value red">{fmt_val(total_sell_val)}</div></div>
    <div class="stat"><div class="stat-label">Net</div><div class="stat-value {net_cls}">{net_sign}{fmt_val(abs(net_val))}</div></div>
  </div>

  <div class="insights-wrap">
    <div class="insights"><ul>{insights_html}</ul></div>
  </div>

{cross_ref_html}

  <div class="table-wrap">
  <table>
    <thead>
      <tr id="tx-head">
        <th style="width:2.5rem">#</th>
        <th class="left" style="width:25%" onclick="sortTx(0)">Insider</th>
        <th onclick="sortTx(1)">Type</th>
        <th onclick="sortTx(2)">Shares</th>
        <th onclick="sortTx(3)">Price</th>
        <th onclick="sortTx(4)">Value</th>
        <th onclick="sortTx(5)">Owned After</th>
        <th onclick="sortTx(6)">Trade Date</th>
        <th onclick="sortTx(7)">Filed</th>
      </tr>
    </thead>
    <tbody id="tx-body"></tbody>
  </table>
  </div>

  <div style="margin-top:0.75rem; font-family:var(--mono); font-size:0.68rem; color:var(--muted); line-height:1.8;">
    Only open market purchases (P) and sales (S) are shown. Awards, option exercises, and tax withholding transactions are excluded.<br/>
    Source: SEC EDGAR Form 4 filings. For informational purposes only — not investment advice.
  </div>
</main>

<footer>
  For informational purposes only · Not investment advice · <a href="../disclaimer.html">Full Disclaimer</a>
</footer>

<script>
// Transaction data embedded at generation time
const TX_DATA = {tx_data_json};

let txSortCol = 6;   // default: trade date
let txSortAsc = false;

function fmtDate(d) {{
  if (!d) return "—";
  const [y, m, day] = d.split("-");
  const mo = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return mo[parseInt(m)-1] + " " + parseInt(day) + ", " + y;
}}
function fmtShares(n) {{
  if (!n) return "—";
  if (n >= 1e6) return (n/1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n/1e3).toFixed(0) + "K";
  return n.toLocaleString();
}}
function fmtVal(v) {{
  if (!v) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return "$" + (v/1e9).toFixed(1) + "B";
  if (a >= 1e6) return "$" + (v/1e6).toFixed(1) + "M";
  if (a >= 1e3) return "$" + (v/1e3).toFixed(0) + "K";
  return "$" + v.toFixed(0);
}}

function sortTx(col) {{
  if (txSortCol === col) {{ txSortAsc = !txSortAsc; }}
  else {{ txSortCol = col; txSortAsc = col === 0; }}
  renderTx();
}}

function arrow(col) {{
  if (txSortCol !== col) return "";
  return txSortAsc ? " ↑" : " ↓";
}}

function aggregateTx(txs) {{
  // Combine same insider + same date + same code into one row
  const agg = {{}};
  for (const t of txs) {{
    const key = t.insider + "|" + t.date + "|" + t.code;
    if (!agg[key]) {{
      agg[key] = {{ ...t, shares: 0, value: 0 }};
    }}
    agg[key].shares      += t.shares || 0;
    agg[key].value       += t.value  || 0;
    agg[key].shares_after = t.shares_after || agg[key].shares_after;
  }}
  return Object.values(agg);
}}

function renderTx() {{
  const aggData = aggregateTx(TX_DATA);

  const sorted = [...aggData].sort((a, b) => {{
    let av, bv;
    switch (txSortCol) {{
      case 0: av = a.insider.toLowerCase(); bv = b.insider.toLowerCase(); break;
      case 1: av = a.code; bv = b.code; break;
      case 2: av = a.shares || 0; bv = b.shares || 0; break;
      case 3: av = (a.shares > 0 ? a.value / a.shares : 0); bv = (b.shares > 0 ? b.value / b.shares : 0); break;
      case 4: av = a.value || 0; bv = b.value || 0; break;
      case 5: av = a.shares_after || 0; bv = b.shares_after || 0; break;
      case 6: av = a.date || ""; bv = b.date || ""; break;
      case 7: av = a.filed || ""; bv = b.filed || ""; break;
      default: av = 0; bv = 0;
    }}
    if (av < bv) return txSortAsc ? -1 : 1;
    if (av > bv) return txSortAsc ? 1 : -1;
    return 0;
  }});

  // Update header arrows
  const ths = document.querySelectorAll("#tx-head th");
  const labels = ["#", "Insider", "Type", "Shares", "Price", "Value", "Owned After", "Trade Date", "Filed"];
  ths.forEach((th, i) => {{
    if (i === 0) {{ th.textContent = "#"; return; }}
    th.textContent = labels[i] + arrow(i - 1);
  }});

  const tbody = document.getElementById("tx-body");
  if (!sorted.length) {{
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:2rem">No insider transactions in the last 90 days.</td></tr>';
    return;
  }}

  tbody.innerHTML = sorted.map((t, i) => {{
    const isBuy  = t.code === "P";
    const cls    = isBuy ? "buy" : "sell";
    const valCls = isBuy ? "var(--green)" : "var(--red)";
    const price  = t.shares > 0 && t.value > 0 ? "$" + (t.value / t.shares).toFixed(2) : "—";
    return `<tr>
      <td class="num" style="color:var(--muted);font-size:0.72rem">${{i+1}}</td>
      <td style="text-align:left">
        <div style="font-weight:500">${{t.insider}}</div>
        <div style="font-family:var(--mono);font-size:0.72rem;color:var(--muted)">${{t.title || ""}}</div>
      </td>
      <td><span class="badge ${{cls}}">${{isBuy ? "BUY" : "SELL"}}</span></td>
      <td class="num">${{fmtShares(t.shares)}}</td>
      <td class="num">${{price}}</td>
      <td class="num" style="color:${{valCls}}">${{fmtVal(t.value)}}</td>
      <td class="num">${{fmtShares(t.shares_after)}}</td>
      <td class="num">${{fmtDate(t.date)}}</td>
      <td class="num" style="font-size:0.68rem;color:var(--muted)">${{fmtDate(t.filed)}}</td>
    </tr>`;
  }}).join("");
}}

// Initial render
renderTx();
</script>
</body>
</html>"""
    return page


# ── Main ─────────────────────────────────────────────────────────
insiders_dir = "data/insiders"
output_dir   = "insiders"

if not os.path.exists(insiders_dir):
    print("No data/insiders/ directory found. Run fetch_insider_data.py first.")
    exit(0)

os.makedirs(output_dir, exist_ok=True)

files = [f for f in os.listdir(insiders_dir) if f.endswith(".json")]
print(f"Generating {len(files)} insider pages...")

for filename in sorted(files):
    ticker = filename.replace(".json", "")
    with open(os.path.join(insiders_dir, filename)) as f:
        data = json.load(f)
    html     = build_page(ticker, data)
    out_path = os.path.join(output_dir, f"{ticker}-insider-trading.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"  Written: {out_path}")

print(f"\nDone. {len(files)} pages written to /{output_dir}/")
