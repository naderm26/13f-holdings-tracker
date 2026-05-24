#!/usr/bin/env python3
"""
generate_pages.py — generates static manager bio HTML pages from funds_content.json.

Reads:
  - funds_content.json        (bio data, trades, tags, etc.)
  - data/{fund_id}.json       (live holdings — top 5 + AUM + positions + filed date)

Writes:
  - {slug}.html               (one page per manager, in repo root)

Run manually or via GitHub Actions after each quarterly data fetch.
"""

import json
import os
import re
from pathlib import Path

SCRIPT_DIR  = Path(__file__).parent
DATA_DIR    = SCRIPT_DIR / "data"
OUTPUT_DIR  = SCRIPT_DIR          # pages go in repo root
CONTENT_FILE = SCRIPT_DIR / "funds_content.json"
TICKERS_FILE = SCRIPT_DIR / "cusip_to_ticker.json"

PAGES_BASE = ""  # Custom domain — no base path needed

# ── Fund page URL helper — mirrors generate_fund_pages.py slug logic ──────────

FUND_SLUG_OVERRIDES = {
    "pershing":              "pershing-square-13f-holdings",
    "greenlight":            "greenlight-capital-13f-holdings",
    "longleaf":              "longleaf-partners-13f-holdings",
    "sequoia":               "sequoia-fund-13f-holdings",
    "ariel_focus":           "ariel-investments-13f-holdings",
    "mairs_power":           "mairs-and-power-13f-holdings",
    "rv_capital":            "rv-capital-13f-holdings",
    "tci":                   "tci-fund-13f-holdings",
    "daily_journal":         "daily-journal-13f-holdings",
    "situational_awareness": "situational-awareness-13f-holdings",
}

def get_fund_url(fund_id, fund_name):
    """Return the static fund page URL for a given fund_id."""
    if fund_id in FUND_SLUG_OVERRIDES:
        slug = FUND_SLUG_OVERRIDES[fund_id]
    else:
        m = re.match(r"^(.+?)\s*\(", fund_name)
        name = m.group(1).strip() if m else fund_name
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + "-13f-holdings"
    return f"funds/{slug}.html"


# ── Helpers ──────────────────────────────────────────────────────────────────

def fmt_val(v):
    """Format a raw EDGAR value (in dollars) as $XB / $XM."""
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"${v / 1e6:.0f}M"
    return f"${v:,.0f}"

def fmt_date(d):
    if not d:
        return "—"
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    try:
        y, m, day = d.split("-")
        return f"{months[int(m)-1]} {int(day)}, {y}"
    except Exception:
        return d

def fmt_q(q):
    m = re.match(r"(\d{4})Q(\d)", q)
    return f"Q{m.group(2)} {m.group(1)}" if m else q

def badge_class(badge):
    return {"WIN": "win", "LOSS": "loss", "CURRENT": "current"}.get(badge, "current")

def group_by_cusip(holdings):
    """Group holdings rows by CUSIP (fallback: company name), filter zero-share rows."""
    m = {}
    for h in holdings:
        key = h.get("cusip") or h.get("company", "")
        if key in m:
            m[key]["value"]  += h.get("value", 0)
            m[key]["shares"] += h.get("shares", 0)
        else:
            m[key] = dict(h)
    return [v for v in m.values() if v.get("shares", 0) > 0]

def load_fund_data(fund_id, tickers, mult=1):
    """Load per-fund JSON and return live stats + top 5 holdings."""
    path = DATA_DIR / f"{fund_id}.json"
    if not path.exists():
        return None

    with open(path) as f:
        fund_json = json.load(f)

    quarters = sorted(fund_json.get("quarters", {}).keys(), reverse=True)
    if not quarters:
        return None

    latest_q = quarters[0]
    qdata    = fund_json["quarters"][latest_q]

    # Filter equities only (exclude PUT/CALL options) — case-insensitive
    holdings = [
        h for h in qdata.get("holdings", [])
        if h.get("shares", 0) > 0 and h.get("putcall", "").upper() not in ("PUT", "CALL")
    ]
    grouped = group_by_cusip(holdings)

    # Apply value_multiplier (same as fund.html: tv = sum(value) * mult)
    total_val = sum(h["value"] for h in grouped) * mult
    positions = len(grouped)

    # Top 5 by value (use multiplied value for correct ranking)
    top5 = sorted(grouped, key=lambda h: h["value"] * mult, reverse=True)[:5]

    holdings_rows = []
    for i, h in enumerate(top5):
        ticker  = tickers.get(h.get("cusip", ""), "")
        weight  = (h["value"] * mult / total_val * 100) if total_val > 0 else 0
        holdings_rows.append({
            "rank":    i + 1,
            "company": h.get("company", ""),
            "ticker":  ticker,
            "cusip":   h.get("cusip", ""),
            "weight":  weight,
        })

    top_weight = holdings_rows[0]["weight"] if holdings_rows else 100

    return {
        "aum":          fmt_val(total_val),
        "positions":    positions,
        "filed":        fmt_date(qdata.get("filed", "")),
        "quarter_label": fmt_q(latest_q),
        "filed_raw":    qdata.get("filed", ""),
        "top5":         holdings_rows,
        "top_weight":   top_weight,
    }


# ── HTML template ─────────────────────────────────────────────────────────────

def render_trade(trade):
    bc   = badge_class(trade["badge"])
    return f"""      <div class="trade-card">
        <span class="trade-badge {bc}">{trade["badge"]}</span>
        <div class="trade-title">{trade["title"]}</div>
        <div class="trade-desc">{trade["desc"]}</div>
      </div>"""

def render_holding_row(row, top_weight):
    bar_pct = (row["weight"] / top_weight * 100) if top_weight > 0 else 0
    ticker_html = ""
    if row["ticker"]:
        ticker_html = f'<div class="h-ticker"><a href="{PAGES_BASE}/stock.html?ticker={row["ticker"]}" style="color:#2563eb;text-decoration:none;font-family:var(--mono);font-size:0.72rem;">{row["ticker"]}</a></div>'
    return f"""      <div class="holding-row">
        <div class="h-rank">{row["rank"]}</div>
        <div class="h-name">
          <div class="h-company">{row["company"]}</div>
          {ticker_html}
        </div>
        <div class="h-bar-wrap"><div class="h-bar" style="width:{bar_pct:.1f}%"></div></div>
        <div class="h-pct">{row["weight"]:.1f}%</div>
      </div>"""

def render_page(manager, live, all_managers):
    slug         = manager["slug"]
    fund_id      = manager["fund_id"]
    name         = manager["manager_name"]
    fund_name    = manager["fund_name"]
    founded      = manager["fund_founded"]
    style        = manager["style"]
    positions_typical = manager["typical_positions"]
    net_worth    = manager["net_worth"]
    initials     = manager["initials"]
    role         = manager["role"]
    photo        = manager.get("photo", fund_id)  # fallback to fund_id if no photo field
    tags         = manager["tags"]
    primary_tag  = manager.get("primary_tag", tags[0] if tags else "")
    bio          = manager["bio"]
    quote        = manager["philosophy_quote"]
    trades       = manager["notable_trades"]

    # Co-manager cross-link (e.g. Buffett ↔ Abel for Berkshire)
    co_slug = manager.get("co_manager_slug", "")
    co_manager = next((m for m in all_managers if m["slug"] == co_slug), None)
    # Also check if another manager lists this one as co
    if not co_manager:
        co_manager = next((m for m in all_managers if m.get("co_manager_slug") == slug), None)
        if co_manager:
            co_slug = co_manager["slug"]

    # SEO
    title       = f"{name} Portfolio 2025 | {fund_name} 13F Holdings"
    description = f"Track {name}'s latest stock picks and portfolio holdings from {fund_name}'s 13F filings. See what {name} is buying and selling in 2025."
    canonical   = f"https://13fai.com/{slug}.html"

    # Tags HTML
    tags_html = f'<span class="tag accent">{primary_tag}</span>\n'
    for t in tags:
        if t != primary_tag:
            tags_html += f'        <span class="tag">{t}</span>\n'

    # CTA / live data
    if live:
        aum_val   = live["aum"]
        pos_val   = str(live["positions"])
        filed_val = live["filed"]
        q_label   = f"Top 5 Holdings · {live['quarter_label']}"
        filed_label = f"Filed {live['filed']}" if live.get("filed_raw") else ""
        holdings_html = "\n".join(render_holding_row(r, live["top_weight"]) for r in live["top5"])
        if not holdings_html:
            holdings_html = '      <div class="loading-state">No holdings data available.</div>'
    else:
        aum_val   = "—"
        pos_val   = "—"
        filed_val = "—"
        q_label   = "Latest Quarter"
        filed_label = ""
        holdings_html = '      <div class="loading-state">No holdings data available.</div>'

    # Bio paragraphs
    bio_html = "\n".join(f"      <p>{p}</p>" for p in bio)

    # Trades
    trades_html = "\n".join(render_trade(t) for t in trades)

    # Co-manager cross-link HTML
    if co_manager:
        co_name = co_manager["manager_name"]
        co_role = co_manager["role"]
        co_manager_html = f'<div style="margin-top:0.5rem;font-family:var(--mono);font-size:0.72rem;color:var(--muted);">Also see: <a href="{PAGES_BASE}/{co_slug}.html" style="color:#2563eb;text-decoration:none;">{co_name}</a> — {co_role}</div>'
    else:
        co_manager_html = ""

    # Stats strip
    stats_html = f"""    <div class="stats-strip">
      <div class="strip-stat"><div class="s-label">Fund Founded</div><div class="s-value">{founded}</div></div>
      <div class="strip-stat"><div class="s-label">Style</div><div class="s-value">{style}</div></div>
      <div class="strip-stat"><div class="s-label">Typical Positions</div><div class="s-value">{positions_typical}</div></div>
      <div class="strip-stat"><div class="s-label">Net Worth</div><div class="s-value">{net_worth}</div></div>
    </div>"""

    fund_url = get_fund_url(fund_id, fund_name)

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
  <title>{title}</title>
  <meta name="description" content="{description}"/>
  <meta property="og:title" content="{title}"/>
  <meta property="og:description" content="{description}"/>
  <meta property="og:type" content="website"/>
  <link rel="canonical" href="{canonical}"/>
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
    .brand-name {{ font-size: 1.1rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; text-decoration: none; color: var(--text); }}
    .nav-links {{ display: flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }}
    .nav-link {{ font-family: var(--mono); font-size: 0.72rem; color: var(--muted); text-decoration: none; padding: 0.35rem 0.6rem; border-radius: 4px; transition: color 0.15s, background 0.15s; white-space: nowrap; }}
    .nav-link:hover {{ color: var(--accent); background: var(--accent-light); }}
    .nav-link.active {{ color: var(--accent); font-weight: 500; }}
    .header-nav-row {{ margin-top: 0.6rem; border-top: 1px solid var(--border); padding-top: 0.6rem; }}
    @media (min-width: 700px) {{ header {{ padding: 1.5rem 3rem; }} .header-nav-row {{ display: none; }} .desktop-nav {{ display: flex !important; }} }}
    @media (max-width: 699px) {{ .desktop-nav {{ display: none !important; }} }}
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
    .no-results {{ padding: 0.75rem 1rem; font-size: 0.875rem; color: var(--muted); }}
    main {{ padding: 1.5rem 1.25rem 4rem; max-width: 860px; margin: 0 auto; }}
    @media (min-width: 700px) {{ main {{ padding: 2.5rem 3rem; }} }}
    .hero {{ display: flex; align-items: flex-start; gap: 1.25rem; margin-bottom: 1.75rem; flex-wrap: wrap; }}
    .avatar {{ width: 64px; height: 64px; border-radius: 50%; background: var(--accent); display: flex; align-items: center; justify-content: center; font-family: var(--mono); font-size: 1.1rem; font-weight: 500; color: #fff; flex-shrink: 0; border: 2px solid var(--border); overflow: hidden; }}
    .hero-text {{ flex: 1; min-width: 200px; }}
    .hero-text h1 {{ font-size: 1.6rem; font-weight: 500; letter-spacing: 0.01em; margin-bottom: 0.2rem; }}
    .hero-text .role {{ font-family: var(--mono); font-size: 0.78rem; color: var(--muted); margin-bottom: 0.6rem; }}
    .hero-tags {{ display: flex; gap: 0.4rem; flex-wrap: wrap; }}
    .tag {{ font-family: var(--mono); font-size: 0.68rem; padding: 0.2rem 0.55rem; border: 1px solid var(--border); border-radius: 4px; color: var(--muted); letter-spacing: 0.04em; }}
    .tag.accent {{ border-color: var(--accent); color: var(--accent); background: var(--accent-light); }}
    .cta-banner {{ background: var(--accent-light); border: 1px solid var(--accent); border-radius: 6px; padding: 1rem 1.25rem; margin-bottom: 1.75rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem; }}
    .cta-stats {{ display: flex; gap: 2rem; flex-wrap: wrap; }}
    .cta-stat .label {{ font-family: var(--mono); font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--accent); margin-bottom: 0.15rem; }}
    .cta-stat .value {{ font-family: var(--mono); font-size: 1rem; font-weight: 500; color: var(--text); }}
    .cta-btn {{ font-family: var(--mono); font-size: 0.78rem; background: var(--accent); color: #fff; padding: 0.55rem 1rem; border-radius: 4px; text-decoration: none; white-space: nowrap; transition: opacity 0.15s; }}
    .cta-btn:hover {{ opacity: 0.85; }}
    .stats-strip {{ display: flex; gap: 0; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; margin-bottom: 1.75rem; flex-wrap: wrap; }}
    .strip-stat {{ flex: 1; min-width: 130px; padding: 0.85rem 1rem; border-right: 1px solid var(--border); background: var(--surface); }}
    .strip-stat:last-child {{ border-right: none; }}
    .strip-stat .s-label {{ font-family: var(--mono); font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-bottom: 0.25rem; }}
    .strip-stat .s-value {{ font-family: var(--mono); font-size: 0.95rem; font-weight: 500; color: var(--text); }}
    .section-heading {{ font-family: var(--mono); font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--muted); margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }}
    .content-section {{ margin-bottom: 2rem; }}
    .bio-text {{ font-size: 0.925rem; line-height: 1.8; color: var(--text); }}
    .bio-text p + p {{ margin-top: 0.9rem; }}
    blockquote {{ border-left: 3px solid var(--accent); padding: 0.75rem 1.25rem; margin: 0; background: var(--accent-light); border-radius: 0 4px 4px 0; }}
    blockquote p {{ font-size: 0.925rem; line-height: 1.75; color: var(--text); font-style: italic; }}
    blockquote cite {{ display: block; margin-top: 0.5rem; font-family: var(--mono); font-size: 0.7rem; color: var(--muted); font-style: normal; }}
    .trades-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.75rem; }}
    .trade-card {{ border: 1px solid var(--border); border-radius: 6px; padding: 0.9rem 1rem; background: var(--surface); }}
    .trade-badge {{ font-family: var(--mono); font-size: 0.65rem; font-weight: 500; letter-spacing: 0.08em; padding: 0.15rem 0.45rem; border-radius: 3px; display: inline-block; margin-bottom: 0.5rem; }}
    .trade-badge.win {{ background: #dcfce7; color: var(--green); }}
    .trade-badge.loss {{ background: #fee2e2; color: var(--red); }}
    .trade-badge.current {{ background: var(--accent-light); color: var(--accent); }}
    .trade-title {{ font-size: 0.875rem; font-weight: 500; margin-bottom: 0.35rem; }}
    .trade-desc {{ font-size: 0.8rem; line-height: 1.6; color: var(--muted); }}
    .holdings-preview {{ border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }}
    .holdings-header {{ background: var(--surface); padding: 0.6rem 1rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); }}
    .holdings-header span {{ font-family: var(--mono); font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); }}
    .holding-row {{ display: flex; align-items: center; gap: 0.75rem; padding: 0.7rem 1rem; border-bottom: 1px solid var(--border); }}
    .holding-row:last-of-type {{ border-bottom: none; }}
    .h-rank {{ font-family: var(--mono); font-size: 0.75rem; color: var(--muted); width: 1.25rem; flex-shrink: 0; text-align: right; }}
    .h-name {{ flex: 1; }}
    .h-company {{ font-size: 0.875rem; font-weight: 500; }}
    .h-ticker {{ font-family: var(--mono); font-size: 0.72rem; color: #2563eb; }}
    .h-bar-wrap {{ flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }}
    .h-bar {{ height: 100%; background: var(--accent); border-radius: 3px; }}
    .h-pct {{ font-family: var(--mono); font-size: 0.78rem; font-weight: 500; color: var(--accent); min-width: 2.5rem; text-align: right; }}
    .holdings-footer {{ padding: 0.75rem 1rem; border-top: 1px solid var(--border); background: var(--surface); text-align: center; }}
    .holdings-footer a {{ font-family: var(--mono); font-size: 0.75rem; color: var(--accent); text-decoration: none; }}
    .holdings-footer a:hover {{ text-decoration: underline; }}
    .loading-state {{ padding: 1.5rem 1rem; text-align: center; font-family: var(--mono); font-size: 0.8rem; color: var(--muted); }}
    footer {{ text-align: center; padding: 2rem; font-family: var(--mono); font-size: 0.7rem; color: var(--muted); border-top: 1px solid var(--border); margin-top: 2rem; }}
    footer a {{ color: var(--muted); text-decoration: none; }}
    footer a:hover {{ color: var(--accent); }}
  </style>
</head>
<body>

<header>
  <div class="header-top">
    <div style="display:flex; align-items:center; gap:1.75rem;">
      <div style="display:flex; flex-direction:column; gap:0.1rem;">
        <a class="brand-name" href="index.html">13FAI</a>
        <span style="font-family:var(--mono);font-size:0.62rem;color:var(--muted);letter-spacing:0.02em;">ai-powered hedge fund tracker</span>
      </div>
      <nav class="nav-links desktop-nav">
        <a class="nav-link" href="index.html">Funds</a>
        <a class="nav-link active" href="managers.html">Manager Bios</a>
        <a class="nav-link" href="top-holdings.html">Top Holdings</a>
        <a class="nav-link" href="hedge-fund-activity.html">Consensus Buys &amp; Sells</a>
        <a class="nav-link" href="portfolio-overlap.html">Fund Comparison</a>
        <a class="nav-link" href="filing-calendar.html">13F Filing Calendar</a>
        <a class="nav-link" href="../insider-activity.html">Insider Trading</a>
        <a class="nav-link" href="faq.html">FAQ</a>
        <a class="nav-link" href="about.html">About</a>
      </nav>
    </div>
    <div class="search-wrap">
      <span class="search-icon">⌕</span>
      <input type="text" id="search" placeholder="Search funds, managers or stocks..." autocomplete="off"/>
      <div class="search-results" id="search-results"></div>
    </div>
  </div>
  <div class="header-nav-row">
    <nav class="nav-links">
      <a class="nav-link" href="index.html">Funds</a>
      <a class="nav-link active" href="managers.html">Manager Bios</a>
      <a class="nav-link" href="top-holdings.html">Top Holdings</a>
      <a class="nav-link" href="hedge-fund-activity.html">Consensus Buys &amp; Sells</a>
      <a class="nav-link" href="portfolio-overlap.html">Fund Comparison</a>
      <a class="nav-link" href="filing-calendar.html">13F Filing Calendar</a>
      <a class="nav-link" href="../insider-activity.html">Insider Trading</a>
      <a class="nav-link" href="faq.html">FAQ</a>
      <a class="nav-link" href="about.html">About</a>
    </nav>
  </div>
</header>

<main>

  <div class="hero">
    <div class="avatar">
      <img src="{PAGES_BASE}/images/{photo}.jpg" alt="{name}"
           onerror="this.style.display='none';document.getElementById('av-{fund_id}').style.display='flex';"
           style="width:100%;height:100%;object-fit:cover;border-radius:50%;display:block;"/>
      <span id="av-{fund_id}" style="display:none">{initials}</span>
    </div>
    <div class="hero-text">
      <h1>{name}</h1>
      <div class="role">{role} — {fund_name}</div>
      <div class="hero-tags">
        {tags_html}      </div>
      {co_manager_html}
    </div>
  </div>

  <div class="cta-banner">
    <div class="cta-stats">
      <div class="cta-stat"><div class="label">Long Stock Value</div><div class="value">{aum_val}</div></div>
      <div class="cta-stat"><div class="label">Positions</div><div class="value">{pos_val}</div></div>
      <div class="cta-stat"><div class="label">Latest Filing</div><div class="value">{filed_val}</div></div>
    </div>
    <a href="{fund_url}" class="cta-btn">View Full Portfolio →</a>
  </div>

{stats_html}

  <div class="content-section">
    <div class="section-heading">Biography</div>
    <div class="bio-text">
{bio_html}
    </div>
  </div>

  <div class="content-section">
    <div class="section-heading">Investment Philosophy</div>
    <blockquote>
      <p>{quote}</p>
      <cite>— {name}, {fund_name}</cite>
    </blockquote>
  </div>

  <div class="content-section">
    <div class="section-heading">Notable Trades</div>
    <div class="trades-grid">
{trades_html}
    </div>
  </div>

  <div class="content-section">
    <div class="section-heading">Top Holdings — {fund_name}</div>
    <div class="holdings-preview">
      <div class="holdings-header">
        <span>{q_label}</span>
        <span>{filed_label}</span>
      </div>
      <div id="holdings-list">
{holdings_html}
      </div>
      <div class="holdings-footer">
        <a href="{fund_url}">View all positions and full portfolio breakdown →</a>
      </div>
    </div>
  </div>

</main>

<footer>
  Data sourced from SEC EDGAR 13F filings · For informational purposes only ·
  <a href="{PAGES_BASE}/disclaimer.html">Disclaimer</a>
</footer>

<script>
  const PAGES = '{PAGES_BASE}';
  const input = document.getElementById('search');
  const results = document.getElementById('search-results');
  let funds = [], stocks = [];

  Promise.all([
    fetch(PAGES + '/funds.json').then(r => r.json()).catch(() => []),
    fetch(PAGES + '/stock_index.json').then(r => r.json()).catch(() => ({{}}))
  ]).then(([f, si]) => {{
    funds  = Array.isArray(f) ? f : (f.funds || []);
    const s = si.stocks || si;
    stocks = Object.values(s).filter(x => x.ticker).map(x => ({{ ticker: x.ticker, name: x.name }}));
  }});

  input.addEventListener('input', () => {{
    const q = input.value.trim().toLowerCase();
    if (!q) {{ results.classList.remove('visible'); return; }}
    const fr = funds.filter(f => f.name.toLowerCase().includes(q)).slice(0, 4);
    const sr = stocks.filter(s => s.ticker.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)).slice(0, 3);
    const all = [
      ...fr.map(f => `<a class="search-result-item" href="${{PAGES}}/fund.html?fund=${{f.id}}"><span style="font-family:var(--mono);font-size:0.72rem;color:var(--muted);min-width:1.5rem">F</span>${{f.name}}</a>`),
      ...sr.map(s => `<a class="search-result-item" href="${{PAGES}}/stock.html?ticker=${{s.ticker}}"><span style="font-family:var(--mono);font-size:0.72rem;color:#2563eb;min-width:1.5rem">${{s.ticker}}</span>${{s.name}}</a>`)
    ];
    results.innerHTML = all.length ? all.join('') : '<div class="no-results">No results</div>';
    results.classList.add('visible');
  }});
  document.addEventListener('click', e => {{ if (!input.contains(e.target)) results.classList.remove('visible'); }});
</script>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    with open(CONTENT_FILE) as f:
        managers = json.load(f)

    tickers = {}
    if TICKERS_FILE.exists():
        with open(TICKERS_FILE) as f:
            tickers = json.load(f)

    # Load value_multiplier from funds.json — same source as fund.html
    funds_config_path = SCRIPT_DIR / "funds.json"
    mult_map = {}
    if funds_config_path.exists():
        with open(funds_config_path) as f:
            for fund in json.load(f):
                mult_map[fund["id"]] = fund.get("value_multiplier", 1)

    generated = 0
    skipped   = 0

    for manager in managers:
        slug    = manager["slug"]
        fund_id = manager["fund_id"]
        mult    = mult_map.get(fund_id, 1)

        live = load_fund_data(fund_id, tickers, mult)
        if not live:
            print(f"  ⚠️  No data for {fund_id} — generating page with placeholders")
            skipped += 1

        html     = render_page(manager, live, managers)
        out_path = OUTPUT_DIR / f"{slug}.html"

        with open(out_path, "w") as f:
            f.write(html)

        status = "✓" if live else "○"
        aum    = live["aum"] if live else "—"
        print(f"  {status}  {slug}.html  ({aum})")
        generated += 1

    print(f"\n✅  Generated {generated} pages ({skipped} without live data)")


if __name__ == "__main__":
    main()
