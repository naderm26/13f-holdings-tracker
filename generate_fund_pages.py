#!/usr/bin/env python3
"""
generate_fund_pages.py — generates static 13F holdings pages per fund.

Reads:
  - funds.json          (all fund configs)
  - fund.html           (template — full JS/CSS, just swaps fundId + URLs)

Writes:
  - funds/{slug}-13f-holdings.html   (one page per fund)
  - Updates sitemap.xml to include all fund pages

Run via GitHub Actions after each quarterly data update.
"""

import json
import re
from pathlib import Path

SCRIPT_DIR  = Path(__file__).parent
OUTPUT_DIR  = SCRIPT_DIR / "funds"
FUNDS_JSON  = SCRIPT_DIR / "funds.json"
TEMPLATE    = SCRIPT_DIR / "fund.html"
SITEMAP     = SCRIPT_DIR / "sitemap.xml"

# ── Slug builder ──────────────────────────────────────────────────────────────

def make_slug(fund):
    """Generate URL slug from fund name. e.g. 'Berkshire Hathaway (Warren Buffett)' -> 'berkshire-hathaway-13f-holdings'"""
    SLUG_OVERRIDES = {
        "pershing":             "pershing-square-13f-holdings",
        "greenlight":           "greenlight-capital-13f-holdings",
        "longleaf":             "longleaf-partners-13f-holdings",
        "sequoia":              "sequoia-fund-13f-holdings",
        "ariel_focus":          "ariel-investments-13f-holdings",
        "mairs_power":          "mairs-and-power-13f-holdings",
        "rv_capital":           "rv-capital-13f-holdings",
        "tci":                  "tci-fund-13f-holdings",
        "daily_journal":        "daily-journal-13f-holdings",
        "situational_awareness": "situational-awareness-13f-holdings",
    }
    if fund["id"] in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[fund["id"]]
    # Extract fund name only (before the parenthesis)
    name = re.match(r"^(.+?)\s*\(", fund["name"])
    name = name.group(1).strip() if name else fund["name"]
    # Lowercase, replace non-alphanumeric with hyphens, collapse multiple hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}-13f-holdings"

# ── URL fixups for /funds/ subfolder ─────────────────────────────────────────

def fix_urls(html):
    """Prefix all relative links and fetches with ../ since pages live in /funds/"""
    # Nav and footer hrefs (relative .html files)
    html = re.sub(r'href="(?!http|#|\.\./|//|mailto)([^"]+\.html)"', r'href="../\1"', html)
    # PAGES constant — data fetches need to go up one level
    html = html.replace('const PAGES = "";', 'const PAGES = "..";')
    # Internal stock links built in JS — stock.html and stocks/
    # These are built dynamically in JS strings so they already use PAGES indirectly,
    # but some are hardcoded strings — fix them:
    html = html.replace('href="stock.html?ticker=', 'href="../stock.html?ticker=')
    html = html.replace('href="stock.html?cusip=', 'href="../stock.html?cusip=')
    html = html.replace('href="fund.html?fund=', 'href="../fund.html?fund=')
    html = html.replace("href=\"stock.html?ticker=${ticker || r.cusip}\"", "href=\"../stock.html?ticker=${ticker || r.cusip}\"")
    html = html.replace("href=\"stock.html?cusip=${p.cusip}\"", "href=\"../stock.html?cusip=${p.cusip}\"")
    html = html.replace("href=\"fund.html?fund=${f.id}\"", "href=\"../fund.html?fund=${f.id}\"")
    # stock.html?ticker= in search results (template literal)
    html = html.replace(
        'href="stock.html?ticker=${encodeURIComponent(key)}"',
        'href="../stock.html?ticker=${encodeURIComponent(key)}"'
    )
    # Top holdings internal links: stocks/${ticker}-hedge-fund-ownership.html
    html = html.replace(
        "`stocks/${ticker}-hedge-fund-ownership.html`",
        "`../stocks/${ticker}-hedge-fund-ownership.html`"
    )
    # Bio page links built dynamically: href="${bioSlug}.html" and href="${f.bio_slug}.html"
    # These are template literals so we fix the pattern
    html = html.replace('href="${bioSlug}.html"', 'href="../${bioSlug}.html"')
    html = html.replace("href=\"${f.bio_slug}.html\"", 'href="../${f.bio_slug}.html"')
    # Berkshire hardcoded bio links
    html = html.replace('href="greg-abel-portfolio.html"', 'href="../greg-abel-portfolio.html"')
    html = html.replace('href="warren-buffett-portfolio.html"', 'href="../warren-buffett-portfolio.html"')
    # Avatar image src
    html = html.replace('`${PAGES}/images/${fundId}.jpg`', '`${PAGES}/images/${fundId}.jpg`')  # already uses PAGES, no change needed
    html = html.replace('`${PAGES}/images/berkshire_abel.jpg`', '`${PAGES}/images/berkshire_abel.jpg`')  # same
    return html

# ── Per-fund substitutions ────────────────────────────────────────────────────

def apply_fund(html, fund, slug, canonical_url):
    """Apply fund-specific values to the template."""
    fund_id   = fund["id"]
    name      = fund["name"]
    name_match = re.match(r"^(.+?)\s*\((.+?)\)$", name)
    fund_only    = name_match.group(1).strip() if name_match else name
    manager_only = name_match.group(2).strip() if name_match else name

    # 1. Hardcode fundId — replace the URL param lookup
    html = html.replace(
        'const fundId = params.get("fund") || "pershing";',
        f'const fundId = "{fund_id}";'
    )
    # Remove the params line too since it's unused now
    html = html.replace(
        'const params = new URLSearchParams(window.location.search);\n  const fundId',
        'const fundId'
    )

    # 2. Static title and meta description
    title = f"{fund_only} 13F Holdings | {manager_only} Portfolio | 13FAI"
    desc  = f"Track {manager_only}'s 13F SEC filings and portfolio holdings. See what {fund_only} is buying and selling, position changes, and quarterly portfolio breakdown."
    html = re.sub(r'<title>.*?</title>', f'<title>{title}</title>', html)
    html = re.sub(
        r'<meta name="description" content=".*?"/>',
        f'<meta name="description" content="{desc}"/>',
        html
    )
    html = re.sub(r'<meta property="og:title" content=".*?"/>', f'<meta property="og:title" content="{title}"/>', html)
    html = re.sub(r'<meta property="og:description" content=".*?"/>', f'<meta property="og:description" content="{desc}"/>', html)

    # 3. Static canonical URL (set both the element href and the JS that updates it)
    html = html.replace(
        '<link rel="canonical" href="" id="canonical-url"/>',
        f'<link rel="canonical" href="{canonical_url}" id="canonical-url"/>'
    )
    # Override the JS canonical setter to point to static URL
    html = html.replace(
        f'canonicalEl.setAttribute("href", `https://13fai.com/fund.html?fund=${"{"}fundId{"}"}`);',
        f'canonicalEl.setAttribute("href", "{canonical_url}");'
    )

    # 4. Static JSON-LD (replaces the dynamic JS setter)
    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"{fund_only} 13F Holdings",
        "description": desc,
        "url": canonical_url,
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "isAccessibleForFree": True,
        "creator": {"@type": "Organization", "name": "13FAI", "url": "https://13fai.com"},
        "about": {"@type": "Person", "name": manager_only}
    }, indent=2)
    # Replace the empty script tag with populated JSON-LD
    html = html.replace(
        '<script type="application/ld+json" id="json-ld"></script>',
        f'<script type="application/ld+json" id="json-ld">{json_ld}</script>'
    )

    return html

# ── Sitemap update ────────────────────────────────────────────────────────────

def update_sitemap(slugs):
    if not SITEMAP.exists():
        print("  ⚠️  sitemap.xml not found — skipping sitemap update")
        return

    with open(SITEMAP) as f:
        content = f.read()

    # Remove existing fund page entries
    content = re.sub(r'\s*<!-- Fund pages -->.+?(?=\s*<(?:!--|url))', '', content, flags=re.DOTALL)

    fund_entries = "\n  <!-- Fund pages -->\n"
    for slug in slugs:
        fund_entries += f'  <url><loc>https://13fai.com/funds/{slug}.html</loc><changefreq>quarterly</changefreq><priority>0.9</priority></url>\n'

    content = content.replace("</urlset>", fund_entries + "</urlset>")

    with open(SITEMAP, "w") as f:
        f.write(content)

    print(f"  ✓  sitemap.xml updated with {len(slugs)} fund URLs")

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    with open(FUNDS_JSON) as f:
        funds = json.load(f)

    with open(TEMPLATE) as f:
        template = f.read()

    # Fix all relative URLs for /funds/ subfolder — done once on the template
    template_fixed = fix_urls(template)

    print(f"Generating {len(funds)} fund pages...")
    generated_slugs = []

    for fund in funds:
        fund_id = fund["id"]
        slug    = make_slug(fund)
        canonical_url = f"https://13fai.com/funds/{slug}.html"

        html = apply_fund(template_fixed, fund, slug, canonical_url)

        out_path = OUTPUT_DIR / f"{slug}.html"
        with open(out_path, "w") as f:
            f.write(html)

        generated_slugs.append(slug)
        print(f"  ✓  {slug}.html  ({fund_id})")

    # Clean up stale pages
    generated_set = set(f"{s}.html" for s in generated_slugs)
    stale = [p for p in OUTPUT_DIR.glob("*-13f-holdings.html") if p.name not in generated_set]
    if stale:
        print(f"\nCleaning up {len(stale)} stale pages...")
        for p in stale:
            p.unlink()
            print(f"  🗑  Deleted {p.name}")

    update_sitemap(generated_slugs)
    print(f"\n✅  Generated {len(generated_slugs)} fund pages in /funds/")

if __name__ == "__main__":
    main()
