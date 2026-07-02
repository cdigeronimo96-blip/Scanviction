# SEO static site — the marketing moat

Streamlit can't be indexed by Google (one JS-rendered route, no per-page URLs/titles/meta). This
generates a **separate, static, indexable site** from your live scan — one page per ticker + one per
signal category + a hub index — that ranks for `[TICKER] stock signals`, `stocks breaking out today`,
etc., and funnels visitors into the app's free signup. This is exactly how StockAnalysis.com (solo,
no VC) reached millions of monthly visits.

## How it works

```
app.py (warm worker, leader)               seo_generate.py (standalone, pure stdlib)
   │ writes on each scan                        │ reads snapshot, emits static HTML
   ▼                                            ▼
.msp_data/universe_snapshot.json  ───────►  seo_site/  →  Cloudflare Pages / Netlify / Vercel
```

- **`seo_export.py`** — the app projects each warm row into a slim, publish-safe snapshot
  (`universe_snapshot.json`). Written automatically (leader-only, `SEO_SNAPSHOT=1` default; set `=0`
  to disable). Same honesty rule as the app: a sub-stat (days-to-cover / insider buys / P/E) is
  written **only when the data is real**.
- **`seo_generate.py`** — reads that JSON and writes `seo_site/`: `index.html`,
  `stocks/<TICKER>.html`, `category/<slug>.html`, `sitemap.xml`, `robots.txt`. Zero app/Streamlit
  import, so it runs in CI/cron/locally.

## 1. Generate locally (MVP — validate ranking fast)

```bash
# after the app has run once and written .msp_data/universe_snapshot.json:
python seo_generate.py \
  --snapshot .msp_data/universe_snapshot.json \
  --out seo_site \
  --site-url https://stocks.marketsignalpro.com \
  --app-url  https://marketsignalpro.streamlit.app
```

Open `seo_site/index.html` in a browser to review. Then **drag-drop the `seo_site/` folder into
[Netlify Drop](https://app.netlify.com/drop)** or `npx wrangler pages deploy seo_site` (Cloudflare
Pages) — both have free tiers. Point a custom domain/subdomain (e.g. `www.` or `stocks.`) at it and
set `--site-url` to that domain so canonicals/sitemap are correct.

## 2. Automate daily (recommended once validated)

The pages should refresh daily (fresh content = better SEO). A GitHub Action:

```yaml
# .github/workflows/seo.yml
name: build-seo
on:
  schedule: [{ cron: "30 22 * * 1-5" }]   # ~after US close, weekdays
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      # Get the latest snapshot (see "Snapshot source" below), then:
      - run: python seo_generate.py --snapshot universe_snapshot.json --out seo_site
             --site-url https://stocks.marketsignalpro.com --app-url https://marketsignalpro.streamlit.app
      - uses: cloudflare/wrangler-action@v3   # or netlify/actions/cli
        with:
          apiToken: ${{ secrets.CF_API_TOKEN }}
          command: pages deploy seo_site --project-name=marketsignalpro-seo
```

**Snapshot source** (pick one — the snapshot lives on the app's server):
- **Simplest:** have the app periodically commit `universe_snapshot.json` to a small repo the Action
  reads, or upload it to object storage (S3/R2) and `curl` it in CI.
- **Or** run the generator on the same host as the app (a cron in your own VPS deployment) and push
  `seo_site/` to the static host from there.

## Notes
- Each page carries the "not financial advice" disclaimer and shows the **same impersonal signals to
  everyone** — this keeps you inside the *Lowe v. SEC* publisher's exclusion (don't personalize).
- Don't publish fabricated performance; the generator never invents sub-stats, and there are no
  "% since" claims on these pages. Keep it that way.
- Start with the full ~2,500 pages, or trim `universe_snapshot.json` to your top N tickers first if
  you want to validate a smaller set before going wide.
