#!/usr/bin/env python3
"""Standalone SEO static-site generator for MarketSignalPro.

Reads the slim universe snapshot (written by the app via seo_export.write_snapshot) and emits a
directory of static, indexable HTML — one page per ticker + one per signal category + a hub index,
plus sitemap.xml and robots.txt. PURE STDLIB: no Streamlit, no app import, so it runs in CI / cron /
locally. Deploy the output dir to any static host (Cloudflare Pages / Netlify / Vercel).

Why static: Streamlit is a single JS-rendered route with no per-page URLs/titles/meta — Google can't
index it. These pages ARE indexable (unique <title>/description/canonical/OG/JSON-LD) and each links
into the app's signup, so they're both the SEO moat and a free→paid funnel top.

Usage:
    python seo_generate.py --snapshot .msp_data/universe_snapshot.json --out seo_site \
                           --site-url https://www.marketsignalpro.com \
                           --app-url  https://marketsignalpro.streamlit.app
Every arg falls back to an env var (MSP_SEO_SNAPSHOT / SEO_OUT / SEO_SITE_URL / APP_URL) then a default.
"""
import os
import re
import sys
import json
import html
import argparse
from datetime import datetime

BRAND = "MarketSignalPro"
DISCLAIMER = ("Educational information only — not financial, investment, or trading advice. "
              "Signals are algorithmic and may be delayed or wrong. Past performance does not "
              "guarantee future results. Do your own research.")

# Google Search Console "HTML tag" verification token — baked into every page's <head> so
# verification is permanent (survives regenerations). Set via --google-verification or the
# GOOGLE_SITE_VERIFICATION env var (paste just the content value from the meta tag Google gives you).
GOOGLE_VERIFICATION = os.environ.get("GOOGLE_SITE_VERIFICATION", "")


# ── helpers ──────────────────────────────────────────────────────────────────
def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def clean_cat(cat):
    """Category display name without the leading emoji/symbols (keeps letters, digits, & + - / spaces)."""
    return re.sub(r"^[^A-Za-z0-9]+", "", str(cat or "")).strip() or "Signal"


def slugify(s):
    s = clean_cat(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "signal"


def fmt_price(v):
    return f"${v:,.2f}" if isinstance(v, (int, float)) and v else "—"


def fmt_pct(v):
    if not isinstance(v, (int, float)):
        return ""
    arrow = "▲" if v >= 0 else "▼"
    return f"{arrow} {abs(v):.2f}%"


def sub_stat(row):
    """Real sub-stat only (the snapshot already stripped fabricated ones)."""
    if row.get("insider_buys"):
        return f"{int(row['insider_buys'])} open-market insider buys (SEC Form 4)"
    if row.get("dtc"):
        return f"{row['dtc']:.1f} days to cover (short interest)"
    if row.get("pe"):
        return f"P/E {row['pe']:.1f}"
    return ""


# ── shared HTML shell ────────────────────────────────────────────────────────
CSS = """
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:#0a0e1c;color:#e2e8f0;font:15px/1.6 -apple-system,Segoe UI,Roboto,Inter,sans-serif}
a{color:#818cf8;text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:900px;margin:0 auto;padding:20px 18px 60px}
header,footer{border-color:#1c2440}
.top{display:flex;align-items:center;justify-content:space-between;padding:14px 0;border-bottom:1px solid #1c2440}
.brand{font-weight:800;font-size:18px}.brand span{color:#f59e0b}
.cta{background:#4f46e5;color:#fff!important;padding:9px 16px;border-radius:8px;font-weight:700;font-size:13px}
h1{font-size:26px;margin:22px 0 6px}h2{font-size:18px;margin:28px 0 10px;color:#cbd5e1}
.muted{color:#5d6b86;font-size:13px}
.card{background:#0e1530;border:1px solid #1c2440;border-radius:12px;padding:16px 18px;margin:14px 0}
.badge{display:inline-block;background:rgba(99,102,241,.14);border:1px solid rgba(99,102,241,.3);color:#a5b4fc;font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px}
.score{font-family:ui-monospace,Menlo,monospace;font-weight:800}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin:10px 0}
.tile{background:#0e1530;border:1px solid #1c2440;border-radius:9px;padding:10px 12px;font-size:14px}
.tile b{font-family:ui-monospace,Menlo,monospace}
.pill{font-size:11px;color:#5d6b86}
.disc{font-size:11px;color:#5d6b86;border-top:1px solid #1c2440;margin-top:34px;padding-top:16px}
"""


def page(title, description, canonical, body, jsonld=None, site_url="", app_url=""):
    ld = f'<script type="application/ld+json">{json.dumps(jsonld)}</script>' if jsonld else ""
    gv = f'<meta name="google-site-verification" content="{esc(GOOGLE_VERIFICATION)}">' if GOOGLE_VERIFICATION else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{gv}
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary">
<style>{CSS}</style>
{ld}
</head>
<body><div class="wrap">
<header class="top">
  <a class="brand" href="{esc(site_url)}/">Market<span>Signal</span>Pro</a>
  <a class="cta" href="{esc(app_url)}/?utm_source=seo&utm_medium=organic">Get free signals →</a>
</header>
{body}
<div class="disc">{esc(DISCLAIMER)}</div>
</div></body></html>"""


# ── page renderers ───────────────────────────────────────────────────────────
def render_ticker(row, related, date_str, site_url, app_url):
    t = row["t"]
    cat = clean_cat(row.get("cat"))
    conv = row.get("conv", 0)
    direction = "short setup" if row.get("dir") == "short" else "long setup"
    ss = sub_stat(row)
    desc = (f"{t} technical signal ({date_str}): {cat} — conviction {conv}/100, {direction}. "
            f"{row.get('why','')}").strip()
    desc = desc[:157] + "…" if len(desc) > 158 else desc
    canonical = f"{site_url}/stocks/{t}.html"
    price_line = f"{fmt_price(row.get('price'))} <span class='muted'>{fmt_pct(row.get('pct'))}</span>"
    body = f"""
<nav class="muted"><a href="{esc(site_url)}/">Home</a> › <a href="{esc(site_url)}/category/{slugify(row.get('cat'))}.html">{esc(cat)}</a> › {esc(t)}</nav>
<h1>{esc(t)} — Technical Signals &amp; Conviction Score</h1>
<div class="muted">As of {esc(date_str)} · scored from daily bars, SEC filings &amp; short interest</div>
<div class="card">
  <div><span class="badge">{esc(cat)}</span> <span class="pill">{esc(direction)}</span></div>
  <p style="font-size:15px;margin:12px 0 6px">{esc(row.get('why',''))}</p>
  <div class="grid">
    <div class="tile"><div class="pill">Conviction</div><b class="score" style="color:#34d399">{esc(conv)}/100</b></div>
    <div class="tile"><div class="pill">Technical score</div><b class="score">{esc(row.get('sc',0))}/100</b></div>
    <div class="tile"><div class="pill">Price</div><b>{price_line}</b></div>
    {f'<div class="tile"><div class="pill">Signal detail</div><b>{esc(ss)}</b></div>' if ss else ''}
  </div>
  <a class="cta" href="{esc(app_url)}/?utm_source=seo&amp;utm_medium=ticker&amp;utm_content={esc(t)}">See {esc(t)}'s full scorecard →</a>
</div>
"""
    if related:
        tiles = "".join(
            f'<a class="tile" href="{esc(site_url)}/stocks/{esc(r["t"])}.html"><b>{esc(r["t"])}</b> '
            f'<span class="pill">{esc(r.get("conv",0))}</span></a>' for r in related[:12])
        body += f'<h2>More {esc(cat)} signals</h2><div class="grid">{tiles}</div>'
    jsonld = {
        "@context": "https://schema.org", "@type": "WebPage",
        "name": f"{t} Technical Signals & Score", "url": canonical, "dateModified": date_str,
        "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{site_url}/"},
            {"@type": "ListItem", "position": 2, "name": cat, "item": f"{site_url}/category/{slugify(row.get('cat'))}.html"},
            {"@type": "ListItem", "position": 3, "name": t, "item": canonical}]}}
    title = f"{t} Stock Signals & Technical Score ({date_str}) | {BRAND}"
    return page(title, desc, canonical, body, jsonld, site_url, app_url)


def render_category(cat, rows, date_str, site_url, app_url):
    name = clean_cat(cat)
    canonical = f"{site_url}/category/{slugify(cat)}.html"
    desc = (f"{len(rows)} stocks flagged as {name} on {date_str} — ranked by conviction. "
            f"Free daily technical scan of 2,500+ US stocks.")[:158]
    tiles = "".join(
        f'<a class="tile" href="{esc(site_url)}/stocks/{esc(r["t"])}.html"><b>{esc(r["t"])}</b> '
        f'<span class="pill">conv {esc(r.get("conv",0))} · {esc(fmt_price(r.get("price")))}</span></a>'
        for r in rows)
    body = f"""
<nav class="muted"><a href="{esc(site_url)}/">Home</a> › {esc(name)}</nav>
<h1>{esc(name)} — Stocks Flagged Today</h1>
<div class="muted">As of {esc(date_str)} · {len(rows)} tickers · ranked by conviction</div>
<div class="grid">{tiles}</div>
<div class="card"><a class="cta" href="{esc(app_url)}/?utm_source=seo&amp;utm_medium=category&amp;utm_content={esc(slugify(cat))}">Get {esc(name)} alerts free →</a></div>
"""
    jsonld = {"@context": "https://schema.org", "@type": "CollectionPage",
              "name": f"{name} stocks", "url": canonical, "dateModified": date_str}
    return page(f"{name} Stocks Today ({date_str}) | {BRAND}", desc, canonical, body, jsonld, site_url, app_url)


def render_index(rows, cats, date_str, site_url, app_url):
    canonical = f"{site_url}/"
    top = rows[:24]
    top_tiles = "".join(
        f'<a class="tile" href="{esc(site_url)}/stocks/{esc(r["t"])}.html"><b>{esc(r["t"])}</b> '
        f'<span class="pill">{esc(clean_cat(r.get("cat")))} · conv {esc(r.get("conv",0))}</span></a>'
        for r in top)
    cat_links = "".join(
        f'<a class="tile" href="{esc(site_url)}/category/{slugify(c)}.html"><b>{esc(clean_cat(c))}</b> '
        f'<span class="pill">{len(cr)} stocks</span></a>' for c, cr in cats)
    all_links = " · ".join(
        f'<a href="{esc(site_url)}/stocks/{esc(r["t"])}.html">{esc(r["t"])}</a>' for r in rows)
    body = f"""
<section style="text-align:center;padding:24px 0 14px;">
  <div style="font-size:11px;font-weight:800;letter-spacing:2px;text-transform:uppercase;color:#818cf8;">Whole-market signal engine</div>
  <h1 style="font-size:34px;line-height:1.15;margin:12px 0 10px;">Every setup in the market,<br><span style="color:#f59e0b;">ranked by conviction.</span></h1>
  <p style="font-size:15px;color:#94a3b8;max-width:660px;margin:0 auto 18px;line-height:1.6;">We scan ~2,500 U.S. stocks every day and score each one 0&ndash;100 &mdash; momentum, breakouts, short-squeeze setups, insider buying &mdash; so the strongest setups surface first. Check any stock's conviction breakdown and how it's done since we flagged it.</p>
  <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap;">
    <a class="cta" style="padding:13px 22px;font-size:14px;" href="{esc(app_url)}/?utm_source=seo&amp;utm_medium=hero">Start free &rarr;</a>
    <a class="cta" style="padding:13px 22px;font-size:14px;background:#0e1530;border:1px solid #2a3550;" href="#pricing">See plans</a>
  </div>
  <div class="muted" style="margin-top:12px;">&#10003; Free forever &nbsp;&middot;&nbsp; &#10003; No credit card &nbsp;&middot;&nbsp; &#10003; Live market + SEC data</div>
</section>

<h2>How it works</h2>
<div class="grid">
  <div class="tile"><b>1 &middot; Discover</b><div class="pill">Browse ~2,500 stocks ranked by conviction across 23 signal categories.</div></div>
  <div class="tile"><b>2 &middot; Dig in</b><div class="pill">Open any stock for its conviction breakdown + % since we flagged it.</div></div>
  <div class="tile"><b>3 &middot; Get pinged</b><div class="pill">Add to a watchlist and set price alerts so you never miss a move.</div></div>
</div>

<h2 id="pricing">Plans</h2>
<div class="card" style="margin:8px 0 16px;">
  <p style="font-size:14px;color:#cbd5e1;margin:0 0 10px;"><strong>MarketSignalPro</strong> is a subscription
  stock-analytics service &mdash; educational technical signals, stock screening, watchlists, and price/volume alerts.</p>
  <div class="grid">
    <div class="tile"><b>Free</b><div class="pill">Core signals + watchlist</div></div>
    <div class="tile"><b>Premium &mdash; $19/month</b><div class="pill">All 23 signal categories, screener, alerts, unlimited watchlist</div></div>
    <div class="tile"><b>Annual &mdash; $149/year</b><div class="pill">Everything in Premium</div></div>
  </div>
  <p class="muted" style="margin:10px 0 12px;">Cancel anytime &middot; billed securely via Stripe &middot; digital subscription, no physical goods &middot; educational only, not financial advice.</p>
  <a class="cta" href="{esc(app_url)}/?utm_source=seo&amp;utm_medium=home_pricing">Get started &rarr;</a>
</div>

<h2>Today's highest-conviction signals</h2>
<div class="muted" style="margin-bottom:8px;">As of {esc(date_str)} &middot; {len(rows)} US stocks scored from daily bars, SEC filings &amp; short interest</div>
<div class="grid">{top_tiles}</div>
<h2>Browse by signal type</h2><div class="grid">{cat_links}</div>
<h2>All tickers</h2><p style="font-size:13px;line-height:2">{all_links}</p>
"""
    jsonld = {"@context": "https://schema.org", "@type": "WebSite", "name": BRAND,
              "url": site_url, "dateModified": date_str}
    desc = (f"Free daily technical signals on {len(rows)}+ US stocks, each scored 0-100 by conviction - "
            f"momentum, breakouts, short squeeze, insider buying. Updated {date_str}.")[:158]
    return page(f"{BRAND} - Daily Stock Signals, Ranked by Conviction", desc, canonical, body, jsonld, site_url, app_url)


def sitemap(urls):
    items = "".join(f"<url><loc>{esc(u)}</loc></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>'


# ── driver ───────────────────────────────────────────────────────────────────
def generate(snapshot, out, site_url, app_url):
    site_url = site_url.rstrip("/")
    app_url = app_url.rstrip("/")
    with open(snapshot, encoding="utf-8") as f:
        snap = json.load(f)
    rows = snap.get("rows", [])
    date_str = (snap.get("generated_at", "") or "")[:10] or datetime.utcnow().strftime("%Y-%m-%d")
    if not rows:
        print("WARNING: snapshot has 0 rows — nothing to generate (is the universe warm?).")

    # group by category (preserve conviction order within each)
    cats = {}
    for r in rows:
        cats.setdefault(r.get("cat", ""), []).append(r)
    cats_sorted = sorted(cats.items(), key=lambda kv: -len(kv[1]))

    os.makedirs(os.path.join(out, "stocks"), exist_ok=True)
    os.makedirs(os.path.join(out, "category"), exist_ok=True)
    urls = [f"{site_url}/"]

    # index
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_index(rows, cats_sorted, date_str, site_url, app_url))

    # category pages
    for c, cr in cats_sorted:
        with open(os.path.join(out, "category", f"{slugify(c)}.html"), "w", encoding="utf-8") as f:
            f.write(render_category(c, cr, date_str, site_url, app_url))
        urls.append(f"{site_url}/category/{slugify(c)}.html")

    # ticker pages
    for r in rows:
        related = [x for x in cats.get(r.get("cat", ""), []) if x["t"] != r["t"]]
        with open(os.path.join(out, "stocks", f"{r['t']}.html"), "w", encoding="utf-8") as f:
            f.write(render_ticker(r, related, date_str, site_url, app_url))
        urls.append(f"{site_url}/stocks/{r['t']}.html")

    with open(os.path.join(out, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap(urls))
    with open(os.path.join(out, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n")

    print(f"Generated {len(rows)} ticker pages + {len(cats_sorted)} category pages + index/sitemap "
          f"-> {out}/  (as of {date_str})")
    return len(urls)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate the MarketSignalPro SEO static site.")
    ap.add_argument("--snapshot", default=os.environ.get(
        "MSP_SEO_SNAPSHOT", os.path.join(".msp_data", "universe_snapshot.json")))
    ap.add_argument("--out", default=os.environ.get("SEO_OUT", "seo_site"))
    ap.add_argument("--site-url", default=os.environ.get("SEO_SITE_URL", "https://stocks.marketsignalpro.com"))
    ap.add_argument("--app-url", default=os.environ.get("APP_URL", "https://marketsignalpro.streamlit.app"))
    ap.add_argument("--google-verification", default=os.environ.get("GOOGLE_SITE_VERIFICATION", ""),
                    help="Google Search Console HTML-tag content token (baked into every page head)")
    a = ap.parse_args(argv)
    global GOOGLE_VERIFICATION
    if a.google_verification:
        GOOGLE_VERIFICATION = a.google_verification
    if not os.path.exists(a.snapshot):
        print(f"ERROR: snapshot not found: {a.snapshot}\n"
              f"Run the app once so the warm worker writes it, or pass --snapshot.", file=sys.stderr)
        return 2
    generate(a.snapshot, a.out, a.site_url, a.app_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
