"""
generate_congress_pages.py
Generates a static HTML trade page for each member in congress_members.json,
reading trade data from data/congress/{member_id}.json.

Usage:
    python generate_congress_pages.py

Output:
    {slug}.html   — one file per member in repo root
"""

import json
from pathlib import Path

MEMBERS_FILE = "congress_members.json"
DATA_DIR     = Path("data/congress")
GA_TAG       = "G-2TBN6R2JZC"

# ── HTML template ─────────────────────────────────────────────────────────────

def render_page(member, trades):
    name      = member["name"]
    slug      = member["slug"]
    party     = member["party"]
    state     = member["state"]
    district  = member["district"]
    chamber   = member["chamber"]
    title_str = member["title"]
    photo     = member.get("photo", f"images/congress/{member['id']}.jpg")

    party_color = "#2563eb" if party == "Democrat" else "#dc2626"

    # Date range from trades
    dates = sorted([t["date_iso"] for t in trades if t.get("date_iso")])
    if dates:
        from_date = next((t["date"] for t in trades if t.get("date_iso") == dates[0]), "")
        to_date   = next((t["date"] for t in sorted(trades, key=lambda x: x.get("date_iso",""), reverse=True) if t.get("date_iso")), "")
        year_range = f"{dates[0][:4]}–{dates[-1][:4]}" if dates[0][:4] != dates[-1][:4] else dates[0][:4]
    else:
        from_date = to_date = year_range = ""

    trades_json = json.dumps(trades)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_TAG}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA_TAG}');
</script>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{name} Stock Trades {year_range} | Congressional Trading | 13FAI</title>
  <meta name="description" content="Track every stock trade {name} has filed under the STOCK Act — purchases, sales, and options {year_range}. Sourced directly from House Periodic Transaction Reports (PTRs)."/>
  <meta name="keywords" content="{name} stock trades, {name} stock portfolio, {name} investments, congressional stock trading, STOCK Act disclosures, House PTR filings"/>
  <meta property="og:title" content="{name} Stock Trades — Congressional Trading | 13FAI"/>
  <meta property="og:description" content="Every stock trade {name} has disclosed under the STOCK Act, sourced directly from House PTR filings."/>
  <meta property="og:type" content="profile"/>
  <meta property="og:url" content="https://13fai.com/{slug}.html"/>
  <meta name="twitter:card" content="summary"/>
  <meta name="twitter:title" content="{name} Stock Trades | 13FAI"/>
  <meta name="twitter:description" content="Every stock trade {name} has disclosed under the STOCK Act."/>
  <link rel="canonical" href="https://13fai.com/{slug}.html"/>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "ProfilePage",
    "name": "{name} Stock Trades",
    "description": "Congressional stock trade disclosures filed by {name} under the STOCK Act.",
    "url": "https://13fai.com/{slug}.html",
    "mainEntity": {{
      "@type": "Person",
      "name": "{name}",
      "jobTitle": "{title_str}",
      "affiliation": {{
        "@type": "Organization",
        "name": "U.S. {chamber} of Representatives"
      }}
    }}
  }}
  </script>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet"/>
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
    main {{ padding: 1.5rem 1.25rem 4rem; max-width: 1100px; margin: 0 auto; }}
    @media (min-width: 700px) {{ main {{ padding: 2.5rem 3rem; }} }}
    .fund-identity {{ margin-bottom: 0.6rem; }}
    .fund-name-row {{ display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.4rem; }}
    .section-label {{ font-size: 1.4rem; letter-spacing: 0.02em; color: var(--text); font-weight: 500; margin-bottom: 0.4rem; }}
    .period-line {{ font-family: var(--mono); font-size: 0.75rem; color: var(--muted); margin-bottom: 0.75rem; }}
    .fund-stats {{ display: flex; gap: 2rem; font-family: var(--mono); flex-shrink: 0; }}
    .fund-stats .stat-label {{ font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); font-weight: 500; }}
    .fund-stats .stat-value {{ font-size: 1.1rem; font-weight: 500; margin-top: 0.1rem; }}
    .quarter-selector {{ display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
    .q-btn {{ font-family: var(--mono); font-size: 0.72rem; padding: 0.35rem 0.75rem; border: 1px solid var(--border); border-radius: 4px; background: var(--surface); color: var(--muted); cursor: pointer; transition: all 0.15s; }}
    .q-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
    .q-btn.active {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
    .insights-wrap {{ border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 0.9rem 0; margin-bottom: 1.25rem; }}
    .insights {{ font-size: 0.875rem; line-height: 1.75; color: var(--text); }}
    .insights ul {{ list-style: none; margin: 0; padding: 0; }}
    .insights li {{ position: relative; padding-left: 1rem; padding-top: 0.15rem; padding-bottom: 0.15rem; }}
    .insights li::before {{ content: "•"; position: absolute; left: 0; color: var(--muted); font-size: 0.75rem; top: 0.22rem; }}
    .ins-green {{ color: var(--green); font-weight: 500; }}
    .ins-red   {{ color: var(--red);   font-weight: 500; }}
    .ins-ticker {{ color: #2563eb; font-weight: 600; font-family: var(--mono); font-size: 0.82rem; text-decoration: none; }}
    .ins-ticker:hover {{ text-decoration: underline; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; min-width: 600px; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; }}
    thead tr {{ background: var(--bg); border-bottom: 1px solid var(--border); }}
    th {{ font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 500; color: var(--muted); padding: 0.75rem 0.6rem; text-align: center; cursor: pointer; user-select: none; white-space: normal; line-height: 1.4; }}
    th.col-asset {{ text-align: left; width: 38%; }}
    th:hover {{ color: var(--text); }}
    td {{ padding: 0.85rem 0.6rem; font-size: 0.875rem; border-bottom: 1px solid var(--border); vertical-align: middle; white-space: nowrap; text-align: center; }}
    td.col-asset {{ text-align: left; white-space: normal; max-width: 260px; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: var(--accent-light); }}
    .company-name {{ font-weight: 500; color: var(--text); white-space: normal; line-height: 1.3; }}
    .cusip {{ font-family: var(--mono); font-size: 0.82rem; font-weight: 600; color: #2563eb; margin-top: 0.15rem; }}
    td.num {{ font-family: var(--mono); font-size: 0.82rem; padding: 0.85rem 0.6rem; text-align: center; }}
    tr.total-row td {{ background: var(--bg); border-top: 2px solid var(--border); font-family: var(--mono); font-size: 0.82rem; }}
    tr.total-row td.col-asset {{ font-family: var(--sans); font-size: 0.875rem; }}
    .tx-badge {{ font-family: var(--mono); font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; padding: 0.2rem 0.5rem; border-radius: 3px; display: inline-block; white-space: nowrap; }}
    .tx-initiated {{ color: var(--green); background: #f0faf2; border: 1px solid #c3e6cb; }}
    .tx-bought    {{ color: var(--green); background: #f0faf2; border: 1px solid #c3e6cb; }}
    .tx-trimmed   {{ color: var(--red);   background: #fff5f5; border: 1px solid #f5c6cb; }}
    .tx-exited    {{ color: var(--red);   background: #fff5f5; border: 1px solid #f5c6cb; }}
    .tx-exchange  {{ color: var(--muted); background: var(--surface); border: 1px solid var(--border); }}
    .fund-avatar {{ width: 48px; height: 48px; border-radius: 50%; background: var(--accent); display: flex; align-items: center; justify-content: center; font-family: var(--mono); font-size: 0.85rem; font-weight: 500; color: #fff; flex-shrink: 0; border: 1px solid var(--border); overflow: hidden; }}
    .fund-avatar img {{ width: 100%; height: 100%; object-fit: cover; border-radius: 50%; }}
    .footnote {{ margin-top: 0.75rem; font-family: var(--mono); font-size: 0.68rem; color: var(--muted); line-height: 1.8; }}
    .search-wrap {{ position: relative; }}
    #search {{ font-family: var(--sans); font-size: 0.875rem; padding: 0.6rem 1rem 0.6rem 2.25rem; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text); width: 200px; outline: none; transition: border 0.15s; }}
    #search:focus {{ border-color: var(--accent); background: var(--surface); }}
    #search::placeholder {{ color: var(--muted); }}
    @media (min-width: 700px) {{ #search {{ width: 280px; }} }}
    .search-icon {{ position: absolute; left: 0.75rem; top: 50%; transform: translateY(-50%); color: var(--muted); font-size: 0.85rem; pointer-events: none; }}
    .search-results {{ position: absolute; top: calc(100% + 4px); left: 0; right: 0; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; overflow: hidden; z-index: 100; box-shadow: 0 4px 16px rgba(0,0,0,0.08); display: none; }}
    .search-results.visible {{ display: block; }}
    .search-result-item {{ display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 1rem; text-decoration: none; color: var(--text); font-size: 0.875rem; border-bottom: 1px solid var(--border); transition: background 0.1s; }}
    .search-result-item:last-child {{ border-bottom: none; }}
    .search-result-item:hover {{ background: var(--accent-light); }}
    .search-result-num {{ font-family: var(--mono); font-size: 0.7rem; color: var(--muted); min-width: 2rem; }}
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
        <a class="brand-name" href="index.html">13FAI</a>
        <span class="brand-sub">ai-powered hedge fund tracker</span>
      </div>
      <nav class="nav-links desktop-nav">
        <a class="nav-link" href="index.html">Funds</a>
        <a class="nav-link" href="managers.html">Manager Bios</a>
        <a class="nav-link" href="top-holdings.html">Top Holdings</a>
        <a class="nav-link" href="hedge-fund-activity.html">Consensus Buys &amp; Sells</a>
        <a class="nav-link" href="portfolio-overlap.html">Fund Comparison</a>
        <a class="nav-link" href="filing-calendar.html">13F Filing Calendar</a>
        <a class="nav-link active" href="congress.html">Congressional Trades</a>
        <a class="nav-link" href="insider-activity.html">Insider Trading</a>
        <a class="nav-link" href="faq.html">FAQ</a>
        <a class="nav-link" href="about.html">About</a>
      </nav>
    </div>
    <div class="search-wrap">
      <span class="search-icon">⌕</span>
      <input type="text" id="search" placeholder="Search funds or stocks..." autocomplete="off"/>
      <div class="search-results" id="search-results"></div>
    </div>
  </div>
  <div class="header-nav-row">
    <nav class="nav-links">
      <a class="nav-link" href="index.html">Funds</a>
      <a class="nav-link" href="managers.html">Manager Bios</a>
      <a class="nav-link" href="top-holdings.html">Top Holdings</a>
      <a class="nav-link" href="hedge-fund-activity.html">Consensus Buys &amp; Sells</a>
      <a class="nav-link" href="portfolio-overlap.html">Fund Comparison</a>
      <a class="nav-link" href="filing-calendar.html">13F Filing Calendar</a>
      <a class="nav-link active" href="congress.html">Congressional Trades</a>
      <a class="nav-link" href="insider-activity.html">Insider Trading</a>
      <a class="nav-link" href="faq.html">FAQ</a>
      <a class="nav-link" href="about.html">About</a>
    </nav>
  </div>
</header>

<main>
  <div class="fund-identity">
    <div class="fund-name-row">
      <div style="display:flex; align-items:center; gap:0.9rem;">
        <div class="fund-avatar">
          <img src="{photo}" alt="{name}"
               onerror="this.style.display='none'; this.parentElement.querySelector('span').style.display='flex';"
               style="display:block;"/>
          <span style="display:none; align-items:center; justify-content:center; width:100%; height:100%;">{initials(name)}</span>
        </div>
        <div>
          <h1 class="section-label">{name}</h1>
          <div style="font-family:var(--mono); font-size:0.78rem; color:var(--muted); margin-top:0.2rem;">
            {title_str} · {district} · <span style="color:{party_color};font-weight:500;">{party}</span>
          </div>
        </div>
      </div>
      <div class="fund-stats">
        <div>
          <div class="stat-label">Trades Shown</div>
          <div class="stat-value" style="color:var(--accent)" id="stat-count">—</div>
        </div>
        <div>
          <div class="stat-label">Period</div>
          <div class="stat-value" id="stat-range" style="font-size:0.9rem;">—</div>
        </div>
      </div>
    </div>
    <div class="quarter-selector" id="year-selector"></div>
  </div>

  <div class="insights-wrap">
    <div class="insights" id="insights"></div>
  </div>

  <div id="table-container"><div style="color:var(--muted); font-family:var(--mono); font-size:0.85rem;">Loading trades...</div></div>

  <div class="footnote">
    * Amount ranges are as reported in the PTR filing. The STOCK Act requires disclosure within 45 days of the transaction.
    Data sourced from <a href="https://disclosures-clerk.house.gov/" target="_blank" rel="noopener" style="color:var(--accent);">disclosures-clerk.house.gov</a>.
    Options activity is included. For informational purposes only — not investment advice.
  </div>
</main>

<footer>
  For informational purposes only · Not investment advice · <a href="disclaimer.html">Full Disclaimer</a>
</footer>

<script>
  const PAGES     = "";
  const MEMBER_NAME = "{name}";
  const ALL_TRADES  = {trades_json};

  let allTrades  = ALL_TRADES;
  let activeYear = "All";
  let sortCol    = 0;
  let sortAsc    = false;

  function toISO(d) {{
    if (!d) return "";
    const p = d.split("/");
    if (p.length !== 3) return d;
    return `${{p[2]}}-${{p[0].padStart(2,"0")}}-${{p[1].padStart(2,"0")}}`;
  }}

  function buildInitiatedSet(trades) {{
    const sorted = [...trades].sort((a,b) => (a.date_iso||"").localeCompare(b.date_iso||""));
    const seen = new Set(), initiated = new Set();
    for (const t of sorted) {{
      if (!t.ticker || t.transaction !== "Purchase") continue;
      if (!seen.has(t.ticker)) {{ initiated.add(`${{t.doc_id}}_${{t.ticker}}_${{t.date}}`); seen.add(t.ticker); }}
    }}
    return initiated;
  }}

  function normaliseTx(raw, isInitiated) {{
    if (!raw) return {{ label: "—", cls: "tx-exchange" }};
    const t = raw.toLowerCase();
    if (t === "purchase") return isInitiated ? {{ label: "Initiated Position", cls: "tx-initiated" }} : {{ label: "Bought More", cls: "tx-bought" }};
    if (t === "s (partial)" || t.includes("s (partial)")) return {{ label: "Trimmed",  cls: "tx-trimmed" }};
    if (t === "s (full)"    || t.includes("s (full)"))    return {{ label: "Exited",    cls: "tx-exited"  }};
    if (t === "sale" || t === "s")                         return {{ label: "Exited",    cls: "tx-exited"  }};
    return {{ label: raw, cls: "tx-exchange" }};
  }}

  function filteredTrades() {{
    return activeYear === "All" ? allTrades : allTrades.filter(t => t.filing_year === activeYear);
  }}

  function init() {{
    const years = [...new Set(allTrades.map(t => t.filing_year))].sort().reverse();
    document.getElementById("year-selector").innerHTML =
      ["All", ...years].map(y =>
        `<button class="q-btn${{y === activeYear ? " active" : ""}}" onclick="setYear('${{y}}')">${{y === "All" ? "All Years" : y}}</button>`
      ).join("");
    renderTable();
  }}

  function setYear(y) {{
    activeYear = y;
    document.querySelectorAll(".q-btn").forEach(b => {{
      b.classList.toggle("active", (b.textContent === "All Years" ? "All" : b.textContent) === y);
    }});
    renderTable();
  }}

  function renderInsights(trades) {{
    const el = document.getElementById("insights");
    if (!el || trades.length === 0) {{ if (el) el.innerHTML = ""; return; }}
    const initiated = buildInitiatedSet(allTrades);
    const sentences = [];
    const allDates  = allTrades.map(t => t.date_iso||"").filter(Boolean).sort();
    const fromDate  = allTrades.find(t => (t.date_iso||"") === allDates[0])?.date || "";
    const toDate    = allTrades.find(t => (t.date_iso||"") === allDates[allDates.length-1])?.date || "";
    const periodLabel = activeYear === "All" ? `from ${{fromDate}} to ${{toDate}}` : `in ${{activeYear}}`;
    const purchases = trades.filter(t => t.transaction === "Purchase");
    const sales     = trades.filter(t => {{ const t2=(t.transaction||"").toLowerCase(); return t2.includes("sale")||t2==="s"||t2.includes("s ("); }});

    // S1 most recent
    const byDate = [...trades].sort((a,b) => (b.date_iso||"").localeCompare(a.date_iso||""));
    if (byDate.length > 0) {{
      const latest = byDate[0];
      const isInit = initiated.has(`${{latest.doc_id}}_${{latest.ticker}}_${{latest.date}}`);
      const tx = normaliseTx(latest.transaction, isInit);
      const isBuy = tx.cls === "tx-initiated" || tx.cls === "tx-bought";
      const ticker = latest.ticker
        ? `<a class="ins-ticker" href="stocks/${{latest.ticker}}-hedge-fund-ownership.html">${{latest.ticker}}</a>`
        : (latest.asset_clean || latest.asset.replace(/\s*\[.*?\]/g,"").split("(")[0].trim());
      sentences.push(`Most recent trade: <span class="${{isBuy?"ins-green":"ins-red"}}">${{tx.label}}</span> ${{ticker}} on ${{latest.date}} (${{latest.amount_range}}).`);
    }}

    // S2 most traded
    const tickerCounts = {{}};
    trades.forEach(t => {{ if (t.ticker) tickerCounts[t.ticker] = (tickerCounts[t.ticker]||0)+1; }});
    const topTickers = Object.entries(tickerCounts).sort((a,b)=>b[1]-a[1]).slice(0,3);
    if (topTickers.length > 0) {{
      const links = topTickers.map(([ticker,count]) =>
        `<a class="ins-ticker" href="stocks/${{ticker}}-hedge-fund-ownership.html">${{ticker}}</a> (${{count}} trade${{count!==1?"s":""}})`
      ).join(", ");
      sentences.push(`Most traded: ${{links}}.`);
    }}

    // S3 largest
    const withAmount = trades.filter(t => t.amount_mid && t.amount_mid < 1e12);
    if (withAmount.length > 0) {{
      const largest = withAmount.reduce((a,b) => a.amount_mid>b.amount_mid?a:b);
      const isInit  = initiated.has(`${{largest.doc_id}}_${{largest.ticker}}_${{largest.date}}`);
      const tx      = normaliseTx(largest.transaction, isInit);
      const isBuy   = tx.cls==="tx-initiated"||tx.cls==="tx-bought";
      const ticker  = largest.ticker
        ? `<a class="ins-ticker" href="stocks/${{largest.ticker}}-hedge-fund-ownership.html">${{largest.ticker}}</a>`
        : (largest.asset_clean||largest.asset.replace(/\s*\[.*?\]/g,"").split("(")[0].trim());
      sentences.push(`Largest reported trade: <span class="${{isBuy?"ins-green":"ins-red"}}">${{tx.label}}</span> ${{ticker}} (${{largest.amount_range}}) on ${{largest.date}}.`);
    }}

    // S4 summary
    sentences.push(
      `${{MEMBER_NAME.split(" ")[1]}} filed <b>${{trades.length}}</b> transaction${{trades.length!==1?"s":""}} ${{periodLabel}} — ` +
      `<span class="ins-green">${{purchases.length}} purchase${{purchases.length!==1?"s":""}}</span> and ` +
      `<span class="ins-red">${{sales.length}} sale${{sales.length!==1?"s":""}}</span>.`
    );

    el.innerHTML = `<ul>${{sentences.map(s=>`<li>${{s}}</li>`).join("")}}</ul>`;
  }}

  function sort(col) {{
    if (sortCol===col) sortAsc=!sortAsc; else {{ sortCol=col; sortAsc=col!==0; }}
    renderTable();
  }}
  function arrow(col) {{ return sortCol!==col?"":sortAsc?" ↑":" ↓"; }}

  function renderTable() {{
    const trades    = filteredTrades();
    const initiated = buildInitiatedSet(allTrades);

    document.getElementById("stat-count").textContent = trades.length;
    if (trades.length > 0) {{
      const dates  = trades.map(t=>t.date_iso||"").filter(Boolean).sort();
      const oldest = trades.find(t=>(t.date_iso||"")===dates[0])?.date||"";
      const newest = trades.find(t=>(t.date_iso||"")===dates[dates.length-1])?.date||"";
      document.getElementById("stat-range").textContent = oldest===newest ? oldest : `${{oldest}} – ${{newest}}`;
    }} else {{ document.getElementById("stat-range").textContent = "—"; }}

    renderInsights(trades);

    if (trades.length === 0) {{
      document.getElementById("table-container").innerHTML =
        `<div style="color:var(--muted);font-family:var(--mono);font-size:0.85rem;padding:1rem 0;">No trades found for this period.</div>`;
      return;
    }}

    const sorted = [...trades].sort((a,b) => {{
      let av, bv;
      if      (sortCol===0) {{ av=a.date_iso||""; bv=b.date_iso||""; }}
      else if (sortCol===1) {{ av=(a.asset_clean||"").toLowerCase(); bv=(b.asset_clean||"").toLowerCase(); }}
      else if (sortCol===2) {{ av=a.transaction||""; bv=b.transaction||""; }}
      else if (sortCol===3) {{ av=a.amount_mid||0; bv=b.amount_mid||0; }}
      return sortAsc ? (av<bv?-1:av>bv?1:0) : (av>bv?-1:av<bv?1:0);
    }});

    const rowsHtml = sorted.map(t => {{
      const clean     = t.asset_clean || t.asset;
      const atype     = t.asset_type  || "";
      const ticker    = t.ticker;
      const stockHref = ticker ? `stocks/${{ticker}}-hedge-fund-ownership.html` : null;
      const isInit    = initiated.has(`${{t.doc_id}}_${{t.ticker}}_${{t.date}}`);
      const tx        = normaliseTx(t.transaction, isInit);
      const assetCell = `
        <div class="company-name">${{stockHref?`<a href="${{stockHref}}" style="color:var(--text);text-decoration:none;">${{clean}}</a>`:clean}}</div>
        ${{ticker?`<div class="cusip"><a href="${{stockHref}}" style="color:#2563eb;text-decoration:none;">${{ticker}}</a>${{atype?` · <span style="color:var(--muted);font-family:var(--mono);font-size:0.72rem;">${{atype}}</span>`:""}}</div>`:(atype?`<div class="cusip" style="color:var(--muted);">${{atype}}</div>`:"")}}`;
      return `<tr><td class="col-asset">${{assetCell}}</td><td class="num"><span class="tx-badge ${{tx.cls}}">${{tx.label}}</span></td><td class="num">${{t.date||"—"}}</td><td class="num">${{(t.amount_range||"—").replace(/\\n/g," ")}}</td></tr>`;
    }}).join("");

    const allDates   = allTrades.map(t=>t.date_iso||"").filter(Boolean).sort();
    const fromDate   = allTrades.find(t=>(t.date_iso||"")===allDates[0])?.date||"";
    const toDate     = allTrades.find(t=>(t.date_iso||"")===allDates[allDates.length-1])?.date||"";
    const tableTitle = activeYear==="All"
      ? `${{MEMBER_NAME}}'s stock trades — ${{fromDate}} to ${{toDate}}`
      : `${{MEMBER_NAME}}'s stock trades — ${{activeYear}}`;

    const purchases = trades.filter(t=>t.transaction==="Purchase").length;
    const sales     = trades.filter(t=>{{const t2=(t.transaction||"").toLowerCase();return t2.includes("sale")||t2==="s"||t2.includes("s (");}}).length;
    const totalRow  = `<tr class="total-row"><td class="col-asset">Total · ${{purchases}} purchase${{purchases!==1?"s":""}}, ${{sales}} sale${{sales!==1?"s":""}}</td><td class="num">${{trades.length}}</td><td class="num">—</td><td class="num">—</td></tr>`;

    document.getElementById("table-container").innerHTML = `
      <div class="period-line" style="margin-bottom:0.5rem">${{tableTitle}}</div>
      <div class="table-wrap"><table>
        <thead><tr>
          <th class="col-asset" onclick="sort(1)">Asset${{arrow(1)}}</th>
          <th onclick="sort(2)">Action${{arrow(2)}}</th>
          <th onclick="sort(0)">Trade Date${{arrow(0)}}</th>
          <th onclick="sort(3)">Amount Range *${{arrow(3)}}</th>
        </tr></thead>
        <tbody>${{rowsHtml}}${{totalRow}}</tbody>
      </table></div>`;
  }}

  // Search
  let allFundsForSearch = [], stockIndexForSearch = {{}};
  fetch(`${{PAGES}}/funds.json`).then(r=>r.json()).then(d=>{{allFundsForSearch=d;}}).catch(()=>{{}});
  fetch(`${{PAGES}}/stock_index.json`).then(r=>r.json()).then(d=>{{stockIndexForSearch=d.stocks||d;}}).catch(()=>{{}});
  const searchInput=document.getElementById("search"), searchResults=document.getElementById("search-results");
  searchInput.addEventListener("input",()=>{{
    const q=searchInput.value.trim().toLowerCase();
    if(!q){{searchResults.classList.remove("visible");return;}}
    const fm=allFundsForSearch.filter(f=>f.name.toLowerCase().includes(q)).slice(0,4)
      .map(f=>`<a class="search-result-item" href="fund.html?fund=${{f.id}}"><span class="search-result-num">Fund</span><span>${{f.name}}</span></a>`);
    const sm=[];
    for(const[key,stock] of Object.entries(stockIndexForSearch)){{
      if(sm.length>=4)break;
      if((stock.ticker&&stock.ticker.toLowerCase().includes(q))||(stock.name&&stock.name.toLowerCase().includes(q)))
        sm.push(`<a class="search-result-item" href="stock.html?ticker=${{encodeURIComponent(key)}}"><span class="search-result-num">Stock</span><span>${{stock.name}}${{stock.ticker?` <span style="color:#2563eb;font-weight:600">${{stock.ticker}}</span>`:""}}</span></a>`);
    }}
    const all=[...fm,...sm];
    searchResults.innerHTML=all.length?all.join(""):`<div style="padding:0.75rem 1rem;font-size:0.875rem;color:var(--muted);">No results found</div>`;
    searchResults.classList.add("visible");
  }});
  document.addEventListener("click",e=>{{if(!searchInput.contains(e.target)&&!searchResults.contains(e.target))searchResults.classList.remove("visible");}});

  init();
</script>
</body>
</html>"""
    return html


def initials(name):
    parts = name.split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    with open(MEMBERS_FILE) as f:
        members = json.load(f)

    generated = []
    for member in members:
        data_path = DATA_DIR / f"{member['id']}.json"
        if not data_path.exists():
            print(f"Skipping {member['name']} — no data file at {data_path}")
            continue

        with open(data_path) as f:
            data = json.load(f)

        trades = data.get("trades", [])
        print(f"Generating {member['slug']}.html — {len(trades)} trades")

        html = render_page(member, trades)

        out_path = Path(f"{member['slug']}.html")
        out_path.write_text(html, encoding="utf-8")
        generated.append(str(out_path))

    print(f"\nDone. Generated {len(generated)} page(s):")
    for p in generated:
        print(f"  {p}")


if __name__ == "__main__":
    main()
