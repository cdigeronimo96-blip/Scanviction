# MarketSignalPro — Project Status Snapshot
**Saved: 2026-06-27**

A point-in-time summary of where the app stands after this work session. Everything below
is implemented, compiles, and (where noted) was verified in a real browser via Playwright.

---

## How to run / verify locally
- **Start the app:** from the project folder —
  `python -m streamlit run app.py --server.port=8501 --server.headless=true`
  then open http://localhost:8501
- **Demo logins (pre-verified, no email needed):**
  - Premium: `premium@marketsignalpro.com` / `premium1`
  - Free: `demo@marketsignalpro.com` / `demo123`
- **First load** kicks off a ~2-minute background "warm" that scores ~2,500 liquid US stocks
  via Polygon. Discover/Scanner populate once it finishes.
- **Browser test harness** (installed in `.venv`): Playwright + Chromium. Reusable scripts live
  in the scratchpad (sweep / verify_flash / free_gate / verify_anchor, etc.).

---

## What was built / fixed this session

### Signals & scoring
- **Bear / short signals** — 3 new categories (📉 Breakdown, 🐻 Distribution, 🔻 Overbought Fade)
  scored by a separate short-side `bear_conviction` model, with rose "SHORT" badges and a
  "🐻 Bearish & Short" Discover theme. Engine now scores both long and short setups.
- **23 composite categories total** (8 free + 15 premium). All marketing copy updated to match
  (was inconsistently "17"/"20").

### Discover
- **Clickable tiles fixed** — the whole-tile click overlay was broken in-browser; rebuilt with a
  marker-sibling selector + explicit `width/height:100%`. Theme dropdowns, category drill-in, and
  Top-Signal cards all work now (Playwright-verified).
- **Dropdown flash + drill-in lag fixed** — theme toggle ~0.48s and flash-free; category drill-in
  ~0.05s, in-place (no full reload), and **scrolls to the top** of the category view.
- **Free-user gating** — locked categories / Top-Signal cards send free users to Pricing.

### Market Scanner (replaces the old Screener + BI pages)
- Filters the **live scanned universe in-memory** (no more hardcoded yfinance lists) by signal
  category, conviction, direction, RSI, volume, MACD, insider buys, 8-K, days-to-cover, price.
- Built-in market-intelligence summary + signal-combo presets + saved scans.
- Premium-only: **hidden from the free-user nav**; reachable via Pricing / lock screens.

### Stock detail page
- **Signal-on-the-Chart** — Plotly candles with the detected pattern drawn on (breakout line,
  bull-flag pole+box, squeeze bands, breakdown, reversal) + a plain-English caption.
- **Track Record HTML leak fixed** (blank-line gotcha — tiles now joined into one string).
- **Signal Performance correctness** — demo signal entries are now **anchored to live prices**
  so the "since signal" return is consistent with the track record and the real current price
  shows everywhere (the old "-61% / Held 0d" was a stale hardcoded demo entry, not a price bug —
  FLUT really is ~$104, AMD ~$521, etc.). Detail page also prefers warm-scan data on any nav path.

### Pricing / checkout
- Plan cards use **real, reliable CTA buttons** (the overlay didn't click).
- **In-page Stripe checkout** — `_do_checkout` is 3-tier: embedded Elements form → hosted redirect
  → clear "not configured" message (never a silent no-op). `stripe` added to `requirements.txt`.

### Contact
- **In-app email webform** → support@marketsignalpro.com (no more `mailto:`/Outlook popups,
  swept app-wide). **AI support chat** re-prompted with accurate current site facts.

### Branding / misc
- **Brand favicon** (`favicon.svg`) replaces the generic emoji.
- **Faster signup** — verification email sends in a background thread.

---

## Secrets / deploy notes (`.streamlit/secrets.toml`)
- **Local**: `DATABASE_URL` is intentionally **commented out** (file storage is instant + durable
  on disk; Neon's serverless cold-start made local signup slow).
- **For Streamlit Cloud**: UNCOMMENT `DATABASE_URL`, ensure `POLYGON_API_KEY` is present (it was
  missing from the pasted cloud block), add `stripe` (now in requirements), and fill in the real
  **`STRIPE_PUBLISHABLE_KEY`** (`pk_test_…`) to get the in-page card form.
- **To enable, before launch**: 4 Stripe keys (secret + publishable + 2 price IDs), `RESEND_API_KEY`
  for live support/verification email. Rotate any keys shared in chat.
- Licensing: still on Polygon/Massive Stocks Starter ($29/mo Individual) — upgrade to a commercial
  license before selling.

---

## Outstanding / nice-to-have (not blocking)
- Root-cause is closed: prices are correct; demo entries are now anchored. (One-time cold-start
  cost: the demo seed does a few quote lookups when history is first created.)
- `use_container_width` deprecation warnings remain app-wide (cosmetic; works fine).
- Possible future polish: hide the demo signals automatically once real signals accrue (already
  partially true — the seed only fills when history is empty).

---

## Key files
- `app.py` — the ~11.7k-line Streamlit monolith (UI, pages, data, scoring glue).
- `scoring.py` — pure factor/category engine (`COMPOSITE_CATS`, `conviction_score`, `bear_conviction`).
- `signal_engine.py` — signal history, outcome tracking, demo seed (now live-anchored).
- `polygon_adapter.py` / `edgar_adapter.py` / `fred_adapter.py` / `msp_store.py` — data + storage.
- `alerts_worker.py` — cron alert delivery (email/Telegram/push).
- `requirements.txt`, `.streamlit/config.toml`, `favicon.svg`.
- Assistant memory: `C:\Users\cdige\.claude\projects\…\memory\` (per-feature notes + MEMORY.md index).
