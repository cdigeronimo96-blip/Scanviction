# Bulk Directional Sentiment — Integration Spec

_Closing the last gap in the composite score: giving the bulk scan a real bull/bear read so the
Sentiment component (up to 15 pts) fires in-scan and the premium **65+ / BUY / Squeeze** tier can
be reached. Written 2026-07 off the forward-return backtest (see `memory/model-backtest-calibration.md`)._

## 1. The problem
`compute_scores()` (scoring.py) awards up to **15 pts** for social/news sentiment, gated on
`sent["bull"]` (direction) and `sent["msgs"]` (volume). In the whole-market scan,
`_poly_bulk_sent()` (app.py) deliberately returns **neutral `bull=50`** — direction costs a
per-ticker news fetch, so it's resolved LAZILY on the detail page (`_raw_sent` → `_hybrid_sent`),
not in the scan. Net: in bulk the Sentiment component contributes only ~**3–6 of its 15** points
(volume, no direction), and the technical core tops out ~64 — so the premium 65+ tier almost never
fires on bulk-scanned names. (Short interest is NOT the gap — it's already bulk-loaded via Polygon
`_poly_short_interest` → `info["dtc"]`, so the Squeeze component works in prod.)

## 2. Key insight — only the *buzz subset* needs direction
The Sentiment component only matters when `msgs >= SENT_MIN_MSGS` (10). ApeWisdom's buzz map yields
only ~**100–400 tickers with meaningful mention volume** out of ~2,500. We do NOT need directional
sentiment for the whole universe — only for the buzzed subset. That turns an impossible
2,500-fetch-per-cycle problem into an easy ~100–200 background-backfill, exactly like the existing
EPS backfill (`_poly_eps_map`, `POLY_PE_BACKFILL=200/warm`, cached 7d, coverage builds over cycles).

## 3. Architecture (mirror the EPS backfill — no new machinery)
```
ApeWisdom buzz map ──► pick top-N by mentions (msgs >= SENT_MIN_MSGS)
                        │
                        ▼  (background, throttled BULK_SENT_BACKFILL/warm, leader-only)
             direction resolver (reuse _news_direction / _yf_news_direction)
                        │  bull%, bear%, article_count
                        ▼
        _POLY_STATE["sent_map"]  (cache BULK_SENT_TTL ~6h)  ──► _poly_bulk_sent() merges it in
                        │                                        (cached bull% if fresh, else 50)
                        ▼
             compute_scores() Sentiment component now fires on buzzed names → sc can reach 65+
```
The resolver ALREADY EXISTS and is battle-tested inside the scan thread pool (`_yf_news_direction`
has the load-bearing hard timeout precisely because it runs there). We just call it for the buzz
subset in the background instead of only on the detail page.

## 4. Provider options (2026)
Direction can come from three sources the app already knows how to use, plus paid upgrades:

| Source | In app today? | Cost | Coverage / quality | Commercial-license? |
|---|---|---|---|---|
| **yfinance news + VADER** (`_yf_news_direction`) | ✅ keyless | **$0** | Yahoo headlines, VADER scoring (crude but OK) | ⚠️ scraping Yahoo — gray for a paid SaaS |
| **Finnhub company-news + VADER** (`_news_direction`) | ✅ (needs key) | Free ~60/min; paid tiers for headroom | Good US news coverage | Free tier = eval; confirm commercial ToS |
| **Alpha Vantage `NEWS_SENTIMENT`** | ➕ new | Free 25 req/day (too thin); Premium ~$50/mo (75/min) | Returns a real **aggregated per-ticker sentiment score** (no VADER needed), 200k+ tickers | ✅ explicit commercial tiers |
| **EODHD sentiment** | ➕ new | ~$20–80/mo tiers | Bulk-friendly news + sentiment | ✅ commercial |
| **Marketaux** | ➕ new | Free (3 articles/req — thin) | Global | ✅ |
| **StockNewsAPI** | ➕ new | Basic 20k calls/mo, Premium 50k/mo | Per-ticker sentiment, well-documented | ✅ |

## 5. Recommendation — phased
- **Phase 1 (ship first, ~$0):** wire the backfill using the EXISTING resolver — Finnhub if
  `FINNHUB_API_KEY` is set (already integrated), else keyless yfinance+VADER. Zero new vendor, zero
  new licensing surface beyond what the detail page already uses. Ship behind `BULK_SENT_ENABLED`.
- **Phase 2 (when monetizing, ~$50/mo):** swap the resolver to **Alpha Vantage `NEWS_SENTIMENT`** —
  it returns a clean aggregated sentiment SCORE per ticker (drop the VADER-on-headlines crudeness),
  has explicit commercial licensing, and one call per ticker fits the buzz-subset budget easily. Keep
  the keyless path as the automatic fallback. (EODHD is the alt if bulk/global coverage matters more
  than the aggregate score.)

Rationale: Phase 1 is a pure code change reusing proven machinery, so it's fast and free to validate;
Phase 2 buys cleaner signal + a clean commercial license once there's revenue — consistent with the
"don't pay for data before you have users" stance in `memory/`.

## 6. Wiring (exact changes)
1. **Config** (app.py, near `POLY_PE_BACKFILL`):
   `BULK_SENT_ENABLED` (default on), `BULK_SENT_BACKFILL` (e.g. 120 tickers/warm),
   `BULK_SENT_TTL` (~21600s), `BULK_SENT_MIN_MSGS` (default = `SENT_MIN_MSGS`).
2. **`_bulk_sent_map(buzz)`** (NEW, mirrors `_poly_eps_map`): pick the top `BULK_SENT_BACKFILL`
   tickers by ApeWisdom mentions with `mentions >= BULK_SENT_MIN_MSGS` and no fresh cache entry;
   resolve each via `_news_direction(t) or _yf_news_direction(t)`; store
   `_POLY_STATE["sent_map"][t] = {"bull":…, "bear":…, "arts":…, "at": now}` (cache `BULK_SENT_TTL`).
   Threaded (reuse the scan's small pool, bounded timeout), leader-only, graceful-empty on failure.
   Called once per warm from `_build_universe_raw_polygon` right after `buzz = _apewisdom_map()`.
3. **`_poly_bulk_sent(ticker, buzz)`** (MODIFY): after building the buzz contract, if
   `_POLY_STATE["sent_map"]` has a fresh entry for the ticker, set `bull`/`bear` from it (else keep
   50/50). One-line merge — everything downstream (`compute_scores`, Social Catalyst fit, conviction
   Sentiment component) already consumes `bull`.
4. Nothing else changes — the score, categories, feed, alerts all read the richer `sent` for free.

## 7. Expected impact
- Buzzed names with real bullish news gain up to **~+9 Sentiment pts** in-scan → the composite can
  clear **65**, so the premium **STRONG BUY / SQUEEZE BUY** tiers fire on bulk-scanned stocks (today
  they only reach it on the detail page after a lazy fetch).
- 🎭 Social Catalyst and the Sentiment component of the Conviction score become directional, not just
  volume-based. Better ranking of catalyst/social names.
- Directly complements the tier recalibration: the 40–64 ACCUMULATE band already works; this lets the
  best of them graduate to a genuine BUY.

## 8. Cost & effort
- **Cost:** Phase 1 = **$0**. Phase 2 = **$0–50/mo** (Finnhub free / Alpha Vantage Premium ~$50).
- **Effort:** Phase 1 ≈ half a day (one new backfill fn + one-line merge + config, mirrors existing
  code). Phase 2 ≈ a new adapter fn + swap the resolver.

## 9. Risks & validation
- **Can't clean-backtest this** — there's no historical bulk sentiment to replay (unlike the price
  backtest). So ship behind `BULK_SENT_ENABLED`, watch: (a) how many names newly clear 65, (b) that
  the new 65+ names aren't garbage (spot-check), (c) rate-limit/timeout health on the resolver.
- **VADER-on-headlines is crude** (Phase 1) — fine as a lean, upgrade to Alpha Vantage's aggregate
  (Phase 2) for real quality. Gate the sentiment contribution conservatively (it already is:
  `SENT_MIN_MSGS` + volume-weighting).
- **Licensing:** the keyless yfinance path is a gray area for a paid product (Yahoo ToS). Phase 2's
  licensed provider removes that. Also confirm the Polygon/Massive plan is a **Business/commercial**
  license before scaling (open item in `memory/data-api-research-2026.md`).
- Rate limits: buzz-subset backfill (~120/warm) is well within Finnhub 60/min and AV Premium 75/min.

## Sources (2026 pricing/coverage)
- Finnhub — news & sentiment, free-tier limits: https://finnhub.io/pricing , https://finnhub.io/docs/api/news-sentiment
- Alpha Vantage `NEWS_SENTIMENT` + free-tier (25/day, 5/min) & premium: https://www.alphavantage.co/documentation/ , https://www.macroption.com/alpha-vantage-api-limits/
- EODHD news+sentiment / 2026 scorecard: https://eodhd.com/financial-apis/stock-market-financial-news-api , https://eodhd.com/financial-academy/financial-faq/the-2026-market-data-api-scorecard-comparing-6-leading-providers
- Tiingo news API + pricing (Power $30/mo, Business $50/mo commercial): https://www.tiingo.com/products/news-api , https://www.tiingo.com/about/pricing
- StockNewsAPI pricing: https://stocknewsapi.com/pricing
- Sentiment-API comparison: https://adanos.org/insights/blog/best-stock-sentiment-apis-2026/
